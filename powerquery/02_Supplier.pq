// Query: Supplier
// Supplier master (40 suppliers).
let
    Source = Csv.Document(File.Contents(DataFolder & "suppliers.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // empty CSV cells in optional columns -> null before typing
    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {"Rating"}),
    // culture en-US so '.' is always the decimal separator, whatever the PC's regional settings
    Typed = Table.TransformColumnTypes(Blanks, {{"Supplier_ID", type text}, {"Supplier_Name", type text}, {"City", type text}, {"State", type text}, {"Rating", type number}, {"Payment_Terms", type text}}, "en-US"),
    Renamed = Table.TransformColumnNames(Typed, each Text.Replace(_, "_", " ")),
    AddBand = Table.AddColumn(Renamed, "Rating Band", each if [Rating] = null then "Unrated" else if [Rating] >= 4.5 then "4.5+ Excellent" else if [Rating] >= 3.5 then "3.5-4.4 Good" else "< 3.5 At risk", type text)
in
    AddBand
