# Font Analysis and Character Set Processing

import os
import unicodedata
from itertools import product

# Third-party imports
import drawBot as db
from fontTools.agl import toUnicode
from fontTools.ttLib import TTFont
from fontTools.unicodedata import script, block

from config import (
    FsSelection,
    axesValues,
    arTemplate,
    faTemplate,
    arfaDualJoin,
    arfaRightJoin,
)

# Character set, filtering out empty glyphs that would normally have outlines.
_ttfont_cache = {}

# Some set templates
upperTemplate = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
lowerTemplate = "abcdefghijklmnopqrstuvwxyz"


def get_ttfont(inputFont):
    """Get a cached TTFont instance."""
    if inputFont in _ttfont_cache:
        return _ttfont_cache[inputFont]
    f = TTFont(inputFont)
    _ttfont_cache[inputFont] = f
    return f


def filteredCharset(inputFont):
    """Get charset excluding glyphs without outlines."""
    f = get_ttfont(inputFont)
    gset = f.getGlyphSet()
    charset = ""
    for i in gset:
        if "." in i:
            pass
        else:
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
    return charset


def findAccented(char):
    """Check if character has diacritical marks."""
    decomp = unicodedata.normalize("NFD", char)
    return len(decomp) > 1 and unicodedata.category(decomp[1]) == "Mn"


def categorize(charset):
    """Categorize characters by Unicode category."""
    cat_map = {
        "Lu": "uniLu",
        "Ll": "uniLl",
        "Lo": "uniLo",
        "Po": "uniPo",
        "Pc": "uniPc",
        "Pd": "uniPd",
        "Ps": "uniPs",
        "Pe": "uniPe",
        "Pi": "uniPi",
        "Pf": "uniPf",
        "Sm": "uniSm",
        "Sc": "uniSc",
        "Nd": "uniNd",
        "No": "uniNo",
    }

    result = {k: [] for k in cat_map.values()}
    result.update(
        {
            "uniLlBase": [],
            "uniLuBase": [],
            "accented": [],
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
            target_key = "accented" if findAccented(char) else base_key
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
        if char in arTemplate:
            result["ar"].append(char)
        if char in faTemplate:
            result["fa"].append(char)
        if char in arfaDualJoin:
            result["arfaDualJoin"].append(char)
        if char in arfaRightJoin:
            result["arfaRightJoin"].append(char)

    # Convert to strings and add boolean flags
    result_str = {k: "".join(v) for k, v in result.items()}
    result_str.update(
        {
            "uppercaseOnly": result_str["uniLl"] == "",
            "lowercaseOnly": result_str["uniLu"] == "",
        }
    )

    return result_str


def product_dict(**kwargs):
    """Generate dictionary products from keyword arguments."""
    keys = kwargs.keys()
    vals = kwargs.values()
    for instance in product(*vals):
        yield dict(zip(keys, instance))


def variableFont(inputFont):
    """Get variable font axis information and product combinations."""
    variableDict = db.listFontVariations(inputFont)
    isVariableFont = bool(variableDict)

    if not isVariableFont:
        return "", {}

    # Use predefined axes values if available
    if axesValues:
        return list(product_dict(**axesValues)), axesValues

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
    font_data = {}

    # Collect font data in single pass
    for font_path in fonts:
        f = get_ttfont(font_path)
        os2 = f["OS/2"]
        name = f["name"]

        font_data[font_path] = {
            "is_italic": bool(os2.fsSelection & FsSelection.ITALIC),
            "weight_class": os2.usWeightClass,
            "family_name": name.getBestFamilyName(),
            "subfamily_name": name.getBestSubFamilyName(),
            "is_main_family": str(name.names[0]) == name.getBestFamilyName(),
        }

    # Build pairs
    up_it_pairs = {}
    rg_bd_pairs = {}

    for font1, data1 in font_data.items():
        for font2, data2 in font_data.items():
            if font1 >= font2:  # Avoid duplicate pairs
                continue

            # Upright/Italic pairs by weight class
            if (
                data1["weight_class"] == data2["weight_class"]
                and data1["is_italic"] != data2["is_italic"]
            ):
                upright = font1 if not data1["is_italic"] else font2
                italic = font2 if data1["is_italic"] else font1
                up_it_pairs[data1["weight_class"]] = (upright, italic)

            # Regular/Bold pairs by family
            if (
                data1["family_name"] == data2["family_name"]
                and data1["is_main_family"]
                and data2["is_main_family"]
                and {data1["subfamily_name"], data2["subfamily_name"]}
                == {"Regular", "Bold"}
            ):
                regular = font1 if data1["subfamily_name"] == "Regular" else font2
                bold = font2 if data1["subfamily_name"] == "Bold" else font1
                rg_bd_pairs[data1["family_name"]] = (regular, bold)

    return dict(sorted(up_it_pairs.items())), dict(sorted(rg_bd_pairs.items()))


class FontManager:
    """Manages font information and processing."""

    def __init__(self):
        self.fonts = tuple()
        self.font_info = {}
        self.axis_values_by_font = {}

    def add_fonts(self, paths):
        """Add new fonts to the collection."""

        def normalize_path(p):
            """Normalize path from various input types."""
            try:
                import AppKit

                if isinstance(p, AppKit.NSURL):
                    return p.path()
            except ImportError:
                pass

            if isinstance(p, str) and p.startswith("file://"):
                return p.replace("file://", "")
            return str(p)

        valid_paths = [
            normalize_path(p)
            for p in paths
            if normalize_path(p).lower().endswith((".otf", ".ttf"))
        ]

        # Only add fonts not already in the list
        new_fonts = [p for p in valid_paths if p not in self.fonts]
        if not new_fonts:
            return False

        self.fonts = tuple(list(self.fonts) + new_fonts)
        self.update_font_info()
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

    def update_font_info(self):
        """Update font information for all loaded fonts."""
        self.font_info = {}
        self.axis_values_by_font = {}

        for font_path in self.fonts:
            try:
                font_info = {
                    "features": db.listOpenTypeFeatures(font_path),
                    "name": os.path.basename(font_path),
                }

                # Process variable font axes
                variableDict = db.listFontVariations(font_path)
                axes_dict = {}

                if variableDict:
                    for axis, data in variableDict.items():
                        # Get unique values in order: min, default, max
                        values = []
                        for key in ("minValue", "defaultValue", "maxValue"):
                            v = data.get(key)
                            if v is not None and v not in values:
                                # Convert to int if it's a whole number
                                values.append(
                                    int(v)
                                    if isinstance(v, (int, float)) and v == int(v)
                                    else v
                                )
                        axes_dict[axis] = values

                font_info["axes"] = axes_dict
                self.axis_values_by_font[font_path] = axes_dict
                self.font_info[font_path] = font_info

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
                f"{k}: {','.join(str(vv) for vv in v)}"
                for k, v in self.axis_values_by_font.get(font_path, {}).items()
            )
            row["axes"] = axes_str
            row["_path"] = font_path
            table_data.append(row)
        return table_data

    def update_axis_values_from_table(self, table_data):
        """Update axis values from table data."""

        def parse_value(v):
            """Parse a string value to float, int, or keep as string."""
            try:
                return float(v) if "." in v else int(v)
            except ValueError:
                return v

        for row in table_data:
            font_path = row.get("_path")
            if not font_path:
                continue

            axes_str = row.get("axes", "")
            axes_dict = {}

            for part in axes_str.split(";"):
                part = part.strip()
                if not part or ":" not in part:
                    continue

                axis, values_str = part.split(":", 1)
                values = [
                    parse_value(v.strip()) for v in values_str.split(",") if v.strip()
                ]
                axes_dict[axis.strip()] = values

            self.axis_values_by_font[font_path] = axes_dict

    def get_family_name(self):
        """Get family name from the first font."""
        return (
            os.path.splitext(os.path.basename(self.fonts[0]))[0].split("-")[0]
            if self.fonts
            else ""
        )

    def get_axis_values_for_font(self, font_path):
        """Get axis values for a specific font."""
        return self.axis_values_by_font.get(font_path, {})
