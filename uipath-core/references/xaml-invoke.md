# Invoke Activities

InvokeWorkflowFile, InvokeCode, InvokeMethod.

## Contents
  - [Invoke Workflow File](#invoke-workflow-file)
  - [Invoke Code](#invoke-code)
  - [Invoke Method](#invoke-method)

### Invoke Workflow File
→ **Use `gen_invoke_workflow()`** — generates correct XAML deterministically.

Notes:
- `ArgumentsVariable="{x:Null}"` — always present in real exports (legacy compatibility)
- `x:Key` must exactly match the argument name defined in the invoked workflow
- Arguments can be `InArgument`, `OutArgument`, or `InOutArgument`
- Complex types supported: `njl:JObject`, `scg:List(x:String)`, `sd:DataTable`, custom entity types
- `WorkflowFileName` — relative path from project root (e.g., `"Subfolder\MyWorkflow.xaml"`)
- `UnSafe="False"` — default; `True` allows running in isolated context

**⚠️ Out/InOut arguments MUST have variable bindings.** `<OutArgument ... x:Key="io_uiBrowser" />` (self-closing, no value) or `<OutArgument ...>[]</OutArgument>` means the output is silently lost. Always bind: `<OutArgument ...>[myVariable]</OutArgument>`. Also ensure direction matches argument name prefix: `io_` → `InOutArgument`, `out_` → `OutArgument`, `in_` → `InArgument`. Lint 55.

### Invoke Code
Executes inline VB.NET or C# code within the workflow. Used for multi-statement logic that doesn't fit in a single expression (loops, algorithms, complex transformations).

**⚠️ When NOT to use InvokeCode — prefer MultipleAssign instead:**
InvokeCode is overused. If the code is just assigning expression results to variables (even complex ones like Regex matches, LINQ queries, GroupBy aggregations), use `Assign` or `MultipleAssign` with inline VB expressions. LINQ queries like `.AsEnumerable().Where()`, `.GroupBy()`, `.Select()`, `.OrderBy()` all work as Assign values. InvokeCode should only be used when you need **procedural control flow** inside the code block (loops, `Using` statements, `Try/Catch`, multi-step algorithms that can't be expressed as a single expression).

**⚠️ When NOT to use InvokeCode — DataTable setup belongs in activities:**
Never create a DataTable and add columns inside InvokeCode. Use the activity-based approach:
1. **Initialize** — variable `Default` attribute: `<mva:VisualBasicValue x:TypeArguments="sd:DataTable" ExpressionText="new DataTable" />`
2. **Add columns** — one `AddDataColumn` activity per column (see `xaml-data.md`)
3. **Business logic** — Assign/MultipleAssign with LINQ expressions, or SortDataTable/FilterDataTable activities

❌ **Wrong** — InvokeCode doing everything (schema + logic):
```
Code="Dim dt As New DataTable()&#xA;dt.Columns.Add(&quot;Country&quot;, GetType(String))&#xA;dt.Columns.Add(&quot;Amount&quot;, GetType(Decimal))&#xA;...business logic..."
```
✅ **Right** — activities for setup, Assign for LINQ logic:
- Variable: `dt_Summary` with Default `new DataTable`
- AddDataColumn × N (one per column)
- Assign: `dt_Summary = dt_Raw.AsEnumerable().GroupBy(Function(r) r("Country").ToString).Select(Function(g) ...).CopyToDataTable()`
- SortDataTable for ordering (chain for multi-column)

❌ **Wrong** — InvokeCode just to do regex extractions:
```
Code="Dim m = Regex.Match(body, pattern)&#xA;out_strVendor = If(m.Success, m.Groups(1).Value, &quot;N/A&quot;)"
```

✅ **Right** — MultipleAssign with inline expressions:
→ **Use `gen_multiple_assign()`** — generates correct XAML deterministically.


✅ **Right** — InvokeCode for actual procedural logic (loops, using, multi-step):
```
Code="Using fs As New IO.FileStream(path, IO.FileMode.Create)&#xA;    stream.CopyTo(fs)&#xA;End Using"
```
→ **Use `gen_invoke_code()`** — generates correct XAML deterministically.


Key properties:
- `Language` — `"CSharp"` or `"VBNet"`. Determines code syntax
- `Code` — inline code string. In XAML, newlines are `&#xA;`, tabs are `&#x9;`, `<` is `&lt;`, `>` is `&gt;`, `"` is `&quot;`
- Arguments work the same as InvokeWorkflowFile: `InArgument`, `OutArgument`, `InOutArgument`
- `ContinueOnError="{x:Null}"` — standard; set `True` to swallow exceptions
- **No return statement** — assign results to `OutArgument` variables directly

#### Code String Encoding
The `Code` attribute contains the full code body as an XML-encoded string:
```
// C# source code:
if (x > 0) { result = "positive"; }

// Encoded in XAML Code attribute:
Code="if (x &gt; 0) { result = &quot;positive&quot;; }"
```
Multi-line code uses `&#xA;` for line breaks:
```
Code="int count = 0;&#xA;foreach (string s in list_items)&#xA;{&#xA;    count++;&#xA;}&#xA;out_count = count;"
```

#### Argument Type Patterns
```xml
<!-- Simple types -->
<InArgument x:TypeArguments="x:String" x:Key="str_param">[strVar]</InArgument>
<InArgument x:TypeArguments="x:Int32" x:Key="int_param">[intVar]</InArgument>
<InArgument x:TypeArguments="x:Boolean" x:Key="bool_param">[boolVar]</InArgument>
<InArgument x:TypeArguments="x:Double" x:Key="dbl_param">[dblVar]</InArgument>

<!-- Collections -->
<InArgument x:TypeArguments="scg:List(x:String)" x:Key="list_param">[listVar]</InArgument>
<InArgument x:TypeArguments="scg:Dictionary(x:String, x:Object)" x:Key="dict_param">[dictVar]</InArgument>

<!-- Complex types -->
<OutArgument x:TypeArguments="scg:KeyValuePair(x:String, x:Double)" x:Key="kvp_result">[kvpVar]</OutArgument>
<InOutArgument x:TypeArguments="sd:DataTable" x:Key="dt_data">[dtVar]</InOutArgument>
```

#### Real Example: Levenshtein Distance (C#)
Fuzzy string matching — finds best match from a reference list against lines in a document.
Shows: nested loops, 2D arrays, early exit, KeyValuePair construction, Math operations.
→ **Use `gen_invoke_code()`** — generates correct XAML deterministically.

Notes on this example:
- **InArgument variables can be modified** inside the code (`list_refToMatch.ConvertAll` mutates the input)
- **OutArgument** `key_bestMatch` is assigned at the end — this is how results flow back to the workflow
- **KeyValuePair** used as a simple tuple: `Key` = matched reference, `Value` = similarity percentage
- Similarity formula: `100 - (editDistance / referenceLength * 100)` → 100% = exact match
- **Sliding window** technique: when line is longer than reference, slides a window of reference length across the line to find best substring match

#### When to Use Invoke Code vs Expressions
| Scenario | Use |
|---|---|
| Single-line calculation | Expression (in Assign) |
| LINQ query (Where, Select, GroupBy, OrderBy) | Assign / MultipleAssign — never InvokeCode |
| Sorting a DataTable | SortDataTable activity — never InvokeCode |
| Multi-statement logic, loops, Using blocks | Invoke Code |
| Algorithm with complex state | Invoke Code |
| String manipulation pipeline | Expression if ≤3 chained methods, Invoke Code if more |
| Modifying a DataTable in-place (row-level loop) | Invoke Code (InOutArgument) |
| Calling a void method (Add, Clear) | Invoke Method |

### Invoke Method
Calls a method on an object or a static method on a type. Useful when you need to call a void method that can't be used in an Assign expression (e.g., `JArray.Add()`, `List.Sort()`, `DataTable.AcceptChanges()`).

> ⛔ **Do NOT write InvokeMethod XAML by hand.** Use `gen_invoke_method()` via `generate_workflow.py`.

#### Instance Method Call
```json
{
  "gen": "invoke_method",
  "args": {
    "method_name": "Add",
    "target_object": "jArrItems",
    "target_object_type": "njl:JArray",
    "parameters": [{"type": "njl:JObject", "value": "[jObjNewItem]"}],
    "display_name": "Invoke Method (Append to JArray)"
  }
}
```

Key properties:
- `method_name` — the method to call (e.g., `"Add"`, `"Sort"`, `"Clear"`, `"Remove"`)
- `target_object` + `target_object_type` — instance method on a variable
- `parameters` — positional InArguments passed to the method
- **No return value capture** — for void methods only. Use Assign for methods that return values

#### Static Method Call
```json
{
  "gen": "invoke_method",
  "args": {
    "method_name": "Copy",
    "target_type": "sio:File",
    "parameters": [
      {"type": "x:String", "value": "[strSourcePath]"},
      {"type": "x:String", "value": "[strDestPath]"},
      {"type": "x:Boolean", "value": "[True]"}
    ],
    "display_name": "Invoke Static Method"
  }
}
```
- `target_type` — the type containing the static method (instead of `target_object`)
- Parameters listed as positional typed arguments

#### Common Use Cases
| Call | What it does |
|---|---|
| `JArray.Add(JObject)` | Append JSON object to array |
| `List.Sort()` | In-place sort |
| `List.Clear()` | Remove all items |
| `DataTable.AcceptChanges()` | Commit row changes |
| `File.Copy(src, dst, overwrite)` | Static file copy |
| `Directory.CreateDirectory(path)` | Static directory creation |
