#!/usr/bin/env python3
"""Unit tests for dependency_graph.py."""

import json
import os
import sys
import tempfile
import unittest

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from dependency_graph import (
    DependencyGraph,
    GraphAnalysis,
    analyze_graph,
    build_dependency_graph,
    export_dot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_XAML_TEMPLATE = """\
<?xml version="1.0" encoding="utf-8"?>
<Activity mc:Ignorable="sap sap2010" x:Class="{cls}"
  xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities"
  xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
  xmlns:ui="http://schemas.uipath.com/workflow/activities"
  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
  xmlns:sap="http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation"
  xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation">
  <Sequence DisplayName="{cls}" sap2010:WorkflowViewState.IdRef="Sequence_1">
{invokes}  </Sequence>
</Activity>
"""

def _invoke_line(target: str) -> str:
    return (
        f'    <ui:InvokeWorkflowFile WorkflowFileName="{target}" '
        f'DisplayName="Invoke" sap2010:WorkflowViewState.IdRef="InvokeWorkflowFile_1" />\n'
    )


def _make_project(tmpdir: str, files: dict[str, list[str]],
                  main: str = "Main.xaml") -> str:
    """Create a minimal UiPath project in *tmpdir*.

    *files*: mapping of ``filename -> [list of invoke targets]``.
    Returns the project directory path.
    """
    pj = {
        "name": "TestProject",
        "projectVersion": "1.0.0",
        "main": main,
        "dependencies": {},
        "schemaVersion": "4.0",
        "studioVersion": "23.10.0",
        "projectType": "Workflow",
        "expressionLanguage": "CSharp",
    }
    with open(os.path.join(tmpdir, "project.json"), "w", encoding="utf-8") as f:
        json.dump(pj, f)

    for fname, targets in files.items():
        fpath = os.path.join(tmpdir, fname.replace("/", os.sep))
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        cls = os.path.splitext(os.path.basename(fname))[0]
        invokes = "".join(_invoke_line(t) for t in targets)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(_XAML_TEMPLATE.format(cls=cls, invokes=invokes))

    return tmpdir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildDependencyGraph(unittest.TestCase):

    def test_linear_chain(self):
        """A → B → C — no cycles, no orphans."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": ["B.xaml"],
                "B.xaml": [],
            })
            graph = build_dependency_graph(td)

            self.assertEqual(graph.entry_point, "Main.xaml")
            self.assertEqual(len(graph.all_files), 3)
            self.assertIn("Main.xaml", graph.edges)
            self.assertIn("A.xaml", graph.edges["Main.xaml"])
            self.assertEqual(len(graph.missing_targets), 0)

    def test_dynamic_path_skipped(self):
        """WorkflowFileName='[variable]' should be ignored."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["[in_strWorkflow]"],
            })
            graph = build_dependency_graph(td)
            # Dynamic path should not appear in edges or missing targets
            self.assertEqual(len(graph.edges), 0)
            self.assertEqual(len(graph.missing_targets), 0)

    def test_mixed_separators(self):
        """Backslash paths are normalised to forward slashes."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["Workflows\\Sub.xaml"],
                "Workflows/Sub.xaml": [],
            })
            graph = build_dependency_graph(td)
            self.assertIn("Workflows/Sub.xaml", graph.edges.get("Main.xaml", set()))

    def test_missing_target_recorded(self):
        """Reference to a non-existent file is recorded in missing_targets."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["DoesNotExist.xaml"],
            })
            graph = build_dependency_graph(td)
            self.assertIn("DoesNotExist.xaml", graph.missing_targets)
            # Should NOT be in edges since the file doesn't exist
            self.assertEqual(len(graph.edges.get("Main.xaml", set())), 0)


class TestAnalyzeGraph(unittest.TestCase):

    def test_no_cycle_linear(self):
        """Linear chain has no cycles."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": ["B.xaml"],
                "B.xaml": [],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            self.assertEqual(len(analysis.cycles), 0)
            self.assertEqual(len(analysis.orphaned), 0)

    def test_simple_cycle(self):
        """A → B → A should be detected as a cycle."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": ["B.xaml"],
                "B.xaml": ["A.xaml"],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            self.assertEqual(len(analysis.cycles), 1)
            cycle = analysis.cycles[0]
            # Cycle must start and end with the same node
            self.assertEqual(cycle[0], cycle[-1])
            # Both A and B must be in the cycle
            self.assertIn("A.xaml", cycle)
            self.assertIn("B.xaml", cycle)

    def test_three_node_cycle(self):
        """Main → A → B → Main should be detected."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": ["B.xaml"],
                "B.xaml": ["Main.xaml"],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            self.assertEqual(len(analysis.cycles), 1)
            cycle = analysis.cycles[0]
            self.assertEqual(cycle[0], cycle[-1])
            self.assertIn("Main.xaml", cycle)
            self.assertIn("A.xaml", cycle)
            self.assertIn("B.xaml", cycle)

    def test_diamond_no_cycle(self):
        """Diamond: A→B, A→C, B→D, C→D — no cycle."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["B.xaml", "C.xaml"],
                "B.xaml": ["D.xaml"],
                "C.xaml": ["D.xaml"],
                "D.xaml": [],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            self.assertEqual(len(analysis.cycles), 0)
            self.assertEqual(len(analysis.orphaned), 0)

    def test_orphan_detection(self):
        """An unreferenced file is flagged as orphaned."""
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": [],
                "Unused.xaml": [],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            self.assertEqual(len(analysis.orphaned), 1)
            self.assertIn("Unused.xaml", analysis.orphaned)

    def test_no_orphans_when_no_entry_point(self):
        """Without an entry point, orphan detection is skipped."""
        graph = DependencyGraph(
            edges={"A.xaml": {"B.xaml"}},
            all_files={"A.xaml", "B.xaml", "C.xaml"},
            entry_point=None,
        )
        analysis = analyze_graph(graph)
        self.assertEqual(len(analysis.orphaned), 0)


class TestExportDot(unittest.TestCase):

    def test_dot_contains_nodes_and_edges(self):
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": [],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            dot = export_dot(graph, analysis)

            self.assertIn("digraph dependencies", dot)
            self.assertIn('"Main.xaml"', dot)
            self.assertIn('"A.xaml"', dot)
            self.assertIn('"Main.xaml" -> "A.xaml"', dot)

    def test_dot_cycle_nodes_are_red(self):
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": ["Main.xaml"],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            dot = export_dot(graph, analysis)

            self.assertIn("fillcolor=red", dot)
            self.assertIn("color=red", dot)

    def test_dot_orphan_is_gray(self):
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": [],
                "Orphan.xaml": [],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            dot = export_dot(graph, analysis)

            self.assertIn("fillcolor=gray", dot)

    def test_dot_entry_is_green(self):
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": [],
            })
            graph = build_dependency_graph(td)
            analysis = analyze_graph(graph)
            dot = export_dot(graph, analysis)

            self.assertIn("fillcolor=green", dot)


class TestLintIntegration(unittest.TestCase):
    """Test the lint_dependency_graph wrapper against real fixture dirs."""

    FIXTURE_DIR = os.path.join(
        os.path.dirname(SCRIPT_DIR), "assets", "lint-test-cases"
    )

    def test_cycle_fixture(self):
        from dependency_graph import lint_dependency_graph
        result = lint_dependency_graph(
            os.path.join(self.FIXTURE_DIR, "bad_project_cycle")
        )
        self.assertIsNotNone(result)
        self.assertTrue(any("lint 101" in e for e in result.errors))

    def test_orphan_fixture(self):
        from dependency_graph import lint_dependency_graph
        result = lint_dependency_graph(
            os.path.join(self.FIXTURE_DIR, "bad_project_orphan")
        )
        self.assertIsNotNone(result)
        self.assertTrue(any("lint 102" in w for w in result.warnings))

    def test_clean_project_returns_none(self):
        """A project with no cycles or orphans returns None."""
        from dependency_graph import lint_dependency_graph
        with tempfile.TemporaryDirectory() as td:
            _make_project(td, {
                "Main.xaml": ["A.xaml"],
                "A.xaml": [],
            })
            result = lint_dependency_graph(td)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
