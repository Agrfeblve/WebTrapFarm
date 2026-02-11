# source 00_vars.sh
benchmark_name="mup"
table_name="test"
benchmark_db_path="benchmark.db"
result_db_path="results.db"

python create_table.py --agent-name "$table_name" --db-path "$result_db_path"

if [[ "$benchmark_name" == "mup" ]]; then
    cd websites/mup
    nohup python -m http.server -d ../websites 8010 --bind 127.0.0.1 > .server8010.log 2>&1 &
    SERVER1_PID=$!
    echo "Static server start, PID: $SERVER1_PID"
    cd text_server
    nohup python server.py --agent-name "$table_name" --db-path "$result_db_path" --benchmark-name "$benchmark_name" --host 0.0.0.0 --port 3003 > .server3003.log 2>&1 &
    SERVER2_PID=$!
    echo "Storage server start, PID: $SERVER2_PID"
    echo "$SERVER1_PID $SERVER2_PID" > ../../../temp_server_pid.log

elif [[ "$benchmark_name" == "mpi" ]]; then
    cd websites/mpi/server
    nohup python frontend_server.py --host 0.0.0.0 --port 8011 > server8011.log 2>&1 &
    SERVER1_PID=$!
    echo "Web server start，PID: $SERVER1_PID"
    nohup python backend_server.py --agent-name "$table_name" --db-path "$result_db_path" --benchmark-name "$benchmark_name" --host 0.0.0.0 --port 3001 > server3001.log 2>&1 &
    SERVER2_PID=$!
    echo "Storage server start，PID: $SERVER2_PID"

elif [[ "$benchmark_name" == "dwd" ]]; then
    cd websites/dwd
    nohup python app.py 2>&1 &
    SERVER1_PID=$!
    echo "Static server start, PID: $SERVER1_PID"
    nohup python server.py --agent-name "$table_name" --db-path "$result_db_path" --benchmark-name "$benchmark_name" --host 0.0.0.0 --port 3002 > .server3002.log 2>&1 &
    SERVER2_PID=$!
    echo "Storage server start, PID: $SERVER2_PID"
    echo "$SERVER1_PID $SERVER2_PID" > ../temp_server_pid.log
fi
