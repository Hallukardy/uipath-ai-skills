"""CLI entry point for validate_xaml."""
import argparse
import os
import sys

# Ensure UTF-8 output on all platforms (Windows cmd defaults to cp1252)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ._constants import _RE_CONFIG_KEYS_SUMMARY
from ._context import ValidationResult
from ._orchestration import validate_xaml_file, validate_project, validate_project_json
from ._fixes import auto_fix_file


def main():

    parser = argparse.ArgumentParser(description="Validate UiPath XAML files")
    parser.add_argument("path", help="XAML file or project directory to validate")
    parser.add_argument("--strict", action="store_true", help="Enable strict checks (naming conventions)")
    parser.add_argument("--lint", action="store_true", help="Enable semantic lint checks (best practices)")
    parser.add_argument("--quiet", action="store_true", help="Only show files with errors or warnings")
    parser.add_argument("--errors-only", action="store_true", dest="errors_only",
                        help="Show only errors and warnings, suppress [OK] lines. Best for generate→validate→fix loop")
    parser.add_argument("--golden", action="store_true",
                        help="Golden template mode — suppress warnings expected in Studio exports "
                             "(naming conventions, Config .ToString, missing DisplayName)")
    parser.add_argument("--config-keys", action="store_true", dest="config_keys",
                        help="Extract and list all Config.xlsx keys referenced across all XAML files")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix deterministic lint violations in-place "
                             "(lints 53, 54, 71, 83, 87, 89, 90, 93, 99). Implies --lint. "
                             "Writes corrected files and re-validates.")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="With --fix: show what would be fixed without writing files.")
    parser.add_argument("--graph", action="store_true",
                        help="Output dependency graph in DOT format (Graphviz)")
    args = parser.parse_args()

    # --config-keys needs lint to extract Config references
    if args.config_keys:
        args.lint = True
    if args.fix:
        args.lint = True

    path = args.path

    if os.path.isfile(path):
        if path.endswith(".xaml"):
            # Single file — try to detect project dir
            project_dir = os.path.dirname(os.path.dirname(path)) if "Framework" in path else os.path.dirname(path)
            results = [validate_xaml_file(path, project_dir, args.strict, args.lint, args.golden)]
        elif path.endswith(".json"):
            result = ValidationResult(path)
            validate_project_json(path, result)
            results = [result]
        else:
            print(f"Unknown file type: {path}", file=sys.stderr)
            sys.exit(1)
    elif os.path.isdir(path):
        results = validate_project(path, args.strict, args.lint, args.golden)
    else:
        print(f"Path not found: {path}", file=sys.stderr)
        sys.exit(1)

    # Config keys aggregation mode
    if args.config_keys:
        all_keys: dict[str, list[str]] = {}  # key -> list of files
        for r in results:
            for msg in r.info:
                if "[lint 39]" in msg:
                    # Extract keys from the message
                    match = _RE_CONFIG_KEYS_SUMMARY.search(msg)
                    if match:
                        keys = [k.strip() for k in match.group(1).split(",")]
                        fname = os.path.basename(r.filepath)
                        for k in keys:
                            all_keys.setdefault(k, []).append(fname)

        if all_keys:
            # Auto-categorize keys by sheet (see config-sample.md decision flowchart)
            SETTINGS_KEYS = {
                "OrchestratorQueueName", "OrchestratorQueueFolder",
                "logF_BusinessProcessName",
            }
            CONSTANTS_KEYS = {
                "MaxRetryNumber", "MaxConsecutiveSystemExceptions",
                "RetryNumberGetTransactionItem", "RetryNumberSetTransactionStatus",
                "ExScreenshotsFolderPath", "ShouldMarkJobAsFaulted",
            }
            CONSTANTS_PREFIXES = ("LogMessage_", "ExceptionMessage_")

            def classify_key(key: str) -> str:
                if key in SETTINGS_KEYS:
                    return "Settings"
                if key in CONSTANTS_KEYS or key.startswith(CONSTANTS_PREFIXES):
                    return "Constants"
                # Credential asset name references → Settings (just a string, no API call)
                if "CredentialAsset" in key or "Credential" in key:
                    return "Settings"
                # URLs, endpoints, paths, shared config → Assets
                return "Assets"

            sheets: dict[str, dict[str, list[str]]] = {
                "Settings": {}, "Constants": {}, "Assets": {}
            }
            for key in all_keys:
                sheet = classify_key(key)
                sheets[sheet][key] = all_keys[key]

            print("\n📋 Required Config.xlsx entries (grouped by sheet):")
            for sheet_name in ("Settings", "Constants", "Assets"):
                sheet_keys = sheets[sheet_name]
                if sheet_keys:
                    print(f"\n  {sheet_name} sheet:")
                    for key in sorted(sheet_keys):
                        files = ", ".join(sorted(set(sheet_keys[key])))
                        print(f"    {key:<40} (used in: {files})")
                else:
                    print(f"\n  {sheet_name} sheet: (none — framework defaults sufficient)")
            print(f"\nTotal: {len(all_keys)} Config keys across {len(results)} files")
            print("Note: Sheet assignment is heuristic — see config-sample.md for decision flowchart.")
        else:
            print("No Config() references found in XAML files.")
        sys.exit(0)

    # --graph mode: output dependency graph in DOT format
    if args.graph:
        if os.path.isdir(path):
            from dependency_graph import build_dependency_graph, analyze_graph, export_dot
            graph = build_dependency_graph(path)
            analysis = analyze_graph(graph)
            print(export_dot(graph, analysis))
        else:
            print("--graph requires a project directory, not a single file.", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # --fix mode: apply auto-fixes, then re-validate
    if args.fix:
        dry_run = getattr(args, "dry_run", False)
        all_fixes = []
        xaml_files = [r.filepath for r in results
                      if r.filepath.endswith(".xaml") and os.path.isfile(r.filepath)]
        for fpath in xaml_files:
            fixes = auto_fix_file(fpath, dry_run=dry_run)
            if fixes:
                all_fixes.append((os.path.basename(fpath), fixes))

        if all_fixes:
            label = "DRY-RUN (no files written)" if dry_run else "AUTO-FIX"
            print(f"\n{'='*60}")
            print(f"{label}: {'Would fix' if dry_run else 'Applied fixes to'} {len(all_fixes)} file(s)")
            print(f"{'='*60}")
            for fname, fixes in all_fixes:
                for fix in fixes:
                    print(f"  {fname}: {fix}")

            # Re-validate after fixes (skip in dry-run — files unchanged)
            if not dry_run:
                print(f"\n--- Re-validating after fixes ---\n")
                if os.path.isfile(path):
                    project_dir = os.path.dirname(os.path.dirname(path)) if "Framework" in path else os.path.dirname(path)
                    results = [validate_xaml_file(path, project_dir, args.strict, args.lint, args.golden)]
                elif os.path.isdir(path):
                    results = validate_project(path, args.strict, args.lint, args.golden)
        else:
            print("\nNo auto-fixable issues found.")

    # Print results
    total_errors = 0
    total_warnings = 0
    eo = args.errors_only
    for r in results:
        if (args.quiet or eo) and r.passed and not r.warnings:
            continue
        print(r.summary(errors_only=eo))
        total_errors += len(r.errors)
        total_warnings += len(r.warnings)

    # Summary
    file_count = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{file_count} files passed, {total_errors} errors, {total_warnings} warnings")
    print(f"{'='*60}")

    sys.exit(0 if total_errors == 0 else 1)


if __name__ == "__main__":
    main()
