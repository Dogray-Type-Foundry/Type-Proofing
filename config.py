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
    "filtered_character_set": {
        "display_name": "Filtered Character Set",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 56,  # charsetFontSize
    },
    "spacing_proof": {
        "display_name": "Spacing Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # spacingFontSize
    },
    "basic_paragraph_large": {
        "display_name": "Basic Paragraph Large",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 21,  # largeTextFontSize
    },
    "diacritic_words_large": {
        "display_name": "Diacritic Words Large",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 21,  # largeTextFontSize
    },
    "basic_paragraph_small": {
        "display_name": "Basic Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "paired_styles_paragraph_small": {
        "display_name": "Paired Styles Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "generative_text_small": {
        "display_name": "Generative Text Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": True,
        "default_size": 8,  # smallTextFontSize
    },
    "diacritic_words_small": {
        "display_name": "Diacritic Words Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "misc_paragraph_small": {
        "display_name": "Misc Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "ar_character_set": {
        "display_name": "Ar Character Set",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 56,  # charsetFontSize
    },
    "ar_paragraph_large": {
        "display_name": "Ar Paragraph Large",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 21,  # largeTextFontSize
    },
    "fa_paragraph_large": {
        "display_name": "Fa Paragraph Large",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 21,  # largeTextFontSize
    },
    "ar_paragraph_small": {
        "display_name": "Ar Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "fa_paragraph_small": {
        "display_name": "Fa Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "ar_vocalization_paragraph_small": {
        "display_name": "Ar Vocalization Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "ar_lat_mixed_paragraph_small": {
        "display_name": "Ar-Lat Mixed Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
    "ar_numbers_small": {
        "display_name": "Ar Numbers Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 8,  # smallTextFontSize
    },
}

# =============================================================================
# PROOF REGISTRY HELPER FUNCTIONS
# =============================================================================


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


def get_proof_default_font_size(proof_key):
    """Get default font size for a proof type from the registry."""
    proof_info = PROOF_REGISTRY.get(proof_key)
    if proof_info:
        return proof_info["default_size"]
    return 8  # Fallback to small text size


def proof_supports_formatting(proof_key):
    """Check if a proof type supports text formatting (tracking, alignment)."""
    # Character Set and ARA Character Set don't support formatting
    return proof_key not in ["filtered_character_set", "ar_character_set"]


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

        # Generate proof order dynamically from registry (excluding show_baselines)
        proof_order = get_proof_display_names(include_arabic=True)

        return {
            "version": "1.0",
            "fonts": {"paths": [], "axis_values": {}},
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
        # Generate default order from registry if not set (excluding show_baselines)
        default_order = get_proof_display_names(include_arabic=True)

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

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.data = self._get_defaults()
        self.user_settings_file = None
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
