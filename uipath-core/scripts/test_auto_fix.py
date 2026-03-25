#!/usr/bin/env python3
"""Auto-fix regression tests.

For each fixable lint, copies the bad test file to a temp directory,
runs auto_fix_file(), asserts fixes were applied, re-validates to confirm
the target lint is gone, and checks idempotency.

Usage:
    python3 scripts/test_auto_fix.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

VALIDATE = os.path.join(SCRIPT_DIR, "validate_xaml")
TEST_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "assets", "lint-test-cases")

from validate_xaml import auto_fix_file

# (source_file, lint_number, expected_fix_substring)
FIXABLE_TESTS = [
    ("bad_double_bracket_expr.xaml", 83, "lint 83"),
    ("bad_double_escaped_quotes.xaml", 71, "lint 71"),
    ("bad_selector_double_quotes.xaml", 89, "lint 89"),
    ("bad_selector_double_escaped.xaml", 90, "lint 90"),
    ("bad_invalid_array_type.xaml", 93, "lint 93"),
    ("bad_fqdn_type_arguments.xaml", 99, "lint 99"),
    ("bad_queue_name_property.xaml", 54, "lint 54"),
    ("bad_gettext_interactionmode.xaml", 53, "lint 53"),
    ("bad_bare_datatable_type.xaml", 87, "lint 87"),
    ("bad_throw_csharp.xaml", 7, "lint 7"),
    ("bad_empty_field_mode.xaml", 70, "lint 70"),
]


def run_validate_lint(filepath: str) -> str:
    """Run validate_xaml --lint on a single file and return stdout+stderr."""
    result = subprocess.run(
        [sys.executable, VALIDATE, "--lint", filepath],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.stdout + result.stderr


def test_fix_and_idempotency(source_file: str, lint_number: int,
                              expected_substr: str) -> tuple[bool, str]:
    """Test that auto_fix_file fixes the lint and is idempotent.

    Returns (passed, message).
    """
    src = os.path.join(TEST_DIR, source_file)
    if not os.path.isfile(src):
        return False, f"Source file not found: {src}"

    with tempfile.TemporaryDirectory() as td:
        dst = os.path.join(td, source_file)
        shutil.copy2(src, dst)

        # --- Pre-check: lint fires before fix ---
        pre_output = run_validate_lint(dst)
        lint_tag = f"lint {lint_number}"
        if lint_tag not in pre_output:
            return False, f"Pre-fix: expected '{lint_tag}' in output but not found"

        # --- Apply fix ---
        fixes = auto_fix_file(dst)
        if not fixes:
            return False, "auto_fix_file() returned no fixes"
        if not any(expected_substr in f for f in fixes):
            return False, f"Expected '{expected_substr}' in fixes, got: {fixes}"

        # --- Post-check: lint should be gone ---
        post_output = run_validate_lint(dst)
        # Check that the specific lint number no longer appears as ERROR
        lint_pattern = rf'\[lint {lint_number}\]'
        post_errors = [line for line in post_output.splitlines()
                       if re.search(lint_pattern, line) and ("[ERROR]" in line or "[WARN]" in line)]
        if post_errors:
            return False, f"Post-fix: lint {lint_number} still fires: {post_errors[0]}"

        # --- Idempotency: second run should produce no fixes ---
        fixes2 = auto_fix_file(dst)
        if fixes2:
            return False, f"Idempotency failed: second run produced: {fixes2}"

        # --- XML well-formedness after fix ---
        if "Well-formed XML" not in post_output:
            return False, "Post-fix: file is no longer well-formed XML"

    return True, f"fixed ({', '.join(fixes)})"


def test_bom_preservation():
    """Verify that auto_fix_file preserves UTF-8 BOM when present."""
    src = os.path.join(TEST_DIR, "bad_fqdn_type_arguments.xaml")
    if not os.path.isfile(src):
        return False, "Source file not found"

    with tempfile.TemporaryDirectory() as td:
        dst = os.path.join(td, "bom_test.xaml")

        # Read original, prepend BOM, write
        with open(src, "r", encoding="utf-8-sig") as f:
            content = f.read()
        with open(dst, "w", encoding="utf-8-sig") as f:
            f.write(content)

        # Verify BOM exists
        with open(dst, "rb") as f:
            assert f.read(3) == b'\xef\xbb\xbf', "BOM not written"

        # Apply fix
        fixes = auto_fix_file(dst)
        if not fixes:
            return False, "No fixes applied to BOM test file"

        # Verify BOM is preserved
        with open(dst, "rb") as f:
            first_bytes = f.read(3)
        if first_bytes != b'\xef\xbb\xbf':
            return False, f"BOM was stripped! First bytes: {first_bytes!r}"

    return True, "BOM preserved after fix"


def test_no_bom_stays_no_bom():
    """Verify that auto_fix_file does NOT add a BOM to non-BOM files."""
    src = os.path.join(TEST_DIR, "bad_fqdn_type_arguments.xaml")
    if not os.path.isfile(src):
        return False, "Source file not found"

    with tempfile.TemporaryDirectory() as td:
        dst = os.path.join(td, "no_bom_test.xaml")

        # Write without BOM
        with open(src, "r", encoding="utf-8-sig") as f:
            content = f.read()
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)

        # Verify no BOM
        with open(dst, "rb") as f:
            assert f.read(3) != b'\xef\xbb\xbf', "File unexpectedly has BOM"

        # Apply fix
        fixes = auto_fix_file(dst)
        if not fixes:
            return False, "No fixes applied"

        # Verify still no BOM
        with open(dst, "rb") as f:
            first_bytes = f.read(3)
        if first_bytes == b'\xef\xbb\xbf':
            return False, "BOM was added to non-BOM file!"

    return True, "no-BOM preserved after fix"


def main():
    passed = 0
    failed = 0
    total = len(FIXABLE_TESTS) + 2  # +2 for BOM tests

    print(f"Running {total} auto-fix tests...\n")

    for source_file, lint_number, expected_substr in FIXABLE_TESTS:
        ok, msg = test_fix_and_idempotency(source_file, lint_number, expected_substr)
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  lint {lint_number:>3} ({source_file}) — {msg}")
        if ok:
            passed += 1
        else:
            failed += 1

    # BOM tests
    ok, msg = test_bom_preservation()
    status = "PASS" if ok else "FAIL"
    print(f"  {status}  BOM preservation — {msg}")
    if ok:
        passed += 1
    else:
        failed += 1

    ok, msg = test_no_bom_stays_no_bom()
    status = "PASS" if ok else "FAIL"
    print(f"  {status}  No-BOM preservation — {msg}")
    if ok:
        passed += 1
    else:
        failed += 1

    print(f"\n{'='*50}")
    print(f"AUTO-FIX TESTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*50}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
