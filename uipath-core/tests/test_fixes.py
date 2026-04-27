"""Regression tests for uipath-core/scripts/validate_xaml/_fixes.py.

Focus: guardrails on string replacements so longer FQDNs that share a prefix
with a FQDN_FIX entry don't get mid-consumed. The motivating bug was
`System.Object` → `x:Object` corrupting `<AssemblyReference>System.ObjectModel</AssemblyReference>`
(the Model suffix survived, leaving the unloadable `x:ObjectModel`).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_xaml._fixes import auto_fix_file
from generate_activities.ui_automation import gen_ntypeinto
from generate_activities.application_card import (
    gen_napplicationcard_open,
    gen_napplicationcard_desktop_open,
)


def _write_xaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "Main.xaml"
    p.write_text(content, encoding="utf-8")
    return p


class TestLint99FqdnBoundary:
    """Lint 99 must stop at identifier boundaries so it doesn't eat longer names."""

    def test_system_objectmodel_assembly_ref_preserved(self, tmp_path):
        """<AssemblyReference>System.ObjectModel</AssemblyReference> must NOT become x:ObjectModel."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <TextExpression.ReferencesForImplementation>\n'
            '    <AssemblyReference>System.ObjectModel</AssemblyReference>\n'
            '  </TextExpression.ReferencesForImplementation>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert "<AssemblyReference>System.ObjectModel</AssemblyReference>" in out
        assert "x:ObjectModel" not in out

    def test_system_object_bare_still_fixed(self, tmp_path):
        """Bare `System.Object` (followed by non-identifier char) should still be rewritten."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <Sequence>\n'
            '    <ForEach x:TypeArguments="System.Object" />\n'
            '  </Sequence>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert 'x:TypeArguments="x:Object"' in out
        assert "System.Object" not in out

    def test_system_string_prefix_safety(self, tmp_path):
        """`System.StringBuilder` and `System.StringComparer` must survive the rewrite."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <TextExpression.NamespacesForImplementation>\n'
            '    <x:String>System.StringBuilder</x:String>\n'
            '  </TextExpression.NamespacesForImplementation>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert "System.StringBuilder" in out

    def test_system_int32_dot_suffix_safety(self, tmp_path):
        """`System.Int32.MaxValue` in expressions must not be chopped to `x:Int32.MaxValue`."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <Sequence>\n'
            '    <Assign>[System.Int32.MaxValue]</Assign>\n'
            '  </Sequence>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert "System.Int32.MaxValue" in out
        assert "x:Int32.MaxValue" not in out

    def test_system_data_datatable_preserved_precedence(self, tmp_path):
        """`System.Data.DataTable` still maps to `sd:DataTable` (longer entry wins)."""
        # dict ordering preserves insertion, so Exception runs before the Data.* entries —
        # but the Data.* entries don't overlap with Exception/String/etc., so ordering
        # within the set matters only within the Data family. This test guards the
        # DataTable mapping still fires.
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <Sequence>\n'
            '    <ForEach x:TypeArguments="System.Data.DataTable" />\n'
            '  </Sequence>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert 'x:TypeArguments="sd:DataTable"' in out


class TestVbExprQuoteEscaping:
    """Generators that emit `[expr]` from a VB-expression argument must escape
    embedded `"` to `&quot;` so the XML attribute parser does not close at the
    first inner quote. The regression: literal-with-quotes input produced
    `Text="["Hello"]"` which Studio compiled but executed as DynamicActivity
    with Implementation=null.
    """

    def test_ntypeinto_text_literal_with_quotes(self):
        out = gen_ntypeinto(
            display_name="Type",
            selector="<webctrl tag='INPUT' />",
            text_variable='"Hello"',
            id_ref="abc",
            scope_id="scope-1",
        )
        assert 'Text="[&quot;Hello&quot;]"' in out
        assert 'Text="["Hello"]"' not in out

    def test_ntypeinto_securetext_literal_with_quotes(self):
        out = gen_ntypeinto(
            display_name="Type Secret",
            selector="<webctrl tag='INPUT' />",
            text_variable='"Secret"',
            id_ref="abc",
            scope_id="scope-1",
            is_secure=True,
        )
        assert 'SecureText="[&quot;Secret&quot;]"' in out
        assert 'SecureText="["Secret"]"' not in out

    def test_ntypeinto_variable_name_unchanged(self):
        out = gen_ntypeinto(
            display_name="Type",
            selector="<webctrl tag='INPUT' />",
            text_variable="strFoo",
            id_ref="abc",
            scope_id="scope-1",
        )
        assert 'Text="[strFoo]"' in out

    def test_napplicationcard_open_url_literal_with_quotes_and_amp(self):
        out = gen_napplicationcard_open(
            display_name="Open Browser",
            url_variable='"https://x.example/?a=1&b=2"',
            out_ui_element="uiBrowser",
            scope_guid="guid-1",
            id_ref="card-1",
            body_content="",
            body_sequence_idref="seq-1",
        )
        assert 'Url="[&quot;https://x.example/?a=1&amp;b=2&quot;]"' in out
        assert '&amp;quot;' not in out  # no double-escape

    def test_napplicationcard_desktop_open_filepath_literal_with_quotes(self):
        out = gen_napplicationcard_desktop_open(
            display_name="Open App",
            file_path_variable='"C:\\Tools\\my app.exe"',
            out_ui_element="uiApp",
            scope_guid="guid-1",
            id_ref="card-1",
            body_content="",
            body_sequence_idref="seq-1",
        )
        assert 'FilePath="[&quot;C:\\Tools\\my app.exe&quot;]"' in out
        assert '&amp;quot;' not in out  # no double-escape from outer _escape_xml_attr

    def test_napplicationcard_desktop_open_filepath_variable_unchanged(self):
        out = gen_napplicationcard_desktop_open(
            display_name="Open App",
            file_path_variable="strExePath",
            out_ui_element="uiApp",
            scope_guid="guid-1",
            id_ref="card-1",
            body_content="",
            body_sequence_idref="seq-1",
        )
        assert 'FilePath="[strExePath]"' in out
