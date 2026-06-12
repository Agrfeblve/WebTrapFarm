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
