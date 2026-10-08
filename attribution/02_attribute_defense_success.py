#!/usr/bin/env python3
"""Assign task-level defense activation labels.

The paper uses an attack-surface-specific localization rule:

* User-side attacks (MUP): localize at the first observed safe state.
* Web-side attacks (MPI/DWD): localize at the last observed unsafe-to-safe
  transition.

For web-side attacks, a trace with no unsafe-to-safe transition is unlocalized;
it does not fall back to the first safe state. The previous longest-contiguous-
safe-segment method is retained only as a named legacy sensitivity rule. A
missing activation is emitted as ``null`` rather than being forced into Stage
IV.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ATTACK_TASK_PREFIXES = ("1_", "2_", "3_")
DEFENSE_SUCCESS = "TAF"

PAPER_RULE = "paper_surface_specific"
LONGEST_SEGMENT_RULE = "longest_contiguous_safe_segment_legacy"
FIRST_SAFE_RULE = "first_safe_state"
FIRST_TRANSITION_RULE = "first_unsafe_to_safe_transition"
LAST_TRANSITION_RULE = "last_unsafe_to_safe_transition"
RULES = (
    PAPER_RULE,
    LONGEST_SEGMENT_RULE,
    FIRST_SAFE_RULE,
    FIRST_TRANSITION_RULE,
    LAST_TRANSITION_RULE,
)


@dataclass(frozen=True)
class State:
    round_index: int
    stage: int
    safe: bool


def attack_surface(task_id: str, benchmark: str) -> str:
    if benchmark.lower() == "mup" or task_id.startswith("1_"):
        return "user"
    return "web"


def parse_state(value: Any, task_id: str, round_index: int, stage: int) -> bool:
    normalized = str(value or "").strip().lower()
    if normalized not in {"safe", "unsafe"}:
        raise ValueError(
            f"Invalid state {value!r} for task {task_id}, round {round_index}, "
            f"Stage {stage}; run 01_annotate_stage_states.py first"
        )
    return normalized == "safe"


def observed_trace(
    task_id: str, steps: Iterable[dict[str, Any]], surface: str
) -> list[State]:
    ordered_steps = sorted(steps, key=lambda step: int(step.get("step", 0)))
    trace: list[State] = []
    for position, step in enumerate(ordered_steps):
        round_index = int(step.get("step", position + 1))
        if surface == "user" and position == 0 and "stage_1_state" in step:
            trace.append(
                State(
                    round_index,
                    1,
                    parse_state(step["stage_1_state"], task_id, round_index, 1),
                )
            )
        stages = (3, 4) if surface == "user" else (2, 3, 4)
        for stage in stages:
            key = f"stage_{stage}_state"
            if key not in step:
                continue
            trace.append(
                State(
                    round_index,
                    stage,
                    parse_state(step[key], task_id, round_index, stage),
                )
            )
    return trace


def safe_segments(trace: list[State]) -> list[tuple[int, int]]:
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for index, state in enumerate(trace):
        if state.safe and start is None:
            start = index
        elif not state.safe and start is not None:
            segments.append((start, index - start))
            start = None
    if start is not None:
        segments.append((start, len(trace) - start))
    return segments


def transition_indices(trace: list[State]) -> list[int]:
    return [
        index
        for index in range(1, len(trace))
        if not trace[index - 1].safe and trace[index].safe
    ]


def longest_segment_attribution(trace: list[State], surface: str) -> int | None:
    candidates = safe_segments(trace)
    if surface == "web":
        candidates = [
            (start, length)
            for start, length in candidates
            if start > 0 and not trace[start - 1].safe
        ]
    if not candidates:
        return None
    # Python's max is stable here, so equal-length ties select the earlier run.
    start, _ = max(candidates, key=lambda segment: segment[1])
    return trace[start].stage


def first_safe_attribution(trace: list[State]) -> int | None:
    return next((state.stage for state in trace if state.safe), None)


def first_transition_attribution(trace: list[State]) -> int | None:
    transitions = transition_indices(trace)
    return trace[transitions[0]].stage if transitions else None


def last_transition_attribution(trace: list[State]) -> int | None:
    transitions = transition_indices(trace)
    return trace[transitions[-1]].stage if transitions else None


def paper_attribution(trace: list[State], surface: str) -> int | None:
    if surface == "user":
        return first_safe_attribution(trace)
    return last_transition_attribution(trace)


def apply_rules(trace: list[State], surface: str) -> dict[str, int | None]:
    return {
        PAPER_RULE: paper_attribution(trace, surface),
        LONGEST_SEGMENT_RULE: longest_segment_attribution(trace, surface),
        FIRST_SAFE_RULE: first_safe_attribution(trace),
        FIRST_TRANSITION_RULE: first_transition_attribution(trace),
        LAST_TRANSITION_RULE: last_transition_attribution(trace),
    }


def select_log_root(
    data: dict[str, Any], harness_key: str | None, model_key: str | None
) -> dict[str, list[dict[str, Any]]]:
    selected: Any = data
    if harness_key:
        selected = selected[harness_key]
    elif len(selected) == 1:
        selected = next(iter(selected.values()))
    else:
        raise ValueError("The log JSON has multiple harnesses; pass --log-harness-key")

    if model_key:
        selected = selected[model_key]
    elif len(selected) == 1:
        selected = next(iter(selected.values()))
    else:
        raise ValueError("The log JSON has multiple models; pass --log-model-key")
    return selected


def read_defense_success_tasks(
    path: Path, harness: str, model: str
) -> dict[str, str]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT task_id, LOWER(benchmark) AS benchmark
            FROM test
            WHERE agent = ? AND model = ? AND UPPER(flag) = ?
            """,
            (harness, model, DEFENSE_SUCCESS),
        ).fetchall()
        return {
            str(row["task_id"]): str(row["benchmark"] or "")
            for row in rows
            if str(row["task_id"]).startswith(ATTACK_TASK_PREFIXES)
        }
    finally:
        connection.close()


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "task_id",
        "benchmark",
        "attack_surface",
        "has_stage_trace",
        *RULES,
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-db", type=Path, default=REPOSITORY_ROOT / "log.db")
    parser.add_argument("--harness", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--logs-json", type=Path, required=True)
    parser.add_argument("--log-harness-key")
    parser.add_argument("--log-model-key")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    log_data = json.loads(args.logs_json.read_text(encoding="utf-8"))
    logs = select_log_root(log_data, args.log_harness_key, args.log_model_key)
    tasks = read_defense_success_tasks(args.results_db, args.harness, args.model)

    output_rows: list[dict[str, Any]] = []
    for task_id, benchmark in sorted(tasks.items()):
        surface = attack_surface(task_id, benchmark)
        steps = logs.get(task_id, [])
        trace = observed_trace(task_id, steps, surface)
        output_rows.append(
            {
                "task_id": task_id,
                "benchmark": benchmark,
                "attack_surface": surface,
                "has_stage_trace": bool(trace),
                **apply_rules(trace, surface),
            }
        )

    if args.format == "csv":
        write_csv(args.output, output_rows)
    else:
        write_jsonl(args.output, output_rows)
    print(
        f"Wrote paper and sensitivity attribution labels for "
        f"{len(output_rows)} tasks to {args.output}"
    )


if __name__ == "__main__":
    main()
