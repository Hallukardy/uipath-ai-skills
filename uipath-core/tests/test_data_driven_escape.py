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
from utils import escape_xml_attr  # noqa: E402


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


# ---------------------------------------------------------------------------
# M-9: annotation-derived strings (fixed_attrs, display_name, etc.) get
# XML-escaped before interpolation.
# ---------------------------------------------------------------------------


def test_annotation_fixed_attrs_value_escapes_xml_specials(monkeypatch):
    """A fixed_attrs value with `&` / `"` is XML-escaped, not raw, in output."""
    entry = {
        "element_tag": "ui:Stub",
        "params": {},
        "fixed_attrs": {"Caption": 'Foo & "Bar"'},
        "child_elements": {},
        "hint_size_key": "Stub",
    }
    monkeypatch.setattr(_data_driven, "_ANNOTATIONS_CACHE", {"stub": entry})
    out = _data_driven.gen_from_annotation(
        activity_name="stub",
        spec_args={},
        id_ref="X",
        scope_id="",
        indent="    ",
    )
    assert 'Caption="Foo &amp; &quot;Bar&quot;"' in out
    # Make sure the raw form did not survive.
    assert 'Foo & "Bar"' not in out


def test_annotation_display_name_escapes_xml_specials(monkeypatch):
    """A child_elements[*].display_name with `&` is XML-escaped in DisplayName."""
    entry = {
        "element_tag": "ui:If",
        "params": {},
        "fixed_attrs": {},
        "child_elements": {
            "Then": {"type": "sequence", "display_name": "Foo & Bar", "tag_prefix": "ui:"},
        },
        "hint_size_key": "If",
    }
    monkeypatch.setattr(_data_driven, "_ANNOTATIONS_CACHE", {"stub": entry})
    out = _data_driven.gen_from_annotation(
        activity_name="stub",
        spec_args={},
        id_ref="X",
        scope_id="",
        indent="    ",
    )
    assert 'DisplayName="Foo &amp; Bar"' in out
    # Raw '&' (i.e. '& ' with nothing after) must not appear inside the
    # DisplayName attribute — search just that attribute substring.
    assert 'DisplayName="Foo & Bar"' not in out


# ---------------------------------------------------------------------------
# M-10: bracket_wrap escape contract — escaped specials land *inside* [...].
# ---------------------------------------------------------------------------


_STUB_BRACKET_ENTRY = {
    "element_tag": "ui:Stub",
    "params": {
        "value_param": {"attr": "Value", "bracket_wrap": True},
    },
    "fixed_attrs": {},
    "child_elements": {},
    "hint_size_key": "Stub",
}


@pytest.fixture
def stub_bracket_annotation(monkeypatch):
    monkeypatch.setattr(
        _data_driven,
        "_ANNOTATIONS_CACHE",
        {"stub": _STUB_BRACKET_ENTRY},
    )


@pytest.mark.parametrize(
    "raw,expected_inside",
    [
        ("a & b",       "a &amp; b"),
        ('say "hi"',    "say &quot;hi&quot;"),
        ("x < y",       "x &lt; y"),
        ("x > y",       "x &gt; y"),
        ('mix: a&b<c"d', "mix: a&amp;b&lt;c&quot;d"),
    ],
)
def test_bracket_wrap_escapes_xml_specials_inside_brackets(
    stub_bracket_annotation, raw, expected_inside,
):
    """bracket_wrap=True wraps `value` in `[...]` and the escaped XML form
    lands inside the brackets (the expression is still in an XML attribute)."""
    out = _data_driven.gen_from_annotation(
        activity_name="stub",
        spec_args={"value_param": raw},
        id_ref="X",
        scope_id="",
        indent="    ",
    )
    expected_attr = f'Value="[{expected_inside}]"'
    assert expected_attr in out, (
        f"missing escaped form in output:\n{out}\nexpected: {expected_attr}"
    )


# ---------------------------------------------------------------------------
# M-18: escape_xml_attr pre-strips XML 1.0 illegal control chars.
# ---------------------------------------------------------------------------


def test_escape_strips_xml_illegal_control_chars():
    """U+0000–U+001F (minus TAB/LF/CR) are stripped before XML escaping."""
    assert escape_xml_attr("hello\x00world\x01") == "helloworld"
    # TAB, LF, CR are legal in XML 1.0 attribute values and must survive.
    assert escape_xml_attr("a\tb\nc\rd") == "a\tb\nc\rd"
    # Mixed: legal + illegal + escaped specials all in one go.
    assert escape_xml_attr("x\x05&\x1Fy") == "x&amp;y"
