# UI Automation & Selectors

NApplicationCard (browser + desktop), NClick, NTypeInto, NSelectItem, NGetText, NExtractDataGeneric, NGoToUrl, NGetUrl, NCheckState, TargetAnchorable patterns, selector syntax, dynamic selectors, wildcards, fuzzy/regex search, anchor-based targeting, desktop selector frameworks.

## Contents
  - [Use Application/Browser (NApplicationCard)](#use-applicationbrowser-napplicationcard)
  - [Desktop Selector Frameworks](#desktop-selector-frameworks)
  - [Click (NClick)](#click-nclick)
  - [Type Into (NTypeInto)](#type-into-ntypeinto)
  - [Select Item (NSelectItem)](#select-item-nselectitem)
  - [Get Text (NGetText)](#get-text-ngettext)
  - [Extract Table Data (NExtractDataGeneric)](#extract-table-data-nextractdatageneric)
  - [Go To URL (NGoToUrl)](#go-to-url-ngotourl)
  - [Get URL (NGetUrl)](#get-url-ngeturl)
  - [Check App State (NCheckState)](#check-app-state-ncheckstate)
  - [Target Element Patterns](#target-element-patterns)
- [Selector Reference](#selector-reference)
  - [Selector Syntax and Structure](#selector-syntax-and-structure)
  - [Full vs Partial Selectors](#full-vs-partial-selectors)
  - [Tag Types and Key Attributes](#tag-types-and-key-attributes)
  - [Dynamic Selectors (Variables in Selectors)](#dynamic-selectors-variables-in-selectors)
  - [Wildcards](#wildcards)
  - [Fuzzy Search](#fuzzy-search)
  - [RegEx Search](#regex-search)
  - [Non-Greedy Search (idx='*')](#non-greedy-search-idx=*)
  - [Table Element Selectors](#table-element-selectors)
  - [Anchor-Based Targeting](#anchor-based-targeting)
  - [Selector Best Practices](#selector-best-practices)
- [XAML Special Characters](#xaml-special-characters)


Requires `xmlns:uix="http://schemas.uipath.com/workflow/activities/uix"` on root Activity.

These are the Modern Design Experience activities (Studio 24.10+, required minimum). They replace classic activities like `AttachBrowser`, `OpenBrowser`, `Click`, `TypeInto`. Real templates in `assets/samples/common-workflows/` and `assets/simple-sequence/FormFilling_Main.xaml`.

Required namespace imports (in `TextExpression.NamespacesForImplementation`):
```
UiPath.UIAutomationNext.Enums
UiPath.UIAutomationCore.Contracts
UiPath.UIAutomation.Models
UiPath.UIAutomation.Activities
UiPath.Shared.Activities
```

> **⚠️ The NuGet package is `UiPath.UIAutomation.Activities` but the CLR enum namespace is `UiPath.UIAutomationNext.Enums`.** The package was renamed, but the enum types kept the old namespace. All fully-qualified enum values in expressions use `UIAutomationNext`: `[UiPath.UIAutomationNext.Enums.NAppOpenMode.Always]`, `[UiPath.UIAutomationNext.Enums.NClickMode.None]`, etc. Do NOT "fix" this to `UIAutomation.Enums` — that namespace does not exist and will cause a compile error.
For Extract Table Data, also add: `UiPath.UIAutomation.Models.ExtractData`

Required assembly references:
```
UiPath.UIAutomation.Activities
UiPath.UIAutomationCore
```

### Use Application/Browser (NApplicationCard)

The container for all modern UI interactions. Wraps any browser or desktop app actions.

**CRITICAL — Browser vs Desktop App:**
- **Browser apps** use `BrowserType` + `Url` in `TargetApp`, selector root is `<html app='...' />`
- **Desktop apps** use `FilePath` in `TargetApp`, selector root is `<wnd app='...' />`
- The `FilePath` attribute is **REQUIRED** for desktop apps when `OpenMode` is `IfNotOpen` or `Always` — without it UiPath cannot launch the application
- ⛔ **`Url` does NOT exist as an attribute on NApplicationCard itself** — it goes in the `<uix:TargetApp Url="...">` child element. Same for `FilePath`, `BrowserType`, `Selector`, `Title`.

#### Browser example (Chrome/Edge)
→ **Use `gen_napplicationcard_open() / gen_napplicationcard_attach() / gen_napplicationcard_desktop_open()`** — generates correct XAML deterministically.


#### Desktop app example — traditional .exe (WinForms/WPF)
→ **Use `gen_napplicationcard_open() / gen_napplicationcard_attach() / gen_napplicationcard_desktop_open()`** — generates correct XAML deterministically.


#### Desktop app example — UWP / Microsoft Store app
UWP apps use the package AppId as `FilePath` and `applicationframehost.exe` in the selector.
→ **Use `gen_napplicationcard_open() / gen_napplicationcard_attach() / gen_napplicationcard_desktop_open()`** — generates correct XAML deterministically.


**Desktop apps:** No `BrowserType`, no `Url`. Selector uses `<wnd>` root (not `<html>`). No `InUiElement`/`OutUiElement` chaining.

**Traditional .exe vs UWP:**
- **Traditional** (.exe): `FilePath` is the full path to the executable. Selector `<wnd app='desktopapp.exe' .../>`. WinForms apps often use `ctrlname` in selector.
- **UWP / Store apps**: `FilePath` is the package AppId (e.g. `Microsoft.WindowsCalculator_8wekyb3d8bbwe!App`). Selector uses `app='applicationframehost.exe'` with `appid='...'` attribute.
- UWP apps omit `TargetApp.WorkingDirectory`.

**TargetApp child elements:**
- `TargetApp.Arguments` — `InArgument(x:String)`, command-line args to pass when launching. Always present (empty = no args).
- `TargetApp.WorkingDirectory` — `InArgument(x:String)`, working directory for launch. Present for traditional .exe apps, omitted for UWP.

**Studio-generated metadata (optional, added by Studio during recording):**
- `ContentHash` — hash of UI snapshot
- `IconBase64` — base64 PNG of the app icon
- `Reference` — encoded reference ID for targeting

Key attributes:
- `OpenMode`: `Always` (launch new), `IfNotOpen` (reuse or launch), `Never` (must be already open). Omitting defaults to `IfNotOpen`. **In Launch workflows: use `Always` — this opens the browser at `TargetApp Url=`, so NGoToUrl is NOT needed. NGoToUrl is for mid-session navigation only.**
- `CloseMode`: `Always` (close when done), `Never` (leave open), `IfOpenedByAppBrowser` (close only if this activity opened it). Omitting defaults to `Never`. For browser close/logout → see `skill-guide.md` Rule 10.
- `AttachMode`: **ONLY two valid values:** `SingleWindow` (browser typical), `ByInstance` (desktop typical — attaches to any window of the process). **NEVER use `ByUrl`** — this value does NOT exist in the `NAppAttachMode` enum and will crash Studio with "ByUrl is not a valid value for NAppAttachMode". This is the #1 hallucinated enum value for this activity.
- `InteractionMode`: `Simulate` (browser default), `DebuggerApi`, `WindowMessages`, `HardwareEvents`. Child activities use `SameAsCard` to inherit
- `WindowResize`: `None` (default), `Maximize`, `Minimize`, `Restore`. Set on the NApplicationCard element
- `HealingAgentBehavior`: `Job` (default for NApplicationCard) — controls AI-based selector healing
- `InUiElement`/`OutUiElement`: pass browser/app reference via `ui:UiElement` argument. Launch workflows use `OutUiElement="[out_uiAppName]"` (OutArgument). Action workflows use `InUiElement="[io_uiAppName]"` + `OutUiElement="[io_uiAppName]"` (InOutArgument — preserves updated reference). One variable per web app → see `skill-guide.md` Rule 11.
- `IsIncognito`: **Always `"True"` for browser automation.** Private/incognito mode — no cached sessions, cookies, or saved credentials interfere. Omit for desktop apps.
- **Browser TargetApp**: `BrowserType` (`Edge`, `Chrome`, `Firefox`), `Url` (string or `[expression]`)
- **Desktop TargetApp**: `FilePath` (full path to `.exe` or UWP AppId). **REQUIRED** when `OpenMode` is `IfNotOpen` or `Always`
**Version attribute — each activity type has its own valid set (Studio crashes on invalid values):**

| Activity | Recommended | Also valid | ❌ Crash |
|---|---|---|---|
| `NApplicationCard` | `V2` | `V1` | ~~V3, V4~~ |
| `TargetApp` | `V2` | | |
| `NClick`, `NTypeInto`, `NGetText`, `NCheckState` | `V5` | `V1` | |
| `NGoToUrl` | `V3` | | |
| `NSelectItem` | `V1` | | |
| `NExtractDataGeneric` | `V5` | | |
| `TargetAnchorable` | `V6` | | |

⚠️ **Do NOT use the same Version value across all activities.** Each has its own enum. `V4` on `NApplicationCard` causes: `V4 is not a valid value for NApplicationCardVersion` → Studio crash.

**`.OCREngine` — NEVER include this child element.** Studio exports an empty OCREngine ActivityFunc delegate on some templates, but it serves no purpose in generated XAML:
- **Browser apps**: OCR is meaningless — the DOM provides all text natively via selectors
- **Desktop apps**: Standard UIA selectors (`automationid`, `ctrlname`, `name`) cover virtually all cases. OCR is only relevant for Citrix/VDI or legacy apps with no accessibility tree, and those require a configured OCR engine (not an empty delegate)

The empty delegate adds complexity (requires `System.Drawing` namespace declarations that conflict with `System.Data` prefixes) and zero functionality. **Always omit it.**

Child order in XAML: `.Body` → `.TargetApp` (no `.OCREngine`)

### Desktop Selector Frameworks

Different Windows UI frameworks produce different selector patterns. Use `scripts/inspect-ui-tree.ps1` to detect the framework and generate appropriate selectors.

#### UWP / WPF / Win32 — `<wnd>` + `<uia>` selectors
Standard apps with proper UIA support. The inspection script generates ready-to-use selectors:
```
ScopeSelectorArgument:  <wnd app='applicationframehost.exe' appid='...' />
FullSelectorArgument:   <uia automationid='num7Button' cls='Button' />
```

Key selector attributes: `automationid` (most stable), `cls`, `name`/`aaname`, `role`.

#### WinForms — `<ctrl name='...' />` selectors (primary) or `<wnd ctrlname='...' />` (with UI Explorer)

WinForms apps expose all elements as `ControlType=Pane` via standard UIA. UiPath uses a proprietary .NET bridge to read `Control.Name` and exposes it as both `ctrlname` and `automationid`.

**Primary approach — `<ctrl>` selectors:** The `inspect-ui-tree.ps1` script generates `<ctrl name='...' role='...' />` selectors using UIA Name and inferred control role:
```
ScopeSelectorArgument:  <wnd app='desktopapp.exe' />
FullSelectorArgument:   <ctrl name='First' role='editable text' />
```

**Alternative — `<wnd ctrlname>` selectors:** When UiPath UI Explorer is available, `ctrlname` selectors are more stable:
```
ScopeSelectorArgument:  <wnd app='desktopapp.exe' />
FullSelectorArgument:   <wnd ctrlname='txtFirstName' />
```

Role mapping for WinForms controls in `<ctrl>` selectors:

| WinForms Control | `<ctrl>` role |
|---|---|
| TextBox (Edit) | `editable text` |
| Button | `push button` |
| CheckBox | `check box` |
| RadioButton | `radio button` |
| ComboBox | `combo box` |
| TabItem | `tab item` |
| Label | `text` (read-only) |

If multiple windows of the same app exist, add `title` (with wildcard) to scope — but **never `cls`**:
```
ScopeSelectorArgument:  <wnd app='desktopapp.exe' title='Desktop App*' />
```

**⚠️ CRITICAL — WinForms `cls` values are DYNAMIC.** WinForms class names contain a session hash that changes between app launches (e.g., `WindowsForms10.Window.8.app.0.378734a`). **Never use `cls` in selectors for WinForms apps.**

WinForms ClassName patterns (for reference only — **do NOT use in selectors**):
- `WindowsForms10.EDIT.app.0.*` → TextBox
- `WindowsForms10.BUTTON.app.0.*` → Button/CheckBox/RadioButton
- `WindowsForms10.COMBOBOX.app.0.*` → ComboBox
- `WindowsForms10.STATIC.app.0.*` → Label
- `WindowsForms10.Window.8.app.0.*` → Container/GroupBox/Form

See `references/ui-inspection-reference.md` for complete framework detection table and property mapping.

### Click (NClick)

→ **Use `gen_nclick()`** — generates correct XAML deterministically.


With verify (wait for element after click):
→ **Use `gen_nclick()`** — generates correct XAML deterministically.


Key attributes:
- `ClickType`: `Single`, `Double`
- `MouseButton`: `Left`, `Right`
- `KeyModifiers`: `None`, `Alt`, `Ctrl`, `Shift`, `Win`

### Type Into (NTypeInto)

→ **Use `gen_ntypeinto()`** — generates correct XAML deterministically.


With dynamic selector (use expression in selector):
```xml
  FullSelectorArgument="[string.Format(&quot;&lt;webctrl aaname='Answer {0}' tag='INPUT' /&gt;&quot;, intIndex + 1)]"
```

Key attributes:
- `EmptyFieldMode`: `SingleLine` (clear before typing — ⚠️ NEVER use `"Clear"`, Studio crash), `MultiLine`, `None`
- `ClickBeforeMode`: `Single`, `Double`, `None`
- `Text`: VB.NET expression in brackets, e.g. `[variableName]`

### Select Item (NSelectItem)

Selects a value from a dropdown. `Item` is the value to select (variable or literal). `Items` is the optional static list of valid options.

→ **Use `gen_nselectitem()`** — generates correct XAML deterministically.

Properties:
- `Item` — VB.NET expression for the value to select (e.g., `[strDepartment]` or `"Engineering"`)
- `NSelectItem.Items` — optional predefined list (`scg:List x:TypeArguments="x:String"`) of valid dropdown values. Studio populates this from design-time inspection. **⚠️ MUST be `scg:List` with `x:String` elements — NOT `InArgument`.**
- **⚠️ NSelectItem does NOT have** `InteractionMode` — that property only exists on NClick and NTypeInto. NGetText, NCheckState, NSelectItem, NGoToUrl, NGetUrl, NExtractDataGeneric all lack it. Studio crashes with `Could not find member 'InteractionMode'`. Lint 53.

### Get Text (NGetText)

Extracts text content from a UI element. Output stored via `TextString` property.

→ **Use `gen_ngettext()`** — generates correct XAML deterministically.


Properties:
- `TextString="[varName]"` — output variable (VB.NET expression). Omit to discard result
- Alternative output pattern (seen in some Studio versions): `NGetText.Text` as OutArgument element:
→ **Use `gen_ngettext()`** — generates correct XAML deterministically.

- `ElementType` — optional. Must be a valid `UIElementType` enum value: `Button`, `CheckBox`, `Document`, `DropDown`, `Group`, `Image`, `InputBox`, `InputBoxPassword`, `List`, `ListItem`, `Menu`, `MenuItem`, `None`, `ProgressBar`, `RadioButton`, `Slider`, `Tab`, `Table`, `Text`, `ToolBar`, `ToolTip`, `Tree`, `TreeItem`, `Window`. **⚠️ `DataGrid` is NOT valid — use `Table`. `ComboBox` is NOT valid — use `DropDown`. `Link`/`Anchor`/`Hyperlink` are NOT valid — use `Text`.** Studio crashes on invalid values.
- `ElementVisibilityArgument="Interactive"` — waits for element visibility
- `WaitForReadyArgument="Interactive"` — waits for page/app ready state
- `ScopeIdentifier` — must match parent NApplicationCard `ScopeGuid`
- `HealingAgentBehavior="SameAsCard"` — inherits from NApplicationCard
- **⚠️ NGetText does NOT have `InteractionMode`** — only NClick and NTypeInto have it. Adding it causes `Could not find member 'InteractionMode'` crash. Lint 53.

### Extract Table Data (NExtractDataGeneric)

Scrapes structured tabular data from web pages. Handles pagination automatically via `.NextLink`. Output is a DataTable. This is the most complex modern UI activity — the `ExtractDataSettings` and `ExtractMetadata` attributes contain embedded XML that defines the table schema and extraction selectors.

→ **Use `gen_nextractdata()`** — generates correct XAML deterministically.


Properties:
- `x:TypeArguments="sd2:DataTable"` — output type. Requires `xmlns:sd2="clr-namespace:System.Data;assembly=System.Data.Common"`
- **`ExtractedData="[dt_variable]"`** — output DataTable variable. Use this **inline attribute**. Do NOT use `Result` or `DataTable` — neither property exists. `DataTable` is the generic type argument (`x:TypeArguments="sd2:DataTable"`), NOT a property. Studio error: `Could not find member 'DataTable'`
- `MaximumResults` — `0` = unlimited. Set to a number to cap rows
- `LimitExtractionTo` — `None` (all pages), `CurrentPage` (single page only)
- `ContinueOnError` — `True` recommended for web scraping (pages may change)
- **IdRef uses backtick notation:** `` NExtractDataGeneric`1_1 `` (generic type parameter)
- `ScopeIdentifier` — must match parent NApplicationCard `ScopeGuid`

**ExtractDataSettings** — XML-encoded table schema defining columns. The XML must be entity-encoded as an attribute value. Decoded structure:
```xml
<Table Type='Structured' AddCvHeader='true' IsScrollEnabled='false'>
  <Column xsi:type='DataColumn' ReferenceName='Column0' Name='ColumnDisplayName'>
    <IsValidName>true</IsValidName>
    <ValidationErrorMessage />
    <IsExtra>false</IsExtra>
    <CanExtractSimilar>true</CanExtractSimilar>
    <Format xsi:type='TextColumnFormat' />
  </Column>
  <!-- More columns... -->
  <Column xsi:type='DataNextLink' />  <!-- Pagination marker -->
</Table>
```
Column types: `DataColumn` (text data), `DataNextLink` (pagination — always last, no Name/ReferenceName)

**ExtractMetadata** — XML-encoded selector rules for row detection and per-column data extraction. Decoded:
```xml
<extract>
  <row exact='1'>
    <webctrl tag='li' />
    <webctrl tag='article' idx='1' />
  </row>
  <column exact='1' name='Column0' attr='href'>
    <webctrl tag='li' />
    <webctrl tag='article' idx='1' />
    <webctrl tag='h3' idx='1' />
    <webctrl tag='a' idx='1' />
  </column>
  <column exact='1' name='Column1' attr='fulltext'>
    <webctrl tag='li' />
    <webctrl tag='article' idx='1' />
    <webctrl tag='div' idx='2' />
    <webctrl tag='p' idx='1' />
  </column>
</extract>
```
- `<row>` — defines the repeating element pattern (each row in the table)
- `<column name='...' attr='...'>` — selector path to extract data for each column. `attr` is the HTML attribute to read: `fulltext` (visible text), `href` (link URL), `src` (image), `innertext`, `aaname`, etc.
- Column `name` must match `ReferenceName` in ExtractDataSettings

**Child elements (order matters):**
1. `.NextLink` — TargetAnchorable pointing to the "Next" page button/link. Omit for single-page extraction. `SearchSteps="Selector, Image"` — uses image fallback since next buttons change across pages
2. `.Target` — TargetAnchorable pointing to the table/list container element

**TargetAnchorable visual anchoring attributes** (seen in Extract Data targets):
- `ImageBase64` — base64-encoded screenshot of the target element for image-based matching
- `BrowserURL` — the URL where the element was recorded (informational, not used for matching)
- `DesignTimeRectangle` — bounding box coordinates from design time: `"x, y, width, height"`

### Go To URL (NGoToUrl)

**Best practice — URL-first navigation:** Always prefer `NGoToUrl` over clicking links/menus. Faster, more reliable, no selector dependency. See `skill-guide.md` Rule 3 for the click-then-fetch discovery technique.

**⚠️ Never hardcode URLs** — all URLs must come from Config.xlsx. See SKILL.md → Production Rules for details. Config keys: `WebApp_Url`, `API_BaseUrl`. Dynamic: `Config("WebApp_BaseUrl").ToString + "/work-item/" + strWIID`.

→ **Use `gen_ngotourl()`** — generates correct XAML deterministically.


### Get URL (NGetUrl)

→ **Use `gen_ngeturl()`** — generates correct XAML deterministically.


### Check App State (NCheckState)

Waits for an element to appear or not, then branches. Acts like a UI-aware If/Else.

→ **Use `gen_ncheckstate()`** — generates correct XAML deterministically.

Properties:
- `Exists="{x:Null}"` — initial value; at runtime resolves to `True`/`False` to indicate which branch was taken. Can be used as output
- `ScopeIdentifier` — must match parent NApplicationCard `ScopeGuid`
- `NCheckState.Target` — uses `uix:TargetAnchorable` (same as NClick/NTypeInto) to identify the element to wait for
- `NCheckState.IfExists` — Sequence to execute when element appears. DisplayName is always `"Target appears"`
- `NCheckState.IfNotExists` — Sequence to execute when element is not found. DisplayName is always `"Target does not appear"`
- `DelayBefore` — optional delay in seconds before checking (e.g., `DelayBefore="5"`)
- **Order in XAML:** `.IfExists`, then `.IfNotExists`, then `.Target` — this is the order Studio exports
- ⛔ **NCheckState does NOT have an `Appears` attribute.** Branching is via `.IfExists`/`.IfNotExists` child elements. `Mode="Appears"` exists only on `VerifyExecutionOptions` (NClick/NTypeInto verify step) — do NOT confuse them. NCheckState also has NO `Selector` attribute — the selector goes in `.Target` → `TargetAnchorable`.

### Target Element Patterns

All modern activities use `uix:TargetAnchorable` for targeting elements. The generators (`gen_nclick()`, `gen_ntypeinto()`, etc.) build this internally via `_selector_xml()` — pass the raw selector string and the generator handles all TargetAnchorable attributes, escaping, and GUID generation.

TargetAnchorable key attributes (for understanding only — generators produce these):
- `FullSelectorArgument` — strict selector (aaname, tag, id). XML-escaped (`&lt;`/`&gt;`)
- `FuzzySelectorArgument` — relaxed selector with fuzzy matching attributes
- `ScopeSelectorArgument` — app-level scope selector
- `SearchSteps` — `Selector` (default), `FuzzySelector`, `Image`, or comma-separated fallback chain
- `ElementType` — `Button`, `InputBox`, `DropDown`, `Text`, `CheckBox`, `Table`
- `Version` — always `V6`
- `Guid` — unique per target element

Core attributes:
- `FullSelectorArgument`: strict selector (aaname, tag, id)
- `FuzzySelectorArgument`: relaxed selector with extra matching attributes (class, type, `check:innerText`, `matching:aaname='fuzzy'`, `fuzzylevel:aaname='0.0'`)
- `ScopeSelectorArgument`: app-level scope selector
- `SearchSteps`: `Selector` (default), `FuzzySelector`, `Image`, `CV` (Computer Vision), or comma-separated fallback chain like `"Selector, Image"`
- **ALWAYS default to `SearchSteps="Selector"` (strict).** Only use `FuzzySelector` when the user explicitly requests it or when strict selectors are proven unreliable for a specific element. Always populate both `FullSelectorArgument` and `FuzzySelectorArgument` (Studio expects both), but route through strict by default.
- Selectors use `&lt;` and `&gt;` for `<` and `>` — they are XML-escaped
- ⛔ **There is NO bare `Selector=` attribute on TargetAnchorable.** Use `FullSelectorArgument`, `ScopeSelectorArgument`, `FuzzySelectorArgument`. Also: `<uix:Selector>` does NOT exist as an element type — selectors are always attributes on `TargetAnchorable`. And `AnchorSelector` is NOT a property — anchors use a separate `TargetAnchorable` inside an anchor delegate (see Anchor-Based Targeting below).

Visual/design-time attributes (optional, Studio-generated):
- `ImageBase64` — base64-encoded screenshot for image-based matching fallback
- `BrowserURL` — URL where element was recorded (informational)
- `DesignTimeRectangle` — bounding box: `"x, y, width, height"`
- `.PointOffset` child — click offset from element center: `X="0" Y="0"` (default center)


## Selector Reference

### Selector Syntax and Structure
A selector is an XML fragment that identifies a UI element through its attributes and position in the UI hierarchy:
```
<node_1 attr='value' /><node_2 attr='value' />...<target_node attr='value' />
```
- First node = root (top-level window/browser)
- Last node = target element
- Intermediate nodes = parent containers in the hierarchy
- Each node: `<tag_type attr_name='attr_value' ... />`

### Full vs Partial Selectors
**Full selector** — contains all nodes from root to target. Used by activities OUTSIDE a Use Application/Browser scope:
```
<wnd app='notepad.exe' />
<wnd cls='Edit' />
```

**Partial selector** — omits the root node. Used by activities INSIDE a Use Application/Browser scope (the scope provides the root):
```
<webctrl aaname='Submit' tag='BUTTON' />
```
In modern design, activities inside `NApplicationCard` use partial selectors. The `ScopeSelectorArgument` on the `TargetAnchorable` provides the root scope.

### Tag Types and Key Attributes

#### WND (Windows desktop applications)
```
<wnd app='notepad.exe' />
<wnd cls='Edit' />
```
Key attributes: `app` (process name — usually sufficient alone for root node), `cls` (window class — useful for child elements), `title` (window title — add only to disambiguate multiple windows), `aaname` (accessible name), `idx` (index among siblings), `ctrlname`/`ctrlid` (WinForms)

#### HTML (Browser top-level — root node)
```
<html app='msedge.exe' title='Dashboard' url='https://app.example.com/dashboard' />
```
Key attributes: `app` (browser process), `title` (page title), `url` (page URL)

#### WEBCTRL (Web elements — most common for web automation)
```
<webctrl aaname='Submit' tag='BUTTON' type='submit' />
<webctrl id='email-input' tag='INPUT' />
<webctrl css-selector='div.modal > form input[name=username]' />
<webctrl tag='TR' tableRow='3' />
<webctrl tag='TD' tableRow='2' tableCol='1' colName='Status' />
```
Key attributes:
- `tag` — HTML element tag (BUTTON, INPUT, DIV, A, TR, TD, SELECT, etc.)
- `aaname` — accessible/visible name (button text, link text, label)
- `id` — HTML id attribute
- `name` — HTML name attribute
- `class` — CSS class(es)
- `parentid` — id of parent element
- `parentclass` — class of parent element
- `innertext` / `visibleinnertext` — text content
- `href` — link URL (for A tags)
- `src` — source URL (for IMG/IFRAME tags)
- `css-selector` — direct CSS selector (no fuzzy/regex support)
- `tableRow` / `tableCol` — row/column index in a table (0-based)
- `colName` / `rowName` — column/row header text
- `idx` — index among matching siblings (1-based)
- `isleaf` — whether element has no children
- `aria-label` / `aria-labelledby` — ARIA accessibility attributes

#### CTRL (Windows desktop controls — legacy)
```
<ctrl role='push button' name='OK' automationid='btnOK' />
```
Key attributes: `role`, `name`, `automationid`, `labeledby`, `text`, `idx`

#### UIA (UI Automation — modern desktop)
```
<uia automationid='txtSearch' role='edit' name='Search' />
```
Key attributes: `automationid` (most stable), `role`, `name`, `cls`, `idx`, `tableRow`/`tableCol`

#### JAVA (Java applications)
```
<java role='push button' name='OK' cls='javax.swing.JButton' />
```
Key attributes: `role`, `name`, `virtualname`, `javastate`, `cls`, `accessibleClass`, `idx`

#### RDP (Remote Desktop)
Same attributes as `<wnd>` tag. Used for remote automation via RDP sessions.

### Selector Tag-Attribute Reference

Complete list of valid attributes per selector tag. Using an attribute on the wrong tag causes silent selector failures.

**WND** (Windows desktop): `app`, `cls`, `title`, `aaname`, `ctrlname` (WinForms), `ctrlid` (WinForms), `idx`, `tid`, `pid`, `aastate`

**HTML** (Browser window): `url`, `htmlwindowname`, `title`, `class`, `app`, `idx`, `pid`, `tid`

**WEBCTRL** (Web element): `tag`, `idx`, `aaname`, `name`, `id`, `parentid`, `class`, `css-selector`, `innertext`, `visibleinnertext`, `isleaf`, `parentclass`, `parentname`, `src`, `href`, `tableCol`, `tableRow`, `colName`, `rowName`, `aria-label`, `aria-labelledby`

**CTRL** (Windows desktop controls): `role`, `name`, `automationid`, `labeledby`, `aastate`, `virtualname`, `text`, `rowName`, `idx`

**UIA** (UI Automation — modern desktop): `automationid`, `cls`, `name`, `role`, `enabled`, `helpText`, `itemstatus`, `itemtype`, `tableRow`, `tableCol`, `rowName`, `colName`, `idx`

**JAVA** (Java applications): `role`, `name`, `virtualname`, `javastate`, `cls`, `accessibleClass`, `tableRow`, `tableCol`, `rowName`, `colName`, `idx`

**RDP** (Remote Desktop): Same attributes as `<wnd>`. Used for remote automation.

#### Attribute-Tag Mismatch Rules

⚠️ Using the wrong attribute on the wrong tag causes silent selector failures:

| Attribute | Valid Tags | ⛔ Invalid Tags |
|---|---|---|
| `aaname` | `<wnd>`, `<webctrl>` | `<ctrl>`, `<uia>`, `<java>` |
| `name` | `<ctrl>`, `<uia>`, `<java>`, `<webctrl>` | `<wnd>` (use `aaname`) |
| `automationid` | `<ctrl>`, `<uia>` | `<wnd>` (use `ctrlname`), `<webctrl>`, `<java>` |
| `ctrlname` | `<wnd>` (WinForms only) | all others |
| `cls` | `<wnd>`, `<uia>`, `<java>` | `<ctrl>`, `<webctrl>` (use `class`) |
| `class` | `<webctrl>`, `<html>` | `<wnd>` (use `cls`), `<ctrl>`, `<uia>` |
| `id` | `<webctrl>` | `<wnd>`, `<ctrl>`, `<uia>` |

### Dynamic Selectors (Variables in Selectors)
Use double curly braces `{{variableName}}` to inject variable values into selectors at runtime:
```
<wnd app='notepad.exe' title='{{strFileName}} - Notepad' />
<webctrl aaname='{{strButtonName}}' tag='BUTTON' />
<webctrl tag='TR' tableRow='{{intRowIndex}}' />
```
In XAML, the full selector string with variables would look like:
```xml
FullSelectorArgument="&lt;webctrl aaname='{{strMenuOption}}' tag='A' /&gt;"
```
- The variable must be defined as a workflow variable (not an argument)
- Dynamic selectors are resolved at runtime — variable value is substituted before matching

### Wildcards
Replace zero or more characters to handle dynamic attribute values:
- `*` — matches zero or more characters
- `?` — matches exactly one character

```
<wnd app='notepad.exe' title='* - Notepad' />           ← any filename
<html title='Dashboard - *' />                            ← any suffix
<webctrl aaname='Order_????' tag='A' />                   ← 4-char order ID
<wnd title='Invoice_2025*' />                             ← any 2025 invoice
```
Best practice: use wildcards for the **changing** portion of an attribute, keep the **stable** portion literal.

### Fuzzy Search
Match attributes approximately rather than exactly. Useful when attributes have slight variations across runs:
```
<html app='firefox.exe' title='WEScho0ls Online Web Tutorials' 
  matching:title='fuzzy' fuzzylevel:title='0.8' />

<webctrl aaname='Colorpicker' parentid='main' tag='IMG' 
  matching:aaname='fuzzy' fuzzylevel:aaname='0.4' />
```
Syntax for any attribute:
- `matching:attrName='fuzzy'` — enable fuzzy matching for that attribute
- `fuzzylevel:attrName='0.0-1.0'` — similarity threshold (1.0 = exact, 0.0 = match anything)
  - High value (0.8-0.9): small variations (typos, minor text changes)
  - Low value (0.3-0.5): large variations

Text content check (verify element contains specific text):
```
<webctrl tag='DIV' check:text='Options' matching:aaname='fuzzy' fuzzylevel:aaname='0.8' />
```

In XAML `FuzzySelectorArgument`:
```xml
FuzzySelectorArgument="&lt;webctrl aaname='Submit Order' tag='BUTTON' 
  matching:aaname='fuzzy' fuzzylevel:aaname='0.8' 
  check:innerText='Submit' /&gt;"
```

### RegEx Search
Use regular expressions for complex pattern matching in attribute values:
```
<webctrl aaname='Order_[0-9]{4,6}' tag='A' matching:aaname='regex' />
<html title='Invoice #\d+ - .*' matching:title='regex' />
```
Syntax: `matching:attrName='regex'` — attribute value is interpreted as a regular expression.

### Non-Greedy Search (idx='*')
Match any window instance. Useful when multiple windows of the same app are open:
```
<wnd app='notepad.exe' idx='*' />
```
Setting `idx='*'` makes the selector match regardless of the window's position/order. Without this, `idx='1'` would only match the first instance.

### Table Element Selectors
For interacting with specific cells/rows in web tables or data grids:
```
← Specific cell by row/column index (0-based for web tables)
<webctrl tag='TD' tableRow='2' tableCol='3' />

← Cell by column header name
<webctrl tag='TD' tableRow='1' colName='Status' />

← Entire row
<webctrl tag='TR' tableRow='5' />

← Dynamic row (using variable for iteration)
<webctrl tag='TD' tableRow='{{intCurrentRow}}' colName='Action' />
```
For SAP tables: `<sap tableRow='3' tableCol='2' colName='Material' />`

### Anchor-Based Targeting
Modern design uses anchors — nearby stable elements that help locate the target:
```xml
<uix:TargetAnchorable ...>
  <!-- Anchor: a label next to the input field -->
  <uix:TargetAnchorable.Anchors>
    <uix:AnchorElement 
      SelectorArgument="&lt;webctrl aaname='Email Address' tag='LABEL' /&gt;"
      AnchorType="Left" />
  </uix:TargetAnchorable.Anchors>
</uix:TargetAnchorable>
```
Anchor types: `Left`, `Right`, `Top`, `Bottom` — relative position of anchor to target.
Anchors make selectors more resilient: even if the target's own attributes are unstable, a stable nearby label can guide matching.

### Selector Best Practices

**Scope selectors — keep minimal:**
The `<wnd>` scope selector (in NApplicationCard's TargetApp or TargetAnchorable's ScopeSelectorArgument) should use the **fewest attributes needed**. When `app` uniquely identifies the process, use only `app` — do not add `cls`, `title`, or other properties:
- ✓ `<wnd app='desktopapp.exe' />` — sufficient, resilient
- ✗ `<wnd app='desktopapp.exe' cls='WindowsForms10.Window' />` — `cls` is fragile (WinForms hashes change per session)
- ✗ `<wnd app='desktopapp.exe' cls='Window' title='Desktop App v2.1' />` — `title` breaks on version updates

Add `title` only when multiple windows of the same process exist and you need to disambiguate (use wildcards: `title='Desktop App*'`).

**Prefer stable attributes:**
1. `automationid` / `id` — most stable (set by developers, rarely changes)
2. `aaname` — visible name (stable if UI text doesn't change)
3. `tag` + `name` — reliable combo for web forms
4. `css-selector` — powerful but couples to page structure

**Avoid unstable attributes:**
- `idx` — changes based on element load order / sibling count. Only use when no alternative exists
- `class` alone — CSS classes change with styling updates
- Dynamic `id` values (e.g., `id='element_abc123'` where suffix is generated)
- `tableRow` with hardcoded values (use variables instead for iteration)

**General rules:**
- Use the fewest attributes needed to uniquely identify the element
- Use wildcards for the volatile portions of otherwise stable attributes
- Prefer `aaname` for buttons/links (matches visible text the user sees)
- Use `css-selector` when the DOM structure is stable and you need precision
- Add anchors when the target itself lacks unique attributes
- Test selectors across different data/states before production

## XAML Special Characters

Always escape these in XAML attribute values:
- `"` → `&quot;`
- `<` → `&lt;`
- `>` → `&gt;`
- `&` → `&amp;`
- newline → `&#xA;` (used for formatting multiline expressions in attributes)
- tab → `&#x9;` (used for indentation in multiline inline arrays)

Square brackets `[ ]` denote VB.NET/C# expressions in UiPath XAML.
