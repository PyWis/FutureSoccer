"""Small input-validation/coercion helpers used across routes."""
import re

_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def valid_hex_color(value, default):
    """Return value if it's a valid #RRGGBB hex color, else default."""
    if isinstance(value, str) and _HEX_COLOR_RE.match(value.strip()):
        return value.strip().lower()
    return default


def parse_float(value, default=0.0, minimum=None, maximum=None):
    """Best-effort float parse with optional clamping. Never raises."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:  # NaN
        return default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def parse_int(value, default=0, minimum=None, maximum=None):
    """Best-effort int parse with optional clamping. Never raises."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result
