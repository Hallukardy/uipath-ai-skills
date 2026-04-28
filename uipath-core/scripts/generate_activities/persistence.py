"""Persistence activity generators (UiPath.Persistence.Activities/1.4).

Covers the 9 long-running task / suspend-resume primitives shipped by
UiPath.Persistence.Activities. Activities split across four sub-namespaces:
  - upat: UiPath.Persistence.Activities.Tasks         (AssignTasks, ForwardTask)
  - upae: UiPath.Persistence.Activities.ExternalTask  (CreateExternalTask, WaitForExternalTaskAndResume)
  - upaf: UiPath.Persistence.Activities.FormTask      (CreateFormTask, GetFormTasks, WaitForFormTaskAndResume)
  - upau: UiPath.Persistence.Activities.UserAction    (GetAppTasks, WaitForUserActionAndResume)

Naming convention: the canonical `def` matches `gen_<lower(activity)>` with no
underscore insertion (matches audit_coverage.py:213's lookup). Snake_case
aliases are provided as `=` assignments for ergonomic callers; assignments
are invisible to the audit's AST scan so they don't double-count.
"""
from ._helpers import _escape_xml_attr, _escape_vb_expr


def _attr_or_null(value, attr_name, vb_expr=False):
    """Render `Attr="[expr]"` for non-empty value, else `Attr="{x:Null}"`."""
    if value is None or value == "":
        return f'{attr_name}="{{x:Null}}"'
    if vb_expr:
        return f'{attr_name}="[{_escape_vb_expr(str(value))}]"'
    return f'{attr_name}="{_escape_xml_attr(str(value))}"'


# ---------------------------------------------------------------------------
# upat: Tasks
# ---------------------------------------------------------------------------

def gen_assigntasks(task_objects_variable="", user_name_or_email="",
                    task_id_variable="", failed_assignments_variable="",
                    user_assignments_variable="", timeout_ms="",
                    task_assignment_type="Assign",
                    enable_multiple_assignments=False,
                    display_name="Assign Tasks",
                    indent="    "):
    """Generate <upat:AssignTasks/>.

    Bulk-assigns or reassigns app/form tasks to users. TaskAssignmentType is
    one of "Assign" or "Reassign".
    """
    if task_assignment_type not in ("Assign", "Reassign"):
        raise ValueError(f"Invalid TaskAssignmentType: {task_assignment_type}")
    dn = _escape_xml_attr(display_name)
    em = "True" if enable_multiple_assignments else "False"
    parts = [
        _attr_or_null(failed_assignments_variable, "FailedTaskAssignments", vb_expr=True),
        _attr_or_null(task_id_variable, "TaskId", vb_expr=True),
        _attr_or_null(user_assignments_variable, "TaskUserAssignments", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(user_name_or_email, "UserNameOrEmail", vb_expr=True),
        f'EnableMultipleAssignments="{em}"',
        'MigrateV144="False"',
        f'TaskAssignmentType="{task_assignment_type}"',
        f'DisplayName="{dn}"',
    ]
    if task_objects_variable:
        parts.append(f'TaskObjects="[{_escape_vb_expr(task_objects_variable)}]"')
    return f'{indent}<upat:AssignTasks {" ".join(parts)} />'


def gen_forwardtask(task_id_variable="", user_name_or_email="",
                    comments="", timeout_ms="",
                    display_name="Forward Task",
                    indent="    "):
    """Generate <upat:ForwardTask/>."""
    dn = _escape_xml_attr(display_name)
    parts = [
        _attr_or_null(comments, "Comments", vb_expr=True),
        _attr_or_null(task_id_variable, "TaskId", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(user_name_or_email, "UserNameOrEmail", vb_expr=True),
        f'DisplayName="{dn}"',
    ]
    return f'{indent}<upat:ForwardTask {" ".join(parts)} />'


# ---------------------------------------------------------------------------
# upae: ExternalTask
# ---------------------------------------------------------------------------

def gen_createexternaltask(task_output_variable="task", task_title="External Task",
                           task_priority="Medium", user_name_or_email="",
                           external_tag="", group="", labels="",
                           task_catalog="", timeout_ms="",
                           task_data=None, assignment_criteria_xaml="",
                           display_name="Create External Task",
                           indent="    "):
    """Generate <upae:CreateExternalTask/>.

    task_data: optional dict of {key: vb_expression} rendered as
      <upae:CreateExternalTask.TaskData><InArgument x:TypeArguments="x:String" x:Key="...">[expr]</InArgument>...</upae:CreateExternalTask.TaskData>
    assignment_criteria_xaml: optional pre-rendered <upat:Criteria .../> XML;
      caller is responsible for matching the harvested shape.
    """
    if task_priority not in ("Low", "Medium", "High", "Critical"):
        raise ValueError(f"Invalid TaskPriority: {task_priority}")
    dn = _escape_xml_attr(display_name)
    title = _escape_xml_attr(task_title)
    parts = [
        _attr_or_null(external_tag, "ExternalTag", vb_expr=True),
        _attr_or_null(group, "Group", vb_expr=True),
        _attr_or_null(labels, "Labels", vb_expr=True),
        _attr_or_null(task_catalog, "TaskCatalog", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(user_name_or_email, "UserNameOrEmail", vb_expr=True),
        f'DisplayName="{dn}"',
        f'TaskOutput="[{_escape_vb_expr(task_output_variable)}]"',
        f'TaskPriority="{task_priority}"',
        f'TaskTitle="{title}"',
    ]
    inner = ""
    ii = indent + "  "
    iii = ii + "  "
    if assignment_criteria_xaml:
        inner += f"\n{ii}<upae:CreateExternalTask.AssignmentCriteria>\n{assignment_criteria_xaml}\n{ii}</upae:CreateExternalTask.AssignmentCriteria>"
    if task_data:
        rows = "\n".join(
            f'{iii}<InArgument x:TypeArguments="x:String" x:Key="{_escape_xml_attr(k)}">[{_escape_vb_expr(v)}]</InArgument>'
            for k, v in task_data.items()
        )
        inner += f"\n{ii}<upae:CreateExternalTask.TaskData>\n{rows}\n{ii}</upae:CreateExternalTask.TaskData>"
    if not inner:
        return f'{indent}<upae:CreateExternalTask {" ".join(parts)} />'
    return f'{indent}<upae:CreateExternalTask {" ".join(parts)}>{inner}\n{indent}</upae:CreateExternalTask>'


def gen_waitforexternaltaskandresume(task_input_variable="task",
                                     task_output_variable="",
                                     task_action_variable="",
                                     status_message_variable="",
                                     wait_item_data_object_variable="",
                                     timeout_ms="",
                                     display_name="Wait For External Task and Resume",
                                     indent="    "):
    """Generate <upae:WaitForExternalTaskAndResume/>."""
    dn = _escape_xml_attr(display_name)
    parts = [
        _attr_or_null(status_message_variable, "StatusMessage", vb_expr=True),
        _attr_or_null(task_action_variable, "TaskAction", vb_expr=True),
        _attr_or_null(task_output_variable, "TaskOutput", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(wait_item_data_object_variable, "WaitItemDataObject", vb_expr=True),
        f'DisplayName="{dn}"',
        f'TaskInput="[{_escape_vb_expr(task_input_variable)}]"',
    ]
    return f'{indent}<upae:WaitForExternalTaskAndResume {" ".join(parts)} />'


# ---------------------------------------------------------------------------
# upaf: FormTask
# ---------------------------------------------------------------------------

# Default empty FormLayout — single-cell submit button table. Mirrors the
# minimal harvest. Caller can override with their own JSON.
_DEFAULT_FORM_LAYOUT = (
    '%[{&quot;mask&quot;:false,&quot;customClass&quot;:&quot;uipath-button-container&quot;,'
    '&quot;tableView&quot;:true,&quot;alwaysEnabled&quot;:false,&quot;type&quot;:&quot;table&quot;,'
    '&quot;input&quot;:false,&quot;key&quot;:&quot;key&quot;,&quot;label&quot;:&quot;label&quot;,'
    '&quot;rows&quot;:[[{&quot;components&quot;:[{&quot;type&quot;:&quot;button&quot;,'
    '&quot;label&quot;:&quot;Submit&quot;,&quot;key&quot;:&quot;submit&quot;,'
    '&quot;disableOnInvalid&quot;:true,&quot;input&quot;:true,&quot;alwaysEnabled&quot;:false,'
    '&quot;tableView&quot;:true}]},{&quot;components&quot;:[]},{&quot;components&quot;:[]},'
    '{&quot;components&quot;:[]},{&quot;components&quot;:[]},{&quot;components&quot;:[]}]],'
    '&quot;numRows&quot;:1,&quot;numCols&quot;:6,&quot;reorder&quot;:false}]'
)


def gen_createformtask(task_output_variable="actask", task_title="Form Task",
                       task_priority="Medium", form_layout=None,
                       user_name_or_email="", task_catalog="",
                       external_tag="", group="", labels="",
                       timeout_ms="", form_data=None,
                       assignment_criteria_xaml="",
                       enable_dynamic_forms=False, generate_input_fields=True,
                       display_name="Create Form Task",
                       indent="    "):
    """Generate <upaf:CreateFormTask/>.

    form_layout: caller-supplied JSON literal for the form (already XML-escaped),
      or None for a minimal single-button layout.
    form_data: optional dict of {key: vb_expr} for the FormData dictionary.
    """
    if task_priority not in ("Low", "Medium", "High", "Critical"):
        raise ValueError(f"Invalid TaskPriority: {task_priority}")
    dn = _escape_xml_attr(display_name)
    title = _escape_xml_attr(task_title)
    layout = form_layout if form_layout is not None else _DEFAULT_FORM_LAYOUT
    edf = "True" if enable_dynamic_forms else "False"
    gif = "True" if generate_input_fields else "False"
    parts = [
        'BucketFolderPath="{x:Null}"',
        'BucketName="{x:Null}"',
        'BulkFormLayout="{x:Null}"',
        'DynamicFormPath="{x:Null}"',
        _attr_or_null(external_tag, "ExternalTag", vb_expr=True),
        _attr_or_null(group, "Group", vb_expr=True),
        _attr_or_null(labels, "Labels", vb_expr=True),
        _attr_or_null(task_catalog, "TaskCatalog", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(user_name_or_email, "UserNameOrEmail", vb_expr=True),
        f'DisplayName="{dn}"',
        'EnableBulkEdit="False"',
        f'EnableDynamicForms="{edf}"',
        'EnableV2="False"',
        f'FormLayout="{layout}"',
        f'GenerateInputFields="{gif}"',
        f'TaskOutput="[{_escape_vb_expr(task_output_variable)}]"',
        f'TaskPriority="{task_priority}"',
        f'TaskTitle="{title}"',
    ]
    ii = indent + "  "
    iii = ii + "  "
    inner = ""
    if assignment_criteria_xaml:
        inner += f"\n{ii}<upaf:CreateFormTask.AssignmentCriteria>\n{assignment_criteria_xaml}\n{ii}</upaf:CreateFormTask.AssignmentCriteria>"
    # FormData child element. Empty by default to mirror harvest shape.
    if form_data:
        rows = "\n".join(
            f'{iii}<InArgument x:TypeArguments="x:String" x:Key="{_escape_xml_attr(k)}">[{_escape_vb_expr(v)}]</InArgument>'
            for k, v in form_data.items()
        )
        inner += f"\n{ii}<upaf:CreateFormTask.FormData>\n{iii}<scg:Dictionary x:TypeArguments=\"x:String, Argument\">\n{rows}\n{iii}</scg:Dictionary>\n{ii}</upaf:CreateFormTask.FormData>"
    else:
        inner += f"\n{ii}<upaf:CreateFormTask.FormData>\n{iii}<scg:Dictionary x:TypeArguments=\"x:String, Argument\" />\n{ii}</upaf:CreateFormTask.FormData>"
    return f'{indent}<upaf:CreateFormTask {" ".join(parts)}>{inner}\n{indent}</upaf:CreateFormTask>'


def gen_getformtasks(task_objects_variable="lisRetrievedTasks",
                     task_catalog_name="", filter_expr="", select="",
                     order_by="", expand="", top="", skip="",
                     timeout_ms="",
                     display_name="Get Form Tasks",
                     indent="    "):
    """Generate <upaf:GetFormTasks/>."""
    dn = _escape_xml_attr(display_name)
    parts = [
        _attr_or_null(expand, "Expand", vb_expr=True),
        _attr_or_null(filter_expr, "Filter", vb_expr=True),
        _attr_or_null(order_by, "OrderBy", vb_expr=True),
        _attr_or_null(select, "Select", vb_expr=True),
        _attr_or_null(skip, "Skip", vb_expr=True),
        _attr_or_null(task_catalog_name, "TaskCatalogName", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(top, "Top", vb_expr=True),
        f'DisplayName="{dn}"',
        f'TaskObjects="[{_escape_vb_expr(task_objects_variable)}]"',
    ]
    return f'{indent}<upaf:GetFormTasks {" ".join(parts)} />'


def gen_waitforformtaskandresume(task_input_variable="actask",
                                 task_output_variable="taskObjectOutput",
                                 task_action_variable="",
                                 status_message_variable="",
                                 wait_item_data_object_variable="",
                                 timeout_ms="",
                                 display_name="Wait for Form Task and Resume",
                                 indent="    "):
    """Generate <upaf:WaitForFormTaskAndResume/>."""
    dn = _escape_xml_attr(display_name)
    parts = [
        _attr_or_null(status_message_variable, "StatusMessage", vb_expr=True),
        _attr_or_null(task_action_variable, "TaskAction", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(wait_item_data_object_variable, "WaitItemDataObject", vb_expr=True),
        f'DisplayName="{dn}"',
        f'TaskInput="[{_escape_vb_expr(task_input_variable)}]"',
        f'TaskOutput="[{_escape_vb_expr(task_output_variable)}]"',
    ]
    return f'{indent}<upaf:WaitForFormTaskAndResume {" ".join(parts)} />'


# ---------------------------------------------------------------------------
# upau: UserAction
# ---------------------------------------------------------------------------

def gen_getapptasks(task_objects_variable="tasks", task_catalog_name="",
                    filter_expr="", select="", order_by="", expand="",
                    top="", skip="", timeout_ms="",
                    display_name="Get App Tasks",
                    indent="    "):
    """Generate <upau:GetAppTasks/>."""
    dn = _escape_xml_attr(display_name)
    parts = [
        _attr_or_null(expand, "Expand", vb_expr=True),
        _attr_or_null(filter_expr, "Filter", vb_expr=True),
        _attr_or_null(order_by, "OrderBy", vb_expr=True),
        _attr_or_null(select, "Select", vb_expr=True),
        _attr_or_null(skip, "Skip", vb_expr=True),
        _attr_or_null(task_catalog_name, "TaskCatalogName", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(top, "Top", vb_expr=True),
        f'DisplayName="{dn}"',
        f'TaskObjects="[{_escape_vb_expr(task_objects_variable)}]"',
    ]
    return f'{indent}<upau:GetAppTasks {" ".join(parts)} />'


def gen_waitforuseractionandresume(task_input_variable="tasks.First",
                                   task_output_variable="",
                                   task_action_variable="",
                                   status_message_variable="",
                                   wait_item_data_object_variable="",
                                   timeout_ms="",
                                   display_name="Wait For App Task and Resume",
                                   indent="    "):
    """Generate <upau:WaitForUserActionAndResume/>."""
    dn = _escape_xml_attr(display_name)
    parts = [
        _attr_or_null(status_message_variable, "StatusMessage", vb_expr=True),
        _attr_or_null(task_action_variable, "TaskAction", vb_expr=True),
        _attr_or_null(task_output_variable, "TaskOutput", vb_expr=True),
        _attr_or_null(timeout_ms, "TimeoutMs", vb_expr=True),
        _attr_or_null(wait_item_data_object_variable, "WaitItemDataObject", vb_expr=True),
        f'DisplayName="{dn}"',
        f'TaskInput="[{_escape_vb_expr(task_input_variable)}]"',
    ]
    return f'{indent}<upau:WaitForUserActionAndResume {" ".join(parts)} />'


# ---------------------------------------------------------------------------
# Snake_case aliases (= assignments, invisible to audit's AST scan)
# ---------------------------------------------------------------------------
gen_assign_tasks = gen_assigntasks
gen_forward_task = gen_forwardtask
gen_create_external_task = gen_createexternaltask
gen_wait_for_external_task_and_resume = gen_waitforexternaltaskandresume
gen_create_form_task = gen_createformtask
gen_get_form_tasks = gen_getformtasks
gen_wait_for_form_task_and_resume = gen_waitforformtaskandresume
gen_get_app_tasks = gen_getapptasks
gen_wait_for_user_action_and_resume = gen_waitforuseractionandresume
