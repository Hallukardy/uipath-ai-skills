# Tasks Activities (Form Tasks)

CreateFormTask, WaitForFormTaskAndResume — human-in-the-loop form approval via UiPath Tasks.

## Action Types Comparison

| Type | Namespace Prefix | UI in Tasks | Data Type | Use Case | Reference |
|------|-----------------|-------------------|-----------|----------|-----------|
| Form Task | `upaf:` | form.io form | `FormTaskData` | Human fills form, reviews data | This file |
| External Task | `upae:` | None (no UI) | `ExternalTaskData` | External system resolves via API | `external-tasks.md` |
| App Task | (future) | UiPath App | `AppTaskData` | Rich app UI, actionable notifications | (not yet implemented) |

**Task Management** activities (CompleteTask, AssignTasks, GetFormTasks) work with any task type. See `task-management.md`.

## Contents
- [Action Types Comparison](#action-types-comparison)
- [Prerequisites](#prerequisites)
- [Create Form Task](#create-form-task)
- [FormData Bindings](#formdata-bindings)
- [Form.io Component Reference](#formio-component-reference)
- [Wait for Form Task and Resume](#wait-for-form-task-and-resume)
- [Typical Tasks Pattern](#typical-tasks-pattern)
- [Shadow Task Pattern](#shadow-task-pattern)

## Prerequisites

**Required NuGet packages (add ALL to project.json via `resolve_nuget.py`):**
- `UiPath.Persistence.Activities` — runtime activities (CreateFormTask, WaitForFormTaskAndResume)
- `UiPath.FormActivityLibrary` (2.0.7+) — form designer UI in Studio. Without this, Studio shows "Install UiPath.FormActivityLibrary (2.0.7 or above) to enable form designer" and the form designer button does nothing. Note: `UiPath.Form.Activities` does NOT transitively install `FormActivityLibrary` — you must add it explicitly.

**project.json requirement:** `"supportsPersistence": true` must be set in `runtimeOptions` for WaitForFormTaskAndResume (long-running activity that persists state). The scaffold script sets this automatically when `UiPath.Persistence.Activities` is in deps. If adding to an existing project manually, ensure this flag is `true`.

**⚠️ Main.xaml constraint:** All wait-and-resume activities (`WaitForFormTaskAndResume`, `CreateFormTask`+wait pairs) are persistence points — the workflow suspends, serializes to the database, and later resumes. **These MUST be in Main.xaml (the entry-point file), never in invoked sub-workflows.** The persistence bookmark context is only available in the entry-point. Move data prep, UI, and API logic into sub-workflows; keep orchestration + persistence activities in Main.

Requires namespace:
```
xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"
```

Variable for task object: `<Variable x:TypeArguments="upaf:FormTaskData" Name="taskObj" />`

## Create Form Task

Creates an Tasks task with a form.io-based form layout that a human user can fill in.

→ **Use `gen_create_form_task()`** from this skill's `extensions/generators.py` (auto-loaded via uipath-core's plugin system) — generates correct XAML deterministically.

### Generator JSON Spec
```json
{
  "gen": "create_form_task",
  "args": {
    "task_title_expr": "String.Format(&quot;DataReview_{0}_{1}&quot;, FileName, DateTime.now.ToString(&quot;ddMMyyyyhhmmss&quot;))",
    "task_output_variable": "taskObj",
    "form_layout_json": "{\"components\":[...]}",
    "task_catalog_expr": "in_Config(&quot;ActionCatalogName&quot;).ToString",
    "task_priority": "Medium",
    "bucket_name_expr": "in_Config(&quot;DUStorageBucket&quot;).ToString",
    "form_data": {
      "in_dt_records": ["InOut", "sd:DataTable", "dt_recordsForReview"],
      "file_url": ["In", "x:String", "StorageBucketUrl"],
      "businessPartnerName": ["In", "x:String", "strBusinessPartnerName"],
      "fileName": ["In", "x:String", "FileName"]
    }
  }
}
```

### Key Properties
- `FormLayout` — JSON string containing form.io schema (see Form.io Component Reference below)
- `FormLayoutGuid` / `BulkFormLayoutGuid` — GUIDs identifying the form layout in Orchestrator
- `TaskCatalog` — Action Catalog name from Orchestrator (typically from config dictionary)
- `TaskTitle` — VB.NET expression for human-readable task name
- `TaskPriority`: `Low`, `Medium`, `High`, `Critical`
- `TaskOutput` — `upaf:FormTaskData` variable that receives the created task object
- `BucketName` — storage bucket for attached files (optional)
- `GenerateInputFields="True"` — auto-generate input fields from FormData
- `EnableBulkEdit` — feature flag for bulk editing (usually False)
- `EnableDynamicForms="True"` — **MUST be True** to enable the form designer in Studio. When False, the "Open Form Designer" button does nothing even with FormActivityLibrary installed.
- `EnableV2` — V2 form engine (usually False)

**⚠️ WRONG property name (common hallucination):** `TaskObject` does NOT exist. Use `TaskOutput` on CreateFormTask and `TaskInput` on WaitForFormTaskAndResume.

### Generator Python API
```python
from extensions.generators import gen_create_form_task  # auto-loaded via plugin system
gen_create_form_task(
    task_title_expr,        # VB.NET expression for task title
    task_output_variable,   # Variable receiving FormTaskData (no brackets)
    form_layout_json,       # form.io JSON schema string
    id_ref,                 # Unique IdRef suffix
    form_data=None,         # Dict: {"fieldKey": ["direction", "type", "variable"]}
    task_catalog_expr="",   # VB.NET expression for Action Catalog name
    task_priority="Medium", # Low | Medium | High | Critical
    bucket_name_expr="",    # VB.NET expression for storage bucket name
    display_name="Create Form Task",
    indent="    "           # String of spaces (default: 4 spaces)
)
```

## FormData Bindings

The `form_data` dict in `gen_create_form_task()` maps form field keys to workflow variables. Each entry is `"fieldKey": ["direction", "type", "variable"]`:
- `"In"` — workflow → form (read-only, pre-populated)
- `"Out"` — form → workflow (user-entered data returned after submission)
- `"InOut"` — two-way binding (pre-populated AND user-editable, common for DataTable ↔ datagrid)

The generator handles the `{}` XAML escape prefix on `FormLayout` (required because JSON starts with `{` which the XAML parser would interpret as a markup extension).

## Form.io Component Reference

### Component Types
```
textfield   — single-line text input
textarea    — multi-line text input
number      — numeric input
select      — dropdown
checkbox    — boolean checkbox
datagrid    — editable table (maps to DataTable via InOutArgument)
htmlelement — static HTML content (e.g., links, labels)
columns     — layout: side-by-side columns
button      — submit/action button
```

### Basic Component Structure
```json
{
  "label": "Field Label",
  "key": "fieldKey",           // Must match FormData key
  "type": "textfield",
  "input": true,
  "disabled": true,            // Read-only when true
  "tableView": true,
  "validate": {"required": true}  // Optional validation
}
```

**⚠️ Always include a submit button as the last component:**
```json
{"type": "button", "label": "Submit", "key": "submit", "action": "submit", "input": true, "tableView": false}
```

### Datagrid (Editable Table → DataTable)
```json
{
  "label": "Records",
  "key": "in_dt_records",    // Must match InOutArgument key
  "type": "datagrid",
  "input": true,
  "disableAddingRemovingRows": true,
  "reorder": false,
  "hideLabel": true,
  "components": [
    {"label": "Raw Input", "key": "rawInput", "type": "textarea", "disabled": true},
    {"label": "City", "key": "ville", "type": "textfield", "validate": {"required": true}}
  ]
}
```

### HTML Element with Dynamic Data Binding
```json
{
  "label": "HTML",
  "key": "file_url",
  "type": "htmlelement",
  "input": false,
  "content": "<a href=\"{{data.file_url}}\">{{data.fileName}}</a>"
}
```
- `{{data.fieldKey}}` — Mustache template syntax referencing other form field values

## Wait for Form Task and Resume

Suspends the workflow (releases the robot) until a human user submits the form in Tasks.
The workflow resumes automatically after submission.

→ **Use `gen_wait_for_form_task()`** from this skill's `extensions/generators.py` (auto-loaded via uipath-core's plugin system) — generates correct XAML deterministically.

### Generator JSON Spec
```json
{
  "gen": "wait_for_form_task",
  "args": {
    "task_input_variable": "taskObj",
    "task_action_variable": "strTaskAction",
    "task_output_variable": "taskObjUpdated"
  }
}
```

### Key Properties
- `task_input_variable` — the `upaf:FormTaskData` variable from `gen_create_form_task()`'s `task_output_variable`
- `task_action_variable` — (optional) receives the action taken by user (e.g., "submit", "reject")
- `task_output_variable` — (optional) receives updated FormTaskData after submission
- **This is a long-running activity** — the robot is freed while waiting. Workflow state is persisted to Orchestrator.

### Generator Python API
```python
from extensions.generators import gen_wait_for_form_task  # auto-loaded via plugin system
gen_wait_for_form_task(
    task_input_variable,       # FormTaskData variable from CreateFormTask.TaskOutput (no brackets)
    id_ref,                    # Unique IdRef suffix
    task_action_variable="",   # Optional — receives action string
    task_output_variable="",   # Optional — receives updated FormTaskData
    display_name="Wait for Form Task and Resume",
    indent="    "           # String of spaces (default: 4 spaces)
)
```

## Typical Tasks Pattern
```
1. Check if task is needed (If condition)
2. LogMessage → "Creating AC task..."
3. RetryScope → CreateFormTask (resilience against transient failures)
     TaskCatalog = config("ActionCatalogName")
     TaskTitle = String.Format("TaskType_{0}_{1}", docName, timestamp)
     FormData binds workflow variables to form fields
     → [taskObj]
4. WaitForFormTaskAndResume → [taskObj]
     (robot released — human completes form in Tasks)
5. Process user input from InOutArgument/OutArgument variables
```

## Shadow Task Pattern

Advanced pattern from real production workflows:
```
1. Create "shadow" task first (a lightweight form for preliminary data)
2. Create main review task (with full form + datagrid of records)
3. WaitForFormTaskAndResume → main task
4. After main task completes, WaitForFormTaskAndResume → shadow task
   (shadow task was already submitted by user earlier — bot just catches up)
```
This avoids blocking: the shadow task doesn't delay creation of the main task.

## Anti-pattern: persistence inside a loop/retry scope

`WaitForFormTaskAndResume` **cannot** be nested inside `ui:ForEachRow`, `ui:ForEach`, `ui:RetryScope`, `TryCatch`, `Parallel`, `Pick`, `While`, or `DoWhile`. These scopes hold per-iteration or per-branch state that cannot serialize mid-flight when a bookmark suspends the workflow. Studio rejects it at validation time with: *"Cannot place activity under scope '<name>', as the activity requires persistence and the scope does not offer support for it."*

❌ Wrong — wait nested inside `ui:ForEachRow`:
```xml
<ui:ForEachRow DisplayName="For Each Invoice">
  <ui:ForEachRow.Body>
    <ActivityAction x:TypeArguments="sd:DataRow">
      <Sequence>
        <upaf:CreateFormTask TaskOutput="[fdtInvoiceTask]" ... />
        <upaf:WaitForFormTaskAndResume TaskInput="[fdtInvoiceTask]" ... />  <!-- fails validation -->
      </Sequence>
    </ActivityAction>
  </ui:ForEachRow.Body>
</ui:ForEachRow>
```

✅ Right — Shadow Task Pattern: collect tasks in the loop, wait outside:
```xml
<!-- Variable: lstInvoiceTasks : List(FormTaskData) = New List(Of FormTaskData) -->
<ui:ForEachRow DisplayName="For Each Invoice">
  <ui:ForEachRow.Body>
    <ActivityAction x:TypeArguments="sd:DataRow">
      <Sequence>
        <upaf:CreateFormTask TaskOutput="[fdtInvoiceTask]" ... />
        <InvokeMethod MethodName="Add">
          <InvokeMethod.TargetObject>
            <InArgument x:TypeArguments="scg:List(upaf:FormTaskData)">[lstInvoiceTasks]</InArgument>
          </InvokeMethod.TargetObject>
          <InvokeMethod.Parameters>
            <InArgument x:TypeArguments="upaf:FormTaskData">[fdtInvoiceTask]</InArgument>
          </InvokeMethod.Parameters>
        </InvokeMethod>
      </Sequence>
    </ActivityAction>
  </ui:ForEachRow.Body>
</ui:ForEachRow>
<ui:ForEach x:TypeArguments="upaf:FormTaskData" Values="[lstInvoiceTasks]">
  <ui:ForEach.Body>
    <ActivityAction x:TypeArguments="upaf:FormTaskData">
      <Sequence>
        <upaf:WaitForFormTaskAndResume TaskInput="[item]" ... />
        <!-- handle decision here -->
      </Sequence>
    </ActivityAction>
  </ui:ForEach.Body>
</ui:ForEach>
```

Enforced by AC-27 (`lint_persistence_in_unsupported_scope`).

### InvokeMethod notes

`InvokeMethod` lives in the **default** activities namespace (`http://schemas.microsoft.com/netfx/2009/xaml/activities`), not under `ui:`. Using `<ui:InvokeMethod>` fails Studio validation with *"Could not find type 'InvokeMethod' in namespace 'http://schemas.uipath.com/workflow/activities'"* (AC-29). Also set `TargetObject` via element form, because the attribute-form `TargetObject="[expr]"` doesn't always dispatch through the `InArgument` converter (AC-30).

## Using an external form file (DynamicFormPath)

When the form is large or shared across workflows, keep it in a `.json` file under the project and set:
- `EnableDynamicForms="True"`
- `DynamicFormPath="Forms\MyForm.json"` (relative to project root)

**The file schema is NOT standard form.io.** UiPath expects:

```json
{
  "id": "<any-guid-or-slug>",
  "form": [
    { "label": "Supplier", "key": "supplier", "type": "textfield", "input": true, "disabled": true, "tableView": true },
    { "label": "Action", "key": "action", "type": "select", "input": true,
      "data": { "values": [ { "label": "Approve", "value": "approve" }, { "label": "Reject", "value": "reject" } ] },
      "validate": { "required": true } },
    { "type": "button", "label": "Submit", "key": "submit", "action": "submit", "input": true }
  ]
}
```

Critical differences from standard form.io:
- Root key is **`form`**, not `components`.
- Root **`id`** is required (any string).
- No `display`, `name`, `title` wrapper fields needed.

Wrong shapes produce misleading runtime errors (all observed):
- `{"components":[...]}` → `Cannot deserialize the current JSON object into List<FormIOComponent> ... Path 'components'`.
- `[...]` (bare array) → `JArray does not contain a definition for 'id'`.
- `{"display":"form","components":[...]}` → `Form File has invalid format`.

## Reading task output

After `WaitForFormTaskAndResume` completes, prefer **typed properties** and your **OutArgument variables** over `.Data("key")` access.

`FormTaskData.Data` is a weakly-typed dictionary. Calling `fdtTask.Data("invoiceNumber")` returns `Object`, which fails under `Option Strict On` with *"BC30574: Option Strict On disallows late binding"* (AC-31).

```xml
<!-- ❌ Wrong -->
<ui:LogMessage Message="[String.Format(&quot;Invoice {0} approved&quot;, fdtTask.Data(&quot;invoiceNumber&quot;).ToString())]" />

<!-- ✅ Right — use the typed Title property (already formatted via CreateFormTask.TaskTitle) -->
<ui:LogMessage Message="[String.Format(&quot;{0} approved&quot;, fdtTask.Title)]" />

<!-- ✅ Right — use the OutArgument variable you bound in CreateFormTask.FormData -->
<ui:LogMessage Message="[String.Format(&quot;Invoice {0} approved&quot;, strInvoiceNum)]" />
```

`FormData` OutArgument bindings (`<OutArgument x:Key="fieldKey">[strMyVar]</OutArgument>` inside `<upaf:CreateFormTask.FormData>`) set typed variables at resume time — that's the strongly-typed path.

## Orchestrator folder (FolderPath)

`CreateFormTask`, `WaitForFormTaskAndResume`, and related Action Center activities need to know which Orchestrator folder to create the task in. Without it, runtime fails with *"A folder is required for this action. Error code: 1101"* (AC-28).

Set the `FolderPath` attribute on the activity to an Orchestrator folder name (e.g. `"Shared"`, or a Config.xlsx key). Studio injects this automatically when you set the value via the Properties panel.

## Validation & Lint Rules

These lint rules live in uipath-core's `validate_xaml` and apply to Tasks workflows:

| Lint | Severity | What it checks |
|---|---|---|
| AC-10 | Warning | CreateFormTask count must match WaitForFormTaskAndResume count |
| AC-26 | Error | Persistence activities (WaitForFormTaskAndResume) must be in Main.xaml only |
| AC-27 | Error | Persistence activities must not be nested in ForEach/ForEachRow/RetryScope/TryCatch/Parallel/Pick/While/DoWhile |
| AC-28 | Warning | `CreateFormTask` needs `FolderPath` set (runtime error code 1101 otherwise) |
| AC-29 | Error | `<ui:InvokeMethod>` doesn't exist — use default namespace `<InvokeMethod>` |
| AC-30 | Warning | `<InvokeMethod TargetObject="[expr]">` attribute form; use element form with typed `InArgument` |
| AC-31 | Warning | `fdtTask.Data("key")` is late-bound — use typed `Title` property or OutArgument variable |

Additional checks within lint 10:
- `TaskOutput="{x:Null}"` — warns that task data won't be captured
- `EnableDynamicForms="False"` — warns that form designer won't work

## Config.xlsx Keys (Typical)

Tasks workflows commonly need these keys in Config.xlsx (Settings sheet):
- `ActionCatalogName` — Action Catalog name in Orchestrator
- `DUStorageBucket` — Document Understanding storage bucket (if using file attachments)
