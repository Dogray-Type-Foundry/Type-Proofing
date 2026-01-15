# Fonts - Font utilities, variable fonts, character analysis, and font management
# Consolidated from font_utils.py, variable_font_utils.py, character_analysis.py, and font_manager.py

import os
import unicodedata
from itertools import product
from fontTools.ttLib import TTFont
from fontTools.agl import toUnicode
from fontTools.unicodedata import script, block
import drawBot as db

from settings import safe_font_load, log_error, normalize_path
from config import (
    FsSelection,
    AXES_VALUES,
    AR_TEMPLATE,
    FA_TEMPLATE,
    ARFA_DUAL_JOIN,
    ARFA_RIGHT_JOIN,
)


# =============================================================================
# Font Utilities - Basic font operations and helpers
# =============================================================================

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
    from settings import normalize_path, is_valid_font_extension

    normalized_path = normalize_path(path, font_specific=True)
    return is_valid_font_extension(normalized_path) and os.path.exists(normalized_path)


def get_font_family_name(font_path):
    """Get family name from font file."""
    return os.path.splitext(os.path.basename(font_path))[0].split("-")[0]


def get_font_info(font_path):
    """Get comprehensive font information including features and axes."""
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


# =============================================================================
# Variable Font Utilities - Variable font axis management and style pairing
# =============================================================================


def product_dict(**kwargs):
    """Generate dictionary products from keyword arguments."""
    keys = kwargs.keys()
    vals = kwargs.values()
    for instance in product(*vals):
        yield dict(zip(keys, instance))


def variableFont(input_font):
    """Get variable font axis information and product combinations."""
    variableDict = db.listFontVariations(input_font)
    isVariableFont = bool(variableDict)

    if not isVariableFont:
        return "", {}

    # Use predefined axes values if available
    if AXES_VALUES:
        return list(product_dict(**AXES_VALUES)), AXES_VALUES

    # Generate axes combinations from font data
    axesContents = {}
    for axis, data in variableDict.items():
        min_val, default_val, max_val = (
            int(data[k]) for k in ("minValue", "defaultValue", "maxValue")
        )

        if default_val in (min_val, max_val):
            axesContents[axis] = (min_val, max_val)
        else:
            axesContents[axis] = (min_val, default_val, max_val)

    return list(product_dict(**axesContents)), axesContents


def pairStaticStyles(fonts):
    """Pair upright/italic and regular/bold fonts by weight class and family."""
    staticUpItPairs = dict()
    staticRgBdPairs = dict()
    uprights = []
    italics = []
    regulars = []
    bolds = []

    for i in fonts:
        f = get_ttfont(i)
        if f["OS/2"].fsSelection & FsSelection.ITALIC:
            italics.append(i)
        else:
            uprights.append(i)

        if str(f["name"].names[1]) == f["name"].getBestFamilyName():
            if f["OS/2"].usWeightClass == 400:
                regulars.append(i)
            if f["OS/2"].usWeightClass == 700:
                bolds.append(i)

    for u in uprights:
        upfont = get_ttfont(u)
        for i in italics:
            itfont = get_ttfont(i)
            if upfont["OS/2"].usWeightClass == itfont["OS/2"].usWeightClass:
                staticUpItPairs[upfont["OS/2"].usWeightClass] = (u, i)

    for r in regulars:
        rgfont = get_ttfont(r)
        for b in bolds:
            bdfont = get_ttfont(b)
            if rgfont["name"].getBestFamilyName() == bdfont["name"].getBestFamilyName():
                if (
                    rgfont["name"].getBestSubFamilyName() == "Regular"
                    and bdfont["name"].getBestSubFamilyName() == "Bold"
                ):
                    staticRgBdPairs[rgfont["name"].getBestSubFamilyName()] = (r, b)
                elif (
                    rgfont["name"].getBestSubFamilyName() == "Italic"
                    and bdfont["name"].getBestSubFamilyName() == "Bold Italic"
                ):
                    staticRgBdPairs[rgfont["name"].getBestSubFamilyName()] = (r, b)

    return dict(sorted(staticUpItPairs.items())), dict(sorted(staticRgBdPairs.items()))


def get_all_font_axes(fonts):
    """Get all unique axes across all loaded fonts in their original font order."""
    all_axes = []
    seen_axes = set()

    for font_path in fonts:
        # Use TTFont to get axes in original order from fvar table
        try:
            f = get_ttfont(font_path)
            if "fvar" in f:
                for axis in f["fvar"].axes:
                    axis_tag = axis.axisTag
                    if axis_tag not in seen_axes:
                        all_axes.append(axis_tag)
                        seen_axes.add(axis_tag)
        except Exception:
            # Fallback for non-variable fonts or error cases
            continue

    return all_axes


# =============================================================================
# Character Analysis - Character set analysis and categorization
# =============================================================================


def find_accented(char):
    """Check if character has diacritical marks."""
    decomp = unicodedata.normalize("NFD", char)
    return len(decomp) > 1 and unicodedata.category(decomp[1]) == "Mn"


def categorize(charset):
    """Categorize characters by Unicode category."""
    cat_map = {
        "Lu": "uniLu",  # Letter, uppercase
        "Ll": "uniLl",  # Letter, lowercase
        "Lo": "uniLo",  # Letter, other
        "Po": "uniPo",  # Punctuation, other
        "Pc": "uniPc",  # Punctuation, connector
        "Pd": "uniPd",  # Punctuation, dash
        "Ps": "uniPs",  # Punctuation, open
        "Pe": "uniPe",  # Punctuation, close
        "Pi": "uniPi",  # Punctuation, initial quote
        "Pf": "uniPf",  # Punctuation, final quote
        "Sm": "uniSm",  # Symbol, math
        "Sc": "uniSc",  # Symbol, currency
        "Nd": "uniNd",  # Number, decimal digit
        "No": "uniNo",  # Number, other
        "So": "uniSo",  # Symbol, other
    }

    result = {k: [] for k in cat_map.values()}
    result.update(
        {
            "uniLlBase": [],
            "uniLuBase": [],
            "accented": [],
            "accented_plus": [],  # Expanded accented category
            "latn": [],
            "arab": [],
            "fa": [],
            "ar": [],
            "arabTyped": [],
            "arfaDualJoin": [],
            "arfaRightJoin": [],
        }
    )

    for char in charset:
        cat = unicodedata.category(char)
        if cat in cat_map:
            result[cat_map[cat]].append(char)

        if cat in ("Ll", "Lu"):
            base_key = "uniLlBase" if cat == "Ll" else "uniLuBase"
            target_key = "accented" if find_accented(char) else base_key
            result[target_key].append(char)

        # Script-based categorization
        try:
            char_script = script(char)
            if char_script == "Latn":
                result["latn"].append(char)
            elif char_script == "Arab":
                result["arab"].append(char)
                # Check if it's specifically Arabic block
                if block(char) == "Arabic":
                    result["arabTyped"].append(char)
        except (ImportError, AttributeError):
            # Fallback if fontTools.unicodedata is not available
            pass

        # Template-based categorization for Arabic/Farsi
        if char in AR_TEMPLATE:
            result["ar"].append(char)
        if char in FA_TEMPLATE:
            result["fa"].append(char)
        if char in ARFA_DUAL_JOIN:
            result["arfaDualJoin"].append(char)
        if char in ARFA_RIGHT_JOIN:
            result["arfaRightJoin"].append(char)

    # Convert to strings and add boolean flags
    result_str = {k: "".join(v) for k, v in result.items()}

    # Create expanded accented category (accented + other uppercase/lowercase not in basic templates)
    uc_lc = result_str["uniLu"] + result_str["uniLl"]
    other = ""
    for char in uc_lc:
        if (
            char not in result_str["accented"]
            and char not in LOWER_TEMPLATE
            and char not in UPPER_TEMPLATE
        ):
            other += char

    result_str["accented_plus"] = result_str["accented"] + other

    result_str.update(
        {
            "uppercaseOnly": result_str["uniLl"] == "",
            "lowercaseOnly": result_str["uniLu"] == "",
        }
    )

    return result_str


def check_arabic_support(charset):
    """Check if charset supports Arabic characters."""
    required_chars = {"ب", "ا", "ح", "د", "ر"}  # Arabic test characters
    charset_set = set(charset)
    return required_chars.issubset(charset_set)


def get_charset_proof_categories(cat):
    """Get organized character sets for character set proofs, matching old drawbot logic.

    Args:
        cat: Dictionary from categorize() function containing character categories

    Returns:
        Dictionary with organized character sets for proofs
    """
    # Numbers and symbols combined (like old version)
    num = (
        cat["uniNd"]
        + "\n"
        + cat["uniSm"]
        + "\n"
        + cat["uniSc"]
        + "\n"
        + cat.get("uniNo", "")
    )

    # All punctuation categories combined
    punct = (
        cat["uniPo"]
        + cat["uniPc"]
        + cat["uniPd"]
        + cat["uniPs"]
        + cat["uniPe"]
        + cat["uniPi"]
        + cat["uniPf"]
    )

    # Sort uppercase and lowercase base characters by Unicode codepoint
    uppercase_base_sorted = "".join(sorted(cat["uniLuBase"], key=ord))
    lowercase_base_sorted = "".join(sorted(cat["uniLlBase"], key=ord))

    # Return organized categories
    return {
        "uppercase_base": uppercase_base_sorted,
        "lowercase_base": lowercase_base_sorted,
        "numbers_symbols": num,
        "punctuation": punct,
        "accented": cat["accented"],
    }


def get_character_set(font_path):
    """Get character set from a font file (alias for filteredCharset)."""
    return filteredCharset(font_path)


# =============================================================================
# Font Manager - Core font management functionality
# =============================================================================


class FontManager:
    """Manages font information and processing."""

    def __init__(self, settings=None):
        self.settings = settings
        self.fonts = tuple()
        self.font_info = {}
        self.axis_values_by_font = {}

        # Load fonts from settings if available
        if self.settings:
            saved_fonts = self.settings.get_fonts()
            if saved_fonts:
                self.fonts = tuple(saved_fonts)
                self.update_font_info()

    def add_fonts(self, paths):
        """Add new fonts to the collection."""
        valid_paths = [
            normalize_path(p, font_specific=True)
            for p in paths
            if is_valid_font_file(normalize_path(p, font_specific=True))
        ]

        # Only add fonts not already in the list
        new_fonts = [p for p in valid_paths if p not in self.fonts]
        if not new_fonts:
            return False

        self.fonts = tuple(list(self.fonts) + new_fonts)
        self.update_font_info()

        # Save to settings
        if self.settings:
            self.settings.set_fonts(list(self.fonts))

        return True

    def remove_fonts_by_indices(self, indices):
        """Remove fonts by their indices."""
        if not indices:
            return
        fonts_list = list(self.fonts)
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(fonts_list):
                removed = fonts_list.pop(index)
                if removed in self.axis_values_by_font:
                    del self.axis_values_by_font[removed]
        self.fonts = tuple(fonts_list)
        self.update_font_info()

        # Save to settings
        if self.settings:
            self.settings.set_fonts(list(self.fonts))
            # Also clean up axis values in settings
            saved_axis_values = self.settings.data.get("fonts", {}).get(
                "axis_values", {}
            )
            for font_path in list(saved_axis_values.keys()):
                if font_path not in self.fonts:
                    # Use the proper method to remove axis values
                    self.settings.set_font_axis_values(font_path, {})

    def update_font_info(self):
        """Update font information for all loaded fonts."""
        self.font_info = {}
        self.axis_values_by_font = {}

        for font_path in self.fonts:
            try:
                font_info = get_font_info(font_path)
                self.font_info[font_path] = font_info

                # Initialize with default axes from font
                self.axis_values_by_font[font_path] = font_info.get("axes", {})

                # Override with saved user axis values from settings if available
                if self.settings:
                    saved_axis_values = self.settings.get_font_axis_values(font_path)
                    if saved_axis_values:
                        self.axis_values_by_font[font_path] = saved_axis_values

            except Exception as e:
                print(f"Error processing font {font_path}: {e}")
                self.font_info[font_path] = {
                    "axes": {},
                    "name": os.path.basename(font_path),
                }
                self.axis_values_by_font[font_path] = {}

    def get_table_data(self):
        """Get formatted data for the file table display."""
        table_data = []
        for font_path in self.fonts:
            info = self.font_info.get(font_path, {})
            row = {"name": info.get("name", os.path.basename(font_path))}
            # Format axes dict as string for display
            axes_str = "; ".join(
                f"{k}: {format_axis_values(v)}"
                for k, v in self.axis_values_by_font.get(font_path, {}).items()
            )
            row["axes"] = axes_str
            row["_path"] = font_path
            table_data.append(row)
        return table_data

    def update_axis_values_from_table(self, table_data, all_axes=None):
        """Update axis values from table data (supports both formats)."""
        for row in table_data:
            font_path = row.get("_path")
            if not font_path:
                continue

            axes_dict = {}

            if all_axes:  # Individual axis columns format
                for axis in all_axes:
                    values_str = row.get(axis, "")
                    if values_str.strip():
                        values = parse_axis_values_string(values_str)
                        if values:
                            axes_dict[axis] = values
            else:  # Combined axes string format
                axes_str = row.get("axes", "")
                for part in axes_str.split(";"):
                    part = part.strip()
                    if not part or ":" not in part:
                        continue
                    axis, values_str = part.split(":", 1)
                    values = parse_axis_values_string(values_str)
                    if values:
                        axes_dict[axis.strip()] = values

            self.axis_values_by_font[font_path] = axes_dict
            if self.settings:
                self.settings.set_font_axis_values(font_path, axes_dict)

    def has_arabic_support(self):
        """Check if any loaded font supports Arabic characters."""
        if not self.fonts:
            return False

        for font_path in self.fonts:
            try:
                charset = filteredCharset(font_path)
                if check_arabic_support(charset):
                    return True
            except Exception as e:
                print(f"Error checking Arabic support in {font_path}: {e}")
                continue

        return False

    def get_axis_values_for_font(self, font_path):
        """Get axis values for a specific font."""
        return self.axis_values_by_font.get(font_path, {})

    def get_family_name(self):
        """Get family name from the first font."""
        return get_font_family_name(self.fonts[0]) if self.fonts else ""

    def load_fonts(self, font_paths):
        """Load fonts from a list of paths (replaces existing fonts)."""
        if not font_paths:
            return False

        valid_paths = [
            normalize_path(p, font_specific=True)
            for p in font_paths
            if is_valid_font_file(normalize_path(p, font_specific=True))
        ]

        if not valid_paths:
            return False

        self.fonts = tuple(valid_paths)
        self.update_font_info()

        # Save to settings
        if self.settings:
            self.settings.set_fonts(list(self.fonts))

        return True

    def get_all_axes(self):
        """Get all unique axes across all loaded fonts in their original font order."""
        return get_all_font_axes(self.fonts)

    def get_table_data_with_individual_axes(self):
        """Get formatted data for the file table display with individual axis columns."""
        all_axes = self.get_all_axes()
        table_data = []

        for font_path in self.fonts:
            info = self.font_info.get(font_path, {})
            row = {"name": info.get("name", os.path.basename(font_path))}

            # Add each axis as a separate column
            axes_dict = self.axis_values_by_font.get(font_path, {})
            for axis in all_axes:
                row[axis] = (
                    format_axis_values(axes_dict[axis]) if axis in axes_dict else ""
                )

            row["_path"] = font_path
            table_data.append(row)

        return table_data, all_axes
