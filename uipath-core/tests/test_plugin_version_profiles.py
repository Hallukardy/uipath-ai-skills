"""Plugin-registered version profile integration tests.

Verifies that plugins can supply their own version profiles + band mappings
through plugin_loader, and that lints_version_compat picks them up.
"""

import shutil
import sys
import warnings
from pathlib import Path
from types import MappingProxyType

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import plugin_loader
from plugin_loader import (
    PLUGIN_API_VERSION,
    get_band_profile_mappings,
    get_version_profiles,
    register_band_profile_mapping,
    register_version_profile,
)


@pytest.fixture
def loaded_plugins():
    plugin_loader.load_plugins()
    yield


@pytest.fixture
def isolated_registries():
    """Snapshot + restore the plugin registries so tests don't leak state."""
    snap_profiles = dict(plugin_loader._version_profiles)
    snap_bands = {b: dict(pkgs) for b, pkgs in plugin_loader._band_profile_mappings.items()}
    yield
    plugin_loader._version_profiles.clear()
    plugin_loader._version_profiles.update(snap_profiles)
    plugin_loader._band_profile_mappings.clear()
    plugin_loader._band_profile_mappings.update(snap_bands)


class TestTasksPluginRegistration:
    """The uipath-tasks plugin ships a Persistence.Activities profile."""

    def test_persistence_profile_is_registered(self, loaded_plugins):
        profiles = get_version_profiles()
        assert ("UiPath.Persistence.Activities", "1.4") in profiles

    def test_persistence_profile_has_expected_activities(self, loaded_plugins):
        profiles = get_version_profiles()
        activities = profiles[("UiPath.Persistence.Activities", "1.4")]["activities"]
        expected = {
            "CreateFormTask", "WaitForFormTaskAndResume", "GetFormTasks",
            "CreateExternalTask", "WaitForExternalTaskAndResume",
            "CompleteTask", "AssignTasks",
        }
        assert expected <= set(activities.keys())

    def test_persistence_band_mappings_cover_25_and_26(self, loaded_plugins):
        mappings = get_band_profile_mappings()
        assert mappings.get("25", {}).get("UiPath.Persistence.Activities") == "1.4"
        assert mappings.get("26", {}).get("UiPath.Persistence.Activities") == "1.4"


class TestMergedBandProfileVersions:
    """lints_version_compat merges core BAND_PROFILE_VERSIONS with plugin entries."""

    def test_merged_includes_plugin_package(self, loaded_plugins):
        from validate_xaml.lints_version_compat import _merged_band_profile_versions
        merged = _merged_band_profile_versions()
        assert merged["25"].get("UiPath.Persistence.Activities") == "1.4"
        assert merged["26"].get("UiPath.Persistence.Activities") == "1.4"

    def test_merged_preserves_core_packages(self, loaded_plugins):
        from validate_xaml.lints_version_compat import _merged_band_profile_versions
        merged = _merged_band_profile_versions()
        assert merged["25"]["UiPath.System.Activities"] == "25.10"
        assert merged["26"]["UiPath.System.Activities"] == "26.2"


class TestProfileLookup:
    """_load_profile_data prefers plugin-registered profiles over on-disk."""

    def test_plugin_profile_wins_over_disk(self, isolated_registries):
        from validate_xaml.lints_version_compat import _load_profile_data
        shadow = {"activities": {"_Sentinel": {"version_attrs": {}}}}
        register_version_profile("UiPath.System.Activities", "25.10", shadow)
        data = _load_profile_data("UiPath.System.Activities", "25.10")
        # get_version_profiles returns deep-copied inner profiles so callers
        # can't mutate the registry — assert value equality, not identity.
        assert data == shadow
        # And the shadow profile's _Sentinel marker is what wins, proving the
        # plugin's profile shadowed the on-disk UiPath.System.Activities/25.10.
        assert "_Sentinel" in data["activities"]

    def test_disk_used_when_plugin_absent(self, loaded_plugins):
        from validate_xaml.lints_version_compat import _load_profile_data
        data = _load_profile_data("UiPath.System.Activities", "25.10")
        assert data is not None
        assert "activities" in data

    def test_returns_none_when_neither_source_has_profile(self, isolated_registries):
        from validate_xaml.lints_version_compat import _load_profile_data
        assert _load_profile_data("NonExistent.Package", "99.99") is None


class TestDynamicRegistration:
    """Round-trip: plugins can add profiles at runtime and see them."""

    def test_register_and_read_back(self, isolated_registries):
        profile = {"activities": {"DummyActivity": {"version_attrs": {"DummyActivity": "V9"}}}}
        register_version_profile("Test.Package", "9.9", profile)
        register_band_profile_mapping("99", "Test.Package", "9.9")

        profiles = get_version_profiles()
        # Inner profile is a deep copy of the registered profile so callers
        # can't mutate the registry — assert value equality, not identity.
        assert profiles[("Test.Package", "9.9")] == profile

        mappings = get_band_profile_mappings()
        assert mappings["99"]["Test.Package"] == "9.9"

    def test_band_mapping_reaches_lint_122_expected_map(self, isolated_registries):
        profile = {"activities": {"_PluginAct": {"version_attrs": {"_PluginTag": "V7"}}}}
        register_version_profile("Test.BandPkg", "1.0", profile)
        register_band_profile_mapping("25", "Test.BandPkg", "1.0")

        from validate_xaml.lints_version_compat import (
            _BAND_EXPECTED_CACHE,
            _build_band_expected_versions,
        )
        _BAND_EXPECTED_CACHE.pop("25", None)
        expected = _build_band_expected_versions("25")
        assert expected.get("_PluginTag") == "V7"


# ---------------------------------------------------------------------------
# HIGH-7 — get_* returns a read-only view; mutating it does not leak
# ---------------------------------------------------------------------------


class TestGetReturnsImmutableView:
    """get_version_profiles / get_band_profile_mappings return an immutable view.

    Outer mappings are wrapped in MappingProxyType (so plugins can't add or
    replace registered profiles via the returned view) and inner profile dicts
    are deep-copied (so caller mutations never reach the live registry).
    """

    def test_get_version_profiles_outer_is_mappingproxy(self, isolated_registries):
        profile = {"activities": {"A": {"version_attrs": {}}}}
        register_version_profile("Pkg.View", "1.0", profile)
        profiles = get_version_profiles()
        assert isinstance(profiles, MappingProxyType)
        # Adding a new key to the returned view must not work.
        with pytest.raises(TypeError):
            profiles[("Other", "1.0")] = {}  # type: ignore[index]

    def test_get_version_profiles_inner_mutation_raises(self, isolated_registries):
        # H-1 contract: inner profile dicts are deep-frozen via _freeze_profile,
        # so any nested write raises TypeError instead of silently corrupting
        # the cached snapshot or leaking into other readers.
        profile = {"activities": {"OriginalAct": {"version_attrs": {"X": "V1"}}}}
        register_version_profile("Pkg.View", "1.0", profile)
        profiles = get_version_profiles()
        inner = profiles[("Pkg.View", "1.0")]
        # Inner is now a MappingProxyType (read-only mapping).
        assert isinstance(inner, MappingProxyType)
        with pytest.raises(TypeError):
            inner["activities"]["LeakedAct"] = {"version_attrs": {}}  # type: ignore[index]
        # The registry itself is untouched.
        assert "LeakedAct" not in plugin_loader._version_profiles[("Pkg.View", "1.0")]["activities"]

    def test_get_version_profiles_caller_b_no_leak_after_caller_a_attempts_mutation(
        self, isolated_registries
    ):
        # H-1 cross-contamination test: caller A reads, attempts a nested
        # write (TypeError), caller B reads after and sees a pristine view.
        profile = {"activities": {"OriginalAct": {"version_attrs": {"X": "V1"}}}}
        register_version_profile("Pkg.View", "1.0", profile)

        # Caller A
        view_a = get_version_profiles()
        with pytest.raises(TypeError):
            view_a[("Pkg.View", "1.0")]["activities"]["X"] = "leaked"  # type: ignore[index]

        # Caller B reads after A — must see the original profile only.
        view_b = get_version_profiles()
        b_inner = view_b[("Pkg.View", "1.0")]
        assert isinstance(b_inner, MappingProxyType)
        assert set(b_inner["activities"].keys()) == {"OriginalAct"}
        assert b_inner["activities"]["OriginalAct"]["version_attrs"]["X"] == "V1"

    def test_get_band_profile_mappings_outer_is_mappingproxy(self, isolated_registries):
        register_version_profile("Pkg.View", "1.0", {"activities": {}})
        register_band_profile_mapping("25", "Pkg.View", "1.0")
        mappings = get_band_profile_mappings()
        assert isinstance(mappings, MappingProxyType)
        # Inner per-band mappings are also MappingProxyType.
        assert isinstance(mappings["25"], MappingProxyType)
        with pytest.raises(TypeError):
            mappings["25"]["Pkg.View"] = "9.9"  # type: ignore[index]


# ---------------------------------------------------------------------------
# HIGH-8 — register_* validates inputs and warns on duplicates
# ---------------------------------------------------------------------------


class TestRegisterValidatesInputs:
    """register_version_profile / register_band_profile_mapping reject malformed input."""

    def test_register_version_profile_rejects_empty_package(self, isolated_registries):
        with pytest.raises(ValueError, match="package"):
            register_version_profile("", "1.0", {"activities": {}})

    def test_register_version_profile_rejects_none_package(self, isolated_registries):
        with pytest.raises(ValueError, match="package"):
            register_version_profile(None, "1.0", {"activities": {}})  # type: ignore[arg-type]

    def test_register_version_profile_rejects_empty_version(self, isolated_registries):
        with pytest.raises(ValueError, match="profile_version"):
            register_version_profile("Pkg", "", {"activities": {}})

    def test_register_version_profile_rejects_non_semver_version(self, isolated_registries):
        with pytest.raises(ValueError, match="profile_version"):
            register_version_profile("Pkg", "not-a-version", {"activities": {}})

    def test_register_version_profile_rejects_non_dict_profile(self, isolated_registries):
        with pytest.raises(ValueError, match="profile"):
            register_version_profile("Pkg", "1.0", "not a dict")  # type: ignore[arg-type]

    def test_register_band_profile_mapping_rejects_empty_band(self, isolated_registries):
        with pytest.raises(ValueError, match="band"):
            register_band_profile_mapping("", "Pkg", "1.0")

    def test_register_band_profile_mapping_rejects_int_band(self, isolated_registries):
        with pytest.raises(ValueError, match="band"):
            register_band_profile_mapping(25, "Pkg", "1.0")  # type: ignore[arg-type]

    def test_register_band_profile_mapping_rejects_non_digit_band(self, isolated_registries):
        with pytest.raises(ValueError, match="band"):
            register_band_profile_mapping("twenty-five", "Pkg", "1.0")

    def test_register_band_profile_mapping_rejects_empty_package(self, isolated_registries):
        with pytest.raises(ValueError, match="package"):
            register_band_profile_mapping("25", "", "1.0")

    def test_register_band_profile_mapping_rejects_empty_version(self, isolated_registries):
        with pytest.raises(ValueError, match="profile_version"):
            register_band_profile_mapping("25", "Pkg", "")


class TestRegisterDuplicateWarns:
    """Duplicate registrations emit a warning before overwriting (matches register_generator)."""

    def test_duplicate_version_profile_warns(self, isolated_registries):
        first = {"activities": {"A": {"version_attrs": {}}}}
        second = {"activities": {"B": {"version_attrs": {}}}}
        register_version_profile("Pkg.Dup", "1.0", first)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            register_version_profile("Pkg.Dup", "1.0", second)
        messages = [str(w.message) for w in caught]
        assert any("Duplicate version_profile" in m and "Pkg.Dup" in m for m in messages), (
            f"expected a duplicate-registration warning; got {messages!r}"
        )
        # Second registration won (overwrite is intentional, just announced).
        assert get_version_profiles()[("Pkg.Dup", "1.0")] == second

    def test_duplicate_band_profile_mapping_warns(self, isolated_registries):
        register_version_profile("Pkg.Dup", "1.0", {"activities": {}})
        register_version_profile("Pkg.Dup", "2.0", {"activities": {}})
        register_band_profile_mapping("25", "Pkg.Dup", "1.0")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            register_band_profile_mapping("25", "Pkg.Dup", "2.0")
        messages = [str(w.message) for w in caught]
        assert any("Duplicate band_profile_mapping" in m and "Pkg.Dup" in m for m in messages), (
            f"expected a duplicate-registration warning; got {messages!r}"
        )
        assert get_band_profile_mappings()["25"]["Pkg.Dup"] == "2.0"


# ---------------------------------------------------------------------------
# HIGH-6 — plugins missing REQUIRED_API_VERSION are rejected with rollback
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_plugin_factory(tmp_path_factory):
    """Materialise a stub plugin under <skill_root>/<name>/extensions/ and reset
    plugin_loader state so load_plugins() picks it up. Cleans up the stub dir
    and restores plugin_loader globals on teardown so other tests are unaffected.
    """
    skill_root = Path(plugin_loader.__file__).resolve().parent.parent.parent
    created_dirs: list[Path] = []

    # Snapshot every plugin_loader registry / state we touch via load_plugins.
    snap_loaded = plugin_loader._loaded
    snap_failures = list(plugin_loader._load_failures)
    snap_generators = dict(plugin_loader._generators)
    snap_aliases = dict(plugin_loader._generator_aliases)
    snap_display = dict(plugin_loader._display_name_map)
    snap_ui_gens = set(plugin_loader._ui_generators)
    snap_lint = list(plugin_loader._lint_rules)
    snap_hooks = list(plugin_loader._scaffold_hooks)
    snap_ns = dict(plugin_loader._extra_namespaces)
    snap_known = set(plugin_loader._extra_known_activities)
    snap_key = list(plugin_loader._extra_key_activities)
    snap_hallucination = list(plugin_loader._hallucination_patterns)
    snap_packages = list(plugin_loader._common_packages)
    snap_graders = dict(plugin_loader._battle_test_graders)
    snap_specs = dict(plugin_loader._test_specs)
    snap_lint_fixtures = list(plugin_loader._lint_test_fixtures)
    snap_type_mappings = dict(plugin_loader._type_mappings)
    snap_variable_prefixes = dict(plugin_loader._variable_prefixes)
    snap_version_profiles = dict(plugin_loader._version_profiles)
    snap_band_mappings = {b: dict(pkgs) for b, pkgs in plugin_loader._band_profile_mappings.items()}
    snap_sys_module_keys = {k for k in sys.modules if k.startswith("_skill_ext_")}

    def _make(name: str, init_body: str) -> Path:
        plugin_dir = skill_root / name
        if plugin_dir.exists():
            raise RuntimeError(
                f"refusing to overwrite existing path {plugin_dir}; "
                f"pick a unique stub-plugin name"
            )
        ext_dir = plugin_dir / "extensions"
        ext_dir.mkdir(parents=True)
        (ext_dir / "__init__.py").write_text(init_body, encoding="utf-8")
        created_dirs.append(plugin_dir)
        return plugin_dir

    yield _make

    # Cleanup: remove any stub directories we created and restore plugin_loader.
    for d in created_dirs:
        shutil.rmtree(d, ignore_errors=True)
    for k in [k for k in sys.modules if k.startswith("_skill_ext_") and k not in snap_sys_module_keys]:
        del sys.modules[k]
    plugin_loader._loaded = snap_loaded
    plugin_loader._load_failures.clear()
    plugin_loader._load_failures.extend(snap_failures)
    plugin_loader._generators.clear(); plugin_loader._generators.update(snap_generators)
    plugin_loader._generator_aliases.clear(); plugin_loader._generator_aliases.update(snap_aliases)
    plugin_loader._display_name_map.clear(); plugin_loader._display_name_map.update(snap_display)
    plugin_loader._ui_generators.clear(); plugin_loader._ui_generators.update(snap_ui_gens)
    plugin_loader._lint_rules.clear(); plugin_loader._lint_rules.extend(snap_lint)
    plugin_loader._scaffold_hooks.clear(); plugin_loader._scaffold_hooks.extend(snap_hooks)
    plugin_loader._extra_namespaces.clear(); plugin_loader._extra_namespaces.update(snap_ns)
    plugin_loader._extra_known_activities.clear(); plugin_loader._extra_known_activities.update(snap_known)
    plugin_loader._extra_key_activities.clear(); plugin_loader._extra_key_activities.extend(snap_key)
    plugin_loader._hallucination_patterns.clear(); plugin_loader._hallucination_patterns.extend(snap_hallucination)
    plugin_loader._common_packages.clear(); plugin_loader._common_packages.extend(snap_packages)
    plugin_loader._battle_test_graders.clear(); plugin_loader._battle_test_graders.update(snap_graders)
    plugin_loader._test_specs.clear(); plugin_loader._test_specs.update(snap_specs)
    plugin_loader._lint_test_fixtures.clear(); plugin_loader._lint_test_fixtures.extend(snap_lint_fixtures)
    plugin_loader._type_mappings.clear(); plugin_loader._type_mappings.update(snap_type_mappings)
    plugin_loader._variable_prefixes.clear(); plugin_loader._variable_prefixes.update(snap_variable_prefixes)
    plugin_loader._version_profiles.clear(); plugin_loader._version_profiles.update(snap_version_profiles)
    plugin_loader._band_profile_mappings.clear(); plugin_loader._band_profile_mappings.update(snap_band_mappings)


class TestPluginMissingRequiredApiVersion:
    """A plugin without REQUIRED_API_VERSION is rejected; partial registrations rolled back."""

    def test_plugin_missing_required_api_version_rejected(self, stub_plugin_factory):
        # Plugin registers a profile in its top-level body, but omits
        # REQUIRED_API_VERSION entirely. The loader must reject it with the
        # actionable message AND roll back the profile registration.
        init_body = (
            "import sys, pathlib\n"
            "_root = pathlib.Path(__file__).resolve().parent.parent.parent / 'uipath-core' / 'scripts'\n"
            "sys.path.insert(0, str(_root))\n"
            "from plugin_loader import register_version_profile\n"
            "register_version_profile('Stub.NoApiVersion.Pkg', '9.9', {'activities': {}})\n"
        )
        stub_plugin_factory("_omc_stub_no_api_version", init_body)

        # Force re-discovery so our stub is picked up.
        plugin_loader._loaded = False
        plugin_loader._load_failures.clear()
        plugin_loader.load_plugins()

        failures = plugin_loader.get_load_failures()
        match = [
            (skill, err) for skill, err in failures
            if skill == "_omc_stub_no_api_version"
        ]
        assert match, f"expected stub plugin to fail; load failures: {failures}"
        skill_name, err_msg = match[0]
        assert "REQUIRED_API_VERSION" in err_msg, err_msg
        assert f"expected {PLUGIN_API_VERSION}" in err_msg, err_msg

        # And the partial profile registration was rolled back.
        profiles = plugin_loader.get_version_profiles()
        assert ("Stub.NoApiVersion.Pkg", "9.9") not in profiles, (
            "rejected plugin's profile registration was not rolled back"
        )

    def test_plugin_with_required_api_version_1_rejected(self, stub_plugin_factory):
        # H-2 part 1: a plugin pinned to the prior API version (v1) must be
        # rejected with a clear "API version mismatch" message that names the
        # required vs declared versions, so a stale plugin author sees what
        # to update.
        init_body = (
            "REQUIRED_API_VERSION = 1\n"
        )
        stub_plugin_factory("_omc_stub_api_v1", init_body)

        plugin_loader._loaded = False
        plugin_loader._load_failures.clear()
        plugin_loader.load_plugins()

        failures = plugin_loader.get_load_failures()
        match = [(s, e) for s, e in failures if s == "_omc_stub_api_v1"]
        assert match, f"expected stub v1 plugin to fail; load failures: {failures}"
        skill_name, err_msg = match[0]
        # The mismatch error names both versions and the remediation hint
        # (added by H-3) so the operator can fix the plugin without grepping.
        assert "API version mismatch" in err_msg, err_msg
        assert "v1" in err_msg, err_msg
        assert f"v{PLUGIN_API_VERSION}" in err_msg, err_msg
        # H-3 remediation hint: tells the plugin author exactly what to set.
        assert "REQUIRED_API_VERSION" in err_msg, err_msg
        assert f"= {PLUGIN_API_VERSION}" in err_msg, err_msg

    def test_plugin_partial_load_failure_rolls_back_all_registries(self, stub_plugin_factory):
        # H-2 part 2: a plugin that calls register_version_profile then raises
        # mid-import must roll back EVERY registry so the failed plugin's
        # partial state can't leak into subsequent plugins or callers.
        # Snapshot every registry from outside the load_plugins call and
        # compare keys after the failed load — they must be byte-identical.
        snap_before = {
            "generators": dict(plugin_loader._generators),
            "aliases": dict(plugin_loader._generator_aliases),
            "display": dict(plugin_loader._display_name_map),
            "ui_gens": set(plugin_loader._ui_generators),
            "lint": list(plugin_loader._lint_rules),
            "hooks": list(plugin_loader._scaffold_hooks),
            "ns": dict(plugin_loader._extra_namespaces),
            "known": set(plugin_loader._extra_known_activities),
            "key": list(plugin_loader._extra_key_activities),
            "hallucination": list(plugin_loader._hallucination_patterns),
            "packages": list(plugin_loader._common_packages),
            "graders": dict(plugin_loader._battle_test_graders),
            "specs": dict(plugin_loader._test_specs),
            "lint_fixtures": list(plugin_loader._lint_test_fixtures),
            "type_mappings": dict(plugin_loader._type_mappings),
            "variable_prefixes": dict(plugin_loader._variable_prefixes),
            "version_profiles": dict(plugin_loader._version_profiles),
            "band_mappings": {b: dict(p) for b, p in plugin_loader._band_profile_mappings.items()},
        }

        init_body = (
            "import sys, pathlib\n"
            "_root = pathlib.Path(__file__).resolve().parent.parent.parent / 'uipath-core' / 'scripts'\n"
            "sys.path.insert(0, str(_root))\n"
            "from plugin_loader import register_version_profile\n"
            "REQUIRED_API_VERSION = 2\n"
            "register_version_profile('Stub.PartialFail.Pkg', '7.7', {'activities': {}})\n"
            "raise RuntimeError('simulated')\n"
        )
        stub_plugin_factory("_omc_stub_partial_fail", init_body)

        plugin_loader._loaded = False
        plugin_loader._load_failures.clear()
        plugin_loader.load_plugins()

        failures = plugin_loader.get_load_failures()
        match = [(s, e) for s, e in failures if s == "_omc_stub_partial_fail"]
        assert match, f"expected partial-fail stub to be in failures: {failures}"
        # Error message is "RuntimeError: simulated".
        assert "simulated" in match[0][1]

        # Every one of the 17 registries must be byte-identical to pre-load.
        snap_after = {
            "generators": dict(plugin_loader._generators),
            "aliases": dict(plugin_loader._generator_aliases),
            "display": dict(plugin_loader._display_name_map),
            "ui_gens": set(plugin_loader._ui_generators),
            "lint": list(plugin_loader._lint_rules),
            "hooks": list(plugin_loader._scaffold_hooks),
            "ns": dict(plugin_loader._extra_namespaces),
            "known": set(plugin_loader._extra_known_activities),
            "key": list(plugin_loader._extra_key_activities),
            "hallucination": list(plugin_loader._hallucination_patterns),
            "packages": list(plugin_loader._common_packages),
            "graders": dict(plugin_loader._battle_test_graders),
            "specs": dict(plugin_loader._test_specs),
            "lint_fixtures": list(plugin_loader._lint_test_fixtures),
            "type_mappings": dict(plugin_loader._type_mappings),
            "variable_prefixes": dict(plugin_loader._variable_prefixes),
            "version_profiles": dict(plugin_loader._version_profiles),
            "band_mappings": {b: dict(p) for b, p in plugin_loader._band_profile_mappings.items()},
        }
        assert snap_after == snap_before, (
            "partial-load failure left state in one or more registries:\n"
            + "\n".join(
                f"  {k}: before={snap_before[k]!r} after={snap_after[k]!r}"
                for k in snap_before if snap_before[k] != snap_after[k]
            )
        )
        # And the partial profile registration is gone.
        assert ("Stub.PartialFail.Pkg", "7.7") not in plugin_loader._version_profiles
