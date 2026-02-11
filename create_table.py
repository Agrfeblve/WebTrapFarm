import argparse
import sqlite3

parser = argparse.ArgumentParser(description='Create table for agent')
parser.add_argument('--agent-name', required=True, help='Name of the agent')
parser.add_argument('--db-path', required=True, help='Path to the database file')
args = parser.parse_args()

conn = sqlite3.connect(args.db_path)
cursor = conn.cursor()

create_table_sql = f"""
CREATE TABLE IF NOT EXISTS {args.agent_name} (
    id INTEGER PRIMARY KEY,
    task_id TEXT NOT NULL,
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