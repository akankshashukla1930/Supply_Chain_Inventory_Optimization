// Query: Inventory
// Weekly (Sunday) stock snapshot per product x warehouse (semi-additive: use the Stock measures, never SUM over dates).
let
    Source = Csv.Document(File.Contents(DataFolder & "inventory.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // culture en-US so '.' is always the decimal separator, whatever the PC's regional settings
    Typed = Table.TransformColumnTypes(Promoted, {{"Snapshot_Date", type date}, {"Product_ID", type text}, {"Warehouse_ID", type text}, {"Stock_Quantity", Int64.Type}, {"Reserved_Qty", Int64.Type}}, "en-US"),
    Renamed = Table.TransformColumnNames(Typed, each Text.Replace(_, "_", " ")),
    AddAvail = Table.AddColumn(Renamed, "Available Qty", each [Stock Quantity] - [Reserved Qty], Int64.Type),
    AddOOS = Table.AddColumn(AddAvail, "Is Stockout", each if [Stock Quantity] <= 0 then 1 else 0, Int64.Type)
in
    AddOOS
