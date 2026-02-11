table_name="test_0119"
result_db_path="C:\Users\cjg_2\Desktop\project\web_agent\benchmark\AgentGuard\mpi\result.db"
benchmark_name="mpi"    # 这就是result数据库中，每一行数据的benchmark

python create_table.py --agent-name "$table_name" --db-path "$result_db_path"

nohup python frontend_server.py --host 0.0.0.0 --port 8011 > server8011.log 2>&1 &
SERVER1_PID=$!
echo "网页服务器启动完成，PID: $SERVER1_PID"

nohup python backend_server.py --agent-name "$table_name" --db-path "$result_db_path" --benchmark-name "$benchmark_name" --host 0.0.0.0 --port 3001 > server3001.log 2>&1 &
SERVER2_PID=$!
echo "存储服务器启动完成，PID: $SERVER2_PID"