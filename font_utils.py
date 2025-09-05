# Font Utilities - Basic font operations and helpers

import os
import unicodedata
from fontTools.ttLib import TTFont
from fontTools.agl import toUnicode
from utils import safe_font_load, log_error, normalize_path

_ttfont_cache = {}

UPPER_TEMPLATE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER_TEMPLATE = "abcdefghijklmnopqrstuvwxyz"


def get_ttfont(input_font):
    """Get a cached TTFont instance using safe font loading."""
    if input_font in _ttfont_cache:
        return _ttfont_cache[input_font]

    font = safe_font_load(input_font)
    if font:
        _ttfont_cache[input_font] = font
        return font
    else:
        log_error(f"Failed to load font: {input_font}")
        return None


def clear_font_cache():
    """Clear the TTFont cache."""
    global _ttfont_cache
    _ttfont_cache.clear()


def filteredCharset(input_font):
    """Get charset excluding glyphs without outlines.

    Updated logic: Prefer cmap-based collection of characters so we keep
    actual encoded Unicode codepoints (including ligature codepoints)
    instead of deriving characters from glyph names via AGL which can
    expand a ligature glyph name like 'f_i' into the sequence 'fi'.
    This prevents noisy "split" ligatures in proofs while still showing
    ligatures that have real Unicode codepoints (detected by a unicode
    name containing 'LIGATURE').
    """
    try:
        f = get_ttfont(input_font)
        if not f:
            return ""

        gset = f.getGlyphSet()

        def _has_outline(gname):
            # Skip synthesized or non-export glyphs indicated by dot names
            if "." in gname:
                return False
            try:
                if "CFF " in f:
                    top_dict = f["CFF "].cff.topDictIndex[0]
                    cs = top_dict.CharStrings[gname]
                    return cs.calcBounds(top_dict.CharStrings) is not None
                elif "glyf" in f:
                    return f["glyf"][gname].numberOfContours != 0
            except Exception:
                return False
            # Other outline table types – assume present
            return True

        charset_chars = []
        seen = set()

        # 1. Primary path: iterate cmap so we only collect encoded chars
        try:
            cmap = f.getBestCmap() or {}
        except Exception:
            cmap = {}

        if cmap:
            for codepoint, gname in sorted(cmap.items()):
                if gname not in gset:
                    continue
                if not _has_outline(gname):
                    continue
                ch = chr(codepoint)
                # Keep each codepoint once
                if ch in seen:
                    continue
                # If it's a ligature codepoint we rely on the single char; no decomposition
                # (The check below is mostly informational; we don't alter ch.)
                if "LIGATURE" in unicodedata.name(ch, ""):
                    charset_chars.append(ch)
                    seen.add(ch)
                else:
                    charset_chars.append(ch)
                    seen.add(ch)

        # 2. Fallback: previous glyph-name based logic if cmap empty (e.g. bitmap/special fonts)
        if not charset_chars:
            for gname in gset.keys():
                if not _has_outline(gname):
                    continue
                try:
                    chars = toUnicode(gname)
                    # If AGL mapping returns multi-character sequence that looks like a decomposed ligature
                    # we skip it to avoid noise; only keep single characters.
                    if len(chars) == 1 and chars not in seen:
                        charset_chars.append(chars)
                        seen.add(chars)
                except Exception:
                    continue

        return "".join(charset_chars)

    except Exception as e:
        log_error(f"Error filtering charset for {input_font}: {e}")
        return ""


def is_valid_font_file(path):
    """Check if a path points to a valid font file."""
    from utils import normalize_path, is_valid_font_extension

    normalized_path = normalize_path(path, font_specific=True)
    return is_valid_font_extension(normalized_path) and os.path.exists(normalized_path)


def get_font_family_name(font_path):
    """Get family name from font file."""
    return os.path.splitext(os.path.basename(font_path))[0].split("-")[0]


def get_font_info(font_path):
    """Get comprehensive font information including features and axes."""
    import drawBot as db

    font_info = {
        "features": db.listOpenTypeFeatures(font_path),
        "name": os.path.basename(font_path),
        "axes": {},
    }

    # Process variable font axes
    variableDict = db.listFontVariations(font_path)
    if variableDict:
        for axis, data in variableDict.items():
            # Get unique values in order: min, default, max
            values = []
            for key in ("minValue", "defaultValue", "maxValue"):
                v = data.get(key)
                if v is not None and v not in values:
                    # Convert to int if it's a whole number
                    values.append(
                        int(v) if isinstance(v, (int, float)) and v == int(v) else v
                    )
            font_info["axes"][axis] = values

    return font_info


def parse_axis_value(value_str):
    """Parse a string value to float, int, or keep as string."""
    try:
        return float(value_str) if "." in value_str else int(value_str)
    except ValueError:
        return value_str


def format_axis_values(axis_values):
    """Format axis values as comma-separated string."""
    return ",".join(str(v) for v in axis_values)


def parse_axis_values_string(values_str):
    """Parse comma-separated axis values string into list."""
    return [parse_axis_value(v.strip()) for v in values_str.split(",") if v.strip()]
