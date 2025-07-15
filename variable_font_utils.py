# Variable Font Utilities - Variable font axis management and style pairing

from itertools import product
import drawBot as db
from font_utils import get_ttfont
from core_config import FsSelection, AXES_VALUES


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


def get_font_variations(font_path):
    """Get variable font variations for a font."""
    return db.listFontVariations(font_path)


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
