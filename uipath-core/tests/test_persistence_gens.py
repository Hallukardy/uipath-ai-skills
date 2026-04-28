"""Tests for persistence activity generators (UiPath.Persistence.Activities/1.4)."""
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "uipath-core" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_activities import persistence  # noqa: E402


NS_DECLS = (
    'xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities" '
    'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
    'xmlns:upat="clr-namespace:UiPath.Persistence.Activities.Tasks" '
    'xmlns:upae="clr-namespace:UiPath.Persistence.Activities.ExternalTask" '
    'xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask" '
    'xmlns:upau="clr-namespace:UiPath.Persistence.Activities.UserAction" '
    'xmlns:scg="clr-namespace:System.Collections.Generic"'
)


def _wrap_and_parse(xaml_fragment: str) -> ET.Element:
    """Wrap fragment in a synthetic root with all needed xmlns and parse."""
    return ET.fromstring(f"<root {NS_DECLS}>{xaml_fragment}</root>")


# Each tuple: (gen_fn, expected_local_tag, kwargs)
CASES = [
    (persistence.gen_assigntasks, "AssignTasks",
     {"task_objects_variable": "tasks", "user_name_or_email": "u@example.com"}),
    (persistence.gen_forwardtask, "ForwardTask",
     {"task_id_variable": "tid", "user_name_or_email": "u@example.com"}),
    (persistence.gen_createexternaltask, "CreateExternalTask",
     {"task_output_variable": "task", "task_title": "T",
      "task_data": {"k": "vexpr"}}),
    (persistence.gen_waitforexternaltaskandresume, "WaitForExternalTaskAndResume",
     {"task_input_variable": "task"}),
    (persistence.gen_createformtask, "CreateFormTask",
     {"task_output_variable": "task", "task_title": "T"}),
    (persistence.gen_getformtasks, "GetFormTasks",
     {"task_objects_variable": "lis"}),
    (persistence.gen_waitforformtaskandresume, "WaitForFormTaskAndResume",
     {"task_input_variable": "ac"}),
    (persistence.gen_getapptasks, "GetAppTasks",
     {"task_objects_variable": "tasks"}),
    (persistence.gen_waitforuseractionandresume, "WaitForUserActionAndResume",
     {"task_input_variable": "tasks.First"}),
]


@pytest.mark.parametrize("gen_fn,local_tag,kwargs", CASES,
                         ids=[c[1] for c in CASES])
def test_emits_expected_tag_and_parses(gen_fn, local_tag, kwargs):
    out = gen_fn(**kwargs)
    assert out, f"{gen_fn.__name__} returned empty output"
    assert local_tag in out, f"{gen_fn.__name__} output missing tag <...:{local_tag}>"
    # XML must be well-formed when wrapped in a root with namespace decls
    root = _wrap_and_parse(out)
    # The activity element should be a direct child or inside a structural wrapper
    found = [el for el in root.iter() if el.tag.endswith("}" + local_tag)]
    assert found, f"{gen_fn.__name__} produced no parseable element matching {local_tag}"


def test_assigntasks_rejects_invalid_assignment_type():
    with pytest.raises(ValueError, match="Invalid TaskAssignmentType"):
        persistence.gen_assigntasks(task_assignment_type="Bogus")


def test_createexternaltask_rejects_invalid_priority():
    with pytest.raises(ValueError, match="Invalid TaskPriority"):
        persistence.gen_createexternaltask(task_priority="Bogus")


def test_createformtask_rejects_invalid_priority():
    with pytest.raises(ValueError, match="Invalid TaskPriority"):
        persistence.gen_createformtask(task_priority="Bogus")


def test_createexternaltask_renders_taskdata_collection():
    out = persistence.gen_createexternaltask(
        task_output_variable="task",
        task_data={"alpha": "exprA", "beta": "exprB"},
    )
    assert "<upae:CreateExternalTask.TaskData>" in out
    assert 'x:Key="alpha"' in out
    assert 'x:Key="beta"' in out
    assert "[exprA]" in out and "[exprB]" in out


def test_createformtask_default_form_layout_present():
    out = persistence.gen_createformtask()
    # Default layout has the Submit button literal
    assert "&quot;Submit&quot;" in out
    # Empty FormData dictionary is the default
    assert '<scg:Dictionary x:TypeArguments="x:String, Argument" />' in out


def test_snake_case_aliases_are_callable():
    # Aliases must point to the same canonical functions
    assert persistence.gen_assign_tasks is persistence.gen_assigntasks
    assert persistence.gen_forward_task is persistence.gen_forwardtask
    assert persistence.gen_create_external_task is persistence.gen_createexternaltask
    assert persistence.gen_wait_for_external_task_and_resume is persistence.gen_waitforexternaltaskandresume
    assert persistence.gen_create_form_task is persistence.gen_createformtask
    assert persistence.gen_get_form_tasks is persistence.gen_getformtasks
    assert persistence.gen_wait_for_form_task_and_resume is persistence.gen_waitforformtaskandresume
    assert persistence.gen_get_app_tasks is persistence.gen_getapptasks
    assert persistence.gen_wait_for_user_action_and_resume is persistence.gen_waitforuseractionandresume
