from database3 import create_table_for_agent
import argparse

parser = argparse.ArgumentParser(description='Create table for agent')
parser.add_argument('--agent-name', required=True, help='Name of the agent')
parser.add_argument('--db-path', required=True, help='Path to the database file')
args = parser.parse_args()

create_table_for_agent(args.agent_name, args.db_path)