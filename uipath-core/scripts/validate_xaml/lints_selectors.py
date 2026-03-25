"""Selector lint rules."""

import re

from ._registry import lint_rule
from ._context import FileContext, ValidationResult
from ._constants import _RE_VARIABLE_DECL, _RE_XPROPERTY_NAME


@lint_rule(9, golden_suppressed=True)
def lint_selector_hardcoded(ctx: FileContext, result: ValidationResult):
    """Lint 9: Detect potentially hardcoded values in selectors."""
    content = ctx.active_content

    # Find FullSelectorArgument values that are static strings (not dynamic [expression])
    selectors = re.findall(r'FullSelectorArgument="([^"]*)"', content)
    if not selectors:
        return

    dynamic = sum(1 for s in selectors if s.startswith("["))
    static = len(selectors) - dynamic

    # Detect suspicious hardcoded idx values in static selectors
    hardcoded_idx = []
    for s in selectors:
        if not s.startswith("[") and "idx='" in s:
            idx_val = re.search(r"idx='(\d+)'", s)
            if idx_val and int(idx_val.group(1)) > 2:
                hardcoded_idx.append(s[:80])

    if hardcoded_idx:
        result.warn(
            f"{len(hardcoded_idx)} selector(s) with hardcoded idx > 2 — "
            f"these are fragile and break when page layout changes"
        )

    # Detect css-selector= usage — valid UiPath WEBCTRL attribute but fragile
    css_selector_hits = [s for s in selectors if "css-selector=" in s.lower()]
    if css_selector_hits:
        result.warn(
            f"[lint 97] {len(css_selector_hits)} selector(s) use 'css-selector=' — "
            f"CSS selectors are fragile and break when page structure changes. "
            f"Prefer id=, aaname=, or parentid= attributes for reliable matching."
        )

    result.ok(f"Selectors: {dynamic} dynamic, {static} static")


@lint_rule(14, golden_suppressed=True)
def lint_selector_quality(ctx: FileContext, result: ValidationResult):
    """Lint 14: Advanced selector quality checks."""
    content = ctx.active_content

    # Fuzzy matching enabled without fuzzylevel
    fuzzy_selectors = re.findall(r"matching:(\w+)='fuzzy'", content)
    for attr in fuzzy_selectors:
        if f"fuzzylevel:{attr}=" not in content:
            result.warn(
                f"Selector has matching:{attr}='fuzzy' but no fuzzylevel:{attr} — "
                f"defaults to 0.5, set explicitly for reliability"
            )

    # Dynamic selector variables — check they're declared
    dynamic_vars = re.findall(r'\{\{(\w+)\}\}', content)
    if dynamic_vars:
        # Get all declared variables and arguments
        declared_vars = set(_RE_VARIABLE_DECL.findall(content))
        declared_args = set(_RE_XPROPERTY_NAME.findall(content))
        declared_delegates = set(re.findall(r'<DelegateInArgument[^>]*Name="([^"]*)"', content))
        all_declared = declared_vars | declared_args | declared_delegates

        undeclared = [v for v in set(dynamic_vars) if v not in all_declared]
        if undeclared:
            result.warn(
                f"Dynamic selector variable(s) {undeclared[:5]} not found in declared "
                f"variables/arguments — selector will fail at runtime"
            )
        else:
            result.ok(f"Dynamic selectors: {len(set(dynamic_vars))} variable(s) all declared")

    # Selectors with only idx (no other identifying attribute)
    idx_only = re.findall(r"<webctrl\s+idx='[^']*'\s*/>", content)
    if idx_only:
        result.warn(
            f"{len(idx_only)} selector(s) using only idx attribute — "
            f"extremely fragile, add aaname/id/tag for stability"
        )

    # FuzzySelectorArgument present but empty
    empty_fuzzy = re.findall(r'FuzzySelectorArgument=""', content)
    if empty_fuzzy:
        result.warn(
            f"{len(empty_fuzzy)} empty FuzzySelectorArgument(s) — "
            f"add fuzzy selectors as fallback for resilience"
        )

    # SearchSteps set to FuzzySelector instead of strict Selector
    fuzzy_steps = re.findall(r'SearchSteps="FuzzySelector"', content)
    if fuzzy_steps:
        result.warn(
            f"{len(fuzzy_steps)} TargetAnchorable(s) use SearchSteps='FuzzySelector' — "
            f"default to 'Selector' (strict) unless fuzzy is explicitly needed"
        )


@lint_rule(110)
def lint_invoke_bare_typearguments(ctx: FileContext, result: ValidationResult):
    """Lint 110: InvokeWorkflowFile argument with unresolved TypeArguments.

    If x:TypeArguments contains a bare type name (no namespace prefix like x:, scg:,
    ui:, sd:, ss:, s:), it's an unresolved shortname that will cause a compile error.
    Common offender: "Dictionary" instead of "scg:Dictionary(x:String, x:Object)".
    """
    content = ctx.active_content
    # Find InvokeWorkflowFile.Arguments blocks
    invoke_arg_blocks = re.findall(
        r'<ui:InvokeWorkflowFile\.Arguments>(.*?)</ui:InvokeWorkflowFile\.Arguments>',
        content, re.DOTALL
    )
    valid_prefixes = ("x:", "scg:", "ui:", "sd:", "ss:", "s:", "sdd:", "sdd1:", "sd1:", "snm:", "uwahm:", "njl:")
    for block in invoke_arg_blocks:
        # Find TypeArguments values in each argument
        type_args = re.findall(r'x:TypeArguments="([^"]+)"', block)
        for ta in type_args:
            if not any(ta.startswith(p) for p in valid_prefixes):
                result.error(
                    f'[lint 110] InvokeWorkflowFile argument has unresolved '
                    f'x:TypeArguments="{ta}" — missing namespace prefix. '
                    f'Use the type shortname in the spec (e.g. "Dictionary" → '
                    f'"scg:Dictionary(x:String, x:Object)"). The generator '
                    f'should resolve this automatically via _normalize_type_arg().'
                )
