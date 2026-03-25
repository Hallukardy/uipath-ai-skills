"""Validation orchestrators — single file and project level."""
import json
import os
import re
from pathlib import Path

from ._context import FileContext, ValidationResult
from ._structural import (
    validate_xml_wellformed, validate_root_element, validate_xclass,
    extract_declared_xmlns, extract_used_prefixes, validate_namespaces,
    validate_idrefs, validate_hintsizes, validate_arguments,
    validate_viewstate_dict, validate_invoke_paths, validate_expression_language,
)


def _get_lint_xaml_file():
    """Lazy-import lint_xaml_file from the registry."""
    from ._registry import lint_xaml_file
    return lint_xaml_file


def _get_lints_project():
    """Lazy-import project-level lint functions."""
    from . import lints_project
    return lints_project


def validate_xaml_file(filepath: str, project_dir: str | None = None,
                       strict: bool = False, lint: bool = False,
                       golden: bool = False) -> ValidationResult:
    """Run all validations on a single XAML file.

    golden: suppress warnings expected in Studio golden template exports.
    """
    result = ValidationResult(filepath)
    ctx = FileContext(filepath)

    # 1. Well-formed XML (critical — everything else depends on this)
    root = validate_xml_wellformed(ctx, result)
    if root is None:
        return result  # Can't continue

    # 2-3. Root element and x:Class
    validate_root_element(root, result)
    validate_xclass(root, filepath, result)

    # 4. Namespace declarations
    validate_namespaces(ctx, result)

    # 5-6. IdRefs and HintSizes
    validate_idrefs(ctx, result, strict)
    validate_hintsizes(ctx, result)

    # 7. Arguments
    validate_arguments(root, result, strict)

    # 8. ViewState
    validate_viewstate_dict(ctx, result)

    # 9. Invoke paths (only if project dir known)
    validate_invoke_paths(ctx, project_dir, result)

    # 10. Expression language
    validate_expression_language(ctx, result)

    # 11. Lint checks (semantic / best practices)
    if lint:
        _lint_xaml_file = _get_lint_xaml_file()
        _lint_xaml_file(ctx, result, golden=golden, project_dir=project_dir)

    return result


def validate_project_json(pj_path: str, result: ValidationResult):
    """Validate project.json basics."""
    try:
        with open(pj_path, "r", encoding="utf-8") as f:
            pj = json.load(f)
    except json.JSONDecodeError as e:
        result.error(f"Invalid JSON: {e}")
        return

    # Required fields
    for field in ["name", "projectId", "main", "dependencies", "targetFramework"]:
        if field not in pj:
            result.error(f"Missing required field: {field}")
        else:
            result.ok(f"{field}: {pj[field]}" if field != "dependencies" else f"{field}: {len(pj[field])} packages")

    # Main must point to existing file
    if "main" in pj:
        main_path = os.path.join(os.path.dirname(pj_path), pj["main"])
        if not os.path.exists(main_path):
            result.error(f"main='{pj['main']}' — file not found")

    # Dependency version format
    if "dependencies" in pj:
        for pkg, ver in pj["dependencies"].items():
            if not re.match(r'^\[[\d.]+\]$', ver):
                result.warn(f"Dependency '{pkg}': '{ver}' — expected format '[x.y.z]'")

    # Expression language
    lang = pj.get("expressionLanguage", "")
    if lang not in ("VisualBasic", "CSharp"):
        result.warn(f"expressionLanguage='{lang}' — expected 'VisualBasic' or 'CSharp'")


def validate_project(project_dir: str, strict: bool = False, lint: bool = False,
                     golden: bool = False) -> list[ValidationResult]:
    """Validate all XAML files in a project directory.

    Auto-detects multi-project asset directories: if no project.json at root,
    scans immediate subdirectories for project.json and validates each as a
    separate project with its own cross-reference context.
    """
    results = []

    pj_path = os.path.join(project_dir, "project.json")

    if os.path.exists(pj_path):
        # Single project — validate project.json + all XAML with this root
        pj_result = ValidationResult(pj_path)
        validate_project_json(pj_path, pj_result)
        results.append(pj_result)

        for root_dir, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d != "lint-test-cases"]
            for fname in sorted(files):
                if fname.endswith(".xaml") and not fname.startswith("~"):
                    # Skip temp files generated during framework wiring
                    if fname.startswith("_tmp_") or fname.startswith("spec_"):
                        continue
                    fpath = os.path.join(root_dir, fname)
                    result = validate_xaml_file(fpath, project_dir, strict, lint, golden)
                    results.append(result)

        # Project-level cross-reference: Config.xlsx vs XAML Config() keys
        if lint:
            _lp = _get_lints_project()
            config_result = _lp.lint_config_xlsx_crossref(project_dir, results)
            if config_result:
                results.append(config_result)

            objrepo_result = _lp.lint_object_repository_missing(project_dir, results)
            if objrepo_result:
                results.append(objrepo_result)

            from dependency_graph import lint_dependency_graph
            dep_result = lint_dependency_graph(project_dir)
            if dep_result:
                results.append(dep_result)
    else:
        # No project.json at root — check for sub-projects
        sub_projects = []
        loose_dirs = []
        for entry in sorted(os.listdir(project_dir)):
            sub = os.path.join(project_dir, entry)
            if os.path.isdir(sub):
                if entry == "lint-test-cases":
                    continue
                if os.path.exists(os.path.join(sub, "project.json")):
                    sub_projects.append(sub)
                else:
                    loose_dirs.append(sub)

        if sub_projects:
            # Multi-project asset directory — validate each sub-project independently
            for sp in sub_projects:
                results.extend(validate_project(sp, strict, lint, golden))

            # Validate loose directories (no project.json) without cross-ref checking
            for ld in loose_dirs:
                for root_dir, dirs, files in os.walk(ld):
                    dirs[:] = [d for d in dirs if d != "lint-test-cases"]
                    for fname in sorted(files):
                        if fname.endswith(".xaml"):
                            fpath = os.path.join(root_dir, fname)
                            result = validate_xaml_file(fpath, None, strict, lint, golden)
                            results.append(result)
        else:
            # No sub-projects found either — validate all files without cross-ref
            for root_dir, dirs, files in os.walk(project_dir):
                dirs[:] = [d for d in dirs if d != "lint-test-cases"]
                for fname in sorted(files):
                    if fname.endswith(".xaml"):
                        fpath = os.path.join(root_dir, fname)
                        result = validate_xaml_file(fpath, None, strict, lint, golden)
                        results.append(result)

    return results
