-- =====================================================================================
-- 03_analysis_queries.sql  (DuckDB)  - one query per business question
-- Every query starts with "-- Qnn: title" (scripts/build_warehouse.py runs and tests each one).
-- Conventions
--   demand        = ordered units excluding customer cancellations (includes demand we failed to serve)
--   units sold    = fulfilled_qty
--   latest stock  = most recent weekly snapshot (v_latest_inventory)
--   assumptions   = table `config` (holding cost 20%/yr, overstock > 90 days cover, dead stock 180 days)
-- =====================================================================================

-- Q01: Warehouse row counts and date coverage (data health check)
SELECT 'fact_sales' AS table_name, COUNT(*) AS row_count, MIN(order_date) AS first_date, MAX(order_date) AS last_date FROM fact_sales
UNION ALL SELECT 'fact_purchases', COUNT(*), MIN(po_date), MAX(po_date) FROM fact_purchases
UNION ALL SELECT 'fact_inventory_snapshot', COUNT(*), MIN(snapshot_date), MAX(snapshot_date) FROM fact_inventory_snapshot
ORDER BY table_name;

-- Q02: Monthly sales trend with MoM growth (LAG) and year-to-date running total
WITH m AS (
    SELECT d.month_start, d.year,
           SUM(s.net_sales_value) AS net_sales,
           SUM(s.fulfilled_qty)   AS units_sold
    FROM fact_sales s JOIN dim_date d ON d.date_key = s.order_date
    GROUP BY d.month_start, d.year
)
SELECT month_start, net_sales, units_sold,
       LAG(net_sales) OVER (ORDER BY month_start) AS prev_month_sales,
       ROUND(100.0 * (net_sales / LAG(net_sales) OVER (ORDER BY month_start) - 1), 1) AS mom_growth_pct,
       ROUND(100.0 * (net_sales / LAG(net_sales, 12) OVER (ORDER BY month_start) - 1), 1) AS yoy_growth_pct,
       SUM(net_sales) OVER (PARTITION BY year ORDER BY month_start ROWS UNBOUNDED PRECEDING) AS ytd_sales
FROM m
ORDER BY month_start;

-- Q03: Which products have the highest demand? Top 20 by units demanded (last 12 months) with RANK and % of total
WITH d AS (
    SELECT p.product_id, p.product_name, p.category,
           SUM(s.quantity) FILTER (WHERE s.order_status <> 'Cancelled') AS units_demanded,
           SUM(s.net_sales_value) AS net_sales
    FROM fact_sales s JOIN dim_product p USING (product_id)
    WHERE s.order_date > (SELECT MAX(order_date) FROM fact_sales) - INTERVAL 12 MONTH
    GROUP BY ALL
)
SELECT RANK() OVER (ORDER BY units_demanded DESC) AS demand_rank, *,
       ROUND(100.0 * units_demanded / SUM(units_demanded) OVER (), 2) AS pct_of_total_units
FROM d
QUALIFY demand_rank <= 20
ORDER BY demand_rank;

-- Q04: ABC classification - cumulative revenue share (A = top 80%, B = next 15%, C = last 5%) + NTILE decile
WITH rev AS (
    SELECT product_id, SUM(net_sales_value) AS net_sales
    FROM fact_sales GROUP BY product_id
), cum AS (
    SELECT product_id, net_sales,
           SUM(net_sales) OVER (ORDER BY net_sales DESC ROWS UNBOUNDED PRECEDING) / SUM(net_sales) OVER () AS cum_share,
           NTILE(10) OVER (ORDER BY net_sales DESC) AS revenue_decile
    FROM rev
)
SELECT CASE WHEN cum_share <= 0.80 THEN 'A' WHEN cum_share <= 0.95 THEN 'B' ELSE 'C' END AS abc_class,
       COUNT(*) AS products,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_products,
       ROUND(SUM(net_sales), 0) AS net_sales,
       ROUND(100.0 * SUM(net_sales) / SUM(SUM(net_sales)) OVER (), 1) AS pct_revenue,
       MIN(revenue_decile) AS best_decile, MAX(revenue_decile) AS worst_decile
FROM cum
GROUP BY abc_class
ORDER BY abc_class;

-- Q05: Which products frequently go out of stock? Stockout-week frequency + lost units (top 15)
WITH so AS (
    SELECT product_id,
           COUNT(*) AS snapshots,
           COUNT(*) FILTER (WHERE stock_quantity = 0) AS stockout_snapshots
    FROM fact_inventory_snapshot GROUP BY product_id
), lost AS (
    SELECT product_id, SUM(lost_qty) AS lost_units,
           SUM(lost_qty * unit_price * (1 - discount)) AS lost_sales_value,
           SUM(quantity) FILTER (WHERE order_status <> 'Cancelled') AS demanded_units
    FROM fact_sales GROUP BY product_id
)
SELECT p.product_id, p.product_name, p.category, s.supplier_name AS main_supplier,
       ROUND(100.0 * so.stockout_snapshots / so.snapshots, 1) AS stockout_rate_pct,
       lost.lost_units, ROUND(lost.lost_sales_value, 0) AS lost_sales_value,
       ROUND(100.0 * (1 - lost.lost_units / lost.demanded_units), 1) AS fill_rate_pct,
       RANK() OVER (ORDER BY so.stockout_snapshots DESC) AS stockout_rank
FROM so JOIN lost USING (product_id) JOIN dim_product p USING (product_id)
LEFT JOIN (SELECT product_id, arg_max(supplier_id, cnt) AS supplier_id
           FROM (SELECT product_id, supplier_id, COUNT(*) AS cnt FROM fact_purchases GROUP BY ALL) GROUP BY product_id) ms USING (product_id)
LEFT JOIN dim_supplier s ON s.supplier_id = ms.supplier_id
QUALIFY stockout_rank <= 15
ORDER BY stockout_rank, lost_units DESC;

-- Q06: Which warehouse holds the most inventory? Latest stock units, value, capacity utilisation, rank
SELECT w.warehouse_name, w.region,
       SUM(i.stock_quantity) AS stock_units,
       ROUND(SUM(i.stock_quantity * p.unit_cost), 0) AS stock_value_inr,
       w.capacity_units,
       ROUND(100.0 * SUM(i.stock_quantity) / w.capacity_units, 1) AS capacity_utilisation_pct,
       RANK() OVER (ORDER BY SUM(i.stock_quantity * p.unit_cost) DESC) AS value_rank
FROM v_latest_inventory i
JOIN dim_product p USING (product_id)
JOIN dim_warehouse w USING (warehouse_id)
GROUP BY w.warehouse_name, w.region, w.capacity_units
ORDER BY value_rank;

-- Q07: Monthly inventory value by warehouse (month-end snapshot) with change vs previous month (LAG)
WITH me AS (
    SELECT warehouse_id, date_trunc('month', snapshot_date) AS month_start, MAX(snapshot_date) AS last_snap
    FROM fact_inventory_snapshot GROUP BY ALL
), val AS (
    SELECT me.warehouse_id, me.month_start, SUM(i.stock_quantity * p.unit_cost) AS stock_value
    FROM me JOIN fact_inventory_snapshot i ON i.warehouse_id = me.warehouse_id AND i.snapshot_date = me.last_snap
    JOIN dim_product p USING (product_id)
    GROUP BY ALL
)
SELECT w.warehouse_name, month_start, ROUND(stock_value, 0) AS stock_value,
       ROUND(stock_value - LAG(stock_value) OVER (PARTITION BY warehouse_id ORDER BY month_start), 0) AS change_vs_prev_month
FROM val JOIN dim_warehouse w USING (warehouse_id)
ORDER BY w.warehouse_name, month_start;

-- Q08: Days of cover per product x warehouse (latest stock / avg daily demand of last 90 days)
WITH dem AS (
    SELECT product_id, warehouse_id, SUM(quantity) / 90.0 AS avg_daily_demand
    FROM fact_sales
    WHERE order_status <> 'Cancelled'
      AND order_date > (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot) - INTERVAL 90 DAY
      AND order_date <= (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot)
    GROUP BY ALL
)
SELECT i.product_id, i.warehouse_id, i.stock_quantity,
       ROUND(COALESCE(dem.avg_daily_demand, 0), 2) AS avg_daily_demand,
       CASE WHEN COALESCE(dem.avg_daily_demand, 0) = 0 THEN NULL
            ELSE ROUND(i.stock_quantity / dem.avg_daily_demand, 0) END AS days_of_cover,
       CASE WHEN i.stock_quantity = 0 THEN 'Stocked out'
            WHEN COALESCE(dem.avg_daily_demand, 0) = 0 THEN 'No recent demand'
            WHEN i.stock_quantity / dem.avg_daily_demand < 14 THEN 'Low (< 14 days)'
            WHEN i.stock_quantity / dem.avg_daily_demand <= 90 THEN 'Healthy (14-90 days)'
            ELSE 'Excess (> 90 days)' END AS cover_band
FROM v_latest_inventory i LEFT JOIN dem USING (product_id, warehouse_id)
ORDER BY days_of_cover DESC NULLS FIRST;

-- Q09: Where is excess inventory accumulating? Value above 90 days of cover, by warehouse and category
WITH dem AS (
    SELECT product_id, warehouse_id, SUM(quantity) / 90.0 AS avg_dd
    FROM fact_sales
    WHERE order_status <> 'Cancelled'
      AND order_date > (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot) - INTERVAL 90 DAY
      AND order_date <= (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot)
    GROUP BY ALL
), ex AS (
    SELECT i.warehouse_id, p.category,
           GREATEST(i.stock_quantity - COALESCE(dem.avg_dd, 0) * (SELECT overstock_cover_days FROM config), 0) AS excess_units,
           p.unit_cost
    FROM v_latest_inventory i JOIN dim_product p USING (product_id) LEFT JOIN dem USING (product_id, warehouse_id)
)
SELECT w.warehouse_name, ex.category,
       SUM(excess_units) AS excess_units,
       ROUND(SUM(excess_units * unit_cost), 0) AS excess_value_inr,
       ROUND(SUM(excess_units * unit_cost) * (SELECT holding_cost_pct_per_year FROM config), 0) AS excess_holding_cost_per_year,
       RANK() OVER (ORDER BY SUM(excess_units * unit_cost) DESC) AS excess_rank
FROM ex JOIN dim_warehouse w USING (warehouse_id)
GROUP BY ALL
HAVING SUM(excess_units) > 0
ORDER BY excess_rank
LIMIT 20;

-- Q10: Dead stock - items with stock on hand but no sale in that warehouse for 180+ days
WITH last_sale AS (
    SELECT product_id, warehouse_id, MAX(order_date) FILTER (WHERE fulfilled_qty > 0) AS last_sale_date
    FROM fact_sales GROUP BY ALL
)
SELECT w.warehouse_name, p.product_id, p.product_name, p.category, i.stock_quantity,
       ROUND(i.stock_quantity * p.unit_cost, 0) AS stock_value_inr,
       ls.last_sale_date,
       date_diff('day', ls.last_sale_date, i.snapshot_date) AS days_since_last_sale
FROM v_latest_inventory i
JOIN dim_product p USING (product_id)
JOIN dim_warehouse w USING (warehouse_id)
LEFT JOIN last_sale ls USING (product_id, warehouse_id)
WHERE i.stock_quantity > 0
  AND (ls.last_sale_date IS NULL
       OR date_diff('day', ls.last_sale_date, i.snapshot_date) >= (SELECT dead_stock_days FROM config))
ORDER BY stock_value_inr DESC;

-- Q11: Which suppliers have longer / less reliable delivery? Lead time, variability, on-time, in-full, OTIF
SELECT s.supplier_id, s.supplier_name, s.rating,
       COUNT(*) AS pos_received,
       ROUND(AVG(f.lead_time_days), 1) AS avg_lead_time_days,
       ROUND(STDDEV_SAMP(f.lead_time_days), 1) AS lead_time_std_dev,
       ROUND(AVG(f.delay_days), 1) AS avg_delay_days,
       ROUND(100.0 * AVG(CASE WHEN f.delay_days <= 0 THEN 1 ELSE 0 END), 1) AS on_time_pct,
       ROUND(100.0 * AVG(CASE WHEN f.received_qty >= f.quantity THEN 1 ELSE 0 END), 1) AS in_full_pct,
       ROUND(100.0 * AVG(CASE WHEN f.delay_days <= 0 AND f.received_qty >= f.quantity THEN 1 ELSE 0 END), 1) AS otif_pct,
       ROUND(100.0 * (1 - SUM(f.received_qty) / SUM(f.quantity)), 1) AS short_units_pct,
       RANK() OVER (ORDER BY AVG(f.delay_days) DESC) AS delay_rank
FROM fact_purchases f JOIN dim_supplier s USING (supplier_id)
WHERE f.actual_delivery_date IS NOT NULL
GROUP BY s.supplier_id, s.supplier_name, s.rating
ORDER BY delay_rank;

-- Q12: Supplier lead-time trend by quarter with change vs previous quarter (LAG) - worst 4 suppliers
WITH q AS (
    SELECT supplier_id, date_trunc('quarter', po_date) AS quarter_start, AVG(lead_time_days) AS avg_lt
    FROM fact_purchases WHERE actual_delivery_date IS NOT NULL GROUP BY ALL
), worst AS (
    SELECT supplier_id FROM fact_purchases WHERE actual_delivery_date IS NOT NULL
    GROUP BY supplier_id ORDER BY AVG(delay_days) DESC LIMIT 4
)
SELECT s.supplier_name, quarter_start, ROUND(avg_lt, 1) AS avg_lead_time_days,
       ROUND(avg_lt - LAG(avg_lt) OVER (PARTITION BY supplier_id ORDER BY quarter_start), 1) AS change_vs_prev_qtr
FROM q JOIN worst USING (supplier_id) JOIN dim_supplier s USING (supplier_id)
ORDER BY s.supplier_name, quarter_start;

-- Q13: Inventory turnover and days inventory outstanding by category (last 12 months)
WITH cogs AS (
    SELECT p.category, SUM(s.fulfilled_qty * p.unit_cost) AS cogs_12m
    FROM fact_sales s JOIN dim_product p USING (product_id)
    WHERE s.order_date > (SELECT MAX(order_date) FROM fact_sales) - INTERVAL 12 MONTH
    GROUP BY ALL
), inv AS (   -- average of weekly network inventory value over the same 12 months
    SELECT category, AVG(v) AS avg_inventory_value FROM (
        SELECT p.category, i.snapshot_date, SUM(i.stock_quantity * p.unit_cost) AS v
        FROM fact_inventory_snapshot i JOIN dim_product p USING (product_id)
        WHERE i.snapshot_date > (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot) - INTERVAL 12 MONTH
        GROUP BY ALL) GROUP BY category
)
SELECT category, ROUND(cogs_12m, 0) AS cogs_12m, ROUND(avg_inventory_value, 0) AS avg_inventory_value,
       ROUND(cogs_12m / avg_inventory_value, 2) AS inventory_turnover,
       ROUND(365 / (cogs_12m / avg_inventory_value), 0) AS days_inventory_outstanding,
       RANK() OVER (ORDER BY cogs_12m / avg_inventory_value) AS slowest_rank
FROM cogs JOIN inv USING (category)
ORDER BY inventory_turnover;

-- Q14: How much does holding inventory cost? Carrying cost (20%/yr) + warehouse fixed cost per unit, by warehouse
WITH v AS (
    SELECT warehouse_id, AVG(val) AS avg_stock_value FROM (
        SELECT i.warehouse_id, i.snapshot_date, SUM(i.stock_quantity * p.unit_cost) AS val
        FROM fact_inventory_snapshot i JOIN dim_product p USING (product_id)
        WHERE i.snapshot_date > (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot) - INTERVAL 12 MONTH
        GROUP BY ALL) GROUP BY warehouse_id
), u AS (
    SELECT warehouse_id, SUM(fulfilled_qty) AS units_shipped_12m FROM fact_sales
    WHERE order_date > (SELECT MAX(order_date) FROM fact_sales) - INTERVAL 12 MONTH GROUP BY ALL
)
SELECT w.warehouse_name,
       ROUND(v.avg_stock_value, 0) AS avg_stock_value,
       ROUND(v.avg_stock_value * c.holding_cost_pct_per_year, 0) AS carrying_cost_per_year,
       ROUND(w.monthly_fixed_cost * 12, 0) AS fixed_cost_per_year,
       ROUND((v.avg_stock_value * c.holding_cost_pct_per_year + w.monthly_fixed_cost * 12) / u.units_shipped_12m, 2) AS total_cost_per_unit_shipped,
       SUM(ROUND(v.avg_stock_value * c.holding_cost_pct_per_year, 0)) OVER () AS network_carrying_cost
FROM v JOIN u USING (warehouse_id) JOIN dim_warehouse w USING (warehouse_id) CROSS JOIN config c
ORDER BY total_cost_per_unit_shipped DESC;

-- Q15: Which products need restocking now? Available stock <= reorder point -> suggested order quantity
WITH dem AS (
    SELECT product_id, warehouse_id, SUM(quantity) / 90.0 AS avg_dd
    FROM fact_sales
    WHERE order_status <> 'Cancelled'
      AND order_date > (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot) - INTERVAL 90 DAY
      AND order_date <= (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot)
    GROUP BY ALL
), open_po AS (
    SELECT product_id, warehouse_id, SUM(quantity) AS on_order
    FROM fact_purchases WHERE status = 'Open' GROUP BY ALL
)
SELECT w.warehouse_name, p.product_id, p.product_name, p.category,
       i.stock_quantity - i.reserved_qty AS available_stock,
       p.reorder_point, COALESCE(o.on_order, 0) AS on_order,
       ROUND(dem.avg_dd, 2) AS avg_daily_demand,
       CEIL(GREATEST(dem.avg_dd * (p.lead_time_days_std + (SELECT review_period_days FROM config)) + p.safety_stock
                     - (i.stock_quantity - i.reserved_qty) - COALESCE(o.on_order, 0), 0)) AS suggested_order_qty,
       CASE WHEN i.stock_quantity - i.reserved_qty <= 0 THEN '1 - Urgent (stocked out)'
            WHEN i.stock_quantity - i.reserved_qty <= p.safety_stock THEN '2 - High (below safety stock)'
            ELSE '3 - Normal (below reorder point)' END AS priority
FROM v_latest_inventory i
JOIN dim_product p USING (product_id)
JOIN dim_warehouse w USING (warehouse_id)
JOIN dem USING (product_id, warehouse_id)
LEFT JOIN open_po o USING (product_id, warehouse_id)
WHERE i.stock_quantity - i.reserved_qty <= p.reorder_point
  AND dem.avg_dd > 0
ORDER BY priority, dem.avg_dd * p.unit_price DESC;

-- Q16: Fill rate by warehouse per year with YoY change (LAG)
WITH y AS (
    SELECT warehouse_id, year(order_date) AS yr,
           SUM(fulfilled_qty) FILTER (WHERE order_status <> 'Cancelled') * 1.0
           / SUM(quantity) FILTER (WHERE order_status <> 'Cancelled') AS fill_rate
    FROM fact_sales GROUP BY ALL
)
SELECT w.warehouse_name, yr, ROUND(100 * fill_rate, 1) AS fill_rate_pct,
       ROUND(100 * (fill_rate - LAG(fill_rate) OVER (PARTITION BY warehouse_id ORDER BY yr)), 1) AS yoy_change_pts
FROM y JOIN dim_warehouse w USING (warehouse_id)
ORDER BY w.warehouse_name, yr;

-- Q17: Sales vs purchases value per month (are we buying more than we sell?) with cumulative gap
WITH s AS (
    SELECT date_trunc('month', s.order_date) AS m, SUM(s.fulfilled_qty * p.unit_cost) AS cogs
    FROM fact_sales s JOIN dim_product p USING (product_id) GROUP BY ALL
), pu AS (
    SELECT date_trunc('month', actual_delivery_date) AS m, SUM(received_qty * unit_cost) AS receipts_value
    FROM fact_purchases WHERE actual_delivery_date IS NOT NULL GROUP BY ALL
)
SELECT m AS month_start, ROUND(cogs, 0) AS cogs, ROUND(receipts_value, 0) AS receipts_value,
       ROUND(receipts_value - cogs, 0) AS net_inventory_build,
       ROUND(SUM(receipts_value - cogs) OVER (ORDER BY m ROWS UNBOUNDED PRECEDING), 0) AS cumulative_build
FROM s JOIN pu USING (m)
ORDER BY m;

-- Q18: Seasonality - average daily units demanded by calendar month (festive vs monsoon)
SELECT d.month, d.month_name,
       ROUND(SUM(s.quantity) * 1.0 / COUNT(DISTINCT s.order_date), 0) AS avg_daily_units,
       ROUND(100.0 * (SUM(s.quantity) * 1.0 / COUNT(DISTINCT s.order_date))
             / AVG(SUM(s.quantity) * 1.0 / COUNT(DISTINCT s.order_date)) OVER () - 100, 1) AS pct_vs_average
FROM fact_sales s JOIN dim_date d ON d.date_key = s.order_date
WHERE s.order_status <> 'Cancelled'
GROUP BY d.month, d.month_name
ORDER BY d.month;

-- Q19: Customer segment mix - revenue, average discount, fill rate
SELECT c.segment,
       COUNT(DISTINCT s.customer_id) AS customers,
       ROUND(SUM(s.net_sales_value), 0) AS net_sales,
       ROUND(100.0 * SUM(s.net_sales_value) / SUM(SUM(s.net_sales_value)) OVER (), 1) AS pct_sales,
       ROUND(100 * AVG(s.discount), 1) AS avg_discount_pct,
       ROUND(100.0 * SUM(s.fulfilled_qty) FILTER (WHERE s.order_status <> 'Cancelled')
             / SUM(s.quantity) FILTER (WHERE s.order_status <> 'Cancelled'), 1) AS fill_rate_pct
FROM fact_sales s JOIN dim_customer c USING (customer_id)
GROUP BY c.segment
ORDER BY net_sales DESC;

-- Q20: ABC x XYZ matrix - revenue class (ABC) x demand variability class (XYZ, coefficient of variation of monthly units, last 12 months)
WITH m AS (
    SELECT s.product_id, date_trunc('month', s.order_date) AS mth, SUM(s.quantity) AS units, SUM(s.net_sales_value) AS rev
    FROM fact_sales s
    WHERE s.order_status <> 'Cancelled'
      AND s.order_date >= date_trunc('month', (SELECT MAX(order_date) FROM fact_sales)) - INTERVAL 12 MONTH
      AND s.order_date <  date_trunc('month', (SELECT MAX(order_date) FROM fact_sales))
    GROUP BY ALL
), p AS (
    SELECT product_id, SUM(rev) AS rev_12m, AVG(units) AS avg_units, STDDEV_SAMP(units) AS sd_units,
           STDDEV_SAMP(units) / NULLIF(AVG(units), 0) AS cv
    FROM m GROUP BY product_id
), c AS (
    SELECT *, SUM(rev_12m) OVER (ORDER BY rev_12m DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / SUM(rev_12m) OVER () AS cum_share
    FROM p
)
SELECT CASE WHEN cum_share <= 0.80 THEN 'A' WHEN cum_share <= 0.95 THEN 'B' ELSE 'C' END AS abc_class,
       CASE WHEN cv <= 0.5 THEN 'X (stable)' WHEN cv <= 1.0 THEN 'Y (variable)' ELSE 'Z (erratic)' END AS xyz_class,
       COUNT(*) AS products,
       ROUND(SUM(rev_12m), 0) AS revenue_12m,
       ROUND(100.0 * SUM(rev_12m) / SUM(SUM(rev_12m)) OVER (), 1) AS pct_revenue,
       ROUND(AVG(cv), 2) AS avg_cv
FROM c GROUP BY ALL
ORDER BY abc_class, xyz_class;

-- Q21: How to reduce holding cost? Savings if every product x warehouse is trimmed to a 60-day cover target
WITH dem AS (
    SELECT product_id, warehouse_id, SUM(quantity) / 90.0 AS avg_dd
    FROM fact_sales
    WHERE order_status <> 'Cancelled'
      AND order_date > (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot) - INTERVAL 90 DAY
      AND order_date <= (SELECT MAX(snapshot_date) FROM fact_inventory_snapshot)
    GROUP BY ALL
), x AS (
    SELECT i.warehouse_id, i.stock_quantity * p.unit_cost AS stock_value,
           GREATEST(i.stock_quantity - (COALESCE(dem.avg_dd, 0) * 60 + p.safety_stock), 0) * p.unit_cost AS releasable_value
    FROM v_latest_inventory i JOIN dim_product p USING (product_id) LEFT JOIN dem USING (product_id, warehouse_id)
)
SELECT w.warehouse_name,
       ROUND(SUM(stock_value), 0) AS stock_value,
       ROUND(SUM(releasable_value), 0) AS releasable_value,
       ROUND(100.0 * SUM(releasable_value) / NULLIF(SUM(stock_value), 0), 1) AS pct_releasable,
       ROUND(SUM(releasable_value) * (SELECT holding_cost_pct_per_year FROM config), 0) AS holding_cost_saving_per_year,
       SUM(ROUND(SUM(releasable_value) * (SELECT holding_cost_pct_per_year FROM config), 0)) OVER (ORDER BY SUM(releasable_value) DESC) AS cumulative_saving
FROM x JOIN dim_warehouse w USING (warehouse_id)
GROUP BY ALL
ORDER BY releasable_value DESC;
