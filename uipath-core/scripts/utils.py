#!/usr/bin/env python3
"""Shared utilities for UiPath skill scripts.

These functions are used across core generators and plugin extensions.
They form a stable public API — do not rename without updating all consumers.
"""

import re
import uuid


def generate_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def escape_xml_attr(s: str) -> str:
    """Escape for XML attribute values (inside double quotes).

    Single quotes are NOT escaped — UiPath Studio preserves them unescaped
    in attribute values (e.g., selectors use single-quoted attribute values
    like tag='INPUT'). XML spec allows unescaped ' inside ""-delimited attrs.
    """
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def escape_vb_expr(s: str) -> str:
    """Escape a VB expression for use inside [expr] in an XML attribute.

    UiPath stores VB expressions as Message="[expr]" where quotes inside
    the expression must be &quot;. Example from Studio golden sample:
      Message="[&quot;Stop process requested.&quot;]"
      Exception="[New BusinessRuleException(&quot;Invalid item&quot;)]"

    Strategy: normalize to raw first (undo any pre-escaping), then escape
    cleanly. This avoids double-escaping on mixed input like
    '&quot;Hello&quot; & "World"' → was producing &amp;quot; (broken).
    """
    # Normalize: undo any existing XML entity escaping to get raw text.
    # Order matters: &amp; last so we don't undo our own unescaping.
    raw = (s.replace("&quot;", '"')
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&"))
    # Escape cleanly from raw text
    return (raw.replace("&", "&amp;")
               .replace('"', "&quot;")
               .replace("<", "&lt;")
               .replace(">", "&gt;"))


def normalize_selector_quotes(selector: str) -> str:
    """Normalize selector attribute values to use single quotes.

    UiPath selectors MUST use single quotes for attribute values:
      CORRECT:  <webctrl tag='INPUT' aaname='Email' />
      WRONG:    <webctrl tag="INPUT" aaname="Email" />

    Double quotes inside selectors get escaped to &quot; by escape_xml_attr,
    which UiPath reads back as literal double quotes — causing selector mismatch.

    Also undoes any pre-existing XML escaping (e.g., if Claude passes
    "&lt;webctrl tag='INPUT' /&gt;" instead of raw "<webctrl tag='INPUT' />").
    This prevents double-escaping: &lt; → &amp;lt; which causes
    "Value is not a valid XML syntax" in UiPath.
    """
    s = selector
    if '&lt;' in s or '&gt;' in s or '&amp;' in s or '&quot;' in s or '&apos;' in s:
        s = (s.replace("&amp;", "&")
              .replace("&lt;", "<")
              .replace("&gt;", ">")
              .replace("&quot;", '"')
              .replace("&apos;", "'"))
    # Replace double-quoted attribute values with single-quoted ones
    # Matches: attr="value" → attr='value'  (inside selector tags)
    s = re.sub(r'(\w+)="([^"]*)"', r"\1='\2'", s)

    # Normalize browser app names — UiPath uses the process name, not the brand
    _BROWSER_APP_FIX = {
        "edge": "msedge",
        "microsoft edge": "msedge",
        "microsoftedge": "msedge",
    }
    def _fix_app_name(m):
        raw = m.group(1)
        fixed = _BROWSER_APP_FIX.get(raw.lower(), raw)
        return f"app='{fixed}'"
    s = re.sub(r"app='([^']*)'", _fix_app_name, s)

    return s


# Browser app name → BrowserType mapping for TargetApp
BROWSER_TYPE_MAP = {
    "msedge": "Edge",
    "msedge.exe": "Edge",
    "chrome": "Chrome",
    "chrome.exe": "Chrome",
    "firefox": "Firefox",
    "firefox.exe": "Firefox",
}


def detect_browser_type(selector: str) -> str:
    """Detect BrowserType from selector's app= attribute. Returns '' for non-browser."""
    m = re.search(r"app='([^']*)'", selector)
    if not m:
        return ""
    return BROWSER_TYPE_MAP.get(m.group(1).lower(), "")


# ---------------------------------------------------------------------------
# Type mappings — canonical source of truth for short-form → xmlns-prefixed
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Known xmlns prefixes — canonical set of valid type prefixes in UiPath XAML.
# Used by generate_workflow.py and modify_framework.py to validate types.
# Plugin prefixes (upaf:, ucas:) are included; add new plugin prefixes here.
# ---------------------------------------------------------------------------

KNOWN_XMLNS_PREFIXES = (
    "x:", "s:", "sd:", "scg:", "sco:", "ss:", "ui:", "uix:",
    "uwah:", "snm:",
)
# Plugin prefixes (upaf:, ucas:, etc.) are no longer hardcoded here.
# They come from plugin_loader.get_extra_namespaces() at runtime.

TYPE_MAP_BASE = {
    # Primitives
    "String": "x:String",
    "Int32": "x:Int32",
    "Int64": "x:Int64",
    "Boolean": "x:Boolean",
    "Double": "x:Double",
    "Decimal": "x:Decimal",
    "Object": "x:Object",
    # System types
    "DateTime": "s:DateTime",
    "TimeSpan": "s:TimeSpan",
    "SecureString": "ss:SecureString",
    # UiPath types
    "UiElement": "ui:UiElement",
    "QueueItem": "ui:QueueItem",
    "GenericValue": "ui:GenericValue",
    # Data types
    "DataTable": "sd:DataTable",
    "DataRow": "sd:DataRow",
    # Collections
    "Dictionary": "scg:Dictionary(x:String, x:Object)",
    "Array_String": "s:String[]",
    "Array_Int32": "s:Int32[]",
    "Array_Object": "s:Object[]",
    # JSON (Newtonsoft)
    "JObject": "njl:JObject",
    "JArray": "njl:JArray",
    # Email
    "MailMessage": "snm:MailMessage",
}
