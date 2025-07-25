# Settings Manager - Centralized settings handling for proof generation

import json
import os
from ui_config import Settings
from core_config import DEFAULT_ON_FEATURES, HIDDEN_FEATURES
from proof_config import (
    get_proof_default_font_size,
    get_proof_by_settings_key,
    get_proof_by_storage_key,
    proof_supports_formatting,
    get_proof_settings_mapping,
)
from proof_handlers import create_unique_proof_key
from utils import safe_json_load, safe_json_save, log_error


def get_default_alignment_for_proof(proof_key):
    """Get the default alignment for a proof type based on whether it's Arabic/Persian."""
    proof_info = get_proof_by_settings_key(proof_key)
    if proof_info and proof_info.get("is_arabic", False):
        return "right"
    return "left"


class ProofSettingsManager:
    """Manages all proof-specific settings including OpenType features, font sizes, etc."""

    def __init__(self, settings, font_manager):
        self.settings = settings
        self.font_manager = font_manager
        self.proof_settings = {}
        self.initialize_proof_settings()

    def initialize_proof_settings(self):
        """Initialize proof-specific settings storage with defaults."""
        # Load existing proof settings from the settings file
        saved_proof_settings = self.settings.get_proof_settings()
        self.proof_settings = (
            saved_proof_settings.copy() if saved_proof_settings else {}
        )

        # Get proof types with settings keys from registry
        settings_mapping = get_proof_settings_mapping()
        proof_types_with_otf = [(key, name) for name, key in settings_mapping.items()]

        # Initialize default values for all proof types
        for proof_key, _ in proof_types_with_otf:
            self._initialize_proof_type_defaults(proof_key)

    def _initialize_proof_type_defaults(self, proof_key):
        """Initialize default settings for a specific proof type."""
        # Get proof info from registry
        proof_info = get_proof_by_settings_key(proof_key)
        if proof_info is None:
            return  # Skip if not found in registry

        # Column settings - use default from registry
        cols_key = f"{proof_key}_cols"
        # Character Set and ARA Character Set don't use columns
        if proof_key not in ["filtered_character_set", "ar_character_set"]:
            default_cols = proof_info["default_cols"]
            if cols_key not in self.proof_settings:
                self.proof_settings[cols_key] = default_cols

        # Font size settings for all proofs
        font_size_key = f"{proof_key}_fontSize"
        # Set default font size based on proof type using registry
        default_font_size = get_proof_default_font_size(proof_key)

        if font_size_key not in self.proof_settings:
            self.proof_settings[font_size_key] = default_font_size

        # Paragraph settings (only for proofs that have paragraphs)
        if proof_info["has_paragraphs"]:
            para_key = f"{proof_key}_para"
            if para_key not in self.proof_settings:
                self.proof_settings[para_key] = 5

        # Text formatting settings for supported proof types
        if proof_supports_formatting(proof_key):
            # Tracking setting (default 0)
            tracking_key = f"{proof_key}_tracking"
            if tracking_key not in self.proof_settings:
                self.proof_settings[tracking_key] = 0

            # Align setting (default based on proof type - "right" for Arabic/Persian, "left" for others)
            align_key = f"{proof_key}_align"
            if align_key not in self.proof_settings:
                self.proof_settings[align_key] = get_default_alignment_for_proof(
                    proof_key
                )

        # Character category settings for Filtered Character Set proof
        if proof_key == "filtered_character_set":
            # Default values: most categories enabled except accented
            category_defaults = {
                "uppercase_base": True,
                "lowercase_base": True,
                "numbers_symbols": True,
                "punctuation": True,
                "accented": False,
            }

            for category_key, default_value in category_defaults.items():
                setting_key = f"{proof_key}_cat_{category_key}"
                if setting_key not in self.proof_settings:
                    self.proof_settings[setting_key] = default_value

        # OpenType features
        self._initialize_opentype_features(proof_key)

    def _initialize_opentype_features(self, proof_key):
        """Initialize OpenType feature settings for a proof type."""
        if not self.font_manager.fonts:
            return

        try:
            import drawBot as db

            feature_tags = db.listOpenTypeFeatures(self.font_manager.fonts[0])
        except Exception:
            feature_tags = []

        for tag in feature_tags:
            # Skip hidden features
            if tag in HIDDEN_FEATURES:
                continue

            feature_key = f"otf_{proof_key}_{tag}"
            if feature_key not in self.proof_settings:
                default_value = tag in DEFAULT_ON_FEATURES
                self.proof_settings[feature_key] = default_value

    def get_proof_font_size(self, proof_identifier):
        """Get font size for a specific proof from its settings."""
        # Get mapping from config
        display_name_to_settings_key = get_proof_settings_mapping()

        # Determine if this is a direct match or a numbered variant
        proof_key = None
        if proof_identifier in display_name_to_settings_key:
            # Direct match - use proof key
            proof_key = display_name_to_settings_key[proof_identifier]
            font_size_key = f"{proof_key}_fontSize"
        else:
            # This might be a numbered variant like "Filtered Character Set 2"
            # Find the base proof type by checking if the identifier starts with any known proof type
            for display_name, settings_key in display_name_to_settings_key.items():
                if proof_identifier.startswith(display_name):
                    proof_key = settings_key
                    # For numbered variants, we use the unique identifier as the key
                    unique_key = create_unique_proof_key(proof_identifier)
                    font_size_key = f"{unique_key}_fontSize"
                    break

            # Fallback if no match found
            if not proof_key:
                proof_key = "basic_paragraph_small"
                unique_key = create_unique_proof_key(proof_identifier)
                font_size_key = f"{unique_key}_fontSize"

        # Set default font size based on proof type using registry
        default_font_size = get_proof_default_font_size(proof_key)

        return self.proof_settings.get(font_size_key, default_font_size)

    def initialize_settings_for_proof(self, unique_proof_name, base_proof_type):
        """Initialize settings for a newly added proof instance."""
        try:
            # Map proof display names to internal keys - use unified snake_case format
            proof_name_to_key = {
                "Show Baselines/Grid": "show_baselines",
                "Filtered Character Set": "filtered_character_set",
                "Spacing Proof": "spacing_proof",
                "Basic Paragraph Large": "basic_paragraph_large",
                "Diacritic Words Large": "diacritic_words_large",
                "Basic Paragraph Small": "basic_paragraph_small",
                "Paired Styles Paragraph Small": "paired_styles_paragraph_small",
                "Generative Text Small": "generative_text_small",
                "Diacritic Words Small": "diacritic_words_small",
                "Misc Paragraph Small": "misc_paragraph_small",
                "Ar Character Set": "ar_character_set",
                "Ar Paragraph Large": "ar_paragraph_large",
                "Fa Paragraph Large": "fa_paragraph_large",
                "Ar Paragraph Small": "ar_paragraph_small",
                "Fa Paragraph Small": "fa_paragraph_small",
                "Ar Vocalization Paragraph Small": "ar_vocalization_paragraph_small",
                "Ar-Lat Mixed Paragraph Small": "ar_lat_mixed_paragraph_small",
                "Ar Numbers Small": "ar_numbers_small",
            }

            # Skip if this is just "Show Baselines/Grid" - it doesn't need special settings
            if base_proof_type == "Show Baselines/Grid":
                return

            base_proof_key = proof_name_to_key.get(base_proof_type)
            if not base_proof_key:
                return

            # Create a unique identifier for this proof instance by sanitizing the unique name
            unique_key = create_unique_proof_key(unique_proof_name)

            # Initialize settings with defaults based on the base proof type
            # Font size setting
            font_size_key = f"{unique_key}_fontSize"
            default_font_size = get_proof_default_font_size(base_proof_key)
            self.proof_settings[font_size_key] = default_font_size

            # Get proof info from registry
            proof_info = get_proof_by_storage_key(base_proof_key)
            if proof_info is None:
                return  # Skip if not found in registry

            # Columns setting (if applicable)
            if base_proof_key not in ["filtered_character_set", "ar_character_set"]:
                cols_key = f"{unique_key}_cols"
                default_cols = proof_info["default_cols"]
                self.proof_settings[cols_key] = default_cols

            # Paragraphs setting (only for proofs that have paragraphs)
            if proof_info["has_paragraphs"]:
                para_key = f"{unique_key}_para"
                self.proof_settings[para_key] = 5

            # Text formatting settings for supported proof types
            if proof_supports_formatting(base_proof_key):
                # Tracking setting (default 0)
                tracking_key = f"{unique_key}_tracking"
                if tracking_key not in self.proof_settings:
                    self.proof_settings[tracking_key] = 0

                # Align setting (default based on proof type - "right" for Arabic/Persian, "left" for others)
                align_key = f"{unique_key}_align"
                if align_key not in self.proof_settings:
                    self.proof_settings[align_key] = get_default_alignment_for_proof(
                        base_proof_key
                    )

            # Character category settings for Filtered Character Set proof
            if base_proof_key == "filtered_character_set":
                # Default values: most categories enabled except accented
                category_defaults = {
                    "uppercase_base": True,
                    "lowercase_base": True,
                    "numbers_symbols": True,
                    "punctuation": True,
                    "accented": False,
                }

                for category_key, default_value in category_defaults.items():
                    setting_key = f"{unique_key}_cat_{category_key}"
                    if setting_key not in self.proof_settings:
                        self.proof_settings[setting_key] = default_value

            # OpenType features
            if self.font_manager.fonts:
                try:
                    import drawBot as db

                    feature_tags = db.listOpenTypeFeatures(self.font_manager.fonts[0])
                except Exception:
                    feature_tags = []

                for tag in feature_tags:
                    # Skip hidden features
                    if tag in HIDDEN_FEATURES:
                        continue

                    feature_key = f"otf_{unique_key}_{tag}"
                    default_value = tag in DEFAULT_ON_FEATURES
                    self.proof_settings[feature_key] = default_value

        except Exception as e:
            print(f"Error initializing settings for proof {unique_proof_name}: {e}")
            import traceback

            traceback.print_exc()

    def update_settings_value(self, key, value):
        """Update a single settings value."""
        self.proof_settings[key] = value

    def get_settings_value(self, key, default=None):
        """Get a single settings value."""
        return self.proof_settings.get(key, default)

    def save_all_settings(self, proof_options_items):
        """Save all current settings including proof options and proof-specific settings."""
        try:
            # Save proof options
            for item in proof_options_items:
                proof_name = item[
                    "Option"
                ]  # Use the actual proof name (including numbers)
                base_option = item.get(
                    "_original_option", proof_name
                )  # Get original option name
                enabled = item["Enabled"]

                if base_option == "Show Baselines/Grid":
                    self.settings.set_proof_option("showBaselines", enabled)
                else:
                    # For unique proof names, use a sanitized version as the key
                    unique_key = create_unique_proof_key(proof_name)
                    self.settings.set_proof_option(unique_key, enabled)

            # Save proof-specific settings
            self.settings.set_proof_settings(self.proof_settings)

            # Save the settings file
            self.settings.save()

        except Exception as e:
            print(f"Error saving settings: {e}")
            import traceback

            traceback.print_exc()

    def build_proof_data_for_generation(self, proof_options_items):
        """Build the data structures needed for proof generation."""
        otfeatures_by_proof = {}
        cols_by_proof = {}
        paras_by_proof = {}

        # Get mapping from config
        display_name_to_settings_key = get_proof_settings_mapping()

        # Process settings for both old-style and new unique proof identifiers
        for item in proof_options_items:
            if not item["Enabled"]:
                continue

            proof_name = item["Option"]

            # Always use the unique identifier for settings keys to ensure consistency
            # This handles both original proofs and numbered duplicates uniformly
            unique_key = create_unique_proof_key(proof_name)

            # Determine the base proof type for validation
            settings_key = None
            for display_name, base_settings_key in display_name_to_settings_key.items():
                if proof_name.startswith(display_name):
                    settings_key = base_settings_key
                    break

            # Fallback if no base type found
            if not settings_key:
                settings_key = "basic_paragraph_small"

            # Always use unique identifier for all settings keys
            cols_key = f"{unique_key}_cols"
            para_key = f"{unique_key}_para"
            otf_prefix = f"otf_{unique_key}_"

            # Get columns setting
            if cols_key in self.proof_settings:
                cols_by_proof[proof_name] = self.proof_settings[cols_key]

            # Get paragraphs setting (only for Wordsiv proofs)
            if "Wordsiv" in proof_name:
                if para_key in self.proof_settings:
                    paras_by_proof[proof_name] = self.proof_settings[para_key]

            # Get OpenType features
            otf_dict = {}
            for key, value in self.proof_settings.items():
                if key.startswith(otf_prefix):
                    feature = key.replace(otf_prefix, "")
                    otf_dict[feature] = bool(value)
            otfeatures_by_proof[proof_name] = otf_dict

        return otfeatures_by_proof, cols_by_proof, paras_by_proof

    def get_popover_settings_for_proof(self, proof_key):
        """Get settings data for popover display for a specific proof type."""
        numeric_items = []

        # Font size setting for all proofs (always first)
        font_size_key = f"{proof_key}_fontSize"
        default_font_size = get_proof_default_font_size(proof_key)
        font_size_value = self.proof_settings.get(font_size_key, default_font_size)
        numeric_items.append(
            {"Setting": "Font Size", "Value": font_size_value, "_key": font_size_key}
        )

        # Columns setting with appropriate defaults (skip for certain proofs)
        if proof_key not in ["filtered_character_set", "ar_character_set"]:
            cols_key = f"{proof_key}_cols"
            proof_info = get_proof_by_storage_key(proof_key)
            if proof_info:
                default_cols = proof_info["default_cols"]
            else:
                default_cols = 2  # Fallback

            cols_value = self.proof_settings.get(cols_key, default_cols)
            numeric_items.append(
                {"Setting": "Columns", "Value": cols_value, "_key": cols_key}
            )

        # Paragraphs setting (only for proofs that have paragraphs)
        proof_info = get_proof_by_settings_key(proof_key)
        if proof_info and proof_info["has_paragraphs"]:
            para_key = f"{proof_key}_para"
            para_value = self.proof_settings.get(para_key, 5)
            numeric_items.append(
                {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
            )

        # Add tracking for supported proof types
        if proof_supports_formatting(proof_key):
            tracking_key = f"{proof_key}_tracking"
            tracking_value = self.proof_settings.get(tracking_key, 0)
            numeric_items.append(
                {"Setting": "Tracking", "Value": tracking_value, "_key": tracking_key}
            )

        return numeric_items

    def get_opentype_features_for_proof(self, proof_key):
        """Get OpenType features data for popover display for a specific proof type."""
        if not self.font_manager.fonts:
            return []

        try:
            import drawBot as db

            feature_tags = db.listOpenTypeFeatures(self.font_manager.fonts[0])
        except Exception:
            feature_tags = []

        feature_items = []
        for tag in feature_tags:
            # Skip hidden features
            if tag in HIDDEN_FEATURES:
                continue

            feature_key = f"otf_{proof_key}_{tag}"

            # Special handling for Spacing_Proof kern feature
            if proof_key == "spacing_proof" and tag == "kern":
                feature_value = False
                self.proof_settings[feature_key] = False
                feature_items.append(
                    {
                        "Feature": f"{tag} (always off)",
                        "Enabled": feature_value,
                        "_key": feature_key,
                        "_readonly": True,
                    }
                )
            else:
                default_value = tag in DEFAULT_ON_FEATURES
                feature_value = self.proof_settings.get(feature_key, default_value)
                feature_items.append(
                    {"Feature": tag, "Enabled": feature_value, "_key": feature_key}
                )

        return feature_items

    def get_alignment_value_for_proof(self, proof_key):
        """Get alignment value for a specific proof type."""
        if not proof_supports_formatting(proof_key):
            return None

        align_key = f"{proof_key}_align"
        default_align = get_default_alignment_for_proof(proof_key)
        return self.proof_settings.get(align_key, default_align)

    def set_alignment_value_for_proof(self, proof_key, align_value):
        """Set alignment value for a specific proof type."""
        if proof_supports_formatting(proof_key):
            align_key = f"{proof_key}_align"
            self.proof_settings[align_key] = align_value

    def update_numeric_setting(self, key, value):
        """Update a numeric setting with validation."""
        try:
            # Handle tracking values (can be float) vs other settings (must be positive int)
            if "_tracking" in key:
                value = float(value)
                self.proof_settings[key] = value
                return True
            else:
                value = int(value)
                if value <= 0:
                    print(f"Invalid value for setting: must be > 0")
                    return False
                self.proof_settings[key] = value
                return True
        except (ValueError, TypeError):
            print(f"Invalid value for setting: {value}")
            return False

    def update_feature_setting(self, key, enabled, readonly=False):
        """Update an OpenType feature setting."""
        if readonly:
            # Reset to disabled if someone tries to change a readonly feature
            if enabled:
                enabled = False

        self.proof_settings[key] = bool(enabled)
        return (
            enabled  # Return the actual value set (may differ from input for readonly)
        )

    def reset_all_proof_settings(self):
        """Reset all proof-specific settings to defaults."""
        # Clear existing settings
        self.proof_settings = {}

        # Reinitialize with defaults
        self.initialize_proof_settings()

        # Save the reset settings
        self.settings.set_proof_settings(self.proof_settings)


class AppSettingsManager:
    """Manages application-level settings (not proof-specific)."""

    def __init__(self, settings):
        """Initialize with an existing Settings object."""
        self.settings = settings

    def get_settings(self):
        """Get the underlying Settings object."""
        return self.settings

    def load_user_settings_file(self, file_path):
        """Load settings from a user-specified file."""
        try:
            user_data = safe_json_load(file_path)
            if user_data:
                self.settings.data.update(user_data)
                self.settings.user_settings_file = file_path
                print(f"Loaded user settings from: {file_path}")
                return True
            else:
                log_error(f"Failed to load user settings file: {file_path}")
                return False
        except Exception as e:
            log_error(f"Error loading user settings file {file_path}: {e}")
            return False

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.settings.reset_to_defaults()

    def get_page_format(self):
        """Get current page format."""
        return self.settings.get_page_format()

    def set_page_format(self, format_name):
        """Set page format."""
        self.settings.set_page_format(format_name)

    def get_pdf_output_settings(self):
        """Get PDF output location settings."""
        return self.settings.data.get(
            "pdf_output",
            {
                "use_custom_location": False,
                "custom_location": "",
            },
        )

    def set_pdf_output_settings(self, use_custom, custom_location=""):
        """Set PDF output location settings."""
        if "pdf_output" not in self.settings.data:
            self.settings.data["pdf_output"] = {}
        self.settings.data["pdf_output"]["use_custom_location"] = use_custom
        self.settings.data["pdf_output"]["custom_location"] = custom_location
        self.settings.save()

    def get_fonts(self):
        """Get font paths."""
        return self.settings.get_fonts()

    def set_fonts(self, font_paths):
        """Set font paths."""
        self.settings.set_fonts(font_paths)

    def get_font_axis_values(self, font_path):
        """Get axis values for a font."""
        return self.settings.get_font_axis_values(font_path)

    def set_font_axis_values(self, font_path, axis_values):
        """Set axis values for a font."""
        self.settings.set_font_axis_values(font_path, axis_values)

    def get_proof_option(self, option_key):
        """Get a proof option value."""
        return self.settings.get_proof_option(option_key)

    def set_proof_option(self, option_key, value):
        """Set a proof option value."""
        self.settings.set_proof_option(option_key, value)

    def get_proof_order(self):
        """Get proof order."""
        return self.settings.get_proof_order()

    def set_proof_order(self, proof_order):
        """Set proof order."""
        self.settings.set_proof_order(proof_order)
        self.settings.save()

    def save(self):
        """Save settings."""
        self.settings.save()
