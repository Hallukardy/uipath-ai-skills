# UI Inspection Reference

Reference documentation for the `inspect-ui-tree.ps1` PowerShell script. This script uses the Windows UI Automation (UIA) API to inspect desktop application UI structures and generate UiPath-compatible selector information.

## Contents
- Quick Start
- Parameters
- Output Formats (tree, flat, selectors, json)
- Flags Reference
- Framework Detection
- UiPath Activity Mapping (WinForms inferred types)
- WinForms Spatial Label Association
- DataGrid/Table Collapse
- Sample Outputs (Calculator UWP, Desktop App WinForms)
- Workflow: Using Inspect Output to Build UiPath Automation
- Dynamic Name Detection
- Troubleshooting

## Quick Start

```powershell
# Basic tree view
.\inspect-ui-tree.ps1 -WindowTitle "Calculator" -OutputFormat tree

# Generate UiPath selectors
.\inspect-ui-tree.ps1 -WindowTitle "Calculator" -OutputFormat selectors

# Match by process name
.\inspect-ui-tree.ps1 -ProcessName "desktopapp.exe" -OutputFormat tree

# Match by window class
.\inspect-ui-tree.ps1 -WindowClass "CabinetWClass" -OutputFormat flat

# JSON output for programmatic use
.\inspect-ui-tree.ps1 -WindowTitle "Calculator" -OutputFormat json

# Control depth and element count
.\inspect-ui-tree.ps1 -WindowTitle "*Notepad" -OutputFormat tree -MaxDepth 4 -MaxElements 100
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-WindowTitle` | "" | Window title (supports wildcards: `*Notepad`, `Create Purchase*`) |
| `-WindowClass` | "" | Window ClassName (e.g., `CabinetWClass`) |
| `-ProcessName` | "" | Process name with extension (e.g., `desktopapp.exe`) |
| `-MaxDepth` | 8 | Maximum UI tree traversal depth |
| `-MaxElements` | 200 | Maximum elements to output (prevents runaway on deep apps) |
| `-OutputFormat` | tree | `tree`, `flat`, `selectors`, or `json` |


## Output Formats

### tree
Indented hierarchy showing all element properties. Best for understanding app structure.

### flat
Pipe-delimited rows for scripting/parsing: `Type|Name|AutomationId|ClassName|FrameworkId|Patterns|Rect|Idx|Flags`

### selectors
Ready-to-use UiPath `<wnd>` + `<uia>` selector pairs with activity hints. Only emits interactive/actionable elements.

### json
Structured JSON for programmatic consumption. Includes full metadata, type counts, and duplicate tracking.

## Flags Reference

| Flag | Meaning | Impact on Selectors |
|------|---------|-------------------|
| `[!NO_AID]` | Missing AutomationId | Selector depends on `name` — locale-fragile |
| `[!NO_CLS]` | Missing ClassName | Less selector specificity |
| `[!DYNAMIC]` | Name has dynamic content (numbers, dates, counters) | Use wildcard: `name='Display is *'` |
| `[!DUP_AID]` | AutomationId not unique among siblings | Needs `idx` attribute |
| `[!DUP_NAME]` | Name+ClassName not unique among siblings | Needs `idx` attribute |
| `[!POS_AID]` | AutomationId is a numeric positional index | Unstable — changes with content |
| `[!VERIFY_TYPE]` | WinForms Button* could be CheckBox/RadioButton | Verify in UiPath UI Explorer |
| `[!EMPTY_FIELD]` | Edit field with no current text | Field exists but currently blank |
| `[!DISABLED]` | Element is not enabled | May need `Wait for Element` before interacting |

## Framework Detection

The script auto-detects the application framework and adjusts its behavior:

| Framework | Detection | Selector Style | Notes |
|-----------|-----------|---------------|-------|
| UWP | `ClassName = ApplicationFrameWindow` | `<wnd appid='...' />` + `<uia>` | Resolves AppId from package |
| WPF | `FrameworkId = WPF` | `<wnd>` + `<uia automationid='...' />` | Rich automation support |
| Win32 | `FrameworkId = Win32` | `<wnd>` + `<uia>` | Standard controls |
| DirectUI | `FrameworkId = DirectUI` | `<wnd>` + `<uia>` | Explorer shell, some system UI |
| WinForms | `FrameworkId = WinForm` or `ClassName ~ WindowsForms10.*` | `<ctrl name='...' />` (default), `<wnd ctrlname='...' />` (with UI Explorer) | Script generates `<ctrl>` selectors; UI Explorer needed for `ctrlname` |

## UiPath Activity Mapping

The script maps ControlTypes and UIA patterns to UiPath activities:

| ControlType | Activity Hint |
|-------------|-------------|
| Edit, Document | Type Into / Get Text |
| Button | Click |
| Button (with Toggle pattern) | Check / Uncheck |
| CheckBox | Check / Uncheck |
| RadioButton | Select Item |
| ComboBox | Select Item |
| ListItem | Select Item / Click |
| TabItem | Select Item |
| MenuItem, Hyperlink | Click |
| Text | Get Text |
| DataGrid, Table | Extract Data / For Each Row |
| Slider | Set Range Value |

### WinForms inferred types

The script infers control types from WinForms ClassNames:

| ClassName Pattern | Inferred Type |
|------------------|--------------|
| `WindowsForms10.EDIT.*` | Edit |
| `WindowsForms10.BUTTON.*` | Button* (could be Button, CheckBox, or RadioButton) |
| `WindowsForms10.COMBOBOX.*` | ComboBox |
| `WindowsForms10.STATIC.*` | Label |
| `WindowsForms10.RichEdit20W.*` | RichTextBox |
| `WindowsForms10.SysListView32.*` | ListView |
| `WindowsForms10.SysTreeView32.*` | TreeView |
| `WindowsForms10.SysDateTimePick32.*` | DatePicker |
| `WindowsForms10.Window.*` | Container |

## WinForms Spatial Label Association

For WinForms apps, the script uses BoundingRectangle proximity to associate labels with their adjacent input fields:

**Primary match** — label to the left on the same row (Y within 15px, label's right edge before field's left edge).

**Fallback** — label directly above (X within 30px, label's bottom above field's top).

This produces output like:
```
Edit 'Oscar' (near: 'First') -> Type Into / Get Text
ComboBox 'NY' (near: 'State') -> Select Item
```

## DataGrid/Table Collapse

DataGrid and Table elements are collapsed into a summary instead of recursing into every cell:
```
[2] === DataGrid: listView (rows=5, cols=3) ===
  Columns: Name | Email | Phone
  -> Activity: Extract Data / For Each Row
```



## Sample Outputs

### Sample 1: Calculator (UWP)

**Command:** `.\inspect-ui-tree.ps1 -WindowTitle "Calculator" -OutputFormat selectors`

```
=== UI TREE INSPECTION ===

Window:
  Title         = Calculator
  ClassName     = ApplicationFrameWindow
  FrameworkId   = Win32
  ProcessName   = ApplicationFrameHost.exe
  UWP AppId     = Microsoft.WindowsCalculator_8wekyb3d8bbwe!App

UiPath Window Selector:  <wnd app='applicationframehost.exe' appid='Microsoft.WindowsCalculator_8wekyb3d8bbwe!App' />
  (add cls='ApplicationFrameWindow' or title='Calculator' only if multiple windows need disambiguation)

# Display is 0 (Text) [!NO_CLS,DYNAMIC]
<wnd app='applicationframehost.exe' appid='Microsoft.WindowsCalculator_8wekyb3d8bbwe!App' />
<uia automationid='CalculatorResults' name='Display is *' role='text' />
# Activity: Get Text (Name attribute)

# Seven (Button)
<wnd app='applicationframehost.exe' appid='Microsoft.WindowsCalculator_8wekyb3d8bbwe!App' />
<uia automationid='num7Button' cls='Button' />
# Activity: Click

# Equals (Button)
<wnd app='applicationframehost.exe' appid='Microsoft.WindowsCalculator_8wekyb3d8bbwe!App' />
<uia automationid='equalButton' cls='Button' />
# Activity: Click

=== Summary ===
Total elements: 56 (max: 200, depth: 6)
```

**Key observations:**
- UWP apps need `appid` in the window selector
- All buttons have stable AutomationIds (`num7Button`, `equalButton`)
- Display text is dynamic (`Display is 0`) → wildcarded to `Display is *`
- Window title doesn't need wildcarding (Calculator is fixed)

### Sample 2: Desktop App (WinForms)

**Command:** `.\inspect-ui-tree.ps1 -WindowTitle "Desktop App*" -OutputFormat tree -MaxDepth 4`

```
=== UI TREE INSPECTION ===

Window:
  Title         = Desktop App (Sample App)
  ClassName     = WindowsForms10.Window.8.app.0.378734a
  FrameworkId   = WinForm
  ProcessName   = DesktopApp.exe

  ** WinForms Detected **

NOTE: WinForms .NET Control.Name (ctrlname/automationid) is NOT accessible
  via standard APIs. Use UiPath UI Explorer to capture real selectors.

[0] === Desktop App (Sample App) ===
  [1] TabControl (empty) -> Click tab item
    [2] === People ===
      [3] === Name: ===
        [4] Button* 'Female' -> Click [!VERIFY_TYPE]
        [4] Button* 'Male' -> Click [!VERIFY_TYPE]
        [4] Label: 'Last:'
        [4] Label: 'First:'
        [4] Edit 'Smith' (near: 'Last') -> Type Into / Get Text
        [4] Edit 'Jane' (near: 'First') -> Type Into / Get Text
      [3] === Email ===
        [4] Edit 'work.email@example.com' (near: 'Work') -> Type Into / Get Text
        [4] Edit 'personal.email@example.com' (near: 'Personal') -> Type Into / Get Text
      [3] === Phone ===
        [4] Edit '555-012-3456' (near: 'Mobile') -> Type Into / Get Text [!DYNAMIC]
        [4] Edit '555-098-7654' (near: 'Home') -> Type Into / Get Text [!DYNAMIC]
      [3] === Address ===
        [4] ComboBox 'NY' (near: 'State') -> Select Item
        [4] Edit '90210' (near: 'Zip') -> Type Into / Get Text [!DYNAMIC]
        [4] Edit '742 Evergreen Terrace' (near: 'Add Line 1') -> Type Into / Get Text [!DYNAMIC]

=== Summary ===
Total elements: 37 (max: 200, depth: 4)
Framework: WinForms (.NET)
Controls: Edit:12, Label:12, Container:7, Button*:4, ComboBox:1, TabControl:1
Selector strategy: <wnd> chains with ctrlname attribute (requires UI Explorer)
```

**Key observations:**
- WinForms apps expose everything as `Pane` via UIA — script infers types from ClassNames
- `Button*` indicates ambiguity: could be Button, CheckBox, or RadioButton (Male/Female are likely RadioButtons)
- Spatial label association works: `Edit 'Oscar' (near: 'First')` correctly pairs the field with its label
- Phone numbers flagged as `[!DYNAMIC]` — they contain digit patterns
- `selectors` mode generates `<ctrl name='...' role='...' />` selectors for WinForms using UIA Name property
- For more stable `ctrlname` selectors, use UiPath UI Explorer

### WinForms Tab Control Hierarchy (CRITICAL)

In the Sample 2 output above, the hierarchy reveals:
```
[1] TabControl (empty) -> Click tab item
  [2] === People ===           <- TabItem -- NAVIGATION TARGET
    [3] === Name: ===          <- GroupBox -- visual container INSIDE People tab
    [3] === Email ===          <- GroupBox -- visual container
    [3] === Phone ===          <- GroupBox -- visual container, NOT a tab
    [3] === Address ===        <- GroupBox -- visual container, NOT a tab
```

**Key distinction:**
- **Children of TabControl** (depth [2]) = **TabItems** — these are the clickable tabs. Use their names for navigation selectors (`aaname='People'`).
- **Children of a TabItem** (depth [3]) = **GroupBoxes** — visual containers that organize fields on that tab's page. Do NOT use their names for tab navigation.

**Why this matters:** The tree only expands the **active tab**. If DesktopApp has tabs People/Company/Other but "People" is active, you'll see People expanded with its GroupBoxes (Name, Email, Phone, Address). The other tabs (Company, Other) appear at depth [2] but are collapsed. The model must NOT assume "Phone" and "Address" are tab names — they're GroupBoxes visible because People is active.

**Verification:** Ask the user to confirm the tab names, or inspect with `-MaxDepth 2` to see only TabControl and its direct TabItem children without GroupBox noise.

## Workflow: Using Inspect Output to Build UiPath Automation

1. **Run inspection** against the target application
2. **Identify interactive elements** — look for activity hints in the output
3. **Check flags** — elements with `[!DUP_AID]` need `idx`, `[!DYNAMIC]` needs wildcards
4. **For WinForms** — `selectors` mode generates `<ctrl name='...' />` selectors. For more stable `ctrlname` selectors, use UiPath UI Explorer
6. **For standard apps** (UWP, WPF, Win32) — the generated selectors are ready to use in XAML workflows

## Dynamic Name Detection

The script flags names as `[!DYNAMIC]` when they contain patterns likely to change between runs:

| Pattern | Example |
|---------|---------|
| Calculator display | `Display is 42` |
| Status counters | `3 items`, `Line 7` |
| Dates | `15/02/2026`, `2026-02-15` |
| Timestamps | `14:30:00` |
| Phone numbers | `718-860-7100` |
| Large numbers | `4500021714` |
| IDs with 4+ digits | `DOC0012345` |
| Currency | `$1,234.56` |
| Percentages | `42.5%` |

Dynamic names are wildcarded in selector output: `name='Display is *'`

## Troubleshooting

**"Window not found"** — The script lists all available windows. Check title spelling, try wildcards, or use `-ProcessName` instead.

**WinForms selectors use `<ctrl>` tags** — The script generates `<ctrl name='...' role='...' />` selectors from UIA Name property. For more stable `ctrlname`/`automationid` selectors, use UiPath UI Explorer.


**Too many elements / truncated** — Increase `-MaxElements` and `-MaxDepth`. For very large apps, use `-OutputFormat json` and filter programmatically.

**Empty output for some controls** — Some frameworks (DirectUI, some custom controls) expose limited UIA data. Use UiPath UI Explorer for manual inspection.
