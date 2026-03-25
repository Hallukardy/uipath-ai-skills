# Expression Foundations

VB.NET expression syntax, C# expression syntax, null safety patterns. Read this first for any expression task.

## Contents
- [VB.NET Expressions](#vbnet-expressions)
  - [Common Patterns](#common-patterns)
  - [VB.NET String Concatenation: `+` vs `&`](#vbnet-string-concatenation-`+`-vs-`&`)
  - [Multiline Expressions in XAML](#multiline-expressions-in-xaml)
- [C# Expressions](#c#-expressions)
  - [Common Patterns](#common-patterns)
- [Null Safety Patterns](#null-safety-patterns)
  - [VB.NET](#vbnet)
  - [C#](#c#)

## VB.NET Expressions

### Common Patterns
```vb
' String interpolation (not supported in VB.NET expressions — use concatenation)
"Hello " + strName + ", welcome!"

' Ternary / inline If
If(boolCondition, "Yes", "No")

' Null coalescing
If(strValue, "default")
If(strValue IsNot Nothing, strValue, "default")

' Nothing check
strValue Is Nothing
strValue IsNot Nothing
String.IsNullOrEmpty(strValue)
String.IsNullOrWhiteSpace(strValue)

' Array initialization
New String() {"item1", "item2", "item3"}
New Object() {strName, intAge, True}

' List initialization
New List(Of String) From {"item1", "item2"}

' Dictionary initialization
New Dictionary(Of String, Object) From {
  {"key1", "value1"},
  {"key2", 42}
}

' Casting
CStr(objValue)
CInt(strNumber)
CDbl(strDecimal)
CBool(strBoolean)
CType(objValue, DataTable)
DirectCast(objValue, String)
Convert.ToInt32(strValue)
Convert.ToDateTime(strDate)

' Exception creation (for Throw activities)
New Exception("Processing failed: " + exception.Message)
New BusinessRuleException("Invalid invoice number")
New ApplicationException("System not responding")

' Global Variables access (UiPath global namespace pattern)
GlobalVariablesNamespace.GlobalVariables.config("SettingKey").ToString
CInt(GlobalVariablesNamespace.GlobalVariables.config("MaxRetries"))

' Document Understanding field access
DocumentDataExtracted.Data.GetFieldValue("FieldName").Value
DocumentDataExtracted.Data.GetFieldValue(strFieldName) IsNot Nothing

' Document Understanding — GetField API (more detailed access)
DocumentDataExtracted.Data.GetField("Company Name").IsMissing   ' Boolean: field not found by DU
DocumentDataExtracted.Data.GetField("FieldName").Values                  ' collection of extracted values
DocumentDataExtracted.Data.GetField("FieldName").Values.First().Value    ' first extracted value as string
DocumentDataExtracted.Data.GetField("FieldName").Values.FirstOrDefault   ' Nothing if no values

' Safe field extraction pattern (null-safe, handles missing fields)
If(Not DocumentDataExtracted.Data.GetField("Company Name").IsMissing And _
  DocumentDataExtracted.Data.GetField("Company Name").Values.FirstOrDefault IsNot Nothing, _
  DocumentDataExtracted.Data.GetField("Company Name").Values.First().Value, _
  "Marked as missing")
' .IsMissing = True → field not found at all by classifier
' .Values.FirstOrDefault = Nothing → field found but no value extracted
```

### VB.NET String Concatenation: `+` vs `&`
```vb
' Both work in VB.NET UiPath expressions
"Hello " + strName                            ' + operator
"Hello " & strName                            ' & operator (VB.NET native)

' & is safer — auto-converts non-strings, + can fail on type mismatch
"Count: " & intCount                          ' Works (auto-ToString)
"Count: " + intCount.ToString                 ' Also works (explicit)
"Count: " + intCount                          ' May fail! String + Integer = error

' In XAML attributes, & must be entity-encoded as &amp;
' So [str1 & str2] in XAML becomes:
' Expression="[str1 &amp; str2]"
```

### Multiline Expressions in XAML

Short expressions go inline in the JSON spec value. Long expressions work the same way — the generators handle `xml:space="preserve"` wrapping, `&#xA;` line breaks, and all XML entity encoding (`&quot;`, `&amp;`, `&lt;`) internally via `_escape_vb_expr()`. Write expressions in plain VB.NET/C# in the JSON spec; never pre-encode.

**XAML entity encoding in expressions:**
- `&quot;` → `"` (string literals inside XAML attributes)
- `&amp;` → `&` (VB.NET concatenation operator)
- `&gt;` → `>` (greater-than or used in strings like `str.Contains(">")`
- `&lt;` → `<` (less-than comparison)
- `&lt;&gt;` → `<>` (VB.NET not-equal operator — common in LINQ lambdas)
- `&#xA;` → newline (XAML attribute formatting for multiline expressions)
- `&#x9;` → tab (XAML attribute indentation — formatting only, not part of expression)

**VB.NET comparison operators:**
- `=` (equal) / `<>` (not equal) — NOT `==` / `!=` like C#
- `<` / `>` / `<=` / `>=`
- `AndAlso` / `OrElse` (short-circuit) — NOT `&&` / `||`
- `Not` (logical negation) — NOT `!`
- `Is Nothing` / `IsNot Nothing` — reference equality check

## C# Expressions

### Common Patterns
```csharp
// String interpolation
$"Hello {strName}, welcome!"

// Ternary
boolCondition ? "Yes" : "No"

// Null coalescing
strValue ?? "default"

// Null conditional
strValue?.Trim()
dictConfig?.ContainsKey("key") ?? false

// Array
new string[] {"item1", "item2", "item3"}
new object[] {strName, intAge, true}

// List
new List<string> {"item1", "item2"}

// Dictionary
new Dictionary<string, object> {
  {"key1", "value1"},
  {"key2", 42}
}

// Casting
(string)objValue
int.Parse(strNumber)
Convert.ToInt32(strValue)
Convert.ToDateTime(strDate)
```

## Null Safety Patterns

Critical for avoiding NullReferenceException in production:

### VB.NET
```vb
' Safe DataRow access
If(row("Column") IsNot Nothing AndAlso Not String.IsNullOrEmpty(row("Column").ToString), row("Column").ToString.Trim, "")

' Safe dictionary access
If(dictConfig.ContainsKey("key"), dictConfig("key").ToString, "default")

' Safe string operations
If(String.IsNullOrEmpty(strInput), "", strInput.Trim.ToUpper)

' Null-safe chaining pattern
If(objResult IsNot Nothing, If(objResult.ToString IsNot Nothing, objResult.ToString.Trim, ""), "")
```

### C#
```csharp
// Safe DataRow
row["Column"]?.ToString()?.Trim() ?? ""

// Safe dictionary
dictConfig.ContainsKey("key") ? dictConfig["key"]?.ToString() ?? "default" : "default"

// TryGetValue pattern (in Invoke Code)
dictConfig.TryGetValue("key", out var val) ? val?.ToString() ?? "" : ""
```

