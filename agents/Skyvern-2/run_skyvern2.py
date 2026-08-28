"""Run the WebTrapFarm benchmarks through a Skyvern 2.0 API service."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pymysql
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


BENCHMARKS = ("mup", "mpi", "dwd")
TERMINAL_STATUSES = {"completed", "failed", "terminated"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark", choices=(*BENCHMARKS, "all"), required=True
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=500.0)
    parser.add_argument("--task-limit", type=int)
    parser.add_argument("--log-root", type=Path, default=Path("logs"))
    return parser.parse_args()


def require_environment(model: str) -> tuple[dict[str, object], str, str, Path]:
    names = (
        "WEBTRAP_DB_HOST",
        "WEBTRAP_DB_PORT",
        "WEBTRAP_DB_USER",
        "WEBTRAP_DB_PASSWORD",
        "WEBTRAP_DB_NAME",
        "SKYVERN_API_KEY",
    )
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))

    active_model = os.getenv("SKYVERN_ACTIVE_MODEL") or os.getenv("OPENAI_MODEL")
    if not active_model:
        raise RuntimeError(
            "Set SKYVERN_ACTIVE_MODEL to the model configured in the Skyvern service"
        )
    if active_model.casefold() != model.casefold():
        raise RuntimeError(
            f"Requested model {model!r}, but the Skyvern service is configured as "
            f"{active_model!r}"
        )

    db_config = {
        "host": os.environ["WEBTRAP_DB_HOST"],
        "port": int(os.environ["WEBTRAP_DB_PORT"]),
        "user": os.environ["WEBTRAP_DB_USER"],
        "password": os.environ["WEBTRAP_DB_PASSWORD"],
        "database": os.environ["WEBTRAP_DB_NAME"],
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }
    api_base = os.getenv("SKYVERN_API_BASE", "http://127.0.0.1:8000/v1").rstrip("/")
    artifacts_root = Path(os.getenv("SKYVERN_ARTIFACTS_ROOT", "artifacts")).resolve()
    return db_config, api_base, os.environ["SKYVERN_API_KEY"], artifacts_root


def model_slug(model: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in model).strip("_")


def fetch_tasks(db_config: dict[str, object], benchmark: str) -> list[dict[str, str]]:
    connection = pymysql.connect(**db_config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT task_id, prompt, website FROM `{benchmark}` ORDER BY task_id ASC"
            )
            rows = cursor.fetchall()
    finally:
        connection.close()
    return [
        {
            "task_id": row["task_id"],
            "confirmed_task": row["prompt"],
            "website": row["website"],
        }
        for row in rows
    ]


def create_session(api_key: str) -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"Content-Type": "application/json", "X-API-Key": api_key})
    return session


def replace_localhost(text: str) -> str:
    return text.replace("127.0.0.1", "host.docker.internal")


def submit_task(
    session: requests.Session,
    api_base: str,
    task: dict[str, str],
    max_steps: int,
) -> str:
    payload = {
        "prompt": replace_localhost(task["confirmed_task"]),
        "url": replace_localhost(task["website"]),
        "engine": "skyvern-2.0",
        "title": task["task_id"],
        "max_steps_per_run": max_steps,
    }
    response = session.post(
        f"{api_base}/run/tasks", json=payload, timeout=300
    )
    response.raise_for_status()
    return response.json()["run_id"]


def cancel_run(session: requests.Session, api_base: str, run_id: str) -> dict:
    try:
        response = session.post(f"{api_base}/runs/{run_id}/cancel", timeout=200)
        return {
            "ok": response.status_code in (200, 202),
            "status_code": response.status_code,
            "body": response.text,
        }
    except Exception as error:
        return {"ok": False, "error": str(error)}


def poll_run(
    session: requests.Session,
    api_base: str,
    run_id: str,
    timeout: float,
) -> dict:
    started = time.monotonic()
    while time.monotonic() - started <= timeout:
        try:
            response = session.get(f"{api_base}/runs/{run_id}", timeout=200)
            response.raise_for_status()
            result = response.json()
            if result.get("status") in TERMINAL_STATUSES:
                return result
        except requests.RequestException as error:
            print(f"Polling {run_id} failed: {error}; retrying in 2 seconds")
        time.sleep(2)
    return {
        "status": "timeout",
        "run_id": run_id,
        "cancellation_result": cancel_run(session, api_base, run_id),
    }


def file_url_to_host_path(file_url: str, artifacts_root: Path) -> Path | None:
    if not file_url.startswith("file://"):
        return None
    parsed = urlparse(file_url)
    try:
        relative = Path(parsed.path).relative_to("/data/artifacts")
    except ValueError:
        return None
    return artifacts_root / relative


def copy_result_artifacts(result: dict, task_dir: Path, artifacts_root: Path) -> dict:
    assets_dir = task_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    recording = result.get("recording_url")
    if recording:
        source = file_url_to_host_path(recording, artifacts_root)
        if source and source.exists():
            destination = assets_dir / source.name
            shutil.copy2(source, destination)
            result["recording_url"] = str(destination)
    screenshots = []
    for value in result.get("screenshot_urls") or []:
        source = file_url_to_host_path(value, artifacts_root)
        if source and source.exists():
            destination = assets_dir / source.name
            shutil.copy2(source, destination)
            screenshots.append(str(destination))
        else:
            screenshots.append(value)
    if "screenshot_urls" in result:
        result["screenshot_urls"] = screenshots
    return result


def archive_run(
    task_dir: Path, run_id: str, artifacts_root: Path
) -> dict[str, object]:
    matches = list(artifacts_root.glob(f"local/*/tasks/{run_id}"))
    if len(matches) != 1:
        return {
            "ok": False,
            "error": f"Expected one artifact directory for {run_id}, found {len(matches)}",
        }
    source = matches[0]
    destination = task_dir / run_id
    if destination.exists():
        return {"ok": True, "skipped": True, "path": str(destination)}
    shutil.copytree(source, destination)
    return {"ok": True, "path": str(destination)}


def save_result(task_dir: Path, task_id: str, result: dict) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (task_dir / f"{task_id}_{timestamp}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def process_task(
    task: dict[str, str],
    api_base: str,
    api_key: str,
    artifacts_root: Path,
    log_dir: Path,
    max_steps: int,
    timeout: float,
) -> tuple[str, bool, str]:
    task_id = task["task_id"]
    session = create_session(api_key)
    try:
        run_id = submit_task(session, api_base, task, max_steps)
        result = poll_run(session, api_base, run_id, timeout)
        task_dir = log_dir / task_id
        result = copy_result_artifacts(result, task_dir, artifacts_root)
        result["artifacts_archive"] = archive_run(task_dir, run_id, artifacts_root)
        save_result(task_dir, task_id, result)
        status = result.get("status", "unknown")
        return task_id, status == "completed", status
    except Exception as error:
        return task_id, False, f"Exception: {error}"
    finally:
        session.close()


def run_benchmark(
    args: argparse.Namespace,
    benchmark: str,
    db_config: dict[str, object],
    api_base: str,
    api_key: str,
    artifacts_root: Path,
) -> None:
    log_dir = args.log_root / model_slug(args.model) / f"{benchmark}_{args.run_index}"
    log_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "agent": "Skyvern 2.0",
        "benchmark": benchmark,
        "model": args.model,
        "run_index": args.run_index,
        "workers": args.workers,
        "max_steps": args.max_steps,
        "timeout": args.timeout,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    (log_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    tasks = fetch_tasks(db_config, benchmark)
    tasks = [
        task
        for task in tasks
        if not (log_dir / task["task_id"]).exists()
        or not any((log_dir / task["task_id"]).iterdir())
    ]
    if args.task_limit is not None:
        tasks = tasks[: args.task_limit]
    print(
        f"Running {benchmark.upper()} with {args.model}: "
        f"{len(tasks)} tasks, {args.workers} workers"
    )

    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                process_task,
                task,
                api_base,
                api_key,
                artifacts_root,
                log_dir,
                args.max_steps,
                args.timeout,
            ): task
            for task in tasks
        }
        for index, future in enumerate(as_completed(futures), start=1):
            task_id, succeeded, status = future.result()
            print(f"[{index}/{len(tasks)}] {task_id}: {status}")
            if not succeeded:
                failures.append((task_id, status))

    (log_dir / "failed_tasks.json").write_text(
        json.dumps(failures, indent=2), encoding="utf-8"
    )
    if failures:
        raise RuntimeError(
            f"{len(failures)} tasks failed; see {log_dir / 'failed_tasks.json'}"
        )


def main() -> None:
    load_dotenv()
    args = parse_args()
    if args.run_index < 1 or args.workers < 1 or args.max_steps < 1:
        raise ValueError("Run index, workers, and max steps must be positive")
    db_config, api_base, api_key, artifacts_root = require_environment(args.model)
    benchmarks = BENCHMARKS if args.benchmark == "all" else (args.benchmark,)
    for benchmark in benchmarks:
        run_benchmark(
            args, benchmark, db_config, api_base, api_key, artifacts_root
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
