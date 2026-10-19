# Dashboard wireframe - SupplyChain.pbip

Canvas 1280 x 720 (16:9). Every main page shares the same **left rail** (x 8-184) and a content area (x 196-1272).
Data is **synthetic** (see the About data box on every page).

```
+----------------+----------------------------------------------------------------------------+
| Supply Chain BI| Page title + subtitle                       | page-specific header control |
| Synthetic | INR+----------------------------------------------------------------------------+
| [Inventory   ] | KPI | KPI | KPI | KPI | KPI | KPI   (cards, y 66-150)                       |
| [Warehouses  ] +----------------------------------------------------------------------------+
| [Suppliers   ] |                                                                            |
| [Sales & Purch]|  chart row (y 160-430)                                                     |
| [Shortage    ] |                                                                            |
| Date range     +----------------------------------------------------------------------------+
| Warehouse      |                                                                            |
| Category       |  chart / table row (y 440-712)                                             |
| Supplier       |                                                                            |
| page slicer    |                                                                            |
| [Clear slicers]|                                                                            |
| [Reset view  ] |                                                                            |
| [? Help      ] |                                                                            |
| About data     |                                                                            |
+----------------+----------------------------------------------------------------------------+
```

- Nav buttons: PageNavigation actions; the current page button is filled navy.
- Date / Warehouse / Category / Supplier slicers are in sync groups (same selection on every page).
- Help opens a hidden overlay (bookmark "Help - show"), Close hides it; Reset view = bookmark that clears this page's rail slicers.

## 1 Inventory Overview
| Area | Visual |
|---|---|
| Rail extra | What-if slider: holding cost % per year (synced with page 5) |
| Cards | Stock Value, Stock Units, Days of Cover, Inventory Turnover, Fill Rate %, Overstock Value, Annual Holding Cost |
| Row 1 | Line: closing stock value with Date Hierarchy drill-down (Year > Quarter > Month > Date) - Donut: stock value by warehouse (Warehouse Tooltip) |
| Row 2 | Bar: stock vs overstock value by category - Column: stockout rate % by category - About this data text |

## 2 Warehouse Performance
| Area | Visual |
|---|---|
| Rail extra | Region |
| Cards | Stock Units, Stock Value, Capacity Utilisation %, Fill Rate %, Overstock Value, Dead Stock Value |
| Row 1 | Bar: stock value by warehouse (tooltip) - Column: capacity utilisation (tooltip) - Line: stock value trend by warehouse |
| Row 2 | Table: warehouse scorecard (capacity / cover / fill-rate colour rules, data bars on stock and overstock value) |

## 3 Supplier Performance
| Area | Visual |
|---|---|
| Rail extra | Supplier rating band |
| Cards | Purchase Value, Delivered POs, On-Time %, OTIF %, Avg Lead Time, Short-Delivery % |
| Row 1-2 left | Bar: avg delay days by supplier (ranked) |
| Row 1 right | Scatter: lead time vs on-time % (size = purchase value) - Line: actual vs quoted lead time by quarter |
| Row 2 right | Table: supplier scorecard (delay colour, OTIF and lead-time data bars) |

## 4 Sales & Purchase Analysis
| Area | Visual |
|---|---|
| Header | Metric switcher (field parameter) - Time calculation slicer (calc group, only drives the trend + matrix) |
| Rail extra | Customer segment |
| Cards | Net Sales, Net Sales YoY %, Units Sold, Gross Margin %, Purchase Value, Sell-Through % |
| Row 1 | Line: selected metric by month, one line per year - Column: COGS vs received value by month |
| Row 2 | Table: Top 10 products by units demanded (Top N filter, data bars, drill-through) - Donut: net sales by segment - Matrix: category x time calculation |

## 5 Stock Shortage & Overstock
| Area | Visual |
|---|---|
| Header | What-if slider: holding cost % (synced with page 1) |
| Rail extra | ABC class |
| Cards | Stockouts (latest), Stockout Rate %, Lost Sales Value, Needs Restock Count, Overstock Value, Dead Stock Value, Excess Holding Cost |
| Row 1 | Bar: Top 10 products by lost sales (Top N, drill-through) - Column: overstock and dead stock by warehouse (tooltip) - Matrix: category x warehouse overstock |
| Row 2 | Table: restock recommendations (priority colour, days-of-cover colour, data bars on suggested reorder value) |

## Product Detail (drill-through, hidden)
Right-click any product > Drill through. Back button, dynamic title, 6 KPI cards, weekly stock by warehouse, demand vs sold
by month, warehouse table (cover / fill-rate colours), supplier table.

## Warehouse Tooltip (hidden, 320 x 240)
Stock Value, Days of Cover, Capacity Utilisation %, Fill Rate % for the hovered warehouse.
