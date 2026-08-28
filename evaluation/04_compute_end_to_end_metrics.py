import os
import pymysql

MYSQL_CONFIG = {}
DATABASES = []
DATABASE_DISPLAY_NAMES = {
    "seeact": "SeeAct",
    "browser_text": "Browser Use (Text)",
    "browser_vision": "Browser Use (Vision)",
    "agent_e": "Agent-E",
    "skyvern_1": "Skyvern 1.0",
    "skyvern_2": "Skyvern 2.0",
}
BENCHMARKS = ["mup", "mpi", "dwd"]
REQUIRED_COLUMNS = {"benchmark", "flag"}

def quote_identifier(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"

def get_all_tables(conn, database: str):
    sql = """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s
          AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
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

def safe_divide(numerator: int, denominator: int):
    if denominator == 0:
        return None
    return numerator / denominator

def format_percent(value):
    if value is None:
        return "--"
    return f"{value * 100:.2f}\\%"

def collect_counts_for_table(conn, database: str, table: str):
    db = quote_identifier(database)
    tb = quote_identifier(table)
    full_table = f"{db}.{tb}"
    sql = f"""
        SELECT
            LOWER(benchmark) AS benchmark,
            SUM(CASE WHEN flag IN ('tas', 'fas') THEN 1 ELSE 0 END) AS numerator,
            SUM(CASE WHEN flag IN ('tas', 'fas', 'taf') THEN 1 ELSE 0 END) AS denominator
        FROM {full_table}
        WHERE LOWER(benchmark) IN ('mpi', 'dwd', 'mup')
          AND flag IN ('tas', 'fas', 'taf')
        GROUP BY LOWER(benchmark)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()

def collect_counts_for_database(conn, database: str):
    benchmark_counts = {
        bm: {"numerator": 0, "denominator": 0}
        for bm in BENCHMARKS
    }
    skipped_tables = []
    tables = get_all_tables(conn, database)
    for table in tables:
        columns = get_table_columns(conn, database, table)
        if not REQUIRED_COLUMNS.issubset(columns):
            skipped_tables.append((table, REQUIRED_COLUMNS - columns))
            continue
        rows = collect_counts_for_table(conn, database, table)
        for row in rows:
            benchmark = row["benchmark"]
            if benchmark not in benchmark_counts:
                continue
            benchmark_counts[benchmark]["numerator"] += int(row["numerator"] or 0)
            benchmark_counts[benchmark]["denominator"] += int(row["denominator"] or 0)
    total_numerator = sum(
        benchmark_counts[bm]["numerator"]
        for bm in BENCHMARKS
    )
    total_denominator = sum(
        benchmark_counts[bm]["denominator"]
        for bm in BENCHMARKS
    )
    result = {
        "database": database,
        "display_name": DATABASE_DISPLAY_NAMES.get(database, database),
        "benchmarks": {},
        "overall": safe_divide(total_numerator, total_denominator),
        "overall_numerator": total_numerator,
        "overall_denominator": total_denominator,
        "skipped_tables": skipped_tables,
    }
    for bm in BENCHMARKS:
        numerator = benchmark_counts[bm]["numerator"]
        denominator = benchmark_counts[bm]["denominator"]
        result["benchmarks"][bm] = {
            "asr": safe_divide(numerator, denominator),
            "numerator": numerator,
            "denominator": denominator,
        }
    return result

def compute_global_overall(results):
    global_counts = {
        bm: {"numerator": 0, "denominator": 0}
        for bm in BENCHMARKS
    }
    for item in results:
        for bm in BENCHMARKS:
            global_counts[bm]["numerator"] += item["benchmarks"][bm]["numerator"]
            global_counts[bm]["denominator"] += item["benchmarks"][bm]["denominator"]
    total_numerator = sum(
        global_counts[bm]["numerator"]
        for bm in BENCHMARKS
    )
    total_denominator = sum(
        global_counts[bm]["denominator"]
        for bm in BENCHMARKS
    )
    global_result = {
        "database": "overall",
        "display_name": "Overall",
        "benchmarks": {},
        "overall": safe_divide(total_numerator, total_denominator),
        "overall_numerator": total_numerator,
        "overall_denominator": total_denominator,
    }
    for bm in BENCHMARKS:
        numerator = global_counts[bm]["numerator"]
        denominator = global_counts[bm]["denominator"]

        global_result["benchmarks"][bm] = {
            "asr": safe_divide(numerator, denominator),
            "numerator": numerator,
            "denominator": denominator,
        }
    return global_result

def print_debug_counts(results):
    print("\n========== Raw Counts ==========")
    for item in results:
        print(f"\n[{item['database']}] {item['display_name']}")
        for bm in BENCHMARKS:
            info = item["benchmarks"][bm]
            print(
                f"  {bm.upper()}: "
                f"{info['numerator']} / {info['denominator']} = "
                f"{format_percent(info['asr'])}"
            )
        print(
            f"  OVERALL: "
            f"{item['overall_numerator']} / {item['overall_denominator']} = "
            f"{format_percent(item['overall'])}"
        )
        if item.get("skipped_tables"):
            print("  Skipped tables:")
            for table, missing in item["skipped_tables"]:
                print(f"    - {table}, missing columns: {missing}")
    global_result = compute_global_overall(results)
    print(f"\n[overall] Overall")
    for bm in BENCHMARKS:
        info = global_result["benchmarks"][bm]
        print(
            f"  {bm.upper()}: "
            f"{info['numerator']} / {info['denominator']} = "
            f"{format_percent(info['asr'])}"
        )
    print(
        f"  OVERALL: "
        f"{global_result['overall_numerator']} / {global_result['overall_denominator']} = "
        f"{format_percent(global_result['overall'])}"
    )

def generate_latex_table(results):
    order = [
        "seeact",
        "browser_text",
        "browser_vision",
        "agent_e",
        "skyvern_1",
        "skyvern_2",
    ]
    result_map = {item["database"]: item for item in results}
    global_result = compute_global_overall(results)
    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{Attack success rates across typical attacks.}")
    lines.append(r"\label{tab:typical_attack_asr}")
    lines.append(r"\begin{tabular}{lcccc}")
    lines.append(r"\toprule")
    lines.append(
        r"\multirow{2}{*}{\textbf{Web Agent}} &"
    )
    lines.append(
        r"\multicolumn{3}{c}{\textbf{Typical Attacks}} &"
    )
    lines.append(
        r"\multirow{2}{*}{\textbf{Overall}} \\"
    )
    lines.append(r"\cmidrule(lr){2-4}")
    lines.append(
        r"& \makecell{MUP}"
        r"& \makecell{MPI}"
        r"& \makecell{DWD}"
        r"& \\"
    )
    lines.append(r"\midrule")
    for db in order:
        if db not in result_map:
            continue
        item = result_map[db]
        name = item["display_name"]
        mup = format_percent(item["benchmarks"]["mup"]["asr"])
        mpi = format_percent(item["benchmarks"]["mpi"]["asr"])
        dwd = format_percent(item["benchmarks"]["dwd"]["asr"])
        overall = format_percent(item["overall"])
        if db == "skyvern_2":
            line = (
                rf"\textbf{{{name}}} & "
                rf"\textbf{{{mup}}} & "
                rf"\textbf{{{mpi}}} & "
                rf"\textbf{{{dwd}}} & "
                rf"\textbf{{{overall}}} \\"
            )
        else:
            line = (
                rf"{name} & "
                rf"{mup} & "
                rf"{mpi} & "
                rf"{dwd} & "
                rf"{overall} \\"
            )
        lines.append(line)
    lines.append(r"\midrule")
    global_mup = format_percent(global_result["benchmarks"]["mup"]["asr"])
    global_mpi = format_percent(global_result["benchmarks"]["mpi"]["asr"])
    global_dwd = format_percent(global_result["benchmarks"]["dwd"]["asr"])
    global_overall = format_percent(global_result["overall"])
    lines.append(
        rf"\textbf{{Overall}} & "
        rf"\textbf{{{global_mup}}} & "
        rf"\textbf{{{global_mpi}}} & "
        rf"\textbf{{{global_dwd}}} & "
        rf"\textbf{{{global_overall}}} \\"
    )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)

def main():
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        results = []
        for database in DATABASES:
            result = collect_counts_for_database(conn, database)
            results.append(result)
        print_debug_counts(results)
        latex = generate_latex_table(results)
        print("\n========== LaTeX Table ==========\n")
        print(latex)
        os.makedirs("table", exist_ok=True)
        with open("table/asr_table.tex", "w", encoding="utf-8") as f:
            f.write(latex)
        print("\nLaTeX table has been saved to: table/asr_table.tex")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
