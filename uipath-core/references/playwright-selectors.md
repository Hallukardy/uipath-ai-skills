# Playwright MCP → UiPath Selector Generation

> ⛔⛔⛔ **PLAYWRIGHT IS READ-ONLY — YOU ARE AN OBSERVER, NOT A USER** ⛔⛔⛔
>
> **When you hit a login page:**
> 1. Snapshot it for selectors (username field, password field, login button)
> 2. **Output the PHASE 2 LOGIN GATE message from SKILL.md** — ask user to simulate failed login, then log in correctly
> 3. **STOP. WAIT for user response. Do NOT proceed.**
>
> **You must NEVER:**
> - Type into ANY form field (not credentials, not test data, not placeholders, nothing)
> - Click Login, Submit, Sign In, or any state-changing button
> - Fill in forms of any kind
> - Guess what's behind a login page
>
> **Your only permitted actions:** navigate to URLs, take snapshots, read the DOM/accessibility tree, click navigation links/menus to discover pages.
>
> This is the #1 recurring bug across all testing. If you are about to type something into a field — **STOP AND RE-READ THIS WARNING.**

When building UI automation workflows, use Playwright MCP to inspect live web pages and generate accurate UiPath selectors. This eliminates guesswork and produces selectors that actually work.

## Contents
- Workflow
- UiPath Selector Structure (Selector Node Format)
- HTML Node Attributes (App/Browser Scope)
- WEBCTRL Attributes (Element Target) — Complete Reference (Attribute Priority)
- ElementType Mapping
- Building UiPath Selectors from Playwright Data (Steps 1–5)
- Full vs Partial Selectors
- Wildcards in Selectors
- Dynamic Selectors (Studio, XAML string.Format, XAML concatenation)
- Complete Example: Playwright Inspection → XAML
- Tips and Best Practices

## Workflow

0. **Check available tools** — look for Playwright MCP tools in your tool list (e.g. `playwright_navigate`, `browser_navigate`, `playwright_snapshot`, `browser_snapshot`, `playwright_evaluate`). If none found, fall back to PDD screenshots but note selectors are estimated.
1. **Navigate** to the target page using Playwright MCP
2. **Inspect elements** — use Playwright's accessibility tree, snapshot, or evaluate to extract element attributes (tag, id, name, aria-label, type, class, role, placeholder, page title)
3. **Map to UiPath selectors** — convert HTML attributes to UiPath `<webctrl>` format using the rules below
4. **Build XAML** — insert selectors into NClick, NTypeInto, NSelectItem, etc. from templates in `xaml-ui-automation.md`

## UiPath Selector Structure

UiPath selectors are hierarchical XML fragments. For web automation, they use two node types:

```
<html app='browser.exe' title='Page Title' />   ← HTML node (app-level scope)
<webctrl tag='BUTTON' aaname='Submit' />         ← WEBCTRL node (element target)
```

The **HTML node** identifies the browser window. The **WEBCTRL node** identifies the specific element within the page. In modern activities (NClick, NTypeInto, etc.), these map to:
- `ScopeSelectorArgument` → the HTML node
- `FullSelectorArgument` → the WEBCTRL node
- `FuzzySelectorArgument` → the WEBCTRL node with extra attributes for resilience

### Selector Node Format

Each node follows: `<tag_type attr1='value1' attr2='value2' />`

Attributes support three search capabilities:
- **Fuzzy** — approximate matching (tolerates minor differences)
- **RegEx** — regular expression patterns in attribute values
- **Case-Sensitive** — exact case matching

## HTML Node Attributes (App/Browser Scope)

| Attribute | Description | Fuzzy | RegEx |
|---|---|---|---|
| `app` | Browser executable: `msedge.exe`, `chrome.exe`, `firefox.exe` | ❌ | ❌ |
| `title` | Page/window title. Supports wildcards: `title='*Dashboard*'` | ✅ | ✅ |
| `url` | Page URL. Useful when title is dynamic | ✅ | ✅ |
| `class` | Window class | ✅ | ✅ |
| `idx` | Window index (when multiple windows of same app) | ❌ | ❌ |

## WEBCTRL Attributes (Element Target) — Complete Reference

These are all officially supported WEBCTRL attributes from UiPath documentation. All support Fuzzy, RegEx, and Case-Sensitive search.

| Attribute | Playwright Source | Priority | Notes |
|---|---|---|---|
| **`tag`** | `element.tagName` | ⬆ Always include | UPPERCASE: `BUTTON`, `INPUT`, `SELECT`, `SPAN`, `DIV`, `A`, `TABLE`, `TR`, `TD`, `H1`–`H6` |
| **`aaname`** | `aria-label`, `innerText`, `alt`, `title` | ⬆ Primary identifier | Accessible name. Most reliable for web. Maps to visible text or aria-label |
| **`id`** | `element.id` | ⬆ When stable | Skip if auto-generated (React/Angular IDs like `react-select-3`) |
| **`name`** | `element.name` | ⬆ For forms | HTML `name` attribute on form elements |
| `class` | `element.className` | ⬇ Fuzzy only | Full class string. Brittle — changes with CSS frameworks |
| `innertext` | `element.innerText` | ⬇ Backup | Full inner text content. Use for text-heavy elements |
| `visibleinnertext` | visible text only | ⬇ Backup | Only the visible portion of inner text |
| `css-selector` | CSS selector | ⬇ Special | Direct CSS selector. Does NOT support Fuzzy/RegEx/Case-Sensitive. **Note:** UiPath internally stores this as `cssSelector` (camelCase). Lint 97 flags `css-selector=`. Prefer `id`, `aaname`, or `parentid` instead. |
| `parentid` | parent `element.id` | Medium | Parent element's ID — helps disambiguate |
| `parentclass` | parent `element.className` | ⬇ Fuzzy only | Parent element's class |
| `parentname` | parent `element.name` | Medium | Parent element's name |
| `src` | `element.src` | Medium | For images, iframes |
| `href` | `element.href` | Medium | For anchor links |
| `idx` | sibling position | Medium | 1-based index among matching siblings. Supports Fuzzy/RegEx |
| `isleaf` | DOM structure | ⬇ Rare | Whether element is a leaf node |
| `tableRow` | row position | ⬆ For tables | Row index in table |
| `tableCol` | column position | ⬆ For tables | Column index in table |
| `rowName` | row header text | ⬆ For tables | Row identifier text |
| `colName` | column header text | ⬆ For tables | Column header text |
| `aria-label` | `aria-label` attr | ⬆ Accessible | Direct aria-label value |
| `aria-labelledby` | `aria-labelledby` attr | Medium | References another element's ID for labeling |
| `placeholder` | `placeholder` attr | ⬇ Fuzzy only | Input placeholder text |
| `type` | `input.type` | Medium | Input type: `text`, `password`, `submit`, `checkbox`, `email` |

### Attribute Priority for Selector Building

1. `aaname` + `tag` — best combo (readable, stable)
2. `id` + `tag` — when id is stable and meaningful
3. `name` + `tag` — for form elements
4. `css-selector` — when nothing else works (no Fuzzy/RegEx support)
5. `tag` + `class` + `idx` — last resort (brittle)

## ElementType Mapping

**Valid `UIElementType` enum values** (Studio crashes on anything else):
`Button`, `CheckBox`, `ComboBox`, `Document`, `DropDown`, `Group`, `Image`, `InputBox`, `InputBoxPassword`, `Link`, `List`, `ListItem`, `Menu`, `MenuItem`, `None`, `ProgressBar`, `RadioButton`, `Slider`, `Tab`, `Table`, `Text`, `ToolBar`, `ToolTip`, `Tree`, `TreeItem`, `Window`

**⚠️ Common hallucination:** `DataGrid` is NOT valid — use `Table` for grids/tables.

| HTML / Desktop Element | UiPath ElementType |
|---|---|
| `<button>`, `<input type="submit">`, `<a>` (styled as button) | `Button` |
| `<input type="text">`, `<input type="email">`, `<textarea>` | `InputBox` |
| `<input type="password">` | `InputBoxPassword` |
| `<select>` | `DropDown` |
| `<span>`, `<div>`, `<p>`, `<h1>`–`<h6>`, `<label>` | `Text` |
| `<a>` (navigation link) | `Link` |
| `<input type="checkbox">`, `<input type="radio">` | `CheckBox` |
| `<table>`, DataGrid controls, `role='table'`/`role='grid'` | `Table` |
| Dialog, modal, window frame | `Window` |

## Building UiPath Selectors from Playwright Data

### Step 1: Get Element Info via Playwright

Use Playwright MCP to inspect the target element. Gather: tag name, text content, id, aria-label, name, type, class, and the page title.

### Step 2: Build the Scope Selector (HTML node)

```
<html app='msedge.exe' title='Page Title' />
```

- `app='msedge.exe'` for Edge, `app='chrome.exe'` for Chrome
- `title='*keyword*'` with wildcards if title changes dynamically
- Can also use `url='https://example.com/*'` for URL-based matching

### Step 3: Build the Full Selector (strict WEBCTRL)

Minimum attributes to uniquely identify the element:

```
<webctrl aaname='Submit' tag='BUTTON' />
<webctrl tag='INPUT' aaname='Email address' />
<webctrl tag='SELECT' aaname='Country' />
<webctrl tag='INPUT' id='username' />
<webctrl tag='A' href='/dashboard' />
```

For table cells:
```
<webctrl tag='TD' tableRow='3' tableCol='2' />
<webctrl tag='TD' rowName='Invoice #1234' colName='Amount' />
```

### Step 4: Build the Fuzzy Selector (relaxed WEBCTRL, optional)

Add extra attributes for resilience. UiPath tries FullSelector first, falls back to Fuzzy:

```
<webctrl aaname='Submit' tag='BUTTON' type='submit' class='btn btn-primary' check:innerText='Submit' />
<webctrl tag='INPUT' aaname='Email' type='email' class='form-control' placeholder='Enter email' />
```

The `check:innerText` attribute is UiPath-specific validation — verifies element text matches after finding it.

### Step 5: XML-Escape for XAML

Selectors go inside XML attributes, so escape them:
- `<` → `&lt;`
- `>` → `&gt;`
- `'` inside selector values → stays as `'` (UiPath uses single quotes inside selectors)
- `"` → `&quot;` (only if selector is inside a `"..."` XML attribute)

Result in XAML:
```xml
FullSelectorArgument="&lt;webctrl aaname='Submit' tag='BUTTON' /&gt;"
ScopeSelectorArgument="&lt;html app='msedge.exe' title='Example Corp' /&gt;"
```

## Full vs Partial Selectors

UiPath Modern activities (NClick, NTypeInto, etc.) separate the target definition into three parts:

| Selector | Type | XAML Property | Purpose |
|---|---|---|---|
| **Window selector** | Full | `ScopeSelectorArgument` | Identifies the application window (top-level). Contains `<html>` or `<wnd>` node |
| **Strict selector** | Partial | `FullSelectorArgument` | Identifies the specific element within the window. Precise match |
| **Fuzzy selector** | Partial | `FuzzySelectorArgument` | Fallback element selector using fuzzy matching algorithm |

The complete target is determined by **merging** the Window selector with the Strict or Fuzzy selector. Partial selectors do NOT contain any information about the top-level window — that's handled by the container (Use Application/Browser / NApplicationCard).

**Full selector** (everything in one string — used in Classic activities or standalone):
```
<html app='msedge.exe' title='Example Corp' /><webctrl aaname='Submit' tag='BUTTON' />
```

**Partial selectors** (split across container + activity — used in Modern activities):
```
Container (NApplicationCard):     <html app='msedge.exe' title='Example Corp' />
Activity (NClick) strict:         <webctrl aaname='Submit' tag='BUTTON' />
Activity (NClick) fuzzy:          <webctrl aaname='Submit' tag='BUTTON' type='submit' class='btn' />
```

When generating XAML, always use partial selectors with the NApplicationCard container pattern. This is faster (doesn't re-find the window for every activity) and makes selector maintenance easier.

## Wildcards in Selectors

Wildcards handle dynamically-changing attribute values without needing variables or expressions. Three patterns are supported:

| Wildcard | Meaning | Example |
|---|---|---|
| `*` | Zero or more characters | `title='* - Notepad'` matches "Untitled - Notepad", "file.txt - Notepad" |
| `?` | Exactly one character | `aaname='Item ?'` matches "Item A", "Item 1", NOT "Item 10" |
| `*?` | One or more characters (at least one) | `id='btn-*?'` matches "btn-submit", "btn-1", NOT "btn-" |

Common wildcard patterns:
```
title='*Dashboard*'                   ← page title contains "Dashboard" anywhere
aaname='Invoice #*'                   ← text starts with "Invoice #"
url='https://example-app.com/*/edit'         ← any resource's edit page
id='field-*'                          ← any id starting with "field-"
```

In XAML:
```xml
ScopeSelectorArgument="&lt;html app='msedge.exe' title='*Dashboard*' /&gt;"
FullSelectorArgument="&lt;webctrl aaname='Invoice #*' tag='SPAN' /&gt;"
```

**Rule of thumb:** If an attribute's value is ALL wildcard (e.g. `name='*'`), remove that attribute entirely — it adds no filtering value.

## Dynamic Selectors

Dynamic selectors use variables or arguments to parameterize attribute values. This allows the same selector to target different elements at runtime.

### In UiPath Studio (Selector Editor)

Studio uses the `{{VariableName}}` syntax inside the Selector Editor. The format is:

```
<tag attribute='{{VariableName}}' />
```

Example — clicking different menu items with one Click activity:
```
Static:    <ctrl name='File' role='menu item' />
Dynamic:   <ctrl name='{{MenuOption}}' role='menu item' />
```

The variable `MenuOption` holds the target value ("File", "Format", "Edit", etc.). Both variables and arguments are supported.

### In XAML (string.Format expressions)

When building selectors in XAML code, use VB.NET `string.Format`:

```xml
FullSelectorArgument="[string.Format(&quot;&lt;webctrl aaname='{0}' tag='BUTTON' /&gt;&quot;, strButtonName)]"
```

Index-based iteration (looping through table rows):
```xml
FullSelectorArgument="[string.Format(&quot;&lt;webctrl tag='TR' tableRow='{0}' /&gt;&quot;, intRowIndex.ToString)]"
```

Multiple dynamic values:
```xml
FullSelectorArgument="[string.Format(&quot;&lt;webctrl tag='TD' tableRow='{0}' colName='{1}' /&gt;&quot;, intRow.ToString, strColumnName)]"
```

### In XAML (string concatenation — Classic style)

For Classic activities that use the `Selector` property (a single string with the full selector), use VB.NET string concatenation with escaped double quotes:

```vb
"<html app='msedge.exe' title='*' /><webctrl aaname='" + strFieldLabel + "' tag='LABEL' />"
```

Note the double-quote escaping: in VB.NET, `""` inside a string produces a literal `"`.

### When to use each approach

| Approach | When | Example |
|---|---|---|
| Wildcards (`*`, `?`) | Pattern is predictable, no runtime variable needed | `aaname='Invoice #*'` |
| `{{Variable}}` | Studio Selector Editor, runtime variable drives the target | `name='{{MenuOption}}'` |
| `string.Format` | XAML expressions in Modern activities | `[string.Format("...", var)]` |
| String concatenation | Classic activities Selector property | `"<webctrl aaname='" + var + "' />"` |

## Complete Example: Playwright Inspection → XAML

**Playwright finds a login form with:**
- Page title: "Example Corp - Login"
- Page URL: "https://example-app.com/login"
- Username input: `<input type="text" id="user" aria-label="Username" placeholder="Enter username" class="form-input">`
- Password input: `<input type="password" id="pass" aria-label="Password" class="form-input">`
- Submit button: `<button type="submit" class="btn-login">Sign In</button>`

**Generated scope (ScopeSelectorArgument):**
```xml
ScopeSelectorArgument="&lt;html app='msedge.exe' title='Example Corp - Login' /&gt;"
```

**Username — NTypeInto:**
```xml
FullSelectorArgument="&lt;webctrl tag='INPUT' aaname='Username' /&gt;"
FuzzySelectorArgument="&lt;webctrl tag='INPUT' aaname='Username' type='text' id='user' class='form-input' placeholder='Enter username' /&gt;"
ElementType="InputBox"
```

**Password — NTypeInto:**
```xml
FullSelectorArgument="&lt;webctrl tag='INPUT' aaname='Password' /&gt;"
FuzzySelectorArgument="&lt;webctrl tag='INPUT' aaname='Password' type='password' id='pass' class='form-input' /&gt;"
ElementType="InputBox"
```

**Submit — NClick:**
```xml
FullSelectorArgument="&lt;webctrl aaname='Sign In' tag='BUTTON' /&gt;"
FuzzySelectorArgument="&lt;webctrl aaname='Sign In' tag='BUTTON' type='submit' class='btn-login' check:innerText='Sign In' /&gt;"
ElementType="Button"
```

## Tips and Best Practices

- **Prefer `aaname` over `id`** — aaname maps to visible text/aria-label and is more readable in Studio
- **Skip auto-generated attributes** — React/Angular IDs like `input-3a7f`, dynamic classes like `css-1dbjc4n` are unstable
- **Use wildcards for dynamic content** — `aaname='Item *'` matches "Item 1", "Item 2", etc. Works in `title` too: `title='*Dashboard*'`
- **Remove all-wildcard attributes** — if `name='*'`, just remove the `name` attribute entirely
- **Avoid `idx` when possible** — `idx` depends on load order and sibling count, making selectors brittle. Only use when value is very small (1 or 2) and stable
- **Avoid `class` in strict selectors** — CSS classes change frequently with framework updates. Use only in FuzzySelector as extra resilience
- **Test multiple pages** — if the site is a SPA, check selectors after navigation, not just initial load
- **Table data** — use `tableRow`/`tableCol` for position-based targeting, `rowName`/`colName` for header-based (more stable)
- **Fuzzy search** — when enabled, UiPath tolerates minor differences in attribute values (typos, whitespace)
- **RegEx in selectors** — add `matching:attr='regex'` to the tag to enable RegEx for specific attributes. Example: `<uia matching:name='regex' name='Display is \d' />`
- **`css-selector`** — use as escape hatch when standard attributes can't target the element, but note it doesn't support Fuzzy/RegEx/Case-Sensitive
- **Use containers (NApplicationCard)** — always use partial selectors inside a container instead of full selectors. This is faster (avoids re-finding the window per activity) and easier to maintain
- **Pick constant attributes** — always choose attributes with values that stay the same across runs. If a value changes each time the app starts, that selector will fail
