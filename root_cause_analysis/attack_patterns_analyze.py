import sqlite3
import pandas as pd
import numpy as np

RESULT_DB = "../results.db"
TASKS_DB = "../tasks.db"
FLAGS = ["TAS", "FAS", "TAF"]

def load_data_from_sqlite():
    conn = sqlite3.connect(RESULT_DB)
    cursor = conn.cursor()
    cursor.execute(f"ATTACH DATABASE '{TASKS_DB}' AS tasks_db")
    query = """
    SELECT 
        r.benchmark,
        r.flag,
        t.attack_goal,
        t.attack_method,
        t.attack_content
    FROM test r
    JOIN tasks_db.test t ON r.task_id = t.task_id
    WHERE r.flag IN ('TAS', 'FAS', 'TAF')
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['benchmark'] = df['benchmark'].str.upper()
    return df

def compute_sr(df, group_cols):
    pivot = (df.groupby(group_cols + ["flag"]).size().unstack(fill_value=0))
    for f in FLAGS:
        if f not in pivot:
            pivot[f] = 0

    denominator = pivot["TAS"] + pivot["FAS"] + pivot["TAF"]
    pivot["SR"] = pivot["TAF"] / denominator
    pivot["SR"] = pivot["SR"].fillna(0)
    return pivot.reset_index()

def build_dataset_table(df, dataset_name, index_col, col_col):
    sub_df = df[df["benchmark"] == dataset_name.upper()]
    if sub_df.empty:
        return pd.DataFrame()
    sr_df = compute_sr(sub_df, [index_col, col_col])
    table = sr_df.pivot(index=index_col, columns=col_col, values="SR")
    return table

def main():
    df = load_data_from_sqlite()
    with pd.ExcelWriter("Attack_Harm_Severity.xlsx") as writer:
        mup_table = build_dataset_table(df, "MUP", "attack_goal", "attack_content")
        if not mup_table.empty:
            mup_table.to_excel(writer, sheet_name="MUP_Analysis")           
        mpi_table = build_dataset_table(df, "MPI", "attack_method", "attack_content")
        if not mpi_table.empty:
            mpi_table.to_excel(writer, sheet_name="MPI_Analysis")          
        dwd_table = build_dataset_table(df, "DWD", "attack_method", "attack_content")
        if not dwd_table.empty:
            dwd_table.to_excel(writer, sheet_name="DWD_Analysis")

if __name__ == "__main__":
    main()