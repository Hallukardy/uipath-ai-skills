"""Golden-template fixture tests for new lint rules.

For each new rule covered by an explicit good/bad pair under
`assets/lint-test-cases/lint<N>_*_good.xaml` /
`assets/lint-test-cases/lint<N>_*_bad.xaml`:
  - the *bad* fixture must trigger the rule's [lint <N>] (or a
    rule-distinctive substring for rules that emit unprefixed messages)
  - the *good* fixture must NOT trigger that rule's marker

These fixtures live alongside the existing `bad_*.xaml` cases (mirroring
the pattern exercised by `scripts/run_lint_tests.py`), and the regression
test's golden-validation pass already excludes the `lint-test-cases/`
directory, so the intentionally-bad files don't pollute that signal.

Rules covered today: 9, 14, 18, 24.
Rules 40, 87, 89, 90, 93, 95, 99, 110 are already exercised by
`scripts/run_lint_tests.py` and/or `scripts/test_auto_fix.py`, so they
aren't duplicated here.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_xaml import validate_xaml_file


_FIXTURES = Path(__file__).parent.parent / "assets" / "lint-test-cases"


def _all_messages(result) -> str:
    """Concatenate every emitted message into a single searchable blob."""
    return " | ".join(result.errors + result.warnings + result.info)


# (rule_number, marker substring expected in BAD output, fixture stem)
# The marker is what we check for. Rules that prefix their messages with
# `[lint N]` use that; rules emitting plain prose (lint 9, 14, 18) use a
# rule-distinctive substring instead.
_CASES = [
    (9,  "hardcoded idx > 2",
     "lint009_hardcoded_idx"),
    (14, "matching:aaname='fuzzy' but no fuzzylevel:aaname",
     "lint014_selector_quality"),
    (18, "System.Drawing.Primitives",
     "lint018_namespace_conflicts"),
]


@pytest.mark.parametrize("rule_n, marker, stem", _CASES,
                         ids=[f"lint{n}" for n, _, _ in _CASES])
def test_bad_fixture_fires_target_rule(rule_n, marker, stem):
    bad = _FIXTURES / f"{stem}_bad.xaml"
    assert bad.is_file(), f"missing bad fixture: {bad}"
    result = validate_xaml_file(str(bad), lint=True)
    blob = _all_messages(result)
    assert marker in blob, (
        f"lint {rule_n}: bad fixture {bad.name} did not emit expected "
        f"marker {marker!r}\n--- output ---\n{blob}\n"
    )


@pytest.mark.parametrize("rule_n, marker, stem", _CASES,
                         ids=[f"lint{n}" for n, _, _ in _CASES])
def test_good_fixture_silent_on_target_rule(rule_n, marker, stem):
    good = _FIXTURES / f"{stem}_good.xaml"
    assert good.is_file(), f"missing good fixture: {good}"
    result = validate_xaml_file(str(good), lint=True)
    blob = _all_messages(result)
    assert marker not in blob, (
        f"lint {rule_n}: good fixture {good.name} unexpectedly emitted "
        f"marker {marker!r}\n--- output ---\n{blob}\n"
    )


def test_lint_24_pair_present_even_when_dict_empty():
    """Lint 24's DEPRECATED dict is currently empty (no active renames),
    so the bad fixture is a placeholder that won't fire today. We still
    keep the pair on disk so a future entry doesn't quietly bypass test
    coverage."""
    good = _FIXTURES / "lint024_deprecated_assemblies_good.xaml"
    bad = _FIXTURES / "lint024_deprecated_assemblies_bad.xaml"
    assert good.is_file()
    assert bad.is_file()
    # Both files must at least be well-formed XAML the validator can ingest.
    for f in (good, bad):
        result = validate_xaml_file(str(f), lint=True)
        # validate_xaml_file always returns; we just make sure it didn't blow up.
        assert result is not None
