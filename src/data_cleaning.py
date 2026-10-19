"""
data_cleaning.py - cleans data/raw/*.csv  ->  data/processed/*.csv

This is the ONLY place where data quality is fixed. The SQL warehouse (scripts/build_warehouse.py)
and Power BI (powerquery/*.pq) both load data/processed/, so cleaning logic is never duplicated.
Every fix is written to data/processed/data_quality_log.csv (table, issue, rows, action).

Rules applied
-------------
All tables : trim/collapse whitespace; canonical casing for categorical text; exact-duplicate
             rows removed; duplicate business keys removed (keep first).
Dates      : raw files mix ISO (YYYY-MM-DD), Indian DD/MM/YYYY and DD-Mon-YYYY -> parsed explicitly
             (never let pandas guess day/month order) and written back as ISO.
'NA' text  : converted to real nulls.
products   : missing Unit_Cost imputed = Unit_Price / median price-to-cost markup of its category.
customers  : missing State inferred from City (city -> most common state).
sales      : negative Quantity = sign error -> abs(); Delivered/Returned lines must have
             Quantity == Fulfilled_Qty (fixes x100 keying outliers); missing Discount imputed with
             the segment median; missing Customer_ID mapped to 'C00000' (Unknown customer) so revenue
             is not lost; Fulfilled_Qty capped at Quantity.
purchases  : negative Received_Qty -> abs(); Unit_Cost > 10x the product's median PO cost
             (keying outlier) replaced by that median; Received_Qty capped at Quantity.
inventory  : negative Stock_Quantity = system error -> interpolated from neighbouring weekly
             snapshots of the same product-warehouse; missing Reserved_Qty -> 0.

Run:  python src/data_cleaning.py
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
LOG = []


def log(table, issue, rows, action):
    LOG.append({"Table": table, "Issue": issue, "Rows_Affected": int(rows), "Action": action})


def read(name):
    # keep_default_na=False + explicit list so that 'NA' is recognised but nothing else surprising
    return pd.read_csv(RAW / f"{name}.csv", dtype=str, keep_default_na=False, na_values=["", "NA", "N/A", "null", "NULL"])


def tidy_text(df, table):
    changed = 0
    for c in df.select_dtypes(include="object").columns:
        new = df[c].str.strip().str.replace(r"\s+", " ", regex=True)
        changed += int((new.fillna("") != df[c].fillna("")).sum())
        df[c] = new
    log(table, "Leading/trailing/double spaces in text", changed, "Trimmed and collapsed whitespace")
    return df


def canon_case(df, col, table):
    """Map case variants to the most frequent spelling (e.g. 'ELECTRONICS' -> 'Electronics')."""
    key = df[col].str.lower()
    best = df.groupby(key)[col].agg(lambda s: s.value_counts().index[0])
    new = key.map(best)
    n = int((new.fillna("") != df[col].fillna("")).sum())
    df[col] = new
    log(table, f"Inconsistent casing in {col}", n, "Mapped to most frequent spelling")
    return df


def title_if_shouted(df, col, table):
    m = df[col].notna() & (df[col].str.isupper() | df[col].str.islower())
    df.loc[m, col] = df.loc[m, col].str.title().str.replace(r"\b(\w)(\d+)\b", lambda x: x.group(0).upper(), regex=True)
    log(table, f"ALL-CAPS / lower-case values in {col}", m.sum(), "Converted to Title Case")
    return df


def parse_dates(s, table, col):
    s = s.str.strip()
    iso = pd.to_datetime(s.where(s.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)), format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(s.where(s.str.match(r"^\d{2}/\d{2}/\d{4}$", na=False)), format="%d/%m/%Y", errors="coerce")
    mon = pd.to_datetime(s.where(s.str.match(r"^\d{2}-[A-Za-z]{3}-\d{4}$", na=False)), format="%d-%b-%Y", errors="coerce")
    out = iso.fillna(dmy).fillna(mon)
    n_alt = int(dmy.notna().sum() + mon.notna().sum())
    bad = int((s.notna() & out.isna()).sum())
    log(table, f"Mixed date formats in {col} (DD/MM/YYYY, DD-Mon-YYYY)", n_alt, "Parsed explicitly to ISO date")
    if bad:
        log(table, f"Unparseable {col}", bad, "Set to null")
    return out


def dedupe(df, table, key=None):
    n0 = len(df)
    df = df.drop_duplicates()
    log(table, "Exact duplicate rows", n0 - len(df), "Removed")
    if key:
        n1 = len(df)
        df = df.drop_duplicates(subset=key, keep="first")
        if n1 - len(df):
            log(table, f"Duplicate key {key}", n1 - len(df), "Kept first occurrence")
    return df.reset_index(drop=True)


def num(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ------------------------------------------------------------------ dimensions
def clean_products():
    t = "products"
    df = tidy_text(read(t), t)
    df = canon_case(df, "Category", t)
    df = canon_case(df, "Sub_Category", t)
    df = title_if_shouted(df, "Product_Name", t)
    df = dedupe(df, t, "Product_ID")
    df = num(df, ["Unit_Cost", "Unit_Price", "Lead_Time_Days_Std", "Reorder_Point", "Safety_Stock", "Shelf_Life_Days"])
    log(t, "'NA' text in Shelf_Life_Days (non-perishable items)", df.Shelf_Life_Days.isna().sum(), "Kept as null (not applicable)")
    markup = (df.Unit_Price / df.Unit_Cost).groupby(df.Category).transform("median")
    miss = df.Unit_Cost.isna()
    df.loc[miss, "Unit_Cost"] = (df.loc[miss, "Unit_Price"] / markup[miss]).round(2)
    log(t, "Missing Unit_Cost", miss.sum(), "Imputed = Unit_Price / category median markup")
    for c in ["Lead_Time_Days_Std", "Reorder_Point", "Safety_Stock"]:
        df[c] = df[c].astype("int64")
    df["Shelf_Life_Days"] = df.Shelf_Life_Days.astype("Int64")
    return df.sort_values("Product_ID").reset_index(drop=True)


def clean_suppliers():
    t = "suppliers"
    df = tidy_text(read(t), t)
    df = title_if_shouted(df, "Supplier_Name", t)
    df = dedupe(df, t, "Supplier_ID")
    df = num(df, ["Rating"])
    log(t, "'NA' supplier Rating", df.Rating.isna().sum(), "Kept as null (unrated supplier)")
    return df.sort_values("Supplier_ID").reset_index(drop=True)


def clean_customers():
    t = "customers"
    df = tidy_text(read(t), t)
    df = canon_case(df, "City", t)
    df = canon_case(df, "Segment", t)
    df = title_if_shouted(df, "Customer_Name", t)
    df = dedupe(df, t, "Customer_ID")
    city_state = df.dropna(subset=["State"]).groupby("City").State.agg(lambda s: s.mode()[0])
    miss = df.State.isna()
    df.loc[miss, "State"] = df.loc[miss, "City"].map(city_state)
    log(t, "Missing State", miss.sum(), "Inferred from City")
    unknown = pd.DataFrame([{"Customer_ID": "C00000", "Customer_Name": "Unknown Customer", "Segment": "Unknown",
                             "City": "Unknown", "State": "Unknown", "Region": "Unknown"}])
    return pd.concat([unknown, df.sort_values("Customer_ID")], ignore_index=True)


def clean_warehouses():
    t = "warehouses"
    df = tidy_text(read(t), t)
    df = title_if_shouted(df, "City", t)
    df = dedupe(df, t, "Warehouse_ID")
    df = num(df, ["Capacity_Units", "Monthly_Fixed_Cost"])
    return df


# ------------------------------------------------------------------ facts
def clean_sales(customers):
    t = "sales"
    df = tidy_text(read(t), t)
    df = canon_case(df, "Order_Status", t)
    df = dedupe(df, t, "Sales_ID")
    for c in ["Order_Date", "Ship_Date", "Delivery_Date"]:
        df[c] = parse_dates(df[c], t, c)
    df = num(df, ["Quantity", "Unit_Price", "Discount", "Fulfilled_Qty"])
    neg = df.Quantity < 0
    df.loc[neg, "Quantity"] = df.loc[neg, "Quantity"].abs()
    log(t, "Negative Quantity", neg.sum(), "Sign error -> absolute value")
    q1, q3 = df.Quantity.quantile([0.25, 0.75])
    fence = q3 + 3 * (q3 - q1)
    log(t, f"Quantity above IQR fence ({fence:.0f}) - informational", (df.Quantity > fence).sum(), "Reviewed; only rule below changes data")
    full = df.Order_Status.isin(["Delivered", "Returned"]) & (df.Quantity != df.Fulfilled_Qty)
    df.loc[full, "Quantity"] = df.loc[full, "Fulfilled_Qty"]
    log(t, "Delivered line with Quantity != Fulfilled_Qty (x100 keying outliers)", full.sum(), "Quantity set to Fulfilled_Qty")
    over = df.Fulfilled_Qty > df.Quantity
    df.loc[over, "Fulfilled_Qty"] = df.loc[over, "Quantity"]
    log(t, "Fulfilled_Qty > Quantity", over.sum(), "Capped at Quantity")
    big = df.Quantity > 500
    log(t, "Quantity > 500 after fixes (still implausible)", big.sum(), "Dropped")
    df = df[~big]
    miss_c = df.Customer_ID.isna()
    df.loc[miss_c, "Customer_ID"] = "C00000"
    log(t, "Missing Customer_ID", miss_c.sum(), "Mapped to C00000 'Unknown Customer'")
    seg = df.Customer_ID.map(customers.set_index("Customer_ID").Segment)
    med = df.groupby(seg).Discount.transform("median")
    miss_d = df.Discount.isna()
    df.loc[miss_d, "Discount"] = med[miss_d].fillna(df.Discount.median())
    log(t, "'NA' Discount", miss_d.sum(), "Imputed with customer-segment median")
    bad_d = df.Delivery_Date.notna() & (df.Delivery_Date < df.Order_Date)
    log(t, "Delivery_Date before Order_Date", bad_d.sum(), "Set Delivery_Date to null")
    df.loc[bad_d, "Delivery_Date"] = pd.NaT
    df["Quantity"] = df.Quantity.astype("int64")
    df["Fulfilled_Qty"] = df.Fulfilled_Qty.astype("int64")
    return df.sort_values("Sales_ID").reset_index(drop=True)


def clean_purchases():
    t = "purchases"
    df = tidy_text(read(t), t)
    df = canon_case(df, "Status", t)
    df = dedupe(df, t, "Purchase_ID")
    for c in ["PO_Date", "Expected_Delivery_Date", "Actual_Delivery_Date"]:
        df[c] = parse_dates(df[c], t, c)
    log(t, "'NA' Actual_Delivery_Date (open / cancelled POs)", df.Actual_Delivery_Date.isna().sum(), "Kept as null")
    df = num(df, ["Quantity", "Unit_Cost", "Received_Qty"])
    neg = df.Received_Qty < 0
    df.loc[neg, "Received_Qty"] = df.loc[neg, "Received_Qty"].abs()
    log(t, "Negative Received_Qty", neg.sum(), "Sign error -> absolute value")
    med = df.groupby("Product_ID").Unit_Cost.transform("median")
    out = df.Unit_Cost > 10 * med
    df.loc[out, "Unit_Cost"] = med[out]
    log(t, "Unit_Cost > 10x product median (keying outlier)", out.sum(), "Replaced with product median PO cost")
    over = df.Received_Qty > df.Quantity
    df.loc[over, "Received_Qty"] = df.loc[over, "Quantity"]
    log(t, "Received_Qty > Quantity", over.sum(), "Capped at Quantity")
    df["Quantity"] = df.Quantity.astype("int64")
    df["Received_Qty"] = df.Received_Qty.astype("int64")
    return df.sort_values("Purchase_ID").reset_index(drop=True)


def clean_inventory():
    t = "inventory"
    df = read(t)
    df = dedupe(df, t, ["Snapshot_Date", "Product_ID", "Warehouse_ID"])
    df["Snapshot_Date"] = parse_dates(df.Snapshot_Date, t, "Snapshot_Date")
    df = num(df, ["Stock_Quantity", "Reserved_Qty"])
    df = df.sort_values(["Product_ID", "Warehouse_ID", "Snapshot_Date"]).reset_index(drop=True)
    neg = df.Stock_Quantity < 0
    df.loc[neg, "Stock_Quantity"] = np.nan
    g = df.groupby(["Product_ID", "Warehouse_ID"]).Stock_Quantity
    df["Stock_Quantity"] = g.transform(lambda s: s.interpolate(limit_direction="both")).round()
    log(t, "Negative Stock_Quantity (system error)", neg.sum(), "Interpolated from neighbouring weekly snapshots")
    miss = df.Reserved_Qty.isna()
    df.loc[miss, "Reserved_Qty"] = 0
    log(t, "'NA' Reserved_Qty", miss.sum(), "Set to 0")
    df["Reserved_Qty"] = np.minimum(df.Reserved_Qty, df.Stock_Quantity)
    df["Stock_Quantity"] = df.Stock_Quantity.astype("int64")
    df["Reserved_Qty"] = df.Reserved_Qty.astype("int64")
    return df.sort_values(["Snapshot_Date", "Warehouse_ID", "Product_ID"]).reset_index(drop=True)


def check_fk(child, col, parent, pcol, name):
    orphans = int((~child[col].isin(parent[pcol])).sum())
    log(name, f"Orphan {col} (FK check)", orphans, "None found" if orphans == 0 else "INVESTIGATE")
    assert orphans == 0, f"{name}.{col} has {orphans} orphans"


def main():
    raw_rows = {n: len(read(n)) for n in ["products", "suppliers", "customers", "warehouses", "sales", "purchases", "inventory"]}
    products, suppliers, customers, warehouses = clean_products(), clean_suppliers(), clean_customers(), clean_warehouses()
    sales, purchases, inventory = clean_sales(customers), clean_purchases(), clean_inventory()
    for df, n in [(sales, "sales"), (purchases, "purchases"), (inventory, "inventory")]:
        check_fk(df, "Product_ID", products, "Product_ID", n)
        check_fk(df, "Warehouse_ID", warehouses, "Warehouse_ID", n)
    check_fk(sales, "Customer_ID", customers, "Customer_ID", "sales")
    check_fk(purchases, "Supplier_ID", suppliers, "Supplier_ID", "purchases")
    out = {"products": products, "suppliers": suppliers, "customers": customers, "warehouses": warehouses,
           "sales": sales, "purchases": purchases, "inventory": inventory}
    for n, df in out.items():
        df.to_csv(OUT / f"{n}.csv", index=False, date_format="%Y-%m-%d")
        print(f"{n:11s} raw {raw_rows[n]:>8,d} -> processed {len(df):>8,d}")
    pd.DataFrame(LOG).to_csv(OUT / "data_quality_log.csv", index=False)
    print(f"data_quality_log.csv: {len(LOG)} checks")


if __name__ == "__main__":
    main()
