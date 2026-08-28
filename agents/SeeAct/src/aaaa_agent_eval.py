import argparse
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from config_loader import PROJECT_ROOT, get_llm_profile, load_app_config
from data_sender import delete_seaweed_directory


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_WORKERS = 20

parser = argparse.ArgumentParser()
parser.add_argument(
    "--task-config-file",
    required=True,
    help="Path to the task configuration file",
)
args = parser.parse_args()

app_config = load_app_config()
llm, _llm_config = get_llm_profile()
configured_db_path = Path(app_config["database"]["result_db_path"])
result_db_path = str(
    configured_db_path
    if configured_db_path.is_absolute()
    else PROJECT_ROOT / configured_db_path
)
table_name = app_config["database"]["result_table_name"]
seaweedfs_root_dir = app_config["seaweedfs"]["root_dir"]


def run_agent_task(task_config):
    """Run one agent evaluation task."""
    with sqlite3.connect(result_db_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT 1 FROM {table_name} WHERE task_id = ?",
            (task_config["task_id"],),
        )
        result = cursor.fetchone()

    if result:
        print(f"Task ID {task_config['task_id']} already exists; skipping")
        return {"task_id": task_config["task_id"], "status": "success", "returncode": 0}

    print(f"[{datetime.now()}] Starting task ID: {task_config['task_id']}")
    logger_dir = f"{task_config['cjg_logger_dir']}/{llm}/{task_config['task_id']}"
    command = [
        sys.executable,
        os.path.join(CURRENT_DIR, "aaaa_agent.py"),
        "--cjg_logger_dir",
        logger_dir,
        "--prompt",
        task_config["prompt"],
        "--max_steps",
        str(task_config["max_steps"]),
        "--starting_website",
        str(task_config["website"]),
        "-c",
        os.path.join(CURRENT_DIR, "config/cjg_demo_mode.toml"),
        "--task_id",
        task_config["task_id"],
    ]

    process_env = os.environ.copy()
    process_env["PYTHONIOENCODING"] = "utf-8"

    if os.path.exists(logger_dir):
        import shutil

        shutil.rmtree(logger_dir)
    os.makedirs(logger_dir, exist_ok=True)

    try:
        with open(os.path.join(logger_dir, "stdout.log"), "w", encoding="utf-8") as log_file:
            process = subprocess.run(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=process_env,
                cwd=CURRENT_DIR,
                check=False,
            )

        print(
            f"[{datetime.now()}] Task ID {task_config['task_id']} finished "
            f"with return code {process.returncode}"
        )

        if process.returncode != 0:
            with sqlite3.connect(result_db_path) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    f"DELETE FROM {table_name} WHERE task_id = ?",
                    (task_config["task_id"],),
                )

            remote_logger_dir = logger_dir[
                logger_dir.find("cjg_logger") + len("cjg_logger\\"):
            ]
            remote_logger_dir = remote_logger_dir[remote_logger_dir.find("/") :]
            delete_seaweed_directory(f"/{seaweedfs_root_dir}{remote_logger_dir}")

        return {
            "task_id": task_config["task_id"],
            "status": "success",
            "returncode": process.returncode,
        }
    except Exception as exc:
        error_log = os.path.join(task_config["cjg_logger_dir"], "error.log")
        with open(error_log, "w", encoding="utf-8") as log_file:
            log_file.write(f"Task execution failed: {exc}")
        print(f"[{datetime.now()}] Task ID {task_config['task_id']} failed: {exc}")
        return {"task_id": task_config["task_id"], "status": "error", "error": str(exc)}


def main():
    try:
        with open(args.task_config_file, "r", encoding="utf-8") as task_file:
            task_configs = json.load(task_file)

        print(f"Loaded {len(task_configs)} task configurations")
        print(f"Starting execution with up to {MAX_WORKERS} concurrent workers")

        completed_task_ids = []
        task_configs = [
            task_config
            for task_config in task_configs
            if task_config["task_id"] not in completed_task_ids
        ]
        failed_tasks = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_task = {
                executor.submit(run_agent_task, task_config): task_config
                for task_config in task_configs
            }
            completed_count = 0
            for future in as_completed(future_to_task):
                task_config = future_to_task[future]
                try:
                    future.result()
                    completed_count += 1
                    print(
                        f"[{datetime.now()}] Completed "
                        f"{completed_count}/{len(task_configs)} tasks"
                    )
                except Exception as exc:
                    print(
                        f"[{datetime.now()}] Task {task_config['task_id']} "
                        f"raised an exception: {exc}"
                    )
                    failed_tasks.append(task_config["task_id"])

        print(f"[{datetime.now()}] All tasks finished")
        print(f"Failed task IDs: {failed_tasks}")
    except Exception as exc:
        print(f"Evaluation failed: {exc}")
        raise


if __name__ == "__main__":
    main()
