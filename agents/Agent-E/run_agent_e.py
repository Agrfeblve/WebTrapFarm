"""Run the WebTrapFarm benchmarks with Agent-E."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import multiprocessing
import os
import random
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pymysql

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


BENCHMARKS = ("mup", "mpi", "dwd")
TASK_FILTERS = {
    "mup": "",
    "mpi": "WHERE task_id LIKE '2\\_%' OR task_id LIKE 'WT\\_2\\_%'",
    "dwd": "WHERE task_id LIKE '3\\_%' OR task_id LIKE 'BK\\_3\\_%'",
}
DEFAULT_WORKERS = {"mup": 5, "mpi": 3, "dwd": 3}


@dataclass(frozen=True)
class RunConfig:
    benchmark: str
    model: str
    run_index: int
    workers: int
    max_retries: int
    retry_delay: float
    log_dir: str
    failed_file: str


class LoggerWriter:
    def __init__(self, logger: logging.Logger, level: int) -> None:
        self.logger = logger
        self.level = level

    def write(self, buffer: str) -> None:
        sys.__stdout__.write(buffer)
        for line in buffer.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self) -> None:
        sys.__stdout__.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark", choices=(*BENCHMARKS, "all"), required=True
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=30.0)
    parser.add_argument("--task-limit", type=int)
    parser.add_argument("--log-root", type=Path, default=Path("logs"))
    return parser.parse_args()


def require_environment() -> dict[str, object]:
    names = (
        "WEBTRAP_DB_HOST",
        "WEBTRAP_DB_PORT",
        "WEBTRAP_DB_USER",
        "WEBTRAP_DB_PASSWORD",
        "WEBTRAP_DB_NAME",
    )
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))
    if not os.getenv("AUTOGEN_MODEL_API_KEY"):
        raise RuntimeError("Missing environment variable: AUTOGEN_MODEL_API_KEY")
    return {
        "host": os.environ["WEBTRAP_DB_HOST"],
        "port": int(os.environ["WEBTRAP_DB_PORT"]),
        "user": os.environ["WEBTRAP_DB_USER"],
        "password": os.environ["WEBTRAP_DB_PASSWORD"],
        "database": os.environ["WEBTRAP_DB_NAME"],
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def model_slug(model: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in model).strip("_")


def build_config(args: argparse.Namespace, benchmark: str) -> RunConfig:
    root = args.log_root / model_slug(args.model) / f"{benchmark}_{args.run_index}"
    return RunConfig(
        benchmark=benchmark,
        model=args.model,
        run_index=args.run_index,
        workers=args.workers or DEFAULT_WORKERS[benchmark],
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        log_dir=str(root),
        failed_file=str(root / "failed_tasks.txt"),
    )


def write_run_metadata(config: RunConfig) -> None:
    path = Path(config.log_dir)
    path.mkdir(parents=True, exist_ok=True)
    metadata = asdict(config)
    metadata["started_at"] = datetime.now(timezone.utc).isoformat()
    metadata["agent"] = "Agent-E"
    (path / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def fetch_tasks(db_config: dict[str, object], benchmark: str) -> list[tuple[str, str, str]]:
    table = benchmark
    where_clause = TASK_FILTERS[benchmark]
    sql = f"""
        SELECT task_id, prompt, website
        FROM `{table}`
        {where_clause}
        ORDER BY task_id ASC
    """
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
    finally:
        connection.close()
    return [(row["task_id"], row["prompt"], row["website"]) for row in rows]


def setup_task_logging(task_id: str, log_dir: str) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = logging.getLogger(f"Task_{task_id}_{os.getpid()}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    handler = logging.FileHandler(
        Path(log_dir) / f"task_{task_id}_{timestamp}.log", encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    )
    logger.addHandler(handler)
    return logger


def run_single_task(
    task_id: str, task_prompt: str, start_url: str, config: RunConfig
) -> bool:
    logger = setup_task_logging(task_id, config.log_dir)
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout = LoggerWriter(logger, logging.INFO)
    sys.stderr = LoggerWriter(logger, logging.ERROR)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def worker() -> bool:
        from ae.core.system_orchestrator import SystemOrchestrator
        import ae.core.playwright_manager as browser_manager

        orchestrator = None
        succeeded = False
        try:
            await asyncio.sleep(random.uniform(1, 10))
            orchestrator = SystemOrchestrator(
                agent_scenario="user,planner_agent,browser_nav_agent,browser_nav_executor",
                input_mode="GUI_ONLY",
                start_url=start_url,
            )
            await orchestrator.initialize()
            await orchestrator.process_command(task_prompt, task_id)
            succeeded = True
        except Exception:
            traceback.print_exc()
        finally:
            if orchestrator is not None:
                try:
                    await orchestrator.shutdown()
                except Exception:
                    traceback.print_exc()
            browser_manager.PlaywrightManager._instance = None
            browser_manager.PlaywrightManager._playwright = None
            browser_manager.PlaywrightManager._browser_context = None
        return succeeded

    try:
        return loop.run_until_complete(worker())
    finally:
        loop.close()
        sys.stdout, sys.stderr = original_stdout, original_stderr


def replace_failed_tasks(path: str, task_ids: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        "".join(f"{task_id}\n" for task_id in task_ids), encoding="utf-8"
    )


def run_benchmark(
    config: RunConfig,
    db_config: dict[str, object],
    task_limit: int | None,
) -> None:
    write_run_metadata(config)
    tasks = fetch_tasks(db_config, config.benchmark)
    pending = tasks[:task_limit] if task_limit is not None else tasks
    print(
        f"Running {config.benchmark.upper()} with {config.model}: "
        f"{len(pending)} tasks, {config.workers} workers"
    )
    started = time.time()

    for attempt in range(config.max_retries + 1):
        if not pending:
            break
        print(f"Attempt {attempt + 1}/{config.max_retries + 1}: {len(pending)} tasks")
        arguments = [(*task, config) for task in pending]
        with multiprocessing.Pool(processes=config.workers) as pool:
            results = pool.starmap(run_single_task, arguments)
        pending = [task for task, succeeded in zip(pending, results) if not succeeded]
        replace_failed_tasks(config.failed_file, [task[0] for task in pending])
        if pending and attempt < config.max_retries:
            time.sleep(config.retry_delay)

    if pending:
        raise RuntimeError(
            f"{len(pending)} tasks failed after {config.max_retries + 1} attempts; "
            f"see {config.failed_file}"
        )
    print(f"Completed {config.benchmark.upper()} in {time.time() - started:.2f}s")


def main() -> None:
    load_dotenv()
    args = parse_args()
    if args.run_index < 1 or args.max_retries < 0:
        raise ValueError("--run-index must be positive and --max-retries non-negative")

    os.environ["AUTOGEN_MODEL_NAME"] = args.model
    db_config = require_environment()
    benchmarks = BENCHMARKS if args.benchmark == "all" else (args.benchmark,)
    for benchmark in benchmarks:
        run_benchmark(build_config(args, benchmark), db_config, args.task_limit)


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    main()
