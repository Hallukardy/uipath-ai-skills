"""Contract tests for `_data_driven.gen_from_annotation` attribute escaping.

Pins M-Cor-1 from the 2026-04-28 v2 review: the dispatcher's default attribute
branch (`escape: null, bracket_wrap: false`) must XML-escape spec_arg values
before interpolating them into the XAML attribute, otherwise any value
containing `&`, `<`, `>`, `"`, or `'` corrupts the output and Studio degrades
the activity to `DynamicActivity` at load.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "uipath-core" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_activities import _data_driven  # noqa: E402


# Minimal annotation entry with a single param using the default branch
# (no escape, no bracket_wrap). Mirrors the shape used by ~20+ corpus
# entries in ui_automation.json (e.g. GoogleCloudOCR.api_key,
# NKeyboardShortcuts.shortcuts).
_STUB_ENTRY = {
    "element_tag": "ui:Stub",
    "params": {
        "value_param": {"attr": "Value"},
    },
    "fixed_attrs": {},
    "child_elements": {},
    "hint_size_key": "Stub",
}


@pytest.fixture
def stub_annotation(monkeypatch):
    """Inject a stub activity into the annotation cache for the duration of a test."""
    monkeypatch.setattr(
        _data_driven,
        "_ANNOTATIONS_CACHE",
        {"stub": _STUB_ENTRY},
    )


def _gen(stub_annotation, value):
    """Run the dispatcher with the default-branch stub and the given value."""
    return _data_driven.gen_from_annotation(
        activity_name="stub",
        spec_args={"value_param": value},
        id_ref="X",
        scope_id="",
        indent="    ",
    )


@pytest.mark.parametrize(
    "raw,expected_attr",
    [
        ('Sales & Marketing', 'Value="Sales &amp; Marketing"'),
        ('a < b > c',         'Value="a &lt; b &gt; c"'),
        ('she said "hi"',     'Value="she said &quot;hi&quot;"'),
        ('mixed: a&b<c>d"e',  'Value="mixed: a&amp;b&lt;c&gt;d&quot;e"'),
    ],
)
def test_default_branch_escapes_xml_specials(stub_annotation, raw, expected_attr):
    """A spec_args value containing `&`, `<`, `>`, or `"` is XML-escaped before
    interpolation into the XAML attribute (M-Cor-1 fix)."""
    out = _gen(stub_annotation, raw)
    assert expected_attr in out, f"missing escaped form in output:\n{out}"


def test_default_branch_passes_clean_enum_unchanged(stub_annotation):
    """For the common case (clean enum-like values, like the actual corpus
    has today), the new escape is a no-op."""
    out = _gen(stub_annotation, "BasicAuth")
    assert 'Value="BasicAuth"' in out


def test_default_branch_passes_numeric_literal_unchanged(stub_annotation):
    """Numeric values (also enum-shaped corpus entries) pass through cleanly."""
    out = _gen(stub_annotation, 100)
    assert 'Value="100"' in out
