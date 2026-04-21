"""Tasks lint rules — moved from uipath-core validate_xaml.py.

AC-10: CreateFormTask / WaitForFormTaskAndResume count mismatch
AC-11: FormData keys don't match form.io component keys
AC-12: CreateExternalTask / WaitForExternalTaskAndResume count mismatch
AC-26: Persistence activities in non-Main workflow
AC-27: Persistence activities nested in a scope that can't serialize bookmarks
AC-28: CreateFormTask / CreateExternalTask missing FolderPath (runtime 1101)
AC-29: <ui:InvokeMethod> — wrong namespace; InvokeMethod is in the default one
AC-30: InvokeMethod.TargetObject attribute form; needs element form
AC-31: FormTaskData.Data(...) / ExternalTaskData.Data(...) late-binding (BC30574)
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from html import unescape


# form.io component types that are layout/decoration and do NOT bind to
# FormData. Keys on these components (e.g. a heading's `header` key or a
# `columns` container's own key) are not missing bindings — they're not
# data-bearing in the first place. AC-11 must skip them to avoid noise.
_NON_DATA_FORMIO_TYPES = frozenset({
    "button",
    "htmlelement",
    "content",
    "columns",
    "panel",
    "well",
    "fieldset",
    "tabs",
    "table",
})


def lint_tasks(ctx, result):
    """AC-10: CreateFormTask should have matching WaitForFormTaskAndResume."""
    content = ctx.active_content

    create_count = len(re.findall(r'<upaf:CreateFormTask[\s>]', content))
    wait_count = len(re.findall(r'<upaf:WaitForFormTaskAndResume[\s>]', content))

    if create_count == 0:
        return  # No Tasks activities

    if wait_count == 0:
        result.warn(
            f"[AC-10] {create_count} CreateFormTask(s) but no WaitForFormTaskAndResume — "
            f"form tasks will be created but workflow won't wait for user input"
        )
    elif wait_count < create_count:
        result.warn(
            f"[AC-10] {create_count} CreateFormTask(s) but only {wait_count} WaitForFormTaskAndResume — "
            f"some tasks may not be awaited (OK if using shadow task pattern)"
        )
    else:
        result.ok(f"Tasks: {create_count} CreateFormTask, {wait_count} WaitForFormTask")

    # Check FormData bindings: key names should be non-empty
    form_data_keys = re.findall(
        r'<(?:InArgument|OutArgument|InOutArgument)[^>]*x:Key="([^"]*)"',
        content
    )
    empty_keys = [k for k in form_data_keys if not k.strip()]
    if empty_keys:
        result.error(f"[AC-10] {len(empty_keys)} FormData binding(s) with empty x:Key — form field key is required")

    # Check that TaskOutput variable is captured
    create_no_output = re.findall(r'<upaf:CreateFormTask\b[^>]*TaskOutput="\{x:Null\}"', content)
    if create_no_output:
        result.warn(
            f"[AC-10] {len(create_no_output)} CreateFormTask(s) with TaskOutput={{x:Null}} — "
            f"task data won't be captured for WaitForFormTaskAndResume"
        )
    # Note: TaskObject hallucination check is in lint_hallucinated_property_names (core)

    # Check EnableDynamicForms — must be True for form designer to work
    dynamic_false = re.findall(
        r'<upaf:CreateFormTask\b[^>]*EnableDynamicForms="False"', content
    )
    if dynamic_false:
        result.warn(
            f"[AC-10] {len(dynamic_false)} CreateFormTask(s) with EnableDynamicForms=\"False\" — "
            f"form designer won't open in Studio. Set EnableDynamicForms=\"True\""
        )


def lint_formdata_key_mismatch(ctx, result):
    """AC-11: FormData x:Key values should match form.io component keys.

    Extracts component keys from the FormLayout JSON and compares against
    FormData binding x:Key values. Warns on mismatches (keys in FormData
    but not in form.io, or vice versa). Skips button components since they
    don't bind to FormData.
    """
    content = ctx.active_content

    if '<upaf:CreateFormTask' not in content:
        return

    # Extract FormLayout JSON from FormLayout="{}escaped_json" attribute
    form_layout_match = re.search(r'FormLayout="\{\}(.*?)"', content)
    if not form_layout_match:
        return

    raw_json = unescape(form_layout_match.group(1))
    try:
        schema = json.loads(raw_json)
    except (json.JSONDecodeError, ValueError):
        return  # Can't parse — skip silently

    # Extract form.io component keys — only the data-bearing ones.
    # Skip layout/decoration types (see _NON_DATA_FORMIO_TYPES). Do not
    # recurse into datagrid children: a datagrid is bound to FormData via
    # its own key (as a DataTable), and its inner `components` array is a
    # column schema, not a flat list of top-level bindings.
    def extract_keys(components):
        keys = set()
        for comp in components:
            key = comp.get("key", "")
            comp_type = comp.get("type", "")
            if key and comp_type not in _NON_DATA_FORMIO_TYPES:
                keys.add(key)
            if comp_type == "datagrid":
                continue  # inner components are column defs, not bindings
            for sub in comp.get("components", []):
                keys.update(extract_keys([sub]))
            for col in comp.get("columns", []):
                keys.update(extract_keys(col.get("components", [])))
        return keys

    form_keys = extract_keys(schema.get("components", []))
    if not form_keys:
        return

    # Extract FormData x:Key values — scoped to CreateFormTask.FormData blocks
    # to avoid false positives from CreateExternalTask.TaskData entries
    formdata_section = re.search(
        r'<upaf:CreateFormTask\.FormData>(.*?)</upaf:CreateFormTask\.FormData>',
        content, re.DOTALL
    )
    if not formdata_section:
        return
    formdata_keys = set(re.findall(
        r'<(?:InArgument|OutArgument|InOutArgument)[^>]*x:Key="([^"]+)"',
        formdata_section.group(1)
    ))

    # Compare
    in_form_not_data = form_keys - formdata_keys
    in_data_not_form = formdata_keys - form_keys

    if in_data_not_form:
        result.warn(
            f"[AC-11] FormData key(s) not in form.io schema: "
            f"{', '.join(sorted(in_data_not_form))}. "
            f"These bindings won't connect to any form field."
        )
    if in_form_not_data:
        result.warn(
            f"[AC-11] Form.io component(s) without FormData binding: "
            f"{', '.join(sorted(in_form_not_data))}. "
            f"Data won't flow to/from these fields unless bound."
        )


def lint_external_task(ctx, result):
    """AC-12: CreateExternalTask should have matching WaitForExternalTaskAndResume."""
    content = ctx.active_content

    create_count = len(re.findall(r'<upae:CreateExternalTask[\s>]', content))
    wait_count = len(re.findall(r'<upae:WaitForExternalTaskAndResume[\s>]', content))

    if create_count == 0:
        return  # No external task activities

    if wait_count == 0:
        result.warn(
            f"[AC-12] {create_count} CreateExternalTask(s) but no WaitForExternalTaskAndResume — "
            f"external tasks will be created but workflow won't wait for completion"
        )
    elif wait_count < create_count:
        result.warn(
            f"[AC-12] {create_count} CreateExternalTask(s) but only {wait_count} WaitForExternalTaskAndResume — "
            f"some tasks may not be awaited"
        )
    else:
        result.ok(f"External Task: {create_count} CreateExternalTask, {wait_count} WaitForExternalTask")

    # Check that TaskOutput variable is captured
    create_no_output = re.findall(r'<upae:CreateExternalTask\b[^>]*TaskOutput="\{x:Null\}"', content)
    if create_no_output:
        result.warn(
            f"[AC-12] {len(create_no_output)} CreateExternalTask(s) with TaskOutput={{x:Null}} — "
            f"task data won't be captured for WaitForExternalTaskAndResume"
        )


def _current_file_is_entry_point(ctx):
    """True if ctx.filepath is declared in the nearest project.json's entryPoints[].

    Walks up from ctx.filepath looking for project.json (same pattern as
    uipath-core/scripts/validate_xaml/lints_framework.py). Returns False when
    no project.json is found, when it can't be parsed, or when the current
    file's basename doesn't match any entry point.

    Comparing by basename is intentional: UiPath project.json entryPoints store
    relative paths from the project root, and HITL/secondary entry points
    typically live at the project root (a persistence-point workflow must be an
    entry point, so it cannot be buried in a subdirectory).
    """
    try:
        filepath = ctx.filepath
    except Exception:
        return False
    if not filepath:
        return False

    # ctx.filepath can be a relative path (when validate_xaml is invoked with
    # a bare filename from the project dir) — abspath it so os.path.dirname
    # returns something we can walk up from.
    filepath = os.path.abspath(filepath)
    project_dir = os.path.dirname(filepath)
    while project_dir and not os.path.isfile(os.path.join(project_dir, "project.json")):
        parent = os.path.dirname(project_dir)
        if parent == project_dir:
            return False
        project_dir = parent
    if not project_dir:
        return False

    project_json_path = os.path.join(project_dir, "project.json")
    try:
        with open(project_json_path, encoding="utf-8") as f:
            project = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return False

    entry_points = project.get("entryPoints") or []
    if not isinstance(entry_points, list):
        return False

    current_basename = os.path.basename(filepath)
    for ep in entry_points:
        if not isinstance(ep, dict):
            continue
        ep_path = ep.get("filePath") or ep.get("FilePath") or ""
        if os.path.basename(ep_path) == current_basename:
            return True
    return False


def lint_persistence_in_subworkflow(ctx, result):
    """AC-26: Persistence (wait-and-resume) activities must be in an entry point.

    Activities like WaitForFormTaskAndResume are persistence points that
    suspend/serialize the workflow. They only work in entry-point files —
    Main.xaml by default, plus any additional workflow declared in
    `project.json.entryPoints[]` (e.g. a HITL sample registered as a second
    entry point alongside Main).
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Check x:Class — Main.xaml always passes (fast path + no project.json needed)
    class_match = re.search(r'x:Class="([^"]+)"', content)
    if class_match and class_match.group(1) == "Main":
        return

    # Secondary entry point declared in project.json → also passes
    if _current_file_is_entry_point(ctx):
        return

    persistence_activities = [
        "WaitForFormTaskAndResume",
        "WaitForFormTaskCompletion",
        "WaitForExternalTaskAndResume",
        "WaitForAppTaskAndResume",
        "WaitForJobAndResume",
        "WaitForQueueItemAndResume",
        "ResumeAfterDelay",
        "WaitForItemEvent",
        "ResumeBookmark",
    ]

    for activity in persistence_activities:
        # Match as XML element: <prefix:ActivityName or <ActivityName
        if re.search(rf'<\w*:?{activity}[\s/>]', content):
            result.error(
                f"[AC-26] Persistence activity '{activity}' found in non-entry-point workflow "
                f"(x:Class='{class_match.group(1) if class_match else '?'}'). "
                f"Wait-and-resume activities MUST be in an entry-point file — Main.xaml "
                f"or another workflow declared in project.json entryPoints[]. The persistence "
                f"bookmark context only exists in entry points. Move '{activity}' to an entry "
                f"point or register this file as one."
            )


_PERSISTENCE_ACTIVITIES = frozenset({
    "WaitForFormTaskAndResume",
    "WaitForFormTaskCompletion",
    "WaitForExternalTaskAndResume",
    "WaitForAppTaskAndResume",
    "WaitForJobAndResume",
    "WaitForQueueItemAndResume",
    "ResumeAfterDelay",
    "WaitForItemEvent",
    "ResumeBookmark",
})

_UNSUPPORTED_PERSISTENCE_SCOPES = frozenset({
    "ForEach",
    "ForEachRow",
    "ForEachFileX",
    "ForEachFolderX",
    "RetryScope",
    "TryCatch",
    "Parallel",
    "ParallelForEach",
    "Pick",
    "While",
    "DoWhile",
})


def _local_name(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def lint_persistence_in_unsupported_scope(ctx, result):
    """AC-27: Persistence activities must not be nested in scopes that can't serialize bookmarks.

    ForEachRow/ForEach/RetryScope/TryCatch/Parallel/Pick/While hold per-iteration
    or per-branch state that cannot be persisted mid-flight, so a nested
    Wait*AndResume triggers Studio's "the scope does not offer support for it"
    validation error. The fix is the Shadow Task Pattern: create tasks inside
    the loop, then wait on them in a second loop directly under the root Sequence.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    if not content:
        return

    if not any(name in content for name in _PERSISTENCE_ACTIVITIES):
        return

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return

    parents = {child: parent for parent in root.iter() for child in parent}

    for elem in root.iter():
        name = _local_name(elem.tag)
        if name not in _PERSISTENCE_ACTIVITIES:
            continue

        id_ref = next(
            (v for k, v in elem.attrib.items() if _local_name(k).endswith("IdRef")),
            None,
        )

        ancestor = parents.get(elem)
        while ancestor is not None:
            anc_name = _local_name(ancestor.tag)
            if anc_name in _UNSUPPORTED_PERSISTENCE_SCOPES:
                display_name = ancestor.attrib.get("DisplayName") or "(no DisplayName)"
                result.error(
                    f"[AC-27] Persistence activity '{name}'"
                    + (f" (IdRef '{id_ref}')" if id_ref else "")
                    + f" is nested inside scope '{anc_name}' "
                    f"(DisplayName '{display_name}'), which does not support persistence "
                    f"bookmarks. Wait-and-resume activities cannot run inside "
                    f"ForEach/ForEachRow/RetryScope/TryCatch/Parallel/Pick/While. Use the "
                    f"Shadow Task Pattern: first loop creates tasks into a List(FormTaskData); "
                    f"a second loop directly under the root Sequence (not nested) runs "
                    f"Wait*AndResume per task. See uipath-tasks/references/form-tasks.md."
                )
                break
            ancestor = parents.get(ancestor)


_TASK_CREATE_ACTIVITIES = ("upaf:CreateFormTask", "upae:CreateExternalTask")


def lint_task_create_missing_folder(ctx, result):
    """AC-28: CreateFormTask / CreateExternalTask should have FolderPath set.

    Without an Orchestrator folder context, the Action Center API rejects the
    task creation call at runtime with 'A folder is required for this action.
    Error code: 1101'. Studio auto-injects FolderPath when the user sets it via
    the Properties panel; generated XAML does not, so the activity arrives with
    FolderPath missing or as {x:Null} and only fails at the first run.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    if not content:
        return

    for act in _TASK_CREATE_ACTIVITIES:
        for m in re.finditer(rf"<{act}\b([^>]*)>", content, flags=re.DOTALL):
            attrs = m.group(1)
            folder_match = re.search(r'\sFolderPath="([^"]*)"', attrs)
            if folder_match is None:
                missing = True
                value = None
            else:
                value = folder_match.group(1)
                missing = value in ("", "{x:Null}")

            if not missing:
                continue

            display_match = re.search(r'\sDisplayName="([^"]*)"', attrs)
            display = display_match.group(1) if display_match else "(no DisplayName)"
            activity_local = act.split(":", 1)[-1]
            if value is None:
                reason = "no FolderPath attribute"
            else:
                reason = f'FolderPath="{value}"'
            result.warn(
                f"[AC-28] {activity_local} '{display}' has {reason}. Action Center "
                f"activities need an Orchestrator folder — runtime will fail with "
                f"'A folder is required for this action. Error code: 1101'. "
                f"Set FolderPath to a folder name (e.g. \"Shared\" or a Config key)."
            )


def lint_ui_invoke_method(ctx, result):
    """AC-29: <ui:InvokeMethod> is not a UiPath activity.

    InvokeMethod lives in the default activities namespace
    (http://schemas.microsoft.com/netfx/2009/xaml/activities), not under ui:.
    The ui: prefix is a plausible hallucination because ui:InvokeWorkflowFile
    and ui:InvokeCode exist. Studio fails to load any XAML that declares
    <ui:InvokeMethod> with "Could not find type 'InvokeMethod' in namespace
    'http://schemas.uipath.com/workflow/activities'".
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    if not content:
        return

    for m in re.finditer(r"<ui:InvokeMethod\b", content):
        result.error(
            f"[AC-29] <ui:InvokeMethod> is not a UiPath activity — InvokeMethod "
            f"lives in the default activities namespace. Remove the 'ui:' prefix: "
            f"use <InvokeMethod .../> directly."
        )


def lint_invoke_method_targetobject_attribute(ctx, result):
    """AC-30: InvokeMethod.TargetObject must use element form, not attribute form.

    Studio rejects <InvokeMethod TargetObject="[expr]"> with "String is not
    assignable to InArgument of member 'TargetObject' and there is no
    TypeConverter defined on the member". TargetObject is typed InArgument(T)
    and the default attribute-to-InArgument converter does not dispatch on
    this property — element form with an explicit typed <InArgument> is
    required.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    if not content:
        return

    for m in re.finditer(
        r"<InvokeMethod\b[^>]*?\sTargetObject=\"\[[^\"]+\]\"",
        content,
    ):
        result.warn(
            f"[AC-30] InvokeMethod uses attribute-form TargetObject=\"[expr]\". "
            f"Studio's default converter rejects this on TargetObject. "
            f"Use element form: "
            f"<InvokeMethod.TargetObject><InArgument x:TypeArguments=\"...\">[expr]"
            f"</InArgument></InvokeMethod.TargetObject>."
        )


_FORMDATA_LATE_BINDING_RE = re.compile(
    r"\b(fdt\w+|edt\w+|FormTaskData\w*|ExternalTaskData\w*)\.Data\s*\("
)


def lint_formtaskdata_data_late_binding(ctx, result):
    """AC-31: FormTaskData.Data("key") / ExternalTaskData.Data("key") is late-bound.

    .Data returns a weakly-typed dictionary (IDictionary / JObject). Default-
    indexer access fails under Option Strict On with BC30574 ("Option Strict On
    disallows late binding"). Prefer the typed Title property or the FormData
    OutArgument variable you already bound in CreateFormTask.FormData.

    Scoped to variable names starting with the skill's fdt/edt prefixes or to
    literal type names to avoid false positives on unrelated .Data members.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    if not content:
        return

    seen = set()
    for m in _FORMDATA_LATE_BINDING_RE.finditer(content):
        var = m.group(1)
        if var in seen:
            continue
        seen.add(var)
        result.warn(
            f"[AC-31] Late-bound access '{var}.Data(...)' — .Data is a weakly-typed "
            f"dictionary; Option Strict On rejects default-indexer access (BC30574). "
            f"Use the typed Title property (e.g. {var}.Title) or the OutArgument "
            f"variable you bound in <CreateFormTask.FormData> / "
            f"<CreateExternalTask.TaskData>."
        )
