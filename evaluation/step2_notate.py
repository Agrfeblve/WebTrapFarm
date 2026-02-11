import sqlite3
import re
from tqdm import tqdm

TASK_DB = "../tasks.db"
RESULT_DB = "../result_test.db"

def get_db_conn(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def main():
    t_conn = get_db_conn(TASK_DB)
    r_conn = get_db_conn(RESULT_DB)
    t_cur = t_conn.cursor()
    r_cur = r_conn.cursor()

    try:
        r_cur.execute("SELECT task_id, model, agent, result FROM test")
        scores = {}
        for row in r_cur.fetchall():
            scores[(row['task_id'], row['model'], row['agent'])] = row['result'] if row['result'] is not None else 0.0

        t_cur.execute("SELECT task_id, origin_id, benchmark FROM test WHERE task_id NOT LIKE 'WT%' AND task_id NOT LIKE 'BK%'")
        original_tasks = t_cur.fetchall()

        t_cur.execute("SELECT task_id, origin_id, benchmark FROM test WHERE task_id LIKE 'WT%' OR task_id LIKE 'BK%'")
        white_tasks = t_cur.fetchall()

        mapping_pool = {}
        mpi_mapping_pool = {}
        for w in white_tasks:
            ds = w['benchmark']
            tid = w['task_id']
            oid = w['origin_id']
            w_type = 'WT' if tid.startswith('WT') else 'BK'

            if ds == 'mup':
                m_key = tid
                if (ds, m_key) not in mapping_pool:
                    mapping_pool[(ds, m_key)] = {}
                mapping_pool[(ds, m_key)][w_type] = tid
            elif ds == 'dwd':
                m_key = oid
                if (ds, m_key) not in mapping_pool:
                    mapping_pool[(ds, m_key)] = {}
                mapping_pool[(ds, m_key)][w_type] = tid
            elif ds == 'mpi':
                match = re.search(r"(?:WT\d+_|BK\d+_)?(\d+_[a-zA-Z0-9]+)", oid)
                if match:
                    kp = match.group(1)
                    if kp not in mpi_mapping_pool:
                        mpi_mapping_pool[kp] = {}
                    mpi_mapping_pool[kp][w_type] = tid

        updates = []
        stats = {"TAS": 0, "FAS": 0, "TAF": 0, "FAF": 0}

        r_cur.execute("SELECT task_id, model, agent, result FROM test WHERE task_id NOT LIKE 'WT%' AND task_id NOT LIKE 'BK%'")
        agent_results = r_cur.fetchall()
        task_attr = {row['task_id']: (row['origin_id'], row['benchmark']) for row in original_tasks}

        for res_row in tqdm(agent_results, desc="Labeling"):
            tid = res_row['task_id']
            model = res_row['model']
            agent = res_row['agent']
            origin_score = res_row['result'] if res_row['result'] is not None else 0.0

            if tid not in task_attr:
                continue
            oid, ds = task_attr[tid]

            ae_tid, au_tid = None, None

            if ds == 'mup':
                parts = tid.split('_')
                if len(parts) == 2:
                    white_tid = f"WT_{parts[0]}_{ (int(parts[1])-1)//4 + 1 }"
                    black_tid = f"BK_{parts[0]}_{ (int(parts[1])-1)//4 + 1 }"
                    ae_tid = black_tid
                    au_tid = white_tid
            elif ds == 'dwd':
                parts = oid.split('_')
                if len(parts) >= 2:
                    parts[-2] = 'white'
                    target_oid = "_".join(parts)
                    ae_tid = mapping_pool.get((ds, target_oid), {}).get('BK')
                    au_tid = mapping_pool.get((ds, target_oid), {}).get('WT')
            elif ds == 'mpi':
                match = re.search(r"MPI_(\d+_[a-zA-Z0-9]+)_", oid)
                if match:
                    kp = match.group(1)
                    tids = mpi_mapping_pool.get(kp, {})
                    ae_tid = tids.get('WT')
                    au_tid = tids.get('BK')

            flag = "UNKNOWN"
            if origin_score != 0.0:
                ae_score = scores.get((ae_tid, model, agent), 0.0)
                flag = "FAS" if ae_score != 0.0 else "TAS"
            else:
                au_score = scores.get((au_tid, model, agent), 0.0)
                flag = "TAF" if au_score != 0.0 else "FAF"

            updates.append((flag, tid, model, agent))
            if flag in stats:
                stats[flag] += 1

        r_cur.execute("BEGIN TRANSACTION")
        r_cur.executemany("UPDATE test SET flag = ? WHERE task_id = ? AND model = ? AND agent = ?", updates)
        r_conn.commit()

    finally:
        t_conn.close()
        r_conn.close()

if __name__ == "__main__":
    main()