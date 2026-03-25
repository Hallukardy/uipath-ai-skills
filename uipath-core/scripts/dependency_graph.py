"""Workflow dependency graph analysis for the UiPath validation pipeline.

Builds a directed graph of InvokeWorkflowFile references across .xaml files,
detects circular dependencies and orphaned workflows, and optionally exports
the graph in Graphviz DOT format.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import deque

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Regex – intentionally self-contained; do NOT import from validate_xaml.py
# ---------------------------------------------------------------------------
_RE_WORKFLOW_FILENAME = re.compile(r'WorkflowFileName="([^"]*)"')
# Scaffold body snippet markers: bare file paths as text nodes in framework XAML
_RE_SCAFFOLD_MARKER = re.compile(r'[A-Za-z]:/[^\s<>]+\.xaml\b')

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DependencyGraph:
    """Directed graph of workflow file dependencies."""
    edges: dict[str, set[str]] = field(default_factory=dict)
    all_files: set[str] = field(default_factory=set)
    entry_point: str | None = None
    missing_targets: set[str] = field(default_factory=set)
    has_scaffold_markers: bool = False  # True if any file has un-inlined body snippet paths


@dataclass
class GraphAnalysis:
    """Results produced by :func:`analyze_graph`."""
    cycles: list[list[str]] = field(default_factory=list)
    orphaned: set[str] = field(default_factory=set)
    missing_targets: set[str] = field(default_factory=set)
    entry_point: str | None = None


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_dependency_graph(project_dir: str) -> DependencyGraph:
    """Walk *project_dir* and build a :class:`DependencyGraph`.

    * Scans all ``.xaml`` files recursively (skipping ``lint-test-cases``
      directories).
    * Extracts ``WorkflowFileName`` references via regex.
    * Reads ``project.json`` for the entry-point (``main`` field).
    """
    graph = DependencyGraph()
    project_dir = os.path.normpath(project_dir)

    # --- Collect .xaml files and their invocations --------------------------
    for dirpath, dirnames, filenames in os.walk(project_dir):
        # Skip lint test-case directories
        dirnames[:] = [d for d in dirnames if d != "lint-test-cases"]

        for fname in filenames:
            if not fname.lower().endswith(".xaml"):
                continue

            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, project_dir).replace("\\", "/")
            graph.all_files.add(rel_path)

            try:
                with open(abs_path, encoding="utf-8-sig") as fh:
                    content = fh.read()
            except (OSError, UnicodeDecodeError):
                continue

            targets: set[str] = set()
            for match in _RE_WORKFLOW_FILENAME.finditer(content):
                raw = match.group(1).replace("\\", "/")

                # Skip dynamic / variable-based paths
                if raw.startswith("["):
                    continue

                # Check whether the target file actually exists on disk
                target_abs = os.path.normpath(os.path.join(project_dir, raw))
                if not os.path.isfile(target_abs):
                    graph.missing_targets.add(raw)
                    continue

                targets.add(raw)

            # Detect scaffold markers (un-inlined body snippet file paths).
            # When a framework file contains a bare file path as a text node
            # (e.g., "C:/Users/.../Temp/dispatcher_init_snippet.xaml"), the
            # file is in an intermediate state: body snippets generated but
            # not yet wired via modify_framework.py.  In this state, framework
            # files (InitAllApplications, Process, GetTransactionData,
            # CloseAllApplications) cannot reach Workflows/ via
            # InvokeWorkflowFile edges because those calls are inside the
            # un-inlined snippet.  Mark the graph so lint_dependency_graph can
            # suppress orphan warnings accordingly.
            if _RE_SCAFFOLD_MARKER.search(content):
                graph.has_scaffold_markers = True

            if targets:
                graph.edges[rel_path] = targets

    # --- Read entry point from project.json --------------------------------
    project_json = os.path.join(project_dir, "project.json")
    if os.path.isfile(project_json):
        try:
            with open(project_json, encoding="utf-8-sig") as fh:
                data = json.load(fh)
            main = data.get("main", None)
            if main:
                graph.entry_point = main.replace("\\", "/")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"[dependency_graph] Warning: failed to parse {project_json}: {exc}",
                  file=sys.stderr)

    return graph


# ---------------------------------------------------------------------------
# Graph analysis
# ---------------------------------------------------------------------------

def analyze_graph(graph: DependencyGraph) -> GraphAnalysis:
    """Detect cycles and orphaned workflows in *graph*."""
    analysis = GraphAnalysis(
        missing_targets=set(graph.missing_targets),
        entry_point=graph.entry_point,
    )

    # --- Cycle detection (iterative three-colour DFS) ----------------------
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph.all_files}
    parent: dict[str, str | None] = {}
    cycles: list[list[str]] = []

    for start in graph.all_files:
        if color[start] != WHITE:
            continue

        stack: list[tuple[str, bool]] = [(start, False)]
        parent[start] = None

        while stack:
            node, processed = stack.pop()

            if processed:
                color[node] = BLACK
                continue

            if color[node] == GRAY:
                # Already being processed; push the finish marker only
                stack.append((node, True))
                continue

            color[node] = GRAY
            # Push a finish marker so we can turn the node BLACK later
            stack.append((node, True))

            for neighbour in graph.edges.get(node, ()):
                if neighbour not in color:
                    # Target is not in all_files (e.g. missing); skip
                    continue

                if color[neighbour] == WHITE:
                    parent[neighbour] = node
                    stack.append((neighbour, False))
                elif color[neighbour] == GRAY:
                    # Back edge detected (node → neighbour).
                    # Reconstruct cycle by walking parent pointers from
                    # *node* back to *neighbour* (reverse tree-edge order),
                    # then reversing to get forward-edge order.
                    path: list[str] = [node]
                    cur = node
                    while cur != neighbour:
                        cur = parent.get(cur)  # type: ignore[assignment]
                        if cur is None:
                            break
                        path.append(cur)
                    path.reverse()            # now: neighbour → … → node
                    path.append(neighbour)    # close the loop
                    cycles.append(path)

    analysis.cycles = cycles

    # --- Orphan detection (BFS from entry point) ---------------------------
    if graph.entry_point and graph.entry_point in graph.all_files:
        reachable: set[str] = set()
        queue: deque[str] = deque([graph.entry_point])
        while queue:
            node = queue.popleft()
            if node in reachable:
                continue
            reachable.add(node)
            for neighbour in graph.edges.get(node, ()):
                if neighbour in graph.all_files and neighbour not in reachable:
                    queue.append(neighbour)
        analysis.orphaned = graph.all_files - reachable

    return analysis


# ---------------------------------------------------------------------------
# Linting entry point
# ---------------------------------------------------------------------------

def lint_dependency_graph(project_dir: str):
    """Run dependency-graph lint rules and return a ``ValidationResult`` or *None*.

    Returns ``None`` when no issues are found.
    """
    from validate_xaml import ValidationResult

    graph = build_dependency_graph(project_dir)
    analysis = analyze_graph(graph)

    result = ValidationResult(filepath="[dependency-graph]")

    for cycle in analysis.cycles:
        result.error(f"[lint 101] Circular dependency: {' \u2192 '.join(cycle)}")

    for path in sorted(analysis.orphaned):
        # When scaffold markers are present (un-inlined body snippets),
        # framework files can't reach Workflows/ or Utils/ via
        # InvokeWorkflowFile edges.  Suppress orphan warnings for
        # non-Test workflows in this intermediate state — the wiring
        # hasn't been completed yet.
        if graph.has_scaffold_markers and not path.startswith("Tests/"):
            continue
        result.warn(
            f"[lint 102] Orphaned workflow not reachable from entry point: {path}"
        )

    if result.errors or result.warnings:
        return result
    return None


# ---------------------------------------------------------------------------
# DOT export
# ---------------------------------------------------------------------------

def export_dot(graph: DependencyGraph, analysis: GraphAnalysis) -> str:
    """Return a Graphviz DOT representation of the dependency graph."""
    cycle_nodes: set[str] = set()
    cycle_edges: set[tuple[str, str]] = set()
    for cycle in analysis.cycles:
        for i in range(len(cycle) - 1):
            cycle_nodes.add(cycle[i])
            cycle_edges.add((cycle[i], cycle[i + 1]))

    lines: list[str] = [
        "digraph dependencies {",
        '    rankdir=LR;',
        '    fontname="Helvetica";',
        '    node [fontname="Helvetica", style=filled];',
        "",
    ]

    # Nodes
    for node in sorted(graph.all_files):
        if node in cycle_nodes:
            colour = "red"
        elif node in analysis.orphaned:
            colour = "gray"
        elif node == graph.entry_point:
            colour = "green"
        else:
            colour = "lightblue"
        label = node.replace('"', '\\"')
        lines.append(f'    "{label}" [fillcolor={colour}];')

    lines.append("")

    # Edges
    for src in sorted(graph.edges):
        for dst in sorted(graph.edges[src]):
            src_label = src.replace('"', '\\"')
            dst_label = dst.replace('"', '\\"')
            if (src, dst) in cycle_edges:
                lines.append(f'    "{src_label}" -> "{dst_label}" [color=red];')
            else:
                lines.append(f'    "{src_label}" -> "{dst_label}";')

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse UiPath workflow dependency graph."
    )
    parser.add_argument("project_dir", help="Path to the UiPath project directory")
    parser.add_argument(
        "--dot",
        action="store_true",
        help="Output graph in Graphviz DOT format instead of a text summary",
    )
    args = parser.parse_args()

    graph = build_dependency_graph(args.project_dir)
    analysis = analyze_graph(graph)

    if args.dot:
        print(export_dot(graph, analysis))
        return

    # Text summary
    print(f"Entry point : {graph.entry_point or '(not set)'}")
    print(f"Files       : {len(graph.all_files)}")
    print(f"Edges       : {sum(len(v) for v in graph.edges.values())}")
    print()

    if analysis.cycles:
        print(f"Cycles ({len(analysis.cycles)}):")
        for cycle in analysis.cycles:
            print(f"  {' \u2192 '.join(cycle)}")
    else:
        print("No circular dependencies found.")

    print()

    if analysis.orphaned:
        print(f"Orphaned workflows ({len(analysis.orphaned)}):")
        for path in sorted(analysis.orphaned):
            print(f"  {path}")
    else:
        print("No orphaned workflows.")

    if analysis.missing_targets:
        print()
        print(f"Missing targets ({len(analysis.missing_targets)}):")
        for path in sorted(analysis.missing_targets):
            print(f"  {path}")


if __name__ == "__main__":
    _cli()
