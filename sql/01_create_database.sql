-- =====================================================================================
-- 01_create_database.sql  (DuckDB)
-- DuckDB is a single-file analytical database, so "creating the database" = opening the
-- file warehouse/supply_chain.duckdb (done by scripts/build_warehouse.py or the CLI:
--     duckdb warehouse/supply_chain.duckdb < sql/01_create_database.sql
-- This script resets the warehouse objects so the build is fully repeatable.
-- =====================================================================================
DROP VIEW  IF EXISTS v_latest_inventory;
DROP TABLE IF EXISTS fact_inventory_snapshot;
DROP TABLE IF EXISTS fact_purchases;
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_warehouse;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_supplier;
DROP TABLE IF EXISTS dim_product;

-- Business assumptions used by the analysis queries (kept in one place)
CREATE OR REPLACE TABLE config AS
SELECT 0.20 AS holding_cost_pct_per_year,   -- 20%/yr: capital 10% + storage/handling 5% + obsolescence/shrink 5%
       90   AS overstock_cover_days,        -- stock above 90 days of demand = excess
       180  AS dead_stock_days,             -- no sale in 180 days = dead stock
       30   AS review_period_days;          -- planning horizon added to lead time for reorder qty
