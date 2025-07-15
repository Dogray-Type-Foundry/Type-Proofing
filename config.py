# Configuration and Constants for Font Proofing Application
# This file provides backward compatibility by re-exporting from modular config files

# Import from modular configuration files
from app_config import (
    SCRIPT_DIR,
    SETTINGS_PATH,
    WINDOW_TITLE,
    FALLBACK_FONT as myFallbackFont,  # Keep old name for compatibility
    USE_FONT_CONTAINS_CHARACTERS as useFontContainsCharacters,  # Keep old name
    WORDSIV_SEED as wordsivSeed,  # Keep old name
    DUAL_STYLE_SEED as dualStyleSeed,  # Keep old name
    FsSelection,
    APP_VERSION,
)

from format_config import (
    PAGE_FORMAT_OPTIONS,
    DEFAULT_PAGE_FORMAT,
    MARGIN_VERTICAL as marginVertical,  # Keep old name
    MARGIN_HORIZONTAL as marginHorizontal,  # Keep old name
    AXES_VALUES as axesValues,  # Keep old name
)

from format_config import DEFAULT_PAGE_FORMAT as pageDimensions  # Legacy alias

from feature_config import (
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
    filter_visible_features,
)

from script_config import (
    AR_TEMPLATE as arTemplate,  # Keep old name
    FA_TEMPLATE as faTemplate,  # Keep old name
    ARFA_DUAL_JOIN as arfaDualJoin,  # Keep old name
    ARFA_RIGHT_JOIN as arfaRightJoin,  # Keep old name
    POS_FORMS as posForms,  # Keep old name
    ARABIC_TEXTS,
)

# Extract individual Arabic texts for backward compatibility
arabicVocalization = ARABIC_TEXTS["arabic_vocalization"]
arabicLatinMixed = ARABIC_TEXTS["arabic_latin_mixed"]
arabicFarsiUrduNumbers = ARABIC_TEXTS["arabic_farsi_urdu_numbers"]

from proof_config import (
    PROOF_REGISTRY,
    get_proof_display_names,
    get_proof_settings_mapping,
    get_proof_popover_mapping,
    get_proof_storage_mapping,
    get_proof_default_columns,
    get_proof_paragraph_settings,
    get_proof_by_display_name,
    get_proof_by_settings_key,
    get_proof_by_storage_key,
    get_arabic_proof_display_names,
    get_base_proof_display_names,
    get_proof_default_font_size,
    proof_supports_formatting,
    get_proof_info,
    get_display_name,
    get_otf_prefix,
)

from settings_config import Settings
