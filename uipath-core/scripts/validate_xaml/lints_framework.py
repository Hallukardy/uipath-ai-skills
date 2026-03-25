"""Framework architecture lint rules."""

import os
import re

from ._registry import lint_rule
from ._context import FileContext, ValidationResult
from ._constants import (
    _RE_DISPLAY_NAME, _RE_CONFIG_KEYS_SUMMARY, _RE_XPROPERTY_NAME,
)


@lint_rule(39)
def lint_config_keys_summary(ctx: FileContext, result: ValidationResult):
    """Lint 39: Extract and list all Config() key references.

    Not a warning — informational output listing all Config keys
    referenced in the XAML so the user knows what to add to Config.xlsx.
    """
    try:
        content = ctx.content
    except Exception:
        return

    # Find Config("KeyName") patterns (both in_Config and Config)
    # Two encodings: &quot; in XML attributes, literal " in element content
    keys = set()
    for pattern in [
        r'Config\(&quot;([^&]+)&quot;\)',
        r'in_Config\(&quot;([^&]+)&quot;\)',
        r'Config\("([^"]+)"\)',
        r'in_Config\("([^"]+)"\)',
    ]:
        keys.update(re.findall(pattern, content))

    if keys:
        sorted_keys = sorted(keys)
        result.ok(
            f"[lint 39] Config.xlsx keys referenced: {', '.join(sorted_keys)}. "
            f"Ensure these exist in the correct sheet of Data/Config.xlsx "
            f"(Settings for project identity/credentials, Assets for URLs/env-specific values, Constants for immutable values)."
        )


@lint_rule(59)
def lint_attach_without_uielement(ctx: FileContext, result: ValidationResult):
    """Lint 59: NApplicationCard attach-mode without InUiElement browser reference.

    When OpenMode="Never" (attach to existing browser), the NApplicationCard
    needs InUiElement bound to a UiElement variable (typically io_uiBrowser)
    to identify which browser instance to attach to. Without it, UiPath falls
    back to selector matching which is ambiguous when multiple browser windows
    exist (e.g., WebApp + SHA1Online both open in Edge).

    Launch workflows (OpenMode="Always") don't need InUiElement — they open
    a new browser.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "<uix:NApplicationCard" not in content:
        return

    # Find all NApplicationCard elements with OpenMode="Never"
    # (attach to existing browser/app)
    cards = re.findall(
        r'<uix:NApplicationCard\b([^>]*)>',
        content, re.DOTALL
    )
    for attrs in cards:
        is_attach = 'OpenMode="Never"' in attrs
        if not is_attach:
            continue

        has_in_ui = re.search(r'InUiElement="(\[.+?\])"', attrs)
        is_null = 'InUiElement="{x:Null}"' in attrs

        if not has_in_ui or is_null:
            # Extract DisplayName for context
            dn_match = _RE_DISPLAY_NAME.search(attrs)
            dn = dn_match.group(1) if dn_match else "NApplicationCard"
            result.warn(
                f"[lint 59] '{dn}' uses OpenMode=\"Never\" (attach) without "
                f"InUiElement binding. Without a UiElement reference (e.g., "
                f"io_uiAppName as InOutArgument), UiPath falls back to "
                f"generic selector matching — fragile when multiple browser "
                f"windows exist. Add a UiElement InOutArgument and bind "
                f"InUiElement=\"[io_uiAppName]\"."
            )


@lint_rule(62)
def lint_log_bookends(ctx: FileContext, result: ValidationResult):
    """Lint 62: Custom workflows should have start/end LogMessage activities.

    Rule 7: Every workflow should begin with LogMessage "[START] WorkflowName"
    and end with LogMessage "[END] WorkflowName". This is critical for
    production debugging — without log bookends, you can't trace which
    workflow was executing when a failure occurred.

    Skips: Framework/ files (template code), Tests/ files, Main.xaml
    (StateMachine has its own logging).
    """
    basename = os.path.basename(ctx.filepath)
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))

    # Skip framework, tests, Main.xaml
    if parent_dir in ("Framework", "Tests"):
        return
    if basename.lower() == "main.xaml":
        return

    content = ctx.active_content
    if not content:
        return

    # Only check files with actual business logic (have activities beyond boilerplate)
    has_activities = any(act in content for act in [
        "<ui:InvokeWorkflowFile", "<uix:NClick", "<uix:NTypeInto",
        "<uix:NGetText", "<uix:NGoToUrl", "<uix:NApplicationCard",
        "<uix:NExtractDataGeneric", "<ui:AddQueueItem", "<Assign",
        "<ui:GetRobotCredential", "<ui:NetHttpRequest",
    ])
    if not has_activities:
        return

    log_count = content.count("<ui:LogMessage")
    if log_count == 0:
        result.warn(
            f"[lint 62] No LogMessage activities in '{basename}'. "
            f"Rule 7: Every custom workflow needs log bookends — "
            f"first activity: LogMessage \"[START] {basename.replace('.xaml', '')}\", "
            f"last activity: LogMessage \"[END] {basename.replace('.xaml', '')}\". "
            f"Without these, production failures are untraceable."
        )


@lint_rule(63, golden_suppressed=True, needs_project_dir=True)
def lint_init_close_symmetry(ctx: FileContext, result: ValidationResult,
                              project_dir: str | None = None):
    """Lint 63: InitAllApplications and CloseAllApplications must be symmetric.

    Every app opened in InitAllApplications (via *_Launch.xaml InvokeWorkflowFile)
    must have a corresponding close in CloseAllApplications (via App_Close.xaml
    or *_Close.xaml). Asymmetry → zombie processes accumulate across transactions.

    Only runs on CloseAllApplications.xaml with project_dir context.
    """
    basename = os.path.basename(ctx.filepath)
    if basename.lower() != "closeallapplications.xaml":
        return
    if not project_dir:
        return

    # Find InitAllApplications
    init_path = os.path.join(os.path.dirname(ctx.filepath), "InitAllApplications.xaml")
    if not os.path.exists(init_path):
        return

    try:
        with open(init_path, "r", encoding="utf-8-sig") as f:
            init_content = f.read()
        close_content = ctx.active_content
    except Exception:
        return

    # Count Launch invocations in Init
    launch_files = re.findall(
        r'WorkflowFileName="([^"]*[Ll]aunch[^"]*)"', init_content
    )
    # Count Close invocations in Close
    close_files = re.findall(
        r'WorkflowFileName="([^"]*[Cc]lose[^"]*)"', close_content
    )

    if not launch_files:
        return  # No launches — nothing to check

    if len(close_files) < len(launch_files):
        launch_names = [os.path.basename(f) for f in launch_files]
        close_names = [os.path.basename(f) for f in close_files]
        result.warn(
            f"[lint 63] InitAllApplications opens {len(launch_files)} app(s) "
            f"({', '.join(launch_names)}) but CloseAllApplications only closes "
            f"{len(close_files)} ({', '.join(close_names) if close_names else 'none'}). "
            f"Each launched app needs a corresponding close — zombie processes "
            f"accumulate across transactions. Add App_Close.xaml or "
            f"AppName_Close.xaml for each missing app."
        )


@lint_rule(64)
def lint_login_without_validation(ctx: FileContext, result: ValidationResult):
    """Lint 64: Login workflow should validate login success.

    When a workflow contains GetRobotCredential (credential retrieval) AND
    NClick (login button submission), it should also contain Pick/PickBranch
    with NCheckAppState (or ElementExists) to validate login succeeded.

    Without validation, the workflow proceeds blindly after clicking login —
    if credentials are wrong or the page is slow, all downstream workflows
    fail with confusing selector errors instead of a clear "login failed".
    """
    basename = os.path.basename(ctx.filepath).lower()
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))

    if parent_dir in ("Framework", "Tests"):
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    has_credential = "<ui:GetRobotCredential" in content
    has_click = "<uix:NClick" in content

    if not (has_credential and has_click):
        return  # Not a login workflow

    # Check for validation patterns
    has_pick = "<Pick" in content or "<PickBranch" in content
    has_check = "<uix:NCheckAppState" in content or "ElementExists" in content

    if not (has_pick or has_check):
        result.warn(
            f"[lint 64] '{os.path.basename(ctx.filepath)}' has GetRobotCredential + "
            f"NClick (login pattern) but no Pick/NCheckAppState validation. "
            f"After clicking login, use Pick with two PickBranch activities: "
            f"(1) NCheckAppState targeting the post-login success element, "
            f"(2) NCheckAppState targeting the login error message. "
            f"This catches wrong credentials immediately instead of failing "
            f"downstream with confusing selector errors."
        )


@lint_rule(65)
def lint_closeall_killprocess(ctx: FileContext, result: ValidationResult):
    """Lint 65: CloseAllApplications must NOT contain KillProcess.

    CloseAllApplications.xaml is the GRACEFUL close path — it invokes
    App_Close.xaml (CloseMode="Always") per application. KillProcess is
    the FORCEFUL fallback and belongs ONLY in KillAllProcesses.xaml.

    Main.xaml End Process uses TryCatch:
      Try: invoke CloseAllApplications (graceful)
      Catch: invoke KillAllProcesses (forceful fallback)
    """
    basename = os.path.basename(ctx.filepath).lower()
    if basename != "closeallapplications.xaml":
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    if "KillProcess" in content:
        result.error(
            f"[lint 65] CloseAllApplications.xaml contains KillProcess — "
            f"this is the GRACEFUL close path and must use App_Close.xaml "
            f"(NApplicationCard CloseMode='Always') per application. "
            f"KillProcess belongs ONLY in KillAllProcesses.xaml (forceful fallback). "
            f"Architecture: Main.xaml End Process → TryCatch → "
            f"Try: CloseAllApplications (graceful) → Catch: KillAllProcesses (forceful)."
        )


@lint_rule(66)
def lint_launch_missing_outuielement(ctx: FileContext, result: ValidationResult):
    """Lint 66: Launch workflows must output the browser/app UiElement.

    NApplicationCard in Launch workflows (OpenMode='Always') must have
    OutUiElement="[out_uiAppName]" so the caller (InitAllApplications)
    can capture the opened browser/app reference and pass it to Main.

    The argument must be declared as OutArgument(UiElement) with name
    pattern out_uiAppName (e.g., out_uiWebApp, out_uiSHA1Online).
    Downstream workflows (Process, actions) use io_ direction (InOut)
    to preserve updated references.
    """
    basename = os.path.basename(ctx.filepath).lower()
    if "launch" not in basename:
        return

    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))
    if parent_dir in ("Framework", "Tests"):
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    if "NApplicationCard" not in content:
        return

    # Check for OutUiElement specifically on NApplicationCard
    has_outuielement_on_card = bool(
        re.search(r'<uix:NApplicationCard[^>]*OutUiElement=', content)
    )

    if not has_outuielement_on_card:
        result.error(
            f"[lint 66] Launch workflow '{os.path.basename(ctx.filepath)}' has NApplicationCard "
            f"but no OutUiElement property. Launch workflows MUST set "
            f"OutUiElement=\"[out_uiAppName]\" on NApplicationCard to capture the opened "
            f"browser/app instance. Declare as OutArgument(UiElement) (e.g., out_uiWebApp). "
            f"InitAllApplications outputs it to Main, which passes it as io_ (InOut) "
            f"to Process.xaml and action workflows to preserve updated references."
        )


@lint_rule(68)
def lint_app_close_outside_closeall(ctx: FileContext, result: ValidationResult):
    """Lint 68: App_Close must only be invoked from CloseAllApplications.

    In REFramework, app lifecycle is managed by the framework states:
      - InitAllApplications opens apps (via AppName_Launch.xaml)
      - CloseAllApplications closes apps (via App_Close.xaml)
      - KillAllProcesses force-kills as fallback

    Process.xaml and action workflows must NEVER invoke App_Close because:
      - The browser/app is needed across multiple transactions
      - Next transaction loop iteration would have no app to attach to
      - The framework's End Process state handles closing via CloseAllApplications

    App_Close in Process.xaml = dead browser on transaction 2.
    """
    basename = os.path.basename(ctx.filepath).lower()

    # App_Close is allowed in CloseAllApplications (its whole purpose)
    if "closeall" in basename or "close_all" in basename:
        return
    # Skip framework files and the close utility itself
    if basename in ("app_close.xaml", "killallprocesses.xaml"):
        return
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))
    if parent_dir == "Framework":
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    # Only applies to REFramework projects (identified by CloseAllApplications.xaml)
    project_dir = os.path.dirname(ctx.filepath)
    # Walk up to find project root (where project.json lives)
    while project_dir and not os.path.isfile(os.path.join(project_dir, "project.json")):
        parent = os.path.dirname(project_dir)
        if parent == project_dir:
            break
        project_dir = parent
    is_reframework = any(
        os.path.isfile(os.path.join(project_dir, "Framework", f))
        for f in ("CloseAllApplications.xaml", "InitAllApplications.xaml")
    ) if project_dir else False
    if not is_reframework:
        return  # Simple sequence — App_Close from anywhere is valid

    # Check for InvokeWorkflowFile referencing App_Close
    if re.search(r'WorkflowFileName="[^"]*App_Close\.xaml"', content, re.IGNORECASE):
        result.error(
            f"[lint 68] '{os.path.basename(ctx.filepath)}' invokes App_Close.xaml — "
            f"this is only allowed in CloseAllApplications.xaml. In REFramework, "
            f"apps stay open across transactions; closing mid-process kills the "
            f"browser for subsequent transactions. The End Process state calls "
            f"CloseAllApplications which handles all app closing."
        )


@lint_rule(69)
def lint_launch_login_without_validation(ctx: FileContext, result: ValidationResult):
    """Lint 69: Launch workflows with login must validate success/failure.

    If a Launch workflow contains GetRobotCredential (i.e., it logs in),
    it MUST have Pick + PickBranch with NCheckState to verify login
    succeeded or catch login errors. Without validation, a failed login
    goes undetected and every subsequent workflow crashes on the login
    page instead of the expected dashboard.

    Pattern: Pick with two PickBranch:
      - Branch 1 (Success): NCheckState waiting for dashboard element
      - Branch 2 (Failure): NCheckState waiting for error element → NGetText → Throw
    """
    basename = os.path.basename(ctx.filepath).lower()
    if "launch" not in basename:
        return

    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))
    if parent_dir in ("Framework", "Tests"):
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    # Only check if workflow has login (GetRobotCredential)
    if "GetRobotCredential" not in content:
        return

    # Must have Pick/PickBranch validation
    has_pick = "<Pick " in content or "<Pick>" in content
    has_pickbranch = "<PickBranch " in content or "<PickBranch>" in content
    has_checkstate = "NCheckState" in content

    if not (has_pick and has_pickbranch and has_checkstate):
        missing = []
        if not has_pick:
            missing.append("Pick")
        if not has_pickbranch:
            missing.append("PickBranch")
        if not has_checkstate:
            missing.append("NCheckState")
        result.error(
            f"[lint 69] Launch workflow '{os.path.basename(ctx.filepath)}' has login "
            f"(GetRobotCredential) but no login validation. Missing: {', '.join(missing)}. "
            f"MUST use Pick with two PickBranch: (1) Success branch — NCheckState "
            f"waiting for dashboard/home element, (2) Failure branch — NCheckState "
            f"waiting for error element → NGetText error message → Throw. "
            f"Without validation, failed logins go undetected and crash downstream workflows."
        )


@lint_rule(74)
def lint_init_all_apps_scope(ctx: FileContext, result: ValidationResult):
    """Lint 74: InitAllApplications must ONLY invoke Launch workflows.

    InitAllApplications.xaml is a delegation workflow — it invokes
    AppName_Launch.xaml sub-workflows via InvokeWorkflowFile and nothing else.
    Any direct UI automation, data extraction, queue operations, or business
    logic here is a structural violation. Those belong in Launch workflows
    (for login/setup) or Process.xaml (for business logic).

    Allowed: InvokeWorkflowFile, LogMessage, TryCatch, Catch, Sequence,
             Assign, Throw, Rethrow (structural/error handling only)
    Banned:  Any uix: activity (NTypeInto, NClick, NApplicationCard, etc.),
             AddQueueItem, GetQueueItem, ForEachRow, ReadRange, WriteRange,
             HttpClient, GetRobotCredential, BuildDataTable, etc.
    """
    basename = os.path.basename(ctx.filepath)
    if "initallapplications" not in basename.lower():
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    # Banned activity patterns — anything that does real work
    banned_patterns = [
        # UI Automation (any uix: activity)
        (r'<uix:\w+', "UI automation activity (uix:*)"),
        # Orchestrator
        (r'<ui:AddQueueItem\b', "AddQueueItem"),
        (r'<ui:GetQueueItem\b', "GetQueueItem"),
        (r'<ui:GetRobotCredential\b', "GetRobotCredential"),
        (r'<ui:GetRobotAsset\b', "GetRobotAsset"),
        # Data operations
        (r'<ui:ReadRange\b', "ReadRange"),
        (r'<ui:WriteRange\b', "WriteRange"),
        (r'<ui:ForEachRow\b', "ForEachRow"),
        (r'<ui:BuildDataTable\b', "BuildDataTable"),
        # HTTP
        (r'<ui:HttpClient\b', "HttpClient"),
        (r'<ui:NetHttpRequest\b', "NetHttpRequest"),
        # Extract
        (r'<ui:ForEachFileX?\b', "ForEachFile"),
        (r'<ui:ReadPDF', "ReadPDF"),
    ]

    violations = []
    for pattern, label in banned_patterns:
        matches = re.findall(pattern, content)
        if matches:
            violations.append(f"{label} ({len(matches)}x)")

    if violations:
        result.error(
            f"[lint 74] InitAllApplications.xaml contains non-launch activities: "
            f"{', '.join(violations)}. This workflow should ONLY delegate to "
            f"AppName_Launch.xaml sub-workflows via InvokeWorkflowFile. "
            f"Move UI automation, data extraction, and business logic to the "
            f"appropriate Launch or Process workflow."
        )

    # Also warn if no InvokeWorkflowFile at all (empty/broken)
    if "InvokeWorkflowFile" not in content:
        # Check for scaffold marker (un-inlined body snippet file path)
        marker_match = re.search(
            r'[A-Za-z]:/[^\s<>]+\.xaml\b', content
        )
        if marker_match:
            result.warn(
                f"[lint 74] InitAllApplications.xaml has an un-inlined body snippet "
                f"marker ({os.path.basename(marker_match.group(0))}). "
                f"Run modify_framework.py to wire the Launch workflow invocations."
            )
        else:
            result.warn(
                f"[lint 74] InitAllApplications.xaml has no InvokeWorkflowFile — "
                f"should invoke AppName_Launch.xaml for each application."
            )


@lint_rule(75)
def lint_process_redundant_wrapper(ctx: FileContext, result: ValidationResult):
    """Lint 75: Process.xaml must contain business logic, not delegate to a wrapper.

    Bad pattern: Process.xaml → InvokeWorkflowFile("Performer_Process.xaml")
    with nothing else. This creates a redundant wrapper that:
    - Adds an unnecessary argument-passing layer (UiElement args get lost)
    - Violates REFramework design: Process.xaml IS the process orchestrator
    - Creates folder clutter (Performer/ folder with a single wrapper file)

    Process.xaml should directly invoke action workflows like:
    - WebApp_ExtractData.xaml, WebApp_UpdateRecord.xaml, SHA1Online_GetHash.xaml

    Detection: Process.xaml invokes a workflow with "Process" in its name
    (e.g. Performer_Process, WebApp_Process, Main_Process) — always redundant.
    """
    basename = os.path.basename(ctx.filepath).lower()
    # Strip test prefix for lint test compatibility
    check_name = basename.replace("bad_", "")
    if check_name != "process.xaml":
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    # Find all InvokeWorkflowFile targets
    invocations = re.findall(
        r'WorkflowFileName="([^"]*)"', content
    )

    if not invocations:
        return

    # Check for wrapper pattern: invoking a *_Process.xaml or *Process*.xaml
    process_wrappers = []
    for inv in invocations:
        # Windows-style paths use \ — split on both separators
        inv_basename = inv.replace("\\", "/").split("/")[-1].lower()
        # Match patterns like Performer_Process.xaml, WebApp_Process.xaml,
        # Main_Process.xaml — but not SetTransactionStatus.xaml
        if "process" in inv_basename and inv_basename != "process.xaml":
            process_wrappers.append(inv.replace("\\", "/").split("/")[-1])

    if process_wrappers:
        result.error(
            f"[lint 75] Process.xaml invokes redundant wrapper: "
            f"{', '.join(process_wrappers)}. Process.xaml IS the process "
            f"orchestrator in REFramework — it should directly invoke action "
            f"workflows (e.g. WebApp_ExtractData.xaml, WebApp_UpdateRecord.xaml), "
            f"not delegate to another wrapper. Move the wrapper's contents "
            f"into Process.xaml and delete the wrapper file."
        )


@lint_rule(77, golden_suppressed=True, needs_project_dir=True)
def lint_init_missing_uielement_out(ctx: FileContext, result: ValidationResult,
                                     project_dir: str | None = None):
    """Lint 77: InitAllApplications must output UiElement for each launched app.

    When InitAllApplications invokes *_Launch.xaml with out_ui* arguments,
    InitAllApplications itself must declare matching OutArgument(UiElement)
    so the reference flows back to Main.xaml. Without this, the UiElement
    dies as a local variable inside InitAllApplications and downstream
    workflows (Process, actions) have no browser/app reference.

    Anti-pattern: storing UiElement in Config dictionary instead of typed args.
    """
    basename = os.path.basename(ctx.filepath).lower()
    # Check both filename and x:Class for InitAllApplications
    xclass_match = re.search(r'x:Class="([^"]*)"', ctx.active_content)
    xclass = xclass_match.group(1).lower() if xclass_match else ""
    if "initallapplications" not in basename and "initallapplications" not in xclass:
        return

    content = ctx.active_content

    # Find out_ui* keys in InvokeWorkflowFile argument dictionaries
    # Pattern: Key="out_ui..." Direction="Out"
    out_ui_keys = re.findall(
        r'x:String[^>]*>out_(ui\w+)</x:String>',
        content
    )
    if not out_ui_keys:
        # Also check attribute-style: Key="out_uiWebApp"
        out_ui_keys = re.findall(
            r'Key="out_(ui\w+)"', content
        )
    if not out_ui_keys:
        return

    # Check if InitAllApplications declares matching OutArguments
    # Pattern: <x:Property Name="out_uiWebApp" Type="OutArgument(...)
    declared_out_args = re.findall(
        r'<x:Property\s+[^>]*Name="out_(ui\w+)"[^>]*Type="OutArgument',
        content
    )

    missing = set(out_ui_keys) - set(declared_out_args)
    if missing:
        names = ", ".join(f"out_{n}" for n in sorted(missing))
        result.error(
            f"[lint 77] InitAllApplications invokes Launch with UiElement out args "
            f"({names}) but does NOT declare matching OutArgument(UiElement) "
            f"x:Property declarations. The UiElement dies as a local variable and "
            f"never reaches Main.xaml. Add <x:Property Name=\"out_uiXxx\" "
            f"Type=\"OutArgument(ui:UiElement)\" /> for each launched app, and wire "
            f"them in Main.xaml's invoke of InitAllApplications. See skill-guide.md "
            f"→ UiElement reference chain."
        )


@lint_rule(100)
def lint_process_main_only_variables(ctx: FileContext, result: ValidationResult):
    """Lint 100: Main-scoped variables used in Process.xaml or action workflows.

    in_TransactionNumber lives in Main.xaml and is passed to
    GetTransactionData.xaml and SetTransactionStatus.xaml — it is NEVER
    passed to Process.xaml. The LLM frequently copies log/throw patterns
    from GetTransactionData into Process, carrying the reference along.

    This lint catches the compiled-time error before Studio does.
    Generic lint 67 misses it because:
      - LogMessage bracket expressions with nested quotes break the regex
      - Throw [New ...(...)] is skip-listed as a constructor call
    So we do a targeted string search instead.
    """
    basename = os.path.basename(ctx.filepath).lower()
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))

    # Only applies to Process.xaml and action workflows (Workflows/ subdir).
    # Main.xaml legitimately passes in_TransactionNumber to GTD/STS as an
    # InvokeWorkflowFile argument key. GTD/STS/RTC declare it as an argument.
    FRAMEWORK_EXEMPT = {
        "main.xaml", "gettransactiondata.xaml", "settransactionstatus.xaml",
        "retrycurrenttransaction.xaml", "initallsettings.xaml",
        "killallprocesses.xaml",
    }
    if basename in FRAMEWORK_EXEMPT:
        return

    is_process = basename == "process.xaml" and parent_dir == "Framework"
    is_action_workflow = parent_dir not in ("Framework", "Tests") and basename != "main.xaml"
    if not is_process and not is_action_workflow:
        return

    content = ctx.active_content

    # Check if in_TransactionNumber is declared as argument in this file
    if 'Name="in_TransactionNumber"' in content:
        return  # Declared locally — not our problem

    # Search for usage in any expression context
    if "in_TransactionNumber" in content:
        result.error(
            f"[lint 100] 'in_TransactionNumber' referenced in "
            f"{os.path.basename(ctx.filepath)} but this argument is NOT passed "
            f"to this workflow. in_TransactionNumber exists only in Main.xaml "
            f"scope and is forwarded to GetTransactionData/SetTransactionStatus "
            f"— never to Process.xaml or action workflows. "
            f"Use in_TransactionItem fields instead (e.g., "
            f"in_TransactionItem(\"WIID\").ToString for DataRow dispatchers, "
            f"in_TransactionItem.SpecificContent(\"Key\").ToString for "
            f"QueueItem performers)."
        )
