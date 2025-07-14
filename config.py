# Configuration and Constants for Font Proofing Application

import json
import os
from pathlib import Path

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Store settings file in user's home directory
SETTINGS_PATH = os.path.expanduser("~/.type-proofing-prefs.json")
WINDOW_TITLE = "Type Proofing"

# Arabic/Farsi character templates for script analysis
arTemplate = "ابجدهوزحطيكلمنسعفصقرشتثخذضظغء"
faTemplate = "یهونملگکقفغعظطضصشسژزرذدخحچجثتپباء"
arfaDualJoin = "بتثپنقفڤسشصضطظكلهةمعغحخجچيئىکگی"
arfaRightJoin = "اأإآٱرزدذوؤژ"

# Positional forms for Arabic/Farsi contextual analysis
posForms = ("init", "medi", "fina")

# Import Arabic text constants
try:
    from importlib import reload
    import prooftexts

    reload(prooftexts)
    # Make Arabic texts available globally
    arabicVocalization = prooftexts.arabicVocalization
    arabicLatinMixed = prooftexts.arabicLatinMixed
    arabicFarsiUrduNumbers = prooftexts.arabicFarsiUrduNumbers
except ImportError:
    print("Warning: prooftexts module not found. Arabic text constants not available.")
    arabicVocalization = "Arabic vocalization text not available"
    arabicLatinMixed = "Arabic-Latin mixed text not available"
    arabicFarsiUrduNumbers = "Arabic-Farsi-Urdu numbers text not available"

# Some constants related to page and layout
# Page dimensions and margin
pageDimensions = "A4Landscape"
marginVertical = 50
marginHorizontal = 40

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

# Font sizes
charsetFontSize = 56
spacingFontSize = 10
largeTextFontSize = 21
smallTextFontSize = 8
fullCharSetSize = 48

# Seeds used for wordsiv and for regular vs italic/bold proofs
wordsivSeed = 987654
dualStyleSeed = 1029384756

# Fallback font. Adobe Blank should be in the same folder as the script
myFallbackFont = os.path.abspath("AdobeBlank.otf")

useFontContainsCharacters = True

# Predefined axes values for variable fonts (empty by default)
# This can be populated with specific axis value combinations if needed
axesValues = {}

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
}

# =============================================================================
# CENTRALIZED PROOF REGISTRY - Single Source of Truth
# =============================================================================

# Single source of truth for all proof definitions
PROOF_REGISTRY = {
    "character_set_proof": {
        "display_name": "Character Set Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
    },
    "spacing_proof": {
        "display_name": "Spacing Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
    },
    "big_paragraph_proof": {
        "display_name": "Big Paragraph Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
    },
    "big_diacritics_proof": {
        "display_name": "Big Diacritics Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
    },
    "small_paragraph_proof": {
        "display_name": "Small Paragraph Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "small_paired_styles_proof": {
        "display_name": "Small Paired Styles Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "small_wordsiv_proof": {
        "display_name": "Small Wordsiv Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": True,
    },
    "small_diacritics_proof": {
        "display_name": "Small Diacritics Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "small_mixed_text_proof": {
        "display_name": "Small Mixed Text Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "arabic_contextual_forms_proof": {
        "display_name": "Arabic Contextual Forms",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "big_arabic_text_proof": {
        "display_name": "Big Arabic Text Proof",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
    },
    "big_farsi_text_proof": {
        "display_name": "Big Farsi Text Proof",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
    },
    "small_arabic_text_proof": {
        "display_name": "Small Arabic Text Proof",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "small_farsi_text_proof": {
        "display_name": "Small Farsi Text Proof",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "arabic_vocalization_proof": {
        "display_name": "Arabic Vocalization Proof",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "arabic_latin_mixed_proof": {
        "display_name": "Arabic-Latin Mixed Proof",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
    "arabic_numbers_proof": {
        "display_name": "Arabic Numbers Proof",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
    },
}

# =============================================================================
# PROOF REGISTRY HELPER FUNCTIONS
# =============================================================================


def get_proof_display_names(include_arabic=True):
    """Get list of proof display names in default order."""
    proof_order = [
        "character_set_proof",
        "spacing_proof",
        "big_paragraph_proof",
        "big_diacritics_proof",
        "small_paragraph_proof",
        "small_paired_styles_proof",
        "small_wordsiv_proof",
        "small_diacritics_proof",
        "small_mixed_text_proof",
        "arabic_contextual_forms_proof",
        "big_arabic_text_proof",
        "big_farsi_text_proof",
        "small_arabic_text_proof",
        "small_farsi_text_proof",
        "arabic_vocalization_proof",
        "arabic_latin_mixed_proof",
        "arabic_numbers_proof",
    ]

    result = []
    for proof_key in proof_order:
        if proof_key in PROOF_REGISTRY:
            proof_info = PROOF_REGISTRY[proof_key]
            if include_arabic or not proof_info["is_arabic"]:
                result.append(proof_info["display_name"])

    return result


def get_proof_settings_mapping():
    """Get mapping from display names to proof keys."""
    return {
        proof_info["display_name"]: proof_key
        for proof_key, proof_info in PROOF_REGISTRY.items()
    }


def get_proof_popover_mapping():
    """Get mapping from display names to proof keys (for popover compatibility)."""
    return get_proof_settings_mapping()


def get_proof_storage_mapping():
    """Get mapping from proof keys to storage keys (now the same)."""
    return {proof_key: proof_key for proof_key in PROOF_REGISTRY.keys()}


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


def proof_supports_formatting(proof_key):
    """Check if a proof type supports text formatting (tracking, alignment)."""
    # Character Set and Arabic Contextual Forms don't support formatting
    return proof_key not in ["character_set_proof", "arabic_contextual_forms_proof"]


# =============================================================================
# END PROOF REGISTRY
# =============================================================================


# Some fsSelection values in bits format
class FsSelection:
    ITALIC = 1 << 0
    BOLD = 1 << 5
    REGULAR = 1 << 6


class Settings:
    """Unified settings management for the proof generator."""

    def __init__(self, settings_path=SETTINGS_PATH):
        self.settings_path = settings_path
        self.user_settings_file = None  # Path to user-loaded settings file
        self.data = self.load()

    def load(self):
        """Load settings from file."""
        # First, try to load from auto-save file to check for user settings file
        auto_save_data = self._load_auto_save_file()
        user_settings_path = auto_save_data.get("user_settings_file")

        if user_settings_path and os.path.exists(user_settings_path):
            # Load from user settings file
            self.user_settings_file = user_settings_path
            return self._load_settings_file(user_settings_path)
        else:
            # Load from auto-save file
            return auto_save_data

    def _load_auto_save_file(self):
        """Load settings from the auto-save file."""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    content = f.read().strip()
                    if not content:
                        return self._get_defaults()

                    data = json.loads(content)

                    # If this is just a reference to a user settings file, return defaults
                    if "user_settings_file" in data and len(data.keys()) == 1:
                        return self._get_defaults()

                    # Validate that fonts still exist
                    if self._validate_fonts(data):
                        return data
                    else:
                        print(
                            "Some saved fonts no longer exist. Resetting to defaults."
                        )
                        return self._get_defaults()
            except Exception as e:
                print(f"Error loading auto-save settings: {e}")
                return self._get_defaults()
        return self._get_defaults()

    def _load_settings_file(self, file_path, raise_on_error=False):
        """Load settings from a specific file."""
        try:
            with open(file_path, "r") as f:
                content = f.read().strip()
                if not content:
                    error_msg = f"Settings file {file_path} is empty."
                    if raise_on_error:
                        raise ValueError(error_msg)
                    print(f"{error_msg} Using defaults.")
                    return self._get_defaults()

                data = json.loads(content)

                # Merge with defaults to ensure all required keys exist
                defaults = self._get_defaults()
                merged_data = self._merge_settings(defaults, data)

                # Validate that fonts still exist
                if self._validate_fonts(merged_data):
                    return merged_data
                else:
                    print(
                        f"Some fonts in {file_path} no longer exist. Keeping paths for user reference."
                    )
                    # For user-loaded settings, keep the font paths even if they don't exist
                    # This allows users to load settings on different systems
                    return merged_data
        except Exception as e:
            print(f"Error loading settings file {file_path}: {e}")
            if raise_on_error:
                raise
            return self._get_defaults()

    def _merge_settings(self, defaults, user_data):
        """Merge user settings with defaults, ensuring all required keys exist."""
        merged = defaults.copy()

        # Recursively merge nested dictionaries
        for key, value in user_data.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = self._merge_dict(merged[key], value)
            else:
                merged[key] = value

        return merged

    def _merge_dict(self, default_dict, user_dict):
        """Recursively merge dictionaries."""
        result = default_dict.copy()
        for key, value in user_dict.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_dict(result[key], value)
            else:
                result[key] = value
        return result

    def _validate_fonts(self, data):
        """Check if saved fonts still exist at their paths."""
        font_paths = data.get("fonts", {}).get("paths", [])
        if not font_paths:
            return True  # No fonts saved, that's fine

        # For testing purposes or when paths don't start with actual filesystem paths,
        # we'll be more lenient. Only validate if paths look like real file paths.
        real_paths = [
            path for path in font_paths if path.startswith("/") or path.startswith("C:")
        ]
        if not real_paths:
            return True  # No real paths to validate

        # Check if all real font paths still exist
        existing_fonts = [path for path in real_paths if os.path.exists(path)]
        return len(existing_fonts) == len(real_paths)

    def _get_defaults(self):
        """Get default settings structure using the centralized proof registry."""
        # Generate proof options dynamically from registry
        proof_options = {}
        for proof_key in PROOF_REGISTRY.keys():
            proof_options[proof_key] = False

        # Generate proof order dynamically from registry
        proof_order = ["Show Baselines/Grid"]  # Special case
        proof_order.extend(get_proof_display_names(include_arabic=True))

        return {
            "version": "1.0",
            "fonts": {"paths": [], "axis_values": {}},
            "font_sizes": {
                "charset": charsetFontSize,
                "spacing": spacingFontSize,
                "large_text": largeTextFontSize,
                "small_text": smallTextFontSize,
            },
            "proof_options": {"show_baselines": False, **proof_options},
            "proof_settings": {},
            "proof_order": proof_order,
            "pdf_output": {
                "use_custom_location": False,
                "custom_location": "",
            },
            "page_format": "A4Landscape",
        }

    def set_pdf_output_custom_location(self, location):
        """Set custom PDF output location."""
        if "pdf_output" not in self.data:
            self.data["pdf_output"] = {
                "use_custom_location": False,
                "custom_location": "",
            }
        self.data["pdf_output"]["custom_location"] = location

    def get_proof_order(self):
        """Get the current proof order."""
        # Generate default order from registry if not set
        default_order = ["Show Baselines/Grid"]
        default_order.extend(get_proof_display_names(include_arabic=True))

        return self.data.get("proof_order", default_order)

    def set_proof_order(self, proof_order):
        """Set the proof order."""
        self.data["proof_order"] = proof_order[:]  # Create a copy

    def get_page_format(self):
        """Get the current page format."""
        return self.data.get("page_format", "A4Landscape")

    def set_page_format(self, page_format):
        """Set the page format."""
        self.data["page_format"] = page_format

    def get_fonts(self):
        """Get the list of font paths."""
        return self.data.get("fonts", {}).get("paths", [])

    def set_fonts(self, font_paths):
        """Set the list of font paths."""
        if "fonts" not in self.data:
            self.data["fonts"] = {"paths": [], "axis_values": {}}
        self.data["fonts"]["paths"] = list(font_paths)
        self.save()

    def get_font_axis_values(self, font_path):
        """Get axis values for a specific font."""
        return self.data.get("fonts", {}).get("axis_values", {}).get(font_path, {})

    def set_font_axis_values(self, font_path, axis_values):
        """Set axis values for a specific font."""
        if "fonts" not in self.data:
            self.data["fonts"] = {"paths": [], "axis_values": {}}
        if "axis_values" not in self.data["fonts"]:
            self.data["fonts"]["axis_values"] = {}
        self.data["fonts"]["axis_values"][font_path] = dict(axis_values)
        self.save()

    def get_proof_option(self, option_key):
        """Get a proof option value."""
        return self.data.get("proof_options", {}).get(option_key, False)

    def set_proof_option(self, option_key, value):
        """Set a proof option value."""
        if "proof_options" not in self.data:
            self.data["proof_options"] = {}
        self.data["proof_options"][option_key] = value
        self.save()

    def get_proof_settings(self):
        """Get the proof settings dictionary."""
        return self.data.get("proof_settings", {})

    def set_proof_settings(self, proof_settings):
        """Set the proof settings dictionary."""
        if "proof_settings" not in self.data:
            self.data["proof_settings"] = {}
        self.data["proof_settings"] = dict(proof_settings)
        self.save()

    def save(self):
        """Save current settings to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)

            # If we're using a user settings file, save to that instead
            save_path = (
                self.user_settings_file
                if self.user_settings_file
                else self.settings_path
            )

            with open(save_path, "w") as f:
                json.dump(self.data, f, indent=2)

            # If we're using a user settings file, also update the auto-save file
            # to remember which user file was loaded
            if self.user_settings_file and save_path != self.settings_path:
                auto_save_data = {"user_settings_file": self.user_settings_file}
                with open(self.settings_path, "w") as f:
                    json.dump(auto_save_data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")


# =============================================================================
# SETTINGS DOCUMENTATION
# =============================================================================

"""
Complete reference for all settings that can be stored in settings files:

SETTINGS FILE STRUCTURE:
{
    "version": "1.0",
    "user_settings_file": "/path/to/user/settings.json",  // Only in auto-save file
    "fonts": {
        "paths": ["/path/to/font1.otf", "/path/to/font2.ttf"],
        "axis_values": {
            "/path/to/font1.otf": {
                "wght": 400,
                "wdth": 100,
                "slnt": 0
            }
        }
    },
    "font_sizes": {
        "charset": 56,      // Font size for character set proofs
        "spacing": 10,      // Font size for spacing proofs
        "large_text": 21,   // Font size for large text proofs
        "small_text": 8     // Font size for small text proofs
    },
    "proof_options": {
        "show_baselines": true,                    // Show baseline/grid overlays
        "character_set_proof": true,               // Generate character set proof
        "spacing_proof": true,                     // Generate spacing proof
        "big_paragraph_proof": true,               // Generate large paragraph proof
        "big_diacritics_proof": false,             // Generate large diacritics proof
        "small_paragraph_proof": true,             // Generate small paragraph proof
        "small_paired_styles_proof": false,        // Generate small paired styles proof
        "small_wordsiv_proof": false,              // Generate small wordsiv proof
        "small_diacritics_proof": false,           // Generate small diacritics proof
        "small_mixed_text_proof": false,           // Generate small mixed text proof
        "arabic_contextual_forms_proof": false,    // Generate Arabic contextual forms
        "big_arabic_text_proof": false,            // Generate large Arabic text proof
        "big_farsi_text_proof": false,             // Generate large Farsi text proof
        "small_arabic_text_proof": false,          // Generate small Arabic text proof
        "small_farsi_text_proof": false,           // Generate small Farsi text proof
        "arabic_vocalization_proof": false,        // Generate Arabic vocalization proof
        "arabic_latin_mixed_proof": false,         // Generate Arabic-Latin mixed proof
        "arabic_numbers_proof": false              // Generate Arabic numbers proof
    },
    "proof_settings": {
        // Column settings for each proof type
        "BigParagraphProof_cols": 1,
        "BigDiacriticsProof_cols": 1,
        "SmallParagraphProof_cols": 2,
        "SmallPairedStylesProof_cols": 2,
        "SmallWordsivProof_cols": 2,
        "SmallDiacriticsProof_cols": 2,
        "SmallMixedTextProof_cols": 2,
        "ArabicContextualFormsProof_cols": 2,
        "BigArabicTextProof_cols": 1,
        "BigFarsiTextProof_cols": 1,
        "SmallArabicTextProof_cols": 2,
        "SmallFarsiTextProof_cols": 2,
        "ArabicVocalizationProof_cols": 2,
        "ArabicLatinMixedProof_cols": 2,
        "ArabicNumbersProof_cols": 2,
        
        // Paragraph settings (currently only for SmallWordsivProof)
        "SmallWordsivProof_para": 3,
        
        // OpenType feature settings per proof type
        // Format: "otf_{ProofType}_{feature_tag}": boolean
        "otf_BigParagraphProof_kern": true,
        "otf_BigParagraphProof_liga": true,
        "otf_BigParagraphProof_calt": true,
        "otf_SmallParagraphProof_kern": true,
        "otf_SmallParagraphProof_liga": false,
        // ... (many more combinations possible)
    },
    "pdf_output": {
        "use_custom_location": false,              // Whether to use custom PDF output location  
        "custom_location": ""                      // Custom directory for PDF output (empty = use font folder)
    },
    "page_format": "A4Landscape"                   // Page format for generated proofs
}
}

PAGE FORMAT OPTIONS:
Available page format values for the "page_format" setting:
- A3Landscape: A3 paper in landscape orientation
- A4Landscape: A4 paper in landscape orientation (default)
- A4SmallLandscape: A4 small paper in landscape orientation
- A5Landscape: A5 paper in landscape orientation
- LegalLandscape: Legal paper in landscape orientation
- LetterLandscape: Letter paper in landscape orientation
- LetterSmallLandscape: Letter small paper in landscape orientation

The page format setting controls the paper size and orientation for generated proof PDFs.
This setting is saved automatically when changed through the GUI.

OPENTYPE FEATURE TAGS REFERENCE:
Common OpenType features that can be enabled/disabled per proof type:

Typography Features:
- kern: Kerning
- liga: Standard ligatures
- clig: Contextual ligatures
- dlig: Discretionary ligatures
- rlig: Required ligatures
- calt: Contextual alternates
- salt: Stylistic alternates
- hist: Historical forms
- titl: Titling forms
- swsh: Swash forms

Case Features:
- smcp: Small capitals
- c2sc: Capitals to small capitals
- pcap: Petite capitals
- c2pc: Capitals to petite capitals
- unic: Unicase
- cpsp: Capital spacing

Number Features:
- lnum: Lining figures
- onum: Oldstyle figures
- pnum: Proportional figures
- tnum: Tabular figures
- frac: Fractions
- afrc: Alternative fractions
- ordn: Ordinals
- sups: Superscript
- subs: Subscript
- sinf: Scientific inferiors

Position Features:
- sups: Superscript
- subs: Subscript
- ordn: Ordinals
- dnom: Denominators
- numr: Numerators

Language Features:
- locl: Localized forms
- ccmp: Glyph composition/decomposition
- mark: Mark positioning
- mkmk: Mark-to-mark positioning
- curs: Cursive positioning

Arabic/Complex Script Features:
- init: Initial forms
- medi: Medial forms
- fina: Final forms
- isol: Isolated forms
- rlig: Required ligatures
- calt: Contextual alternates
- rclt: Required contextual alternates
- curs: Cursive positioning
- kern: Kerning
- mark: Mark positioning
- mkmk: Mark-to-mark positioning

Stylistic Features:
- ss01-ss20: Stylistic sets 1-20
- cv01-cv99: Character variants 1-99
- aalt: Access all alternates

Technical Features:
- ccmp: Glyph composition/decomposition (always recommended)
- rvrn: Required variation alternates (for variable fonts)
- rclt: Required contextual alternates
- curs: Cursive positioning
- dist: Distances
- abvf: Above-base forms
- blwf: Below-base forms
- half: Half forms
- pres: Pre-base substitutions
- abvs: Above-base substitutions
- blws: Below-base substitutions
- psts: Post-base substitutions
- haln: Halant forms
- rphf: Reph forms
- pref: Pre-base forms
- rkrf: Rakar forms
- abvm: Above-base mark positioning
- blwm: Below-base mark positioning

USAGE NOTES:
1. The auto-save file (~/.type-proofing-prefs.json) only stores non-default values
2. User settings files can contain complete settings structures
3. When a user settings file is loaded, only its path is stored in the auto-save file
4. Font axis values are stored per font path
5. OpenType features are stored per proof type for maximum flexibility
6. Column and paragraph settings allow customization of proof layout
7. All boolean settings default to their defined values in proof_options
8. Font sizes have sensible defaults but can be customized per proof type

EXAMPLE USER SETTINGS FILE:
{
    "version": "1.0",
    "fonts": {
        "paths": ["/Users/designer/fonts/MyFont-Regular.otf"],
        "axis_values": {
            "/Users/designer/fonts/MyFont-Regular.otf": {
                "wght": 500,
                "wdth": 95
            }
        }
    },
    "proof_options": {
        "character_set_proof": true,
        "spacing_proof": true,
        "big_paragraph_proof": true,
        "small_paragraph_proof": true,
        "arabic_contextual_forms_proof": true
    },
    "proof_settings": {
        "BigParagraphProof_cols": 1,
        "SmallParagraphProof_cols": 2,
        "otf_BigParagraphProof_kern": true,
        "otf_BigParagraphProof_liga": true,
        "otf_BigParagraphProof_calt": true,
        "otf_SmallParagraphProof_kern": true,
        "otf_SmallParagraphProof_liga": false,
        "otf_ArabicContextualFormsProof_calt": true,
        "otf_ArabicContextualFormsProof_rlig": true
    },
    "pdf_output": {
        "use_custom_location": false,              // Whether to use custom PDF output location
        "custom_location": ""                      // Custom directory for PDF output
    },
    "page_format": "A4Landscape"                   // Page format for generated proofs
}
}
"""
