"""Tests for the idempotency guards and surfaced-error paths added on
fix/idempotency-modify-scaffold.

Three things are pinned here, each corresponding to one Track 5 finding:

1. cmd_insert_invoke idempotency — re-running with the same target
   WorkflowFileName must skip cleanly, NOT append a duplicate
   <ui:InvokeWorkflowFile> block. The synthesis report flagged this as
   the most likely silent-corrupt path.

2. _add_invoke_arg WireTargetMissing — when the target invoke is
   absent, the function must raise (not silent-warn-and-return). The
   regression bug was cmd_wire_uielement reporting success while the
   wiring did not happen.

3. _replace_gtd_body_for_dispatcher anchor-missing — when neither the
   performer RetryScope anchor nor the dispatcher SCAFFOLD marker are
   present, the function must raise RuntimeError. Already-applied
   re-runs (marker present) must remain silent skips.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import modify_framework
from modify_framework import (
    WireTargetMissing,
    _add_invoke_arg,
    cmd_insert_invoke,
)
import scaffold_project
from scaffold_project import _replace_gtd_body_for_dispatcher


# ---------------------------------------------------------------------------
# 1. cmd_insert_invoke idempotency
# ---------------------------------------------------------------------------

_MIN_FRAMEWORK_XAML = """\
<?xml version="1.0" encoding="utf-8"?>
<Activity x:Class="Test"
  xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities"
  xmlns:ui="http://schemas.uipath.com/workflow/activities"
  xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation"
  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
  <Sequence sap2010:WorkflowViewState.IdRef="Sequence_Main">
    <ui:LogMessage DisplayName="Bookend" Message="[&quot;START&quot;]"
      sap2010:WorkflowViewState.IdRef="LogMessage_1" />
  </Sequence>
</Activity>
"""

_INVOKE_SNIPPET = (
    '<ui:InvokeWorkflowFile DisplayName="Run Foo" '
    'WorkflowFileName="Workflows\\Foo.xaml" '
    'sap2010:WorkflowViewState.IdRef="InvokeWorkflowFile_99" />'
)


def test_cmd_insert_invoke_is_idempotent_on_same_target(tmp_path, capsys):
    fw = tmp_path / "InitAllApplications.xaml"
    fw.write_text(_MIN_FRAMEWORK_XAML, encoding="utf-8")

    assert cmd_insert_invoke(str(fw), _INVOKE_SNIPPET) is True
    after_first = fw.read_text(encoding="utf-8")
    first_count = after_first.count('WorkflowFileName="Workflows\\Foo.xaml"')
    assert first_count == 1, (
        f"first insert produced {first_count} invoke(s); expected exactly 1"
    )

    # Second call with the SAME target must be a clean no-op.
    capsys.readouterr()  # drain the first call's output
    assert cmd_insert_invoke(str(fw), _INVOKE_SNIPPET) is True
    after_second = fw.read_text(encoding="utf-8")
    second_count = after_second.count('WorkflowFileName="Workflows\\Foo.xaml"')
    assert second_count == 1, (
        f"second insert appended a duplicate — found {second_count} invoke(s); "
        f"the file should remain at 1 (idempotent)"
    )
    assert after_first == after_second, (
        "second insert mutated the file even though the target was already invoked"
    )

    captured = capsys.readouterr()
    assert "already invoked" in captured.out or "skipping" in captured.out, (
        f"second call did not log the skip; got: {captured.out!r}"
    )


# ---------------------------------------------------------------------------
# 2. _add_invoke_arg WireTargetMissing
# ---------------------------------------------------------------------------

def test_add_invoke_arg_raises_when_target_absent():
    """If the target InvokeWorkflowFile is not in `content`, raise — not warn."""
    content_no_invoke = (
        '<Activity><Sequence><ui:LogMessage Message="hello" /></Sequence></Activity>'
    )
    with pytest.raises(WireTargetMissing) as exc_info:
        _add_invoke_arg(
            content_no_invoke,
            workflow_filename="InitAllApplications.xaml",
            arg_key="out_uiApp",
            arg_type="ui:UiElement",
            direction="OutArgument",
            var_name="uiApp",
        )
    msg = str(exc_info.value)
    assert "InitAllApplications.xaml" in msg
    assert "out_uiApp" in msg


def test_add_invoke_arg_succeeds_when_target_present():
    """Sanity: when the target invoke exists, _add_invoke_arg returns mutated content."""
    content = (
        '<ui:InvokeWorkflowFile DisplayName="X" '
        'WorkflowFileName="InitAllApplications.xaml" '
        'sap2010:WorkflowViewState.IdRef="InvokeWorkflowFile_5">\n'
        '  <ui:InvokeWorkflowFile.Arguments>\n'
        '    <scg:Dictionary x:TypeArguments="x:String, Argument" />\n'
        '  </ui:InvokeWorkflowFile.Arguments>\n'
        '</ui:InvokeWorkflowFile>'
    )
    result = _add_invoke_arg(
        content,
        workflow_filename="InitAllApplications.xaml",
        arg_key="out_uiApp",
        arg_type="ui:UiElement",
        direction="OutArgument",
        var_name="uiApp",
    )
    assert 'x:Key="out_uiApp"' in result
    assert "[uiApp]" in result


# ---------------------------------------------------------------------------
# 3. _replace_gtd_body_for_dispatcher anchor-missing
# ---------------------------------------------------------------------------

_GTD_NEITHER_ANCHOR_NOR_MARKER = """\
<?xml version="1.0" encoding="utf-8"?>
<Activity x:Class="GetTransactionData"
  xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities"
  xmlns:ui="http://schemas.uipath.com/workflow/activities"
  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
  <Sequence>
    <!-- Template has drifted: no performer RetryScope, no dispatcher marker -->
    <ui:LogMessage Message="not the expected shape" />
  </Sequence>
</Activity>
"""

_GTD_ALREADY_APPLIED = """\
<?xml version="1.0" encoding="utf-8"?>
<Activity x:Class="GetTransactionData"
  xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities"
  xmlns:ui="http://schemas.uipath.com/workflow/activities"
  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
  <Sequence>
    <ui:Comment DisplayName="SCAFFOLD.DISPATCHER_LOAD_DATA" Text="..." />
  </Sequence>
</Activity>
"""


def test_replace_gtd_body_raises_on_anchor_missing(tmp_path):
    """Template drift: neither performer anchor nor dispatcher marker present."""
    gtd = tmp_path / "GetTransactionData.xaml"
    gtd.write_text(_GTD_NEITHER_ANCHOR_NOR_MARKER, encoding="utf-8")

    with pytest.raises(RuntimeError) as exc_info:
        _replace_gtd_body_for_dispatcher(gtd, "DataRow", "sd:DataRow")
    msg = str(exc_info.value)
    assert "anchor" in msg.lower() or "drift" in msg.lower()


def test_replace_gtd_body_silent_skip_when_already_applied(tmp_path, capsys):
    """Re-run on already-modified GTD must be a clean no-op (no exception)."""
    gtd = tmp_path / "GetTransactionData.xaml"
    original = _GTD_ALREADY_APPLIED
    gtd.write_text(original, encoding="utf-8")

    # Should NOT raise.
    _replace_gtd_body_for_dispatcher(gtd, "DataRow", "sd:DataRow")
    assert gtd.read_text(encoding="utf-8") == original, (
        "already-applied case mutated the file — expected silent skip"
    )

    captured = capsys.readouterr()
    assert "already applied" in captured.out or "skipping" in captured.out, (
        f"already-applied case did not log the skip; got: {captured.out!r}"
    )
