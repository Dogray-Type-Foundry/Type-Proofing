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

# Set your own axes values manually. Otherwise, leave empty and the script
# will automatically use the master instances.
axesValues = {}


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
        """Get default settings structure."""
        return {
            "version": "1.0",
            "fonts": {"paths": [], "axis_values": {}},
            "font_sizes": {
                "charset": charsetFontSize,
                "spacing": spacingFontSize,
                "large_text": largeTextFontSize,
                "small_text": smallTextFontSize,
            },
            "proof_options": {
                "show_baselines": False,
                "character_set_proof": False,
                "spacing_proof": False,
                "big_paragraph_proof": False,
                "big_diacritics_proof": False,
                "small_paragraph_proof": False,
                "small_paired_styles_proof": False,
                "small_wordsiv_proof": False,
                "small_diacritics_proof": False,
                "small_mixed_text_proof": False,
                "arabic_contextual_forms_proof": False,
                "big_arabic_text_proof": False,
                "big_farsi_text_proof": False,
                "small_arabic_text_proof": False,
                "small_farsi_text_proof": False,
                "arabic_vocalization_proof": False,
                "arabic_latin_mixed_proof": False,
                "arabic_numbers_proof": False,
            },
            "proof_settings": {},
            "proof_order": [
                "Show Baselines/Grid",
                "Character Set Proof",
                "Spacing Proof",
                "Big Paragraph Proof",
                "Big Diacritics Proof",
                "Small Paragraph Proof",
                "Small Paired Styles Proof",
                "Small Wordsiv Proof",
                "Small Diacritics Proof",
                "Small Mixed Text Proof",
                "Arabic Contextual Forms",
                "Big Arabic Text Proof",
                "Big Farsi Text Proof",
                "Small Arabic Text Proof",
                "Small Farsi Text Proof",
                "Arabic Vocalization Proof",
                "Arabic-Latin Mixed Proof",
                "Arabic Numbers Proof",
            ],
            "pdf_output": {
                "use_custom_location": False,
                "custom_location": "",
            },
        }

    def save(self):
        """Save settings to file."""
        try:
            # Ensure directory exists
            settings_dir = os.path.dirname(self.settings_path)
            if settings_dir and not os.path.exists(settings_dir):
                os.makedirs(settings_dir, exist_ok=True)

            if self.user_settings_file:
                # If using a user settings file, save everything to that file
                # and only save the reference in the auto-save file
                with open(self.user_settings_file, "w") as f:
                    json.dump(self.data, f, indent=2)

                # Save reference to user settings file in auto-save
                auto_save_data = {"user_settings_file": self.user_settings_file}
                with open(self.settings_path, "w") as f:
                    json.dump(auto_save_data, f, indent=2)
            else:
                # Save only non-default values to auto-save file
                defaults = self._get_defaults()
                non_default_data = self._get_non_default_values(self.data, defaults)

                with open(self.settings_path, "w") as f:
                    json.dump(non_default_data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
            raise

    def _get_non_default_values(self, current_data, defaults):
        """Get only the values that differ from defaults."""
        non_defaults = {}

        for key, value in current_data.items():
            if key not in defaults:
                non_defaults[key] = value
            elif isinstance(value, dict) and isinstance(defaults[key], dict):
                nested_non_defaults = self._get_non_default_values(value, defaults[key])
                if nested_non_defaults:
                    non_defaults[key] = nested_non_defaults
            elif value != defaults[key]:
                non_defaults[key] = value

        return non_defaults

    def load_user_settings_file(self, file_path):
        """Load settings from a user-specified file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Settings file not found: {file_path}")

        try:
            new_data = self._load_settings_file(file_path, raise_on_error=True)
            self.data = new_data
            self.user_settings_file = file_path
            self.save()  # Save the reference to the user settings file
            return True
        except Exception as e:
            print(f"Error loading user settings file: {e}")
            return False

    def clear_user_settings_file(self):
        """Clear the user settings file and revert to auto-save mode."""
        self.user_settings_file = None
        # The current data will be saved as non-default values in auto-save mode
        self.save()

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.data = self._get_defaults()
        self.user_settings_file = None  # Clear user settings file reference
        self.save()

    def get(self, key, default=None):
        """Get a setting value."""
        return self.data.get(key, default)

    def set(self, key, value):
        """Set a setting value."""
        self.data[key] = value

    def update(self, updates):
        """Update multiple settings at once."""
        self.data.update(updates)

    def get_font_size(self, size_type):
        """Get font size by type."""
        size_map = {
            "charset": "charset",
            "spacing": "spacing",
            "large": "large_text",
            "small": "small_text",
        }
        key = size_map.get(size_type, size_type)
        return self.data.get("font_sizes", {}).get(
            key,
            {
                "charset": charsetFontSize,
                "spacing": spacingFontSize,
                "large_text": largeTextFontSize,
                "small_text": smallTextFontSize,
            }.get(key, 10),
        )

    def set_font_size(self, size_type, value):
        """Set font size by type."""
        size_map = {
            "charset": "charset",
            "spacing": "spacing",
            "large": "large_text",
            "small": "small_text",
        }
        key = size_map.get(size_type, size_type)
        if "font_sizes" not in self.data:
            self.data["font_sizes"] = {}
        self.data["font_sizes"][key] = value

    def get_proof_option(self, proof_name):
        """Get proof option by name."""
        # Convert proof names to standardized format
        option_map = {
            "showBaselines": "show_baselines",
            "Character_Set_Proof": "character_set_proof",
            "Spacing_Proof": "spacing_proof",
            "Big_Paragraph_Proof": "big_paragraph_proof",
            "Big_Diacritics_Proof": "big_diacritics_proof",
            "Small_Paragraph_Proof": "small_paragraph_proof",
            "Small_Paired_Styles_Proof": "small_paired_styles_proof",
            "Small_Wordsiv_Proof": "small_wordsiv_proof",
            "Small_Diacritics_Proof": "small_diacritics_proof",
            "Small_Mixed_Text_Proof": "small_mixed_text_proof",
            "Arabic_Contextual_Forms_Proof": "arabic_contextual_forms_proof",
            "Big_Arabic_Text_Proof": "big_arabic_text_proof",
            "Big_Farsi_Text_Proof": "big_farsi_text_proof",
            "Small_Arabic_Text_Proof": "small_arabic_text_proof",
            "Small_Farsi_Text_Proof": "small_farsi_text_proof",
            "Arabic_Vocalization_Proof": "arabic_vocalization_proof",
            "Arabic_Latin_Mixed_Proof": "arabic_latin_mixed_proof",
            "Arabic_Numbers_Proof": "arabic_numbers_proof",
        }
        key = option_map.get(proof_name, proof_name.lower())
        return self.data.get("proof_options", {}).get(key, False)

    def set_proof_option(self, proof_name, enabled):
        """Set proof option by name."""
        option_map = {
            "showBaselines": "show_baselines",
            "Character_Set_Proof": "character_set_proof",
            "Spacing_Proof": "spacing_proof", 
            "Big_Paragraph_Proof": "big_paragraph_proof",
            "Big_Diacritics_Proof": "big_diacritics_proof",
            "Small_Paragraph_Proof": "small_paragraph_proof",
            "Small_Paired_Styles_Proof": "small_paired_styles_proof",
            "Small_Wordsiv_Proof": "small_wordsiv_proof",
            "Small_Diacritics_Proof": "small_diacritics_proof",
            "Small_Mixed_Text_Proof": "small_mixed_text_proof",
            "Arabic_Contextual_Forms_Proof": "arabic_contextual_forms_proof",
            "Big_Arabic_Text_Proof": "big_arabic_text_proof",
            "Big_Farsi_Text_Proof": "big_farsi_text_proof",
            "Small_Arabic_Text_Proof": "small_arabic_text_proof",
            "Small_Farsi_Text_Proof": "small_farsi_text_proof",
            "Arabic_Vocalization_Proof": "arabic_vocalization_proof",
            "Arabic_Latin_Mixed_Proof": "arabic_latin_mixed_proof",
            "Arabic_Numbers_Proof": "arabic_numbers_proof",
        }
        key = option_map.get(proof_name, proof_name.lower())
        if "proof_options" not in self.data:
            self.data["proof_options"] = {}
        self.data["proof_options"][key] = enabled

    def get_fonts(self):
        """Get saved font paths."""
        return self.data.get("fonts", {}).get("paths", [])

    def set_fonts(self, font_paths):
        """Set font paths."""
        if "fonts" not in self.data:
            self.data["fonts"] = {"paths": [], "axis_values": {}}
        self.data["fonts"]["paths"] = font_paths

    def get_font_axis_values(self, font_path):
        """Get axis values for a specific font."""
        return self.data.get("fonts", {}).get("axis_values", {}).get(font_path, {})

    def set_font_axis_values(self, font_path, axis_values):
        """Set axis values for a specific font."""
        if "fonts" not in self.data:
            self.data["fonts"] = {"paths": [], "axis_values": {}}
        if "axis_values" not in self.data["fonts"]:
            self.data["fonts"]["axis_values"] = {}
        self.data["fonts"]["axis_values"][font_path] = axis_values

    def get_proof_settings(self):
        """Get all proof settings."""
        return self.data.get("proof_settings", {})

    def set_proof_settings(self, proof_settings):
        """Set all proof settings."""
        self.data["proof_settings"] = proof_settings

    def get_pdf_output_use_custom(self):
        """Get whether to use custom PDF output location."""
        return self.data.get("pdf_output", {}).get("use_custom_location", False)

    def set_pdf_output_use_custom(self, use_custom):
        """Set whether to use custom PDF output location."""
        if "pdf_output" not in self.data:
            self.data["pdf_output"] = {
                "use_custom_location": False,
                "custom_location": "",
            }
        self.data["pdf_output"]["use_custom_location"] = use_custom

    def get_pdf_output_custom_location(self):
        """Get custom PDF output location."""
        return self.data.get("pdf_output", {}).get("custom_location", "")

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
        return self.data.get(
            "proof_order",
            [
                "Show Baselines/Grid",
                "Character Set Proof",
                "Spacing Proof",
                "Big Paragraph Proof",
                "Big Diacritics Proof",
                "Small Paragraph Proof",
                "Small Paired Styles Proof",
                "Small Wordsiv Proof",
                "Small Diacritics Proof",
                "Small Mixed Text Proof",
                "Arabic Contextual Forms",
                "Big Arabic Text Proof",
                "Big Farsi Text Proof",
                "Small Arabic Text Proof",
                "Small Farsi Text Proof",
                "Arabic Vocalization Proof",
                "Arabic-Latin Mixed Proof",
                "Arabic Numbers Proof",
            ],
        )

    def set_proof_order(self, proof_order):
        """Set the proof order."""
        self.data["proof_order"] = proof_order[:]  # Create a copy


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
    }
}

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
    }
}
"""
