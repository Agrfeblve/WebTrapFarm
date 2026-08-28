dataset_file="test"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

cd "$script_dir"
python aaaa_agent_eval.py --task-config-file "zzzz_agent_eval_task/$dataset_file.json"
