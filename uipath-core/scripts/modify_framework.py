#!/usr/bin/env python3
"""
UiPath Framework File Modifier

Structured operations on scaffolded REFramework files. Replaces hand-editing
XAML with deterministic insertions at known anchor points.

Commands:
  insert-invoke <file> <xaml_snippet>
    Insert an InvokeWorkflowFile activity into a framework Sequence.
    Inserts before </Sequence> (after existing LogMessage/activities).
    Use for: InitAllApplications, CloseAllApplications, Process.xaml

  replace-marker <file> <marker_name> <xaml_snippet>
    Replace a SCAFFOLD.<marker> Comment element with XAML content.
    Markers: DISPATCHER_LOAD_DATA, DISPATCHER_GET_ITEM, PROCESS_BODY

  add-variables <file> <name:type> [<name:type> ...]
    Add local variables to a framework file's Sequence.Variables block.
    Creates the block if it doesn't exist yet. Skips already-declared vars.
    Use for: Process.xaml, GetTransactionData.xaml (local processing vars)

  list-markers <file>
    Show all SCAFFOLD.* markers in a file.

Usage:
  python3 modify_framework.py insert-invoke Framework/InitAllApplications.xaml '<ui:InvokeWorkflowFile ...>'
  python3 modify_framework.py replace-marker Framework/Process.xaml PROCESS_BODY '<ui:InvokeWorkflowFile ...>'
  python3 modify_framework.py add-variables Framework/Process.xaml strWIID:String strHash:String dtItems:DataTable
  python3 modify_framework.py list-markers Framework/Process.xaml

Short-form types for add-variables (auto-normalized to xmlns-prefixed forms):
  String, Int32, Int64, Boolean, Object, Double, Decimal, SecureString,
  UiElement, QueueItem, DataTable, DataRow, MailMessage, Array_String,
  Dictionary, Exception, TimeSpan, DateTime
  Already-prefixed types (e.g. sd:DataTable, snm:MailMessage) also accepted.

All operations preserve XAML formatting (indentation, line endings).
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure scripts/ is on sys.path so we can import utils
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from _mf_types import VAR_TYPE_MAP, _normalize_var_type, _ALL_XMLNS_PREFIXES
from _mf_snippet_checks import _SNIPPET_CHECKS, validate_snippet, _warn_nested_retryscope


# Match SCAFFOLD.* markers — handles both self-closing and multi-attribute Comments.
# Supports attributes in any order (DisplayName may not be first).
MARKER_PATTERN = re.compile(
    r'[ \t]*<ui:Comment\s+[^>]*?DisplayName="SCAFFOLD\.([A-Z_]+)[^"]*"[^>]*/>\s*\r?\n?',
    re.DOTALL
)


def _renumber_idrefs(target_content: str, snippet: str) -> str:
    """Renumber IdRefs in a snippet to avoid collisions with the target file.

    Scans the target for existing IdRefs (e.g., LogMessage_1, Sequence_3),
    finds the max ordinal per activity type, then renumbers the snippet's
    IdRefs starting from max+1 for each type.
    """
    idref_pattern = re.compile(r'IdRef="([A-Za-z_]+?)_(\d+)"')

    # Build max-ordinal map from target file
    max_ordinals: dict[str, int] = {}
    for m in idref_pattern.finditer(target_content):
        activity_type = m.group(1)
        ordinal = int(m.group(2))
        if activity_type not in max_ordinals or ordinal > max_ordinals[activity_type]:
            max_ordinals[activity_type] = ordinal

    # Collect snippet IdRefs (preserve order of first appearance for stable renumbering)
    snippet_refs: list[tuple[str, int]] = []
    seen: set[str] = set()
    for m in idref_pattern.finditer(snippet):
        full_ref = m.group(0)
        if full_ref not in seen:
            seen.add(full_ref)
            snippet_refs.append((m.group(1), int(m.group(2))))

    if not snippet_refs:
        return snippet

    # Build renumbering map: old "Type_N" -> new "Type_M"
    rename_map: dict[str, str] = {}
    next_ordinal: dict[str, int] = {}
    for activity_type, old_ord in snippet_refs:
        old_key = f"{activity_type}_{old_ord}"
        if old_key in rename_map:
            continue
        if activity_type not in next_ordinal:
            next_ordinal[activity_type] = max_ordinals.get(activity_type, 0) + 1
        new_ord = next_ordinal[activity_type]
        next_ordinal[activity_type] = new_ord + 1
        rename_map[old_key] = f"{activity_type}_{new_ord}"

    if not rename_map:
        return snippet

    # Apply renames (longest-first to avoid partial replacements)
    result = snippet
    for old_ref, new_ref in sorted(rename_map.items(), key=lambda x: -len(x[0])):
        result = result.replace(f'IdRef="{old_ref}"', f'IdRef="{new_ref}"')

    renamed_count = len(rename_map)
    print(f"  IdRef renumber: {renamed_count} ref(s) renumbered to avoid collision")
    return result


def detect_indent(content: str) -> str:
    """Detect indentation for child activities by looking at existing siblings.

    Tries multiple reference points in priority order to be resilient to
    template changes:
      1. Existing LogMessage activity (always present in framework files)
      2. Any ui:* activity child element
      3. Fallback: </Sequence> indent + 2 spaces
    """
    # Primary: use existing LogMessage activity as indent reference
    match = re.search(r'^([ \t]*)<ui:LogMessage', content, re.MULTILINE)
    if match:
        return match.group(1)
    # Secondary: any UiPath activity child
    match = re.search(r'^([ \t]*)<ui:\w+\s', content, re.MULTILINE)
    if match:
        return match.group(1)
    # Tertiary: indent from </Sequence> + 2
    match = re.search(r'^([ \t]*)</Sequence>', content, re.MULTILINE)
    if match:
        return match.group(1) + "  "
    return "    "


def detect_line_ending(content: str) -> str:
    """Detect \\r\\n vs \\n."""
    return "\r\n" if "\r\n" in content else "\n"


def cmd_insert_invoke(filepath: str, xaml_snippet: str) -> bool:
    """Insert XAML before </Sequence> in a framework file."""
    # ── Reject hallucinated snippets ──
    snippet_errors = validate_snippet(xaml_snippet)
    if snippet_errors:
        print("ERROR: XAML snippet contains hallucinated patterns:", file=sys.stderr)
        for e in snippet_errors:
            print(f"  {e}", file=sys.stderr)
        print("\n⛔ The snippet passed to insert-invoke MUST come from generator output "
              "(gen_*() or generate_workflow.py). Do NOT hand-write XAML.", file=sys.stderr)
        return False

    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        return False

    # Find the LAST </Sequence> (the main body)
    close_seq = content.rfind("</Sequence>")
    if close_seq == -1:
        print(f"ERROR: No </Sequence> found in {filepath}", file=sys.stderr)
        return False

    # Find the start of the line containing </Sequence>
    line_start = content.rfind("\n", 0, close_seq) + 1

    le = detect_line_ending(content)
    child_indent = detect_indent(content)

    # Renumber IdRefs in the snippet to avoid collisions
    xaml_snippet = _renumber_idrefs(content, xaml_snippet)
    _warn_nested_retryscope(xaml_snippet)

    # Indent the snippet
    snippet_lines = xaml_snippet.strip().split("\n")
    indented = le.join(child_indent + line.strip() for line in snippet_lines)

    # Insert before the </Sequence> line (preserving its indentation)
    insertion = indented + le
    new_content = content[:line_start] + insertion + content[line_start:]

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(new_content)

    print(f"OK: Inserted {len(snippet_lines)} lines before </Sequence> in {filepath}")
    return True


def cmd_replace_marker(filepath: str, marker_name: str, xaml_snippet: str) -> bool:
    """Replace a SCAFFOLD.<marker> Comment with XAML content."""
    # ── Reject hallucinated snippets ──
    snippet_errors = validate_snippet(xaml_snippet)
    if snippet_errors:
        print("ERROR: XAML snippet contains hallucinated patterns:", file=sys.stderr)
        for e in snippet_errors:
            print(f"  {e}", file=sys.stderr)
        print("\n⛔ The snippet passed to replace-marker MUST come from generator output "
              "(gen_*() or generate_workflow.py). Do NOT hand-write XAML.", file=sys.stderr)
        return False

    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        return False

    # Renumber IdRefs in the snippet to avoid collisions
    xaml_snippet = _renumber_idrefs(content, xaml_snippet)
    _warn_nested_retryscope(xaml_snippet)

    # Find the marker
    found = False
    for match in MARKER_PATTERN.finditer(content):
        if match.group(1) == marker_name:
            found = True
            le = detect_line_ending(content)
            # Detect indent from the matched Comment element
            comment_line = match.group(0)
            leading_space = re.match(r'^([ \t]*)', comment_line).group(1)

            # Indent the replacement snippet
            snippet_lines = xaml_snippet.strip().split("\n")
            indented = le.join(
                leading_space + line.strip() if i > 0 else leading_space + line.strip()
                for i, line in enumerate(snippet_lines)
            )

            content = content[:match.start()] + indented + le + content[match.end():]
            break

    if not found:
        print(f"ERROR: Marker SCAFFOLD.{marker_name} not found in {filepath}", file=sys.stderr)
        return False

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    print(f"OK: Replaced SCAFFOLD.{marker_name} in {filepath}")
    return True


def cmd_list_markers(filepath: str) -> bool:
    """List all SCAFFOLD.* markers in a file."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        return False

    markers = MARKER_PATTERN.findall(content)
    if not markers:
        print(f"No SCAFFOLD.* markers found in {filepath}")
    else:
        print(f"Markers in {filepath}:")
        for m in markers:
            print(f"  SCAFFOLD.{m}")
    return True


def _add_xproperty(content: str, prop_xml: str) -> str:
    """Add an x:Property to the x:Members block. Creates x:Members if absent."""
    if "</x:Members>" in content:
        return content.replace(
            "</x:Members>",
            f"    {prop_xml}\n  </x:Members>"
        )
    # No x:Members block — insert after first line of <Activity ...>
    activity_end = content.find(">") + 1
    members_block = (
        f"\n  <x:Members>\n"
        f"    {prop_xml}\n"
        f"  </x:Members>"
    )
    return content[:activity_end] + members_block + content[activity_end:]


def _add_invoke_arg(content: str, workflow_filename: str,
                    arg_key: str, arg_type: str, direction: str,
                    var_name: str) -> str:
    """Add an argument to an InvokeWorkflowFile's Arguments dictionary."""
    pattern = re.compile(
        rf'(<ui:InvokeWorkflowFile[^>]*WorkflowFileName="[^"]*{re.escape(workflow_filename)}[^"]*"'
        rf'.*?)(</ui:InvokeWorkflowFile\.Arguments>)',
        re.DOTALL
    )
    match = pattern.search(content)
    if not match:
        print(f"  WARN: Could not find invoke of {workflow_filename}", file=sys.stderr)
        return content

    block = match.group(1)

    # Handle empty dictionary: <scg:Dictionary x:TypeArguments="x:String, Argument" />
    empty_dict = re.search(
        r'(<scg:Dictionary x:TypeArguments="x:String, Argument"\s*/>)',
        block
    )
    if empty_dict:
        le = detect_line_ending(content)
        # Detect indent of the empty dict line
        dict_pos = content.index(empty_dict.group(1))
        line_start = content.rfind("\n", 0, dict_pos) + 1
        base_indent = re.match(r'(\s*)', content[line_start:]).group(1)
        arg_indent = base_indent + "  "
        new_arg = f'<{direction} x:TypeArguments="{arg_type}" x:Key="{arg_key}">[{var_name}]</{direction}>'
        replacement = (
            f'<scg:Dictionary x:TypeArguments="x:String, Argument">{le}'
            f'{arg_indent}{new_arg}{le}'
            f'{base_indent}</scg:Dictionary>'
        )
        content = content.replace(empty_dict.group(1), replacement, 1)
        return content

    # Check if args are wrapped in <scg:Dictionary> (old-style syntax)
    dict_close = re.search(r'</scg:Dictionary>', block)
    if dict_close:
        # Insert inside the Dictionary, before </scg:Dictionary>
        arg_lines = re.findall(r'^(\s+)<(?:In|Out|InOut)Argument ', block, re.MULTILINE)
        arg_indent = arg_lines[0] if arg_lines else "                          "
        new_arg_line = (
            f'{arg_indent}<{direction} x:TypeArguments="{arg_type}" '
            f'x:Key="{arg_key}">[{var_name}]</{direction}>'
        )
        le = detect_line_ending(content)
        # Find the </scg:Dictionary> position in the full content
        dict_close_abs = content.find('</scg:Dictionary>', match.start())
        content = content[:dict_close_abs] + new_arg_line + le + content[dict_close_abs:]
        return content

    # Normal case: detect arg indent and insert before closing tag
    arg_lines = re.findall(r'^(\s+)<(?:In|Out|InOut)Argument ', block, re.MULTILINE)
    arg_indent = arg_lines[0] if arg_lines else "                          "
    new_arg_line = (
        f'{arg_indent}<{direction} x:TypeArguments="{arg_type}" '
        f'x:Key="{arg_key}">[{var_name}]</{direction}>'
    )
    le = detect_line_ending(content)
    insert_pos = match.start(2)
    content = content[:insert_pos] + new_arg_line + le + content[insert_pos:]
    return content


def _add_variable(content: str, var_name: str, var_type: str) -> str:
    """Add a Variable to a XAML file's Variables block.

    NOTE: This function handles single-variable insertion and is called by
    cmd_wire_uielement(). The CLI 'add-variables' command uses cmd_add_variables()
    which has its own batch insertion logic. If you fix indent/insertion logic
    here, check cmd_add_variables() too — they are parallel code paths.

    Searches for (in order):
      1. <StateMachine.Variables> — REFramework Main.xaml (cross-state scope)
      2. <Sequence.Variables>     — framework files (Process.xaml, GTD, etc.)
      3. Creates <Sequence.Variables> — if no block exists yet, inserts one
         after the first <Sequence ...> opening tag (before child activities)

    In REFramework Main.xaml, variables must be in <StateMachine.Variables>
    so they're accessible across all states (Init, GetTransactionData, Process, End).
    """
    # Normalize short-form types (e.g. DataTable → sd:DataTable)
    var_type = _normalize_var_type(var_type)

    # Skip if variable already declared
    if f'Name="{var_name}"' in content:
        print(f"  . Variable {var_name} already exists — skipped")
        return content

    var_xml = f'<Variable x:TypeArguments="{var_type}" Name="{var_name}" />'
    le = detect_line_ending(content)

    # 1. StateMachine.Variables (REFramework Main.xaml)
    if "</StateMachine.Variables>" in content:
        idx = content.index("</StateMachine.Variables>")
        line_start = content.rfind("\n", 0, idx) + 1
        indent_match = re.match(r'(\s+)', content[line_start:])
        indent = indent_match.group(1) if indent_match else "      "
        content = content[:idx] + f"{indent}{var_xml}{le}" + content[idx:]
        return content

    # 2. Existing Sequence.Variables — use closing tag indent + 2 spaces
    if "</Sequence.Variables>" in content:
        close_idx = content.index("</Sequence.Variables>")
        close_line_start = content.rfind("\n", 0, close_idx) + 1
        close_indent_match = re.match(r'(\s*)', content[close_line_start:])
        close_indent = close_indent_match.group(1) if close_indent_match else "      "
        var_indent = close_indent + "  "
        content = content[:close_idx] + f"{var_indent}{var_xml}{le}" + content[close_idx:]
        return content

    # 3. No Variables block yet — create <Sequence.Variables> after the
    #    first <Sequence ...> tag's closing bracket (before child activities).
    #    In framework files the main Sequence typically has DisplayName="Process"
    #    or similar and is the outermost activity container.
    seq_match = re.search(
        r'(<Sequence\s[^>]*DisplayName="[^"]*"[^>]*>)\s*\r?\n',
        content
    )
    if not seq_match:
        # Fallback: any <Sequence ...> with attributes
        seq_match = re.search(r'(<Sequence\s[^>]*>)\s*\r?\n', content)
    if seq_match:
        insert_after = seq_match.end()
        # Detect indent from the Sequence tag
        seq_line_start = content.rfind("\n", 0, seq_match.start()) + 1
        base_indent = re.match(r'(\s*)', content[seq_line_start:]).group(1)
        vars_indent = base_indent + "  "
        var_indent = vars_indent + "  "
        block = (
            f"{vars_indent}<Sequence.Variables>{le}"
            f"{var_indent}{var_xml}{le}"
            f"{vars_indent}</Sequence.Variables>{le}"
        )
        content = content[:insert_after] + block + content[insert_after:]
        return content

    print(f"  WARN: No Variables block found and no <Sequence> to attach to", file=sys.stderr)
    return content


def cmd_add_variables(filepath: str, *var_specs_args) -> bool:
    """Add variables to a framework XAML file.

    Args:
        filepath: Path to the XAML file (e.g. Framework/Process.xaml)
        *var_specs_args: Variable specs — either positional args like
            ("strResult", "x:String"), ("strHash", "x:String") or a single
            list [("strResult", "x:String"), ("strHash", "x:String")].

    Creates <Sequence.Variables> block if one doesn't exist yet.
    Skips variables that are already declared (idempotent).
    Inserts all variables in a single pass to maintain correct indentation.
    """
    # Support both: cmd_add_variables(f, 'a:x:String', 'b:x:Int32')
    #           and: cmd_add_variables(f, [('a', 'x:String'), ('b', 'x:Int32')])
    if len(var_specs_args) == 1 and isinstance(var_specs_args[0], list):
        variables = var_specs_args[0]
    else:
        variables = list(var_specs_args)
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        return False

    le = detect_line_ending(content)

    # Normalize types before filtering (fail fast on unknown bare types)
    try:
        variables = [(n, _normalize_var_type(t)) for n, t in variables]
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False

    # Filter out already-declared variables
    new_vars = [(n, t) for n, t in variables if f'Name="{n}"' not in content]
    skipped = len(variables) - len(new_vars)
    if skipped:
        for n, t in variables:
            if f'Name="{n}"' in content:
                print(f"  . Variable {n} already exists — skipped")

    if not new_vars:
        print(f"OK: No new variables needed in {filepath}")
        return True

    # Build the variable XML lines
    def _var_xml(name: str, vtype: str) -> str:
        return f'<Variable x:TypeArguments="{vtype}" Name="{name}" />'

    # Case 1: StateMachine.Variables exists (Main.xaml)
    if "</StateMachine.Variables>" in content:
        close_tag = "</StateMachine.Variables>"
        close_idx = content.index(close_tag)
        # Insert at the start of the close tag's line (before its indent)
        close_line_start = content.rfind("\n", 0, close_idx) + 1
        close_indent = re.match(r'(\s*)', content[close_line_start:]).group(1)
        var_indent = close_indent + "  "
        insert_lines = le.join(f"{var_indent}{_var_xml(n, t)}" for n, t in new_vars)
        content = content[:close_line_start] + insert_lines + le + content[close_line_start:]

    # Case 2: Sequence.Variables exists
    elif "</Sequence.Variables>" in content:
        close_tag = "</Sequence.Variables>"
        close_idx = content.index(close_tag)
        close_line_start = content.rfind("\n", 0, close_idx) + 1
        close_indent = re.match(r'(\s*)', content[close_line_start:]).group(1)
        var_indent = close_indent + "  "
        insert_lines = le.join(f"{var_indent}{_var_xml(n, t)}" for n, t in new_vars)
        content = content[:close_line_start] + insert_lines + le + content[close_line_start:]

    # Case 3: No Variables block — create one after <Sequence ...>
    else:
        seq_match = re.search(
            r'(<Sequence\s[^>]*DisplayName="[^"]*"[^>]*>)\s*\r?\n',
            content
        )
        if not seq_match:
            seq_match = re.search(r'(<Sequence\s[^>]*>)\s*\r?\n', content)
        if seq_match:
            insert_after = seq_match.end()
            seq_line_start = content.rfind("\n", 0, seq_match.start()) + 1
            base_indent = re.match(r'(\s*)', content[seq_line_start:]).group(1)
            block_indent = base_indent + "  "
            var_indent = block_indent + "  "
            var_lines = le.join(f"{var_indent}{_var_xml(n, t)}" for n, t in new_vars)
            block = (
                f"{block_indent}<Sequence.Variables>{le}"
                f"{var_lines}{le}"
                f"{block_indent}</Sequence.Variables>{le}"
            )
            content = content[:insert_after] + block + content[insert_after:]
        else:
            print(f"ERROR: No Variables block and no <Sequence> to attach to",
                  file=sys.stderr)
            return False

    for n, t in new_vars:
        print(f"  + Added variable: {n} ({t})")

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"OK: Added {len(new_vars)} variable(s) to {filepath}")
    return True


def cmd_wire_uielement(project_dir: str, app_name: str) -> bool:
    """Wire UiElement argument chain for an app across all REFramework files.

    Creates the full typed argument flow:
      InitAllApplications: out_uiXxx (OutArgument)
      Main.xaml: uiXxx (Variable) + wired in 3 invokes
      Process.xaml: io_uiXxx (InOutArgument)
      CloseAllApplications: in_uiXxx (InArgument)

    Usage:
      python3 modify_framework.py wire-uielement <project_dir> <AppName>
    """
    from pathlib import Path
    project = Path(project_dir)

    files = {
        "init": project / "Framework" / "InitAllApplications.xaml",
        "close": project / "Framework" / "CloseAllApplications.xaml",
        "process": project / "Framework" / "Process.xaml",
        "gtd": project / "Framework" / "GetTransactionData.xaml",
        "main": project / "Main.xaml",
    }

    for key, path in files.items():
        if not path.exists():
            if key == "gtd":
                continue  # Optional — only dispatchers modify GTD
            print(f"ERROR: {path} not found", file=sys.stderr)
            return False

    var_name = f"ui{app_name}"
    out_arg = f"out_ui{app_name}"
    io_arg = f"io_ui{app_name}"
    in_arg = f"in_ui{app_name}"
    ui_type = "ui:UiElement"
    changes = 0

    # 1. InitAllApplications — add OutArgument
    with open(files["init"], "r", encoding="utf-8-sig") as f:
        init_content = f.read()
    if out_arg not in init_content:
        prop = f'<x:Property Name="{out_arg}" Type="OutArgument({ui_type})" />'
        init_content = _add_xproperty(init_content, prop)
        with open(files["init"], "w", encoding="utf-8", newline="") as f:
            f.write(init_content)
        print(f"  + InitAllApplications: added {out_arg} OutArgument")
        changes += 1
    else:
        print(f"  . InitAllApplications: {out_arg} already exists")

    # 2. CloseAllApplications — add InArgument
    with open(files["close"], "r", encoding="utf-8-sig") as f:
        close_content = f.read()
    if in_arg not in close_content:
        prop = f'<x:Property Name="{in_arg}" Type="InArgument({ui_type})" />'
        close_content = _add_xproperty(close_content, prop)
        with open(files["close"], "w", encoding="utf-8", newline="") as f:
            f.write(close_content)
        print(f"  + CloseAllApplications: added {in_arg} InArgument")
        changes += 1
    else:
        print(f"  . CloseAllApplications: {in_arg} already exists")

    # 3. Process.xaml — add InOutArgument
    with open(files["process"], "r", encoding="utf-8-sig") as f:
        process_content = f.read()
    if io_arg not in process_content:
        prop = f'<x:Property Name="{io_arg}" Type="InOutArgument({ui_type})" />'
        process_content = _add_xproperty(process_content, prop)
        with open(files["process"], "w", encoding="utf-8", newline="") as f:
            f.write(process_content)
        print(f"  + Process.xaml: added {io_arg} InOutArgument")
        changes += 1
    else:
        print(f"  . Process.xaml: {io_arg} already exists")

    # 3b. GetTransactionData.xaml — add InOutArgument (dispatchers use GTD for navigation+extraction)
    if files["gtd"].exists():
        with open(files["gtd"], "r", encoding="utf-8-sig") as f:
            gtd_content = f.read()
        if io_arg not in gtd_content:
            prop = f'<x:Property Name="{io_arg}" Type="InOutArgument({ui_type})" />'
            gtd_content = _add_xproperty(gtd_content, prop)
            with open(files["gtd"], "w", encoding="utf-8", newline="") as f:
                f.write(gtd_content)
            print(f"  + GetTransactionData.xaml: added {io_arg} InOutArgument")
            changes += 1
        else:
            print(f"  . GetTransactionData.xaml: {io_arg} already exists")

    # 4. Main.xaml — add variable + wire 3 invokes
    with open(files["main"], "r", encoding="utf-8-sig") as f:
        main_content = f.read()

    if f'Name="{var_name}"' not in main_content:
        main_content = _add_variable(main_content, var_name, ui_type)
        print(f"  + Main.xaml: added variable {var_name}")
        changes += 1
    else:
        print(f"  . Main.xaml: variable {var_name} already exists")

    if f'x:Key="{out_arg}"' not in main_content:
        main_content = _add_invoke_arg(
            main_content, "InitAllApplications.xaml",
            out_arg, ui_type, "OutArgument", var_name
        )
        print(f"  + Main.xaml: wired {out_arg} in InitAllApplications invoke")
        changes += 1
    else:
        print(f"  . Main.xaml: {out_arg} already wired")

    # Wire GetTransactionData invoke (dispatchers pass UiElement for navigation)
    if "GetTransactionData.xaml" in main_content:
        # Check if io_arg is already in the GTD invoke specifically
        gtd_match = re.search(
            rf'<ui:InvokeWorkflowFile[^>]*GetTransactionData\.xaml.*?</ui:InvokeWorkflowFile>',
            main_content, re.DOTALL
        )
        if gtd_match and f'x:Key="{io_arg}"' not in gtd_match.group():
            main_content = _add_invoke_arg(
                main_content, "GetTransactionData.xaml",
                io_arg, ui_type, "InOutArgument", var_name
            )
            print(f"  + Main.xaml: wired {io_arg} in GetTransactionData invoke")
            changes += 1
        else:
            print(f"  . Main.xaml: {io_arg} already wired in GetTransactionData invoke")

    # Wire Process invoke
    process_match = re.search(
        rf'<ui:InvokeWorkflowFile[^>]*Process\.xaml.*?</ui:InvokeWorkflowFile>',
        main_content, re.DOTALL
    )
    if process_match and f'x:Key="{io_arg}"' not in process_match.group():
        main_content = _add_invoke_arg(
            main_content, "Process.xaml",
            io_arg, ui_type, "InOutArgument", var_name
        )
        print(f"  + Main.xaml: wired {io_arg} in Process invoke")
        changes += 1
    else:
        print(f"  . Main.xaml: {io_arg} already wired in Process invoke")

    if f'x:Key="{in_arg}"' not in main_content:
        main_content = _add_invoke_arg(
            main_content, "CloseAllApplications.xaml",
            in_arg, ui_type, "InArgument", var_name
        )
        print(f"  + Main.xaml: wired {in_arg} in CloseAllApplications invoke")
        changes += 1
    else:
        print(f"  . Main.xaml: {in_arg} already wired")

    with open(files["main"], "w", encoding="utf-8", newline="") as f:
        f.write(main_content)

    print(f"\nDone: {changes} changes for app '{app_name}'")
    print(f"  Chain: Launch({out_arg}) -> InitAllApps({out_arg}) -> Main({var_name}) -> GTD({io_arg}) -> Process({io_arg}) -> CloseAll({in_arg})")
    return True


def cmd_set_expression(filepath: str, target: str, attribute: str,
                       expression: str) -> bool:
    """Replace a placeholder expression in a framework activity.

    Locates an activity by DisplayName or IdRef, then replaces the specified
    attribute's expression value.

    For Assign activities with attribute='Value':
      Finds <Assign.Value><InArgument ...>[old]</InArgument></Assign.Value>
      and replaces [old] with [expression].

    For other attributes:
      Finds attribute="[old]" on the activity element and replaces with [expression].

    Args:
        filepath: Path to the XAML file
        target: Activity DisplayName or IdRef (e.g. "Assign out_TransactionID" or "Assign_5")
        attribute: Which attribute to modify (e.g. 'Value' for Assign.Value)
        expression: New VB expression (without brackets — brackets are added automatically)

    Returns:
        True if replacement succeeded.
    """
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        return False

    le = detect_line_ending(content)

    # Escape the target for use in regex
    target_escaped = re.escape(target)

    # Heuristic: IdRefs are like "Assign_5", "If_1" (no spaces, has underscore).
    # DisplayNames like "Assign out_TransactionID" always have spaces.
    # Edge case: a spaceless DisplayName with underscore (e.g. "Log_Error") would
    # be misclassified, but the error path lists available targets for recovery.
    is_idref = not any(c == " " for c in target) and "_" in target
    if is_idref:
        activity_pattern = re.compile(
            rf'<(\w[\w:]*)\b[^>]*IdRef="{target_escaped}"[^>]*>',
            re.DOTALL
        )
    else:
        activity_pattern = re.compile(
            rf'<(\w[\w:]*)\b[^>]*DisplayName="{target_escaped}"[^>]*>',
            re.DOTALL
        )

    match = activity_pattern.search(content)
    if not match:
        # List available targets for helpful error
        display_names = re.findall(r'DisplayName="([^"]+)"', content)
        id_refs = re.findall(r'IdRef="([^"]+)"', content)
        print(f"ERROR: Activity not found with "
              f"{'IdRef' if is_idref else 'DisplayName'}=\"{target}\"",
              file=sys.stderr)
        if display_names:
            print(f"  Available DisplayNames: {', '.join(display_names[:15])}",
                  file=sys.stderr)
        if id_refs:
            print(f"  Available IdRefs: {', '.join(id_refs[:15])}",
                  file=sys.stderr)
        return False

    activity_tag = match.group(1)
    activity_start = match.start()

    # For Assign activities with Value attribute, find <Assign.Value><InArgument>
    if activity_tag == "Assign" and attribute == "Value":
        # Find the Assign.Value block after this activity
        value_block = re.search(
            r'<Assign\.Value>\s*<InArgument[^>]*>\[([^\]]*)\]</InArgument>\s*</Assign\.Value>',
            content[activity_start:]
        )
        if not value_block:
            print(f"ERROR: Could not find <Assign.Value> block for '{target}'",
                  file=sys.stderr)
            return False

        # Replace the expression
        old_full = value_block.group(0)
        old_expr = value_block.group(1)
        new_full = old_full.replace(f"[{old_expr}]", f"[{expression}]")
        content = content[:activity_start + value_block.start()] + new_full + \
                  content[activity_start + value_block.end():]
        print(f"  + {attribute}: [{old_expr}] → [{expression}]")

    else:
        # For other attributes, find attribute="[old]" on the activity element
        # Look for the attribute within the activity's opening tag or nearby
        attr_pattern = re.compile(
            rf'({re.escape(attribute)}=")(\[[^\]]*\]|[^"]*?)(")',
        )
        attr_match = attr_pattern.search(content[activity_start:activity_start + 2000])
        if not attr_match:
            print(f"ERROR: Attribute '{attribute}' not found near '{target}'",
                  file=sys.stderr)
            return False

        old_val = attr_match.group(2)
        new_val = f"[{expression}]" if not expression.startswith("[") else expression
        old_full = attr_match.group(0)
        new_full = f'{attr_match.group(1)}{new_val}{attr_match.group(3)}'
        abs_start = activity_start + attr_match.start()
        abs_end = activity_start + attr_match.end()
        content = content[:abs_start] + new_full + content[abs_end:]
        print(f"  + {attribute}: {old_val} → {new_val}")

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"OK: Updated '{target}' in {filepath}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Structured framework file modification for UiPath REFramework projects"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_insert = sub.add_parser("insert-invoke", help="Insert XAML before </Sequence>")
    p_insert.add_argument("file", help="Framework XAML file path")
    p_insert.add_argument("xaml", help="XAML snippet to insert")

    p_replace = sub.add_parser("replace-marker", help="Replace SCAFFOLD.* marker")
    p_replace.add_argument("file", help="Framework XAML file path")
    p_replace.add_argument("marker", help="Marker name (e.g. PROCESS_BODY)")
    p_replace.add_argument("xaml", help="XAML snippet to insert")

    p_list = sub.add_parser("list-markers", help="List all markers in a file")
    p_list.add_argument("file", help="Framework XAML file path")

    p_vars = sub.add_parser("add-variables",
        help="Add variables to a framework XAML file")
    p_vars.add_argument("file", help="Framework XAML file path")
    p_vars.add_argument("variables", nargs="+",
        help="Variables as name:type pairs (e.g. strResult:x:String strCount:x:Int32)")

    p_wire = sub.add_parser("wire-uielement",
        help="Wire UiElement argument chain for an app across REFramework files")
    p_wire.add_argument("project_dir", help="Project root directory")
    p_wire.add_argument("app_name", help="App name (e.g. WebApp, SHA1Online)")

    p_expr = sub.add_parser("set-expression",
        help="Replace a placeholder expression in a framework activity")
    p_expr.add_argument("file", help="Framework XAML file path")
    p_expr.add_argument("target",
        help="Activity DisplayName or IdRef (e.g. 'Assign out_TransactionID' or 'Assign_5')")
    p_expr.add_argument("attribute",
        help="Attribute to modify (e.g. 'Value' for Assign.Value)")
    p_expr.add_argument("expression",
        help="New VB expression without brackets (brackets added automatically)")

    args = parser.parse_args()

    if args.command == "insert-invoke":
        ok = cmd_insert_invoke(args.file, args.xaml)
    elif args.command == "replace-marker":
        ok = cmd_replace_marker(args.file, args.marker, args.xaml)
    elif args.command == "list-markers":
        ok = cmd_list_markers(args.file)
    elif args.command == "add-variables":
        # Parse name:type pairs — type can contain colons (e.g. x:String)
        # so split on FIRST colon only
        var_list = []
        for v in args.variables:
            parts = v.split(":", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                print(f"ERROR: Invalid variable format '{v}'. Use name:type (e.g. strResult:x:String)",
                      file=sys.stderr)
                sys.exit(1)
            var_list.append((parts[0], parts[1]))
        ok = cmd_add_variables(args.file, var_list)
    elif args.command == "wire-uielement":
        ok = cmd_wire_uielement(args.project_dir, args.app_name)
    elif args.command == "set-expression":
        ok = cmd_set_expression(args.file, args.target, args.attribute,
                                args.expression)
    else:
        parser.print_help()
        ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
