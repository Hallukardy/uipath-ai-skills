# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.2.2] - 2026-04-26

Closes 21 findings from a multi-agent deep review of the v1.2.1 surface
(commits `fd6a6d7`, `c4abc45`, `46bb988` on `feature/version-compatibility-v2`).
Tests: 242/242 pytest + 102/102 lints + 13/13 auto-fix + 21/21 regression
+ 10/10 cross-plugin + 16/16 snapshots + 16/16 gen-lint integration.

### Added

- `harvest_studio_xaml.py` and `harvest_all_supported.py` — `--deterministic` flag (also honors `CI=1` env var) drops `harvested_at` / `started_at` / `finished_at` from emitted JSON so re-runs no longer churn the ground-truth corpus
- `scaffold_project.py` — `--force-band` flag re-enables the legacy "warn and stamp anyway" behavior when `--band` disagrees with deps (default is now hard error; see Fixed below)
- `harvest_studio_xaml.py` — 10s `uip --version` reachability probe at the top of `main()` (skipped in `--scrub-only` mode); fails fast with rc=3 on missing Studio install instead of failing 5+ minutes into a scaffolding run
- `harvest_all_supported.py` — final stdout summary line `OK: N, ERROR: N, UNRESOLVED: N, TIMEOUT: N` so users see status without parsing `_bulk_summary.json`
- Golden-template fixture pairs added under `assets/lint-test-cases/` for lint rules **9** (hardcoded `idx > 2`), **14** (selector `matching:X` without `fuzzylevel`), **18** (OCREngine `sd:Image` bound to `System.Drawing.Primitives`), and **24** (deprecated-assemblies placeholder). Rules 40, 87, 89, 90, 93, 95, 99, 110 already had coverage via `test_auto_fix` and `run_lint_tests`. New `tests/test_golden_templates.py` exercises the new pairs.
- `SKILL.md` — new "Battle-test scripts (manual-only)" subsection documenting that `battle_test_studio.py` and `battle_test_activities.py` are not run by CI, have side effects (Studio invocation, temp project creation), and when to invoke them

### Fixed

- **lints_version_compat now fails loud on `version_band` ImportError** — previously a silent stderr print left lints 120/121/122 as no-ops for the rest of the process. A packaging slip-up (rename, sys.path quirk, partial-edit syntax error) could quietly ship validate_xaml without version-band enforcement. Escape hatch: set `OMC_VERSION_COMPAT_OFF=1` to keep the soft-disable behavior; failures are then logged via the module logger (not stderr print).
- **`scaffold_project --band` disagreeing with deps is now a hard error** — previously printed a warning and stamped the explicit band anyway, creating a project that would fail downstream lints. Use `--force-band` to restore the old behavior.
- **`_orchestration._read_version_band` validates int→str coerced versionBand** — previously coerced `"versionBand": <int>` to a string and passed it through with only a warning, so out-of-range ints reached lint dispatch silently. Now calls `validate_band()` after coercion and raises `ValueError` on failure.
- **`lints_version_compat._safe_read_json` logs WARNING on profile read failure** — previously swallowed `OSError` / `JSONDecodeError` and returned None silently; truncated or corrupt profile JSONs during dev would silently degrade lint behavior
- **`_data_driven.py` `list` child-element type assertion** — previously coerced any item via `str(item)`, so a dict-valued list item would silently produce `{'k': 'v'}` strings in emitted XAML. Now raises `TypeError` naming activity, child key, item index, type, and repr if any item is not `(str, int, float, bool)`.
- **`import_wizard_xaml.py` preflight assertion** — `_preflight_assert_keys_resolve()` now runs after argument parsing and asserts every `(package, version, elem)` triple in `DEFAULT_MATCHES` and `DEMOTE_NOT_AVAILABLE` resolves in the loaded index. Previously a typo or stale entry would silently no-op, quietly reverting the closed wizard intervention. All 16 currently-listed keys (11 imports + 5 demotes) verified to resolve cleanly.
- `scaffold_project.py` — `versionBand` is now stamped **before** plugin scaffold hooks, so future hooks can read it. No behavior change today; defensive ordering.
- `generate_workflow.py` — replaced bare `except ImportError` with `except ModuleNotFoundError` in the data-driven fallback path so syntax/load errors inside `_data_driven.py` surface their real message instead of being masked as `Unknown generator`
- `import_wizard_xaml.py` — `ET.fromstring` failures now increment a parse-error counter and log at WARNING with the file path; final summary includes the count (was silent swallow)

### Internal

- **`plugin_loader.get_version_profiles()` and `get_band_profile_mappings()` cache MappingProxyType snapshots** — previously deep-copied the entire profile tree on every call (lints invoke this repeatedly). Cache invalidated on `register_version_profile` / `register_band_profile_mapping` and on `_restore_registries()` rollback.
- **`plugin_loader._cleanup_failed_plugin()` helper extracted** — `_restore_registries()` and `sys.modules[pkg_name*]` cleanup now always run together. Previously the API-version-mismatch elif branch only called the registry restore; the `sys.modules` cleanup happened in the `except` block, so two consecutive API-mismatch loads could leave sub-modules cached.
- `plugin_loader.py` — added `__all__` listing the public API (`PLUGIN_API_VERSION`, register / get / discover functions) and a one-line marker declaring `PLUGIN_API_VERSION` as stable public surface
- `version_band.band_for()` — debug logging on regex-extract failure and `validate_band` failure, naming the package and version string
- `lints_version_compat` — module-import-time `assert _FALLBACK_VERSION_SENSITIVE` so the fallback set drift is caught loudly instead of silently producing empty lint coverage
- `populate_routing_metadata.py` — expanded inline comment on `system_extended.json → data_operations` mapping documenting heterogeneity rationale and TODO to subcategorize. JSON file unchanged (no recognized `_meta` key in current schema).
- `generate_routing_index.py` — review-pending marker now emits both the emoji glyph and a textual fallback `[REVIEW]` for environments that strip emoji
- `audit_coverage.py` — removed dead local `has_dispatchable_annotation`; left load-bearing `gen_function_resolves` field in place with a comment clarifying which flag drives `classify()`'s broken-annotation verdict
- `tests/test_plugin_version_profiles.py` — `test_get_version_profiles_inner_mutation_does_not_leak` rewritten to assert the new caching contract: cache invalidated on re-register, registry isolation preserved (replaces the per-call deepcopy assertion)

---

## [1.2.1] - 2026-04-25

### Added

**uipath-core — version-band-aware lints and scaffolding** (branch `feature/version-compatibility-v2`)
- `version_band.py` single-source versioning model — `ProjectVersion`, band parsing, year-based vs independent package classification, band-to-profile-version mapping
- Lint 120 (error): Version="V5"+ attributes on UiX activities are invalid below band 25
- Lint 121 (error): HealingAgentBehavior / ClipboardMode attributes don't exist below band 25 (introduced in 25.10+)
- Lint 122 (error): cross-band `Version` attribute mismatch — activity Version attr does not match the target band's profile
- Lints 120-122 are opt-in: they fire only when `project.json` contains an explicit `"versionBand"` field (opt-in via `versionBand` in `project.json`; lints 120/121 additionally gate on `band ≥ 25`, lint 122 additionally gates on profile-data presence for the (package, band) pair)
- `scaffold_project.py` auto-stamps `versionBand` when year-based dependencies are supplied via `--deps` — the band is derived from the resolved deps by `derive_band_from_deps()` in `version_band.py` (returns the max year-based band present, falls back to `None` when no year-based dep is resolved). Keeps the opt-in contract for bare scaffolds while closing the gap where downstream lints 120-122 stayed dormant on every freshly scaffolded project.
- **Plugin API v2 in `plugin_loader.py`** — new `register_version_profile` / `register_band_profile_mapping` / `get_version_profiles` / `get_band_profile_mappings`; `PLUGIN_API_VERSION` bumped 1 → 2. Plugins can now ship per-band activity profiles that lint 122 enforces. `uipath-tasks` registers `UiPath.Persistence.Activities/1.4` for bands 25 and 26.
- **`generate_workflow.py` dispatcher fall-through** — the dispatcher now tries `gen_from_annotation` before raising `Unknown generator`, so activities described purely in `references/annotations/*.json` can be emitted without a hand-written `gen_*` function. `WizardOnlyActivityError`, `MissingScopeError`, and `ReviewNeededError` are wrapped as `ValueError("Cannot generate ...")`. Adds one new core generator (`gen_from_annotation` in `generate_activities/_data_driven.py`); core generator total is now 95.
- Version profiles for UIAutomation 25.10, System 25.10 and 26.2, Excel 3.4, Mail 2.8, Testing 25.10 (uipath-core) and Persistence 1.4 (uipath-tasks)
- Annotation corpus (`references/annotations/*.json`) — 202 activity entries across 16 annotation files; data-driven generator engine in `generate_activities/_data_driven.py`
- Studio harvest tooling under `scripts/`: `harvest_studio_xaml.py`, `compare_to_ground_truth.py`, `validate_with_studio.py`, `battle_test_activities.py`, `battle_test_studio.py`, `annotate_profile_schema.py`, `backfill_annotations.py`, `backfill_profile_templates.py`

### Fixed

- `WizardOnlyActivityError` raised by `gen_from_annotation` for wizard-only stubs instead of bare `KeyError('element_tag')` — callers can now distinguish "activity not found" from "activity exists but requires Studio wizard"

### Security

- `defusedxml` safe-fallback pattern applied across the new harvest/backfill tooling for defense-in-depth against XXE/billion-laughs in XAML parsing. Coverage on this branch: `backfill_annotations.py`, `backfill_profile_templates.py`, `compare_to_ground_truth.py`, `battle_test_activities.py`, `import_wizard_xaml.py` (untracked), `harvest_all_supported.py` (untracked)

### Internal

- Lint test suite expanded with 8 new `*_project_version_compat*` fixtures (105 fixtures total under `uipath-core/assets/lint-test-cases/`)
- New `test_lints_version_compat_integration.py` drives the real `validate_project()` pipeline against the fixtures and asserts lints 120/121/122 fire (and stay silent) end-to-end. Without it, breakage between the lint dispatcher and the version-compat lint module would not be caught by the existing helper-level tests.
- Wired `lints_version_compat` into `validate_xaml/__init__.py` so lints 120/121/122 register with `_LINT_REGISTRY` on package import. Added `target_version_band` to `FileContext.__slots__` and propagated `versionBand` from `project.json` through `validate_project()` / `validate_xaml_file()` so the lints actually run against real projects (the unit tests passed previously by importing helpers directly; the dispatcher path was dead).
- `pytest uipath-core/tests/` now reports **166 passed** (no skips, no xfails)
- `SKILL.md` and `references/cheat-sheet.md` core-generator and lint-rule counts updated to match the code (was `94 generators` / `71 lint rules`; now `95 generators` / `75 lint rules`). The 71→75 lint drift is partly pre-existing (main was already at 72); this branch adds lints 120/121/122 and the new `gen_from_annotation` core generator

### Migration

- **Plugin API v1 → v2.** Out-of-tree plugins that explicitly declare `REQUIRED_API_VERSION = 1` will now fail to load with `API version mismatch: plugin wants v1, core provides v2`. Plugins that do not declare `REQUIRED_API_VERSION` are unaffected. To upgrade: bump `REQUIRED_API_VERSION` to `2` (no API surface was removed; v2 only adds `register_version_profile` / `register_band_profile_mapping` and their getters). The in-tree `uipath-tasks` plugin was bumped in the same commit as the core change.
- **Plugin migration (v1→v2):** Bump `REQUIRED_API_VERSION = 2` in your plugin's `extensions/__init__.py`. The new registration helpers are `register_version_profile(package, profile_version, profile_dict)` and `register_band_profile_mapping(band, package, profile_version)`. Call `register_band_profile_mapping` once per `(band, package)` pair (not once per package). On API-version mismatch, plugin_loader rolls back every registration the plugin made before the mismatch was detected. See `uipath-tasks/extensions/__init__.py:33,266-278` for a worked example.
- **Partial band-26 profiles are intentional.** `UiPath.System.Activities/26.2.json` is a partial profile (41/163 activities). `_build_band_expected_versions` loads every available profile for the package up to the band's canonical version in ascending order, so activities missing from 26.2.json fall back to their 25.10.json `version_attrs`. The currently-shipping 26.2.json carries the activities harvested from Studio 26.2; the rest still resolve correctly through the canonical-version walk. UIAutomation has no 26.x stable yet, so cross-band UIAutomation drift is not currently checked.

---

## [1.2.0] - 2026-04-21

### Added

**uipath-tasks — local form file emission** (PR #18, #19, #20)
- `gen_create_form_task` accepts new `dynamic_form_path` and `project_root` kwargs. When set, the generator emits `DynamicFormPath="<path>"` instead of `{x:Null}` and writes the schema to `<project_root>/<path>` in UiPath's external-file shape — `{"id": "<guid>", "form": [...]}` — per `form-tasks.md`
- When `project_root` is set but `dynamic_form_path` is empty, the generator derives `Forms/<sanitized-display-name>.json` automatically (falls back to `id_ref` when display name is the default)
- New exported helper `form_layout_to_external_file()` converts form.io `{"components": [...]}` to the UiPath shape for callers that write files themselves
- `generate_workflow.py` now threads `--project-dir` through to plugin generators via a new `_PROJECT_ROOT` module global forwarded in `_auto_dispatch`; core generators without a `project_root` parameter are unaffected because `_auto_dispatch` filters kwargs by signature

**uipath-tasks — new lint rules** (PRs #15, #17, #18)
- **AC-27** (error): `Wait*AndResume` nested in `ForEach` / `ForEachRow` / `RetryScope` / `TryCatch` / `Parallel` / `Pick` / `While` / `DoWhile`. Studio rejects with "the scope does not offer support for it". Complements file-level AC-26 with intra-file ancestor walking (commit 605f59e, fixes #14)
- **AC-28** (warn): `CreateFormTask` / `CreateExternalTask` missing or `{x:Null}` `FolderPath` — runtime error 1101
- **AC-29** (error): `<ui:InvokeMethod>` belongs in the default activities namespace, not `ui:`; Studio refuses to load the XAML
- **AC-30** (warn): `<InvokeMethod TargetObject="[expr]">` attribute form — `TargetObject` needs element form with typed `InArgument`
- **AC-31** (warn): `fdt*.Data("key")` / `edt*.Data("key")` / `FormTaskData*.Data(...)` default-indexer access — late-bound, fails under Option Strict On (BC30574). Recommends `Title` property or typed `OutArgument` variable (AC-28/29/30/31 from commit 937ca74, refs #16)
- **AC-32** (error): `DynamicFormPath` points to a file that is missing, unparseable, has wrong root key (`components` / bare array / `display: "form"` instead of `form`), or lacks the required `id`
- **AC-33** (warn): inline `FormLayout` exceeds ~500 chars of raw JSON while `DynamicFormPath` is null — large inline schemas aren't editable from Studio's form designer and poison XAML diffs (AC-32/33 from commit 87084e0)

**Documentation — form-tasks reference expansion** (commit 47c9215)
- `references/form-tasks.md` — new subsections on external form file schema (DynamicFormPath), typed output (`FormTaskData.Title` and typed `OutArgument` over `.Data("key")`), Orchestrator folder requirement, and InvokeMethod placement and element-form rules
- `references/external-tasks.md` — mirrored FolderPath and typed-output notes; Shadow Task Pattern example updated to correct InvokeMethod namespace and element form

### Fixed

- `uipath-core` Image type mapping (PR #13, #12) — `TYPE_MAP_BASE` gained `"Image": "ui:Image"`. Variables declared with `type: "Image"` (e.g. `img_Screenshot`) were previously emitted as bare `x:TypeArguments="Image"` and Studio failed with "Cannot create unknown type ... Image". The fix cascades to the variable emitter, argument normalizer, and spec validator via `TYPE_MAP_BASE`

### Internal

- New cross-plugin test file `uipath-core/scripts/test_cross_plugin.py` covers both the subprocess emit path (asserts sidecar JSON shape plus XAML attribute) and the no-project-root inline fallback for local form-file emission
- Lint test suite expanded to 92/92 with new fixtures under `uipath-tasks/assets/lint-test-cases/` covering AC-27 through AC-33

---

## [1.1.0] - 2026-04-14

### Added

**uipath-tasks plugin** (PR #11)
- New plugin covering Form Tasks, External Tasks, and Task Management — for human-in-the-loop, system-in-the-loop, and recovery patterns
- Form Task generators: `CreateFormTask`, `WaitForFormTaskAndResume`, `GetFormTasks`
- External Task generators: `CreateExternalTask`, `WaitForExternalTaskAndResume`
- Task Management generators: `CompleteTask`, `AssignTasks`
- Form.io schema design — textfield, textarea, number, select, checkbox, datagrid (DataTable binding), htmlelement (Mustache templates), columns, button
- FormData direction bindings — In (read-only), Out (user-entered), InOut (editable pre-populated, DataTable ↔ datagrid)
- Shadow Task pattern for non-blocking multi-task orchestration
- Lint rules — AC-10 (Form Create/Wait mismatch), AC-11 (FormData key mismatch), AC-12 (External Create/Wait mismatch), AC-26 (persistence activities must stay in Main.xaml)
- Scaffold hook auto-enables `supportsPersistence: true` when `UiPath.Persistence.Activities` is in project dependencies
- Battle test scenarios in `uipath-tasks/evals/tasks-battle-tests.md` with `ac` grader suite
- Registered in `.claude-plugin/marketplace.json` for Claude Code marketplace install

**Plugin loader extensions** (commits fe1454e, e598c5d)
- New registration types in `plugin_loader.py`: `register_known_activities`, `register_key_activities`, `register_hallucination_pattern`, `register_common_packages`, `register_type_mapping`, `register_variable_prefix`, `register_battle_test_grader`, `register_test_spec`, `register_lint_test_fixture`
- Plugin-registered namespaces and known activities are merged into `validate_xaml`'s `PREFIX_TO_XMLNS` and `NEEDS_IDREF` tables at load time
- xmlns validation and namespace detection extended to recognize plugin-registered prefixes

**Documentation**
- Contributors section in README with auto-generated avatar grid (commit 500ed80)
- README rewritten — qualitative descriptions instead of hardcoded counts; fixed CLI paths (`uipath-core/scripts/...`); new Plugin Architecture and Plugin Development sections; complete walkthrough video; "Using the skill" guide

### Changed

- Action Center-specific code moved out of `uipath-core` into the `uipath-tasks` plugin (commit 0dca38c)
- `uipath-action-center` renamed to `uipath-tasks` with scope expanded to include external tasks (commit 41ebaf0)

### Fixed

- `validate_snippet()` now rejects file paths and non-XAML input that previously could slip through (PR #4)
- `modify_framework` now rejects snippets containing top-level `ViewState` that produced broken framework wiring (PR #6)
- Generator output prevents Studio BC36915 compile error on `AddDataRow` with mixed-type rows (PR #10, commit 4bc31fd)
- Battle-test cleanup — xmlns pruning, plugin variable prefixes, HintSize emission on plugin generators, Assign type inference (PR #10, commit 37c6296)
- HITL battle test findings in `uipath-tasks` (commit 26d6e7c, issue #7)
- Critical issues found in version-band review (PR #2)

### Internal

- Local OMC state directory added to `.gitignore` (commit 730c11c)

---

## [1.0.0] - 2026-03-25

Initial release of **uipath-core** — the foundational skill for generating production-quality UiPath Studio projects from natural language.

### Added

**XAML Generation**
- Deterministic Python generators across UI automation, control flow, data operations, error handling, integrations, orchestrator, file system, HTTP/JSON, invoke, logging, dialogs, navigation, and application card
- JSON spec intermediate format — LLMs write JSON, generators produce structurally correct XAML
- Generators anchored to real UiPath Studio 24.10 exports
- Enum validation, namespace locking, and child element enforcement on every generated activity

**Validation Pipeline**
- Lint rules targeting LLM hallucination patterns in UiPath XAML
- Severity tiers — ERROR (Studio crash), WARN (runtime failure), INFO (best practice)
- Auto-fix support for common issues (`--fix` flag)
- Catches hallucinated properties, invalid enum values, missing xmlns declarations, placeholder paths, wrong child elements

**Project Scaffolding**
- Three project variants — simple sequence, REFramework dispatcher, REFramework performer
- Config.xlsx generation with three-sheet structure (Settings, Constants, Assets)
- Customized GetTransactionData for dispatcher (DataTable row indexing) vs performer (queue item)

**Framework Wiring**
- `modify_framework.py` — insert InvokeWorkflowFile calls, inject variables, replace scaffold markers, wire UiElement argument chains, replace placeholder expressions
- `generate_object_repository.py` — build `.objects/` tree from captured selectors
- `resolve_nuget.py` — resolve real NuGet package versions against UiPath feed, add/update deps in `project.json`
- `config_xlsx_manager.py` — add, list, and validate Config.xlsx keys against XAML references

**UI Inspection**
- Desktop inspection via PowerShell (`inspect-ui-tree.ps1`) — UIA tree capture for WPF, Win32, WinForms, DirectUI, UWP
- Web inspection workflow via Playwright MCP — multi-step process with login gate safety
- Playwright-to-UiPath selector mapping

**Plugin Architecture**
- `plugin_loader.py` API v1 — register generators, lint rules, scaffold hooks, namespaces, known activities
- Auto-discovery of sibling skill directories with `extensions/__init__.py`

**Reference Documentation**
- Reference documents covering XAML structure, expressions, selectors, decomposition, scaffolding, generation, UI inspection, and lint rules

**Test Infrastructure**
- Lint test suite, regression suite, generator snapshot tests
- Semi-automated battle test grading (`grade_battle_test.py`)
