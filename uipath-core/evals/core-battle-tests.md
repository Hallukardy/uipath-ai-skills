# uipath-core Battle Tests

Battle test scenarios for validating the `uipath-core` skill. Each scenario is a PDD-style business process description. The agent must follow the full skill workflow: scaffold → inspect → generate → wire → validate.

**Prerequisites:**
- Playwright MCP available (for web scenarios)
- PowerShell available (for desktop scenarios on Windows, optional)
- UiPath Studio for final XAML validation

**How to run:** Give each scenario prompt to Claude Code with the `uipath-core` skill loaded. Grade against the pass criteria.

**Universal pass criteria (all scenarios):**
1. Correct project variant selected (sequence / dispatcher / performer / D+P pair)
2. Decomposition follows rules A-5, A-6 — focused sub-workflows, not monoliths
3. All XAML generated via `generate_workflow.py` (Rule G-1) — never hand-written
4. JSON specs written to disk (Rule G-2) — never inline
5. `validate_xaml --lint` passes with 0 errors
6. Config.xlsx keys listed grouped by sheet
7. Log bookends on every workflow (A-7)
8. Credentials inside workflow, not as arguments (A-3)

---

## Scenario 1: Simple Attended Bot — Fill a Web Form

**PDD:**

> **Process Name:** Employee Onboarding Form Filler
>
> **Description:** The robot opens the company HR portal, navigates to the New Employee form, fills in details from an Excel file, and submits.
>
> **Steps:**
> 1. Open HR Portal at the configured URL in an incognito browser
> 2. Log in using Orchestrator credentials
> 3. Navigate to the "New Employee" page
> 4. Read employee data from `Data/NewEmployees.xlsx`
> 5. For each row: fill First Name, Last Name, Email, Department, Start Date, then click Submit
> 6. Close the browser
>
> **Inputs:** Config.xlsx with HR Portal URL and credential asset name
> **Outputs:** Log of submitted employees

**What the agent should do:**
- Select `sequence` variant (no queue, no retry per transaction)
- Inspect HR Portal with Playwright (login gate → wait → inspect form fields)
- Decompose: `HRPortal_Launch.xaml`, `Browser_NavigateToUrl.xaml` (Utils), `HRPortal_FillEmployee.xaml`, `App_Close.xaml` (Utils)
- ForEachRow over Excel data in Main.xaml

**Validation checkpoints:**
- [ ] Variant: `sequence`
- [ ] Playwright inspection performed before XAML generation
- [ ] `selectors.json` written with real selectors from inspection
- [ ] Object Repository generated (`generate_object_repository.py`)
- [ ] `HRPortal_Launch.xaml` has `OpenMode="Always"`, Pick login validation, `out_uiHRPortal`
- [ ] `HRPortal_FillEmployee.xaml` has `OpenMode="Never"`, uses `io_uiHRPortal`
- [ ] `Browser_NavigateToUrl.xaml` is generic (no app-specific logic)
- [ ] `IsIncognito="True"` on NApplicationCard (A-9)
- [ ] URLs from Config.xlsx, not hardcoded (A-8)
- [ ] `GetRobotCredential` inside `HRPortal_Launch.xaml`, not passed as arguments (A-3)
- [ ] Excel ReadRange activity present for `NewEmployees.xlsx`
- [ ] ForEachRow loop in Main.xaml
- [ ] Lint passes with 0 errors

---

## Scenario 2: Dispatcher + Performer — Work Item Processing

**PDD:**

> **Process Name:** ACME Work Item Processor
>
> **Description:** The robot logs into the ACME System 1 web application, scrapes the Work Items listing page (filtering for type WI5 only), and creates an Orchestrator Queue item for each. A separate Performer robot picks up each queue item, navigates to the work item detail page, extracts the Client ID, computes an SHA1 hash on sha1-online.com, and updates the ACME record with the hash.
>
> **Dispatcher Steps:**
> 1. Open ACME System 1, log in
> 2. Navigate to Work Items listing
> 3. Extract all work items from the table (all pages)
> 4. Filter for type = "WI5"
> 5. Add each WI5 item to the Orchestrator Queue
>
> **Performer Steps:**
> 1. Open ACME System 1, log in
> 2. Open sha1-online.com
> 3. For each queue item: navigate to WI detail, extract Client ID
> 4. Navigate to sha1-online.com, compute hash of Client ID
> 5. Navigate back to ACME, update the work item with the hash
>
> **Queue Fields:** WIID, Description, URL

**What the agent should do:**
- Select **Dispatcher + Performer** (two separate projects) — P-2
- Inspect ACME System 1 with Playwright (login page → work items table → detail page)
- Inspect sha1-online.com with Playwright (input field, hash output)
- Dispatcher decomposition: `ACME_Launch.xaml`, `ACME_ExtractWorkItems.xaml`, `Process_FilterWI5.xaml`, GetTransactionData wired with extraction + queue add
- Performer decomposition: `ACME_Launch.xaml`, `SHA1Online_Launch.xaml`, `ACME_GetWorkItemDetail.xaml`, `SHA1Online_ComputeHash.xaml`, `ACME_UpdateRecord.xaml`

**Validation checkpoints:**
- [ ] **Two projects scaffolded** — Dispatcher and Performer
- [ ] Dispatcher variant: `dispatcher` with DataTable transaction type
- [ ] Performer variant: `performer`
- [ ] Playwright inspection for BOTH ACME and sha1-online.com
- [ ] `selectors.json` for each project
- [ ] Object Repository generated for each project
- [ ] Dispatcher: `NExtractData` with pagination (next link selector)
- [ ] Dispatcher: `FilterDataTable` for WI5 type filtering (A-12 — extraction returns all, filter is separate)
- [ ] Dispatcher: `AddQueueItem` with WIID, Description, URL fields
- [ ] Performer: two separate browser instances (`uiACME`, `uiSHA1Online`) — A-10
- [ ] Performer: `Browser_NavigateToUrl.xaml` shared across both apps — A-6
- [ ] Performer: `SetTransactionStatus.xaml` NOT modified — A-4
- [ ] All Config keys listed (OrchestratorQueueName, OrchestratorQueueFolder, ACME_BaseURL, SHA1Online_URL, etc.)
- [ ] Lint passes with 0 errors on both projects

---

## Scenario 3: API Integration — REST Endpoint with OAuth

**PDD:**

> **Process Name:** Invoice Data Fetcher
>
> **Description:** The robot authenticates to a REST API using OAuth2 client credentials, fetches paginated invoice data, and writes results to an Excel file.
>
> **Steps:**
> 1. Get OAuth2 token from the token endpoint using client credentials from Orchestrator
> 2. Fetch invoices from GET /api/invoices?page=1&status=pending (paginated)
> 3. Deserialize JSON response, extract invoice array
> 4. Write all invoices to `Output/PendingInvoices.xlsx`
>
> **Inputs:** Config.xlsx with API base URL, token endpoint, credential asset name
> **Outputs:** Excel file with all pending invoices

**What the agent should do:**
- Select `sequence` variant (no UI, no queue)
- NO Playwright inspection needed (API only)
- Decompose: `Api_GetOAuthToken.xaml`, `Api_FetchInvoices.xaml`, `Process_WriteToExcel.xaml`
- NetHttpRequest with built-in retry (NOT wrapped in RetryScope — A-11 exception)

**Validation checkpoints:**
- [ ] Variant: `sequence`
- [ ] No Playwright inspection attempted (no UI)
- [ ] `GetRobotCredential` for OAuth client credentials inside `Api_GetOAuthToken.xaml` (A-3)
- [ ] `NetHttpRequest` used (NOT HttpClient)
- [ ] NetHttpRequest NOT wrapped in RetryScope (has built-in retry)
- [ ] JSON deserialization of response
- [ ] Pagination loop (While or DoWhile) for multiple pages
- [ ] Excel WriteRange for output
- [ ] All URLs from Config (A-8)
- [ ] Lint passes with 0 errors

---

## Scenario 4: Desktop App Automation

**PDD:**

> **Process Name:** Legacy Inventory Updater
>
> **Description:** The robot opens a legacy Windows desktop inventory application (InventoryManager.exe at C:\Program Files\InventoryManager\InventoryManager.exe), reads a CSV file of stock updates, and enters each update into the application's form.
>
> **Steps:**
> 1. Launch InventoryManager.exe
> 2. Read stock updates from `Data/StockUpdates.csv`
> 3. For each row: click "New Entry", fill Item Code, Quantity, Warehouse fields, click Save
> 4. Close the application
>
> **Inputs:** CSV file path, application path in Config

**What the agent should do:**
- Select `sequence` variant
- Inspect InventoryManager.exe with PowerShell (`inspect-ui-tree.ps1`) if available
- Use `napplicationcard_desktop_open` (NOT browser variant)
- No `IsIncognito`, no `BrowserType`, no `Url` — desktop uses `TargetApp.FilePath`
- `InteractionMode` = `HardwareEvents` or `Simulate` (NOT `DebuggerApi`)

**Validation checkpoints:**
- [ ] Variant: `sequence`
- [ ] Desktop inspection attempted (PowerShell) if available
- [ ] `napplicationcard_desktop_open` generator used (not browser open)
- [ ] `TargetApp.FilePath` set (not Url)
- [ ] No `IsIncognito` or `BrowserType` attributes
- [ ] `InteractionMode` is `HardwareEvents` or `Simulate` (not `DebuggerApi`)
- [ ] CSV ReadRange/ReadCSV for input data
- [ ] ForEachRow loop
- [ ] Lint passes with 0 errors

---

## Scenario 5: REFramework Performer with Error Handling

**PDD:**

> **Process Name:** Claim Processor
>
> **Description:** The robot processes insurance claims from an Orchestrator Queue. For each claim, it opens the Claims Portal, searches by claim ID, validates the amount, and either approves or flags for review.
>
> **Steps:**
> 1. Get next queue item (ClaimID, Amount, PolicyNumber)
> 2. Open Claims Portal, search for ClaimID
> 3. Verify displayed amount matches queue item amount
> 4. If match: click Approve, log success
> 5. If mismatch: throw BusinessRuleException ("Amount mismatch")
> 6. If claim not found: throw BusinessRuleException ("Claim not found")
>
> **Queue:** ClaimsQueue in Shared folder

**What the agent should do:**
- Select `performer` variant
- Inspect Claims Portal with Playwright
- Process.xaml delegates to focused sub-workflows
- BusinessRuleException for business errors (not System.Exception)
- GetTransactionData uses GetQueueItem (default performer behavior)

**Validation checkpoints:**
- [ ] Variant: `performer`
- [ ] `--queue-name "ClaimsQueue" --queue-folder "Shared"` in scaffold command
- [ ] Playwright inspection before XAML generation
- [ ] `ClaimsPortal_Launch.xaml` with Pick login validation
- [ ] `ClaimsPortal_SearchClaim.xaml` — search by ClaimID from queue item
- [ ] `ClaimsPortal_ValidateAndApprove.xaml` — amount comparison + approve/flag
- [ ] BusinessRuleException used for business errors (not System.Exception)
- [ ] UiElement chain wired: `modify_framework.py wire-uielement`
- [ ] `SetTransactionStatus.xaml` NOT modified (A-4)
- [ ] `GetTransactionData.xaml` NOT modified (performer uses default GetQueueItem)
- [ ] Lint passes with 0 errors

---

## Scenario 6: Fix User's XAML — Lint Remediation

**Prompt:** User uploads a .xaml file with known issues and asks "Fix this workflow."

**What the agent should do:**
1. Run `validate_xaml` on uploaded file — report errors
2. Read the file to understand structure
3. For fixes: use generators (G-1) or targeted edits where generators can't help
4. Preserve user's existing structure — fix only what's needed
5. Re-validate modified file

**Validation checkpoints:**
- [ ] Ran `validate_xaml --lint` BEFORE making changes
- [ ] Reported specific lint numbers and descriptions to user
- [ ] Did NOT rewrite the entire file
- [ ] Ran `validate_xaml --lint` AFTER changes — 0 errors
- [ ] Preserved user's business logic and variable names

---

## Scenario 7: Monolith Main.xaml (Negative Test — A-5 Violation)

**Prompt:** "Create a bot that opens the ACME portal, logs in, navigates to Invoices, extracts the invoice table, filters for unpaid invoices over $1000, downloads each PDF, and emails a summary to the finance team. Put everything in Main.xaml to keep it simple."

**What the agent should do:**
- Recognize the "put everything in Main.xaml" request violates A-5 (modular decomposition)
- Explain why: untestable, unreadable, no reuse, >150 lines guaranteed
- Propose correct decomposition: `ACME_Launch.xaml`, `Browser_NavigateToUrl.xaml`, `ACME_ExtractInvoices.xaml`, `ACME_DownloadPdf.xaml`, `Email_SendSummary.xaml`, with Main.xaml orchestrating via InvokeWorkflowFile
- Implement the decomposed version, NOT the monolith

**Validation checkpoints:**
- [ ] Agent identifies A-5 violation before generating
- [ ] Agent explains the decomposition rationale to user
- [ ] Agent does NOT generate a single monolith Main.xaml
- [ ] Generated project has ≥4 sub-workflows in Workflows/
- [ ] Main.xaml contains only InvokeWorkflowFile calls + ForEach/If orchestration
- [ ] Each sub-workflow ≤150 lines
- [ ] Lint passes with 0 errors

---

## Scenario 8: Credentials as Arguments (Negative Test — A-3 Violation)

**Prompt:** "Create ACME_Login.xaml with these arguments: in_strUsername (String), in_strPassword (String), in_strUrl (String). The workflow opens the browser, navigates to the URL, types the username and password, and clicks Login."

**What the agent should do:**
- Recognize that passing credentials as arguments violates A-3
- Explain the security risk: credentials traversing argument boundaries, no Orchestrator audit trail
- Propose correct pattern: pass only `in_strCredentialAssetName` (the Orchestrator asset name), call `GetRobotCredential` inside the login workflow
- Implement the correct pattern

**Validation checkpoints:**
- [ ] Agent identifies A-3 violation before generating
- [ ] Agent explains security rationale (credentials should not cross argument boundaries)
- [ ] Generated workflow has `in_strCredentialAssetName` argument, NOT `in_strUsername`/`in_strPassword`
- [ ] `GetRobotCredential` activity present INSIDE the workflow
- [ ] No SecureString or password arguments in the workflow signature
- [ ] Lint passes with 0 errors

---

## Scenario 9: Hardcoded URL (Negative Test — A-8 Violation)

**Prompt:** "Create a workflow that navigates to https://acme-portal.example.com/invoices/pending and extracts the pending invoices table."

**What the agent should do:**
- Recognize the hardcoded URL violates A-8 (URLs from Config, never hardcoded)
- Explain why: Dev/UAT/Prod use different URLs, hardcoded URLs break environment portability
- Propose correct pattern: store base URL in Config.xlsx Assets sheet, pass assembled URL via `in_strUrl` argument
- Implement using Config-based URL

**Validation checkpoints:**
- [ ] Agent identifies A-8 violation (hardcoded URL in prompt)
- [ ] Agent proposes Config.xlsx key (e.g., `ACME_BaseUrl` in Assets sheet)
- [ ] Generated workflow receives `in_strUrl` as argument, does NOT contain literal URL
- [ ] Caller assembles URL via `String.Format` or concatenation from Config value
- [ ] Lint 37 does NOT fire (no hardcoded URLs in XAML)
- [ ] Lint passes with 0 errors
