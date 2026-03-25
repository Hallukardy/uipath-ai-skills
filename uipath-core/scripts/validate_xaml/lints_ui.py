"""UI automation lint rules."""

import os
import re

from ._registry import lint_rule
from ._context import FileContext, ValidationResult
from ._constants import (
    _RE_SCOPE_GUID, _RE_SCOPE_ID, _RE_DISPLAY_NAME,
)


@lint_rule(1)
def lint_scope_guid_mismatch(ctx: FileContext, result: ValidationResult):
    """Lint 1: NApplicationCard ScopeGuid must match child ScopeIdentifier."""
    content = ctx.active_content

    scope_guids = _RE_SCOPE_GUID.findall(content)
    scope_ids = _RE_SCOPE_ID.findall(content)

    if not scope_guids:
        return  # No UI automation, skip

    guid_set = set(scope_guids)
    orphan_ids = [s for s in scope_ids if s not in guid_set]
    if orphan_ids:
        unique_orphans = list(dict.fromkeys(orphan_ids))
        for oid in unique_orphans[:5]:
            result.warn(f"ScopeIdentifier='{oid}' has no matching NApplicationCard ScopeGuid")
    else:
        result.ok(f"ScopeGuid/ScopeIdentifier: {len(scope_guids)} scope(s) matched")


@lint_rule(41, golden_suppressed=True)
def lint_searchsteps_fuzzy_default(ctx: FileContext, result: ValidationResult):
    """Lint 41: Warn when SearchSteps defaults to FuzzySelector instead of Selector.

    SearchSteps="Selector" (strict) should be the default. FuzzySelector should only
    be used when explicitly needed. This catches the common hallucination where the
    model uses FuzzySelector as the primary search strategy.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Count SearchSteps usage
    # FuzzySelector as sole/primary strategy (not in a fallback chain starting with Selector)
    fuzzy_only = re.findall(r'SearchSteps="FuzzySelector(?:,\s*\w+)*"', content)
    # Strict Selector as primary (includes "Selector", "Selector, Image", etc.)
    strict = re.findall(r'SearchSteps="Selector(?:,\s*\w+)*"', content)

    if fuzzy_only and not strict:
        result.warn(
            f"[lint 41] All {len(fuzzy_only)} SearchSteps use FuzzySelector — "
            "SearchSteps=\"Selector\" (strict) should be the default. "
            "Only use FuzzySelector when strict selectors are proven unreliable. "
            "Always populate both FullSelectorArgument and FuzzySelectorArgument, "
            "but route through strict by default."
        )
    elif len(fuzzy_only) > len(strict):
        result.warn(
            f"[lint 41] {len(fuzzy_only)} FuzzySelector vs {len(strict)} Selector SearchSteps — "
            "strict Selector should be the default. Review whether FuzzySelector "
            "is truly needed for each element."
        )


@lint_rule(45, golden_suppressed=True)
def lint_goto_url_inline(ctx: FileContext, result: ValidationResult):
    """Lint 45: NGoToUrl placement rules.

    Rule 3: Navigation uses the GENERIC Browser_NavigateToUrl.xaml — never
    create app-specific NavigateTo workflows (WebApp_NavigateTo.xaml etc.).
    The caller passes the full URL from Config.

    Rule 9: Navigation is always a separate workflow from page action.
    NGoToUrl is never inlined in action workflows (ComputeHash, CreateTask).

    Launch workflows: NApplicationCard OpenMode="Always" already handles
    initial navigation — NGoToUrl is redundant.
    """
    basename = os.path.basename(ctx.filepath).lower()

    # Skip the ONE allowed navigation utility
    if "browser_" in basename:
        return

    # Skip framework files
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))
    if parent_dir in ("Framework", "Tests"):
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    # App-specific NavigateTo workflow — should not exist for BROWSER apps (Rule A-6).
    # Desktop tab-navigation (Rule 14) IS a valid pattern — exempt if desktop content detected.
    if "navigate" in basename:
        is_desktop_nav = (
            "WindowsForms10" in content
            or "&lt;wnd " in content
            or "<wnd " in content
            or "SysTabControl" in content
        )
        if not is_desktop_nav:
            result.error(
                f"[lint 45] App-specific navigation workflow '{os.path.basename(ctx.filepath)}' "
                f"should not exist. Rule A-6: Use the generic Browser_NavigateToUrl.xaml from "
                f"Utils/ — the caller passes the full URL from Config. Never clone navigation "
                f"per app. Delete this file and invoke Browser_NavigateToUrl.xaml instead."
            )
        return

    if "NGoToUrl" not in content:
        return

    # Launch workflows: NGoToUrl is redundant because OpenMode="Always" handles it
    if "launch" in basename:
        result.warn(
            f"[lint 45] NGoToUrl found in Launch workflow '{os.path.basename(ctx.filepath)}'. "
            f"Launch workflows use NApplicationCard with OpenMode='Always' and TargetApp Url= "
            f"which already opens the browser at the target URL. NGoToUrl is redundant here — "
            f"remove it and let NApplicationCard handle the initial navigation."
        )
        return

    result.error(
        f"[lint 45] NGoToUrl found in non-navigation workflow '{os.path.basename(ctx.filepath)}'. "
        f"Rule 9: Navigation must be a separate workflow from page action. "
        f"Use the generic Browser_NavigateToUrl.xaml (args: in_strUrl, io_uiBrowser) "
        f"and invoke it from the caller BEFORE invoking this action workflow."
    )


@lint_rule(46, golden_suppressed=True)
def lint_generic_uibrowser_variable(ctx: FileContext, result: ValidationResult):
    """Lint 46: Orchestrator files must use app-specific UiElement names.

    Rule 11: One browser instance per web app. Main.xaml uses variables
    like uiWebApp, uiSHA1Online. Process.xaml and action workflows use
    io_uiWebApp (InOut). A generic 'io_uiBrowser' or 'uiBrowser' without
    an app suffix means the model didn't differentiate app instances.
    Sub-workflows (Browser_NavigateToUrl, App_Close) keep generic names
    as their argument (for reusability) — the caller maps app-specific → generic.
    """
    basename = os.path.basename(ctx.filepath)
    basename_lower = basename.lower()

    # Only check orchestrator files
    ORCHESTRATOR_FILES = {
        "main.xaml", "process.xaml",
        "initallapplications.xaml", "closeallapplications.xaml",
    }
    if basename_lower not in ORCHESTRATOR_FILES:
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    # Check for Variable or Property declarations with generic uiBrowser names (no app suffix)
    generic_patterns = [
        r'<Variable\b[^>]*Name="(io_uiBrowser)"[^>]*/?>',
        r'<Variable\b[^>]*Name="(uiBrowser)"[^>]*/?>',
        r'<x:Property\b[^>]*Name="(io_uiBrowser)"[^>]*/?>',
    ]
    generic_found = False
    for pattern in generic_patterns:
        if re.search(pattern, content):
            generic_found = True
            break

    if generic_found:
        result.warn(
            f"[lint 46] Generic 'io_uiBrowser'/'uiBrowser' in orchestrator file '{basename}'. "
            f"Rule 11: Each web app needs its own instance. Use app-specific names: "
            f"Main variables: uiWebApp, uiSHA1Online. Process/action args: io_uiWebApp (InOut). "
            f"Launch: out_uiWebApp (Out). CloseAll: in_uiWebApp (In). "
            f"Sub-workflows (Browser_NavigateToUrl, App_Close) keep generic args for reusability."
        )


@lint_rule(47, golden_suppressed=True)
def lint_app_open_outside_launch(ctx: FileContext, result: ValidationResult):
    """Lint 47: Apps should only be opened in dedicated Launch workflows.

    Rule 4: In REFramework, every app with UI interaction must be opened in
    InitAllApplications via a dedicated AppName_Launch.xaml workflow.
    Process.xaml and action workflows attach to already-open apps using
    OpenMode="Never" + AttachMode="SingleWindow".

    NApplicationCard with OpenMode != "Never" in non-launch files means the
    workflow is trying to open an app itself instead of relying on Init.
    """
    basename = os.path.basename(ctx.filepath)
    basename_lower = basename.lower()

    # These files are ALLOWED to open apps
    # Launch/Init workflows open apps by definition
    # Main.xaml and *_Main.xaml are entry points for sequence projects
    is_main = basename_lower == "main.xaml" or basename_lower.endswith("_main.xaml")
    if "launch" in basename_lower or "init" in basename_lower or is_main:
        return

    # Skip framework/test files
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))
    if parent_dir in ("Framework", "Tests"):
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    if "NApplicationCard" not in content:
        return

    # Find OpenMode values that aren't "Never"
    open_modes = re.findall(
        r'<uix:NApplicationCard\b[^>]*OpenMode="([^"]*)"', content
    )

    non_never = [m for m in open_modes if m != "Never"]
    if non_never:
        result.warn(
            f"[lint 47] NApplicationCard in '{basename}' has OpenMode=\"{non_never[0]}\" — "
            f"app is being opened in an action workflow instead of a dedicated Launch workflow. "
            f"Rule 4: In REFramework, open all apps in InitAllApplications via "
            f"AppName_Launch.xaml (OpenMode=\"Always\"/\"IfNotOpen\"). Action workflows use "
            f"OpenMode=\"Never\" + AttachMode=\"SingleWindow\" to attach to the already-open app."
        )


@lint_rule(105)
def lint_tab_click_no_sync(ctx: FileContext, result: ValidationResult):
    """Lint 105: Tab/navigation NClick immediately followed by NTypeInto without sync.

    WinForms tab switching may have rendering latency. If NClick targets a tab
    control (SysTabControl, TabItem) and the very next activity is NTypeInto,
    add a Delay or NCheckAppState between them.
    """
    content = ctx.active_content
    tab_patterns = [r"SysTabControl", r"TabItem", r"aaname='[^']*[Tt]ab[^']*'"]
    tab_regex = "|".join(tab_patterns)
    pattern = (
        r'<uix:NClick\b[^>]*(?:FullSelectorArgument|Selector)="[^"]*'
        r'(?:' + tab_regex + r')[^"]*"[^>]*/?\s*>'
        r'\s*'
        r'<uix:NTypeInto\b'
    )
    hits = re.findall(pattern, content, re.DOTALL)
    if hits:
        result.warn(
            f"[lint 105] NClick on tab control immediately followed by NTypeInto "
            f"({len(hits)}x) — WinForms tab switching may have rendering latency. "
            f"Add NCheckAppState between the tab click and the first TypeInto "
            f"to ensure the target tab is fully rendered."
        )

    # ---- Lint 106: DebuggerApi on desktop NApplicationCard ----
    # Desktop = has TargetApp.FilePath child element or FilePath= attribute
    nac_blocks = re.findall(
        r'<uix:NApplicationCard\b[^>]*>(.*?)</uix:NApplicationCard>',
        content, re.DOTALL
    )
    nac_attrs_blocks = re.findall(
        r'<uix:NApplicationCard\b([^>]*)>', content
    )
    for i_nac, nac_attr in enumerate(nac_attrs_blocks):
        nac_body = nac_blocks[i_nac] if i_nac < len(nac_blocks) else ""
        # Desktop = FilePath attribute with a value on TargetApp, or FilePath child
        # with actual content (not empty <InArgument />)
        has_filepath_attr = bool(re.search(r'FilePath="[^"]+\S+[^"]*"', nac_attr))
        has_filepath_child = bool(re.search(
            r'<uix:TargetApp[^>]*\sFilePath="[^"]+\S+[^"]*"', nac_body
        ))
        # Empty FilePath child (<TargetApp.FilePath><InArgument .../></TargetApp.FilePath>)
        # is a generic utility pattern — NOT desktop
        has_browser = 'BrowserType' in nac_attr or 'Url=' in nac_attr or 'BrowserType' in nac_body
        is_desktop = (has_filepath_attr or has_filepath_child) and not has_browser
        if not is_desktop:
            continue
        if 'InteractionMode="DebuggerApi"' in nac_attr:
            result.error(
                f"[lint 106] NApplicationCard with desktop FilePath uses "
                f"InteractionMode=\"DebuggerApi\" — DebuggerApi is browser-only. "
                f"Use Simulate or HardwareEvents for desktop apps."
            )
        if 'IsIncognito="True"' in nac_attr:
            result.error(
                f"[lint 107] NApplicationCard with desktop FilePath uses "
                f"IsIncognito=\"True\" — IsIncognito is a browser concept. "
                f"Remove IsIncognito from desktop NApplicationCards."
            )

    # ---- Lint 108: Empty TryCatch Catch block ----
    catch_sequences = re.findall(
        r'<Sequence\s+DisplayName="Catch"[^>]*>(.*?)</Sequence>',
        content, re.DOTALL
    )
    for catch_seq in catch_sequences:
        stripped = catch_seq.strip()
        # Check if the catch sequence has only ViewState or is truly empty
        without_viewstate = re.sub(
            r'<sap:WorkflowViewStateService\.ViewState>.*?</sap:WorkflowViewStateService\.ViewState>',
            '', stripped, flags=re.DOTALL
        ).strip()
        if not without_viewstate:
            result.error(
                f"[lint 108] TryCatch has empty Catch block — exceptions will be "
                f"silently swallowed. Add error logging, cleanup, or Rethrow."
            )



@lint_rule(111)
def lint_ncheckstate_empty_ifnotexists(ctx: FileContext, result: ValidationResult):
    """Lint 111: NCheckState with empty IfNotExists in navigation/switch-to workflows.

    When NCheckState verifies a tab/screen loaded after navigation, an empty IfNotExists
    means the workflow silently continues even if the target never appeared — causing
    cascading failures downstream. Navigation workflows should Throw a TimeoutException.

    Only checks workflows with 'navigate' or 'switch' in the filename. Other workflows
    have legitimate one-sided patterns (Pick triggers, optional element checks).
    """
    basename = os.path.basename(ctx.filepath).lower()
    if "navigate" not in basename:
        return

    content = ctx.active_content
    # Match IfNotExists blocks whose inner Sequence has only ViewState (no real activities)
    pattern = (
        r'<uix:NCheckState\.IfNotExists>\s*'
        r'<Sequence\b[^>]*DisplayName="Target does not appear"[^>]*>\s*'
        r'(?:<sap:WorkflowViewStateService\.ViewState>.*?</sap:WorkflowViewStateService\.ViewState>\s*)?'
        r'</Sequence>\s*'
        r'</uix:NCheckState\.IfNotExists>'
    )
    hits = re.findall(pattern, content, re.DOTALL)
    if hits:
        result.warn(
            f"[lint 111] NCheckState has {len(hits)} empty IfNotExists handler(s) — "
            f"if the target element never appears, the workflow continues silently. "
            f"Add a Throw (TimeoutException) in the IfNotExists branch to fail fast. "
            f"Use if_not_exists_children in the spec to add a throw activity."
        )


@lint_rule(112)
def lint_nclick_on_checkbox(ctx: FileContext, result: ValidationResult):
    """Lint 112: NClick targeting a checkbox element — should use NCheck instead.

    NClick toggles a checkbox (checked→unchecked or vice versa), which is not
    idempotent. Use NCheck with Action="Check" or "Uncheck" for deterministic behavior.
    """
    content = ctx.active_content
    # Detect NClick whose selector targets a checkbox-like element:
    # - WinForms: cls='WindowsForms10.BUTTON.*' with aaname containing common checkbox terms
    # - Web: ElementType="CheckBox" or type='checkbox'
    nclick_blocks = re.finditer(
        r'<uix:NClick\b[^>]*DisplayName="([^"]*)"[^>]*/?\s*>.*?</uix:NClick>',
        content, re.DOTALL
    )
    checkbox_indicators = [
        r"ElementType=['\"]CheckBox['\"]",
        r"type='checkbox'",
        r"type=&apos;checkbox&apos;",
    ]
    # Also check display name for checkbox keywords
    checkbox_name_words = {"check", "checkbox", "uncheck", "toggle"}
    for m in nclick_blocks:
        block = m.group(0)
        display_name = m.group(1).lower()
        name_match = any(w in display_name for w in checkbox_name_words)
        selector_match = any(re.search(pat, block, re.IGNORECASE) for pat in checkbox_indicators)
        if name_match or selector_match:
            result.warn(
                f'[lint 112] NClick targets a checkbox element '
                f'(DisplayName="{m.group(1)}") — NClick toggles the state and is '
                f'not idempotent. Use NCheck with Action="Check" or "Uncheck" instead.'
            )
