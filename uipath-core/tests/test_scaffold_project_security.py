"""Security tests for `scaffold_project.scaffold_project()`.

Pins M-Sec-3 / C-1 from the v2 review: `--name` must be rejected (before any
filesystem op) when it contains path separators, `..`, NUL bytes, drive-relative
forms, Windows reserved device names, trailing dot/space, or is empty/whitespace.
Otherwise an agent-pipeline caller passing a user-controlled project name can
trigger `shutil.rmtree` (under `--overwrite`) on an unintended directory.
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
# before any filesystem op. Each entry is exercised against `--overwrite=True`
# to confirm rejection happens at the validator, not at the rmtree call.
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

    # The new positive-allowlist validator rejects with one of several messages
    # ("--name must match ...", "--name must not be ...", "--name must not be empty ...").
    # All start with "--name must" — pin on that stable prefix and on the repr.
    assert "--name must" in str(exc_info.value)
    assert repr(bad_name) in str(exc_info.value) or bad_name in ("", "..")
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
        if "--name must" in str(e):
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
        if "--name must" in str(e):
            pytest.fail(
                f"validator over-rejected literal name 'foo..bar': {e}"
            )
        raise


# -----------------------------------------------------------------------------
# C-1: positive allowlist for `--name`
# -----------------------------------------------------------------------------


class TestNameAllowlist:
    """Pins C-1: `--name` accepts only [A-Za-z0-9][A-Za-z0-9._-]{0,99} and is
    further restricted against Windows reserved device names, trailing dot/space,
    NUL bytes, empty/whitespace, and bare `.` / `..`.

    Each rejection path is exercised against `--overwrite=True` to prove the
    rejection is structural (validator) and not incidental (rmtree side-effect).
    """

    # Each input MUST be rejected with ValueError before any filesystem op.
    _REJECTED = [
        # Empty / whitespace-only
        "",
        "   ",
        "\t",
        # Bare relative segments
        ".",
        "..",
        # Drive-relative (Windows) — pathlib drops LHS, blast-radius escape
        "C:foo",
        "Z:bar",
        # Path separators
        "foo/bar",
        "foo\\bar",
        # Windows reserved device names (case-insensitive, with/without ext)
        "CON",
        "con",
        "PRN",
        "AUX",
        "NUL",
        "nul.txt",
        "COM1",
        "COM9",
        "com5.log",
        "LPT1",
        "LPT9",
        "lpt3.dat",
        # Trailing dot or space — silently stripped by Windows -> alias collision
        "foo ",
        "foo.",
        "MyProject ",
        "MyProject.",
        # NUL byte / control chars
        "foo\x00bar",
        "foo\x01bar",
        "foo\nbar",
        # Leading punctuation (regex requires alnum first)
        ".hidden",
        "-flag",
        "_priv",
        # Spaces inside (regex disallows)
        "my project",
    ]

    @pytest.mark.parametrize("bad_name", _REJECTED)
    def test_name_rejected(self, tmp_path, bad_name):
        sentinel = tmp_path / "should_not_be_touched"
        sentinel.mkdir()
        marker = sentinel / "marker.txt"
        marker.write_text("intact", encoding="utf-8")

        with pytest.raises(ValueError) as exc_info:
            scaffold_project(
                name=bad_name,
                description="Test",
                output_dir=str(tmp_path),
                variant="sequence",
                overwrite=True,
            )

        # All rejections share the "--name must" stable prefix.
        assert "--name must" in str(exc_info.value)
        # Sentinel survives — validator ran before any rmtree.
        assert marker.exists()
        assert marker.read_text(encoding="utf-8") == "intact"

    # Names that MUST be accepted (validator is not over-broad).
    _ACCEPTED = [
        "MyProject",
        "my-project_v2",
        "a",
        "X.Y.Z",
        "foo..bar",  # literal `..` inside a single segment, not a traversal
        "Project123",
        "v1.0.0",
    ]

    @pytest.mark.parametrize("good_name", _ACCEPTED)
    def test_name_accepted(self, tmp_path, good_name):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        # Should not raise on the validator. Downstream FileNotFoundError from
        # missing template assets in the test env is expected and ignored.
        try:
            scaffold_project(
                name=good_name,
                description="Test",
                output_dir=str(out_dir),
                variant="sequence",
                overwrite=True,
            )
        except FileNotFoundError:
            pass
        except ValueError as e:
            if "--name must" in str(e):
                pytest.fail(
                    f"validator over-rejected clean name {good_name!r}: {e}"
                )
            raise

    def test_name_at_max_length_accepted(self, tmp_path):
        """Boundary: 100-char name (1 leading alnum + 99 inner chars) is accepted."""
        good = "A" + ("b" * 99)
        assert len(good) == 100
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        try:
            scaffold_project(
                name=good,
                description="Test",
                output_dir=str(out_dir),
                variant="sequence",
                overwrite=True,
            )
        except FileNotFoundError:
            pass
        except ValueError as e:
            if "--name must" in str(e):
                pytest.fail(f"validator over-rejected 100-char name: {e}")
            raise

    def test_name_over_max_length_rejected(self, tmp_path):
        """Boundary: 101-char name exceeds {0,99} inner-char budget."""
        bad = "A" + ("b" * 100)
        assert len(bad) == 101
        with pytest.raises(ValueError) as exc_info:
            scaffold_project(
                name=bad,
                description="Test",
                output_dir=str(tmp_path),
                variant="sequence",
                overwrite=True,
            )
        assert "--name must" in str(exc_info.value)


# -----------------------------------------------------------------------------
# M-4: --overwrite must not follow symlinks/junctions outside output_dir
# -----------------------------------------------------------------------------


class TestOverwriteSymlinkSafety:
    """Pins M-4: when output_dir/<name> is a symlink, --overwrite must NOT
    rmtree the symlink target. Either unlink the symlink in place, or refuse
    when the target resolves outside output_dir.
    """

    def test_overwrite_symlink_does_not_delete_target_contents(self, tmp_path):
        """A symlink at output_dir/<name> pointing to a sibling directory must
        not be followed: the sibling's contents must survive --overwrite."""
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        # Sibling directory — outside out_dir — that an attacker wants to nuke.
        sibling = tmp_path / "sibling_data"
        sibling.mkdir()
        marker = sibling / "important.txt"
        marker.write_text("must_survive", encoding="utf-8")

        # Place a symlink at out_dir/MyProject pointing at sibling.
        link = out_dir / "MyProject"
        try:
            link.symlink_to(sibling, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted in this environment")

        # Run scaffold with --overwrite. The validator accepts MyProject;
        # the rmtree path must NOT traverse the symlink.
        try:
            scaffold_project(
                name="MyProject",
                description="Test",
                output_dir=str(out_dir),
                variant="sequence",
                overwrite=True,
            )
        except (FileNotFoundError, PermissionError, OSError):
            # Template asset missing or refusal — both are acceptable for this
            # test; what matters is that the sibling marker survives.
            pass

        # The link itself may be gone (unlinked) or replaced by a real
        # directory; either is fine. The sibling's contents must remain.
        assert marker.exists(), "scaffold --overwrite traversed a symlink and deleted target contents"
        assert marker.read_text(encoding="utf-8") == "must_survive"
