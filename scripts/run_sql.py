"""
run_sql.py - run every query in sql/03_analysis_queries.sql against the DuckDB warehouse,
print a preview of each result and save each result to outputs/sql_results/Qnn.csv.

Run from the project root, after `python scripts/build_warehouse.py`:
    python scripts/run_sql.py              # all queries, first 10 rows each
    python scripts/run_sql.py Q05 Q15      # only selected queries
    python scripts/run_sql.py --rows 25    # longer previews
"""
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "supply_chain.duckdb"
OUT = ROOT / "outputs" / "sql_results"
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_colwidth", 40)


def split_queries(text):
    """Each query starts with a line '-- Qnn: title'. Returns [(id, title, sql)]."""
    parts = re.split(r"^-- (Q\d+): (.*)$", text, flags=re.M)
    out = []
    for i in range(1, len(parts), 3):
        body = re.sub(r"^--.*$", "", parts[i + 2], flags=re.M).strip().rstrip(";").strip()
        out.append((parts[i], parts[i + 1].strip(), body))
    return out


def main(argv):
    rows = 10
    if "--rows" in argv:
        rows = int(argv[argv.index("--rows") + 1])
        argv = [a for a in argv if a not in ("--rows", str(rows))]
    selected = set(argv)
    if not DB.exists():
        sys.exit(f"{DB} not found - run `python scripts/build_warehouse.py` first")
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    fails = 0
    queries = split_queries((ROOT / "sql" / "03_analysis_queries.sql").read_text(encoding="utf-8"))
    for qid, title, q in queries:
        if selected and qid not in selected:
            continue
        print("=" * 100, f"\n{qid}: {title}")
        try:
            df = con.execute(q).df()
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"FAILED: {e}")
            continue
        df.to_csv(OUT / f"{qid}.csv", index=False)
        print(f"rows: {len(df)}")
        print(df.head(rows).to_string(index=False))
    con.close()
    print("=" * 100)
    print(f"{len(queries) if not selected else len(selected)} queries run, {fails} failed; results in {OUT.relative_to(ROOT)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
