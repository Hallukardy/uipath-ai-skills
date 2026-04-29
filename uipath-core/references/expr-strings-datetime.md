# String, DateTime & Utility Expressions

String operations (split, join, trim, pad, replace, regex, format), DateTime (parse, format, add, diff, business days), file/path operations, numeric operations, regex patterns.

## Contents
- [String Operations](#string-operations)
  - [Core Methods](#core-methods)
  - [Split & Join](#split-&-join)
  - [Case-Insensitive Operations](#case-insensitive-operations)
  - [String.Format & Concatenation](#stringformat-&-concatenation)
  - [Data Cleaning Patterns](#data-cleaning-patterns)
  - [Regex in Expressions](#regex-in-expressions)
  - [Unicode Normalization & Diacritics Removal](#unicode-normalization-&-diacritics-removal)
  - [Null/Empty Safety](#nullempty-safety)
  - [Padding & Alignment](#padding-&-alignment)
  - [Encoding & Conversion](#encoding-&-conversion)
  - [Common UiPath String Tasks](#common-uipath-string-tasks)
- [DateTime Operations](#datetime-operations)
  - [Core Operations](#core-operations)
  - [Format Tokens Reference](#format-tokens-reference)
  - [First/Last Day & Period Boundaries](#firstlast-day-&-period-boundaries)
  - [Business Day & Weekday Patterns](#business-day-&-weekday-patterns)
  - [TimeSpan](#timespan)
- [File & Path Operations](#file-&-path-operations)
- [Array & List Operations](#array-&-list-operations)
  - [Array (Fixed Size)](#array-fixed-size)
  - [Split → Array Patterns (Very Common in UiPath)](#split-→-array-patterns-very-common-in-uipath)
  - [List (Dynamic Size)](#list-dynamic-size)
  - [Collection XAML Types](#collection-xaml-types)

## String Operations

### Core Methods
```vb
' Basic operations (same in VB.NET and C#)
strInput.Trim                              ' Remove leading/trailing whitespace
strInput.TrimStart / strInput.TrimEnd      ' One side only
strInput.ToUpper / strInput.ToLower
strInput.Length

' Search
strInput.Contains("search")               ' Boolean — case-sensitive!
strInput.StartsWith("prefix")
strInput.EndsWith("suffix")
strInput.IndexOf("search")                ' Returns -1 if not found
strInput.LastIndexOf(".")

' Extract
strInput.Substring(5)                      ' From index 5 to end
strInput.Substring(5, 10)                  ' From index 5, take 10 chars

' Replace
strInput.Replace("old", "new")
strInput.Replace(vbCrLf, "")              ' Remove line breaks
strInput.Replace(Environment.NewLine, " ") ' Replace line breaks with space
```

### Split & Join
```vb
' Split — returns String array
strInput.Split({";"c}, StringSplitOptions.RemoveEmptyEntries)
strInput.Split({","c})                     ' Single char delimiter
strInput.Split({" - "}, StringSplitOptions.None)  ' String delimiter (no "c")
strInput.Split({vbCrLf, vbLf}, StringSplitOptions.RemoveEmptyEntries) ' By line

' Split and take specific part
strInput.Split({";"c})(0)                  ' First element
strInput.Split({";"c}).Last                ' Last element (needs System.Linq)

' Join
String.Join(", ", arrItems)
String.Join(Environment.NewLine, listLines)
String.Join(" | ", dtRow.ItemArray.Select(Function(x) x.ToString).ToArray)
```

**VB.NET quirk:** Single character delimiters need `"c"` suffix: `","c`. String delimiters use `{"string"}` array syntax without `c`. Getting this wrong is a common error.

### Case-Insensitive Operations
```vb
' VB.NET — Contains is case-sensitive! Use these instead:
strInput.ToUpper.Contains("SEARCH")
strInput.IndexOf("search", StringComparison.OrdinalIgnoreCase) >= 0

' Case-insensitive comparison
String.Equals(str1, str2, StringComparison.OrdinalIgnoreCase)
str1.Equals(str2, StringComparison.OrdinalIgnoreCase)
```

### String.Format & Concatenation
```vb
' Concatenation (primary method in VB.NET UiPath expressions)
"Processing: " + strName + " (ID: " + strId + ")"

' String.Format (use in Assign or expressions)
String.Format("Item {0} of {1}: {2}", intCurrent, intTotal, strName)
String.Format("{0:C2}", decAmount)         ' Currency: "$1,234.56"
String.Format("{0:N2}", decNumber)         ' Number: "1,234.56"
String.Format("{0:D8}", intNumber)         ' Padded: "00000042"
String.Format("{0:P1}", dblRatio)          ' Percent: "85.5%"

' VB.NET does NOT support $"interpolated strings" in UiPath expressions!
' Always use + concatenation or String.Format
```

### Data Cleaning Patterns
```vb
' Remove all whitespace
strInput.Replace(" ", "")

' Normalize whitespace (collapse multiple spaces to one)
Regex.Replace(strInput, "\s+", " ").Trim

' Remove non-alphanumeric characters
Regex.Replace(strInput, "[^a-zA-Z0-9]", "")

' Remove non-numeric (keep only digits)
Regex.Replace(strInput, "[^\d]", "")

' Clean web-scraped text (common in UiPath)
strInput.Replace(vbCrLf, " ").Replace(vbLf, " ").Replace(vbTab, " ").Trim

' Remove diacritics/accents (normalize to ASCII)
' Requires Invoke Code — too complex for single expression

' Extract digits from string like "Total: $1,234.56"
Regex.Match(strInput, "[\d,]+\.?\d*").Value

' Extract text between two markers
Regex.Match(strInput, "(?<=Start:).*?(?=End:)").Value.Trim
```

### Regex in Expressions

**⚠️ Always add `System.Text.RegularExpressions` to `NamespacesForImplementation`** so you can use short `Regex.Match(...)` form instead of the verbose `System.Text.RegularExpressions.Regex.Match(...)`. All generated XAML must include this import.

```vb
Regex.Match(strInput, "\\d{3}-\\d{4}").Value
Regex.IsMatch(strInput, "^\\d+$")
Regex.Replace(strInput, "[^a-zA-Z0-9]", "")
Regex.Matches(strInput, "\\b\\w+@\\w+\\.\\w+\\b").Count
Regex.Match(strInput, "pattern", RegexOptions.IgnoreCase).Success
Regex.IsMatch(strInput, "pattern", RegexOptions.IgnoreCase)

' Named groups
Regex.Match(strInput, "(?<name>\\w+):(?<value>\\d+)").Groups("name").Value

' Common validation patterns
Regex.IsMatch(strValue, "^[A-Z]{2}\\d{9}$", RegexOptions.None)
Regex.Match(strText, "[\\d,]+\\.?\\d*", RegexOptions.None).Value
```

#### Safe extraction (always guard `.Groups(N).Value`)

`Regex.Match(...).Groups(1).Value` throws `IndexOutOfRangeException` when the match fails or the capture group is absent. **Always** check `m.Success` and `m.Groups.Count` before reading a capture. Use the `If(...)` ternary to fall back to a sentinel:

```vb
' Single-line safe extraction with fallback
out_strID = If(Regex.Match(in_strBody, "Client ID:\s*(.+)").Success, _
               Regex.Match(in_strBody, "Client ID:\s*(.+)").Groups(1).Value.Trim(), _
               String.Empty)

' Preferred: assign once, then guard — avoids re-running the regex
Dim m = Regex.Match(in_strBody, "Client ID:\s*(.+)")
out_strID = If(m.Success AndAlso m.Groups.Count > 1, m.Groups(1).Value.Trim(), String.Empty)
```

The two-line form (assign + guarded read) is the recommended idiom in spec authoring — it makes the failure mode explicit and avoids running the regex twice. Use the inline form only when expression-language constraints force a single statement.

### Unicode Normalization & Diacritics Removal
```vb
' Remove diacritics/accents (ã→a, é→e, ñ→n)
' Decomposes characters, then strips combining marks via LINQ on chars
New String(strInput.Normalize(System.Text.NormalizationForm.FormD).Where( _
  Function(c) System.Globalization.CharUnicodeInfo.GetUnicodeCategory(c) <> _
    System.Globalization.UnicodeCategory.NonSpacingMark).ToArray())

' Practical: normalize + strip non-alpha for fuzzy matching
Regex.Replace( _
  New String(strInput.Normalize(System.Text.NormalizationForm.FormD).Where( _
    Function(c) System.Globalization.CharUnicodeInfo.GetUnicodeCategory(c) <> _
      System.Globalization.UnicodeCategory.NonSpacingMark).ToArray()), _
  "[^a-zA-Z]", "")

' Chain: String → Normalize → LINQ Where (filter chars) → ToArray → New String
' Works because String implements IEnumerable(Of Char)
```

### Null/Empty Safety
```vb
' Check before operating
String.IsNullOrEmpty(strValue)
String.IsNullOrWhiteSpace(strValue)

' Safe chain pattern — use If() ternary
If(String.IsNullOrEmpty(strInput), "", strInput.Trim.ToUpper)
If(strInput IsNot Nothing, strInput.Trim, "")

' Safe from DataRow (common source of NullReferenceException)
If(row("Column") IsNot Nothing AndAlso Not String.IsNullOrEmpty(row("Column").ToString), row("Column").ToString.Trim, "")
```

### Padding & Alignment
```vb
' Pad left (right-align text / zero-pad numbers)
strNumber.PadLeft(8, "0"c)           ' "42" → "00000042"
intInvoice.ToString.PadLeft(6, "0"c) ' 123 → "000123"

' Pad right (left-align text)
strName.PadRight(20)                 ' "Alex" → "Alex                "
strName.PadRight(20, "."c)           ' "Alex" → "Alex................"
```

### Encoding & Conversion
```vb
' Base64 encode/decode
Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(strInput))
System.Text.Encoding.UTF8.GetString(Convert.FromBase64String(strBase64))

' URL encode/decode (for API parameters)
System.Net.WebUtility.UrlEncode(strInput)    ' "hello world" → "hello+world"
System.Net.WebUtility.UrlDecode(strEncoded)

' HTML encode/decode (for web-scraped content)
System.Net.WebUtility.HtmlDecode(strHtml)    ' "&amp;" → "&"
System.Net.WebUtility.HtmlEncode(strText)

' SecureString to plain text (for credential handling)
New System.Net.NetworkCredential("", secureStr).Password
```

### Common UiPath String Tasks
```vb
' Extract filename from path
System.IO.Path.GetFileName(strPath)           ' "C:\Data\report.xlsx" → "report.xlsx"
System.IO.Path.GetFileNameWithoutExtension(strPath)  ' → "report"
System.IO.Path.GetExtension(strPath)          ' → ".xlsx"

' Build dynamic file path with timestamp
System.IO.Path.Combine(strFolder, "Report_" + Now.ToString("yyyyMMdd_HHmmss") + ".xlsx")

' Truncate string safely
If(strInput.Length > 100, strInput.Substring(0, 100) + "...", strInput)

' Extract email domain
strEmail.Split({"@"c})(1)                    ' "user@example.com" → "example.com"

' Count occurrences of a character
strInput.Length - strInput.Replace(",", "").Length   ' count commas

' Multiline string in XAML expression (use vbCrLf)
"Line 1" + vbCrLf + "Line 2" + vbCrLf + "Line 3"

' Clean currency string for parsing
CDbl(strPrice.Replace("$", "").Replace(",", "").Trim)   ' "$1,234.56" → 1234.56
CInt(Regex.Replace(strInput, "[^\d]", ""))  ' "INV-00123" → 123
```

## DateTime Operations

### Core Operations
```vb
' Current date/time
DateTime.Now
DateTime.Today          ' Date only, time = 00:00:00
DateTime.UtcNow

' Parse
DateTime.Parse("2024-01-15")
DateTime.ParseExact("15/01/2024", "dd/MM/yyyy", System.Globalization.CultureInfo.InvariantCulture)
DateTime.TryParse(strDate, dtResult)

' Arithmetic
dtDate.AddDays(7)
dtDate.AddMonths(-1)
dtDate.AddHours(3)
dtDate.AddMinutes(30)
DateDiff(DateInterval.Day, dtStart, dtEnd)   ' VB.NET only
(dtEnd - dtStart).TotalDays                   ' Both VB.NET and C#
(dtEnd - dtStart).TotalHours

' Components
dtDate.Year / dtDate.Month / dtDate.Day
dtDate.Hour / dtDate.Minute / dtDate.Second
dtDate.DayOfWeek                              ' Returns DayOfWeek enum
dtDate.DayOfYear                              ' 1-366
dtDate.Date                                   ' Date component only (strips time)
dtDate.TimeOfDay                              ' Returns TimeSpan
```

### Format Tokens Reference
```vb
' Date formatting — dtDate.ToString("format")
dtDate.ToString("yyyy-MM-dd")                 ' "2024-01-15"
dtDate.ToString("dd/MM/yyyy")                 ' "15/01/2024"
dtDate.ToString("MM/dd/yyyy")                 ' "01/15/2024"
dtDate.ToString("yyyyMMdd")                   ' "20240115" (compact, good for filenames)
dtDate.ToString("yyyy-MM-dd HH:mm:ss")        ' "2024-01-15 14:30:00" (24h)
dtDate.ToString("yyyy-MM-dd hh:mm:ss tt")     ' "2024-01-15 02:30:00 PM" (12h)
dtDate.ToString("MMMM dd, yyyy")              ' "January 15, 2024"
dtDate.ToString("MMM dd, yyyy")               ' "Jan 15, 2024"
dtDate.ToString("ddd, MMM dd")                ' "Mon, Jan 15"
dtDate.ToString("dddd, MMMM dd, yyyy")        ' "Monday, January 15, 2024"

' Key tokens:
'   yyyy=4-digit year  yy=2-digit    MM=month(01-12)  M=month(1-12)
'   dd=day(01-31)      d=day(1-31)   HH=hour24(00-23) hh=hour12(01-12)
'   mm=minute(00-59)   ss=second     tt=AM/PM         fff=milliseconds
'   MMM=abbreviated month  MMMM=full month  ddd=abbreviated day  dddd=full day

' Timestamp for filenames (no colons or slashes)
Now.ToString("yyyyMMdd_HHmmss")                ' "20240115_143000"

' ISO 8601
dtDate.ToString("o")                           ' "2024-01-15T14:30:00.0000000"
dtDate.ToString("yyyy-MM-ddTHH:mm:ssZ")        ' "2024-01-15T14:30:00Z"

' Culture-specific formatting
dtDate.ToString("d", New System.Globalization.CultureInfo("pt-BR"))  ' "15/01/2024"
dtDate.ToString("D", New System.Globalization.CultureInfo("en-US"))  ' "Monday, January 15, 2024"
```

### First/Last Day & Period Boundaries
```vb
' First day of current month
New DateTime(Now.Year, Now.Month, 1)

' Last day of current month
New DateTime(Now.Year, Now.Month, DateTime.DaysInMonth(Now.Year, Now.Month))

' First day of next month
New DateTime(Now.Year, Now.Month, 1).AddMonths(1)

' First day of current year
New DateTime(Now.Year, 1, 1)

' Last day of current year
New DateTime(Now.Year, 12, 31)

' Start of today (midnight)
DateTime.Today    ' or: Now.Date

' End of today (just before midnight)
DateTime.Today.AddDays(1).AddTicks(-1)

' Days in a month
DateTime.DaysInMonth(2024, 2)                  ' 29 (leap year)

' Is leap year
DateTime.IsLeapYear(2024)                      ' True
```

### Business Day & Weekday Patterns
```vb
' Is weekday?
dtDate.DayOfWeek <> DayOfWeek.Saturday AndAlso dtDate.DayOfWeek <> DayOfWeek.Sunday

' Is weekend?
dtDate.DayOfWeek = DayOfWeek.Saturday OrElse dtDate.DayOfWeek = DayOfWeek.Sunday

' Next business day (simple — no holidays)
If(dtDate.DayOfWeek = DayOfWeek.Friday, dtDate.AddDays(3),
   If(dtDate.DayOfWeek = DayOfWeek.Saturday, dtDate.AddDays(2), dtDate.AddDays(1)))

' Get day name
dtDate.DayOfWeek.ToString                      ' "Monday"
dtDate.ToString("dddd")                        ' "Monday" (locale-dependent)

' Start of week (Monday)
dtDate.AddDays(-(CInt(dtDate.DayOfWeek) + 6) Mod 7)
```

### TimeSpan
```vb
' Create
New TimeSpan(1, 30, 0)                         ' 1 hour, 30 minutes, 0 seconds
TimeSpan.FromMinutes(90)
TimeSpan.FromHours(2.5)
TimeSpan.FromDays(7)

' From date difference
Dim tsDiff As TimeSpan = dtEnd - dtStart
tsDiff.TotalDays                               ' Double (e.g., 1.5)
tsDiff.TotalHours
tsDiff.TotalMinutes
tsDiff.Days                                    ' Integer part only

' Format TimeSpan
tsDiff.ToString("hh\:mm\:ss")                 ' "01:30:00" (must escape colons!)
tsDiff.ToString("d\.hh\:mm")                  ' "1.01:30"
```

## File & Path Operations

```vb
' Path operations (System.IO.Path)
Path.Combine(strFolder, strFileName)
Path.GetFileName(strFilePath)              ' "file.xlsx"
Path.GetFileNameWithoutExtension(strPath)  ' "file"
Path.GetExtension(strPath)                 ' ".xlsx"
Path.GetDirectoryName(strPath)             ' parent folder
Path.GetTempPath                           ' temp folder (correct way)
Path.GetTempFileName                       ' temp file path
' ⚠️ Environment.SpecialFolder.Temp does NOT exist — compile error BC30456.
' Use Path.GetTempPath() instead. Valid SpecialFolders: Desktop, MyDocuments,
' LocalApplicationData, ApplicationData, CommonApplicationData, UserProfile.

' Directory operations (use in Invoke Code or assign)
Directory.GetFiles(strFolderPath, "*.xlsx")
Directory.GetFiles(strFolderPath, "*.pdf", SearchOption.AllDirectories)
Directory.GetDirectories(strFolderPath)
Directory.Exists(strFolderPath)
File.Exists(strFilePath)
```

## Array & List Operations

### Array (Fixed Size)
```vb
' Initialize (in Assign — variable type String[])
New String() {"item1", "item2", "item3"}
New Integer() {1, 2, 3}

' Initialize empty with size
New String(9) {}                              ' 10-element empty array (0-9)

' Access
arrItems(0)                                   ' First element
arrItems(arrItems.Length - 1)                  ' Last element

' Properties
arrItems.Length                                ' Element count
arrItems.Contains("search")                   ' Boolean — case-sensitive

' LINQ on arrays (requires System.Linq imported)
arrItems.First                                ' First element (throws if empty)
arrItems.Last                                 ' Last element
arrItems.FirstOrDefault                       ' First or Nothing
arrItems.Where(Function(x) x.Contains("test")).ToArray
arrItems.Select(Function(x) x.Trim.ToUpper).ToArray
arrItems.OrderBy(Function(x) x).ToArray
arrItems.Distinct.ToArray
arrItems.Any(Function(x) x = "target")
arrItems.Count(Function(x) x.StartsWith("A"))

' Convert
arrItems.ToList                               ' Array → List
String.Join(", ", arrItems)                   ' Array → delimited string
```

### Split → Array Patterns (Very Common in UiPath)
```vb
' Single char delimiter — MUST use "c" suffix
strInput.Split({";"c})                        ' Returns String()
strInput.Split({","c}, StringSplitOptions.RemoveEmptyEntries)

' String delimiter — NO "c" suffix, use string array
strInput.Split({"||"}, StringSplitOptions.None)     ' Multi-char delimiter
strInput.Split({">"}, StringSplitOptions.None)      ' Single-char as string also works

' Split + LINQ access
strInput.Split({">"}).First.ToString.Trim     ' First part
strInput.Split({">"}).Last.ToString.Trim      ' Last part
strInput.Split({";"c})(0)                     ' First by index

' Multiline split
strInput.Split({vbCrLf, vbLf}, StringSplitOptions.RemoveEmptyEntries)
strInput.Split({Environment.NewLine}, StringSplitOptions.RemoveEmptyEntries)
```

**VB.NET Split delimiter rules:**
- `","c` — char literal (single character, uses `c` suffix)
- `{","c}` — char array (for Split overload, wraps in array)
- `{"||"}` — string array (multi-character delimiter, NO `c` suffix)
- `{";"c, ","c}` — multiple char delimiters
- `{" - ", " | "}` — multiple string delimiters

### List (Dynamic Size)
```vb
' Initialize (variable type List<String> = scg:List(x:String))
New List(Of String)
New List(Of String) From {"item1", "item2"}

' Add / Remove
listItems.Add("newItem")
listItems.AddRange(arrMoreItems)
listItems.Insert(0, "first")                  ' Insert at index
listItems.Remove("item1")                     ' Remove first occurrence
listItems.RemoveAt(0)                         ' Remove by index
listItems.Clear                               ' Remove all

' Access
listItems(0)                                  ' By index
listItems.Count                               ' Element count (NOT .Length)
listItems.Contains("search")
listItems.IndexOf("item")                     ' Returns -1 if not found

' LINQ
listItems.Where(Function(x) x.Length > 3).ToList
listItems.Select(Function(x) x.ToUpper).ToList
listItems.OrderBy(Function(x) x).ToList
listItems.Distinct.ToList

' Convert
listItems.ToArray                             ' List → Array
```

### Collection XAML Types

Use these type names in the `variables` array of the JSON spec for `generate_workflow.py`:

| JSON type | XAML TypeArguments |
|---|---|
| `"Array_String"` | `s:String[]` |
| `"scg:List(x:String)"` | `scg:List(x:String)` |
| `"scg:Dictionary(x:String, x:Object)"` | `scg:Dictionary(x:String, x:Object)` |
| `"scg:KeyValuePair(x:String, x:Double)"` | `scg:KeyValuePair(x:String, x:Double)` |

For `gen_foreach()`, pass the item type as `item_type` (e.g., `"x:String"`). The generator handles `ActivityAction` and `DelegateInArgument` wrapping.

