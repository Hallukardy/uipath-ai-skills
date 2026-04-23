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
AC-32: DynamicFormPath points to a file that's missing or has the wrong shape
AC-33: Large inline FormLayout should be extracted to a sibling .json file
AC-34: Unrolled / sequential per-item Create→Wait — use Shadow Task Pattern
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


def _find_project_root(filepath):
    """Walk up from ``filepath`` looking for the nearest project.json.

    Mirrors the lookup in _current_file_is_entry_point but returns the
    directory containing project.json (or None if not found).
    """
    if not filepath:
        return None
    filepath = os.path.abspath(filepath)
    project_dir = os.path.dirname(filepath)
    while project_dir and not os.path.isfile(os.path.join(project_dir, "project.json")):
        parent = os.path.dirname(project_dir)
        if parent == project_dir:
            return None
        project_dir = parent
    return project_dir or None


_CREATE_FORM_TASK_RE = re.compile(r"<upaf:CreateFormTask\b([^>]*)>", re.DOTALL)


def _dynamic_form_path_value(attrs):
    """Return the DynamicFormPath attribute value or None if absent/null."""
    m = re.search(r'\bDynamicFormPath="([^"]*)"', attrs)
    if m is None:
        return None
    v = m.group(1)
    return None if v in ("", "{x:Null}") else v


def _inline_form_layout_size(attrs):
    """Return the raw JSON length of the inline FormLayout attribute (0 if absent)."""
    m = re.search(r'\bFormLayout="\{\}(.*?)"', attrs)
    if not m:
        return 0
    return len(unescape(m.group(1)))


def lint_dynamic_form_path_missing_file(ctx, result):
    """AC-32: DynamicFormPath must point to an existing, correctly-shaped file.

    When CreateFormTask sets ``DynamicFormPath="Forms/X.json"``, Studio (and
    the runtime) load the external form file instead of the inline
    FormLayout. If the file is missing, the form designer fails to open;
    at runtime the task errors with 'Form File has invalid format' or
    'Cannot deserialize … List<FormIOComponent>' (see form-tasks.md:319-321).

    Required shape: root ``form`` array + required ``id`` string. The common
    mistakes — ``{"components": [...]}`` (form.io default) and bare arrays —
    are explicitly flagged.
    """
    try:
        content = ctx.active_content
        filepath = getattr(ctx, "filepath", None)
    except Exception:
        return
    if not content or "<upaf:CreateFormTask" not in content:
        return

    project_root = _find_project_root(filepath)
    if project_root is None:
        return  # Without project root we can't resolve the relative path.

    for m in _CREATE_FORM_TASK_RE.finditer(content):
        attrs = m.group(1)
        dyn_path = _dynamic_form_path_value(attrs)
        if dyn_path is None:
            continue

        display_match = re.search(r'\sDisplayName="([^"]*)"', attrs)
        display = display_match.group(1) if display_match else "(no DisplayName)"

        normalized = dyn_path.replace("\\", "/").replace("/", os.sep)
        abs_path = os.path.join(project_root, normalized)
        if not os.path.isfile(abs_path):
            result.error(
                f"[AC-32] CreateFormTask '{display}' sets DynamicFormPath="
                f"\"{dyn_path}\" but no file exists at that path under the "
                f"project root. The form designer won't open and the task "
                f"will fail at runtime. Either write the form schema to "
                f"'{dyn_path}' or clear DynamicFormPath to fall back to "
                f"inline FormLayout."
            )
            continue

        try:
            with open(abs_path, encoding="utf-8") as f:
                schema = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            result.error(
                f"[AC-32] CreateFormTask '{display}' DynamicFormPath file "
                f"'{dyn_path}' is unreadable or invalid JSON: {e}."
            )
            continue

        if not isinstance(schema, dict) or "form" not in schema or \
                not isinstance(schema.get("form"), list):
            hint = (
                " Root key 'components' is the form.io default; UiPath "
                "external form files require 'form'. Convert with "
                "form_layout_to_external_file()."
                if isinstance(schema, dict) and "components" in schema
                else ""
            )
            result.error(
                f"[AC-32] CreateFormTask '{display}' DynamicFormPath file "
                f"'{dyn_path}' has the wrong shape — root key must be 'form' "
                f"(array of components). Runtime will raise 'Cannot "
                f"deserialize the current JSON object into "
                f"List<FormIOComponent>' or 'Form File has invalid format'."
                f"{hint}"
            )
            continue

        if not schema.get("id"):
            result.error(
                f"[AC-32] CreateFormTask '{display}' DynamicFormPath file "
                f"'{dyn_path}' is missing the required 'id' string at the "
                f"root. Runtime will raise 'JArray does not contain a "
                f"definition for \\'id\\''."
            )


# Inline FormLayout above this many characters of raw JSON should live in a
# sibling file (better diffs, designer-editable, reusable). Chosen to fire on
# real-world forms (~10 fields / ~1KB+) without nagging tiny demo snippets.
_INLINE_FORM_LAYOUT_SOFT_LIMIT = 500


def lint_inline_form_layout_should_extract(ctx, result):
    """AC-33: Large inline FormLayout — recommend extraction to a .json file.

    Inline FormLayout isn't editable from Studio's form designer, blows up
    XAML diffs, and can't be shared across workflows. Past the soft limit
    (~500 chars of raw JSON), the payoff of extracting to a sibling
    DynamicFormPath file outweighs the ceremony.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    if not content or "<upaf:CreateFormTask" not in content:
        return

    for m in _CREATE_FORM_TASK_RE.finditer(content):
        attrs = m.group(1)
        if _dynamic_form_path_value(attrs) is not None:
            continue

        size = _inline_form_layout_size(attrs)
        if size < _INLINE_FORM_LAYOUT_SOFT_LIMIT:
            continue

        display_match = re.search(r'\sDisplayName="([^"]*)"', attrs)
        display = display_match.group(1) if display_match else "(no DisplayName)"
        result.warn(
            f"[AC-33] CreateFormTask '{display}' carries a {size}-char inline "
            f"FormLayout with DynamicFormPath={{x:Null}}. Studio's form "
            f"designer can't edit inline schemas and large FormLayout "
            f"attributes poison XAML diffs. Extract to a sibling file and "
            f"set DynamicFormPath=\"Forms/<name>.json\" — generators.py "
            f"exposes form_layout_to_external_file() for the shape conversion."
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


_CREATE_TASK_LOCAL_NAMES = frozenset({"CreateFormTask", "CreateExternalTask"})

# Loop scopes that indicate the Creates are already driven by a collection —
# AC-34 should stay silent for these (AC-27 already handles the "Wait nested
# inside ForEach" variant of this mistake).
_LOOP_SCOPES_FOR_AC34 = frozenset({
    "ForEach",
    "ForEachRow",
    "ForEachFileX",
    "ForEachFolderX",
    "ParallelForEach",
    "While",
    "DoWhile",
})

_ROW_INDEX_RE = re.compile(r"Rows\(\s*\d+\s*\)")
_TASK_OUTPUT_RE = re.compile(
    r'<(?:upaf|upae):Create(?:Form|External)Task\b[^>]*?\bTaskOutput="\[([^\]]+)\]"',
    flags=re.DOTALL,
)


def lint_unrolled_sequential_task_pairs(ctx, result):
    """AC-34: Unrolled / sequential per-item Create→Wait antipattern.

    Detects the shape where the workflow creates N tasks for N items but did NOT
    use a ForEach loop — either because it unrolled the collection into
    hardcoded `If Rows.Count >= N` / `Rows(0..N-1)` blocks, or because it
    repeated inline `Create → Wait` pairs at the flat Sequence level.

    In both cases the robot is tied up for the sum of the human wait times
    instead of the max, and the unrolled form additionally bypasses AC-27
    (which only fires on `Wait*AndResume` nested inside a loop scope).

    The fix is the Shadow Task Pattern: one ForEach over the collection that
    only creates tasks and appends to a List(Of FormTaskData), then a second
    ForEach over that list that runs Wait*AndResume + decision handling.
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    if not content:
        return
    if "CreateFormTask" not in content and "CreateExternalTask" not in content:
        return

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return

    parents = {child: parent for parent in root.iter() for child in parent}

    def has_loop_ancestor(elem):
        anc = parents.get(elem)
        while anc is not None:
            if _local_name(anc.tag) in _LOOP_SCOPES_FOR_AC34:
                return True
            anc = parents.get(anc)
        return False

    flat_creates = [
        elem for elem in root.iter()
        if _local_name(elem.tag) in _CREATE_TASK_LOCAL_NAMES
        and not has_loop_ancestor(elem)
    ]

    if len(flat_creates) < 2:
        return

    row_index_hits = len(_ROW_INDEX_RE.findall(content))
    task_outputs = _TASK_OUTPUT_RE.findall(content)
    reused_output = (
        len(task_outputs) >= 2 and len(set(task_outputs)) < len(task_outputs)
    )

    # Strong signal gates: fire only when we're confident this isn't a legitimate
    # two-step fixed pattern (e.g. "create a shadow summary task AND a main
    # review task for the same entity"). Three or more flat Creates, or row-
    # index unroll, or a shared TaskOutput variable reused across Creates — any
    # of these effectively rules out the two-step case.
    should_fire = (
        len(flat_creates) >= 3
        or row_index_hits >= 2
        or reused_output
    )
    if not should_fire:
        return

    hints = []
    if row_index_hits >= 2:
        hints.append(f"hardcoded Rows(N) index access ({row_index_hits} occurrences)")
    if reused_output:
        dup = next(
            (v for v in task_outputs if task_outputs.count(v) >= 2),
            None,
        )
        if dup:
            hints.append(
                f"TaskOutput variable '{dup}' reused across multiple Creates"
            )
    hint_suffix = f" ({'; '.join(hints)})" if hints else ""

    severity_error = row_index_hits >= 2 or len(flat_creates) >= 3
    emit = result.error if severity_error else result.warn

    emit(
        f"[AC-34] Found {len(flat_creates)} Create*Task activities at the flat "
        f"Sequence level with no ForEach/ForEachRow wrapper{hint_suffix}. This is "
        f"the sequential per-item antipattern — each task blocks the next, so the "
        f"robot is tied up for the sum of all human wait times instead of the max. "
        f"Use the Shadow Task Pattern: one ForEach over the collection that only "
        f"creates tasks and appends the FormTaskData to a List(Of FormTaskData), "
        f"then a second ForEach (directly under the root Sequence) that runs "
        f"WaitForFormTaskAndResume + decision handling per task. "
        f"See uipath-tasks/references/form-tasks.md → Shadow Task Pattern."
    )
