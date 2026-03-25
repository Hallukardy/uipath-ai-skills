# DataTable Expressions

DataTable operations: Select/filter rows, Compute aggregates, sort, lookup, merge, clone, add/remove/rename columns, row iteration, Build Data Table expressions.

## Contents
- [DataTable Operations](#datatable-operations)
  - [VB.NET](#vbnet)
  - [LINQ on DataTable (VB.NET)](#linq-on-datatable-vbnet)
  - [LINQ on DataTable (C#)](#linq-on-datatable-c#)
  - [LINQ Query Syntax (VB.NET)](#linq-query-syntax-vbnet)
  - [LINQ Operator Reference](#linq-operator-reference)
  - [Making LINQ Available (Cast / AsEnumerable)](#making-linq-available-cast-asenumerable)
  - [Useful LINQ Patterns (DataTable)](#useful-linq-patterns-datatable)
  - [VB.NET Aggregate Keyword (Query Syntax Alternative)](#vbnet-aggregate-keyword-query-syntax-alternative)
  - [Non-DataTable LINQ (Arrays, Lists, Collections)](#non-datatable-linq-arrays-lists-collections)
  - [Robust DataTable Aggregation (Null-Safe Patterns)](#robust-datatable-aggregation-null-safe-patterns)

## DataTable Operations

### VB.NET
```vb
' Row count
dtData.Rows.Count

' Column count
dtData.Columns.Count

' Access cell value
dtData.Rows(0)("ColumnName").ToString
dtData.Rows(intIndex)(intColIndex).ToString

' Select rows (returns DataRow array)
dtData.Select("[Status] = 'Active'")
dtData.Select("[Amount] > 1000", "[Date] DESC")
dtData.Select("[Name] LIKE '%smith%'")

' Clone structure (no data)
dtData.Clone

' Copy structure + data
dtData.Copy

' Add column
dtData.Columns.Add("NewColumn", GetType(String))

' Remove column
dtData.Columns.Remove("ColumnName")

' Check column exists
dtData.Columns.Contains("ColumnName")

' DefaultView sort + filter
dtData.DefaultView.Sort = "[Date] ASC"
dtData.DefaultView.RowFilter = "[Status] = 'Active'"
dtData.DefaultView.ToTable
```

### LINQ on DataTable (VB.NET)
```vb
' Filter rows
dtData.AsEnumerable.Where(Function(row) row("Status").ToString = "Active").CopyToDataTable

' Filter with multiple conditions
dtData.AsEnumerable.Where(Function(row) _
  row("Status").ToString = "Active" AndAlso _
  CInt(row("Amount")) > 1000).CopyToDataTable

' Select distinct values (single column → array)
dtData.AsEnumerable.Select(Function(row) row("Category").ToString).Distinct.ToArray

' Select distinct rows (by specific columns → DataTable)
dtData.DefaultView.ToTable(True, "ColumnName")
dtData.DefaultView.ToTable(True, "Col1", "Col2")    ' Multiple columns

' Sum / Average / Min / Max
dtData.AsEnumerable.Sum(Function(row) Convert.ToDouble(row("Amount")))
dtData.AsEnumerable.Average(Function(row) CDbl(row("Price")))
dtData.AsEnumerable.Min(Function(row) CInt(row("Quantity")))
dtData.AsEnumerable.Max(Function(row) CDate(row("Date")))

' Count with condition
dtData.AsEnumerable.Count(Function(row) row("Status").ToString = "Error")

' Group by (returns IGrouping — usually used in Invoke Code)
dtData.AsEnumerable.GroupBy(Function(row) row("Category").ToString)

' Group by + aggregate (sum per category)
dtData.AsEnumerable.GroupBy(Function(row) row("Category").ToString) _
  .Select(Function(g) New Object() {g.Key, g.Sum(Function(r) CDbl(r("Amount")))})

' Order by (ascending)
dtData.AsEnumerable.OrderBy(Function(row) row("Name").ToString).CopyToDataTable
' Order by (descending)
dtData.AsEnumerable.OrderByDescending(Function(row) CDate(row("Date"))).CopyToDataTable
' Multi-column sort
dtData.AsEnumerable _
  .OrderBy(Function(row) row("Category").ToString) _
  .ThenByDescending(Function(row) CDbl(row("Amount"))) _
  .CopyToDataTable

' Any / All
dtData.AsEnumerable.Any(Function(row) row("Status").ToString = "Error")
dtData.AsEnumerable.All(Function(row) CInt(row("Amount")) > 0)

' First / FirstOrDefault
dtData.AsEnumerable.First(Function(row) row("ID").ToString = strTargetID)
dtData.AsEnumerable.FirstOrDefault(Function(row) row("ID").ToString = strTargetID)

' Skip / Take (pagination)
dtData.AsEnumerable.Skip(10).Take(10).CopyToDataTable

' Select (transform) — project to new shape
dtData.AsEnumerable.Select(Function(row) row("Name").ToString.ToUpper).ToList

' Join two DataTables (Inner Join)
From row1 In dtTable1.AsEnumerable
Join row2 In dtTable2.AsEnumerable
On row1("ID").ToString Equals row2("ID").ToString
Select dtResult.LoadDataRow(New Object() {row1("Name"), row2("Value")}, True)

' Left Outer Join (keep all rows from dt1, null for unmatched dt2)
From row1 In dtTable1.AsEnumerable
Group Join row2 In dtTable2.AsEnumerable
On row1("ID").ToString Equals row2("ID").ToString Into matches = Group
From m In matches.DefaultIfEmpty()
Select dtResult.LoadDataRow(New Object() {
  row1("Name"),
  If(m IsNot Nothing, m("Value").ToString, "")}, True)

' Lookup value from another table (like VLOOKUP)
dtLookup.AsEnumerable.FirstOrDefault(
  Function(row) row("Code").ToString = strSearchCode)?("Description")?.ToString

' Lookup with default value (safe — no NullReferenceException)
If(dtLookup.AsEnumerable.Any(Function(row) row("Code").ToString = strSearchCode),
   dtLookup.AsEnumerable.First(Function(row) row("Code").ToString = strSearchCode)("Description").ToString,
   "Not Found")
```

**⚠ CRITICAL: CopyToDataTable() throws on empty results!**
```vb
' BAD — throws InvalidOperationException if filter returns 0 rows:
dtData.AsEnumerable.Where(Function(row) row("Status").ToString = "X").CopyToDataTable

' SAFE — check first:
Dim filtered = dtData.AsEnumerable.Where(Function(row) row("Status").ToString = "X")
Dim dtResult = If(filtered.Any, filtered.CopyToDataTable, dtData.Clone)
' .Clone creates empty DataTable with same schema

' In single expression (safe):
If(dtData.AsEnumerable.Any(Function(row) row("Status").ToString = "X"),
   dtData.AsEnumerable.Where(Function(row) row("Status").ToString = "X").CopyToDataTable,
   dtData.Clone)
```

### LINQ on DataTable (C#)
```csharp
// Filter
dtData.AsEnumerable().Where(row => row["Status"].ToString() == "Active").CopyToDataTable()

// Sum
dtData.AsEnumerable().Sum(row => Convert.ToDouble(row["Amount"]))

// Group by
dtData.AsEnumerable().GroupBy(row => row["Category"].ToString())

// Order by
dtData.AsEnumerable().OrderBy(row => row["Name"].ToString()).CopyToDataTable()

// Safe CopyToDataTable
var filtered = dtData.AsEnumerable().Where(row => row["Status"].ToString() == "X");
var dtResult = filtered.Any() ? filtered.CopyToDataTable() : dtData.Clone();
```

### LINQ Query Syntax (VB.NET)
UiPath supports two LINQ syntaxes. Method Syntax (above) is compact for simple operations. 
Query Syntax is clearer for complex operations like GroupBy with aggregation.

```vb
' --- Basic Query Syntax ---
' Filter + Select (equivalent to .Where().Select())
(From d In dtData.AsEnumerable
Where d("Status").ToString.Equals("Active")
Select d).CopyToDataTable

' Multi-condition filter
(From d In dtData.AsEnumerable
Where d("Status").ToString = "Active" AndAlso CInt(d("Amount")) > 1000
Select d).CopyToDataTable

' --- GroupBy: Split DataTable into List(Of List(Of DataRow)) ---
' Outer list = groups, inner list = group member rows
(From d In dtData.AsEnumerable
Group d By k=d("RegionCode").ToString.Trim Into grp=Group
Select grp.toList).toList

' --- GroupBy: Split DataTable into List(Of DataTable) ---
' Each group becomes its own DataTable — useful for per-group processing
(From d In dtData.AsEnumerable
Group d By k=d("RegionCode").ToString.Trim Into grp=Group
Select grp.CopyToDataTable).toList

' --- GroupBy + Aggregation with Let (report generation) ---
' The "Let" keyword stores intermediate calculations for each group
' This pattern builds a summary report DataTable in a single Assign:
' (dtReport must be pre-built with matching columns via Build Data Table)
(From d In dtData.AsEnumerable
Group d By k=d("RegionCode").ToString.Trim Into grp=Group
Let cs = grp.Sum(Function(rc) CInt("0" & rc("CaseCount").ToString))
Let cn = String.Join(";", grp.Select(Function(rn) rn("CaseName").ToString).toArray)
Let ra = New Object(){k, cs, cn}
Select dtReport.Rows.Add(ra)).CopyToDataTable

' Explanation:
' Line 1: iterate DataTable rows (d = current DataRow)
' Line 2: group by RegionCode (k = group key, grp = group members)
' Line 3: Let cs = sum of CaseCount for this group
' Line 4: Let cn = semicolon-joined CaseNames for this group
' Line 5: Let ra = Object array for the report row
' Line 6: add row to dtReport and return result

' --- GroupBy with Count ---
(From d In dtData.AsEnumerable
Group d By k=d("Category").ToString.Trim Into grp=Group
Let cnt = grp.Count
Let ra = New Object(){k, cnt}
Select dtReport.Rows.Add(ra)).CopyToDataTable

' --- GroupBy with multiple keys ---
(From d In dtData.AsEnumerable
Group d By k1=d("Region").ToString, k2=d("Year").ToString Into grp=Group
Let total = grp.Sum(Function(r) CDbl(r("Amount")))
Let ra = New Object(){k1, k2, total}
Select dtReport.Rows.Add(ra)).CopyToDataTable
```

**⚠ GroupBy report pattern requires:** 
- `dtReport` must exist with matching columns (Build Data Table or `New DataTable`)
- Column count in `New Object(){...}` must match dtReport column count
- `CInt("0" & value)` is a safe numeric conversion (empty string → 0)

### LINQ Operator Reference
Complete taxonomy of available LINQ operators:
```
Filtering:      Where
Projection:     Select, SelectMany
Ordering:       OrderBy, OrderByDescending, ThenBy, ThenByDescending, Reverse
Quantifiers:    All, Any, Contains
Join:           Join (inner), GroupJoin (left outer)
Grouping:       GroupBy
Aggregation:    Aggregate, Count, LongCount, Sum, Min, Max, Average
Partitioning:   Skip, SkipWhile, Take, TakeWhile
Set:            Distinct, Except, Intersect, Union
Conversion:     AsEnumerable, Cast, OfType, ToArray, ToDictionary, ToList, ToLookup
Element Access: ElementAt, ElementAtOrDefault, First, FirstOrDefault,
                Last, LastOrDefault, Single, SingleOrDefault
Concatenation:  Concat, Append, Prepend
Generation:     DefaultIfEmpty, Empty, Range, Repeat
Other:          SequenceEqual, Zip
```

### Making LINQ Available (Cast / AsEnumerable)
**Required import:** Ensure `System.Linq` is in the workflow's Imports panel.
Most UiPath templates include it by default, but if LINQ methods don't appear in IntelliSense, check imports.
```vb
' DataTable → requires AsEnumerable (System.Data.DataTableExtensions)
dtData.AsEnumerable.Where(Function(row) ...)

' MatchCollection (Regex) → requires Cast
Regex.Matches(strInput, strPattern) _
  .Cast(Of Match) _
  .Select(Function(m) m.Value).ToList

' Non-generic IEnumerable → Cast(Of T) or OfType(Of T)
someCollection.Cast(Of String).Where(Function(s) s.Length > 5).ToList

' OfType — filter + cast (skips items that don't match type, never throws)
mixedCollection.OfType(Of String).ToList
```

### Useful LINQ Patterns (DataTable)
```vb
' --- Distinct rows by specific columns ---
dtData.DefaultView.ToTable(True, "ColumnName")             ' Single column
dtData.DefaultView.ToTable(True, "Col1", "Col2")           ' Multiple columns

' --- Remove empty rows ---
dtData.AsEnumerable.Where(Function(row) _
  Not row.ItemArray.All(Function(field) _
    field Is DBNull.Value OrElse String.IsNullOrWhiteSpace(field.ToString))).CopyToDataTable

' --- Find duplicates (rows appearing more than once by key column) ---
(From d In dtData.AsEnumerable
Group d By k=d("ID").ToString Into grp=Group
Where grp.Count > 1
Select grp).SelectMany(Function(g) g).CopyToDataTable

' --- Remove duplicates (keep first occurrence by key column) ---
(From d In dtData.AsEnumerable
Group d By k=d("ID").ToString Into grp=Group
Select grp.First).CopyToDataTable

' --- Column values to delimited string ---
String.Join(", ", dtData.AsEnumerable.Select(Function(row) row("Name").ToString))

' --- Check if value exists in DataTable column ---
dtData.AsEnumerable.Any(Function(row) row("Email").ToString.Equals(strSearch, StringComparison.OrdinalIgnoreCase))

' --- Except (rows in dt1 not in dt2, by key column) ---
Dim dt2Keys = dtTable2.AsEnumerable.Select(Function(r) r("ID").ToString).ToList
dtTable1.AsEnumerable.Where(Function(r) Not dt2Keys.Contains(r("ID").ToString)).CopyToDataTable

' --- Intersect (rows in both tables, by key column) ---
dtTable1.AsEnumerable.Where(Function(r) dt2Keys.Contains(r("ID").ToString)).CopyToDataTable

' --- Convert column values (e.g., trim all strings in all columns) ---
dtData.AsEnumerable.ToList.ForEach(Sub(row)
  For Each col As DataColumn In dtData.Columns
    If row(col) IsNot DBNull.Value Then row(col) = row(col).ToString.Trim
  End If
Next)

' --- Enumerable.Range (generate sequence) ---
Enumerable.Range(1, 10).ToList        ' {1, 2, 3, ..., 10}
Enumerable.Range(0, dtData.Rows.Count).Where(Function(i) i Mod 2 = 0) _
  .Select(Function(i) dtData.Rows(i)).CopyToDataTable   ' Every other row
```

### VB.NET Aggregate Keyword (Query Syntax Alternative)
VB.NET offers the `Aggregate ... Into` syntax as an alternative to method syntax for aggregation.
This is unique to VB.NET and has no C# equivalent.
```vb
' --- Aggregate on simple arrays/lists ---
Dim arrValues() As Int32 = {2, 12, -8, 6, 14, 5}
intResult = Aggregate x In arrValues Into Min(x)       ' -8
intResult = Aggregate x In arrValues Into Max(x)       ' 14
intResult = Aggregate x In arrValues Into Sum(x)       ' 31
dblResult = Aggregate x In arrValues Into Average(x)   ' 5.166...

' --- Aggregate with type conversion (string values → numeric) ---
Dim arrStrings() As String = {"2", "12", "-8", "6", "14", "5"}
intResult = Aggregate x In arrStrings Into Min(CInt(x))
intResult = Aggregate x In arrStrings Into Sum(CInt(x))

' --- Aggregate on DataTable column ---
dblResult = Aggregate d In dtData.AsEnumerable Into Sum(CDbl(d("Amount").ToString))
```

### Non-DataTable LINQ (Arrays, Lists, Collections)
LINQ works directly on arrays and lists without needing `.AsEnumerable`:
```vb
' --- Filter ---
Dim arrNums() As Int32 = {12, 34, 5, 8, 10, 2, 15, 7}
arrNums.Where(Function(x) x > 10).ToList               ' {12, 34, 15}
arrNums.Where(Function(x) x > 10).ToArray               ' Int32 array

' --- Short-form aggregation (numericals) ---
arrNums.Min()          ' 2
arrNums.Max()          ' 34
arrNums.Sum()          ' 93
arrNums.Average()      ' 11.625

' --- Lambda-form aggregation (non-numerical source) ---
Dim arrStrings() As String = {"2", "12", "8"}
arrStrings.Sum(Function(x) CInt(x))                     ' 22
arrStrings.Min(Function(x) CInt(x))                     ' 2

' --- Query syntax: filter + type projection ---
(From x In arrNums
Where x > 10
Select x.ToString()).ToList                               ' List(Of String): {"12","34","15"}

' --- Ordering ---
arrNums.OrderBy(Function(x) x).ToArray                  ' ascending
arrNums.OrderByDescending(Function(x) x).ToArray        ' descending

' --- Partitioning ---
arrNums.Skip(2).Take(3).ToArray                          ' skip first 2, take next 3
arrNums.SkipWhile(Function(x) x < 20).ToArray           ' skip until condition fails
arrNums.TakeWhile(Function(x) x < 20).ToArray           ' take until condition fails

' --- Set operations ---
Dim arr1() As Int32 = {1, 2, 3, 4}
Dim arr2() As Int32 = {3, 4, 5, 6}
arr1.Except(arr2).ToArray                                ' {1, 2}
arr1.Intersect(arr2).ToArray                             ' {3, 4}
arr1.Union(arr2).ToArray                                 ' {1, 2, 3, 4, 5, 6}
arr1.Concat(arr2).ToArray                                ' {1, 2, 3, 4, 3, 4, 5, 6} (with dupes)

' --- Check string array for partial match ---
arrKeywords.Any(Function(kw) strSubject.Contains(kw))    ' True if any keyword found
arrKeywords.All(Function(kw) strInput.Contains(kw))      ' True if ALL keywords found

' --- Generate sequence ---
Enumerable.Range(1, 12).ToList                           ' {1,2,...,12}
Enumerable.Range(0, 5).Select(Function(i) Now.AddDays(i).ToString("yyyy-MM-dd")).ToArray
Enumerable.Repeat("N/A", 10).ToArray                     ' 10 copies of "N/A"
```

### Robust DataTable Aggregation (Null-Safe Patterns)
Real-world data often has empty, null, or non-parseable values. These patterns handle them:
```vb
' --- Robust Sum: safe from nulls, empty strings, and non-numeric values ---
(From d In dtData.AsEnumerable
Let v = d("Amount")
Let chk1 = Not (IsNothing(v) OrElse String.IsNullOrEmpty(v.ToString.Trim))
Let chk2 = If(chk1, Double.TryParse(v.ToString, Nothing), False)
Let x = If(chk2, Double.Parse(v.ToString), 0)
Select n = x).Sum()
' chk1: value is not null/empty
' chk2: value passes parse test (is a valid number)
' x: parsed value or 0 as default

' --- Simple safe sum (empty → 0, throws on non-numeric) ---
dtData.AsEnumerable.Sum(Function(x) CDbl("0" & x("Amount").ToString.Trim))
' Prepending "0" makes empty string parse as 0

' --- Duration string sum (HH:mm:ss strings → total TimeSpan) ---
Dim arrDurations() As String = {"01:15:00", "00:25:00", "00:45:00"}
TimeSpan.FromTicks(arrDurations.Sum(Function(x) CDate(x).TimeOfDay.Ticks))
' Result: 02:25:00 as TimeSpan

' --- Count non-empty values in a column ---
dtData.AsEnumerable.Count(Function(row) _
  Not String.IsNullOrWhiteSpace(row("FieldName").ToString))

' --- Conditional aggregation (Sum only positive values) ---
dtData.AsEnumerable _
  .Where(Function(row) CDbl("0" & row("Amount").ToString) > 0) _
  .Sum(Function(row) CDbl(row("Amount").ToString))
```

