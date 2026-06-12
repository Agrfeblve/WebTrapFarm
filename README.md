# WebTrapFarm

## dataset

For the three datasets, we extracted a subset of sample websites, which are stored in the mup, mpi, and dwd subdirectories under the websites folder respectively. To launch the environment, run the command `bash start_env.sh` and this will start both the frontend and backend servers automatically.

## Score
To score the performance of Web agents on MUP, MPI, and DWD, we designed a series of scripts in Chapter 4 to enable automated assessment. Specifically, `tasks.db` and `results.db` serve as sample files for the task dataset and result dataset, respectively. `tasks.db` contains user prompts, website urls, scoring rules, and corresponding attack configurations, while `results.db` stores the operational logs of agents. To ensure you can use these scripts, you should first configure the LLM settings in config.py to enable LLM calls during the analysis.  

To evaluate, navigate to the directory and execute the following script:

```Bash
python scoring.py
```

`scoring.py` is designed to convert the agent's operations in `results.db` collected through instrumentation into scores according to predefined rules in `tasks.db`, and evaluate whether the task has been successfully attacked. 
