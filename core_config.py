# Core Configuration - Application constants, paths, and fundamental settings
# Consolidated from app_config.py, format_config.py, feature_config.py, and script_config.py

import os

# =============================================================================
# Application Configuration
# =============================================================================

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Store settings file in user's home directory
SETTINGS_PATH = os.path.expanduser("~/.type-proofing-prefs.json")
WINDOW_TITLE = "Type Proofing"
APP_VERSION = "1.2.0"

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

# Default page dimensions and margins
DEFAULT_PAGE_FORMAT = "A4Landscape"
MARGIN_VERTICAL = 50
MARGIN_HORIZONTAL = 40

# Predefined axes values for variable fonts (empty by default)
AXES_VALUES = {}


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
AR_TEMPLATE = "ابجدهوزحطيكلمنسعفصقرشتثخذضظغء"
FA_TEMPLATE = "یهونملگکقفغعظطضصشسژزرذدخحچجثتپباء"
ARFA_DUAL_JOIN = "بتثپنقفڤسشصضطظكلهةمعغحخجچيئىکگی"
ARFA_RIGHT_JOIN = "اأإآٱرزدذوؤژ"

# Positional forms for Arabic/Farsi contextual analysis
POS_FORMS = ("init", "medi", "fina")


def load_arabic_texts():
    """Load Arabic text constants from prooftexts module."""
    try:
        from importlib import reload
        import prooftexts

        reload(prooftexts)

        return {
            "arabic_vocalization": prooftexts.arabicVocalization,
            "arabic_latin_mixed": prooftexts.arabicLatinMixed,
            "arabic_farsi_urdu_numbers": prooftexts.arabicFarsiUrduNumbers,
        }
    except ImportError:
        print(
            "Warning: prooftexts module not found. Arabic text constants not available."
        )
        return {
            "arabic_vocalization": "Arabic vocalization text not available",
            "arabic_latin_mixed": "Arabic-Latin mixed text not available",
            "arabic_farsi_urdu_numbers": "Arabic-Farsi-Urdu numbers text not available",
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
