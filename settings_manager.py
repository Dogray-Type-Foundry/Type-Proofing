# Settings Manager - Centralized settings handling for proof generation

import json
import os
from core_config import (
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
    SETTINGS_PATH,
    DEFAULT_PAGE_FORMAT,
)
from proof_config import (
    PROOF_REGISTRY,
    get_proof_by_settings_key,
    get_proof_by_storage_key,
    get_proof_default_font_size,
    proof_supports_formatting,
    get_proof_settings_mapping,
    get_default_alignment_for_proof,
    get_proof_name_to_key_mapping,
    get_proof_display_names,
)
from proof_handlers import create_unique_proof_key
from utils import safe_json_load, safe_json_save, log_error, validate_setting_value


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
        from core_config import APP_VERSION

        # Generate proof options dynamically from registry
        proof_options = {}
        for proof_key in PROOF_REGISTRY.keys():
            proof_options[proof_key] = False

        # Generate proof order dynamically from registry (excluding show_baselines)
        proof_order = get_proof_display_names(include_arabic=True)

        return {
            "version": APP_VERSION,
            "fonts": {"paths": [], "axis_values": {}},
            "proof_options": {"show_baselines": False, **proof_options},
            "proof_settings": {},
            "proof_order": proof_order,
            "pdf_output": {
                "use_custom_location": False,
                "custom_location": "",
            },
            "page_format": DEFAULT_PAGE_FORMAT,
        }

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

    def get(self, key, default=None):
        """Get a setting value."""
        return self.data.get(key, default)

    def set(self, key, value):
        """Set a setting value."""
        self.data[key] = value

    def update(self, updates):
        """Update multiple settings at once."""
        self.data.update(updates)

    def get_proof_option(self, option_key):
        """Get a proof option value."""
        return self.data.get("proof_options", {}).get(option_key, False)

    def set_proof_option(self, option_key, value):
        """Set a proof option value."""
        if "proof_options" not in self.data:
            self.data["proof_options"] = {}
        self.data["proof_options"][option_key] = value
        self.save()

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
        return self.data.get("page_format", DEFAULT_PAGE_FORMAT)

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

    def get_proof_settings(self):
        """Get the proof settings dictionary."""
        return self.data.get("proof_settings", {})

    def set_proof_settings(self, proof_settings):
        """Set the proof settings dictionary."""
        if "proof_settings" not in self.data:
            self.data["proof_settings"] = {}
        self.data["proof_settings"] = dict(proof_settings)
        self.save()

    def set_pdf_output_custom_location(self, location):
        """Set custom PDF output location."""
        if "pdf_output" not in self.data:
            self.data["pdf_output"] = {
                "use_custom_location": False,
                "custom_location": "",
            }
        self.data["pdf_output"]["custom_location"] = location

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.data = self._get_defaults()
        self.user_settings_file = None
        self.save()

    def load_from_file(self, file_path):
        """Load settings from a specific file."""
        if os.path.exists(file_path):
            self.user_settings_file = file_path
            self.data = self._load_settings_file(file_path)
            return True
        return False

    def export_to_file(self, file_path):
        """Export current settings to a file."""
        try:
            with open(file_path, "w") as f:
                json.dump(self.data, f, indent=2)
            return True
        except IOError:
            return False


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
        # Character Set, Spacing Proof, and Arabic Character Set don't use columns (they handle them differently)
        if proof_key not in [
            "filtered_character_set",
            "spacing_proof",
            "ar_character_set",
        ]:
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

        # Character category settings for Filtered Character Set and Spacing Proof
        if proof_key in ["filtered_character_set", "spacing_proof"]:
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
            # Use centralized mapping
            proof_name_to_key = get_proof_name_to_key_mapping()

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
            if base_proof_key not in [
                "filtered_character_set",
                "spacing_proof",
                "ar_character_set",
            ]:
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

            # Character category settings for Filtered Character Set and Spacing Proof
            if base_proof_key in ["filtered_character_set", "spacing_proof"]:
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
        if proof_key not in [
            "filtered_character_set",
            "spacing_proof",
            "ar_character_set",
        ]:
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
        is_valid, converted_value, error_msg = validate_setting_value(key, value)
        if not is_valid:
            print(f"Invalid value for setting: {error_msg}")
            return False
        self.proof_settings[key] = converted_value
        return True

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


# Create singleton instance for app-level settings (replaces AppSettingsManager)
def get_app_settings(settings_path=SETTINGS_PATH):
    """Get a singleton Settings instance for application settings."""
    if not hasattr(get_app_settings, "_instance"):
        get_app_settings._instance = Settings(settings_path)
    return get_app_settings._instance
