table_name="test_0119"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
result_db_path="${RESULT_DB_PATH:-$script_dir/results.db}"
benchmark_name="mpi"

python create_table.py --agent-name "$table_name" --db-path "$result_db_path"

nohup python frontend_server.py --host 0.0.0.0 --port 8011 > server8011.log 2>&1 &
SERVER1_PID=$!
echo "Web server started, PID: $SERVER1_PID"

nohup python backend_server.py --agent-name "$table_name" --db-path "$result_db_path" --benchmark-name "$benchmark_name" --host 0.0.0.0 --port 3001 > server3001.log 2>&1 &
SERVER2_PID=$!
echo "Storage server started, PID: $SERVER2_PID"
