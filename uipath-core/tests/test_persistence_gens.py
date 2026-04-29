"""Contract tests for the persistence audit-coverage stub.

`uipath-core/scripts/generate_activities/persistence.py` is an AUDIT-STUB-ONLY
module: its 9 `gen_*` functions exist solely to satisfy
`audit_coverage.collect_hand_written_gens()`'s AST scan, NOT to emit XAML.

The live generator path runs through `uipath-tasks/extensions/`. These tests
pin the new contract: every `gen_*` in this module must raise
`NotImplementedError` with a pointer to the live path, so any direct caller
gets a loud failure instead of structurally broken XAML.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "uipath-core" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_activities import persistence  # noqa: E402


# The 9 audit-required gen_* names. If this list shrinks, the audit coverage
# scan will reclassify Persistence as uncovered and exit-code-3 the hardening
# guard. If it grows, the new function must also raise.
PERSISTENCE_GEN_NAMES = [
    "gen_assigntasks",
    "gen_forwardtask",
    "gen_createexternaltask",
    "gen_waitforexternaltaskandresume",
    "gen_createformtask",
    "gen_getformtasks",
    "gen_waitforformtaskandresume",
    "gen_getapptasks",
    "gen_waitforuseractionandresume",
]


def test_all_audit_required_names_present():
    """Audit AST scan looks for these `def gen_*` names by string. Must persist."""
    for name in PERSISTENCE_GEN_NAMES:
        assert hasattr(persistence, name), (
            f"persistence.{name} missing — audit_coverage.collect_hand_written_gens "
            "will reclassify UiPath.Persistence.Activities as uncovered."
        )
        assert callable(getattr(persistence, name))


@pytest.mark.parametrize("name", PERSISTENCE_GEN_NAMES)
def test_gen_raises_not_implemented(name):
    """Every audit-stub `gen_*` must refuse to run — direct calls produce
    silently broken XAML otherwise (no IdRef, no HintSize)."""
    fn = getattr(persistence, name)
    with pytest.raises(NotImplementedError) as exc_info:
        fn()
    msg = str(exc_info.value)
    assert "AUDIT COVERAGE STUB" in msg, (
        f"{name} raised NotImplementedError but missing AUDIT COVERAGE STUB "
        f"banner: {msg}"
    )
    assert "uipath-tasks/extensions" in msg, (
        f"{name} error message does not point at the live generator path: {msg}"
    )


def test_gen_raises_with_args_and_kwargs():
    """Stubs accept *args/**kwargs and still raise — defends against signature
    introspection callers who pass real arguments."""
    with pytest.raises(NotImplementedError):
        persistence.gen_createformtask(
            task_output_variable="task",
            task_title="Some title",
            indent="    ",
        )


def test_audit_stub_helper_includes_activity_name():
    """Activity name must thread through to the error message so the failing
    caller knows which symbol to replace."""
    with pytest.raises(NotImplementedError) as exc_info:
        persistence._audit_stub("MadeUpActivity")
    assert "MadeUpActivity" in str(exc_info.value)
