# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0] - 2026-03-25

Initial release of **uipath-core** — the foundational skill for generating production-quality UiPath Studio projects from natural language.

### Added

**XAML Generation**
- 94 deterministic Python generators across 13 categories (UI automation, control flow, data operations, error handling, integrations, orchestrator, file system, HTTP/JSON, invoke, logging, dialogs, navigation, application card)
- JSON spec intermediate format — LLMs write JSON, generators produce structurally correct XAML
- All generators anchored to real UiPath Studio 24.10 exports
- Enum validation, namespace locking, and child element enforcement on every generated activity

**Validation Pipeline**
- 71 lint rules targeting LLM hallucination patterns in UiPath XAML
- Severity tiers: ERROR (Studio crash), WARN (runtime failure), INFO (best practice)
- Auto-fix support for common issues (`--fix` flag)
- Catches hallucinated properties, invalid enum values, missing xmlns declarations, placeholder paths, wrong child elements

**Project Scaffolding**
- Three project variants: simple sequence, REFramework dispatcher, REFramework performer
- Config.xlsx generation with three-sheet structure (Settings, Constants, Assets)
- Customized GetTransactionData for dispatcher (DataTable row indexing) vs performer (queue item)

**Framework Wiring**
- `modify_framework.py` — insert InvokeWorkflowFile calls, inject variables, replace scaffold markers, wire UiElement argument chains, replace placeholder expressions
- `generate_object_repository.py` — build `.objects/` tree from captured selectors
- `resolve_nuget.py` — resolve real NuGet package versions against UiPath feed, add/update deps in project.json
- `config_xlsx_manager.py` — add, list, and validate Config.xlsx keys against XAML references

**UI Inspection**
- Desktop inspection via PowerShell (`inspect-ui-tree.ps1`) — UIA tree capture for WPF, Win32, WinForms, DirectUI, UWP
- Web inspection workflow via Playwright MCP — 5-step process with login gate safety
- Playwright-to-UiPath selector mapping

**Plugin Architecture**
- `plugin_loader.py` API v1 — register generators, lint rules, scaffold hooks, namespaces, known activities
- Auto-discovery of sibling skill directories with `extensions/__init__.py`

**Reference Documentation**
- 24 reference documents covering XAML structure, expressions, selectors, decomposition, scaffolding, generation, UI inspection, and lint rules

**Test Infrastructure**
- 81 lint test cases
- 18 regression tests
- Generator snapshot tests
- Semi-automated battle test grading (`grade_battle_test.py`)
