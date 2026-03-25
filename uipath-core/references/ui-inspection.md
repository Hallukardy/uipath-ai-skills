# UI Inspection — Playwright & Desktop

Mandatory inspection workflows for browser and desktop automation. Run these BEFORE generating any XAML. For XAML generation see `generation.md`. For decomposition rules see `decomposition.md`.

## Workflow: UI Automation with Playwright MCP

**⚠️ MANDATORY STEP for browser automation.** When building browser automation workflows and Playwright MCP is available, ALWAYS navigate to the target web pages and inspect elements BEFORE generating XAML. Do NOT guess selectors from PDD screenshots, descriptions, or assumptions — inspect the live DOM.

> ⛔ **HARD RULE: Playwright is READ-ONLY. You are an observer, not a user.**
> - NEVER type into ANY form field, NEVER enter credentials, NEVER click Login/Submit
> - **Login page → follow the exact Login Gate sequence in SKILL.md § "PLAYWRIGHT INSPECTION — PHASE 2 LOGIN GATE"**
> - If user can't simulate failure → use placeholder error selector with TODO comment
> - **If you are about to call a Playwright tool to type or click on a login page — STOP. You are violating this rule.**
> - Violation of this rule has been the single most recurring bug across all testing sessions

**Never guess these if Playwright MCP is available:**
- "What is the selector for the login button?" → navigate to the page, inspect it
- "What's the id of the status dropdown?" → navigate to the page, inspect it
- "What tag is the hash result element?" → navigate to the page, inspect it

### Steps:

**Step 0: Check tool availability.** List your available MCP tools. Look for Playwright-related tools (common names: `playwright_navigate`, `browser_navigate`, `playwright_snapshot`, `browser_snapshot`, `playwright_evaluate`). If no Playwright tools are available, fall back to PDD screenshots/descriptions and note in your output that selectors are estimated.

**Step 1: Navigate to each target page.** For every web application the workflow interacts with, navigate to the actual URL. If the app requires login, navigate to the login page first — but **DO NOT interact with the login form** (see "Handling login-protected pages" immediately below). **While navigating, check the address bar for stable URL patterns** — if a page has a direct URL (e.g., `/work-items`, `/work-item/{id}`, `/dashboard?tab=reports`), the generated workflow should use `NGoToUrl` to navigate there instead of clicking through UI elements. Only use NClick for navigation when the page has no addressable URL.

**⚠️ STOP-AND-ASK RULE:** If ANY page redirects to a login screen, you MUST: (1) inspect the login page selectors, (2) ask the user to log in, (3) **END YOUR RESPONSE IMMEDIATELY — do not make any more tool calls, do not inspect other pages "in the meantime", do not start generating XAML.** Your response ENDS with the login request. Resume only in your NEXT response after the user confirms login.

**Handling login-protected pages — MANDATORY, NEVER SKIP:** When you navigate to a page and hit a login screen, do NOT skip the page or guess what's behind it. Do NOT move on to inspect other pages first. Instead:
1. **Inspect the login page first** — capture selectors for username field, password field, login button (you need these for the Launch workflow anyway)
2. **Ask the user to log in** — tell them: "Could you enter incorrect credentials and click Login so I can capture the error message element? Then log in correctly and tell me when you're done." **Do NOT type anything yourself.**
3. **HALT. END YOUR RESPONSE. STOP GENERATING TEXT.** Do not inspect other pages. Do not inspect non-auth pages "in the meantime." Do not say "while waiting" and continue working. Do not proceed to XAML generation. Your message must END after asking the user to log in. The very last thing in your response is the login request — nothing after it.
4. **On the user's next message** (e.g., "I'm logged in" / "done" / "logged in, also tried wrong creds"):
   - If they simulated a failed login: snapshot the page to capture the error element selector
   - If they didn't (or no error appears): use placeholder `FullSelectorArgument="&lt;webctrl tag='DIV' class='PLACEHOLDER_ERROR_SELECTOR' /&gt;"` with `<!-- TODO: Replace with real error selector -->`
   - Navigate to each authenticated page and inspect it
5. **Resume inspection** — NOW continue navigating and inspecting the authenticated pages

**Why HALT is mandatory:** Claude's agentic loop will happily keep running tool calls without user input. But you NEED the user to perform manual actions in the browser (enter credentials, click Login). If you keep running, you'll exhaust your tool calls inspecting irrelevant pages and then start generating XAML with missing selectors — which is exactly the failure mode this rule prevents.

**During Playwright inspection you may:** navigate to URLs, take snapshots, read the DOM/accessibility tree, click links/menus to discover pages.
**During Playwright inspection you must NEVER:** type into any form field, submit any form, enter credentials (real or fake — not fake ones either, not any), click "Login"/"Submit" buttons, or perform any action that modifies application state.

Never skip authenticated pages. Never guess what elements exist behind a login. The whole point of Playwright inspection is getting real selectors — that means inspecting the actual pages the workflow will interact with, which are usually behind authentication.

**URL-first discovery technique:** When inspecting, click a link/menu item to reach the next page, then copy the resulting URL. Open a new tab (or reload) and paste the URL directly — if the page loads correctly, it's a stable URL and the workflow should use `NGoToUrl` instead of replicating the click chain. If it doesn't load (redirects to login, shows error, or loads a different state), the URL is not directly addressable and you must use UI navigation.

```
Example — inspecting the target web application:
  1. Navigate to https://webapp-example.com → redirects to /login
  2. Snapshot/inspect the login page → get selectors for username, password, login button
  3. Ask user: "I've captured the login page selectors. Could you first enter wrong credentials
     and click Login so I can capture the error message element? Then log in with your real credentials.
     I'll wait here — I cannot and will not type anything into the login form."
  4. **END RESPONSE HERE. Do not continue.** Wait for user's next message.
  --- user replies: "Done, I'm logged in. Wrong creds showed a red banner." ---
  5. Snapshot → get error element selector (e.g. <webctrl class='alert alert-danger' />)
  6. Navigate to /work-items → page loads (user is authenticated) →
     copy URL → stable → use NGoToUrl
  7. Snapshot/inspect the work items listing → get selectors for table rows, status column, links
  8. Click on work item "WI-123" → lands on /work-item/WI-123 →
     URL pattern /work-item/{WIID} is stable → use NGoToUrl with dynamic URL
  9. Snapshot/inspect → get selectors for form fields, update button, status dropdown
```

**Step 2: Extract element attributes + screenshot coordinates.** Use the Playwright snapshot/accessibility tree tool to get the DOM structure. For each interactive element you need, record: `tag`, `id`, `name`, `aria-label` (→ `aaname`), `type`, `class`, `placeholder`, `role`, and the page `<title>`.

Then, in the **same step**, run this JavaScript via Playwright MCP `browser_evaluate` to collect screen coordinates for all elements you identified. Adjust the `els` array to match the CSS selectors and names from your inspection:

```javascript
const els = [
  { sel: '#email', name: 'email_field' },
  { sel: '#password', name: 'password_field' },
  { sel: 'button[type="submit"]', name: 'login_button' }
];
const dpr = window.devicePixelRatio || 1;
const chromeY = window.outerHeight - window.innerHeight;
const chromeX = (window.outerWidth - window.innerWidth) / 2;
const results = els.map(e => {
  const el = document.querySelector(e.sel);
  if (!el) return null;
  el.scrollIntoView({ block: 'center' });
  const r = el.getBoundingClientRect();
  return {
    name: e.name,
    x: Math.round((window.screenX + chromeX + r.x) * dpr),
    y: Math.round((window.screenY + chromeY + r.y) * dpr),
    w: Math.round(r.width * dpr),
    h: Math.round(r.height * dpr)
  };
}).filter(Boolean);
JSON.stringify(results);
```

Save the JSON output — you need it for Step 3.

**Step 3: Map to UiPath selectors** using the mapping rules below. Build `ScopeSelectorArgument` (HTML node from page title + browser) and `FullSelectorArgument` (WEBCTRL node from element attributes). Copy XAML patterns from `references/xaml-ui-automation.md` (NClick/NTypeInto/NSelectItem golden patterns) and insert the real selectors. Set `SearchSteps="Selector"` (strict).

**Step 4: Generate XAML.** Use activity generators from `generate_activities`:

```python
gen_nclick("Click Login", selector, "NClick_1", scope_id)

gen_ntypeinto("Type Into 'Email'", selector, "strUsername", "NTypeInto_1", scope_id)
```

**Step 5: Record what you inspected.** When generating XAML, add a comment noting the selectors came from live inspection, e.g. `<!-- Selector from Playwright inspection of webapp-example.com/login -->`. This helps future maintainers know which selectors are verified vs guessed.

Quick mapping: `aria-label` / visible text → `aaname`, `tagName` → `tag` (UPPERCASE), `id` → `id`, page title → `ScopeSelectorArgument`.

## Workflow: Inspecting Desktop Apps (PowerShell)

**⚠️ MANDATORY STEP for desktop automation.** When building desktop automation workflows and PowerShell is available (Windows), ALWAYS run `inspect-ui-tree.ps1` BEFORE generating XAML. Do NOT ask the user what UI framework the app uses or what selectors to use — the script detects the framework automatically and returns real element attributes from the running app.

**Never ask the user these questions if PowerShell is available:**
- "What UI framework does your app use?" → inspect it
- "What are the selector attributes?" → inspect it
- "Is it WinForms or WPF?" → inspect it

### 1. Copy the script to the user's machine

```powershell
# Via PowerShell — copy from WSL to user's home (adjust distro name if needed)
Copy-Item "\\wsl$\Ubuntu-24.04\mnt\user-data\outputs\uipath-core\scripts\inspect-ui-tree.ps1" "$env:USERPROFILE\inspect-ui-tree.ps1" -Force
```

If the WSL path doesn't work (distro name differs, or no WSL), write the file content directly via `[System.IO.File]::WriteAllText()`.

### 2. Run inspection

```powershell
# Tree view — understand the app structure
& "$env:USERPROFILE\inspect-ui-tree.ps1" -WindowTitle "Desktop App*" -OutputFormat tree -MaxDepth 6

# Selector output — ready-to-use UiPath selectors (all desktop apps)
& "$env:USERPROFILE\inspect-ui-tree.ps1" -WindowTitle "Calculator" -OutputFormat selectors

# Match by process name
& "$env:USERPROFILE\inspect-ui-tree.ps1" -ProcessName "desktopapp.exe" -OutputFormat tree

# With element screenshots — captures each interactive element's region as PNG
& "$env:USERPROFILE\inspect-ui-tree.ps1" -WindowTitle "Calculator" -OutputFormat json -ScreenshotDir "$projectPath\.screenshots"
```

### 3. Interpret the output

- **UWP/WPF/Win32 apps**: `selectors` mode generates ready-to-use `<wnd>` + `<uia>` selector pairs with activity hints. Copy these directly into `FullSelectorArgument`.
- **WinForms apps**: `selectors` mode generates `<ctrl name='...' role='...' />` selectors using UIA Name property and inferred control roles. For more stable `ctrlname`/`automationid` selectors, use UiPath UI Explorer.
- **Flags**: `[!DUP_AID]` → add `idx` to selector. `[!DYNAMIC]` → use wildcard `name='Display is *'`. `[!VERIFY_TYPE]` → check if Button is actually CheckBox/RadioButton.

### 4. Build selectors from output

For non-WinForms apps, the script outputs selector pairs. **Trim to minimal** — keep only `app` + `appid` (UWP) or `app` alone (.exe):
```
<wnd app='applicationframehost.exe' appid='...' />
<uia automationid='num7Button' cls='Button' />
# Activity: Click
```

Map to XAML:
- Window selector → `ScopeSelectorArgument` on `TargetAnchorable`
- Element selector → `FullSelectorArgument` on `TargetAnchorable`
- Activity hint → which XAML activity to use (NClick, NTypeInto, NSelectItem, etc.)
- Always set `SearchSteps="Selector"` (strict)

See `references/ui-inspection-reference.md` for full property mapping tables, framework behaviors, and sample outputs.
