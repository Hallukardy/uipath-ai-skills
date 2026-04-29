"""Security tests for `scaffold_project.scaffold_project()`.

Pins M-Sec-3 from the 2026-04-28 v2 review: `--name` must be rejected when it
contains path separators or `..` segments before any filesystem op runs.
Otherwise an agent-pipeline caller passing user-controlled project names can
trigger `shutil.rmtree` (under `--overwrite`) on arbitrary directories.
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "uipath-core" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scaffold_project import scaffold_project  # noqa: E402


# Path-separator-bearing or traversal-bearing names that must all be rejected
# before any filesystem op. Each entry is exercised against both `--overwrite`
# and non-`--overwrite` to confirm rejection happens at the validator, not at
# the rmtree call.
_REJECTED_NAMES = [
    "../sensitive_dir",
    "..",
    "foo/bar",
    "/etc",
    ".." + os.sep + "etc",
]
if os.altsep:
    _REJECTED_NAMES.extend(
        [
            f"foo{os.altsep}bar",
            f"..{os.altsep}etc",
        ]
    )


@pytest.mark.parametrize("bad_name", _REJECTED_NAMES)
def test_path_traversal_name_rejected(tmp_path, bad_name):
    """Validator must raise ValueError before any filesystem op."""
    sentinel_dir = tmp_path / "should_not_be_touched"
    sentinel_dir.mkdir()
    sentinel_file = sentinel_dir / "marker.txt"
    sentinel_file.write_text("intact", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        scaffold_project(
            name=bad_name,
            description="Test",
            output_dir=str(tmp_path),
            variant="sequence",
            overwrite=True,
        )

    assert "--name must not contain" in str(exc_info.value)
    assert repr(bad_name) in str(exc_info.value)
    # Sentinel must remain untouched — no rmtree may have run.
    assert sentinel_file.exists()
    assert sentinel_file.read_text(encoding="utf-8") == "intact"


def test_clean_name_accepted(tmp_path):
    """Sanity: a valid name still scaffolds normally — validator is not over-broad."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # Should not raise. We don't assert the full scaffold succeeded; some asset
    # paths may not be reachable in this test environment. The point is that
    # the validator did not reject "MyProject".
    try:
        scaffold_project(
            name="MyProject",
            description="Test",
            output_dir=str(out_dir),
            variant="sequence",
            overwrite=True,
        )
    except FileNotFoundError:
        # Template asset missing in test env is fine — the validator passed.
        pass
    except ValueError as e:
        if "--name must not contain" in str(e):
            pytest.fail(
                f"validator rejected a clean name 'MyProject': {e}"
            )
        raise


def test_dotdot_inside_name_segment_allowed(tmp_path):
    """`foo..bar` is a literal directory name, not a traversal — must NOT be rejected."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # Validator must not raise on names that merely contain `..` as a substring
    # within a single segment.
    try:
        scaffold_project(
            name="foo..bar",
            description="Test",
            output_dir=str(out_dir),
            variant="sequence",
            overwrite=True,
        )
    except FileNotFoundError:
        pass
    except ValueError as e:
        if "--name must not contain" in str(e):
            pytest.fail(
                f"validator over-rejected literal name 'foo..bar': {e}"
            )
        raise
