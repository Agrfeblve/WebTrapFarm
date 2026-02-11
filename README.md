# WebTrapFarm

## dataset

For the three datasets, we extracted a subset of sample websites, which are stored in the mup, mpi, and dwd subdirectories under the websites folder respectively. To launch the environment, run the command `bash start_env.sh` and this will start both the frontend and backend servers automatically.

## evaluation
To evaluate the performance of Web agents on MUP, MPI, and DWD, we designed a series of scripts in Chapter 4 to enable automated assessment. To ensure you can use these scripts, you should first configure the LLM settings in config.py to enable LLM calls during the analysis.  

To evaluate, navigate to the directory and execute the following script:

```Bash
cd evaluation/
python step1_evaluation.py
python step2_notate.py
python step3_analyze.py
```

`step1_evaluation.py` is designed to convert the agent's operations collected through instrumentation into scores according to predefined rules, and evaluate whether the task has been successfully attacked. `step2_notate.py` labels the type (TAS/FAS/TAF/FAF) by comparing against the control task corresponding to the original task.`step3_analyze.py` calculates and statistics the Harm Severity and Security Resilience metrics from the dimensions of dataset, model, and agent.

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

