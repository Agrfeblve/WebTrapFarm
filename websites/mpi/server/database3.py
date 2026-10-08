import sqlite3
import json
from pprint import pprint


def create_table_for_agent(agent_name: str, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {agent_name} (
        id INTEGER PRIMARY KEY,
        task_id TEXT NOT NULL,
        origin_id TEXT NOT NULL,
        button TEXT,
        value TEXT,
        button_score REAL,
        value_score REAL,
        result REAL,
        finish BOOLEAN,
        benchmark TEXT
    )
    """
    cursor.execute(create_table_sql)
    conn.commit()
    cursor.close()
    conn.close()

def drop_table_for_agent(agent_name: str, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    drop_table_sql = f"""
    DROP TABLE IF EXISTS {agent_name}
    """
    cursor.execute(drop_table_sql)
    conn.commit()
    cursor.close()
    conn.close()

def create_table_for_benchmark(benchmark_name: str, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {benchmark_name} (
        id INTEGER PRIMARY KEY,
        task_id TEXT NOT NULL,
        prompt TEXT NOT NULL,
        website TEXT NOT NULL,
        button_clicked TEXT NOT NULL,
        check_strategy TEXT NOT NULL,
        value_strategy TEXT NOT NULL,
        value_llm TEXT NOT NULL,
        value_string TEXT NOT NULL,
        dataset_subtype TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        tags TEXT NOT NULL,
        source TEXT NOT NULL
    )
    """
    cursor.execute(create_table_sql)
    conn.commit()
    cursor.close()
    conn.close()

def drop_table_for_benchmark(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    drop_table_sql = """
    DROP TABLE IF EXISTS benchmark
    """
    cursor.execute(drop_table_sql)
    conn.commit()
    cursor.close()
    conn.close()

def get_task_info(agent_name: str, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    select_sql = f"""
    SELECT * FROM {agent_name}
    """
    cursor.execute(select_sql)

    field_names = [description[0] for description in cursor.description]

    task_info_list = []
    rows = cursor.fetchall()
    for row in rows:
        # print(row)
        task_info = {field_names[i]: row[i] for i in range(len(field_names))}
        task_info_list.append(task_info)

    conn.commit()
    cursor.close()
    conn.close()

    # pprint(task_info_list)
    return task_info_list

def save_benchmark_info(task_file_path, benchmark_name: str, db_path: str):
    task_list = json.load(open(task_file_path, 'r', encoding='utf-8'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    insert_sql = f"""
    INSERT INTO {benchmark_name} (task_id, prompt, website, button_clicked, check_strategy, value_strategy, value_llm, value_string, dataset_subtype, difficulty, tags, source)
    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    WHERE NOT EXISTS (
        SELECT 1 FROM {benchmark_name} WHERE task_id = ?
    )
    """
    cursor.executemany(insert_sql, [(task["task_id"], task["prompt"], task["website"], task["button_clicked"], task["check_strategy"], task["value_strategy"], task["value_llm"], task["value_string"], task["dataset_subtype"], task["difficulty"], task["tags"], task["source"], task["task_id"]) for task in task_list])

    conn.commit()
    cursor.close()
    conn.close()

def get_benchmark_info(benchmark_name: str, db_path: str):
    assert benchmark_name in ["BrowserArt", "EIA", "AgentBait"], f"benchmark_name must be 'BrowserArt' or 'EIA' or 'AgentBait', but got {benchmark_name}"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    select_sql = f"""
    SELECT * FROM {benchmark_name}
    """
    cursor.execute(select_sql)

    field_names = [description[0] for description in cursor.description]

    task_list = []
    rows = cursor.fetchall()
    for row in rows:
        # print(row)
        task = {field_names[i]: row[i] for i in range(len(field_names))}
        task_list.append(task)

    conn.commit()
    cursor.close()
    conn.close()

    return task_list

def get_benchmark_info_2(benchmark_detail_name: str, db_path: str):
    assert benchmark_detail_name in [
        "BrowserArt",
        "EIA_benign",
        "EIA_visible_PII_FI_text",
        # "EIA_visible_PII_FI_aria",
        # "EIA_visible_PII_MI",
        "EIA_visible_request_FI_text",
        "EIA_invisible_PII_FI_text",
        "EIA_invisible_PII_FI_aria",
        "EIA_invisible_PII_MI",
        "EIA_invisible_request_FI_text",
        "EIA_invisible_request_FI_aria",
        "EIA_invisible_request_MI",
    ], f"benchmark_detail_name {benchmark_detail_name} invalid"

    if benchmark_detail_name == "BrowserArt":
        return get_benchmark_info("BrowserArt", db_path)
    elif benchmark_detail_name.startswith("EIA"):
        task_list = get_benchmark_info("EIA", db_path)
        task_list = [task for task in task_list if benchmark_detail_name[3:] in task["task_id"]]
        return task_list

    return []


def calculate_result_for_agent(agent_name: str, db_path: str):
    task_info_list = get_task_info(agent_name, db_path)
    result_list = [task_info["result"] if task_info["result"] is not None else 0 for task_info in task_info_list]
    total = len(result_list)
    avg_score = round(sum(result_list)/total, 2)
    return total, avg_score
