# Control Flow Activities

If, IfElseIf, ForEach, ForEachRow, While, DoWhile, Break/Continue, ForEachFile, Flowchart, State Machine, annotations.

## Contents
  - [If](#if)
  - [If Else If (IfElseIfV2)](#if-else-if-ifelseifv2)
  - [Pick / PickBranch (Parallel Race)](#pick--pickbranch-parallel-race)
  - [For Each](#for-each)
  - [For Each Row in DataTable](#for-each-row-in-datatable)
  - [While](#while)
  - [Do While](#do-while)
  - [Break & Continue (Loop Control)](#break-&-continue-loop-control)
  - [Annotations](#annotations)
  - [For Each File in Folder (ForEachFileX)](#for-each-file-in-folder-foreachfilex)
  - [Flowchart (alternative to Sequence-based workflows)](#flowchart-alternative-to-sequence-based-workflows)
  - [State Machine](#state-machine)
- [Data Manipulation Activities](#data-manipulation-activities)


### If
→ **Use `gen_if()`** — generates correct XAML deterministically.


### If Else If (IfElseIfV2)
Multi-branch conditional — equivalent to `ElseIf` chains. Uses `BindingList` for additional branches.
→ **Use `gen_if_else_if()`** — generates correct XAML deterministically.

Notes:
- **Namespace required:** `xmlns:sc="clr-namespace:System.ComponentModel;assembly=System.ComponentModel.TypeConverter"`
- `Condition` on root element is the first `If` test
- Each `ui:IfElseIfBlock` has `BlockType="ElseIf"` and its own `Condition`
- `BindingList` attributes `AllowEdit="True" AllowNew="True" AllowRemove="True" RaiseListChangedEvents="True"` are always present
- Conditions use XML entity encoding: `&lt;` for `<`, `&gt;` for `>`, `&amp;` for `&`
- Multiline conditions use `&#xA;` for line breaks within attributes

**⚠️ WRONG property names (common hallucination — Studio crashes):**
- `IfElseIfV2.Conditions` → WRONG. Use `IfElseIfV2.ElseIfs` (for extra branches) + `Condition` attribute on root element
- `IfElseIfV2Condition` → WRONG. The type is `IfElseIfBlock`
- `IfElseIfV2Condition.Body` → WRONG. Use `IfElseIfBlock.Then`
- `IfElseIfV2.ElseBody` → WRONG. Use `IfElseIfV2.Else`

### Pick / PickBranch (Parallel Race)

Pick runs multiple PickBranch triggers in parallel — the **first trigger that fires wins**, its Action body executes, and all other branches are cancelled. Primary use case: **login validation** (race between "success element appears" and "error element appears").

**⚠️ MANDATORY for Launch workflows with login.** Every Launch workflow that performs login MUST use Pick to validate the outcome. See golden sample `WebAppName_Launch.xaml` for complete XAML.

→ **Use `gen_pick_login_validation()`** — generates correct XAML deterministically.

Key patterns:
- **OutUiElement** on NCheckState in the error branch → passes the found element to NGetText via `InUiElement` (avoids re-locating the element)
- **NCheckState** is the trigger activity — it blocks until the element appears or times out
- **Throw** in error branch creates an Exception with the actual error message from the page

### For Each
→ **Use `gen_foreach()`** — generates correct XAML deterministically. For DataTable iteration, use `gen_foreach_row()` instead.


### For Each Row in DataTable

→ **Use `gen_foreach_row()`** — generates correct XAML deterministically. Handles ActivityAction wrapper, DelegateInArgument, sd:DataRow TypeArguments.

### While
→ **Use `gen_while()`** — generates correct XAML deterministically.


### Do While
→ **Use `gen_do_while()`** — generates correct XAML deterministically.


### Break & Continue (Loop Control)
→ **Use `gen_break()` and `gen_continue()`** — generates correct XAML deterministically.

Notes:
- Only valid inside loop bodies (ForEach, ForEachRow, While, DoWhile)
- `gen_break()` commonly used with an If condition to exit early when a match is found
- Both produce self-closing elements (no child content)

### Annotations
Add `sap2010:Annotation.AnnotationText="..."` attribute on any activity element. Set `IsAnnotationDocked` ViewState key to `True` (attached) or `False` (floating). Annotations are design-time metadata — the generators don't produce them, but they can be added manually to generated XAML if needed.
- Requires `xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation"`
- Can be added to **any** activity element (Assign, If, Sequence, ForEach, etc.)

### For Each File in Folder (ForEachFileX)

Iterates over files in a directory. Uses two delegate arguments: `CurrentFile` (System.IO.FileInfo) and `CurrentIndex` (Int32).

→ **Use `gen_foreach_file()`** — generates correct XAML deterministically.

Key differences from ForEachRow:
- Requires `xmlns:si="clr-namespace:System.IO;assembly=System.Private.CoreLib"` namespace
- Uses **two** delegate arguments (`Argument1` + `Argument2`) vs one for ForEachRow
- `TypeArguments="si:FileInfo, x:Int32"` — comma-separated pair
- `CurrentFile` properties: `.FullName` (full path), `.Name` (filename), `.Extension`, `.DirectoryName`
- `OrderBy`: `NameAscFirst`, `NameDescFirst`, `DateAscFirst`, `DateDescFirst`, `SizeAscFirst`, `SizeDescFirst`
- `IncludeSubDirectories`: `True`/`False`
- ViewState block appears **after** `.Body` (unlike most activities)
→ **Use `gen_switch()`** — generates correct XAML deterministically.

Notes:
- `x:TypeArguments` sets the switch type: `x:String`, `x:Int32`, etc.
- Case labels go in `x:Key` attribute — these are the match values (can contain spaces: `x:Key="ANY EXISTS"`)
- Case body can be a single activity or a Sequence (for multiple). The generator wraps multi-activity case bodies in Sequence automatically.
- Each case body `DisplayName` is `"Body"` by convention (but not required)
- IdRef uses backtick notation: `` Switch`1_1 ``
- Nested Switch is valid (Switch inside a case's Sequence body)

Real-world example — Switch on DataRow column value with case bodies updating Data Service entity:
→ **Use `gen_switch()`** — generates correct XAML deterministically.

Pattern notes:
- Switch Expression uses DataRow column: `CurrentRow("Column Name").ToString`
- Case keys match exact string values from the data (can contain spaces and hyphens)
- Each case updates a different set of Data Service entity properties
- `Capacity="16"` — set higher than actual operation count to avoid reallocations

### Flowchart (alternative to Sequence-based workflows)
→ **Use `gen_flowchart()`** — generates correct XAML deterministically.

Critical Flowchart rules:
- Requires `xmlns:av="http://schemas.microsoft.com/winfx/2006/xaml/presentation"` for `av:Point`, `av:Size`, `av:PointCollection`
- Nodes use `__ReferenceID{N}` naming (Studio convention for cross-references)
- `Flowchart.StartNode` references the first FlowStep
- FlowDecision conditions use `<VisualBasicValue x:TypeArguments="x:Boolean" ExpressionText="..." />`
- All `x:Name` references must be listed as `<x:Reference>` at end of Flowchart
- Each FlowStep/FlowDecision needs `ShapeLocation` and `ShapeSize` ViewState for Studio layout

### State Machine

Used by REFramework Main.xaml. States contain Entry actions and Transitions with conditions that route to other states. The XAML structure is deeply nested — `gen_state_machine()` handles all of it: inline state definitions, `x:Reference` back-references, ViewState, and `av:` namespace.

```json
{
  "gen": "state_machine",
  "args": {
    "states": [
      {
        "ref": "S0", "display_name": "State A",
        "entry_content": "<!-- entry activities -->",
        "transitions": [
          {"to_ref": "S1", "display_name": "Go to B", "condition": "boolCondition"},
          {"to_ref": "S2", "display_name": "Go to Final (no condition)"}
        ]
      },
      {
        "ref": "S1", "display_name": "State B",
        "transitions": [
          {"to_ref": "S0", "display_name": "Back to A", "condition": "otherCondition"},
          {"to_ref": "S2", "display_name": "Go to Final"}
        ]
      },
      {"ref": "S2", "display_name": "End", "is_final": true}
    ],
    "initial_state_ref": "S0"
  }
}
```

**Critical structural rules:**
1. `InitialState="{x:Reference __ReferenceID_N}"` — points to the starting state's `x:Name`
2. **First reference defines inline, subsequent references use `<x:Reference>`:** Each State is defined in full XML exactly once — inside the first `Transition.To` that targets it. All other transitions to that state use `<x:Reference>__ReferenceID_N</x:Reference>`
3. **Final state:** REFramework uses `IsFinal="True"` on a regular `<State>` element. Studio also supports a standalone `<FinalState>` element (only has Entry, no Exit or Transitions). Both are valid. Final states have `State.Entry` but no `State.Transitions`
4. **All back-referenced states listed at StateMachine level:** After the first inline State, all other states appear as `<x:Reference>` elements directly inside StateMachine (before `.Variables`)
5. **Transitions are ordered:** First matching condition wins. Omit `Transition.Condition` for the default/fallback transition (should be last)

**ViewState keys specific to StateMachine/State:**
- `ShapeLocation` (`av:Point`) — position in the designer canvas
- `StateContainerWidth` / `StateContainerHeight` (`x:Double`) — state box dimensions
- `ConnectorLocation` (`av:PointCollection`) — arrow path between states, on both StateMachine and Transition ViewState
- `SrcConnectionPointIndex` / `DestConnectionPointIndex` (`x:Int32`) — connector anchor points on Transition ViewState
- Requires `xmlns:av="http://schemas.microsoft.com/winfx/2006/xaml/presentation"`

**State child elements:**
- `State.Entry` — activities executed when entering the state (Sequence or single activity)
- `State.Exit` — activities executed when leaving the state (optional, not used in REFramework). Runs before the transition's Action
- `State.Transitions` — container for all outgoing Transition elements

**Transition child elements (order varies in exports):**
- `Transition.Trigger` — activity that triggers the transition evaluation (optional, not used in REFramework). In most cases transitions are evaluated automatically after the Entry completes
- `Transition.Condition` — VB.NET boolean expression (optional — omit for default/fallback transition)
- `Transition.Action` — activities to execute during the transition, after Condition is true but before entering the target state (optional)
- `Transition.To` — target state (inline `<State>` or `<x:Reference>`)
- **Order in exports varies** — Studio exports these in different orders. Common pattern: `.To` → `.Action` → `.Condition`. Sometimes `.Condition` appears before `.To`

**FinalState variants:**
- REFramework uses `IsFinal="True"` on a regular `<State>` element (most common in real exports)
- Studio also supports a standalone `<FinalState>` element (functionally identical, only has Entry section — no Exit or Transitions)
- Only **one initial state** is allowed, but **multiple Final States** are permitted

**REFramework State Machine structure (4 states):**
```
Initialization ──[Success]──> Get Transaction Data
    ^                              |
    |                    [New Transaction]──> Process Transaction
    |                              |              |    |    |
    |                    [No Data]──> End Process  |    |    |
    |                                              |    |    |
    +────────[System Exception]────────────────────+    |    |
             [Business Exception]───────────────────────+    |
             [Success]───────────────────────────────────────+
                              (both go back to Get Transaction Data)
```

**Argument default values on root Activity:**
REFramework Main.xaml sets argument defaults using the `this:` namespace prefix (e.g., `this:Main.in_boolAttendedRun="True"` on the `<Activity>` element). The `this:` prefix references the workflow's own class namespace. Scaffold handles this.

## Data Manipulation Activities
