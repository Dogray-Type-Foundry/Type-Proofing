# Configuration - Application constants, paths, settings, and proof type definitions
# Consolidated from core_config.py and proof_config.py

import os

# =============================================================================
# Application Configuration
# =============================================================================

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Store settings file in user's home directory
SETTINGS_PATH = os.path.expanduser("~/.type-proofing-prefs.json")
WINDOW_TITLE = "Type Proofing"
APP_VERSION = "1.6.1"

# Fallback font. Adobe Blank should be in the same folder as the script
FALLBACK_FONT = os.path.abspath("AdobeBlank.otf")

# Font analysis configuration
USE_FONT_CONTAINS_CHARACTERS = True

# Seeds used for wordsiv and for regular vs italic/bold proofs
WORDSIV_SEED = 987654
DUAL_STYLE_SEED = 1029384756


# Some fsSelection values in bits format
class FsSelection:
    ITALIC = 1 << 0
    BOLD = 1 << 5
    REGULAR = 1 << 6


# =============================================================================
# Page Format Configuration
# =============================================================================

# Available page format options
PAGE_FORMAT_OPTIONS = [
    "A3Landscape",
    "A4Landscape",
    "A4SmallLandscape",
    "A5Landscape",
    "LegalLandscape",
    "LetterLandscape",
    "LetterSmallLandscape",
]

# Page format dimensions mapping (in points)
PAGE_DIMENSIONS = {
    "A3Landscape": (1190, 842),  # A3 landscape: 420mm x 297mm
    "A4Landscape": (842, 595),  # A4 landscape: 297mm x 210mm
    "A4SmallLandscape": (756, 531),  # A4 small landscape: 267mm x 187mm
    "A5Landscape": (595, 420),  # A5 landscape: 210mm x 148mm
    "LegalLandscape": (1008, 612),  # Legal landscape: 14" x 8.5"
    "LetterLandscape": (792, 612),  # Letter landscape: 11" x 8.5"
    "LetterSmallLandscape": (720, 540),  # Letter small landscape: 10" x 7.5"
}

# Default page dimensions and margins
DEFAULT_PAGE_FORMAT = "A4Landscape"
MARGIN_VERTICAL = 50
MARGIN_HORIZONTAL = 40

# Predefined axes values for variable fonts (empty by default)
AXES_VALUES = {}


# =============================================================================
# UI Layout Constants
# =============================================================================

# Main window dimensions
WINDOW_SIZE = (1000, 700)
WINDOW_MIN_SIZE = (1000, 700)

# SplitView panel sizes
SPLIT_MAIN_SIZE = 600
SPLIT_DEBUG_SIZE = 100

# Table column widths
TABLE_FONT_NAME_WIDTH = 200
TABLE_AXIS_COLUMN_WIDTH = 180

# Popover dimensions
POPOVER_PROOF_SETTINGS_SIZE = (400, 620)
POPOVER_ADD_PROOF_SIZE = (300, 100)

# Default tracking value for character set proofs
DEFAULT_CHARSET_TRACKING = 24

# Footer font settings
FOOTER_FONT_NAME = "Courier"
FOOTER_FONT_SIZE = 9
FOOTER_FEATURES_FONT_SIZE = 7


# =============================================================================
# OpenType Feature Configuration
# =============================================================================

# Default OpenType features that are typically enabled
DEFAULT_ON_FEATURES = {
    "ccmp",
    "kern",
    "calt",
    "rlig",
    "liga",
    "mark",
    "mkmk",
    "clig",
    "dist",
    "rclt",
    "rvrn",
    "curs",
    "locl",
}

HIDDEN_FEATURES = {
    "init",
    "medi",
    "med2",
    "fina",
    "fin2",
    "fin3",
    "isol",
    "curs",
    "aalt",
    "rand",
}


def filter_visible_features(feature_tags):
    """Filter out hidden OpenType features from a list of feature tags."""
    return [tag for tag in feature_tags if tag not in HIDDEN_FEATURES]


# =============================================================================
# Script Configuration (Arabic/Farsi)
# =============================================================================

# Arabic/Farsi character templates for script analysis
AR_TEMPLATE = "ءاأإآٱبتثجچحخدذرزسشصضطظعغفڤقكلمنهةوؤىيﻻ"
FA_TEMPLATE = "اآبپتثجچحخدذرزژسشصضطظعغفقکگلمنهویﻻ"
ARFA_DUAL_JOIN = "بپتثجچحخسصضطظعغفڤقكکگلمنهہھيئی"
ARFA_RIGHT_JOIN = "اأإآٱدذرزژوﻻ"

# Positional forms for Arabic/Farsi contextual analysis
POS_FORMS = ("init", "medi", "fina")


def load_arabic_texts():
    """Load Arabic text constants from script_texts module."""
    try:
        from script_texts import (
            arabicVocalization,
            arabicLatinMixed,
            arabicFarsiUrduNumbers,
        )

        return {
            "arabic_vocalization": arabicVocalization,
            "arabic_latin_mixed": arabicLatinMixed,
            "arabic_farsi_urdu_numbers": arabicFarsiUrduNumbers,
        }
    except ImportError:
        print(
            "Warning: prooftexts module not found. Arabic text constants not available."
        )
        return {
            "arabic_vocalization": "Arabic vocalization text not available",
            "arabic_latin_mixed": "Arabic-Latin mixed text not available",
            "arabic_farsi_urdu_numbers": (
                "Arabic-Farsi-Urdu numbers text not available"
            ),
        }


# Load the texts when module is imported
ARABIC_TEXTS = load_arabic_texts()

# Backward compatibility aliases
myFallbackFont = FALLBACK_FONT
useFontContainsCharacters = USE_FONT_CONTAINS_CHARACTERS
wordsivSeed = WORDSIV_SEED
dualStyleSeed = DUAL_STYLE_SEED
marginVertical = MARGIN_VERTICAL
marginHorizontal = MARGIN_HORIZONTAL
axesValues = AXES_VALUES
pageDimensions = DEFAULT_PAGE_FORMAT  # Legacy alias
arTemplate = AR_TEMPLATE
faTemplate = FA_TEMPLATE
arfaDualJoin = ARFA_DUAL_JOIN
arfaRightJoin = ARFA_RIGHT_JOIN
posForms = POS_FORMS

# Extract individual Arabic texts for backward compatibility
arabicVocalization = ARABIC_TEXTS["arabic_vocalization"]
arabicLatinMixed = ARABIC_TEXTS["arabic_latin_mixed"]
arabicFarsiUrduNumbers = ARABIC_TEXTS["arabic_farsi_urdu_numbers"]


# =============================================================================
# CENTRALIZED PROOF REGISTRY - Single Source of Truth
# =============================================================================

# Single source of truth for all proof definitions
PROOF_REGISTRY = {
    "filtered_character_set": {
        "display_name": "Filtered Character Set",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 78,  # charsetFontSize
    },
    "spacing_proof": {
        "display_name": "Spacing Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 14,  # spacingFontSize
    },
    "basic_paragraph_large": {
        "display_name": "Basic Paragraph Large",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
        "text": {
            "character_set_key": "base_letters",
            "default_paragraphs": 2,
            "hoefler_style": True,
        },
    },
    "diacritic_words_large": {
        "display_name": "Diacritic Words Large",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
        "text": {
            "character_set_key": "accented_plus",
            "default_paragraphs": 3,
            "accents": 3,
        },
    },
    "basic_paragraph_small": {
        "display_name": "Basic Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "base_letters",
            "default_paragraphs": 5,
            "hoefler_style": True,
        },
    },
    "paired_styles_paragraph_small": {
        "display_name": "Paired Styles Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "base_letters",
            "default_paragraphs": 5,
            "mixed_styles": True,
            "force_wordsiv": True,
        },
    },
    "generative_text_small": {
        "display_name": "Generative Text Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": True,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "base_letters",
            "default_paragraphs": 5,
            "force_wordsiv": True,
        },
    },
    "diacritic_words_small": {
        "display_name": "Diacritic Words Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "accented_plus",
            "default_paragraphs": 5,
            "accents": 3,
        },
    },
    "misc_paragraph_small": {
        "display_name": "Misc Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "base_letters",
            "default_paragraphs": 5,
            # Provide key so handler stays generic; resolved at runtime
            "inject_text_key": "misc_small_injects",
        },
    },
    "ar_character_set": {
        "display_name": "Ar Character Set",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 78,  # charsetFontSize
    },
    "ar_paragraph_large": {
        "display_name": "Ar Paragraph Large",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
        "text": {
            "character_set_key": "arabic",
            "default_paragraphs": 2,
            "language": "ar",
        },
    },
    "fa_paragraph_large": {
        "display_name": "Fa Paragraph Large",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
        "text": {
            "character_set_key": "farsi",
            "default_paragraphs": 2,
            "language": "fa",
        },
    },
    "ar_paragraph_small": {
        "display_name": "Ar Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "arabic",
            "default_paragraphs": 5,
            "language": "ar",
        },
    },
    "fa_paragraph_small": {
        "display_name": "Fa Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "farsi",
            "default_paragraphs": 5,
            "language": "fa",
        },
    },
    "ar_vocalization_paragraph_small": {
        "display_name": "Ar Vocalization Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "arabic",
            "default_paragraphs": 5,
            "language": "ar",
            "inject_text_key": "arabicVocalization",
        },
    },
    "ar_lat_mixed_paragraph_small": {
        "display_name": "Ar-Lat Mixed Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "arabic",
            "default_paragraphs": 5,
            "language": "ar",
            "inject_text_key": "arabicLatinMixed",
        },
    },
    "ar_numbers_small": {
        "display_name": "Ar Numbers Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
        "text": {
            "character_set_key": "arabic",
            "default_paragraphs": 5,
            "language": "ar",
            "inject_text_key": "arabicFarsiUrduNumbers",
        },
    },
}

# =============================================================================
# PROOF REGISTRY HELPER FUNCTIONS
# =============================================================================


def get_text_proof_config(proof_key):
    """Get nested text config for a proof from the registry, if present."""
    info = PROOF_REGISTRY.get(proof_key)
    return info.get("text") if info else None


def resolve_character_set_by_key(cat: dict, key: str) -> str:
    """Map a character_set_key to an actual string using the category dict."""
    if key == "base_letters":
        return (cat.get("uniLu", "") or "") + (cat.get("uniLl", "") or "")
    if key == "accented_plus":
        return cat.get("accented_plus", "") or ""
    if key == "arabic":
        return cat.get("ar", "") or cat.get("arab", "") or ""
    if key == "farsi":
        return cat.get("fa", "") or cat.get("arab", "") or ""
    return cat.get(key, "") or ""


def get_proof_display_names(include_arabic=True):
    """Get list of proof display names in default order."""
    proof_order = [
        "filtered_character_set",
        "spacing_proof",
        "basic_paragraph_large",
        "diacritic_words_large",
        "basic_paragraph_small",
        "paired_styles_paragraph_small",
        "generative_text_small",
        "diacritic_words_small",
        "misc_paragraph_small",
        "ar_character_set",
        "ar_paragraph_large",
        "fa_paragraph_large",
        "ar_paragraph_small",
        "fa_paragraph_small",
        "ar_vocalization_paragraph_small",
        "ar_lat_mixed_paragraph_small",
        "ar_numbers_small",
    ]

    result = []
    for proof_key in proof_order:
        if proof_key in PROOF_REGISTRY:
            proof_info = PROOF_REGISTRY[proof_key]
            if include_arabic or not proof_info["is_arabic"]:
                result.append(proof_info["display_name"])

    return result


def resolve_base_proof_key(proof_name: str) -> tuple[str | None, str | None]:
    """Resolve a user-visible proof option name to (base_display_name, base_key).

    Returns (display_name, key) or (None, None) if not found.
    """
    mapping = get_proof_settings_mapping()
    # Exact match
    if proof_name in mapping:
        return proof_name, mapping[proof_name]
    # Prefix match for numbered variants
    for display_name in mapping.keys():
        if proof_name.startswith(display_name):
            return display_name, mapping[display_name]
    return None, None


def get_proof_settings_mapping():
    """Get mapping from display names to proof keys."""
    return {
        proof_info["display_name"]: proof_key
        for proof_key, proof_info in PROOF_REGISTRY.items()
    }


# get_proof_popover_mapping removed; use get_proof_settings_mapping() directly


def get_proof_default_columns():
    """Get default column counts for all proofs."""
    return {
        f"{proof_key}_cols": proof_info["default_cols"]
        for proof_key, proof_info in PROOF_REGISTRY.items()
    }


def get_proof_paragraph_settings():
    """Get proof types that have paragraph settings."""
    return {
        f"{proof_key}_para": 3  # Default paragraph count
        for proof_key, proof_info in PROOF_REGISTRY.items()
        if proof_info["has_paragraphs"]
    }


def get_proof_by_display_name(display_name):
    """Get proof info by display name."""
    for proof_key, proof_info in PROOF_REGISTRY.items():
        if proof_info["display_name"] == display_name:
            return proof_info
    return None


def get_proof_by_settings_key(settings_key):
    """Get proof info by settings key (now same as proof key)."""
    return PROOF_REGISTRY.get(settings_key)


def get_proof_by_storage_key(storage_key):
    """Get proof info by storage key (now same as proof key)."""
    return PROOF_REGISTRY.get(storage_key)


def get_arabic_proof_display_names():
    """Get list of Arabic proof display names only."""
    return [
        proof_info["display_name"]
        for proof_info in PROOF_REGISTRY.values()
        if proof_info["is_arabic"]
    ]


def get_base_proof_display_names():
    """Get list of non-Arabic proof display names only."""
    return [
        proof_info["display_name"]
        for proof_info in PROOF_REGISTRY.values()
        if not proof_info["is_arabic"]
    ]


def get_proof_default_font_size(proof_key):
    """Get default font size for a proof type from the registry."""
    proof_info = PROOF_REGISTRY.get(proof_key)
    if proof_info:
        return proof_info["default_size"]
    return 8  # Fallback to small text size


def proof_supports_formatting(proof_key):
    """Check if a proof type supports text formatting (tracking, alignment)."""
    # Character Set, Spacing Proof, and Arabic Character Set don't support formatting (they handle it per category)
    return proof_key not in [
        "filtered_character_set",
        "spacing_proof",
        "ar_character_set",
    ]


def get_proof_info(proof_key):
    """Get proof info by proof key (alias for backward compatibility)."""
    return PROOF_REGISTRY.get(proof_key)


def get_display_name(proof_key):
    """Get display name for a proof key (alias for backward compatibility)."""
    proof_info = PROOF_REGISTRY.get(proof_key)
    return proof_info["display_name"] if proof_info else proof_key


def get_otf_prefix(proof_key):
    """Get OpenType feature prefix for a proof key."""
    return f"otf_{proof_key}_"


def get_default_alignment_for_proof(proof_key):
    """Get the default alignment for a proof type based on whether it's Arabic/Persian."""
    proof_info = get_proof_by_settings_key(proof_key)
    if proof_info and proof_info.get("is_arabic", False):
        return "right"
    return "left"
