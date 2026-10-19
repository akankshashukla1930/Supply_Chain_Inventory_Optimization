// Query: Sales
// Order lines (~152k). Quantity = ordered, Fulfilled Qty = shipped. Model columns added in Power Query: Net Sales, Demand Qty, Lost Qty, Delivery Days.
let
    Source = Csv.Document(File.Contents(DataFolder & "sales.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // empty CSV cells in optional columns -> null before typing
    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {"Ship_Date", "Delivery_Date"}),
    // culture en-US so '.' is always the decimal separator, whatever the PC's regional settings
    Typed = Table.TransformColumnTypes(Blanks, {{"Sales_ID", type text}, {"Order_Date", type date}, {"Product_ID", type text}, {"Customer_ID", type text}, {"Warehouse_ID", type text}, {"Quantity", Int64.Type}, {"Unit_Price", type number}, {"Discount", type number}, {"Ship_Date", type date}, {"Delivery_Date", type date}, {"Order_Status", type text}, {"Fulfilled_Qty", Int64.Type}}, "en-US"),
    Renamed = Table.TransformColumnNames(Typed, each Text.Replace(_, "_", " ")),
    // model-specific columns (no cleaning here - data/processed is already clean)
    AddNet = Table.AddColumn(Renamed, "Net Sales", each [Fulfilled Qty] * [Unit Price] * (1 - [Discount]), type number),
    // demand excludes customer cancellations; lost = demand we could not ship (stockouts / partial fills)
    AddDemand = Table.AddColumn(AddNet, "Demand Qty", each if [Order Status] = "Cancelled" then 0 else [Quantity], Int64.Type),
    AddLost = Table.AddColumn(AddDemand, "Lost Qty", each if [Order Status] = "Cancelled" then 0 else [Quantity] - [Fulfilled Qty], Int64.Type),
    AddDays = Table.AddColumn(AddLost, "Delivery Days", each if [Delivery Date] = null then null else Duration.Days([Delivery Date] - [Order Date]), Int64.Type)
in
    AddDays
