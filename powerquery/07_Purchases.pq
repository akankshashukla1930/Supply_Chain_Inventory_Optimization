// Query: Purchases
// Purchase-order lines (~22k). Active date relationship = PO Date; inactive = Actual Delivery Date (used for receipts).
let
    Source = Csv.Document(File.Contents(DataFolder & "purchases.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // empty CSV cells in optional columns -> null before typing
    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {"Actual_Delivery_Date"}),
    // culture en-US so '.' is always the decimal separator, whatever the PC's regional settings
    Typed = Table.TransformColumnTypes(Blanks, {{"Purchase_ID", type text}, {"PO_Date", type date}, {"Supplier_ID", type text}, {"Product_ID", type text}, {"Warehouse_ID", type text}, {"Quantity", Int64.Type}, {"Unit_Cost", type number}, {"Expected_Delivery_Date", type date}, {"Actual_Delivery_Date", type date}, {"Received_Qty", Int64.Type}, {"Status", type text}}, "en-US"),
    Renamed = Table.TransformColumnNames(Typed, each Text.Replace(_, "_", " ")),
    AddValue = Table.AddColumn(Renamed, "PO Value", each [Quantity] * [Unit Cost], type number),
    AddRecVal = Table.AddColumn(AddValue, "Received Value", each [Received Qty] * [Unit Cost], type number),
    AddDeliv = Table.AddColumn(AddRecVal, "Is Delivered", each if [Actual Delivery Date] = null then 0 else 1, Int64.Type),
    AddLT = Table.AddColumn(AddDeliv, "Lead Time Days", each if [Is Delivered] = 1 then Duration.Days([Actual Delivery Date] - [PO Date]) else null, Int64.Type),
    AddDelay = Table.AddColumn(AddLT, "Delay Days", each if [Is Delivered] = 1 then Duration.Days([Actual Delivery Date] - [Expected Delivery Date]) else null, Int64.Type),
    AddOnTime = Table.AddColumn(AddDelay, "On Time Flag", each if [Is Delivered] = 1 then (if [Delay Days] <= 0 then 1 else 0) else null, Int64.Type),
    AddInFull = Table.AddColumn(AddOnTime, "In Full Flag", each if [Is Delivered] = 1 then (if [Received Qty] >= [Quantity] then 1 else 0) else null, Int64.Type),
    AddOTIF = Table.AddColumn(AddInFull, "OTIF Flag", each if [Is Delivered] = 1 then [On Time Flag] * [In Full Flag] else null, Int64.Type),
    AddShort = Table.AddColumn(AddOTIF, "Short Flag", each if [Is Delivered] = 1 then 1 - [In Full Flag] else null, Int64.Type),
    AddOpen = Table.AddColumn(AddShort, "Open Qty", each if [Status] = "Open" then [Quantity] else 0, Int64.Type)
in
    AddOpen
