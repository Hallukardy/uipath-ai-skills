"""Unit tests for harvest-determinism scrub helpers.

Closes review findings E-MAJOR-1 (random ScopeGuid in committed profile JSON)
and E-MAJOR-2 (per-machine Studio assembly hash in committed wizard XAML).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestScrubScopeGuids:
    """``backfill_profile_templates.scrub_scope_guids`` replaces random
    Studio-minted UUIDs with the root-scope sentinel so re-harvests produce
    bit-identical xaml_template values.
    """

    def _f(self):
        from backfill_profile_templates import scrub_scope_guids
        return scrub_scope_guids

    def test_replaces_real_uuid_with_sentinel(self):
        before = '<x ScopeGuid="e7935895-731f-4ccc-af43-bcaf97460019" />'
        after = self._f()(before)
        assert 'ScopeGuid="00000000-0000-0000-0000-000000000000"' in after
        assert "e7935895" not in after

    def test_idempotent(self):
        f = self._f()
        once = f('<x ScopeGuid="e7935895-731f-4ccc-af43-bcaf97460019" />')
        twice = f(once)
        assert twice == once

    def test_replaces_multiple_in_one_string(self):
        before = (
            '<a ScopeGuid="e7935895-731f-4ccc-af43-bcaf97460019" />'
            '<b ScopeGuid="691fed1f-41b4-4681-abd6-e997aa777027" />'
        )
        after = self._f()(before)
        assert after.count('ScopeGuid="00000000-0000-0000-0000-000000000000"') == 2

    def test_preserves_non_scope_uuids(self):
        # A UUID that's not behind ScopeGuid= (e.g. inside selectors) must not
        # be touched — only ScopeGuid attribute values are stripped.
        before = '<x SomeOtherGuid="e7935895-731f-4ccc-af43-bcaf97460019" />'
        after = self._f()(before)
        assert "e7935895" in after  # untouched

    def test_empty_input_returns_empty(self):
        assert self._f()("") == ""
        assert self._f()(None) is None


class TestHarvestWritePathScrubs:
    """C-2 + H-8 contract test: a freshly-harvested XAML must pass through
    BOTH ``scrub_scope_guids`` AND ``scrub_dynamic_assembly_xmlns`` before
    landing on disk under ``studio-ground-truth/``.

    This test deliberately exercises the scrub helpers as a pair the way the
    harvest write path uses them. A future refactor that removes either call
    from ``harvest_studio_xaml.py`` (around the ``write_text`` of
    ``out_dir / f"{key}.xaml"``) will break this test, because the imported
    ``harvest_studio_xaml`` module-level binding is what we assert against.
    """

    def _harvest_module(self):
        # Importing the worker pulls in both scrubbers as module-level names.
        # If a refactor drops either import, this test fails at import time.
        import harvest_studio_xaml
        return harvest_studio_xaml

    def test_module_binds_both_scrubbers(self):
        """The harvest module MUST expose both scrubbers as module attributes
        so the write-path callsite can reach them. Removing either import
        breaks this test."""
        m = self._harvest_module()
        assert hasattr(m, "scrub_scope_guids"), \
            "harvest_studio_xaml must import scrub_scope_guids"
        assert hasattr(m, "scrub_dynamic_assembly_xmlns"), \
            "harvest_studio_xaml must import scrub_dynamic_assembly_xmlns"
        # Smoke-check both are callable str -> str.
        assert m.scrub_scope_guids("") == ""
        assert m.scrub_dynamic_assembly_xmlns("") == ""

    def test_write_path_call_sequence_scrubs_real_uuid(self):
        """Simulate the harvest write path: feed XAML carrying a real UUID
        and a dynamic-assembly xmlns through both scrubbers in the same
        order the harvest code uses, and assert both sentinels appear in
        what *would* be written to disk."""
        m = self._harvest_module()
        synthetic = (
            '<Activity x:Class="X" xmlns:x="x" '
            'xmlns:dyn="clr-namespace:Dyn;assembly=fd1135674040.qPNHG3TSMPM1ZMTPy3t2VOM1">'
            '<NScope ScopeGuid="e7935895-731f-4ccc-af43-bcaf97460019" />'
            '</Activity>'
        )
        scrubbed = m.scrub_scope_guids(synthetic)
        scrubbed = m.scrub_dynamic_assembly_xmlns(scrubbed)
        # Real UUID gone, sentinel in.
        assert "e7935895" not in scrubbed
        assert 'ScopeGuid="00000000-0000-0000-0000-000000000000"' in scrubbed
        # Dynamic-assembly xmlns gone.
        assert "fd1135674040" not in scrubbed
        assert "xmlns:dyn=" not in scrubbed

    def test_write_path_source_calls_both_scrubbers(self):
        """Belt-and-braces: the harvest worker's source MUST contain both
        scrub calls in the write-path region. This guards against a refactor
        that imports the helpers but stops calling them."""
        from pathlib import Path
        src = (Path(__file__).parent.parent / "scripts" /
               "harvest_studio_xaml.py").read_text(encoding="utf-8")
        # The write-path block currently looks like:
        #   xaml = scrub_scope_guids(xaml)
        #   xaml = scrub_dynamic_assembly_xmlns(xaml)
        #   (out_dir / f"{key}.xaml").write_text(xaml, encoding="utf-8")
        assert "scrub_scope_guids(xaml)" in src, \
            "harvest_studio_xaml must call scrub_scope_guids on harvested XAML"
        assert "scrub_dynamic_assembly_xmlns(xaml)" in src, \
            "harvest_studio_xaml must call scrub_dynamic_assembly_xmlns on harvested XAML"


class TestScrubDynamicAssemblyXmlns:
    """``import_wizard_xaml.scrub_dynamic_assembly_xmlns`` strips
    ``xmlns:NAME="…assembly=fdNNNN.HASH"`` declarations leaked from
    Studio's per-machine wizard project.
    """

    def _f(self):
        from import_wizard_xaml import scrub_dynamic_assembly_xmlns
        return scrub_dynamic_assembly_xmlns

    def test_strips_dynamic_assembly_xmlns(self):
        before = (
            '<Activity x:Class="X" xmlns:x="x" '
            'xmlns:uuadsfb="clr-namespace:UiPath.UIAutomationNext.Activities.Design.SWEntities.fd1135674040.Bundle;'
            'assembly=fd1135674040.qPNHG3TSMPM1ZMTPy3t2VOM1" '
            'xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib">'
            '</Activity>'
        )
        after = self._f()(before)
        assert "fd1135674040" not in after
        assert "uuadsfb" not in after
        assert 'xmlns:scg="' in after  # other xmlns preserved

    def test_idempotent(self):
        f = self._f()
        before = (
            '<x xmlns:foo="clr-namespace:Foo;assembly=fd9999.AAA" '
            'xmlns:bar="clr-namespace:Bar;assembly=Bar" />'
        )
        once = f(before)
        twice = f(once)
        assert twice == once

    def test_preserves_real_assembly_xmlns(self):
        # A regular (non-dynamic) assembly xmlns must not be touched.
        before = (
            '<Activity '
            'xmlns:s="clr-namespace:System;assembly=System.Private.CoreLib" '
            'xmlns:ui="http://schemas.uipath.com/workflow/activities" />'
        )
        after = self._f()(before)
        assert after == before

    def test_empty_input_returns_empty(self):
        assert self._f()("") == ""
        assert self._f()(None) is None
