// Query: Warehouse
// 6 regional distribution hubs with storage capacity (units) and monthly fixed cost (INR).
let
    Source = Csv.Document(File.Contents(DataFolder & "warehouses.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // culture en-US so '.' is always the decimal separator, whatever the PC's regional settings
    Typed = Table.TransformColumnTypes(Promoted, {{"Warehouse_ID", type text}, {"Warehouse_Name", type text}, {"City", type text}, {"State", type text}, {"Region", type text}, {"Capacity_Units", Int64.Type}, {"Monthly_Fixed_Cost", type number}}, "en-US"),
    Renamed = Table.TransformColumnNames(Typed, each Text.Replace(_, "_", " ")),
    AddShort = Table.AddColumn(Renamed, "Warehouse", each Text.BeforeDelimiter([Warehouse Name], " ("), type text)
in
    AddShort
