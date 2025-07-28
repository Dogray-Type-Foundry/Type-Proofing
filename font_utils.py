# Font Utilities - Basic font operations and helpers

import os
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
    """Get charset excluding glyphs without outlines."""
    try:
        f = get_ttfont(input_font)
        if not f:
            return ""

        gset = f.getGlyphSet()
        charset = ""

        for i in gset:
            if "." in i:
                continue

            if "CFF " in f:
                top_dict = f["CFF "].cff.topDictIndex[0]
                char_strings = top_dict.CharStrings
                char_string = char_strings[i]
                bounds = char_string.calcBounds(char_strings)
                if bounds is None:
                    continue
                else:
                    charset = charset + toUnicode(i)
            elif "glyf" in f:
                if f["glyf"][i].numberOfContours == 0:
                    continue
                else:
                    charset = charset + toUnicode(i)
            else:
                charset = charset + toUnicode(i)

        return charset

    except Exception as e:
        log_error(f"Error filtering charset for {input_font}: {e}")
        return ""


def normalize_font_path(path):
    """Normalize path from various input types for font files."""
    return normalize_path(path, font_specific=True)


def is_valid_font_file(path):
    """Check if a path points to a valid font file."""
    normalized_path = normalize_font_path(path)
    return normalized_path.lower().endswith((".otf", ".ttf")) and os.path.exists(
        normalized_path
    )


def get_font_family_name(font_path):
    """Get family name from font file."""
    return os.path.splitext(os.path.basename(font_path))[0].split("-")[0]
