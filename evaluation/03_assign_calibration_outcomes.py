import pymysql

MYSQL_CONFIG = {}
DATABASES = []
REQUIRED_COLUMNS = {"task_id", "result", "flag"}

def quote_identifier(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"

def get_all_tables(conn, database: str):
    sql = """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
          AND TABLE_TYPE = 'BASE TABLE'
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (database,))
        return [row["TABLE_NAME"] for row in cursor.fetchall()]

def get_table_columns(conn, database: str, table: str):
    sql = """
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (database, table))
        return {row["COLUMN_NAME"] for row in cursor.fetchall()}

def update_bk_3_tasks(conn, database: str, table: str):
    db = quote_identifier(database)
    tb = quote_identifier(table)
    full_table = f"{db}.{tb}"
    sql = f"""
        UPDATE {full_table} AS bk
        LEFT JOIN {full_table} AS wt
          ON wt.task_id = CONCAT('wt_3', SUBSTRING(bk.task_id, LENGTH('bk_3') + 1))
        SET bk.flag = CASE
            WHEN COALESCE(bk.result, 0) <> 0 THEN 'tas'
            WHEN COALESCE(wt.result, 0) <> 0 THEN 'taf'
            ELSE 'faf'
        END
        WHERE bk.task_id LIKE 'bk\\_3%';
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return cursor.rowcount

def update_wt_2_tasks(conn, database: str, table: str):
    db = quote_identifier(database)
    tb = quote_identifier(table)
    full_table = f"{db}.{tb}"
    sql = f"""
        UPDATE {full_table} AS wt
        LEFT JOIN {full_table} AS bk
          ON bk.task_id = CONCAT('bk_2', SUBSTRING(wt.task_id, LENGTH('wt_2') + 1))
        SET wt.flag = CASE
            WHEN COALESCE(wt.result, 0) <> 0 THEN 'tas'
            WHEN COALESCE(bk.result, 0) <> 0 THEN 'taf'
            ELSE 'faf'
        END
        WHERE wt.task_id LIKE 'wt\\_2%';
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return cursor.rowcount

def process_database(conn, database: str):
    print(f"\n========== Processing database: {database} ==========")
    tables = get_all_tables(conn, database)
    if not tables:
        print(f"[WARN] No tables found in database: {database}")
        return
    for table in tables:
        columns = get_table_columns(conn, database, table)
        if not REQUIRED_COLUMNS.issubset(columns):
            missing = REQUIRED_COLUMNS - columns
            print(f"[SKIP] {database}.{table}, missing columns: {missing}")
            continue
        try:
            bk3_count = update_bk_3_tasks(conn, database, table)
            wt2_count = update_wt_2_tasks(conn, database, table)
            print(
                f"[OK] {database}.{table}: "
                f"updated bk_3 rows = {bk3_count}, "
                f"updated wt_2 rows = {wt2_count}"
            )
        except Exception as e:
            print(f"[ERROR] Failed on {database}.{table}: {e}")
            raise

def main():
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        for database in DATABASES:
            process_database(conn, database)
        conn.commit()
        print("\nAll updates committed successfully.")
    except Exception as e:
        conn.rollback()
        print("\nError occurred. All changes rolled back.")
        print(f"Reason: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
