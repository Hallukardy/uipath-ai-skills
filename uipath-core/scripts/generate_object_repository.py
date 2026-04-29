"""Generate UiPath Object Repository (.objects/ directory tree).

The Object Repository stores UI element definitions in a hierarchical structure:
  Library → App → AppVersion → Screen → Element

Each XAML activity that targets a UI element can reference the Object Repository
via a `Reference` attribute on TargetAnchorable/TargetApp, binding it to a
centrally-managed element definition. This enables reuse and refactoring.

Usage:
    from generate_object_repository import generate_object_repository

    apps = [{
        "name": "ACME System1",
        "selector": "<html app='msedge.exe' title='ACME System 1' />",
        "url": "https://acme-test.example.com/login",
        "browser_type": "Edge",          # Edge | Chrome | Firefox
        "screens": [{
            "name": "Login",
            "url": "https://acme-test.example.com/login",
            "elements": [{
                "name": "Username",
                "taxonomy_type": "Input",  # Input | Password | Button | Dropdown | Link | CheckBox | RadioButton | Text
                "element_type": "InputBox", # InputBox | InputBoxPassword | Button | DropDown | Link | CheckBox | RadioButton | Text
                "selector": "<webctrl id='username' tag='INPUT' />",
            }]
        }]
    }]

    refs = generate_object_repository(apps, project_dir="/path/to/project")
    # refs = {
    #     "apps": {
    #         "ACME System1": {
    #             "reference": "LibId/ScreenId",  # for NApplicationCard TargetApp
    #             "content_hash": "...",
    #         }
    #     },
    #     "elements": {
    #         "ACME System1/Login/Username": {
    #             "reference": "LibId/ElementId",  # for TargetAnchorable
    #             "content_hash": "...",
    #         }
    #     },
    #     "screens": {
    #         "ACME System1/Login": {
    #             "reference": "LibId/ScreenId",
    #             "content_hash": "...",
    #         }
    #     }
    # }
"""

import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# ID generation — matches Studio's base64url-encoded GUID pattern
# ---------------------------------------------------------------------------

def _generate_objrepo_id(seed: str | None = None) -> tuple[str, str]:
    """Generate an Object Repository ID.

    Returns (short_prefix, full_id):
        short_prefix: first 4 chars, used as directory name
        full_id:      22-char base64url-encoded UUID (no padding)

    When `seed` is given, the ID is derived deterministically from it via
    UUID5 — so regenerating the same project produces the same directory
    tree (no diff churn). When `seed` is None, falls back to uuid4 for
    backward compatibility with callers that don't have a stable key.
    """
    if seed is None:
        raw = uuid.uuid4().bytes
    else:
        raw = uuid.uuid5(uuid.NAMESPACE_DNS, f"uipath-core:objrepo:{seed}").bytes
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return encoded[:4], encoded


def _content_hash(xml_content: str) -> str:
    """Compute ContentHash for Object Repository XML content.

    Returns a 22-char base64url-encoded MD5 hash (no padding),
    matching Studio's ContentHash format.
    """
    md5 = hashlib.md5(xml_content.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(md5).rstrip(b"=").decode("ascii")


def _pascalcase_to_display(name: str) -> str:
    """Convert PascalCase to spaced display name for Object Repository.

    FirstName → First Name
    AddressLine1 → Address Line 1
    MyCRM → My CRM
    PeopleTab → People Tab
    """
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    s = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', s)
    s = re.sub(r'(\d)([A-Z])', r'\1 \2', s)
    return s


def _escape_xml_attr(s: str) -> str:
    """Escape string for use in XML attribute values."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _normalize_selector_quotes(selector: str) -> str:
    """Normalize selector to use single quotes (UiPath convention)."""
    import re
    s = selector
    if '&lt;' in s or '&gt;' in s or '&amp;' in s:
        s = (s.replace("&amp;", "&")
              .replace("&lt;", "<")
              .replace("&gt;", ">")
              .replace("&quot;", '"')
              .replace("&apos;", "'"))
    return re.sub(r'(\w+)="([^"]*)"', r"\1='\2'", s)


def _now_iso() -> str:
    """Return current UTC time in Studio's ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + "0000000Z"


# ---------------------------------------------------------------------------
# Metadata / content generators
# ---------------------------------------------------------------------------

PLATFORM_VERSION = "25.12.1.0"
UIAUTOMATION_VERSION = "25.10.26.0"

_CREATED_BY_FULL = [
    f"UiPath.UIAutomationCore, Version={UIAUTOMATION_VERSION}, Culture=neutral, PublicKeyToken=null",
    f"UiPath.Platform, Version={PLATFORM_VERSION}, Culture=neutral, PublicKeyToken=null",
]
_CREATED_BY_PLATFORM = [
    f"UiPath.Platform, Version={PLATFORM_VERSION}, Culture=neutral, PublicKeyToken=null",
]


def _write_file(path: Path, content: str, bom: bool = True):
    """Write a file with optional UTF-8 BOM (Studio convention for JSON metadata)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\r\n") as f:
        f.write(content)


def _write_metadata(path: Path, data: dict):
    """Write a .metadata JSON file (with BOM, CRLF)."""
    _write_file(path, json.dumps(data, indent=2))


def _write_type(path: Path, type_name: str):
    """Write a .type file."""
    _write_file(path, type_name, bom=False)


def _write_hash(path: Path, content: str):
    """Write a .hash file with the content hash."""
    h = hashlib.md5(content.encode("utf-8")).hexdigest()
    # Studio uses a 22-char base64 hash in .hash files
    _write_file(path, h, bom=False)


def _write_search_hash(path: Path, seed: str | None = None):
    """Write a SearchHash file (10-char hex string).

    When `seed` is given, the hash is derived deterministically from it,
    so the same input produces the same file across regenerations.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if seed is None:
        h = hashlib.md5(uuid.uuid4().bytes).hexdigest()[:10]
    else:
        h = hashlib.md5(f"uipath-core:searchhash:{seed}".encode("utf-8")).hexdigest()[:10]
    _write_file(path, h, bom=False)


# ---------------------------------------------------------------------------
# XML content generators
# ---------------------------------------------------------------------------

def _generate_screen_data_xml(app_selector: str, app_url: str, browser_type: str) -> str:
    """Generate ObjectRepositoryScreenData XML content for browser apps."""
    esc_sel = _escape_xml_attr(_normalize_selector_quotes(app_selector))
    return (
        '<?xml version="1.0" encoding="utf-16"?>\n'
        '<ObjectRepositoryScreenData ContentHash="{content_hash}" '
        'xmlns="http://schemas.uipath.com/workflow/activities/uix" '
        'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
        '  <ObjectRepositoryScreenData.Data>\n'
        f'    <TargetApp x:Key="TargetApp" Area="0, 0, 0, 0" BrowserType="{browser_type}" '
        f'Selector="{esc_sel}" Url="{_escape_xml_attr(app_url)}" Version="V2" />\n'
        '  </ObjectRepositoryScreenData.Data>\n'
        '</ObjectRepositoryScreenData>'
    )


def _generate_screen_data_xml_desktop(app_selector: str, file_path: str) -> str:
    """Generate ObjectRepositoryScreenData XML content for desktop apps.

    Desktop apps use FilePath instead of BrowserType/Url.
    Studio requires expanded TargetApp with child elements and a Variables list
    declaring any argument references used in FilePath (e.g. in_strAppPath).
    Format verified against Studio 24.10 clipboard export.
    """
    esc_sel = _escape_xml_attr(_normalize_selector_quotes(app_selector))
    esc_fp = _escape_xml_attr(file_path)

    # Extract variable name from [varName] expression for the Variables list
    var_name = ""
    if file_path.startswith("[") and file_path.endswith("]"):
        var_name = file_path[1:-1]

    variables_block = ""
    if var_name:
        variables_block = (
            '    <scg:List x:TypeArguments="ObjectRepositoryVariableData" '
            f'x:Key="Variables" Capacity="1">\n'
            f'      <ObjectRepositoryVariableData IsVariable="False" Name="{_escape_xml_attr(var_name)}" />\n'
            '    </scg:List>\n'
        )

    scg_xmlns = ""
    if var_name:
        scg_xmlns = ' xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib"'

    return (
        '<?xml version="1.0" encoding="utf-16"?>\n'
        '<ObjectRepositoryScreenData ContentHash="{content_hash}" '
        'Reference="{reference}" '
        'xmlns="http://schemas.uipath.com/workflow/activities/uix" '
        'xmlns:p="http://schemas.microsoft.com/netfx/2009/xaml/activities"'
        f'{scg_xmlns} '
        'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
        '  <ObjectRepositoryScreenData.Data>\n'
        f'    <TargetApp x:Key="TargetApp" Area="0, 0, 0, 0" '
        f'ContentHash="{{target_app_content_hash}}" '
        f'FilePath="{esc_fp}" Reference="{{reference}}" '
        f'Selector="{esc_sel}" Version="V2">\n'
        '      <TargetApp.Arguments>\n'
        '        <p:InArgument x:TypeArguments="x:String" />\n'
        '      </TargetApp.Arguments>\n'
        '      <TargetApp.WorkingDirectory>\n'
        '        <p:InArgument x:TypeArguments="x:String" />\n'
        '      </TargetApp.WorkingDirectory>\n'
        '    </TargetApp>\n'
        f'{variables_block}'
        '  </ObjectRepositoryScreenData.Data>\n'
        '</ObjectRepositoryScreenData>'
    )


def _generate_target_data_xml(
    element_selector: str,
    app_selector: str,
    element_type: str,
    element_guid: str,
    browser_url: str = "",
) -> str:
    """Generate ObjectRepositoryTargetData XML content."""
    esc_full = _escape_xml_attr(_normalize_selector_quotes(element_selector))
    esc_scope = _escape_xml_attr(_normalize_selector_quotes(app_selector))
    browser_url_attr = ""
    if browser_url:
        # Strip protocol prefix for BrowserURL attribute
        clean_url = browser_url.replace("https://", "").replace("http://", "")
        browser_url_attr = f'BrowserURL="{_escape_xml_attr(clean_url)}" '
    return (
        '<?xml version="1.0" encoding="utf-16"?>\n'
        '<ObjectRepositoryTargetData ContentHash="{content_hash}" '
        'xmlns="http://schemas.uipath.com/workflow/activities/uix" '
        'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
        '  <ObjectRepositoryTargetData.Data>\n'
        f'    <TargetAnchorable x:Key="TargetAnchorable" '
        f'{browser_url_attr}'
        f'DesignTimeRectangle="0, 0, 0, 0" '
        f'ElementType="{element_type}" '
        f'ElementVisibilityArgument="Interactive" '
        f'FullSelectorArgument="{esc_full}" '
        f'Guid="{element_guid}" '
        f'ScopeSelectorArgument="{esc_scope}" '
        f'SearchSteps="Selector" '
        f'Version="V6" '
        f'WaitForReadyArgument="Interactive" />\n'
        '  </ObjectRepositoryTargetData.Data>\n'
        '</ObjectRepositoryTargetData>'
    )


# ---------------------------------------------------------------------------
# Selector quality gate — runs at import time, before any directory is
# created, so users find out their inspection captured fragile selectors
# while it is still cheap to refine.
# ---------------------------------------------------------------------------


def _validate_selector_quality(selector: str, location: str) -> list[str]:
    """Return a list of warning strings if `selector` looks fragile.

    Mirrors the post-generation checks in `validate_xaml/lints_selectors.py`
    (lints 9, 14, 97) so the user sees the same diagnoses *before* the
    project is built — not after. Each warning string is prefixed with
    `location` so callers can tell which app/screen/element triggered it.
    """
    warnings: list[str] = []

    # Lint 9 / 14: idx as the only or dominant discriminator.
    idx_match = re.search(r"idx='(\d+)'", selector)
    if idx_match and int(idx_match.group(1)) > 0:
        # Strip the leading <tag and trailing /> to count remaining attrs.
        body = re.sub(r"^<\w+\s*", "", selector.strip())
        body = re.sub(r"\s*/?>\s*$", "", body)
        attrs = re.findall(r"(\w[\w-]*)='", body)
        non_idx_discriminators = [a for a in attrs if a not in ("idx", "tag", "type")]
        if not non_idx_discriminators:
            warnings.append(
                f"{location}: selector relies on idx alone "
                f"({selector!r}) — extremely fragile under page reflows. "
                f"Add aaname/id/parentid for stability."
            )
        elif int(idx_match.group(1)) > 2:
            warnings.append(
                f"{location}: selector uses idx={idx_match.group(1)} "
                f"({selector!r}) — high indices break when layout changes."
            )

    # Lint 14-style: innertext='...*' wildcard with no other anchor.
    if re.search(r"innertext='[^']*\*'", selector):
        body = re.sub(r"^<\w+\s*", "", selector.strip())
        body = re.sub(r"\s*/?>\s*$", "", body)
        attrs = re.findall(r"(\w[\w-]*)='", body)
        anchor_attrs = [a for a in attrs if a in ("aaname", "id", "parentid", "name", "automationid")]
        if not anchor_attrs:
            warnings.append(
                f"{location}: selector uses wildcard innertext "
                f"({selector!r}) without an aaname/id/parentid anchor — "
                f"fails when surrounding text changes."
            )

    # Bare web selector with no discriminator beyond tag/type.
    bare_match = re.match(
        r"^\s*<webctrl(?:\s+(?:tag|type)='[^']*')+\s*/?>\s*$",
        selector,
    )
    if bare_match:
        warnings.append(
            f"{location}: selector has no discriminator beyond tag/type "
            f"({selector!r}) — matches every element of that kind. "
            f"Add id/aaname/parentid to disambiguate."
        )

    # Lint 97: css-selector= is documented as fragile.
    if "css-selector=" in selector.lower():
        warnings.append(
            f"{location}: selector uses css-selector= "
            f"({selector!r}) — CSS selectors break under DOM restructure. "
            f"Prefer id/aaname/parentid attributes."
        )

    return warnings


def _check_apps_selectors(apps: list[dict]) -> list[str]:
    """Collect quality warnings for every selector under `apps`."""
    warnings: list[str] = []
    for app in apps:
        app_name = app.get("name", "<unnamed>")
        app_sel = app.get("selector")
        if app_sel:
            warnings.extend(_validate_selector_quality(app_sel, f"app {app_name!r}"))
        for screen in app.get("screens", []):
            screen_name = screen.get("name", "<unnamed>")
            for elem in screen.get("elements", []):
                elem_name = elem.get("name", "<unnamed>")
                elem_sel = elem.get("selector")
                if elem_sel:
                    warnings.extend(
                        _validate_selector_quality(
                            elem_sel,
                            f"{app_name}/{screen_name}/{elem_name}",
                        )
                    )
    return warnings


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

# Map taxonomy types to their UiPath element types
TAXONOMY_TO_ELEMENT_TYPE = {
    "Input": "InputBox",
    "Password": "InputBoxPassword",
    "Button": "Button",
    "Dropdown": "DropDown",
    "Link": "Link",
    "CheckBox": "CheckBox",
    "RadioButton": "RadioButton",
    "Text": "Text",
}


def generate_object_repository(
    apps: list[dict],
    project_dir: str,
    strict_selectors: bool = False,
) -> dict:
    """Generate the Object Repository directory tree for a UiPath project.

    Args:
        apps: List of application definitions (see module docstring for schema).
        project_dir: Root directory of the UiPath project.
        strict_selectors: When True, raise ValueError if any captured
            selector trips the fragility checks (idx-only, innertext
            wildcard, bare tag, css-selector). When False (default),
            warnings go to stderr and generation proceeds.

    Returns:
        Dictionary with reference mappings:
        {
            "library_id": "...",
            "apps": {"AppName": {"reference": "LibId/ScreenId", "content_hash": "..."}},
            "screens": {"AppName/ScreenName": {"reference": "...", "content_hash": "..."}},
            "elements": {"AppName/ScreenName/ElementName": {"reference": "...", "content_hash": "...", "guid": "..."}},
        }
    """
    selector_warnings = _check_apps_selectors(apps)
    if selector_warnings:
        if strict_selectors:
            raise ValueError(
                "Selector quality gate failed:\n  - "
                + "\n  - ".join(selector_warnings)
            )
        import sys as _sys
        for w in selector_warnings:
            print(f"⚠ selector quality: {w}", file=_sys.stderr)

    project_path = Path(project_dir)
    objects_dir = project_path / ".objects"
    screenshots_dir = project_path / ".screenshots"

    # Create base directories
    objects_dir.mkdir(parents=True, exist_ok=True)
    (objects_dir / ".data").mkdir(exist_ok=True)
    screenshots_dir.mkdir(exist_ok=True)
    (project_path / ".entities").mkdir(exist_ok=True)
    (project_path / ".templates").mkdir(exist_ok=True)

    # .tmh/config.json
    tmh_dir = project_path / ".tmh"
    tmh_dir.mkdir(exist_ok=True)
    tmh_config = tmh_dir / "config.json"
    if not tmh_config.exists():
        _write_file(tmh_config, '{\n  "issueKeyTestcaseValues": {}\n}', bom=False)

    now = _now_iso()

    # Generate Library root — seed from project path so the same project
    # always produces the same library_id, then app/screen/element IDs are
    # seeded relative to that.
    _, library_id = _generate_objrepo_id(seed=f"library:{project_dir}")

    _write_metadata(objects_dir / ".metadata", {
        "Type": "Library",
        "Id": library_id,
        "Created": now,
        "Updated": now,
        "CreatedBy": _CREATED_BY_PLATFORM,
    })
    _write_type(objects_dir / ".type", "Library")

    refs = {
        "library_id": library_id,
        "apps": {},
        "screens": {},
        "elements": {},
    }

    for app_def in apps:
        app_name = app_def["name"]
        app_selector = app_def.get("selector", "<html app='msedge.exe' title='App' />")
        app_url = app_def.get("url", "")
        # Auto-detect app type from selector: <wnd> = desktop, <html> = browser
        if "type" in app_def:
            app_type = app_def["type"]
        else:
            app_type = "desktop" if app_selector.strip().startswith("<wnd") else "browser"
        app_file_path = app_def.get("file_path", "")
        browser_type = app_def.get("browser_type", "Edge")

        # Create App node
        app_short, app_id = _generate_objrepo_id(seed=f"app:{library_id}:{app_name}")
        app_dir = objects_dir / app_short
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / ".data" / "ObjectSelectionName").mkdir(parents=True, exist_ok=True)

        _write_metadata(app_dir / ".metadata", {
            "Name": _pascalcase_to_display(app_name),
            "Type": "App",
            "Id": app_id,
            "Reference": f"{library_id}/{app_id}",
            "Created": now,
            "Updated": now,
            "CreatedBy": _CREATED_BY_FULL,
        })
        _write_type(app_dir / ".type", "App")
        _write_file(
            app_dir / ".data" / "ObjectSelectionName" / ".content",
            "UnifiedTarget", bom=False,
        )
        _write_hash(
            app_dir / ".data" / "ObjectSelectionName" / ".hash",
            "UnifiedTarget",
        )

        # Create AppVersion node (always "1.0.0")
        ver_short, ver_id = _generate_objrepo_id(seed=f"appver:{library_id}:{app_name}:1.0.0")
        ver_dir = app_dir / ver_short
        ver_dir.mkdir(parents=True, exist_ok=True)

        _write_metadata(ver_dir / ".metadata", {
            "Name": "1.0.0",
            "Type": "AppVersion",
            "Id": ver_id,
            "Reference": f"{library_id}/{ver_id}",
            "ParentRef": f"{library_id}/{app_id}",
            "Created": now,
            "Updated": now,
            "CreatedBy": _CREATED_BY_FULL,
        })
        _write_type(ver_dir / ".type", "AppVersion")

        for screen_def in app_def.get("screens", []):
            screen_name = screen_def["name"]
            screen_url = screen_def.get("url", app_url)

            # Create Screen node
            scr_short, scr_id = _generate_objrepo_id(seed=f"screen:{library_id}:{app_name}:{screen_name}")
            scr_dir = ver_dir / scr_short
            scr_dir.mkdir(parents=True, exist_ok=True)

            # Generate screen data XML (desktop vs browser)
            screen_reference = f"{library_id}/{scr_id}"
            if app_type == "desktop":
                screen_xml_template = _generate_screen_data_xml_desktop(
                    app_selector, app_file_path
                )
                # Desktop template has {reference} and {target_app_content_hash} placeholders.
                # Compute TargetApp hash first (on template with {reference} resolved but
                # {content_hash}/{target_app_content_hash} still as placeholders — matches
                # Studio behavior where TargetApp hash covers the TargetApp element only).
                screen_xml_template = screen_xml_template.replace("{reference}", screen_reference)
                # Compute TargetApp content hash from just the TargetApp element
                ta_match = re.search(r"(<TargetApp .*?</TargetApp>)", screen_xml_template, re.DOTALL)
                ta_content_hash = _content_hash(ta_match.group(1)) if ta_match else _content_hash("")
                screen_xml_template = screen_xml_template.replace("{target_app_content_hash}", ta_content_hash)
            else:
                screen_xml_template = _generate_screen_data_xml(
                    app_selector, screen_url, browser_type
                )
            screen_content_hash = _content_hash(screen_xml_template)
            screen_xml = screen_xml_template.replace("{content_hash}", screen_content_hash)

            # Write screen data
            screen_data_dir = scr_dir / ".data" / "ObjectRepositoryScreenData"
            screen_data_dir.mkdir(parents=True, exist_ok=True)
            (screen_data_dir / ".attributes").mkdir(exist_ok=True)
            (screen_data_dir / ".images" / ".design").mkdir(parents=True, exist_ok=True)

            _write_file(screen_data_dir / ".content", screen_xml, bom=False)
            _write_hash(screen_data_dir / ".hash", screen_xml)
            _write_search_hash(
                screen_data_dir / ".attributes" / "SearchHash",
                seed=f"screen:{library_id}:{app_name}:{screen_name}",
            )

            _write_metadata(scr_dir / ".metadata", {
                "Name": _pascalcase_to_display(screen_name),
                "Type": "Screen",
                "Id": scr_id,
                "Reference": f"{library_id}/{scr_id}",
                "ParentRef": f"{library_id}/{ver_id}",
                "Created": now,
                "Updated": now,
                "CreatedBy": _CREATED_BY_PLATFORM,
            })
            _write_type(scr_dir / ".type", "Screen")

            screen_key = f"{app_name}/{screen_name}"
            refs["screens"][screen_key] = {
                "reference": f"{library_id}/{scr_id}",
                "content_hash": screen_content_hash,
            }

            # Store first screen reference as the app-level reference
            # (used by NApplicationCard.TargetApp)
            if app_name not in refs["apps"]:
                refs["apps"][app_name] = {
                    "reference": f"{library_id}/{scr_id}",
                    "content_hash": screen_content_hash,
                }

            for elem_def in screen_def.get("elements", []):
                elem_name = elem_def["name"]
                taxonomy_type = elem_def.get("taxonomy_type", "Input")
                element_type = elem_def.get(
                    "element_type",
                    TAXONOMY_TO_ELEMENT_TYPE.get(taxonomy_type, "InputBox"),
                )
                elem_selector = elem_def["selector"]
                elem_seed = f"elem:{library_id}:{app_name}:{screen_name}:{elem_name}"
                elem_guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"uipath-core:elemguid:{elem_seed}"))

                # Create Element node
                elem_short, elem_id = _generate_objrepo_id(seed=elem_seed)
                elem_dir = scr_dir / elem_short
                elem_dir.mkdir(parents=True, exist_ok=True)

                # Generate target data XML
                target_xml_template = _generate_target_data_xml(
                    element_selector=elem_selector,
                    app_selector=app_selector,
                    element_type=element_type,
                    element_guid=elem_guid,
                    browser_url=screen_url,
                )
                target_content_hash = _content_hash(target_xml_template)
                target_xml = target_xml_template.replace("{content_hash}", target_content_hash)

                # Write target data
                target_data_dir = elem_dir / ".data" / "ObjectRepositoryTargetData"
                target_data_dir.mkdir(parents=True, exist_ok=True)
                (target_data_dir / ".attributes").mkdir(exist_ok=True)
                (target_data_dir / ".images" / ".design").mkdir(parents=True, exist_ok=True)

                _write_file(target_data_dir / ".content", target_xml, bom=False)
                _write_hash(target_data_dir / ".hash", target_xml)
                _write_search_hash(
                    target_data_dir / ".attributes" / "SearchHash",
                    seed=elem_seed,
                )

                _write_metadata(elem_dir / ".metadata", {
                    "Name": _pascalcase_to_display(elem_name),
                    "Type": "Element",
                    "TaxonomyType": taxonomy_type,
                    "Id": elem_id,
                    "Reference": f"{library_id}/{elem_id}",
                    "ParentRef": f"{library_id}/{scr_id}",
                    "Created": now,
                    "Updated": now,
                    "CreatedBy": _CREATED_BY_PLATFORM,
                })
                _write_type(elem_dir / ".type", "Element")

                elem_key = f"{app_name}/{screen_name}/{elem_name}"
                refs["elements"][elem_key] = {
                    "reference": f"{library_id}/{elem_id}",
                    "content_hash": target_content_hash,
                    "guid": elem_guid,
                }

    return refs


# ---------------------------------------------------------------------------
# CLI for standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    def _print_usage():
        print("Usage:")
        print("  python3 generate_object_repository.py --from-selectors <selectors.json> --project-dir <dir>")
        print("  python3 generate_object_repository.py --self-test")
        print()
        print("  --from-selectors    Path to selectors.json with apps/screens/elements")
        print("  --project-dir       Path to UiPath project root (must contain .objects/)")
        print("  --strict-selectors  Treat selector-quality warnings as fatal errors")
        print("  --self-test         Run built-in self-test with sample data")

    args = sys.argv[1:]

    if "--self-test" in args:
        import tempfile
        test_apps = [{
            "name": "Edge The Internet",
            "selector": "<html app='msedge.exe' title='The Internet' />",
            "url": "https://the-internet.herokuapp.com/login",
            "browser_type": "Edge",
            "screens": [{
                "name": "Login",
                "url": "https://the-internet.herokuapp.com/login",
                "elements": [
                    {"name": "Username", "taxonomy_type": "Input",
                     "selector": "<webctrl id='username' tag='INPUT' />"},
                    {"name": "Password", "taxonomy_type": "Password",
                     "selector": "<webctrl id='password' tag='INPUT' />"},
                ],
            }],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, "TestProject")
            os.makedirs(project_dir)
            refs = generate_object_repository(test_apps, project_dir)
            print(f"Apps: {list(refs['apps'].keys())}")
            print(f"Screens: {list(refs['screens'].keys())}")
            print(f"Elements: {list(refs['elements'].keys())}")
            count = sum(len(f) for _, _, f in os.walk(os.path.join(project_dir, '.objects')))
            print(f"Files in .objects/: {count}")
            print("OK")

    elif "--from-selectors" in args:
        try:
            sel_idx = args.index("--from-selectors")
            selectors_path = args[sel_idx + 1]
            dir_idx = args.index("--project-dir")
            project_dir = args[dir_idx + 1]
        except (IndexError, ValueError):
            _print_usage()
            sys.exit(1)

        strict = "--strict-selectors" in args

        if not os.path.isfile(selectors_path):
            print(f"Error: selectors file not found: {selectors_path}", file=sys.stderr)
            sys.exit(1)
        if not os.path.isdir(project_dir):
            print(f"Error: project directory not found: {project_dir}", file=sys.stderr)
            sys.exit(1)

        with open(selectors_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        apps = data.get("apps", [])
        if not apps:
            print("Error: selectors.json has no 'apps' array", file=sys.stderr)
            sys.exit(1)

        refs = generate_object_repository(apps, project_dir, strict_selectors=strict)

        app_count = len(refs["apps"])
        screen_count = len(refs["screens"])
        elem_count = len(refs["elements"])
        print(f"Object Repository generated: {app_count} app(s), {screen_count} screen(s), {elem_count} element(s)")
        print(f"  Project: {project_dir}")
        print(f"  Source:  {selectors_path}")

        # Write refs for downstream use
        refs_path = os.path.join(project_dir, ".objects", "refs.json")
        with open(refs_path, "w", encoding="utf-8") as f:
            json.dump(refs, f, indent=2)
        print(f"  Refs:    {refs_path}")
    else:
        _print_usage()
        sys.exit(1)
