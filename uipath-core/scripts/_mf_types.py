"""Variable type normalization for modify_framework.

Exports:
    _ALL_XMLNS_PREFIXES — full xmlns prefix tuple (core + plugin-registered)
    VAR_TYPE_MAP        — short-form → xmlns-prefixed XAML type mapping
    _normalize_var_type — normalize a raw type string to xmlns-prefixed form
"""
import os
import sys

# Ensure scripts/ is on sys.path so we can import utils
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from utils import TYPE_MAP_BASE, KNOWN_XMLNS_PREFIXES
from plugin_loader import load_plugins, get_extra_namespaces

load_plugins()

# Build full xmlns prefix list (core + plugin-registered prefixes)
_ALL_XMLNS_PREFIXES = KNOWN_XMLNS_PREFIXES + tuple(f"{p}:" for p in get_extra_namespaces())


# ── Variable type normalization ───────────────────────────────────────
# Extends utils.TYPE_MAP_BASE with additional types for framework variables.
# add-variables accepts the same short forms as JSON specs plus extras.

VAR_TYPE_MAP = {
    **TYPE_MAP_BASE,
    # Additional types for framework variables (not in base map)
    "Int64": "x:Int64",
    "Double": "x:Double",
    "Decimal": "x:Decimal",
    "DataTable": "sd:DataTable",
    "DataRow": "sd:DataRow",
    "MailMessage": "snm:MailMessage",
    "Exception": "s:Exception",
    "TimeSpan": "s:TimeSpan",
    "DateTime": "s:DateTime",
}


def _normalize_var_type(raw_type: str) -> str:
    """Normalize a variable type to its xmlns-prefixed XAML form.

    - Short forms in VAR_TYPE_MAP are mapped (e.g. 'DataTable' -> 'sd:DataTable')
    - Already-prefixed types pass through (e.g. 'sd:DataTable' -> 'sd:DataTable')
    - Unknown bare types raise ValueError (fail fast, never produce invalid XAML)
    """
    # Direct map match
    if raw_type in VAR_TYPE_MAP:
        return VAR_TYPE_MAP[raw_type]

    # Already prefixed — pass through
    if any(raw_type.startswith(p) for p in _ALL_XMLNS_PREFIXES):
        return raw_type

    # Array types with prefix are OK (e.g. s:String[])
    if ":" in raw_type:
        return raw_type

    # Unknown bare type — error
    valid_shorts = sorted(VAR_TYPE_MAP.keys())
    raise ValueError(
        f"Unknown bare type '{raw_type}'. "
        f"Use a prefixed form (e.g. 'sd:DataTable') or a short form: "
        f"{', '.join(valid_shorts)}"
    )
