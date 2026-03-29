"""Snippet validation for modify_framework.

Catches hallucinated XAML patterns BEFORE they get inserted into
framework files.  This is the enforcement layer -- the LLM can
hallucinate all it wants in its agent prompt, but the snippet is
rejected at insertion time with an actionable error message.

Exports:
    _SNIPPET_CHECKS        — list of (regex, label, fix_hint) tuples
    validate_snippet        — check a snippet against all patterns
    _warn_nested_retryscope — warn about nested RetryScope anti-pattern
"""
import re
import sys

_PATH_RE = re.compile(
    r'^(?:'
    r'[A-Za-z]:[/\\]'           # Windows drive: C:/ or C:\
    r'|[/\\]{1,2}[A-Za-z]'      # Unix absolute or UNC: /home, \\server
    r'|\.{0,2}[/\\]'            # Relative: ./ ../ \
    r').*\.(?:json|xaml|txt|xml|csv|xlsx?)$',
    re.IGNORECASE
)

_SNIPPET_CHECKS: list[tuple[str, str, str]] = [
    # (regex_pattern, human_label, fix_hint)

    # -- FilterDataTable hallucinations --
    (r'FilterRowsCollection',
     "FilterRowsCollection (hallucinated property)",
     "Use gen_filter_data_table() — correct property is .Filters"),
    (r'FilterOperationArgument[^>]*\bColumnName=',
     "FilterOperationArgument ColumnName= (hallucinated attribute)",
     "Use gen_filter_data_table() — column goes in a .Column child element"),
    (r'FilterOperationArgument[^>]*\bValue=',
     "FilterOperationArgument Value= (hallucinated attribute)",
     "Use gen_filter_data_table() — value goes in a .Operand child element"),
    (r'FilterOperationArgument[^>]*\bOperand="(?:EQ|NE|LT|LE|GT|GE|CONTAINS|STARTS_WITH|ENDS_WITH|EMPTY|NOT_EMPTY|Contains|StartsWith|EndsWith|IsEmpty|IsNotEmpty)"',
     "Operator value stuffed into Operand attribute",
     "Operand is the value, Operator is the comparison. Use gen_filter_data_table()"),
    (r'FilterOperationArgument[^>]*\bOperator="(?:=|==|!=|<>|<|<=|>|>=)"',
     "Symbolic operator in Operator attribute",
     "UiPath FilterOperator enum requires: EQ NE LT LE GT GE. Use gen_filter_data_table()"),

    # -- BuildDataTable hallucinations --
    (r'BuildDataTable\.Columns>',
     "BuildDataTable.Columns (hallucinated child element)",
     "BuildDataTable is self-closing with a TableInfo= attribute. Use gen_build_data_table()"),
    (r'DataTableColumnInfo',
     "DataTableColumnInfo (hallucinated type)",
     "BuildDataTable uses an XML-escaped XSD schema in TableInfo=. Use gen_build_data_table()"),

    # -- AddQueueItem hallucinations --
    (r'AddQueueItem\.ItemFields>\s*<scg:Dictionary',
     "AddQueueItem.ItemFields with Dictionary child (hallucinated structure)",
     "Use gen_add_queue_item() — ItemInformation property, not ItemFields"),

    # -- SortDataTable hallucinations --
    (r'SortDataTable[^>]*\bOrderByColumnName=',
     "SortDataTable OrderByColumnName= (hallucinated attribute)",
     "Correct attribute is ColumnName. Use the generator"),
    (r'SortDataTable[^>]*\bOrderByType=',
     "SortDataTable OrderByType= (hallucinated attribute)",
     "Correct attribute is SortOrder. Use the generator"),

    # -- NApplicationCard hallucinations --
    (r'NApplicationCard\b[^>]*\sUrl="',
     "NApplicationCard Url= (hallucinated attribute)",
     "URL belongs in <uix:TargetApp Url=\"...\"> child element"),

    # -- TargetAnchorable hallucinations --
    (r'<uix:N\w+\.TargetAnchorable>',
     ".TargetAnchorable child element (hallucinated)",
     "The child element is .Target (the TYPE inside it is TargetAnchorable)"),
]


def validate_snippet(xaml_snippet: str) -> list[str]:
    """Validate an XAML snippet against known hallucination patterns.

    Returns a list of error strings (empty = OK).
    """
    # ── Structural pre-checks (reject non-XAML input early) ──
    stripped = xaml_snippet.strip()
    if not stripped:
        return ["REJECTED: Empty snippet. The XAML snippet argument must "
                "contain actual XAML content, not an empty string."]

    if '\n' not in stripped and '<' not in stripped:
        if _PATH_RE.match(stripped):
            return [f"REJECTED: File path detected instead of XAML content: "
                    f"'{stripped}'. Read the file first, then pass its CONTENT "
                    f"as the snippet argument. Do NOT pass the file path string."]

    if not stripped.startswith('<'):
        return [f"REJECTED: Snippet does not start with '<' — not valid XAML. "
                f"Got: '{stripped[:80]}{'...' if len(stripped) > 80 else ''}'. "
                f"The snippet must be actual XAML content "
                f"(e.g., '<ui:InvokeWorkflowFile ...>')."]

    # ── Hallucination pattern checks ──
    errors = []
    for pattern, label, fix in _SNIPPET_CHECKS:
        if re.search(pattern, xaml_snippet):
            errors.append(f"REJECTED: {label}. Fix: {fix}")
    return errors


def _warn_nested_retryscope(xaml_snippet: str) -> None:
    """Warn if snippet has nested RetryScopes (common hallucination pattern).

    In REFramework, Process.xaml retries are handled by Main.xaml's
    RetryCurrentTransaction logic. RetryScope inside a process body should
    only wrap specific API/network calls, not the entire body.
    A snippet with a RetryScope as root AND another RetryScope nested inside
    almost always means the outer one is wrong.
    """
    retryscope_count = len(re.findall(r'<ui:RetryScope\b', xaml_snippet))
    if retryscope_count <= 1:
        return
    # Check if the first non-whitespace XML element is a RetryScope
    stripped = xaml_snippet.strip()
    if re.match(r'<ui:RetryScope\b', stripped):
        print(
            "WARNING: Snippet has a RetryScope as its root element AND contains "
            f"nested RetryScope(s) ({retryscope_count} total). In REFramework, "
            "retries are handled by Main.xaml — the outer RetryScope is likely "
            "unnecessary. Only wrap specific API/network calls in RetryScope.",
            file=sys.stderr
        )
