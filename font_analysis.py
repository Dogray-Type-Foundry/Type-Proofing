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

    # Create expanded accented category (accented + other uppercase/lowercase not in basic templates)
    uc_lc = result_str["uniLu"] + result_str["uniLl"]
    other = ""
    for char in uc_lc:
        if (
            char not in result_str["accented"]
            and char not in lowerTemplate
            and char not in upperTemplate
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
                # Load axis values from settings
                for font_path in self.fonts:
                    axis_values = self.settings.get_font_axis_values(font_path)
                    if axis_values:
                        self.axis_values_by_font[font_path] = axis_values

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

            # Save to settings
            if self.settings:
                self.settings.set_font_axis_values(font_path, axes_dict)

    def update_axis_values_from_individual_axes_table(self, table_data, all_axes):
        """Update axis values from table data with individual axis columns."""

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

            axes_dict = {}
            for axis in all_axes:
                values_str = row.get(axis, "")
                if values_str.strip():
                    values = [
                        parse_value(v.strip())
                        for v in values_str.split(",")
                        if v.strip()
                    ]
                    if values:  # Only add if we have valid values
                        axes_dict[axis] = values

            self.axis_values_by_font[font_path] = axes_dict

            # Save to settings
            if self.settings:
                self.settings.set_font_axis_values(font_path, axes_dict)

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

    def has_arabic_support(self):
        """Check if any loaded font supports Arabic characters."""
        if not self.fonts:
            return False

        required_chars = {"ب", "ا", "ح", "د", "ر"}  # Arabic test characters

        for font_path in self.fonts:
            try:
                charset = filteredCharset(font_path)
                font_chars = set(charset)

                if required_chars.issubset(font_chars):
                    return True
            except Exception as e:
                print(f"Error checking Arabic support in {font_path}: {e}")
                continue

        return False

    def load_fonts(self, font_paths):
        """Load fonts from a list of paths."""
        if not font_paths:
            return False

        valid_paths = [
            path
            for path in font_paths
            if path.lower().endswith((".otf", ".ttf")) and os.path.exists(path)
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
        all_axes = []
        seen_axes = set()

        for font_path in self.fonts:
            # Use TTFont to get axes in original order from fvar table
            try:
                f = get_ttfont(font_path)
                if "fvar" in f:
                    for axis in f["fvar"].axes:
                        axis_tag = axis.axisTag
                        if axis_tag not in seen_axes:
                            all_axes.append(axis_tag)
                            seen_axes.add(axis_tag)
                else:
                    # Fallback for non-variable fonts
                    axes_dict = self.axis_values_by_font.get(font_path, {})
                    for axis_tag in axes_dict.keys():
                        if axis_tag not in seen_axes:
                            all_axes.append(axis_tag)
                            seen_axes.add(axis_tag)
            except Exception:
                # Fallback to existing method for this font
                axes_dict = self.axis_values_by_font.get(font_path, {})
                for axis_tag in axes_dict.keys():
                    if axis_tag not in seen_axes:
                        all_axes.append(axis_tag)
                        seen_axes.add(axis_tag)

        return all_axes

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
                if axis in axes_dict:
                    # Format axis values as comma-separated string
                    axis_values = axes_dict[axis]
                    row[axis] = ",".join(str(v) for v in axis_values)
                else:
                    row[axis] = ""  # Empty for fonts that don't have this axis

            row["_path"] = font_path
            table_data.append(row)

        return table_data, all_axes
