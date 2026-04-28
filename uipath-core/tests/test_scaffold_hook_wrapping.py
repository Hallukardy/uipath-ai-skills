"""Tests for the try/except wrapping around plugin scaffold hooks.

Track 4 of the deep-team review flagged that scaffold_project.py iterated
plugin scaffold hooks and called each raw, so a single buggy plugin's
exception aborted the entire scaffold (project.json write, Config.xlsx
customization, workflow files all skipped). The fix wraps each hook in
try/except. This test pins both halves: the scaffold survives a throwing
hook AND the warning surfaces on stderr naming the failing hook.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import scaffold_project
import plugin_loader


@pytest.fixture
def isolated_hooks(monkeypatch):
    """Replace the plugin_loader scaffold-hook registry for the duration of the test.

    Avoids leaking the test's hook into other tests in the same pytest
    session, and bypasses load_plugins() so the test does not depend on
    which plugins happen to be installed.
    """
    saved = list(plugin_loader._scaffold_hooks)
    monkeypatch.setattr(plugin_loader, "_scaffold_hooks", [])
    monkeypatch.setattr(plugin_loader, "load_plugins", lambda: [])
    yield plugin_loader._scaffold_hooks
    plugin_loader._scaffold_hooks.clear()
    plugin_loader._scaffold_hooks.extend(saved)


def test_throwing_scaffold_hook_does_not_abort_scaffold(
    isolated_hooks, tmp_path, capsys
):
    """A plugin hook that raises must be caught — scaffold must complete."""

    def busted_hook(project_json):
        raise RuntimeError("simulated plugin bug")

    isolated_hooks.append(busted_hook)

    out_dir = tmp_path / "ScaffoldedProject"
    scaffold_project.scaffold_project(
        name="ScaffoldedProject",
        description="hook-wrap test",
        output_dir=str(out_dir.parent),
        variant="sequence",
        extra_deps={"UiPath.System.Activities": "[25.12.2]"},
    )

    # The follow-up writes must have happened despite the hook throwing.
    pj = out_dir / "project.json"
    assert pj.exists(), "project.json was not written — scaffold aborted mid-run"

    pj_content = json.loads(pj.read_text(encoding="utf-8"))
    assert pj_content["name"] == "ScaffoldedProject", (
        "project.json was written but not customized — name field unchanged"
    )

    # The wrapper must surface a clear stderr warning naming the failing hook.
    captured = capsys.readouterr()
    assert "busted_hook" in captured.err, (
        f"stderr did not name the failing hook; got: {captured.err!r}"
    )
    assert "simulated plugin bug" in captured.err, (
        f"stderr did not include the original exception message; "
        f"got: {captured.err!r}"
    )


def test_well_behaved_scaffold_hook_still_runs(isolated_hooks, tmp_path):
    """Sanity: a non-throwing hook still mutates project.json."""
    sentinel_calls = []

    def good_hook(project_json):
        sentinel_calls.append(project_json["name"])
        project_json["dependencies"]["UiPath.Test.Plugin.Marker"] = "[1.0.0]"

    isolated_hooks.append(good_hook)

    out_dir = tmp_path / "GoodHookProject"
    scaffold_project.scaffold_project(
        name="GoodHookProject",
        description="hook-wrap good-hook test",
        output_dir=str(out_dir.parent),
        variant="sequence",
        extra_deps={"UiPath.System.Activities": "[25.12.2]"},
    )

    assert sentinel_calls == ["GoodHookProject"], (
        "non-throwing hook was not invoked"
    )

    pj_content = json.loads((out_dir / "project.json").read_text(encoding="utf-8"))
    assert "UiPath.Test.Plugin.Marker" in pj_content["dependencies"], (
        "non-throwing hook mutation was not preserved in project.json"
    )
