import json
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols

# mock the exp results (assign TAS/FAS/TAF/FAF flag to each task)
def get_exp_results(results_file):
    with open(results_file, "r", encoding="utf-8") as f:
        x = json.load(f)
    return x

def get_score_from_dict(dic):
    if dic['flag'] in ["TAS", "FAS"]:
        return 0    # indicate defense failure
    elif dic['flag'] in ["TAF"]:
        return 1    # indicate defense success
    else:
        return -1

def calculate_anova_results(x, agent_list, model_list):
    data_records = []

    for agent in agent_list:
        for model in model_list:
            if model in x.get(agent, {}):
                for item in x[agent][model]:
                    score = get_score_from_dict(item)
                    if score != -1:
                        data_records.append({
                            'agent': agent,
                            'model': model,
                            'y': score
                        })

    df = pd.DataFrame(data_records)
    print(f"Total valid samples (N_valid): {len(df)}")

    formula = 'y ~ C(agent) + C(model) + C(agent):C(model)'
    model_fit = ols(formula, data=df).fit()

    # Type III ANOVA
    anova_table = sm.stats.anova_lm(model_fit, typ=3)

    # calculate Partial Eta Squared
    # formula：SS_effect / (SS_effect + SS_error)
    ss_error = anova_table.loc['Residual', 'sum_sq']
    anova_table['eta_p_sq'] = anova_table['sum_sq'] / (anova_table['sum_sq'] + ss_error)

    # output format：Agent, Model, Interaction (C(agent):C(model))
    results = anova_table.loc[['C(agent)', 'C(model)', 'C(agent):C(model)']]
    results.index = ['Agent Framework', 'Backend Model', 'Interaction']
    
    return results[['df', 'F', 'PR(>F)', 'eta_p_sq']]


# step 1: collect exp results (assign TAS/FAS/TAF/FAF flag to each task)
# results_example.json is an example of the result (not true exp results)
x = get_exp_results("results_example.json")

# step 2: anova
# we use the following agent/models as an example
agent_list = ["agent_e", "browser_text", "seeact"]
model_list = ["claude_3_7","gpt_4o", "gpt_5_1", "qwen_30b"]
anova_results = calculate_anova_results(x, agent_list, model_list)
print("\n--- ANOVA Analysis Results ---")
print(anova_results)