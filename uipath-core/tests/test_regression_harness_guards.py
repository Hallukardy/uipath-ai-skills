"""Tests for the silent-pass guards in regression_test.test_golden_templates.

Track 6 of the deep-team review flagged that test_golden_templates parsed
the validator's SUMMARY line via regex and silently reported OK when the
regex never matched (all_total stayed 0, the only assertion 0 != 0 was
trivially false). These tests pin the new fail-loud branches by
monkeypatching run_validator to simulate validator wording drift.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import regression_test


def _ok_validator(_path, *_args):
    """Stand-in run_validator that returns a parseable SUMMARY line."""
    stdout = "SUMMARY: 4/4 files passed, 0 errors, 0 warnings\n"
    return 0, stdout, ""


def _wording_drift_validator(_path, *_args):
    """Simulates a future validator that drops the SUMMARY line entirely."""
    stdout = "  [OK] All checks passed\n"  # no SUMMARY: ... line
    return 0, stdout, ""


def _empty_total_validator(_path, *_args):
    """SUMMARY line present but reports 0 files scored (empty asset tree)."""
    stdout = "SUMMARY: 0/0 files passed, 0 errors, 0 warnings\n"
    return 0, stdout, ""


def test_golden_templates_succeeds_on_normal_output(monkeypatch):
    """Sanity check: success path still passes when SUMMARY parses cleanly."""
    monkeypatch.setattr(regression_test, "run_validator", _ok_validator)
    result = regression_test.test_golden_templates()
    assert result.passed is True, (
        f"success path regressed: {result.messages}"
    )


def test_golden_templates_fails_on_summary_wording_drift(monkeypatch):
    """The previously-silent-pass: validator wording drift must now fail loudly."""
    monkeypatch.setattr(regression_test, "run_validator", _wording_drift_validator)
    result = regression_test.test_golden_templates()
    assert result.passed is False, (
        "test_golden_templates silently passed when SUMMARY line was missing — "
        "the silent-pass guard is not in place"
    )
    joined = "\n".join(result.messages)
    assert "SUMMARY line not parsed" in joined, (
        f"failure message missing the diagnostic phrase; got: {joined}"
    )


def test_golden_templates_fails_when_zero_files_scored(monkeypatch):
    """SUMMARY parses but 0 files scored — should fail, not silently pass."""
    monkeypatch.setattr(regression_test, "run_validator", _empty_total_validator)
    result = regression_test.test_golden_templates()
    assert result.passed is False, (
        "test_golden_templates silently passed when 0 files were scored — "
        "the all_total>0 guard is not in place"
    )
    joined = "\n".join(result.messages)
    assert "0 files scored" in joined, (
        f"failure message missing the 0-files diagnostic; got: {joined}"
    )
