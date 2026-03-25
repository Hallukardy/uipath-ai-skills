"""Structural validation helpers."""
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from ._constants import NS, REQUIRED_XMLNS, PREFIX_TO_XMLNS, NEEDS_IDREF, _RE_IDREF, _RE_XPROPERTY_NAME, _RE_DISPLAY_NAME, _RE_WORKFLOW_FILENAME
from ._context import FileContext, ValidationResult


def validate_xml_wellformed(ctx: FileContext, result: ValidationResult) -> ET.Element | None:
    """Check 1: Is it valid XML?"""
    try:
        tree = ET.parse(ctx.filepath)
        root = tree.getroot()
        ctx.tree = tree  # Store for lint rules that need tree traversal
        result.ok("Well-formed XML")
        return root
    except ET.ParseError as e:
        result.error(f"Malformed XML: {e}")
        return None


def validate_root_element(root: ET.Element, result: ValidationResult):
    """Check 2: Root must be Activity element."""
    # ET uses Clark notation {namespace}localname
    local = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if local != "Activity":
        result.error(f"Root element must be 'Activity', got '{local}'")
    else:
        result.ok("Root element is Activity")


def validate_xclass(root: ET.Element, filepath: str, result: ValidationResult):
    """Check 3: x:Class should exist."""
    xclass = root.get(f"{{{NS['x']}}}Class")
    if not xclass:
        result.error("Missing x:Class attribute on root Activity")
        return

    fname = Path(filepath).stem
    if xclass != fname:
        # Known x:Class→filename mismatches from REFramework and Studio exports
        known_mismatches = {
            # REFramework standard naming
            ("Initialize_Applications", "InitAllApplications"),
            ("InitiAllSettings", "InitAllSettings"),  # typo in official template
            # Clean/variant templates
            ("Process", "Process_Clean"),
            # Studio default x:Class for simple exports
            ("Sequence", "EmailFormFilling"),
            ("Sequence1", "WebScraping_Sequence1"),
            ("Main", "FormFilling_Main"),
            ("Main", "PDFExtraction_Main"),
        }
        if (xclass, fname) not in known_mismatches:
            result.warn(f"x:Class='{xclass}' doesn't match filename '{fname}' (Studio allows this but it's unusual)")
        else:
            result.ok(f"x:Class='{xclass}' (known template pattern)")
    else:
        result.ok(f"x:Class='{xclass}'")


def extract_declared_xmlns(filepath: str) -> dict[str, str]:
    """Extract xmlns declarations from raw text (ET normalizes them away)."""
    declared = {}
    with open(filepath, "r", encoding="utf-8") as f:
        # Only check the root element (first ~20 lines typically)
        header = ""
        for line in f:
            header += line
            if ">" in line and len(header) > 200:
                break

    for match in re.finditer(r'xmlns:(\w+)="([^"]*)"', header):
        prefix, uri = match.group(1), match.group(2)
        declared[prefix] = uri
    return declared


def extract_used_prefixes(filepath: str) -> set[str]:
    """Find all namespace prefixes used in elements or type references."""
    prefixes = set()
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    # Match <prefix:ElementName (actual elements)
    for match in re.finditer(r'<(\w+):(\w+)', content):
        prefix = match.group(1)
        if prefix not in ("x",):
            prefixes.add(prefix)
    # Match prefix:Type in TypeArguments, Type=, etc. (type references)
    # Find ALL prefixes inside these attribute values, not just the first
    for attr_match in re.finditer(r'(?:TypeArguments|Type|x:TypeArguments)="([^"]*)"', content):
        attr_val = attr_match.group(1)
        for match in re.finditer(r'(\w+):', attr_val):
            prefix = match.group(1)
            if prefix not in ("x",):
                prefixes.add(prefix)
    # Match [prefix:Type] patterns in expression brackets
    for match in re.finditer(r'\[(\w+):', content):
        prefix = match.group(1)
        if prefix not in ("x",):
            prefixes.add(prefix)
    return prefixes


def validate_namespaces(ctx: FileContext, result: ValidationResult):
    """Check 4: Required xmlns declared, used prefixes have declarations."""
    declared = extract_declared_xmlns(ctx.filepath)
    used = extract_used_prefixes(ctx.filepath)

    # Check required
    for req in REQUIRED_XMLNS:
        if req not in declared:
            result.error(f"Missing required xmlns:{req}")

    # Check used prefixes have declarations
    for prefix in used:
        if prefix not in declared and prefix not in ("x",):
            result.error(f"Activity prefix '{prefix}:' used but xmlns:{prefix} not declared")

    # Check declared but unused (warning only, skip known Studio noise)
    # Studio declares many xmlns for type system / expression resolution that
    # appear in VB.NET/C# expression strings rather than as XML prefixes
    STUDIO_NOISE = {
        "x", "mc", "sap", "sap2010", "scg", "sco", "sco1",
        # Common type-system prefixes Studio auto-adds
        "s", "s1", "s2", "s3", "sd", "sd1", "sd2", "sd3", "si", "sl", "sx", "sxl",
        "sc", "sc1", "scg1", "scg2", "scg3", "snm",
        "sa", "sa1", "sae", "sas",
        "mv", "this",
        "uc", "uc1", "uca", "uca1",
    }
    unused = [p for p in declared if p not in used and p not in STUDIO_NOISE]
    for prefix in unused:
        result.warn(f"xmlns:{prefix} declared but no '{prefix}:' usage found")

    result.ok(f"{len(declared)} xmlns declarations, {len(used)} prefixes used")

    # Lint 95: Validate xmlns URLs match expected values
    # Catches the Session 3 bug: xmlns:uix="activities/next" instead of "activities/uix"
    EXPECTED_URLS = {
        "uix": "http://schemas.uipath.com/workflow/activities/uix",
        "ui": "http://schemas.uipath.com/workflow/activities",
        "ss": "clr-namespace:System.Security;assembly=System.Private.CoreLib",
    }
    for prefix, expected_url in EXPECTED_URLS.items():
        if prefix in declared and declared[prefix] != expected_url:
            result.error(
                f"[lint 95] xmlns:{prefix} has wrong URL: '{declared[prefix]}' — "
                f"expected '{expected_url}'. This causes Studio designer issues. "
                f"Use generate_workflow.py (correct URL built-in) instead of "
                f"hand-writing namespace declarations."
            )

    # Check for known-wrong assembly names in any sd/sd2 prefix
    # System.Data (no suffix) doesn't contain DataTable in .NET Core — must be System.Data.Common
    for prefix in declared:
        url = declared[prefix]
        if "System.Data" in url and re.search(r'assembly=System\.Data$', url):
            result.error(
                f"[lint 95] xmlns:{prefix} uses wrong assembly: '{url}' — "
                f"'assembly=System.Data' should be 'assembly=System.Data.Common'. "
                f"DataTable/DataRow won't resolve without the correct assembly."
            )


def validate_idrefs(ctx: FileContext, result: ValidationResult, strict: bool = False):
    """Check 5: IdRefs must be unique, activities should have them."""
    content = ctx.content

    idrefs = _RE_IDREF.findall(content)

    if not idrefs:
        result.error("No WorkflowViewState.IdRef found — Studio requires these")
        return

    # Check uniqueness (FlowStep IdRefs can repeat across nested Flowchart scopes)
    counts = Counter(idrefs)
    dupes = {k: v for k, v in counts.items()
             if v > 1 and not k.startswith("FlowStep_")}
    if dupes:
        for idref, count in dupes.items():
            result.error(f"Duplicate IdRef '{idref}' appears {count} times")
    else:
        result.ok(f"{len(idrefs)} unique IdRefs")

    # Check naming convention (ActivityType_N)
    bad_format = [r for r in idrefs if not re.match(r'^[\w`]+_\d+$', r)]
    if bad_format and strict:
        result.warn(f"{len(bad_format)} IdRefs don't follow Type_N convention: {bad_format[:3]}...")

    # Check that key activities have IdRefs (heuristic: count elements vs idrefs)
    activity_count = len(_RE_DISPLAY_NAME.findall(content))
    if activity_count > 0 and len(idrefs) < activity_count * 0.5:
        result.warn(f"Only {len(idrefs)} IdRefs for ~{activity_count} activities — some may be missing")


def validate_hintsizes(ctx: FileContext, result: ValidationResult):
    """Check 6: Activities with IdRef should have HintSize."""
    content = ctx.content

    idref_count = len(_RE_IDREF.findall(content))
    hint_count = len(re.findall(r'VirtualizedContainerService\.HintSize=', content))

    if idref_count > 0 and hint_count == 0:
        result.error("No HintSize attributes found — Studio needs these for layout")
    elif hint_count < idref_count * 0.5:
        result.warn(f"{hint_count} HintSizes for {idref_count} IdRefs — some activities may lack layout info")
    else:
        result.ok(f"{hint_count} HintSize attributes")


def validate_arguments(root: ET.Element, result: ValidationResult, strict: bool = False):
    """Check 7: x:Members/x:Property have valid Type attributes."""
    members = root.find(f"{{{NS['x']}}}Members")
    if members is None:
        result.ok("No arguments (x:Members) — OK for simple workflows")
        return

    valid_directions = ("InArgument", "OutArgument", "InOutArgument")
    props = members.findall(f"{{{NS['x']}}}Property")

    for prop in props:
        name = prop.get("Name", "?")
        type_attr = prop.get("Type", "")

        if not type_attr:
            result.error(f"Argument '{name}' has no Type attribute")
            continue

        if not any(type_attr.startswith(d) for d in valid_directions):
            result.error(f"Argument '{name}' Type='{type_attr}' — must start with InArgument/OutArgument/InOutArgument")

        # Check naming convention (strict only)
        if strict and not (name.startswith("in_") or name.startswith("out_") or name.startswith("io_")):
            result.warn(f"Argument '{name}' doesn't follow in_/out_/io_ naming convention")

    result.ok(f"{len(props)} arguments declared")


def validate_viewstate_dict(ctx: FileContext, result: ValidationResult):
    """Check 8: ViewState dictionary should exist."""
    content = ctx.content

    has_viewstate = "WorkflowViewStateService.ViewState" in content
    if not has_viewstate:
        result.warn("No ViewState dictionary blocks found — layout may be lost in Studio")
    else:
        viewstate_count = content.count("WorkflowViewStateService.ViewState")
        result.ok(f"{viewstate_count} ViewState dictionary blocks")


def validate_invoke_paths(ctx: FileContext, project_dir: str | None, result: ValidationResult):
    """Check 9: InvokeWorkflowFile paths should resolve."""
    content = ctx.content

    paths = _RE_WORKFLOW_FILENAME.findall(content)
    if not paths:
        return

    if not project_dir:
        result.ok(f"{len(paths)} InvokeWorkflowFile references (project dir unknown, can't verify)")
        return

    missing = []
    for wp in paths:
        # Normalize path separators
        normalized = wp.replace("\\", os.sep).replace("/", os.sep)
        full_path = os.path.join(project_dir, normalized)
        if not os.path.exists(full_path):
            missing.append(wp)

    if missing:
        unique_missing = list(dict.fromkeys(missing))  # deduplicate preserving order
        for m in unique_missing:
            count = missing.count(m)
            suffix = f" ({count} references)" if count > 1 else ""
            result.error(f"InvokeWorkflowFile references '{m}' — file not found{suffix}")
    else:
        result.ok(f"{len(paths)} InvokeWorkflowFile paths verified")


def validate_expression_language(ctx: FileContext, result: ValidationResult):
    """Check 10: Consistent expression language markers."""
    content = ctx.content

    has_vb = "VisualBasic.Settings" in content or "Microsoft.VisualBasic" in content
    has_cs = "CSharpReference" in content or "CSharpValue" in content

    if has_vb and has_cs:
        result.error("Mixed VB.NET and C# expression markers — file must use one language")
    elif has_vb:
        result.ok("Expression language: VB.NET")
    elif has_cs:
        result.ok("Expression language: C#")
    else:
        result.warn("No expression language markers detected")

