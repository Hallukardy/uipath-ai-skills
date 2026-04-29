#!/usr/bin/env python3
"""Compile a JSON spec to XAML and inject the activity body into a REFramework
file.

Replaces the common one-off "spec → snippet → modify_framework" glue script
that users would otherwise hand-roll for every Dispatcher+Performer scaffold.

Pipeline:
  1. Load spec.json.
  2. `generate_workflow.generate_workflow(spec)` → full XAML string.
  3. `extract_sequence_body()` → inner activities of the outer <Sequence>.
  4. `strip_leading_viewstate()` → drop ViewState dict (destination owns it).
  5. `modify_framework.cmd_insert_invoke()` or `cmd_replace_marker()`.

Usage:
    python inject_spec.py insert  <spec.json> <target.xaml>
    python inject_spec.py replace <spec.json> <target.xaml> <MARKER_NAME>

Examples:
    # Append a snippet inside InitAllApplications.xaml's outer Sequence:
    python inject_spec.py insert  specs/init.json Framework/InitAllApplications.xaml

    # Replace the SCAFFOLD.PROCESS_BODY marker in Process.xaml:
    python inject_spec.py replace specs/process.json Framework/Process.xaml PROCESS_BODY

Exit code is 0 on success, non-zero on any failure (spec parse, generation,
extraction, or marker mismatch).
"""
import argparse
import json
import sys
from pathlib import Path

# Make scripts/ importable when run as a file path. Mirrors the pattern in
# modify_framework.py so plugin extensions and helper modules resolve.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_workflow  # noqa: E402
import modify_framework  # noqa: E402
from generate_activities._xml_utils import (  # noqa: E402
    extract_sequence_body,
    strip_leading_viewstate,
)


def _build_body(spec_path: Path) -> str:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    xaml = generate_workflow.generate_workflow(spec)
    return strip_leading_viewstate(extract_sequence_body(xaml))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile a JSON spec and inject its body into a REFramework file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="op", required=True)

    p_insert = sub.add_parser(
        "insert",
        help="Insert the spec body before </Sequence> in the target file.",
    )
    p_insert.add_argument("spec", help="Path to the JSON spec.")
    p_insert.add_argument("target", help="Path to the framework .xaml file.")

    p_replace = sub.add_parser(
        "replace",
        help="Replace a SCAFFOLD.<MARKER> Comment in target with the spec body.",
    )
    p_replace.add_argument("spec", help="Path to the JSON spec.")
    p_replace.add_argument("target", help="Path to the framework .xaml file.")
    p_replace.add_argument("marker", help="Marker name (e.g. PROCESS_BODY).")

    args = parser.parse_args(argv)

    spec_path = Path(args.spec).resolve()
    target_path = Path(args.target).resolve()
    if not spec_path.is_file():
        print(f"spec not found: {spec_path}", file=sys.stderr)
        return 2
    if not target_path.is_file():
        print(f"target not found: {target_path}", file=sys.stderr)
        return 2

    try:
        body = _build_body(spec_path)
    except Exception as exc:
        print(f"Failed to compile spec → body: {exc}", file=sys.stderr)
        return 1

    if args.op == "insert":
        ok = modify_framework.cmd_insert_invoke(str(target_path), body)
    else:  # replace
        ok = modify_framework.cmd_replace_marker(
            str(target_path), args.marker, body
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
