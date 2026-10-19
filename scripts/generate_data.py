"""
generate_data.py - builds the SYNTHETIC raw dataset for the Supply Chain & Inventory
Optimization project (7 linked CSVs in data/raw/).

!!! SYNTHETIC DATA !!!
No public dataset ships products + suppliers + customers + warehouses + sales + purchases +
inventory snapshots that are linked by keys, so this script simulates a fictional Indian
distribution company ("BharatMart Distribution Pvt Ltd" - not a real company).

How it works (daily simulation, Jan 2024 - Sep 2026, seed 42):
  * Every product x warehouse pair has its own stock level.
  * Customer orders arrive (seasonality: festive Oct-Nov peak, monsoon Jun-Aug dip, +12%/yr trend,
    ABC-skewed demand). Orders are fulfilled from on-hand stock -> partial fills / out-of-stock
    happen naturally when stock runs out.
  * A (s, Q) reorder policy raises purchase orders when stock + on-order <= Reorder_Point.
    Suppliers deliver after a (noisy) lead time, sometimes short.
  * Weekly (Sunday) inventory snapshots are taken from the simulated stock, so
    stock = opening stock + receipts - fulfilled sales (fully consistent).

Patterns deliberately embedded (for the analysis to discover):
  * ~12 "chronic stockout" products (reorder point set too low + unreliable supplier)
  * ~20 products that became obsolete in 2025 but keep getting "push" allocations into
    Kolkata and Chennai -> dead stock accumulates there
  * 4 suppliers with long, highly variable lead times and frequent short deliveries
  * Mumbai (Bhiwandi) warehouse running close to its capacity
  * One-size-fits-all reorder points across warehouses (a realistic policy flaw)

Finally, realistic dirty data is injected into the raw files (duplicates, mixed date formats,
casing/whitespace issues, 'NA' strings, nulls, negative quantities, outliers) so that
src/data_cleaning.py has real work to do.

Run:  python scripts/generate_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-09-30")
DAYS = pd.date_range(START, END, freq="D")
ND = len(DAYS)

# --------------------------------------------------------------------------- warehouses
warehouses = pd.DataFrame({
    "Warehouse_ID": [f"WH0{i}" for i in range(1, 7)],
    "Warehouse_Name": ["Delhi NCR Hub (Gurugram)", "Mumbai Hub (Bhiwandi)", "Bengaluru Hub (Hoskote)",
                       "Kolkata Hub (Dankuni)", "Hyderabad Hub (Shamshabad)", "Chennai Hub (Sriperumbudur)"],
    "City": ["Gurugram", "Bhiwandi", "Bengaluru", "Kolkata", "Hyderabad", "Chennai"],
    "State": ["Haryana", "Maharashtra", "Karnataka", "West Bengal", "Telangana", "Tamil Nadu"],
    "Region": ["North", "West", "South", "East", "South", "South"],
    "Monthly_Fixed_Cost": [3800000, 4500000, 3200000, 2400000, 2700000, 2600000],
})
WH_SHARE = np.array([0.24, 0.27, 0.16, 0.09, 0.13, 0.11])   # share of network demand
NW = len(warehouses)

# --------------------------------------------------------------------------- suppliers
sup_cities = [("Delhi", "Delhi"), ("Noida", "Uttar Pradesh"), ("Ludhiana", "Punjab"), ("Jaipur", "Rajasthan"),
              ("Ahmedabad", "Gujarat"), ("Surat", "Gujarat"), ("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"),
              ("Bengaluru", "Karnataka"), ("Chennai", "Tamil Nadu"), ("Coimbatore", "Tamil Nadu"),
              ("Hyderabad", "Telangana"), ("Kolkata", "West Bengal"), ("Indore", "Madhya Pradesh"),
              ("Kanpur", "Uttar Pradesh"), ("Vadodara", "Gujarat")]
sup_prefix = ["Shree", "Sai", "Om", "Ganesh", "Laxmi", "Bharat", "Apex", "Prime", "Sunrise", "Galaxy", "Royal",
              "Unity", "Pioneer", "Vardhman", "Kaveri", "Narmada", "Everest", "Sterling", "Orient", "Zenith"]
sup_suffix = ["Traders", "Industries", "Enterprises", "Exports", "Manufacturing Co", "Distributors",
              "Suppliers", "Sourcing Pvt Ltd", "Wholesale Co", "Supply Chain LLP"]
NS = 40
names = set()
while len(names) < NS:
    names.add(f"{rng.choice(sup_prefix)} {rng.choice(sup_suffix)}")
names = sorted(names)
rng.shuffle(names)
sc = [sup_cities[i] for i in rng.integers(0, len(sup_cities), NS)]
BAD_SUP = [3, 11, 22, 34]                       # index of the 4 unreliable suppliers
suppliers = pd.DataFrame({
    "Supplier_ID": [f"SUP{i:03d}" for i in range(1, NS + 1)],
    "Supplier_Name": names,
    "City": [c for c, _ in sc], "State": [s for _, s in sc],
    "Rating": np.round(rng.uniform(3.6, 4.9, NS), 1),
    "Payment_Terms": rng.choice(["Net 30", "Net 45", "Net 60", "Advance 50%"], NS, p=[0.4, 0.3, 0.2, 0.1]),
})
suppliers.loc[BAD_SUP, "Rating"] = np.round(rng.uniform(2.6, 3.3, len(BAD_SUP)), 1)
sup_lt_mult = rng.uniform(0.76, 0.92, NS)        # actual LT vs quoted (good suppliers quote with a buffer)
sup_lt_cv = np.full(NS, 0.12)
sup_short_p = np.full(NS, 0.03)
sup_lt_mult[BAD_SUP] = [1.9, 1.6, 2.2, 1.7]
sup_lt_cv[BAD_SUP] = 0.45
sup_short_p[BAD_SUP] = [0.32, 0.25, 0.38, 0.28]

# --------------------------------------------------------------------------- products
CATS = {
    "Electronics": (["Mobile Accessories", "Audio", "Smart Home", "Computer Peripherals"], (300, 15000), 1.0),
    "Home & Kitchen": (["Cookware", "Small Appliances", "Storage", "Cleaning"], (150, 6000), 1.1),
    "Grocery & FMCG": (["Staples", "Beverages", "Snacks", "Packaged Foods"], (25, 600), 2.2),
    "Personal Care": (["Skin Care", "Hair Care", "Oral Care", "Hygiene"], (40, 900), 1.6),
    "Apparel": (["Men", "Women", "Kids", "Footwear"], (200, 3000), 0.9),
    "Furniture": (["Office Chairs", "Tables", "Storage Units"], (2500, 28000), 0.25),
    "Office Supplies": (["Paper", "Writing", "Desk Accessories"], (20, 1200), 1.0),
    "Hardware & Tools": (["Power Tools", "Hand Tools", "Fasteners"], (80, 7000), 0.6),
}
brand_words = ["Nova", "Aarav", "Kriti", "Swift", "Urban", "Desi", "Pristine", "Vega", "Tara", "Indus",
               "Maple", "Orbit", "Zeal", "Ruby", "Agni", "Nimbu", "Saral", "Pukka", "Aster", "Mitra"]
NP = 400
cat_names = list(CATS)
cat_w = np.array([CATS[c][2] for c in cat_names]); cat_w /= cat_w.sum()
pcat = rng.choice(cat_names, NP, p=cat_w)
rows = []
for i, c in enumerate(pcat):
    subs, (lo, hi), _ = CATS[c]
    sub = rng.choice(subs)
    cost = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
    cost = round(cost, 2)
    price = round(cost * rng.uniform(1.18, 1.65), 2)
    rows.append((f"P{i+1:04d}", f"{rng.choice(brand_words)} {sub} {rng.choice(list('ABCDEFGHKLMRSTX'))}{rng.integers(100, 999)}",
                 c, sub, cost, price))
products = pd.DataFrame(rows, columns=["Product_ID", "Product_Name", "Category", "Sub_Category", "Unit_Cost", "Unit_Price"])
products["Shelf_Life_Days"] = np.where(products.Category.isin(["Grocery & FMCG", "Personal Care"]),
                                       rng.choice([90, 180, 270, 365, 540, 730], NP), np.nan)

# primary supplier per product (suppliers specialise loosely by category)
cat_sups = {c: rng.choice(NS, 9, replace=False) for c in cat_names}
prim_sup = np.array([rng.choice(cat_sups[c]) for c in pcat])
sec_sup = np.array([rng.choice(cat_sups[c]) for c in pcat])
quoted_lt = np.where(products.Category.isin(["Furniture", "Electronics"]), rng.integers(12, 30, NP), rng.integers(5, 18, NP))

# demand: ABC skew via lognormal popularity
pop = rng.lognormal(0, 1.25, NP)
CHRONIC = rng.choice(np.argsort(-pop)[:120], 12, replace=False)        # popular items that keep running out
DEAD = rng.choice(np.setdiff1d(np.where(~products.Category.isin(["Grocery & FMCG"]))[0], CHRONIC), 20, replace=False)
prim_sup[CHRONIC] = rng.choice(BAD_SUP, len(CHRONIC))
# make bad suppliers also serve a fair number of other products
extra = rng.choice(np.setdiff1d(np.arange(NP), np.r_[CHRONIC, DEAD]), 40, replace=False)
prim_sup[extra] = rng.choice(BAD_SUP, len(extra))

# orders/day per product-warehouse (calibrated to ~150k orders over the period)
TARGET_ORDERS = 152_000
season_m = {1: 0.95, 2: 0.92, 3: 1.0, 4: 0.98, 5: 0.96, 6: 0.86, 7: 0.80, 8: 0.85, 9: 0.96, 10: 1.32, 11: 1.38, 12: 1.08}
season = np.array([season_m[d.month] for d in DAYS]) * np.where(DAYS.dayofweek >= 5, 1.08, 0.97)
trend = 1 + 0.12 * (np.arange(ND) / 365.0)
festive_extra = {"Electronics": 1.18, "Apparel": 1.22, "Home & Kitchen": 1.10}
dead_change = rng.integers((pd.Timestamp("2025-02-01") - START).days, (pd.Timestamp("2025-08-01") - START).days, NP)
life = np.ones((NP, ND))
for p in DEAD:
    life[p, dead_change[p]:] = 0.04
lam_base = np.outer(pop / pop.sum(), WH_SHARE)                          # (NP, NW)
scale = TARGET_ORDERS / (lam_base.sum() * (season * trend).mean() * ND / 1.0)
scale *= 1.02
lam_base *= scale

# customers
SEGMENTS = ["Retail", "Wholesale", "Online", "Distributor"]
seg_p = [0.52, 0.18, 0.24, 0.06]
cust_city = {
    "North": [("Delhi", "Delhi"), ("Gurugram", "Haryana"), ("Noida", "Uttar Pradesh"), ("Lucknow", "Uttar Pradesh"), ("Jaipur", "Rajasthan"), ("Chandigarh", "Chandigarh"), ("Ludhiana", "Punjab")],
    "West": [("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"), ("Thane", "Maharashtra"), ("Ahmedabad", "Gujarat"), ("Surat", "Gujarat"), ("Nagpur", "Maharashtra"), ("Indore", "Madhya Pradesh")],
    "South": [("Bengaluru", "Karnataka"), ("Mysuru", "Karnataka"), ("Hyderabad", "Telangana"), ("Chennai", "Tamil Nadu"), ("Coimbatore", "Tamil Nadu"), ("Kochi", "Kerala"), ("Vijayawada", "Andhra Pradesh")],
    "East": [("Kolkata", "West Bengal"), ("Howrah", "West Bengal"), ("Bhubaneswar", "Odisha"), ("Patna", "Bihar"), ("Guwahati", "Assam"), ("Ranchi", "Jharkhand")],
}
NC = 2000
c_region = rng.choice(["North", "West", "South", "East"], NC, p=[0.26, 0.28, 0.36, 0.10])
first = ["Sharma", "Gupta", "Agarwal", "Patel", "Reddy", "Iyer", "Nair", "Das", "Banerjee", "Singh", "Khan", "Mehta",
         "Joshi", "Rao", "Kumar", "Verma", "Menon", "Chopra", "Bose", "Shetty", "Jain", "Kapoor", "Pillai", "Sinha"]
kind = {"Retail": ["Kirana Store", "Supermart", "General Store", "Retail Mart"], "Wholesale": ["Wholesale Traders", "Trading Co"],
        "Online": ["E-Store", "Online Retail", "D2C Store"], "Distributor": ["Distributors", "Agencies"]}
c_seg = rng.choice(SEGMENTS, NC, p=seg_p)
c_rows = []
for i in range(NC):
    city, state = cust_city[c_region[i]][rng.integers(len(cust_city[c_region[i]]))]
    c_rows.append((f"C{i+1:05d}", f"{rng.choice(first)} {rng.choice(kind[c_seg[i]])}", c_seg[i], city, state, c_region[i]))
customers = pd.DataFrame(c_rows, columns=["Customer_ID", "Customer_Name", "Segment", "City", "State", "Region"])
wh_region = warehouses.Region.values
cust_by_wh = [np.where(c_region == wh_region[w])[0] for w in range(NW)]
qty_mu = {"Retail": 6.0, "Online": 1.5, "Wholesale": 24, "Distributor": 55}
disc_base = {"Retail": 0.02, "Online": 0.06, "Wholesale": 0.08, "Distributor": 0.11}

# --------------------------------------------------------------------------- policy parameters
# expected units per order and E[q^2] across the segment mix (orders are lumpy)
_q = np.concatenate([np.maximum(1, rng.poisson(qty_mu[s], 20000) + (1 if s in ("Wholesale", "Distributor") else 0))
                     for s in SEGMENTS for _ in range(int(seg_p[SEGMENTS.index(s)] * 20))])
EQ, EQ2 = _q.mean(), (_q ** 2).mean()
lam_wh = lam_base.mean(axis=1)                           # avg orders/day per warehouse (network average)
avg_daily_units = lam_wh * EQ
lt = quoted_lt.astype(float)
safety = np.ceil(1.65 * np.sqrt(lam_wh * EQ2 * lt) + 1).astype(int)    # z=1.65 (~95% cycle service)
rop = np.ceil(avg_daily_units * lt + safety).astype(int)
rop[CHRONIC] = np.maximum(1, (rop[CHRONIC] * 0.25).astype(int))
safety[CHRONIC] = np.maximum(0, (safety[CHRONIC] * 0.2).astype(int))
cover_days = rng.integers(40, 75, NP)
moq = rng.choice([30, 40, 50, 60], NP)                    # supplier minimum order quantity
order_q = np.maximum(np.ceil(avg_daily_units * cover_days / 5) * 5, moq).astype(int)
products["Lead_Time_Days_Std"] = quoted_lt
products["Reorder_Point"] = rop
products["Safety_Stock"] = safety

# --------------------------------------------------------------------------- simulation
on_hand = (rop[:, None] + order_q[:, None] * rng.uniform(0.3, 0.8, (NP, NW))).astype(int)

on_order = np.zeros((NP, NW), dtype=int)
arrivals = {}                       # day index -> list of PO idx
po = {k: [] for k in ["PO_Date", "Supplier_ID", "Product_ID", "Warehouse_ID", "Quantity", "Unit_Cost",
                      "Expected_Delivery_Date", "Actual_Delivery_Date", "Received_Qty", "Status"]}
po_arr_day = []
sales = {k: [] for k in ["Order_Date", "Product_ID", "Customer_ID", "Warehouse_ID", "Quantity", "Unit_Price",
                         "Discount", "Ship_Date", "Delivery_Date", "Order_Status", "Fulfilled_Qty"]}
snap = []
PUSH_WH = [3, 5]                    # Kolkata, Chennai receive push allocations of obsolete items
cost_infl = 1 + 0.045 * (np.arange(ND) / 365.0)
p_ids = products.Product_ID.values
w_ids = warehouses.Warehouse_ID.values
s_ids = suppliers.Supplier_ID.values
cats = products.Category.values
cust_ids = customers.Customer_ID.values
transit_days = {"North": 2, "West": 2, "South": 3, "East": 4}


def place_po(t, p, w, qty, sup):
    q_lt = int(quoted_lt[p])
    act = max(1, int(round(rng.normal(q_lt * sup_lt_mult[sup], q_lt * sup_lt_mult[sup] * sup_lt_cv[sup]))))
    cancelled = rng.random() < 0.01
    short = rng.random() < sup_short_p[sup]
    rec = int(qty * rng.uniform(0.5, 0.9)) if short else qty
    po["PO_Date"].append(DAYS[t]); po["Supplier_ID"].append(s_ids[sup]); po["Product_ID"].append(p_ids[p])
    po["Warehouse_ID"].append(w_ids[w]); po["Quantity"].append(int(qty))
    po["Unit_Cost"].append(round(products.Unit_Cost.iat[p] * cost_infl[t] * rng.uniform(0.97, 1.03), 2))
    po["Expected_Delivery_Date"].append(DAYS[t] + pd.Timedelta(days=q_lt))
    idx = len(po["Status"])
    arr = t + act
    if cancelled:
        po["Actual_Delivery_Date"].append(pd.NaT); po["Received_Qty"].append(0); po["Status"].append("Cancelled")
        arr = t + q_lt
    elif arr > ND - 1:
        po["Actual_Delivery_Date"].append(pd.NaT); po["Received_Qty"].append(0); po["Status"].append("Open")
    else:
        po["Actual_Delivery_Date"].append(DAYS[arr]); po["Received_Qty"].append(rec)
        po["Status"].append("Partially Received" if rec < qty else "Received")
    arrivals.setdefault(arr, []).append(idx)
    on_order[p, w] += qty


cat_fest = np.array([festive_extra.get(c, 1.0) for c in cats])
for t in range(ND):
    d = DAYS[t]
    # 1) receipts
    for idx in arrivals.pop(t, []):
        p = int(po["Product_ID"][idx][1:]) - 1
        w = int(po["Warehouse_ID"][idx][-1]) - 1
        on_hand[p, w] += po["Received_Qty"][idx]
        on_order[p, w] -= po["Quantity"][idx]
    # 2) customer orders
    f = season[t] * trend[t] * np.where(d.month in (10, 11), cat_fest, 1.0)
    lam = lam_base * (f * life[:, t])[:, None]
    n = rng.poisson(lam)
    for p, w in zip(*np.nonzero(n)):
        for _ in range(n[p, w]):
            ci = rng.choice(cust_by_wh[w])
            seg = c_seg[ci]
            q = int(max(1, rng.poisson(qty_mu[seg]) + (1 if seg in ("Wholesale", "Distributor") else 0)))
            status = None
            if rng.random() < 0.015:
                status, ful = "Cancelled", 0
            else:
                ful = min(q, on_hand[p, w])
                on_hand[p, w] -= ful
                if ful == 0:
                    status = "Out of Stock"
                elif ful < q:
                    status = "Partially Delivered"
                else:
                    status = "Delivered"
            price = round(products.Unit_Price.iat[p] * (1 + 0.05 * (t / 365.0)), 2)
            disc = disc_base[seg] + (0.05 if d.month in (10, 11) else 0) + rng.choice([0, 0, 0.02, 0.05])
            ship = deliv = pd.NaT
            if ful > 0:
                ship = d + pd.Timedelta(days=int(rng.integers(0, 3)))
                deliv = ship + pd.Timedelta(days=int(transit_days[c_region[ci]] + rng.integers(0, 4)))
                if deliv > END:
                    deliv = pd.NaT; status = "In Transit"
                    if ship > END:
                        ship = pd.NaT
                elif status == "Delivered" and rng.random() < 0.025:
                    status = "Returned"
            for k, v in zip(sales, [d, p_ids[p], cust_ids[ci], w_ids[w], q, price, round(min(disc, 0.3), 2), ship, deliv, status, ful]):
                sales[k].append(v)
    # 3) replenishment
    need = np.argwhere((on_hand + on_order) <= rop[:, None])
    for p, w in need:
        if life[p, t] < 1 and w not in PUSH_WH:
            continue
        sup = prim_sup[p] if rng.random() < 0.85 else sec_sup[p]
        q = int(order_q[p] * rng.uniform(0.9, 1.3) * (1.0 if w in (0, 1) else 0.8))
        place_po(t, p, w, max(q, 5), sup)
    # push allocations of obsolete stock into Kolkata/Chennai (central planning ignores demand)
    if t % 60 == 0:
        for p in DEAD:
            if life[p, t] < 1:
                for w in PUSH_WH:
                    place_po(t, p, w, int(order_q[p] * rng.uniform(0.6, 1.0)), prim_sup[p])
    # 4) weekly snapshot (Sunday)
    if d.dayofweek == 6:
        snap.append((d, on_hand.copy()))

# --------------------------------------------------------------------------- assemble
sales = pd.DataFrame(sales)
sales.insert(0, "Sales_ID", [f"S{i+1:07d}" for i in range(len(sales))])
purchases = pd.DataFrame(po)
purchases.insert(0, "Purchase_ID", [f"PO{i+1:06d}" for i in range(len(purchases))])
inv_rows = []
for d, oh in snap:
    pp, ww = np.meshgrid(np.arange(NP), np.arange(NW), indexing="ij")
    stock = oh.ravel()
    reserved = rng.binomial(stock, 0.04)
    inv_rows.append(pd.DataFrame({"Snapshot_Date": d, "Product_ID": p_ids[pp.ravel()], "Warehouse_ID": w_ids[ww.ravel()],
                                  "Stock_Quantity": stock, "Reserved_Qty": reserved}))
inventory = pd.concat(inv_rows, ignore_index=True)

# capacity: Bhiwandi runs ~92% full over the last year (peaks above 100% -> overflow storage); others comfortable
wk = inventory.groupby(["Warehouse_ID", "Snapshot_Date"]).Stock_Quantity.sum()
recent = wk[wk.index.get_level_values(1) > END - pd.Timedelta(days=365)].groupby(level=0).mean()
peak = wk.groupby(level=0).max()
cap = []
for w in w_ids:
    c = recent[w] / 0.92 if w == "WH02" else peak[w] / rng.uniform(0.60, 0.75)
    cap.append(int(np.ceil(c / 1000) * 1000))
warehouses.insert(5, "Capacity_Units", cap)
products = products[["Product_ID", "Product_Name", "Category", "Sub_Category", "Unit_Cost", "Unit_Price",
                     "Lead_Time_Days_Std", "Reorder_Point", "Safety_Stock", "Shelf_Life_Days"]]

# --------------------------------------------------------------------------- dirty data injection
def fmt_dates(s, frac):
    """Return date strings, with `frac` of rows written as DD/MM/YYYY or DD-Mon-YYYY."""
    out = s.dt.strftime("%Y-%m-%d").astype(object).copy()
    m = (rng.random(len(s)) < frac) & s.notna()
    alt = rng.random(len(s)) < 0.5
    out[m & alt] = s[m & alt].dt.strftime("%d/%m/%Y")
    out[m & ~alt] = s[m & ~alt].dt.strftime("%d-%b-%Y")
    return out


def messy_case(s, frac):
    s = s.copy().astype(object)
    m = rng.random(len(s)) < frac
    ops = rng.integers(0, 4, len(s))
    for i in np.where(m)[0]:
        v = s.iat[i]
        if not isinstance(v, str):
            continue
        s.iat[i] = [v.upper(), v.lower(), "  " + v, v + " "][ops[i]]
    return s


def add_dups(df, n):
    return pd.concat([df, df.sample(n, random_state=SEED)], ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)


products_raw = products.copy()
products_raw["Category"] = messy_case(products_raw.Category, 0.12)
products_raw["Product_Name"] = messy_case(products_raw.Product_Name, 0.05)
products_raw["Shelf_Life_Days"] = products_raw.Shelf_Life_Days.astype(object).where(products_raw.Shelf_Life_Days.notna(), "NA")
products_raw.loc[rng.choice(NP, 4, replace=False), "Unit_Cost"] = np.nan
products_raw = add_dups(products_raw, 5)

suppliers_raw = suppliers.copy()
suppliers_raw["Supplier_Name"] = messy_case(suppliers_raw.Supplier_Name, 0.15)
suppliers_raw["Rating"] = suppliers_raw.Rating.astype(object)
suppliers_raw.loc[rng.choice(NS, 2, replace=False), "Rating"] = "NA"
suppliers_raw = add_dups(suppliers_raw, 2)

customers_raw = customers.copy()
customers_raw["City"] = messy_case(customers_raw.City, 0.08)
customers_raw["Segment"] = messy_case(customers_raw.Segment, 0.06)
customers_raw.loc[rng.choice(NC, 15, replace=False), "State"] = np.nan
customers_raw = add_dups(customers_raw, 25)

warehouses_raw = warehouses.copy()
warehouses_raw.loc[3, "City"] = " kolkata "

sales_raw = sales.copy()
for c in ["Order_Date", "Ship_Date", "Delivery_Date"]:
    sales_raw[c] = fmt_dates(sales_raw[c], 0.08)
neg = rng.choice(len(sales_raw), 120, replace=False)
sales_raw.loc[neg, "Quantity"] = -sales_raw.loc[neg, "Quantity"]
outl = rng.choice(len(sales_raw), 60, replace=False)
sales_raw.loc[outl, "Quantity"] = sales_raw.loc[outl, "Quantity"] * 100
sales_raw["Discount"] = sales_raw.Discount.astype(object)
sales_raw.loc[rng.choice(len(sales_raw), 900, replace=False), "Discount"] = "NA"
sales_raw["Order_Status"] = messy_case(sales_raw.Order_Status, 0.04)
sales_raw.loc[rng.choice(len(sales_raw), 150, replace=False), "Customer_ID"] = np.nan
sales_raw = add_dups(sales_raw, 900)

purchases_raw = purchases.copy()
for c in ["PO_Date", "Expected_Delivery_Date", "Actual_Delivery_Date"]:
    purchases_raw[c] = fmt_dates(purchases_raw[c], 0.08)
purchases_raw["Actual_Delivery_Date"] = purchases_raw.Actual_Delivery_Date.fillna("NA")
negp = rng.choice(len(purchases_raw), 25, replace=False)
purchases_raw.loc[negp, "Received_Qty"] = -purchases_raw.loc[negp, "Received_Qty"]
outp = rng.choice(len(purchases_raw), 15, replace=False)
purchases_raw.loc[outp, "Unit_Cost"] = purchases_raw.loc[outp, "Unit_Cost"] * 1000
purchases_raw["Status"] = messy_case(purchases_raw.Status, 0.04)
purchases_raw = add_dups(purchases_raw, 120)

inventory_raw = inventory.copy()
inventory_raw["Snapshot_Date"] = inventory_raw.Snapshot_Date.dt.strftime("%Y-%m-%d")
negi = rng.choice(len(inventory_raw), 40, replace=False)
inventory_raw.loc[negi, "Stock_Quantity"] = -inventory_raw.loc[negi, "Stock_Quantity"] - 1
inventory_raw["Reserved_Qty"] = inventory_raw.Reserved_Qty.astype(object)
inventory_raw.loc[rng.choice(len(inventory_raw), 300, replace=False), "Reserved_Qty"] = "NA"
inventory_raw = pd.concat([inventory_raw, inventory_raw.sample(400, random_state=SEED)], ignore_index=True)

for name, df in [("products", products_raw), ("suppliers", suppliers_raw), ("customers", customers_raw),
                 ("warehouses", warehouses_raw), ("sales", sales_raw), ("purchases", purchases_raw),
                 ("inventory", inventory_raw)]:
    df.to_csv(RAW / f"{name}.csv", index=False)
    print(f"{name:11s} {len(df):>8,d} rows")

# ground truth of embedded patterns (for README / validation, not loaded by Power BI)
pd.DataFrame({"Product_ID": p_ids[CHRONIC], "Pattern": "Chronic stockout"}).pipe(
    lambda a: pd.concat([a, pd.DataFrame({"Product_ID": p_ids[DEAD], "Pattern": "Obsolete / pushed to WH04+WH06"})])
).to_csv(ROOT / "data" / "embedded_patterns_answer_key.csv", index=False)
print("bad suppliers:", list(s_ids[BAD_SUP]))
