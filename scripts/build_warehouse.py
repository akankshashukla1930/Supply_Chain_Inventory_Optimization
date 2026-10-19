"""
build_warehouse.py - builds the DuckDB star-schema warehouse and tests every analysis query.

  1. opens/creates warehouse/supply_chain.duckdb
  2. runs sql/01_create_database.sql  (reset + config table)
  3. runs sql/02_create_tables.sql    (star schema with PRIMARY / FOREIGN keys)
  4. loads data/processed/*.csv       (dimensions first, then facts -> FK constraints are enforced)
  5. runs every query in sql/03_analysis_queries.sql and prints its row count (a smoke test)

Run:  python scripts/build_warehouse.py            (build + test)
      python scripts/build_warehouse.py --show Q11  (also print one query's result)
"""
import re
import sys
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "supply_chain.duckdb"
SQL = ROOT / "sql"
P = (ROOT / "data" / "processed").as_posix()


def csv(name):
    return f"read_csv('{P}/{name}.csv', header=true, auto_detect=true)"


LOADS = [
    ("dim_product", f"""INSERT INTO dim_product SELECT Product_ID, Product_Name, Category, Sub_Category, Unit_Cost, Unit_Price,
        Lead_Time_Days_Std, Reorder_Point, Safety_Stock, TRY_CAST(Shelf_Life_Days AS INTEGER) FROM {csv('products')}"""),
    ("dim_supplier", f"INSERT INTO dim_supplier SELECT Supplier_ID, Supplier_Name, City, State, TRY_CAST(Rating AS DECIMAL(3,1)), Payment_Terms FROM {csv('suppliers')}"),
    ("dim_customer", f"INSERT INTO dim_customer SELECT Customer_ID, Customer_Name, Segment, City, State, Region FROM {csv('customers')}"),
    ("dim_warehouse", f"INSERT INTO dim_warehouse SELECT Warehouse_ID, Warehouse_Name, City, State, Region, Capacity_Units, Monthly_Fixed_Cost FROM {csv('warehouses')}"),
    ("dim_date", """INSERT INTO dim_date
        SELECT d::DATE, year(d), quarter(d), month(d), strftime(d, '%b'), strftime(d, '%Y-%m'),
               date_trunc('month', d)::DATE, date_trunc('week', d)::DATE, dayname(d), dayofweek(d) IN (0, 6),
               CASE WHEN month(d) >= 4 THEN 'FY' || year(d) || '-' || right(CAST(year(d) + 1 AS VARCHAR), 2)
                    ELSE 'FY' || (year(d) - 1) || '-' || right(CAST(year(d) AS VARCHAR), 2) END,
               month(d) IN (10, 11)
        FROM range(DATE '2024-01-01', DATE '2026-12-31' + INTERVAL 1 DAY, INTERVAL 1 DAY) t(d)"""),
    ("fact_sales", f"""INSERT INTO fact_sales
        SELECT Sales_ID, Order_Date, Ship_Date, Delivery_Date, Product_ID, Customer_ID, Warehouse_ID, Quantity, Fulfilled_Qty,
               Unit_Price, Discount, Order_Status,
               ROUND(Fulfilled_Qty * Unit_Price * (1 - Discount), 2),
               CASE WHEN Order_Status = 'Cancelled' THEN 0 ELSE Quantity - Fulfilled_Qty END
        FROM {csv('sales')}"""),
    ("fact_purchases", f"""INSERT INTO fact_purchases
        SELECT Purchase_ID, PO_Date, Supplier_ID, Product_ID, Warehouse_ID, Quantity, Received_Qty, Unit_Cost,
               Expected_Delivery_Date, Actual_Delivery_Date, Status,
               date_diff('day', PO_Date, Actual_Delivery_Date), date_diff('day', Expected_Delivery_Date, Actual_Delivery_Date)
        FROM {csv('purchases')}"""),
    ("fact_inventory_snapshot", f"INSERT INTO fact_inventory_snapshot SELECT Snapshot_Date, Product_ID, Warehouse_ID, Stock_Quantity, Reserved_Qty FROM {csv('inventory')}"),
]


def split_queries(text):
    """03 file: each query starts with a line '-- Q01: title'. Returns [(id, title, sql)]."""
    parts = re.split(r"^-- (Q\d+): (.*)$", text, flags=re.M)
    out = []
    for i in range(1, len(parts), 3):
        body = parts[i + 2].strip().rstrip(";")
        body = re.sub(r"^--.*$", "", body, flags=re.M).strip()   # drop trailing comment lines
        out.append((parts[i], parts[i + 1].strip(), body))
    return out


def main():
    DB.parent.mkdir(exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute((SQL / "01_create_database.sql").read_text())
    con.execute((SQL / "02_create_tables.sql").read_text())
    for table, stmt in LOADS:
        con.execute(stmt)
        print(f"loaded {table:26s} {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:>9,d} rows")
    con.execute("""CREATE VIEW v_latest_inventory AS
                   SELECT * FROM fact_inventory_snapshot
                   WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot)""")
    show = sys.argv[sys.argv.index("--show") + 1] if "--show" in sys.argv else None
    failures = 0
    for qid, title, q in split_queries((SQL / "03_analysis_queries.sql").read_text()):
        try:
            df = con.execute(q).df()
            print(f"  {qid} OK  {len(df):>6,d} rows  {title}")
            if qid == show:
                print(df.head(25).to_string())
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  {qid} FAIL {title}: {e}")
    con.close()
    print("ALL QUERIES PASSED" if failures == 0 else f"{failures} QUERY FAILURES")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
