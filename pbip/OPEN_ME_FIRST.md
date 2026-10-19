# OPEN ME FIRST - Power BI file kaise kholna hai

> Data **synthetic** hai (fake Indian distributor, INR, Jan 2024 - Sep 2026). Report me har page par "About data" box hai.

## Step 1 - Folder copy karo
Pura folder `Supply_Chain_Inventory_Optimization` ko yahan copy karo:

```
C:\PBI\Supply_Chain_Inventory_Optimization\
```

Is path par CSV files honi chahiye: `C:\PBI\Supply_Chain_Inventory_Optimization\data\processed\sales.csv` (aur baaki 6 files).
Agar kisi aur jagah rakhna hai to Step 3 me path badal dena.

## Step 2 - .pbip kholo
- Power BI Desktop latest version (Windows) install hona chahiye.
- `pbip\SupplyChain.pbip` par double-click karo (ya Power BI Desktop > File > Open > `SupplyChain.pbip`).
- Agar "PBIR / TMDL preview feature" ke baare me pooche: File > Options > Preview features me
  **Power BI Project (.pbip) save option** aur **Store reports using enhanced metadata format (PBIR)** ON karo, Desktop restart karo.

## Step 3 - Parameter check karo (Manage parameters)
Home > Transform data > **Edit parameters**:

| Parameter | Value |
|---|---|
| DataFolder | `C:\PBI\Supply_Chain_Inventory_Optimization\data\processed\` (last me `\` zaroori hai) |
| DateStart | 01-01-2024 |
| DateEnd | 31-12-2026 |

## Step 4 - Refresh
Home > **Refresh**. Pehli baar 1-2 minute lagega (~5 lakh rows). Refresh ke baad sab visuals data dikhayenge.
Phir **File > Save** (PBIP format me hi save hoga).

## Report me kya kya hai
- 5 main pages + Product Detail (drill-through) + Warehouse Tooltip (hidden pages).
- Left side buttons se page change karo (current page dark blue dikhta hai). Desktop me button par **Ctrl + click** karna padta hai.
- Date / Warehouse / Category / Supplier slicers sab pages par sync hain.
- **Clear slicers**, **Reset view**, **? Help** buttons (bookmarks).
- Kisi product par right-click > **Drill through > Product Detail**; wapas aane ke liye Back arrow (Ctrl + click).
- Page 4: **Metric switcher** (field parameter) aur **Time calculation** (calculation group: PY, YoY %, YTD, Rolling 3M ...).
- Page 1 / 5: **What-if slider** - holding cost % badlo, holding cost cards turant update honge.

## Common errors aur solution
| Error | Kya karna hai |
|---|---|
| `DataSource.Error: Could not find a part of the path ...` | DataFolder galat hai - Step 3 me sahi path daalo, last me `\` lagao, Refresh. |
| "We couldn't load the report / unsupported format" | Power BI Desktop update karo; PBIR preview feature ON karo (Step 2). |
| Visual par "Something's wrong with one or more fields" | Refresh nahi hua hai - pehle Refresh karo. Phir bhi aaye to us visual ka field dobara drag karo. |
| Calculation group / field parameter ka error | File > Options > Data Load > "Discourage implicit measures" ON rehna chahiye (model me already set hai). |
| Dates ya numbers galat (jaise 1.234,5) | Queries me culture `en-US` set hai; agar phir bhi issue ho to File > Options > Regional settings > English (United States). |
| Refresh bahut slow | `inventory.csv` + `sales.csv` bade hain; normal hai. Background apps band karo. |

## Polish karne ke liye (optional, 15-20 min)
1. Har page ko ek baar dekho - koi title cut ho raha ho to visual thoda bada karo.
2. View > **Sync slicers** pane me check karo ki 4 slicers sab pages par sync dikh rahe hain.
3. Bookmarks pane me "Reset view" / "Help" bookmarks ek baar click karke test karo.
4. Theme colours pasand na aaye to View > Themes se badlo (custom theme `SupplyChain_Theme.json` laga hai).
5. Screenshots le kar `images/` folder me daalo aur README me add karo (portfolio ke liye).
6. Publish karna ho to Power BI Service me publish karo (data synthetic hai, share karna safe hai).
