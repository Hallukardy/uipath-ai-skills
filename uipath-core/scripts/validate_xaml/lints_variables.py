"""Variable and argument lint rules."""

import os
import re
from collections import Counter

from ._registry import lint_rule
from ._context import FileContext, ValidationResult
from ._constants import _RE_VARIABLE_DECL, _RE_XPROPERTY_NAME


# Known variable type prefixes (camelCase or underscore variants)
_VAR_PREFIXES = (
    "str", "secstr", "int", "bool", "dbl", "dec", "dtm", "obj", "gv_", "ss_",
    "dt_", "dr_", "arr_", "list_", "dict_", "jo_", "ja_", "mm_", "qi_",
    "ui",  # UiElement variables (e.g. uiDesktopApp, uiACMESystem1, uiBrowser)
    # Argument-backed local variables keep their direction prefix
    "in_", "out_", "io_",
)

# Known argument direction prefixes
_ARG_PREFIXES = ("in_", "out_", "io_")


@lint_rule(5)
def lint_duplicate_variables(ctx: FileContext, result: ValidationResult):
    """Lint 5: Variables with the same name in the same scope."""
    content = ctx.active_content

    # Find all variable declarations: <Variable x:TypeArguments="..." Name="..." />
    var_names = _RE_VARIABLE_DECL.findall(content)

    if not var_names:
        return

    counts = Counter(var_names)
    dupes = {k: v for k, v in counts.items() if v > 1}
    if dupes:
        for name, count in dupes.items():
            result.warn(f"Variable '{name}' declared {count} times — may shadow or conflict")
    else:
        result.ok(f"{len(var_names)} variables, no duplicates")


@lint_rule(16, golden_suppressed=True)
def lint_naming_conventions(ctx: FileContext, result: ValidationResult):
    """Lint 16: Variable and argument naming conventions."""
    try:
        content = ctx.active_content
    except Exception:
        return

    # Check variable names
    var_names = _RE_VARIABLE_DECL.findall(content)
    bad_vars = []
    # Skip framework/loop/delegate variables and REFramework standard names
    skip_vars = {
        "item", "row", "currentItem", "element", "mail", "file", "index",
        # REFramework standard variables (do not rename)
        "ShouldStop", "TransactionItem", "SystemException", "BusinessException",
        "TransactionNumber", "TransactionID", "TransactionField1", "TransactionField2",
        "RetryNumber", "MaxRetryNumber", "ConsecutiveSystemExceptions",
        "Config", "AssetValue", "QueueRetry", "ScreenshotPath",
        "Screenshot", "ScreenshotFileInfo", "uiBrowser",
    }
    for name in var_names:
        if name in skip_vars:
            continue
        if not any(name.startswith(p) for p in _VAR_PREFIXES):
            bad_vars.append(name)
    if bad_vars:
        result.warn(
            f"{len(bad_vars)} variable(s) missing type prefix "
            f"(expected str/int/bool/dt_/list_/dict_/...): "
            f"{', '.join(bad_vars[:5])}"
            + (f" +{len(bad_vars)-5} more" if len(bad_vars) > 5 else "")
        )

    # Check argument direction prefixes
    arg_names = _RE_XPROPERTY_NAME.findall(content)
    bad_args = []
    for name in arg_names:
        if not any(name.startswith(p) for p in _ARG_PREFIXES):
            bad_args.append(name)
    if bad_args:
        result.warn(
            f"{len(bad_args)} argument(s) missing direction prefix "
            f"(expected in_/out_/io_): "
            f"{', '.join(bad_args[:5])}"
            + (f" +{len(bad_args)-5} more" if len(bad_args) > 5 else "")
        )


VALID_ELEMENT_TYPES = {
    "Button", "CheckBox", "Document", "DropDown", "Group",
    "Image", "InputBox", "InputBoxPassword", "List", "ListItem",
    "Menu", "MenuItem", "None", "ProgressBar", "RadioButton", "Slider",
    "Tab", "Table", "Text", "ToolBar", "ToolTip", "Tree", "TreeItem", "Window",
}

ELEMENT_TYPE_FIXES = {
    "DataGrid": "Table",
    "Datagrid": "Table",
    "datagrid": "Table",
    "Grid": "Table",
    "TextBox": "InputBox",
    "Textbox": "InputBox",
    "InputBoxText": "InputBox",
    "Edit": "InputBox",
    "Password": "InputBoxPassword",
    "Select": "DropDown",
    "ComboBox": "DropDown",
    "Combobox": "DropDown",
    "Combo": "DropDown",
    "Link": "Text",
    "Anchor": "Text",
    "Hyperlink": "Text",
    "Dialog": "Window",
    "Label": "Text",
    "Span": "Text",
}


@lint_rule(28)
def lint_invalid_element_type(ctx: FileContext, result: ValidationResult):
    """Lint 28: Detect invalid UIElementType enum values in TargetAnchorable.

    Studio crashes with 'X is not a valid value for UIElementType' if an
    invalid enum value is used. Common hallucination: DataGrid → use Table.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    for match in re.finditer(r'ElementType="([^"]+)"', content):
        value = match.group(1)
        if value not in VALID_ELEMENT_TYPES:
            fix = ELEMENT_TYPE_FIXES.get(value, "Table or Text")
            result.error(
                f"[lint 28] Invalid ElementType=\"{value}\" — Studio will crash with "
                f"'{value} is not a valid value for UIElementType'. "
                f"Use ElementType=\"{fix}\" instead. "
                f"Valid values: Button, CheckBox, Document, DropDown, "
                f"InputBox, InputBoxPassword, List, Table, Text, Window, ..."
            )


@lint_rule(81)
def lint_main_invoke_undeclared_variables(ctx: FileContext, result: ValidationResult):
    """Lint 81: InvokeWorkflowFile Out/InOut bindings in Main.xaml must reference declared variables.

    Lint 67 deliberately skips Main.xaml (complex state machine scope) but that creates
    a blind spot: Claude can write [uiWebApp] in an OutArgument binding without ever declaring
    <Variable Name="uiWebApp">, producing BC30451 at Studio compile time.

    This targeted rule checks ONLY Out/InOut argument values in InvokeWorkflowFile blocks
    (the crash-prone pattern) without the false-positive risk of scanning all expressions
    in the state machine.

    Fix: run `python3 scripts/modify_framework.py wire-uielement <project> <AppName>`
    for each UI app. This adds both the <Variable> declaration AND the invoke binding.
    """
    basename_lower = os.path.basename(ctx.filepath).lower()
    content = ctx.active_content
    # Applies to Main.xaml (any name) — detect by filename OR x:Class="...Main"
    is_main = (basename_lower == "main.xaml"
               or re.search(r'x:Class="[^"]*\bMain"', content) is not None)
    if not is_main:
        return

    # All declared variable names anywhere in the file (any scope)
    declared_vars = set(re.findall(r'<Variable\b[^>]*\bName="([^"]*)"', content))
    declared_args = set(_RE_XPROPERTY_NAME.findall(content))
    all_declared = declared_vars | declared_args

    # Find simple [identifier] values on Out/InOut argument tags only.
    # Use re.DOTALL + strip whitespace to handle multiline/padded content:
    #   <OutArgument ...>[uiWebApp]</OutArgument>        — single line
    #   <OutArgument ...>\n    [uiWebApp]\n</OutArgument> — multiline (Studio export)
    raw_blocks = re.findall(
        r'<(OutArgument|InOutArgument)\b[^>]*>(.*?)</(?:OutArgument|InOutArgument)>',
        content, re.DOTALL
    )
    out_inout_values = []
    for _tag, inner in raw_blocks:
        inner = inner.strip()
        m = re.fullmatch(r'\[(\w+)\]', inner)
        if m:
            out_inout_values.append(m.group(1))

    undeclared = sorted(set(out_inout_values) - all_declared)
    if undeclared:
        apps = [v for v in undeclared if v.startswith("ui")]
        fix_hint = ""
        if apps:
            # Derive AppName from variable like uiWebApp → WebApp
            app_names = [v[2:] for v in apps]  # strip leading 'ui'
            fix_hint = (
                f" Fix: python3 scripts/modify_framework.py wire-uielement <project> "
                + " && python3 scripts/modify_framework.py wire-uielement <project> ".join(app_names)
            )
        result.error(
            f"[lint 81] {len(undeclared)} variable(s) bound in InvokeWorkflowFile Out/InOut "
            f"arguments but never declared in Main.xaml: {', '.join(undeclared)}. "
            f"Studio raises BC30451 at compile time.{fix_hint}"
        )


@lint_rule(82)
def lint_bare_config_in_non_main(ctx: FileContext, result: ValidationResult):
    """Lint 82: Bare Config(...) references are only valid in Main.xaml.

    In non-Main workflows (Process.xaml, action workflows, dispatchers, etc.)
    the Config dictionary is received as the argument 'in_Config', NOT as a
    bare variable named 'Config'. Writing [Config("Key")] in Process.xaml
    produces BC30451: 'Config' is not declared at Studio compile time.

    Correct pattern in non-Main files: [in_Config("Key").ToString]
    Correct pattern in Main.xaml: [Config("Key").ToString]
    """
    basename_lower = os.path.basename(ctx.filepath).lower()
    content = ctx.active_content

    # Main.xaml has Config as a declared variable — skip it
    is_main = (basename_lower == "main.xaml"
               or re.search(r'x:Class="[^"]*\bMain"', content) is not None)
    if is_main:
        return

    # Also skip the framework files that ship with REFramework and legitimately
    # use Config — they declare it as a local variable (InitAllSettings produces it)
    FRAMEWORK_WITH_CONFIG = {
        "initsettings.xaml", "initallsettings.xaml",
        "gettransactiondata.xaml", "settransactionstatus.xaml",
    }
    if basename_lower in FRAMEWORK_WITH_CONFIG:
        return

    # Check whether this file declares Config as a variable or argument
    has_config_declared = bool(
        re.search(r'<Variable\b[^>]*\bName="Config"', content)
        or re.search(r'<x:Property\b[^>]*\bName="Config"', content)
    )
    if has_config_declared:
        return

    # Find bare Config("...") bracket expressions — but NOT in_Config(
    # Look inside bracket expressions: [Config( but not [in_Config(
    # Also catches attribute-encoded form: &quot; instead of "
    all_bracket_exprs = re.findall(r'="\[([^\]"]*)\]"', content)
    # Also text nodes
    all_bracket_exprs += re.findall(r'>\[([^\]<]*)\]</', content)

    bare_config_hits = [
        e for e in all_bracket_exprs
        if re.search(r'(?<![_\w])Config(?!\w)', e)
        and not re.search(r'in_Config(?!\w)', e)
        and not re.search(r'io_Config(?!\w)', e)
    ]

    if bare_config_hits:
        result.error(
            f"[lint 82] {len(bare_config_hits)} bare 'Config' reference(s) found in "
            f"'{os.path.basename(ctx.filepath)}'. Outside Main.xaml, the Config dictionary "
            f"is received as argument 'in_Config' — use in_Config(\"Key\").ToString "
            f"or pass in_Config (not Config) to InvokeWorkflowFile bindings. "
            f"Bare 'Config' causes BC30451: 'Config' is not declared."
        )


@lint_rule(67)
def lint_undeclared_variables(ctx: FileContext, result: ValidationResult):
    """Lint 67: Variables used in expressions but never declared.

    The model frequently writes [strSomething] or [intCount] in activity
    properties but forgets to add the <Variable> declaration. Studio shows
    a compile error or the workflow silently fails at runtime.

    Checks all simple bracket references =[identifier] against:
      - <Variable ... Name="x"> declarations
      - <x:Property Name="x"> argument declarations
      - <DelegateInArgument ... Name="x"> (ForEach, Catch)
    Also extracts identifiers from complex VB.NET expressions that match
    the UiPath naming pattern (type-prefixed camelCase).
    """
    content = ctx.active_content
    if not content:
        return

    # Skip complex framework state machine files — they have their own variable ecosystem
    # But DO check InitAllApplications, CloseAllApplications, Process — the LLM edits these
    # GetTransactionData is also edited (dispatcher load logic) — must check it
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))
    basename_lower = os.path.basename(ctx.filepath).lower()
    if parent_dir == "Framework" and basename_lower in (
        "main.xaml", "settransactionstatus.xaml",
        "initallsettings.xaml", "killallprocesses.xaml",
    ):
        return

    # 1. Collect all declared names
    declared_vars = set(_RE_VARIABLE_DECL.findall(content))
    declared_args = set(_RE_XPROPERTY_NAME.findall(content))
    declared_delegates = set(re.findall(
        r'<DelegateInArgument\b[^>]*Name="([^"]*)"', content
    ))
    all_declared = declared_vars | declared_args | declared_delegates

    # 2. Find all bracket expressions in attribute values: ="[...]"
    # AND in text nodes: >[...]</ (used by Assign.To, Assign.Value)
    bracket_exprs = re.findall(r'="(\[[^\]]*\])"', content)
    bracket_exprs += re.findall(r'>(\[[^\]]+\])</', content)

    # Known non-variable patterns to skip
    SKIP_PREFIXES = (
        "UiPath.", "System.", "Microsoft.", "Newtonsoft.",  # Enum/type refs
        "&quot;",  # String literals
        "new ",    # Constructor calls
        "New ",
    )
    VB_KEYWORDS = {
        "Nothing", "True", "False", "0", "1", "2", "3", "4", "5",
        "6", "7", "8", "9", "x:Null",
    }

    referenced_vars = set()
    for expr in bracket_exprs:
        inner = expr[1:-1]  # Strip [ ]

        # Skip non-variable expressions
        if any(inner.startswith(p) for p in SKIP_PREFIXES):
            continue
        if inner in VB_KEYWORDS:
            continue

        # Simple reference: single identifier
        if re.fullmatch(r'\w+', inner):
            referenced_vars.add(inner)
        elif re.fullmatch(r'[\w.]+', inner):
            # Dotted identifier like UiPath.Something.Enum — skip (enum/type)
            continue
        else:
            # Complex expression: extract identifiers matching UiPath naming
            # Look for type-prefixed variables: str*, int*, bool*, dt_*, list_*, dict_*,
            # io_*, in_*, out_*, secstr*, ui*, qi_*, mm_*
            complex_vars = re.findall(
                r'\b((?:str|int|bool|dt_|list_|dict_|io_|in_|out_|secstr|ui|qi_|mm_)\w+)\b',
                inner
            )
            referenced_vars.update(complex_vars)

    # 3. Find undeclared
    undeclared = sorted(referenced_vars - all_declared)

    if undeclared:
        # Special hint for UiElement naming confusion in InitAllApplications
        ui_hints = []
        if "initallapplications" in os.path.basename(ctx.filepath).lower():
            for v in undeclared:
                if v.startswith("ui") and not v.startswith(("uiPath", "uipath")):
                    ui_hints.append(
                        f"'{v}' looks like Main's variable — inside InitAllApplications, "
                        f"use the argument name 'out_{v}' instead"
                    )
        extra = ""
        if ui_hints:
            extra = " HINT: " + "; ".join(ui_hints) + "."
        result.error(
            f"[lint 67] {len(undeclared)} variable(s) used but never declared: "
            f"{', '.join(undeclared[:8])}. "
            f"Add <Variable x:TypeArguments=\"...\" Name=\"...\"> for each, or "
            f"<x:Property Name=\"...\" Type=\"InArgument(...)\"> if they are arguments. "
            f"Undeclared variables cause Studio compile errors (BC30451)."
            f"{extra}"
        )


@lint_rule(113)
def lint_assign_operation_type_mismatch(ctx: FileContext, result: ValidationResult):
    """Lint 113: AssignOperation.To type doesn't match declared variable type.

    MultipleAssign emits <OutArgument x:TypeArguments="TYPE">[varName]</OutArgument>
    for each assignment's .To element. If the TypeArguments doesn't match the
    declared variable type, Studio raises BC30512 (Option Strict On disallows
    implicit conversions).
    """
    content = ctx.active_content

    # Build var_name → declared_type map from Variable declarations
    var_types = {}
    for m in re.finditer(
        r'<Variable\s+x:TypeArguments="([^"]*)"\s+Name="([^"]*)"', content
    ):
        var_types[m.group(2)] = m.group(1)

    # Also include argument types from x:Members
    for m in re.finditer(
        r'<x:Property\s+Name="([^"]*)"\s+Type="(?:In|Out|InOut)Argument\(([^)]*)\)"',
        content,
    ):
        var_types[m.group(1)] = m.group(2)

    if not var_types:
        return

    # Find AssignOperation.To blocks
    for m in re.finditer(
        r'<ui:AssignOperation\.To>\s*'
        r'<OutArgument\s+x:TypeArguments="([^"]*)"\s*>\[([^\]]*)\]</OutArgument>',
        content,
    ):
        assign_type = m.group(1)
        var_name = m.group(2)
        declared_type = var_types.get(var_name)
        if declared_type and declared_type != assign_type:
            result.error(
                f"[lint 113] AssignOperation for '{var_name}' uses "
                f"x:TypeArguments=\"{assign_type}\" but variable is declared as "
                f"\"{declared_type}\". This causes BC30512 (Option Strict On "
                f"disallows implicit conversions). Fix: use the correct type "
                f"in the assignment."
            )
