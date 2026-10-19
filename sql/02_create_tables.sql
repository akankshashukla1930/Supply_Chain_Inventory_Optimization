-- =====================================================================================
-- 02_create_tables.sql  (DuckDB) - star schema
--   dimensions : dim_product, dim_supplier, dim_customer, dim_warehouse, dim_date
--   facts      : fact_sales (order line), fact_purchases (PO line),
--                fact_inventory_snapshot (weekly stock per product x warehouse)
-- Natural business keys are used as primary keys (they are stable, short and unique).
-- =====================================================================================
CREATE TABLE dim_product (
    product_id          VARCHAR PRIMARY KEY,
    product_name        VARCHAR NOT NULL,
    category            VARCHAR NOT NULL,
    sub_category        VARCHAR NOT NULL,
    unit_cost           DECIMAL(12,2) NOT NULL,
    unit_price          DECIMAL(12,2) NOT NULL,
    lead_time_days_std  INTEGER NOT NULL,
    reorder_point       INTEGER NOT NULL,
    safety_stock        INTEGER NOT NULL,
    shelf_life_days     INTEGER            -- NULL = non-perishable
);

CREATE TABLE dim_supplier (
    supplier_id    VARCHAR PRIMARY KEY,
    supplier_name  VARCHAR NOT NULL,
    city           VARCHAR,
    state          VARCHAR,
    rating         DECIMAL(3,1),           -- NULL = unrated
    payment_terms  VARCHAR
);

CREATE TABLE dim_customer (
    customer_id    VARCHAR PRIMARY KEY,
    customer_name  VARCHAR NOT NULL,
    segment        VARCHAR NOT NULL,
    city           VARCHAR,
    state          VARCHAR,
    region         VARCHAR
);

CREATE TABLE dim_warehouse (
    warehouse_id        VARCHAR PRIMARY KEY,
    warehouse_name      VARCHAR NOT NULL,
    city                VARCHAR,
    state               VARCHAR,
    region              VARCHAR,
    capacity_units      INTEGER NOT NULL,
    monthly_fixed_cost  DECIMAL(14,2) NOT NULL
);

CREATE TABLE dim_date (
    date_key        DATE PRIMARY KEY,
    year            INTEGER,
    quarter         INTEGER,
    month           INTEGER,
    month_name      VARCHAR,
    year_month      VARCHAR,
    month_start     DATE,
    week_start      DATE,
    day_of_week     VARCHAR,
    is_weekend      BOOLEAN,
    fiscal_year     VARCHAR,               -- Indian FY (Apr-Mar), e.g. FY2025-26
    is_festive      BOOLEAN                -- Oct-Nov (Navratri / Diwali season)
);

CREATE TABLE fact_sales (
    sales_id        VARCHAR PRIMARY KEY,
    order_date      DATE NOT NULL REFERENCES dim_date(date_key),
    ship_date       DATE,
    delivery_date   DATE,
    product_id      VARCHAR NOT NULL REFERENCES dim_product(product_id),
    customer_id     VARCHAR NOT NULL REFERENCES dim_customer(customer_id),
    warehouse_id    VARCHAR NOT NULL REFERENCES dim_warehouse(warehouse_id),
    quantity        INTEGER NOT NULL,      -- ordered units
    fulfilled_qty   INTEGER NOT NULL,      -- shipped units (< quantity when stock ran out)
    unit_price      DECIMAL(12,2) NOT NULL,
    discount        DECIMAL(5,2) NOT NULL,
    order_status    VARCHAR NOT NULL,
    net_sales_value DECIMAL(16,2),         -- fulfilled_qty * unit_price * (1 - discount)
    lost_qty        INTEGER                -- unmet demand (excl. customer cancellations)
);

CREATE TABLE fact_purchases (
    purchase_id             VARCHAR PRIMARY KEY,
    po_date                 DATE NOT NULL REFERENCES dim_date(date_key),
    supplier_id             VARCHAR NOT NULL REFERENCES dim_supplier(supplier_id),
    product_id              VARCHAR NOT NULL REFERENCES dim_product(product_id),
    warehouse_id            VARCHAR NOT NULL REFERENCES dim_warehouse(warehouse_id),
    quantity                INTEGER NOT NULL,
    received_qty            INTEGER NOT NULL,
    unit_cost               DECIMAL(12,2) NOT NULL,
    expected_delivery_date  DATE,
    actual_delivery_date    DATE,          -- NULL = open or cancelled PO
    status                  VARCHAR NOT NULL,
    lead_time_days          INTEGER,       -- actual - PO date
    delay_days              INTEGER        -- actual - expected (positive = late)
);

CREATE TABLE fact_inventory_snapshot (
    snapshot_date   DATE NOT NULL REFERENCES dim_date(date_key),
    product_id      VARCHAR NOT NULL REFERENCES dim_product(product_id),
    warehouse_id    VARCHAR NOT NULL REFERENCES dim_warehouse(warehouse_id),
    stock_quantity  INTEGER NOT NULL,
    reserved_qty    INTEGER NOT NULL,
    PRIMARY KEY (snapshot_date, product_id, warehouse_id)
);
