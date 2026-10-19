// Query: Date
// Marked date table (Jan 2024 - Dec 2026) generated in Power Query from DateStart / DateEnd. Auto date/time is off.
let
    StartDate = DateStart,
    EndDate   = DateEnd,
    Dates     = List.Dates(StartDate, Duration.Days(EndDate - StartDate) + 1, #duration(1, 0, 0, 0)),
    Base      = Table.FromList(Dates, Splitter.SplitByNothing(), type table [Date = date]),
    AddYear   = Table.AddColumn(Base, "Year", each Date.Year([Date]), Int64.Type),
    AddQNo    = Table.AddColumn(AddYear, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),
    AddYQ     = Table.AddColumn(AddQNo, "Year Quarter", each Text.From([Year]) & " " & [Quarter], type text),
    AddYQKey  = Table.AddColumn(AddYQ, "Year Quarter Key", each [Year] * 10 + Date.QuarterOfYear([Date]), Int64.Type),
    AddMNo    = Table.AddColumn(AddYQKey, "Month No", each Date.Month([Date]), Int64.Type),
    AddMName  = Table.AddColumn(AddMNo, "Month", each Date.ToText([Date], [Format = "MMM", Culture = "en-US"]), type text),
    AddYM     = Table.AddColumn(AddMName, "Year Month", each Date.ToText([Date], [Format = "MMM yyyy", Culture = "en-US"]), type text),
    AddYMKey  = Table.AddColumn(AddYM, "Year Month Key", each [Year] * 100 + [Month No], Int64.Type),
    AddMStart = Table.AddColumn(AddYMKey, "Month Start", each Date.StartOfMonth([Date]), type date),
    AddWStart = Table.AddColumn(AddMStart, "Week Start", each Date.StartOfWeek([Date], Day.Monday), type date),
    AddDName  = Table.AddColumn(AddWStart, "Day Name", each Date.ToText([Date], [Format = "ddd", Culture = "en-US"]), type text),
    AddDNo    = Table.AddColumn(AddDName, "Day of Week No", each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type),
    // Indian financial year runs April - March
    AddFY     = Table.AddColumn(AddDNo, "Fiscal Year", each if [Month No] >= 4
                    then "FY" & Text.From([Year]) & "-" & Text.End(Text.From([Year] + 1), 2)
                    else "FY" & Text.From([Year] - 1) & "-" & Text.End(Text.From([Year]), 2), type text),
    AddSeason = Table.AddColumn(AddFY, "Season", each if [Month No] = 10 or [Month No] = 11 then "Festive (Oct-Nov)"
                    else if [Month No] >= 6 and [Month No] <= 8 then "Monsoon (Jun-Aug)" else "Regular", type text)
in
    AddSeason
