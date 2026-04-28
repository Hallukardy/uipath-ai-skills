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
