# Collections, JSON & Type Expressions

Array/List operations, numeric operations, regex patterns, Dictionary operations, JSON (Newtonsoft.Json — JObject, JArray, parse, query, build, serialize), LINQ on typed collections, type conversions, Queue Item & Orchestrator expressions.

## Contents
- [Numeric Operations](#numeric-operations)
- [Regex Patterns](#regex-patterns)
- [Dictionary Operations](#dictionary-operations)
- [JSON Operations (Newtonsoft.Json)](#json-operations-newtonsoftjson)
  - [JObject — Create & Parse](#jobject-create-&-parse)
  - [JObject — Read Values (Chained Indexer)](#jobject-read-values-chained-indexer)
  - [JObject — Null-Safe Access (Critical!)](#jobject-null-safe-access-critical!)
  - [JObject — Write Values](#jobject-write-values)
  - [JArray Operations](#jarray-operations)
  - [JToken Type Conversions](#jtoken-type-conversions)
  - [Common UiPath JSON Patterns](#common-uipath-json-patterns)
- [LINQ on Typed Collections](#linq-on-typed-collections)
  - [Entity / Object List LINQ](#entity-object-list-linq)
  - [KeyValuePair Access](#keyvaluepair-access)
- [Type Conversions](#type-conversions)
  - [String ↔ Numeric](#string-↔-numeric)
  - [Boolean Conversions](#boolean-conversions)
  - [DataRow Cell Access & Conversion](#datarow-cell-access-&-conversion)
  - [JToken Conversions](#jtoken-conversions)
  - [GenericValue (UiPath Proprietary Type)](#genericvalue-uipath-proprietary-type)
- [Queue Item & Orchestrator](#queue-item-&-orchestrator)

## Numeric Operations

```vb
' Rounding
Math.Round(3.14159, 2)                        ' 3.14 (banker's rounding by default!)
Math.Round(3.145, 2, MidpointRounding.AwayFromZero)  ' 3.15 (standard rounding)
Math.Floor(3.9)                               ' 3 (always rounds down)
Math.Ceiling(3.1)                             ' 4 (always rounds up)
Math.Truncate(3.9)                            ' 3 (drops decimals, no rounding)

' Min / Max / Abs
Math.Min(intA, intB)
Math.Max(dblA, dblB)
Math.Abs(-42)                                 ' 42

' Integer division & modulo
intTotal \ intBatchSize                       ' VB.NET integer division (backslash!)
intTotal Mod intBatchSize                     ' Remainder

' Random number (in Assign or Invoke Code)
New Random().Next(1, 100)                     ' Random int between 1-99
New Random().NextDouble()                     ' Random double between 0.0-1.0

' Percentage
CDbl(intPart) / CDbl(intTotal) * 100          ' Calculate percentage
Math.Round(CDbl(intPart) / CDbl(intTotal) * 100, 1)  ' Rounded to 1 decimal
```

**Banker's rounding gotcha:** `Math.Round(2.5)` returns `2`, not `3`! Use `MidpointRounding.AwayFromZero` for standard rounding behavior.

## Regex Patterns

Common patterns for UiPath automations:

```vb
' Email
"[\w\.-]+@[\w\.-]+\.\w+"

' Phone (US)
"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"

' Invoice number
"INV[-\s]?\d{4,10}"

' Currency amount
"\$?\d{1,3}(,\d{3})*(\.\d{2})?"

' Date patterns
"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"

' Postal code (US)
"\d{5}(-\d{4})?"

' Extract between delimiters
"(?<=START).*?(?=END)"
```

## Dictionary Operations

```vb
' Initialize
New Dictionary(Of String, Object) From {{"key", "value"}}

' Access
dictConfig("key").ToString

' Safe access
If(dictConfig.ContainsKey("key"), dictConfig("key").ToString, "default")

' Add/Update
dictConfig("newKey") = "newValue"

' Remove
dictConfig.Remove("key")

' Iterate (in For Each with KeyValuePair(Of String, Object))
item.Key + " = " + item.Value.ToString

' Keys/Values
dictConfig.Keys.ToList
dictConfig.Values.ToList

' Count / Check
dictConfig.Count
dictConfig.ContainsKey("key")
dictConfig.ContainsValue(someValue)

' Merge two dictionaries (in Invoke Code or ForEach)
' For each kvp In dict2: dict1(kvp.Key) = kvp.Value
```

## JSON Operations (Newtonsoft.Json)

**Namespace:** `xmlns:njl="clr-namespace:Newtonsoft.Json.Linq;assembly=Newtonsoft.Json"`
**Required import:** `Newtonsoft.Json.Linq` in NamespacesForImplementation
**Variable types:** `njl:JObject`, `njl:JArray`, `njl:JToken`

### JObject — Create & Parse
```vb
' Create empty JObject
new JObject()

' Parse JSON string into JObject
JObject.Parse(strJsonString)

' Parse with error handling (in Assign — will throw if invalid)
JObject.Parse(strResponse)

' Create JObject with initial properties
JObject.Parse("{""key"": ""value"", ""count"": 42}")

' Serialize JObject back to string
jObj.ToString                          ' Pretty-printed (indented)
jObj.ToString(Newtonsoft.Json.Formatting.None)  ' Compact, single line
```

### JObject — Read Values (Chained Indexer)
```vb
' Single level access — returns JToken
jObj("propertyName")

' Access and convert to string
jObj("propertyName").ToString

' Chained indexer — nested access (2 levels deep)
jObj("validation")(str_FieldTitle)

' 3 levels deep
jObj("data")(str_RootKey)(str_ChildKey)

' Dynamic key from variable
jObj("data")(strDynamicKey).ToString.Trim

' Convert to specific types
jObj("count").Value(Of Integer)
jObj("amount").Value(Of Double)
jObj("isActive").Value(Of Boolean)
CInt(jObj("count"))
CDbl(jObj("amount"))
CBool(jObj("isActive"))
```

### JObject — Null-Safe Access (Critical!)
```vb
' JToken access returns Nothing if key doesn't exist — ALWAYS null-check
If(Not jObj("key") Is Nothing, jObj("key").ToString.Trim, "")

' Nested null-safe
If(Not jObj("data")(strKey) Is Nothing, jObj("data")(strKey).ToString.Trim, "")

' Deep nested null-safe (check each level)
If(jObj("data") IsNot Nothing AndAlso jObj("data")(strKey) IsNot Nothing,
   jObj("data")(strKey).ToString, "")

' Check if property exists
jObj.ContainsKey("propertyName")
jObj("propertyName") IsNot Nothing
```

### JObject — Write Values
```vb
' Set property value (creates or overwrites)
jObj("validation")(str_FieldTitle) = new JObject()

' Set nested value via chained indexer
jObj("validation")(strField)(strStatusKey) = True
jObj("validation")(strField)(strStatusKey) = False

' Assign Boolean to JToken path
' In XAML: OutArgument x:TypeArguments="njl:JToken" and InArgument value [True] or [False]

' Add new property
jObj.Add("newProperty", "newValue")
jObj.Add("nested", new JObject())

' Remove property
jObj.Remove("propertyName")

' Merge from another JObject
jObj.Merge(jObjOther)
```

### JArray Operations
```vb
' Parse JSON array
JArray.Parse(strJsonArrayString)

' Access from JObject
jObj("items")                          ' Returns JToken — cast to JArray if needed
CType(jObj("items"), JArray)

' Iterate (in For Each with JToken type)
' ForEach TypeArguments="njl:JToken" Values="[jArr]"
currentItem("propertyName").ToString

' Array count
jArr.Count

' Access by index
jArr(0)("propertyName").ToString

' Add item to array
jArr.Add(new JObject())

' LINQ on JArray
jArr.Where(Function(item) item("status").ToString = "active").Count
jArr.Select(Function(item) item("name").ToString).ToList
jArr.Any(Function(item) CBool(item("isValid")))
```

### JToken Type Conversions
```vb
' JToken is the base type — JObject and JArray inherit from it
' In XAML Assign, use njl:JToken for both input and output types

' Check JToken type
jToken.Type    ' returns JTokenType enum: Object, Array, String, Integer, Float, Boolean, Null

' Safe type checking
jToken.Type = Newtonsoft.Json.Linq.JTokenType.Null
jToken.Type = Newtonsoft.Json.Linq.JTokenType.Object

' Convert between types
CType(jToken, JObject)   ' Cast JToken to JObject
CType(jToken, JArray)    ' Cast JToken to JArray
```

### Common UiPath JSON Patterns
```vb
' API response → JObject → extract values
JObject.Parse(strResponseBody)("data")("id").ToString

' Build request body (in Invoke Code)
Dim jBody As New JObject()
jBody.Add("name", strName)
jBody.Add("amount", decAmount)
jBody.ToString(Newtonsoft.Json.Formatting.None)

' Config dictionary to JSON key access (common REFramework pattern)
jObj("data")(dictConfig("JsonKeyName").ToString).ToString

' Validate extraction — check field exists and isn't a "not found" marker
Not String.IsNullOrEmpty(strValue) AndAlso
Not Regex.Match(strValue, strNotFoundPattern, RegexOptions.IgnoreCase).Success

' Safe field extraction with ContainsKey (from AddDataRow inline arrays)
If(jObj.ContainsKey("City"), jObj("City").ToString, "")

' Validate ALL required fields present — Split config + All LINQ
config("RequiredFields").ToString.Split(",").All(
  Function(k) jObj(k) IsNot Nothing AndAlso 
  Not String.IsNullOrWhiteSpace(jObj(k).ToString))

' String truncation (common for DB/entity field length limits)
If(strValue.Length > 2000, strValue.Substring(0, 2000), strValue)
If(jObj("Correction").ToString.Length > 2000, 
   jObj("Correction").ToString.Substring(0, 2000), 
   jObj("Correction").ToString)
```

## LINQ on Typed Collections

Beyond DataTables, LINQ is heavily used on typed lists (Data Service entities, custom objects).

### Entity / Object List LINQ
```vb
' Select single property → List(Of String)
listEntities.Select(Function(item) item.RawInput).ToList()

' Where + FirstOrDefault + property access (VLOOKUP equivalent)
listEntities.Where(Function(r) r.RawInput.ToString().ToLower.Equals(strSearch)).FirstOrDefault().City

' Case-insensitive matching with .ToUpper
listEntities.Where(Function(r) r.RawInput.ToUpper.Equals(strKey.ToUpper)).FirstOrDefault().PropertyName

' Count matching (equality check)
listEntities.Where(Function(r) r.RawInput.ToUpper.Equals(strKey.ToUpper)).Count

' First (throws if empty) vs FirstOrDefault (returns Nothing)
listEntities.First().Id
listEntities.FirstOrDefault()?.PropertyName   ' C# only — use If() wrapper in VB.NET

' Check existence
listEntities.Any(Function(r) r.PropertyName = strValue)

' All match condition
arrFields.All(Function(k) jObj(k) IsNot Nothing)

' Data Service entity properties with special characters use URL encoding:
' Space → _20_    |  Apostrophe → _27_    |  Accented chars preserved as-is
dsEntity.RequiresManualReview     ' "entity field with spaces in schema" (spaces removed at word boundaries)
jObj.Company_20_Name                                      ' "Company Name"
jObj.Additional_20_Info                             ' "Additional Info"
jObj.Street_20_Number_20_and_20_Name                       ' "Street Number and Name"
```

### KeyValuePair Access
```vb
' Variable type: KeyValuePair(Of String, Double) — scg:KeyValuePair(x:String, x:Double)
kvp.Key                                       ' String part
kvp.Value                                     ' Double part

' Common pattern: algorithm returns best match as KeyValuePair
CurrentAddressMatchFound.Key                   ' The matched string
CurrentAddressMatchFound.Value                 ' The match score
```

## Type Conversions

### String ↔ Numeric
```vb
' String to Integer
CInt("42") / Integer.Parse("42") / Convert.ToInt32("42")

' String to Double
CDbl("3.14") / Double.Parse("3.14") / Convert.ToDouble("3.14")

' String to Decimal
CDec("99.99") / Decimal.Parse("99.99")

' Culture-aware parsing (for European decimals like "1.234,56")
Double.Parse(strValue, System.Globalization.CultureInfo.InvariantCulture)
Decimal.Parse(strValue, System.Globalization.NumberStyles.Any, 
  System.Globalization.CultureInfo.GetCultureInfo("pt-BR"))

' Numeric to formatted string
intValue.ToString
decAmount.ToString("F2")         ' "99.99"  — fixed 2 decimals
decAmount.ToString("N2")         ' "1,234.56" — with thousands separator
decAmount.ToString("C")          ' "$99.99" (locale-dependent currency)
decAmount.ToString("C2", System.Globalization.CultureInfo.GetCultureInfo("pt-BR"))  ' "R$ 99,99"
intValue.ToString("D6")          ' "000042" — zero-padded
dblRatio.ToString("P1")          ' "85.5%" — percentage

' Safe numeric parse (in Invoke Code — TryParse returns Boolean)
Dim result As Integer
If Integer.TryParse(strInput, result) Then
    ' use result
End If
```

### Boolean Conversions
```vb
' From string
CBool("True") / Boolean.Parse("true") / Convert.ToBoolean("true")

' From DataRow (common pattern from sample)
CBool(CurrentRow("Mandatory"))               ' Direct cast from Object
Convert.ToBoolean(CurrentRow("IsActive"))

' From numeric
CBool(1)                                      ' True (any non-zero = True)
CBool(0)                                      ' False
```

### DataRow Cell Access & Conversion
```vb
' String (most common — always safe)
CurrentRow("ColumnName").ToString
row("Column Name").ToString.Trim

' Numeric
CInt(CurrentRow("Amount"))
CDbl(CurrentRow("Price"))
Convert.ToDouble(row("Value"))

' Boolean
CBool(CurrentRow("IsRequired"))

' Date
DateTime.Parse(CurrentRow("Date").ToString)
CDate(CurrentRow("Date"))

' Null-safe (DataRow cells can be DBNull)
If(CurrentRow("Column") IsNot Nothing AndAlso 
   Not IsDBNull(CurrentRow("Column")) AndAlso
   Not String.IsNullOrEmpty(CurrentRow("Column").ToString),
   CurrentRow("Column").ToString.Trim, "")

' Shorthand: If column is always populated
CurrentRow("Column").ToString.Trim
```

### JToken Conversions
```vb
' JToken to native types
jObj("count").Value(Of Integer)
jObj("amount").Value(Of Double)
jObj("isActive").Value(Of Boolean)
jObj("name").Value(Of String)

' VB.NET casting shortcuts also work
CInt(jObj("count"))
CDbl(jObj("amount"))
CBool(jObj("isActive"))
jObj("name").ToString                         ' Most common — always safe

' JToken to JObject/JArray
CType(jToken, JObject)
CType(jToken, JArray)

' Native types auto-convert when assigning TO JToken
' In XAML Assign with OutArgument njl:JToken and InArgument njl:JToken:
'   [True] → JToken Boolean
'   [42] → JToken Integer
'   ["text"] → JToken String
'   [new JObject()] → JToken Object
```

### GenericValue (UiPath Proprietary Type)
```vb
gvValue.ToString
CInt(gvValue)
CDbl(gvValue)
```

## Queue Item & Orchestrator

```vb
' Access QueueItem specific content
in_TransactionItem.SpecificContent("FieldName").ToString

' Safe access
If(in_TransactionItem.SpecificContent.ContainsKey("FieldName"), 
   in_TransactionItem.SpecificContent("FieldName").ToString, "")

' Queue item properties
in_TransactionItem.Reference
in_TransactionItem.Priority
in_TransactionItem.DeferDate
in_TransactionItem.DueDate

' Set transaction progress
"Processing item " + in_TransactionItem.Reference
```
