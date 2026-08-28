# WebTrapFarm

## Dataset

For the three datasets, we extracted a subset of sample websites, which are stored in the `mup`, `mpi`, and `dwd` subdirectories under the `websites` folder, respectively.

To launch the environment, run:

```bash
bash start_env.sh
```
This command will start both the frontend and backend servers automatically.

## Scoring

`scoring.py` converts the agent operations collected in `results.db` into quantitative scores according to the predefined scoring rules in `tasks.db`.

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
- `results.db`: Stores the operational logs of Web agents collected through instrumentation.

### Output
The script updates `results.db` with the calculated scores:
- `value_score`: Score for value-based evaluation.
- `button_score`: Score for button-click evaluation.
- `result`: Final combined score based on the task evaluation strategy.

## Reproducing the Chapter 4 Evaluation

The consolidated scripts use the repository's `tasks.db` and `results.db`:

```bash
python evaluation/01_score_tasks.py
python evaluation/02_assign_standard_outcomes.py
python evaluation/03_assign_calibration_outcomes.py
python evaluation/04_compute_end_to_end_metrics.py --output end_to_end_metrics.csv
```

`02_assign_standard_outcomes.py` uses the GPT-4o control runs from the same
harness by default, matching the final evaluation pipeline. Pass
`--reference-model same` to reproduce the earlier per-model-control variant,
or pass both reference arguments to select another fixed configuration.

The `analysis/` directory contains the GLMM input and output artifacts copied
unchanged from the analysis archive. They include the 22,092-row four-state
input, fitted-model RDS files, model summaries, convergence diagnostics,
omnibus tests, and marginal estimates. The supplied archive did not contain
the R source code used to create these artifacts.

## Reproducing the Chapter 5 Attribution

First annotate extracted stage logs using the exact Table 8 pattern names and
binary `safe`/`unsafe` states:

```bash
export WEBTRAP_LLM_API_KEY=YOUR_KEY
python attribution/01_annotate_stage_states.py \
  --input extracted_logs.json --output annotated_logs.json
```

Then assign every Defense Success task a stage label under each of the four
attribution rules:

```bash
python attribution/02_attribute_defense_success.py \
  --harness agent_e --model gpt_4o \
  --logs-json annotated_logs.json \
  --log-harness-key agent_e --log-model-key gpt_4o \
  --output attribution_agent_e_gpt_4o.jsonl
```

The four task-level labels are the paper rule
`longest_contiguous_safe_segment`, the two intentionally incorrect rules
`first_safe_state` and `first_unsafe_to_safe_transition`, and the sensitivity
alternative `last_unsafe_to_safe_transition_with_first_safe_fallback`.
Calibration controls (`WT_*` and `BK_*`) are never treated as attack traces in
stage attribution. See `attribution/README.md` for the complete Table 8 label
taxonomy, input format, rule definitions, and tests.
