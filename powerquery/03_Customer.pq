// Query: Customer
// Customer master (2,000 customers + C00000 'Unknown Customer' for orders with missing customer id).
let
    Source = Csv.Document(File.Contents(DataFolder & "customers.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // culture en-US so '.' is always the decimal separator, whatever the PC's regional settings
    Typed = Table.TransformColumnTypes(Promoted, {{"Customer_ID", type text}, {"Customer_Name", type text}, {"Segment", type text}, {"City", type text}, {"State", type text}, {"Region", type text}}, "en-US"),
    Renamed = Table.TransformColumnNames(Typed, each Text.Replace(_, "_", " "))
in
    Renamed
