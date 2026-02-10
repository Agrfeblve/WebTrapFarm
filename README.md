# WebTrapFarm

## dataset


## anova calculation

The code for performing the Two-way ANOVA (Analysis of Variance) is located in the `anova/` directory, with `anova.py` as the primary script. This analysis is used to quantitatively evaluate the impact of different agent frameworks and backend LLM models on defense performance. We provide `results_example.json` as a example result file to demonstrate the script's calculation process and output.

### usage
To run the anova calculation, navigate to the directory and execute the main script:

```Bash
cd anova/
python anova.py
```

## root cause analysis

### method
The code for root cause analysis(Section 5.2.1) is located in the `root_cause_analysis/` directory, with `agent_log_analysis.py` serving as the main entry point. The workflow is divided into the following four stages:

1. Log Collection: Agent execution logs are collected and saved in a specific JSON format to serve as the input for analysis. You can refer to `agent_log_before_eval.json` for a sample of the required input structure.

2. Automated Labeling: The system evaluates the defense patterns of the agent at each execution step. These labels are then appended to the input JSON file. See ` agent_log_after_eval.json` for an example of a labeled log.

3. Root Cause Attribution: Based on the labeled defense patterns, the script performs a root cause analysis to identify the specific `defense_stage` where the agent first successfully mitigated the attack. The corresponding `defense_pattern` for that stage is recorded. Example output can be found in `root_cause_analysis_result.json`.

4. Stage-wise Metrics: Finally, the system aggregates the results across all test tasks for each agent. It counts the frequency of successful first-time defenses at different execution stages and calculates the Conditional Security Resilience (as discussed in the paper).

### usage
You should first add the LLM configuration in `config.py` to enable LLM calls during the analysis.

To run the analysis, navigate to the directory and execute the main script:

```Bash
cd root_cause_analysis/
python agent_log_analysis.py
```

