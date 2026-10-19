// Query: Product
// Product master (400 SKUs, 8 categories). ABC Class is a DAX calculated column (lifetime net sales, 80/15/5 split).
let
    Source = Csv.Document(File.Contents(DataFolder & "products.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // empty CSV cells in optional columns -> null before typing
    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {"Shelf_Life_Days"}),
    // culture en-US so '.' is always the decimal separator, whatever the PC's regional settings
    Typed = Table.TransformColumnTypes(Blanks, {{"Product_ID", type text}, {"Product_Name", type text}, {"Category", type text}, {"Sub_Category", type text}, {"Unit_Cost", type number}, {"Unit_Price", type number}, {"Lead_Time_Days_Std", Int64.Type}, {"Reorder_Point", Int64.Type}, {"Safety_Stock", Int64.Type}, {"Shelf_Life_Days", Int64.Type}}, "en-US"),
    Renamed = Table.TransformColumnNames(Typed, each Text.Replace(_, "_", " ")),
    AddLabel = Table.AddColumn(Renamed, "Product Label", each [Product ID] & " - " & [Product Name], type text),
    AddMargin = Table.AddColumn(AddLabel, "Unit Margin %", each if [Unit Price] = 0 then null else ([Unit Price] - [Unit Cost]) / [Unit Price], type number),
    AddPerish = Table.AddColumn(AddMargin, "Perishable", each if [Shelf Life Days] = null then "Non-perishable" else "Perishable", type text)
in
    AddPerish
