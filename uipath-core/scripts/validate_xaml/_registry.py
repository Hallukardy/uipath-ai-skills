"""Lint rule registry and dispatcher."""

import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class LintEntry:
    fn: object  # callable(ctx, result) or callable(ctx, result, project_dir=)
    number: int
    golden_suppressed: bool = False
    needs_project_dir: bool = False


_LINT_REGISTRY: list[LintEntry] = []


def lint_rule(number, *, golden_suppressed=False, needs_project_dir=False):
    """Register a core lint rule function in the global registry."""
    def decorator(fn):
        _LINT_REGISTRY.append(LintEntry(
            fn=fn, number=number,
            golden_suppressed=golden_suppressed,
            needs_project_dir=needs_project_dir,
        ))
        return fn
    return decorator


def lint_xaml_file(ctx, result, golden=False, project_dir=None):
    """Run all lint checks on a XAML file.

    Dispatches registered lint rules from _LINT_REGISTRY (populated by
    @lint_rule decorators in source order). Golden-suppressed rules are
    skipped when golden=True. Rules that need project_dir receive it as
    a keyword argument.

    golden: when True, suppress warnings expected in real Studio exports:
    - naming conventions (variable/argument prefixes)
    - missing DisplayName attributes
    - in_Config() without .ToString
    - hardcoded idx > 2 in selectors
    - FuzzySelector usage, empty FuzzySelectorArgument
    """
    for entry in _LINT_REGISTRY:
        if golden and entry.golden_suppressed:
            continue
        if entry.needs_project_dir:
            entry.fn(ctx, result, project_dir=project_dir)
        else:
            entry.fn(ctx, result)

    # --- Plugin lint rules (registered via plugin_loader, not @lint_rule) ---
    from plugin_loader import get_lint_rules
    for lint_fn, lint_name in get_lint_rules():
        try:
            lint_fn(ctx, result)
        except Exception as e:
            result.warn(f"Plugin lint '{lint_name}' failed: {e}")
