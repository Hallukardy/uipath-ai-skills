# Data & File Activities

BuildDataTable, AddDataRow, FilterDataTable, MergeDataTable, SortDataTable, RemoveDuplicateRows, OutputDataTable, JoinDataTables, LookupDataTable, GenerateDataTableFromText, DeserializeJSON, file system operations.

## Contents
  - [Build DataTable](#build-datatable)
  - [Add Data Row](#add-data-row)
  - [Filter Data Table](#filter-data-table)
  - [Merge Data Table](#merge-data-table)
  - [Sort Data Table](#sort-data-table)
  - [Remove Duplicate Rows](#remove-duplicate-rows)
  - [Output Data Table](#output-data-table)
  - [Join Data Tables](#join-data-tables)
  - [Lookup Data Table](#lookup-data-table)
  - [Generate Data Table From Text](#generate-data-table-from-text)
  - [Deserialize JSON](#deserialize-json)
- [File System Activities](#file-system-activities)
  - [Copy File](#copy-file)
  - [Move File](#move-file)
  - [Create Directory](#create-directory)
  - [Delete File](#delete-file)
  - [Path Exists](#path-exists)
  - [Common File System Patterns](#common-file-system-patterns)
- [Error Handling](#error-handling)


### Build DataTable

Uses `TableInfo` attribute containing an XSD schema + initial row data, all XML-escaped. Studio generates this — the schema defines columns and types.

**⚠️ CRITICAL — BuildDataTable is a SELF-CLOSING tag.** It has NO child elements. Columns are defined entirely inside the `TableInfo` attribute as an XML-escaped XSD schema. ⛔ `.Columns` property does NOT exist. ⛔ `DataTableColumnInfo` does NOT exist. Using either causes `Cannot set unknown member 'BuildDataTable.Columns'` → Studio crash.

→ **Use `gen_build_data_table()`** — generates correct XAML deterministically.


Schema column type mapping:
- `xs:string` (with `maxLength` restriction) — System.String
- `xs:int` — System.Int32
- `xs:boolean` — System.Boolean
- `xs:double` — System.Double
- `xs:dateTime` — System.DateTime

Initial data rows go after `</xs:schema>` as `<TableName>` elements.

### Add Data Row
→ **Use `gen_add_data_row()`** — generates correct XAML deterministically.

Notes:
- `ArrayRow` takes a VB.NET array literal: `[{"val1", "val2"}]` (XML-escaped quotes for string literals)
- For variable references, no quotes needed: `[{strCol1, strCol2, strCol3}]`
- `DataRow="{x:Null}"` when using ArrayRow (mutually exclusive)
- Can also use `DataRow="[dataRowVariable]"` with `ArrayRow` omitted
- Complex arrays use `&#xA;` (newlines) and `&#x9;` (tabs) for formatting within XAML attributes
- Each element can be any VB.NET expression: `If(condition, value, default)`, `obj.Property`, LINQ results, etc.
- **Column count must match DataTable schema** — mismatches cause runtime errors

**⚠️ Mixed-type arrays MUST use `New Object()` syntax:**
When ArrayRow contains values of different types (strings + numbers + booleans), wrap with `New Object()`. Plain `{val1, val2}` only works when all values are strings.
```xml
<!-- ❌ WRONG — mixed types without New Object() causes type inference error -->
ArrayRow="[{&quot;GRAND TOTAL&quot;, decGrandTotal, intGrandCount, decGrandAvg}]"

<!-- ✅ RIGHT — New Object() for mixed String + Decimal + Integer -->
ArrayRow="[New Object() {&quot;GRAND TOTAL&quot;, decGrandTotal, intGrandCount, decGrandAvg}]"
```
Rule: if the array contains ANY non-string value (numeric variables, booleans, expressions returning non-string types) → always use `New Object() {}`.

### Add Data Column (AddDataColumn)
Adds a column to an existing DataTable. **Use this instead of InvokeCode to define DataTable schemas.**
→ **Use `gen_add_data_column()`** — generates correct XAML deterministically.

For typed columns, change the `TypeArguments`:
- `x:TypeArguments="x:String"` — String column
- `x:TypeArguments="x:Int32"` — Integer column
- `x:TypeArguments="x:Decimal"` — Decimal column
- `x:TypeArguments="x:Boolean"` — Boolean column
- `x:TypeArguments="x:Object"` — generic (default)

**⚠️ Preferred pattern for creating DataTables with columns:**

Instead of InvokeCode with `New DataTable` + `dt.Columns.Add(...)`:

1. **Declare variable with default** — in the JSON spec `variables` array, pass `"default": "new DataTable"`. The generator wraps it in `VisualBasicValue` automatically.

2. **Add columns** — use `AddDataColumn` activities (one per column):
→ **Use `gen_add_data_column()`** — generates correct XAML deterministically.


This is cleaner than InvokeCode and stays within the low-code paradigm. For aggregation/grouping logic, use Assign or MultipleAssign with LINQ expressions in the Value field (e.g., `dt_Data.AsEnumerable().GroupBy(...)`) rather than InvokeCode.

### Filter Data Table
→ **Use `gen_filter_data_table()`** — generates correct XAML deterministically.

Properties:
- `FilterRowsMode`: `Keep` (keep matching rows) or `Remove` (remove matching rows)
- `SelectColumnsMode`: `Keep` (keep listed columns) or `Remove` (remove listed columns)
- `Operator`: `EQ`, `NE`, `LT`, `LE`, `GT`, `GE`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `EMPTY`, `NOT_EMPTY` (ALL CAPS — source: real Studio export)
- `BooleanOperator`: `And`, `Or` (for chaining multiple filters)
- For `EMPTY`/`NOT_EMPTY`: uses `Operand="{x:Null}"` attribute (no value needed)
- Operand type varies: `x:String` for text, `x:Int32` for numeric comparisons
- `OutputDataTable` can be same as input (in-place filter) or different variable

### Merge Data Table
→ **Use `gen_merge_data_table()`** — generates correct XAML deterministically.

Properties:
- `Source` — DataTable to add rows from
- `Destination` — DataTable receiving the rows (modified in-place)
- `MissingSchemaAction`: `Add` (add missing columns), `Ignore`, `Error`, `AddWithKey`
- Source columns not in Destination are added when `MissingSchemaAction="Add"`
- Both tables should share same schema for best results

### Sort Data Table
→ **Use `gen_sort_data_table()`** — generates correct XAML deterministically.

Properties:
- `ColumnName` — column name to sort by (string)
- `SortOrder`: `Ascending` or `Descending`
- `DataTable` — input DataTable to sort
- `OutputDataTable` — can be same as input (in-place) or a new variable
- `ColumnIndex` / `DataColumn` — alternative column selectors (usually `{x:Null}` when using `ColumnName`)
- For multi-column sort, chain multiple SortDataTable activities (secondary sort first, then primary — stable sort preserves order within ties)

**⚠️ WRONG property names (common hallucination):** `OrderByColumnName` → use `ColumnName`. `OrderByType` → use `SortOrder`.

### Remove Duplicate Rows
→ **Use `gen_remove_duplicate_rows()`** — generates correct XAML deterministically.

Properties:
- `DataTable` — input DataTable
- `OutputDataTable` — can be same as input (in-place) or new variable
- Keeps first occurrence of each duplicate row
- Compares ALL columns — for key-based dedup use Assign with `dt_Data.AsEnumerable().GroupBy(Function(r) r("Key")).Select(Function(g) g.First()).CopyToDataTable()`

### Output Data Table
→ **Use `gen_output_data_table()`** — generates correct XAML deterministically.

Properties:
- `DataTable` — DataTable to convert
- `Text` — output string in CSV format (headers + rows)
- Useful for logging, debugging, or writing to text files
- For custom formatting, use Assign with `String.Join(separator, dt_Data.AsEnumerable().Select(Function(r) r("Col").ToString))`

### Join Data Tables
→ **Use `gen_join_data_tables()`** — generates correct XAML deterministically.

Properties:
- `JoinType`: `Inner`, `Left`, `Full`
  - `Inner` — only matching rows from both tables
  - `Left` — all rows from DataTable1, matching from DataTable2 (nulls for non-matches)
  - `Full` — all rows from both tables (nulls where no match)
- `Operator`: `EQ`, `NE`, `LT`, `LE`, `GT`, `GE`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`
- `BooleanOperator`: `And`, `Or` (for multi-column join conditions)
- Column1 = column from DataTable1, Column2 = column from DataTable2
- If column names collide, DataTable2 columns get `_1` suffix (e.g., `Name_1`)
- Order of DataTable1 vs DataTable2 matters — affects output structure

### Lookup Data Table
→ **Use `gen_lookup_data_table()`** — generates correct XAML deterministically.

Properties:
- `LookupValue` — value to search for (String)
- `DataTable` — DataTable to search in
- `LookupColumnName` — column to search in (use `LookupColumnIndex` for index)
- `TargetColumnName` — column to return value from (use `TargetColumnIndex` for index)
- `RowIndex` — output Int32: row index where found (-1 if not found)
- `CellValue` — output: value from the target column at the found row
- Equivalent to Excel VLOOKUP — search one column, return from another
- For multiple matches or complex lookups, use Assign with `dt_Data.AsEnumerable().Where(Function(r) r("Key").ToString = strSearch).FirstOrDefault()`

### Generate Data Table From Text
→ **Use `gen_generate_data_table()`** — generates correct XAML deterministically.

Properties:
- `Input` — structured text string to parse
- `ColumnSeparators` — character array for column delimiter (e.g., `","c` for CSV)
- `NewLineSeparator` — row separator (default: `\n`)
- `UseColumnHeader` — if True, first row becomes column headers
- `AutoDetect` — auto-detect column types (String, Int32, etc.)
- `DataTable` — output DataTable variable
- Parsing methods: CSV, Custom (specify separators), Fixed width columns

### Deserialize JSON
Requires `xmlns:njl="clr-namespace:Newtonsoft.Json.Linq;assembly=Newtonsoft.Json"` for JObject output type.
→ **Use `gen_deserialize_json()`** — generates correct XAML deterministically.

Properties:
- `x:TypeArguments` — output type: `njl:JObject` (most common), or a custom type
- `JsonString` — VB.NET expression returning string to deserialize
- `JsonObject` — output variable receiving deserialized object
- `JsonSample` — optional sample JSON for type inference (usually empty string)

## File System Activities

**⚠️ Exact activity element names (do NOT invent alternatives):**
- `ui:CopyFile` — copy file (NOT `CopyFileX` or `FileCopy`)
- `ui:MoveFile` — move file (NOT `MoveFileX` or `FileMove`)
- `ui:DeleteFileX` — delete file (NOT `DeleteFile` or `ui:DeleteFile` — that doesn't exist and becomes `UnresolvedActivity`)
- `ui:CreateDirectory` — create folder
- `ui:PathExists` — check if path exists
- `ui:ForEachFileX` — iterate files in folder (NOT `ForEachFile`)

### Copy File
→ **Use `gen_copy_file()`** — generates correct XAML deterministically.

- `Path` — source file. Can be a literal relative path (from project root) or VB.NET expression `[variable]`
- `Destination` — target file path (VB.NET expression)
- `Overwrite` — `True` / `False` (default False). Whether to overwrite if destination exists
- `PathResource` / `DestinationResource` — `{x:Null}` unless using storage bucket references

### Move File
→ **Use `gen_move_file()`** — generates correct XAML deterministically.

- Same properties as Copy File, but moves instead of copies (source is deleted after transfer)
- Common pattern: move to archive folder after processing, building destination with `Path.GetFileName`

### Create Directory
→ **Use `gen_create_directory()`** — generates correct XAML deterministically.

- `Path` — directory path to create (creates parent directories if needed, like `mkdir -p`)
- `Output` — `{x:Null}` (optional DirectoryInfo output, rarely used)
- **Safe to call on existing directories** — does nothing if directory already exists (no error)
- Common pattern: create output/log/archive folders during Init phase from config dictionary

### Delete File
→ **Use `gen_delete_file()`** — generates correct XAML deterministically.

**⚠️ DeleteFileX does NOT have `ContinueOnError`** — it's a newer "X" activity that doesn't inherit from legacy ActivityBase. Wrap in TryCatch if you need error suppression.

### Path Exists
→ **Use `gen_path_exists()`** — generates correct XAML deterministically.

- `PathType` — `"File"` or `"Folder"`
- `Result` — Boolean output

### Common File System Patterns
```
Init phase:
  CreateDirectory → logs folder (from config)
  CreateDirectory → output folder (from config)
  CreateDirectory → archive folder (from config)
  CopyFile → template from Data\ folder to output path

Processing:
  ForEachFileInFolder → iterate files in input folder
    (process each file)
    MoveFile → archive folder after success

Cleanup:
  DeleteFile → temp files
  PathExists → check before operations
```


## Error Handling
