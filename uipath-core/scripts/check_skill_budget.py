#!/usr/bin/env python3
"""Skill token budget checker.

Estimates token counts for SKILL.md files and warns if they exceed the
budget target defined in Rule K-1 (≤8,000 tokens for 1M-context models).

Token estimation uses word count × 1.3, which is a reasonable approximation
for English markdown content with code fragments.

Usage:
    python3 scripts/check_skill_budget.py                    # check all skills
    python3 scripts/check_skill_budget.py path/to/SKILL.md   # check one file
    python3 scripts/check_skill_budget.py --strict            # fail on warnings too
"""

import argparse
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Budget constants (Rule K-1)
TOKEN_BUDGET_PER_SKILL = 8_000
TOKEN_ESTIMATION_FACTOR = 1.3  # words → approximate tokens
WARN_THRESHOLD = 0.75  # warn at 75% of budget


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using word-based heuristic."""
    words = len(text.split())
    return int(words * TOKEN_ESTIMATION_FACTOR)


def check_skill_file(path: Path) -> dict:
    """Check a single SKILL.md file against the token budget."""
    text = path.read_text(encoding="utf-8")
    words = len(text.split())
    tokens = estimate_tokens(text)
    lines = text.count("\n") + 1

    status = "OK"
    if tokens > TOKEN_BUDGET_PER_SKILL:
        status = "OVER"
    elif tokens > TOKEN_BUDGET_PER_SKILL * WARN_THRESHOLD:
        status = "WARN"

    return {
        "path": path,
        "words": words,
        "tokens": tokens,
        "lines": lines,
        "status": status,
        "budget": TOKEN_BUDGET_PER_SKILL,
        "pct": tokens / TOKEN_BUDGET_PER_SKILL * 100,
    }


def find_all_skills(skills_root: Path) -> list[Path]:
    """Find all SKILL.md files under the skills directory."""
    return sorted(skills_root.glob("*/SKILL.md"))


def main():
    parser = argparse.ArgumentParser(description="Check SKILL.md token budgets (Rule K-1)")
    parser.add_argument("path", nargs="?", help="Path to a specific SKILL.md file")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings too")
    args = parser.parse_args()

    # Find skill files
    if args.path:
        files = [Path(args.path)]
    else:
        script_dir = Path(__file__).resolve().parent
        skills_root = script_dir.parent.parent  # .claude/skills/
        files = find_all_skills(skills_root)

    if not files:
        print("No SKILL.md files found.")
        sys.exit(1)

    # Check each file
    results = [check_skill_file(f) for f in files]

    # Report
    print(f"{'Skill':<30} {'Words':>6} {'~Tokens':>8} {'Budget':>7} {'Used':>6}  Status")
    print("-" * 75)

    has_error = False
    has_warn = False

    for r in results:
        skill_name = r["path"].parent.name
        marker = ""
        if r["status"] == "OVER":
            marker = " << OVER BUDGET"
            has_error = True
        elif r["status"] == "WARN":
            marker = " (approaching limit)"
            has_warn = True

        print(f"{skill_name:<30} {r['words']:>6} {r['tokens']:>8} {r['budget']:>7} {r['pct']:>5.1f}%  {r['status']}{marker}")

    # Summary
    total_tokens = sum(r["tokens"] for r in results)
    print("-" * 75)
    print(f"{'Total':<30} {'':>6} {total_tokens:>8}         {total_tokens / 1_000_000 * 100:.2f}% of 1M context")

    if has_error:
        print("\nRule K-1 violation: one or more skills exceed the 8,000 token budget.")
        sys.exit(1)
    elif has_warn and args.strict:
        print("\nWarning (--strict): one or more skills approaching budget limit.")
        sys.exit(1)


if __name__ == "__main__":
    main()
