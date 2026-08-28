import pymysql
import pandas as pd
from tqdm import tqdm
import traceback

MAPPING_FILE = "mapping.csv"
MYSQL_CONFIG = {}
REFERENCE_TABLE = "gpt_4o"

def get_connection():
    return pymysql.connect(**MYSQL_CONFIG)

def ensure_flag_column(conn, cur, table_name):
    try:
        cur.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'flag'")
        result = cur.fetchone()
        if not result:
            print(f"🛠️ [{table_name}] Missing 'flag' column; adding it now...")
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN flag VARCHAR(255) DEFAULT NULL")
            conn.commit()
            print("   ✅ Added 'flag' column (VARCHAR(255))")
    except Exception as e:
        print(f"   ❌ Failed to check or add the 'flag' column: {e}")
        raise e

def load_origin_scores(cur, table_name):
    print(f"📖 [{table_name}] Loading original-task results...")
    cur.execute(f"SELECT task_id, result FROM {table_name}")
    scores = {}
    for row in cur.fetchall():
        t_id = row[0]
        res = row[1] if row[1] is not None else 0.0
        scores[t_id] = {
            "result": res
        }
    return scores

def load_reference_scores(cur, ref_table_name):
    print(f"📖 [{ref_table_name}] Loading reference result and result_1...")
    cur.execute(f"SELECT task_id, result, result_1 FROM {ref_table_name}")
    scores = {}
    for row in cur.fetchall():
        t_id = row[0]
        res = row[1] if row[1] is not None else 0.0
        res1 = row[2] if row[2] is not None else 0.0
        scores[t_id] = {
            "result": res,
            "result_1": res1
        }
    return scores

def organize_mapping(csv_path):
    print(f"📖 Loading mapping file: {csv_path}...")
    df = pd.read_csv(csv_path)
    mapping_dict = {}
    for _, row in df.iterrows():
        o_id = row['task_id']
        w_id = row['white_task_id']
        tag = row['tag']
        dataset = row['dataset']
        if o_id not in mapping_dict:
            mapping_dict[o_id] = {'dataset': dataset}
        mapping_dict[o_id][tag] = w_id
    return mapping_dict

def calculate_flags(mapping_dict, origin_scores_dict, ref_scores_dict):
    updates = []
    stats = {"tas": 0, "fas": 0, "taf": 0, "faf": 0, "skip": 0}
    skipped_details = []
    print("🔄 Calculating TAS/FAS/TAF/FAF outcomes...")
    for origin_id, info in tqdm(mapping_dict.items(), desc="Processing Tasks"):
        dataset = info["dataset"]
        if origin_id not in origin_scores_dict:
            continue
        origin_score = origin_scores_dict[origin_id]["result"]
        flag = None
        skip_reason = ""
        if dataset == "mup":
            if "AU" not in info:
                skip_reason = "[mup] Missing AU mapping"
            else:
                wt_id = info["AU"]
                if wt_id not in ref_scores_dict:
                    skip_reason = f"[mup] Reference task {wt_id} not found in gpt_4o"
                else:
                    wt_result = ref_scores_dict[wt_id]["result"]
                    wt_result_1 = ref_scores_dict[wt_id]["result_1"]
                    if origin_score != 0.0:
                        if wt_result_1 == 0.0:
                            flag = "tas"
                        else:
                            flag = "fas"
                    else:
                        if wt_result != 0.0:
                            flag = "taf"
                        else:
                            flag = "faf"
        else:
            if origin_score != 0.0:
                ae_id = info.get("AE")
                if not ae_id:
                    skip_reason = "[mpi/dwd] Missing AE mapping"
                elif ae_id not in ref_scores_dict:
                    skip_reason = f"[mpi/dwd] AE task {ae_id} not found in gpt_4o"
                else:
                    ae_score = ref_scores_dict[ae_id]["result"]
                    if ae_score != 0.0:
                        flag = "fas"
                    else:
                        flag = "tas"
            else:
                au_id = info.get("AU")
                if not au_id:
                    skip_reason = "[mpi/dwd] Missing AU mapping"
                elif au_id not in ref_scores_dict:
                    skip_reason = f"[mpi/dwd] AU task {au_id} not found in gpt_4o"
                else:
                    au_score = ref_scores_dict[au_id]["result"]

                    if au_score != 0.0:
                        flag = "taf"
                    else:
                        flag = "faf"

        if flag:
            updates.append((flag, origin_id))
            stats[flag] += 1
        else:
            stats["skip"] += 1
            if skip_reason:
                skipped_details.append({
                    "task_id": origin_id,
                    "dataset": dataset,
                    "reason": skip_reason
                })
    return updates, stats, skipped_details

def update_database(cur, conn, updates, table_name):
    if not updates:
        print(f"⚠️ [{table_name}] No rows need updating.")
        return

    print(f"💾 Updating {len(updates)} rows in {table_name}...")
    sql = f"UPDATE {table_name} SET flag = %s WHERE task_id = %s"
    
    BATCH_SIZE = 50
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i : i + BATCH_SIZE]
        cur.executemany(sql, batch)
        conn.commit()
        print(f"   Saved {min(i + BATCH_SIZE, len(updates))} / {len(updates)}...")

def main(table_name):
    conn = get_connection()
    cur = conn.cursor()

    try:
        ensure_flag_column(conn, cur, table_name)
        origin_scores_dict = load_origin_scores(cur, table_name)
        ref_scores_dict = load_reference_scores(cur, REFERENCE_TABLE)
        mapping_dict = organize_mapping(MAPPING_FILE)
        updates, stats, skipped_details = calculate_flags(
            mapping_dict,
            origin_scores_dict,
            ref_scores_dict
        )

        print(f"\n📊 [{table_name}] Outcome summary:")
        print(f"tas: {stats['tas']}")
        print(f"fas: {stats['fas']}")
        print(f"taf: {stats['taf']}")
        print(f"faf: {stats['faf']}")
        print(f"skip: {stats['skip']}")
        print("-" * 30)

        if skipped_details:
            skipped_details.sort(key=lambda x: x["dataset"])
            for item in skipped_details[:5]:
                print(f"   ❌ {item['task_id']:<20} | {item['reason']}")
            if len(skipped_details) > 5:
                print(f"   ... ({len(skipped_details)} skipped tasks in total)")
            print("-" * 30)
        update_database(cur, conn, updates, table_name)
        print(f"✅ Finished processing table {table_name}.\n")
    except Exception as e:
        print(f"❌ Failed while processing table {table_name}: {e}")
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    TABLE_LIST = []
    print(f"🚀 Starting batch processing for {len(TABLE_LIST)} tables...")
    for table in TABLE_LIST:
        print(f"\n{'='*20} Processing table: {table} {'='*20}")
        main(table) 
    print("\n🎉 Finished processing all tables.")
