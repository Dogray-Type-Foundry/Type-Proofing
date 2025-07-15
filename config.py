# Configuration and Constants for Font Proofing Application
# This file provides backward compatibility by re-exporting from consolidated config files

# Import from consolidated configuration files
from core_config import (
    # Application constants
    SCRIPT_DIR,
    SETTINGS_PATH,
    WINDOW_TITLE,
    APP_VERSION,
    FALLBACK_FONT,
    USE_FONT_CONTAINS_CHARACTERS,
    WORDSIV_SEED,
    DUAL_STYLE_SEED,
    FsSelection,
    # Page format settings
    PAGE_FORMAT_OPTIONS,
    DEFAULT_PAGE_FORMAT,
    MARGIN_VERTICAL,
    MARGIN_HORIZONTAL,
    AXES_VALUES,
    # OpenType features
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
    filter_visible_features,
    # Script configuration
    AR_TEMPLATE,
    FA_TEMPLATE,
    ARFA_DUAL_JOIN,
    ARFA_RIGHT_JOIN,
    POS_FORMS,
    ARABIC_TEXTS,
    # Backward compatibility aliases
    myFallbackFont,
    useFontContainsCharacters,
    wordsivSeed,
    dualStyleSeed,
    marginVertical,
    marginHorizontal,
    axesValues,
    pageDimensions,
    arTemplate,
    faTemplate,
    arfaDualJoin,
    arfaRightJoin,
    posForms,
    arabicVocalization,
    arabicLatinMixed,
    arabicFarsiUrduNumbers,
)

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

from ui_config import Settings
