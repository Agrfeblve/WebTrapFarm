# WebTrapFarm

## Dataset

For the three datasets, we extracted a subset of sample websites, which are stored in the `mup`, `mpi`, and `dwd` subdirectories under the `websites` folder, respectively.

To launch the environment, run:

```bash
bash start_env.sh
```
This command will start both the frontend and backend servers automatically.

## Scoring

`scoring.py` converts agent operations collected in a local result database into
quantitative scores according to the predefined scoring rules in `tasks.db`.
Result databases and collected trajectories are not included in this
code-only release.

The script evaluates task success based on one of the following strategies:

- **`value`**: whether the agent submitted or generated the expected value.
- **`button`**: whether the agent clicked the expected button.
- **`value&button`**: whether both the expected value and button-click behavior are satisfied.

For tasks that use the **`llm`** scoring strategy, make sure the LLM settings in `config.py` are properly configured before running the script.

### Usage

```bash
cd evaluation/
python scoring.py
```

### Input Files
- `tasks.db`: Contains user prompts, website URLs, scoring rules, and corresponding attack configurations.
- Result database (not included): Stores operational logs collected through
  instrumentation.

### Output
The script updates the supplied result database with the calculated scores:
- `value_score`: Score for value-based evaluation.
- `button_score`: Score for button-click evaluation.
- `result`: Final combined score based on the task evaluation strategy.

## Harness Security Evaluation

The consolidated scripts operate on the experiment databases configured by
the user. Experimental result databases are not included in this release:

```bash
python evaluation/01_score_tasks.py
python evaluation/02_assign_standard_outcomes.py
python evaluation/03_assign_calibration_outcomes.py
python evaluation/04_compute_end_to_end_metrics.py --output end_to_end_metrics.csv
```

`02_assign_standard_outcomes.py` uses the GPT-4o control runs from the same
harness by default, matching the final evaluation pipeline. Pass
`--reference-model same` to select the earlier per-model-control variant,
or pass both reference arguments to select another fixed configuration.

The `evaluation/05_glmm/` directory contains the analysis notebooks. Private
model inputs, fitted artifacts, collected trajectories, and experiment results
are not part of this code-only release.

## Harness Component Security Analysis

First annotate extracted stage logs using the exact Table 8 pattern names and
binary `safe`/`unsafe` states:

```bash
export WEBTRAP_LLM_API_KEY=YOUR_KEY
python attribution/01_annotate_stage_states.py \
  --input extracted_logs.json --output annotated_logs.json
```

Then localize the defense stage for every Defense Success task using the
attack-surface-specific rule, together with explicitly named sensitivity
rules:

```bash
python attribution/02_attribute_defense_success.py \
  --results-db /path/to/results.db \
  --harness agent_e --model gpt_4o \
  --logs-json annotated_logs.json \
  --log-harness-key agent_e --log-model-key gpt_4o \
  --output attribution_agent_e_gpt_4o.jsonl
```

The canonical output field is `paper_surface_specific`. It localizes user-side
attacks at the first observed safe state and web-side attacks at the last
observed unsafe-to-safe transition. A web-side trace without such a transition
is left unlocalized (`null`); it does not fall back to the first safe state.
An additional longest-safe-segment method is retained as
`longest_contiguous_safe_segment_legacy` for sensitivity analysis.
Calibration controls (`WT_*` and `BK_*`) are never treated as attack traces in
defense-stage localization. See `attribution/README.md` for the complete Table
8 label taxonomy, input format, and localization rules.
