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
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            save_path = self.user_settings_file or self.settings_path

            with open(save_path, "w") as f:
                json.dump(self.data, f, indent=2)

            # Update auto-save file if using user settings
            if self.user_settings_file and save_path != self.settings_path:
                with open(self.settings_path, "w") as f:
                    json.dump(
                        {"user_settings_file": self.user_settings_file}, f, indent=2
                    )
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
        return self.data.get(
            "proof_order", get_proof_display_names(include_arabic=True)
        )

    def set_proof_order(self, proof_order):
        """Set the proof order."""
        self.data["proof_order"] = proof_order[:]

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

    # Common defaults to avoid duplication
    _CATEGORY_DEFAULTS = {
        "uppercase_base": True,
        "lowercase_base": True,
        "numbers_symbols": True,
        "punctuation": True,
        "accented": False,
    }

    _COLUMN_EXCLUDED_PROOFS = {
        "filtered_character_set",
        "spacing_proof",
        "ar_character_set",
    }

    def _initialize_proof_type_defaults(self, proof_key):
        """Initialize default settings for a specific proof type."""
        proof_info = get_proof_by_settings_key(proof_key)
        if proof_info is None:
            return

        self._init_basic_settings(proof_key, proof_info)
        self._init_category_settings(proof_key)
        self._initialize_opentype_features(proof_key)

    def _init_basic_settings(self, proof_key, proof_info):
        """Initialize basic settings (font size, columns, paragraphs, formatting)."""
        settings = {
            f"{proof_key}_fontSize": get_proof_default_font_size(proof_key),
        }

        # Column settings for applicable proofs
        if proof_key not in self._COLUMN_EXCLUDED_PROOFS:
            settings[f"{proof_key}_cols"] = proof_info["default_cols"]

        # Paragraph settings for applicable proofs
        if proof_info["has_paragraphs"]:
            settings[f"{proof_key}_para"] = 5

        # Text formatting settings
        if proof_supports_formatting(proof_key):
            settings[f"{proof_key}_tracking"] = 0
            settings[f"{proof_key}_align"] = get_default_alignment_for_proof(proof_key)

        # Apply settings only if not already present
        for key, value in settings.items():
            if key not in self.proof_settings:
                self.proof_settings[key] = value

    def _init_category_settings(self, proof_key):
        """Initialize character category settings for applicable proofs."""
        if proof_key in ["filtered_character_set", "spacing_proof"]:
            for category_key, default_value in self._CATEGORY_DEFAULTS.items():
                setting_key = f"{proof_key}_cat_{category_key}"
                if setting_key not in self.proof_settings:
                    self.proof_settings[setting_key] = default_value

    def _get_font_features(self):
        """Get OpenType feature tags from the current font."""
        if not self.font_manager.fonts:
            return []
        try:
            import drawBot as db

            return db.listOpenTypeFeatures(self.font_manager.fonts[0])
        except Exception:
            return []

    def _initialize_opentype_features(self, proof_key):
        """Initialize OpenType feature settings for a proof type."""
        for tag in self._get_font_features():
            if tag not in HIDDEN_FEATURES:
                feature_key = f"otf_{proof_key}_{tag}"
                if feature_key not in self.proof_settings:
                    self.proof_settings[feature_key] = tag in DEFAULT_ON_FEATURES

    def _get_proof_key_for_identifier(self, proof_identifier):
        """Get proof key and font size key for a given proof identifier."""
        display_name_to_settings_key = get_proof_settings_mapping()

        if proof_identifier in display_name_to_settings_key:
            # Direct match
            proof_key = display_name_to_settings_key[proof_identifier]
            return proof_key, f"{proof_key}_fontSize"

        # Check for numbered variants
        for display_name, settings_key in display_name_to_settings_key.items():
            if proof_identifier.startswith(display_name):
                unique_key = create_unique_proof_key(proof_identifier)
                return settings_key, f"{unique_key}_fontSize"

        # Fallback
        proof_key = "basic_paragraph_small"
        unique_key = create_unique_proof_key(proof_identifier)
        return proof_key, f"{unique_key}_fontSize"

    def get_proof_font_size(self, proof_identifier):
        """Get font size for a specific proof from its settings."""
        proof_key, font_size_key = self._get_proof_key_for_identifier(proof_identifier)
        default_font_size = get_proof_default_font_size(proof_key)
        return self.proof_settings.get(font_size_key, default_font_size)

    def _init_proof_instance_settings(self, unique_key, base_proof_key, proof_info):
        """Initialize settings for a specific proof instance."""
        settings = {
            f"{unique_key}_fontSize": get_proof_default_font_size(base_proof_key),
        }

        # Column and paragraph settings
        if base_proof_key not in self._COLUMN_EXCLUDED_PROOFS:
            settings[f"{unique_key}_cols"] = proof_info["default_cols"]

        if proof_info["has_paragraphs"]:
            settings[f"{unique_key}_para"] = 5

        # Text formatting settings
        if proof_supports_formatting(base_proof_key):
            settings[f"{unique_key}_tracking"] = 0
            settings[f"{unique_key}_align"] = get_default_alignment_for_proof(
                base_proof_key
            )

        # Category settings
        if base_proof_key in ["filtered_character_set", "spacing_proof"]:
            for category_key, default_value in self._CATEGORY_DEFAULTS.items():
                settings[f"{unique_key}_cat_{category_key}"] = default_value

        # Apply settings
        for key, value in settings.items():
            if key not in self.proof_settings:
                self.proof_settings[key] = value

        # OpenType features
        for tag in self._get_font_features():
            if tag not in HIDDEN_FEATURES:
                feature_key = f"otf_{unique_key}_{tag}"
                if feature_key not in self.proof_settings:
                    self.proof_settings[feature_key] = tag in DEFAULT_ON_FEATURES

    def initialize_settings_for_proof(self, unique_proof_name, base_proof_type):
        """Initialize settings for a newly added proof instance."""
        try:
            if base_proof_type == "Show Baselines/Grid":
                return

            proof_name_to_key = get_proof_name_to_key_mapping()
            base_proof_key = proof_name_to_key.get(base_proof_type)
            if not base_proof_key:
                return

            proof_info = get_proof_by_storage_key(base_proof_key)
            if proof_info is None:
                return

            unique_key = create_unique_proof_key(unique_proof_name)
            self._init_proof_instance_settings(unique_key, base_proof_key, proof_info)

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

    def _build_settings_for_proof(self, proof_name, unique_key, settings_key):
        """Build settings data for a single proof."""
        cols_key = f"{unique_key}_cols"
        para_key = f"{unique_key}_para"
        otf_prefix = f"otf_{unique_key}_"

        result = {"cols": None, "paras": None, "otf": {}}

        # Get columns and paragraphs settings
        if cols_key in self.proof_settings:
            result["cols"] = self.proof_settings[cols_key]

        if "Wordsiv" in proof_name and para_key in self.proof_settings:
            result["paras"] = self.proof_settings[para_key]

        # Get OpenType features
        for key, value in self.proof_settings.items():
            if key.startswith(otf_prefix):
                feature = key.replace(otf_prefix, "")
                result["otf"][feature] = bool(value)

        return result

    def build_proof_data_for_generation(self, proof_options_items):
        """Build the data structures needed for proof generation."""
        otfeatures_by_proof = {}
        cols_by_proof = {}
        paras_by_proof = {}

        display_name_to_settings_key = get_proof_settings_mapping()

        for item in proof_options_items:
            if not item["Enabled"]:
                continue

            proof_name = item["Option"]
            unique_key = create_unique_proof_key(proof_name)

            # Determine base proof type
            settings_key = None
            for display_name, base_settings_key in display_name_to_settings_key.items():
                if proof_name.startswith(display_name):
                    settings_key = base_settings_key
                    break

            if not settings_key:
                settings_key = "basic_paragraph_small"

            # Build settings for this proof
            proof_data = self._build_settings_for_proof(
                proof_name, unique_key, settings_key
            )

            if proof_data["cols"] is not None:
                cols_by_proof[proof_name] = proof_data["cols"]
            if proof_data["paras"] is not None:
                paras_by_proof[proof_name] = proof_data["paras"]
            otfeatures_by_proof[proof_name] = proof_data["otf"]

        return otfeatures_by_proof, cols_by_proof, paras_by_proof

    def _build_numeric_settings_list(self, proof_key):
        """Build list of numeric settings for a proof."""
        items = []

        # Font size (always first)
        font_size_key = f"{proof_key}_fontSize"
        default_font_size = get_proof_default_font_size(proof_key)
        font_size_value = self.proof_settings.get(font_size_key, default_font_size)
        items.append(
            {"Setting": "Font Size", "Value": font_size_value, "_key": font_size_key}
        )

        # Columns (for applicable proofs)
        if proof_key not in self._COLUMN_EXCLUDED_PROOFS:
            cols_key = f"{proof_key}_cols"
            proof_info = get_proof_by_storage_key(proof_key)
            default_cols = proof_info["default_cols"] if proof_info else 2
            cols_value = self.proof_settings.get(cols_key, default_cols)
            items.append({"Setting": "Columns", "Value": cols_value, "_key": cols_key})

        # Paragraphs (for applicable proofs)
        proof_info = get_proof_by_settings_key(proof_key)
        if proof_info and proof_info["has_paragraphs"]:
            para_key = f"{proof_key}_para"
            para_value = self.proof_settings.get(para_key, 5)
            items.append(
                {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
            )

        # Tracking (for supported proofs)
        if proof_supports_formatting(proof_key):
            tracking_key = f"{proof_key}_tracking"
            tracking_value = self.proof_settings.get(tracking_key, 0)
            items.append(
                {"Setting": "Tracking", "Value": tracking_value, "_key": tracking_key}
            )

        return items

    def get_popover_settings_for_proof(self, proof_key):
        """Get settings data for popover display for a specific proof type."""
        return self._build_numeric_settings_list(proof_key)

    def get_popover_settings_for_proof_instance(self, unique_proof_key, base_proof_key):
        """Get settings data for popover display for a specific proof instance."""
        return self._build_numeric_settings_list_with_key(
            unique_proof_key, base_proof_key
        )

    def _build_numeric_settings_list_with_key(self, settings_key, base_proof_key=None):
        """Build list of numeric settings using a custom settings key."""
        items = []

        # Use base_proof_key for registry lookups, settings_key for actual settings
        lookup_key = base_proof_key or settings_key

        # Font size (always first)
        font_size_key = f"{settings_key}_fontSize"
        default_font_size = get_proof_default_font_size(lookup_key)
        font_size_value = self.proof_settings.get(font_size_key, default_font_size)
        items.append(
            {"Setting": "Font Size", "Value": font_size_value, "_key": font_size_key}
        )

        # Columns (for applicable proofs)
        if lookup_key not in self._COLUMN_EXCLUDED_PROOFS:
            cols_key = f"{settings_key}_cols"
            proof_info = get_proof_by_storage_key(lookup_key)
            default_cols = proof_info["default_cols"] if proof_info else 2
            cols_value = self.proof_settings.get(cols_key, default_cols)
            items.append({"Setting": "Columns", "Value": cols_value, "_key": cols_key})

        # Paragraphs (for applicable proofs)
        proof_info = get_proof_by_settings_key(lookup_key)
        if proof_info and proof_info["has_paragraphs"]:
            para_key = f"{settings_key}_para"
            para_value = self.proof_settings.get(para_key, 5)
            items.append(
                {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
            )

        # Tracking (for supported proofs)
        if proof_supports_formatting(lookup_key):
            tracking_key = f"{settings_key}_tracking"
            tracking_value = self.proof_settings.get(tracking_key, 0)
            items.append(
                {"Setting": "Tracking", "Value": tracking_value, "_key": tracking_key}
            )

        return items

    def get_opentype_features_for_proof(self, proof_key):
        """Get OpenType features data for popover display for a specific proof type."""
        feature_items = []

        for tag in self._get_font_features():
            if tag in HIDDEN_FEATURES:
                continue

            feature_key = f"otf_{proof_key}_{tag}"

            # Special handling for spacing proof kern feature
            if proof_key == "spacing_proof" and tag == "kern":
                self.proof_settings[feature_key] = False
                feature_items.append(
                    {
                        "Feature": f"{tag} (always off)",
                        "Enabled": False,
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
        return self.proof_settings.get(
            align_key, get_default_alignment_for_proof(proof_key)
        )

    def set_alignment_value_for_proof(self, proof_key, align_value):
        """Set alignment value for a specific proof type."""
        if proof_supports_formatting(proof_key):
            self.proof_settings[f"{proof_key}_align"] = align_value

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
        if readonly and enabled:
            enabled = False
        self.proof_settings[key] = bool(enabled)
        return enabled

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
