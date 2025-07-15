# Font Analysis and Character Set Processing
# This file provides backward compatibility by re-exporting from modular font analysis files

# Import from modular font analysis files
from font_utils import (
    get_ttfont,
    filteredCharset,
    normalize_font_path,
    is_valid_font_file,
    get_font_family_name,
    clear_font_cache,
    UPPER_TEMPLATE as upperTemplate,  # Keep old name for compatibility
    LOWER_TEMPLATE as lowerTemplate,  # Keep old name for compatibility
)

from character_analysis import (
    find_accented as findAccented,  # Keep old name for compatibility
    categorize,
    check_arabic_support,
    get_character_set,
)

from variable_font_utils import (
    product_dict,
    variableFont,
    pairStaticStyles,
    get_font_variations,
    get_all_font_axes,
    parse_axis_value,
    format_axis_values,
    parse_axis_values_string,
)

from font_manager import FontManager
