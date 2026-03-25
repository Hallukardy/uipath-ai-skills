#!/usr/bin/env python3
"""Unified test runner — executes all 7 test suites sequentially.

Usage:
    python3 scripts/test_all.py
    python3 scripts/test_all.py --verbose
    python3 scripts/test_all.py --only lint_tests
    python3 scripts/test_all.py --fail-fast
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

# (short_name, script_filename, supports_verbose, is_unittest)
SUITES = [
    ("generator_snapshots",        "test_generator_snapshots.py",        True,  False),
    ("generator_lint_integration", "test_generator_lint_integration.py", True,  False),
    ("cross_plugin",               "test_cross_plugin.py",               True,  False),
    ("lint_tests",                 "run_lint_tests.py",                  False, False),
    ("auto_fix",                   "test_auto_fix.py",                   False, False),
    ("dependency_graph",           "test_dependency_graph.py",           False, True),
    ("regression",                 "regression_test.py",                 True,  False),
]

# Regex for custom test summaries: "15/15 passed"
RE_CUSTOM = re.compile(r"(\d+)/(\d+) passed")
# Regex for unittest output on stderr: "Ran 17 tests"
RE_UNITTEST_RAN = re.compile(r"Ran (\d+) tests?")


def parse_custom(stdout: str) -> tuple[int, int] | None:
    """Extract (passed, total) from the last 'X/Y passed' line."""
    matches = RE_CUSTOM.findall(stdout)
    if matches:
        passed, total = matches[-1]
        return int(passed), int(total)
    return None


def parse_unittest(stderr: str) -> tuple[int, int] | None:
    """Extract (passed, total) from unittest stderr output."""
    m = RE_UNITTEST_RAN.search(stderr)
    if not m:
        return None
    total = int(m.group(1))
    ok = "OK" in stderr and "FAILED" not in stderr
    return (total, total) if ok else (0, total)


def run_suite(name: str, script: str, verbose: bool,
              is_unittest: bool, supports_verbose: bool) -> tuple[bool, int, int, str]:
    """Run a single test suite. Returns (ok, passed, total, output)."""
    cmd = [sys.executable, str(SCRIPTS_DIR / script)]
    if verbose and supports_verbose:
        cmd.append("--verbose")

    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

    if is_unittest:
        result = parse_unittest(proc.stderr)
    else:
        result = parse_custom(proc.stdout)

    if result:
        passed, total = result
    else:
        # Fallback: treat exit code as pass/fail for 1 test
        passed = 1 if proc.returncode == 0 else 0
        total = 1

    ok = proc.returncode == 0
    output = proc.stdout + proc.stderr if verbose else ""
    return ok, passed, total, output


def main():
    parser = argparse.ArgumentParser(description="Run all test suites")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Pass --verbose to subscripts that support it")
    parser.add_argument("--only", metavar="NAME",
                        help="Run single suite by short name")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop on first failure")
    args = parser.parse_args()

    suites = SUITES
    if args.only:
        suites = [s for s in suites if s[0] == args.only]
        if not suites:
            valid = ", ".join(s[0] for s in SUITES)
            print(f"Unknown suite '{args.only}'. Valid names: {valid}")
            sys.exit(2)

    print(f"Running {len(suites)} test suite{'s' if len(suites) != 1 else ''}...\n")

    results = []  # (name, ok, passed, total)

    for name, script, supports_verbose, is_unittest in suites:
        ok, passed, total, output = run_suite(
            name, script, args.verbose, is_unittest, supports_verbose)
        results.append((name, ok, passed, total))

        tag = "  PASS" if ok else "  FAIL"
        counts = f"{passed}/{total}"
        print(f"{tag}  {name:<30s} {counts:>6s}")
        if args.verbose and output:
            for line in output.rstrip().splitlines():
                print(f"        {line}")

        if not ok and args.fail_fast:
            print("\n--fail-fast: stopping after first failure.")
            break

    # Aggregate summary
    suites_passed = sum(1 for _, ok, _, _ in results if ok)
    suites_total = len(results)
    all_ok = suites_passed == suites_total

    print(f"\n{'=' * 60}")
    if all_ok:
        print(f"ALL SUITES: {suites_passed}/{suites_total} passed — all clear")
    else:
        print(f"ALL SUITES: {suites_passed}/{suites_total} passed — "
              f"{suites_total - suites_passed} FAILED")
    print(f"{'=' * 60}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
