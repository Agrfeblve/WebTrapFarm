# Skyvern 1.0

This directory runs the `mup`, `mpi`, and `dwd` WebTrapFarm benchmarks with
Skyvern's `skyvern-1.0` engine. It is the cleaned-up counterpart of the
experimental scripts under `web-agent/skyvern`: credentials and machine-local
paths are supplied through environment variables, completed tasks are skipped,
and each run records metadata, API results, screenshots, recordings, and the
original Skyvern artifact tree.

## 1. Configure

From the WebTrapFarm repository root:

```bash
cp agents/Skyvern-1/.env.example agents/Skyvern-1/.env
```

Edit `.env` and set:

- `WEBTRAP_DB_*` to the MySQL database containing the `mup`, `mpi`, and `dwd`
  tables. Each table must provide `task_id`, `prompt`, and `website` columns.
- The model-provider variables used by the Skyvern service.
- `SKYVERN_ACTIVE_MODEL` to the exact model name passed to `--model`.

The runner needs Python 3.11+ and the `requests`, `PyMySQL`, and
`python-dotenv` packages. They are already listed in the repository
requirements.

## 2. Start Skyvern

The compose file builds the checked-in Skyvern source at
`../web-agent/skyvern`, starts PostgreSQL, and exposes the API on port 8000:

```bash
docker compose --env-file agents/Skyvern-1/.env \
  -f agents/Skyvern-1/docker-compose.yml up -d --build
```

On the first start, create an organization and API key:

```bash
docker compose -f agents/Skyvern-1/docker-compose.yml exec skyvern \
  python scripts/create_organization.py WebTrapFarm
```

Copy the printed token into `SKYVERN_API_KEY` in
`agents/Skyvern-1/.env`. The API key authenticates benchmark submissions; it
is not the model-provider key.

## 3. Run a benchmark

Run from the WebTrapFarm repository root:

```bash
python agents/Skyvern-1/run_skyvern1.py \
  --benchmark mpi \
  --model qwen3-vl-235b-a22b-instruct \
  --run-index 2
```

Useful options:

- `--benchmark {mup,mpi,dwd,all}` selects one or all benchmark tables.
- `--workers N` controls parallel API tasks (default: 10).
- `--max-steps N` sets the Skyvern 1.0 task step limit (default: 10).
- `--timeout SECONDS` cancels a run after the deadline (default: 500).
- `--task-limit N` runs only the first N pending tasks for a smoke test.
- `--log-root PATH` changes the output root (default: `logs`).

For example, validate the setup with one task:

```bash
python agents/Skyvern-1/run_skyvern1.py \
  --benchmark mup --model qwen3-vl-235b-a22b-instruct \
  --run-index 1 --task-limit 1
```

Results are written to:

```text
logs/<model>/<benchmark>_<run-index>/
├── run_metadata.json
├── failed_tasks.json
└── <task-id>/
    ├── <task-id>_<timestamp>.json
    ├── assets/
    └── <skyvern-run-id>/
```

Re-running the same model, benchmark, and run index skips task directories
that already contain output. Use a new `--run-index`, or remove only the
specific task directory you explicitly want to rerun.

## Stop the service

```bash
docker compose -f agents/Skyvern-1/docker-compose.yml down
```
