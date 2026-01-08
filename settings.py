# Settings - Core utilities, file operations, validation, and settings management
# Consolidated from utils.py and settings_manager.py

import os
import json
import datetime
import traceback
import re
from urllib.parse import urlparse, unquote
from functools import lru_cache


# =============================================================================
# Core Utilities - File operations, validation, string processing, error handling
# =============================================================================


def normalize_path(path, font_specific=False):
    """Normalize path from various input types (URL, string, AppKit.NSURL, etc.)"""
    if not path:
        return ""

    # Handle AppKit.NSURL objects for font-specific paths
    if font_specific:
        try:
            import AppKit

            if isinstance(path, AppKit.NSURL):
                return path.path()
        except ImportError:
            pass

    # Handle URL format
    if isinstance(path, str):
        if path.startswith("file://"):
            if font_specific:
                return path.replace("file://", "")
            else:
                parsed = urlparse(path)
                path = unquote(parsed.path)

    if font_specific:
        return str(path)
    else:
        return os.path.abspath(os.path.expanduser(str(path)))


def ensure_directory_exists(directory):
    """Create directory if it doesn't exist"""
    try:
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        log_error(f"Failed to create directory {directory}: {e}")
        return False


def get_file_extension(path):
    """Get file extension in lowercase"""
    if not path:
        return ""
    return os.path.splitext(path)[1].lower()


def is_valid_font_extension(path):
    """Check if path has a valid font file extension"""
    valid_extensions = {".otf", ".ttf", ".woff", ".woff2"}
    return get_file_extension(path) in valid_extensions


def make_safe_filename(name, extension=""):
    """Create a safe filename by removing/replacing invalid characters"""
    if not name:
        return "unnamed"

    # Replace invalid filename characters
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
    safe_name = safe_name.strip(". ")

    # Limit length
    if len(safe_name) > 200:
        safe_name = safe_name[:200]

    # Add extension if provided and not already present
    if extension and not safe_name.endswith(extension):
        safe_name += extension

    return safe_name or "unnamed"


def get_file_size_formatted(path):
    """Get formatted file size string"""
    try:
        if not path or not os.path.exists(path):
            return "Unknown"

        size_bytes = os.path.getsize(path)
        return format_file_size(size_bytes)
    except Exception:
        return "Unknown"


def format_file_size(bytes_size):
    """Format bytes into human readable string"""
    if bytes_size == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    size = bytes_size
    i = 0

    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def safe_json_load(file_path, default=None):
    """Safely load JSON file with error handling"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_error(f"Failed to load JSON from {file_path}: {e}")

    return default if default is not None else {}


def safe_json_save(data, file_path):
    """Safely save data to JSON file"""
    try:
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory:
            ensure_directory_exists(directory)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        log_error(f"Failed to save JSON to {file_path}: {e}")
        return False


def clean_font_name(name):
    """Clean font name for display"""
    if not name:
        return "Unnamed Font"

    # Remove common font suffixes and clean up
    cleaned = name.replace("Regular", "").replace("Normal", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned or "Unnamed Font"


def format_timestamp(datetime_obj=None):
    """Format datetime object to readable string"""
    if datetime_obj is None:
        datetime_obj = datetime.datetime.now()

    return datetime_obj.strftime("%Y-%m-%d_%H%M")


def validate_font_path(path):
    """Validate that path points to a valid font file"""
    try:
        if not path:
            return False, "No path provided"

        normalized = normalize_path(path)

        if not os.path.exists(normalized):
            return False, f"File does not exist: {path}"

        if not os.path.isfile(normalized):
            return False, f"Path is not a file: {path}"

        if not is_valid_font_extension(normalized):
            return False, f"Invalid font file extension: {get_file_extension(path)}"

        return True, "Valid font file"

    except Exception as e:
        return False, f"Validation error: {e}"


def is_valid_numeric_input(value):
    """Check if value can be converted to a number"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_setting_value(key, value):
    """Validate and convert setting values based on key type.

    Args:
        key: Setting key (used to determine validation rules)
        value: Value to validate and convert

    Returns:
        tuple: (is_valid, converted_value, error_message)
    """
    try:
        if "_tracking" in key:
            # Tracking values can be float (including negative)
            converted_value = float(value)
            return True, converted_value, None
        else:
            # Other settings must be positive integers
            converted_value = int(float(value))
            if converted_value <= 0:
                return False, None, "must be > 0"
            return True, converted_value, None
    except (ValueError, TypeError):
        return False, None, f"invalid value: {value}"


def log_error(error, context=""):
    """Log error with context information"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    context_str = f" [{context}]" if context else ""
    print(f"[{timestamp}] ERROR{context_str}: {error}")


def safe_execute(operation_name, func, *args, **kwargs):
    """Safely execute an operation with standardized error handling.

    Args:
        operation_name: Name of the operation for error reporting
        func: Function to execute
        *args, **kwargs: Arguments to pass to the function

    Returns:
        bool: True if operation succeeded, False if it failed
    """
    try:
        func(*args, **kwargs)
        return True
    except Exception as e:
        print(f"Error in {operation_name}: {e}")
        traceback.print_exc()
        return False


def safe_font_load(font_path):
    """Safely attempt to load a font file"""
    try:
        from fontTools.ttLib import TTFont

        normalized_path = normalize_path(font_path)

        valid, message = validate_font_path(normalized_path)
        if not valid:
            log_error(f"Font validation failed: {message}", "safe_font_load")
            return None

        return TTFont(normalized_path)

    except Exception as e:
        log_error(f"Failed to load font {font_path}: {e}", "safe_font_load")
        return None


# =============================================================================
# Settings Manager - Centralized settings handling for proof generation
# =============================================================================

from config import (
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
    SETTINGS_PATH,
    DEFAULT_PAGE_FORMAT,
)
from config import (
    PROOF_REGISTRY,
    get_proof_by_settings_key,
    get_proof_by_storage_key,
    get_proof_default_font_size,
    proof_supports_formatting,
    get_proof_settings_mapping,
    get_default_alignment_for_proof,
    get_proof_display_names,
    get_otf_prefix,
)


# =============================================================================
# Centralized Settings Key Construction
# =============================================================================


def create_unique_proof_key(proof_name):
    """Create a unique key from proof name for settings storage."""
    unique_proof_key = (
        proof_name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    )
    return unique_proof_key


def make_settings_key(base_key, setting_type, category=None):
    """Construct a consistent settings key.

    Args:
        base_key: The proof key or unique proof key (e.g., "basic_paragraph_small")
        setting_type: The type of setting (e.g., "fontSize", "cols", "tracking", "align")
        category: Optional category for category-specific settings (e.g., "uppercase_base")

    Returns:
        Formatted settings key string

    Examples:
        make_settings_key("basic_paragraph_small", "fontSize") -> "basic_paragraph_small_fontSize"
        make_settings_key("filtered_character_set", "cat", "uppercase_base") -> "filtered_character_set_cat_uppercase_base"
    """
    if category:
        return f"{base_key}_{setting_type}_{category}"
    return f"{base_key}_{setting_type}"


def make_feature_key(base_key, feature_tag):
    """Construct a consistent OpenType feature settings key.

    Args:
        base_key: The proof key or unique proof key
        feature_tag: The OpenType feature tag (e.g., "kern", "liga")

    Returns:
        Formatted feature key string

    Example:
        make_feature_key("basic_paragraph_small", "kern") -> "otf_basic_paragraph_small_kern"
    """
    return f"{get_otf_prefix(base_key)}{feature_tag}"


@lru_cache(maxsize=16)
def _cached_list_ot_features(font_path, mtime):
    """LRU-cached wrapper around drawBot.listOpenTypeFeatures keyed by path+mtime."""
    try:
        import drawBot as db

        return tuple(db.listOpenTypeFeatures(font_path))
    except Exception:
        return tuple()


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
        return self._load_settings_file(self.settings_path, is_auto_save=True)

    def _load_settings_file(self, file_path, raise_on_error=False, is_auto_save=False):
        """Load settings from a specific file."""
        if not os.path.exists(file_path):
            return self._get_defaults()

        try:
            data = safe_json_load(file_path, default={}) or {}

            # Treat empty files as defaults
            if not data:
                if raise_on_error:
                    raise ValueError(f"Settings file {file_path} is empty.")
                return self._get_defaults()

            # Auto-save pointer-only file -> ignore and use defaults
            if is_auto_save and set(data.keys()) == {"user_settings_file"}:
                return self._get_defaults()

            # Merge with defaults if not auto-save
            if not is_auto_save:
                defaults = self._get_defaults()
                data = self._merge_settings(defaults, data)

            # Validate fonts
            if self._validate_fonts(data):
                return data
            else:
                msg = (
                    "Some saved fonts no longer exist. Resetting to defaults."
                    if is_auto_save
                    else f"Some fonts in {file_path} no longer exist. Keeping paths for user reference."
                )
                print(msg)
                return self._get_defaults() if is_auto_save else data

        except Exception as e:
            print(
                f"Error loading {'auto-save' if is_auto_save else 'settings file'} {file_path}: {e}"
            )
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
        from config import APP_VERSION

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
            save_path = self.user_settings_file or self.settings_path
            safe_json_save(self.data, save_path)

            # Update auto-save pointer if using a user settings file
            if self.user_settings_file and save_path != self.settings_path:
                safe_json_save(
                    {"user_settings_file": self.user_settings_file}, self.settings_path
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

    # Consolidated generic getter/setter methods
    def _get_nested_value(self, path, default=None):
        """Get a value from nested dictionary using dot notation path."""
        value = self.data
        for key in path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def _set_nested_value(self, path, value, auto_save=True):
        """Set a value in nested dictionary using dot notation path."""
        keys = path.split(".")
        current = self.data

        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set final value
        current[keys[-1]] = value

        if auto_save:
            self.save()

    def _ensure_nested_structure(self, path, default_structure):
        """Ensure nested dictionary structure exists."""
        keys = path.split(".")
        current = self.data

        for key in keys:
            if key not in current:
                current[key] = (
                    default_structure.copy()
                    if isinstance(default_structure, dict)
                    else default_structure
                )
            current = current[key]

    # Specific getter/setter methods using consolidated approach
    def get_proof_option(self, option_key):
        """Get a proof option value."""
        return self._get_nested_value(f"proof_options.{option_key}", False)

    def set_proof_option(self, option_key, value):
        """Set a proof option value."""
        self._ensure_nested_structure("proof_options", {})
        self._set_nested_value(f"proof_options.{option_key}", value)

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
        return self._get_nested_value("fonts.paths", [])

    def set_fonts(self, font_paths):
        """Set the list of font paths."""
        self._ensure_nested_structure("fonts", {"paths": [], "axis_values": {}})
        self._set_nested_value("fonts.paths", list(font_paths))

    def get_font_axis_values(self, font_path):
        """Get axis values for a specific font."""
        return self._get_nested_value(f"fonts.axis_values.{font_path}", {})

    def set_font_axis_values(self, font_path, axis_values):
        """Set axis values for a specific font."""
        self._ensure_nested_structure("fonts", {"paths": [], "axis_values": {}})
        self._ensure_nested_structure("fonts.axis_values", {})
        self._set_nested_value(f"fonts.axis_values.{font_path}", dict(axis_values))

    def get_proof_settings(self):
        """Get the proof settings dictionary."""
        return self.data.get("proof_settings", {})

    def set_proof_settings(self, proof_settings):
        """Set the proof settings dictionary."""
        self._set_nested_value("proof_settings", dict(proof_settings))

    def set_pdf_output_custom_location(self, location):
        """Set custom PDF output location."""
        self._ensure_nested_structure(
            "pdf_output", {"use_custom_location": False, "custom_location": ""}
        )
        self._set_nested_value("pdf_output.custom_location", location, auto_save=False)

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

    # load_user_settings_file removed; use load_from_file directly

    def export_to_file(self, file_path):
        """Export current settings to a file."""
        return safe_json_save(self.data, file_path)


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

    # Consolidated setting type configuration
    _SETTING_TYPES = {
        "fontSize": lambda proof_key: get_proof_default_font_size(proof_key),
        "cols": lambda proof_key: (
            get_proof_by_storage_key(proof_key)["default_cols"]
            if get_proof_by_storage_key(proof_key)
            else 2
        ),
        "para": lambda proof_key: 5,
        "tracking": lambda proof_key: 0,
        "align": lambda proof_key: get_default_alignment_for_proof(proof_key),
    }

    def _get_setting_conditions(self):
        """Get setting application conditions."""
        return {
            "cols": lambda proof_key: proof_key not in self._COLUMN_EXCLUDED_PROOFS,
            "para": lambda proof_key: get_proof_by_settings_key(proof_key)
            and get_proof_by_settings_key(proof_key).get("has_paragraphs", False),
            "tracking": lambda proof_key: proof_supports_formatting(proof_key),
            "align": lambda proof_key: proof_supports_formatting(proof_key),
        }

    def _apply_settings_for_key(self, settings_key, proof_key):
        """Apply all applicable settings for a given key using consolidated logic."""
        conditions = self._get_setting_conditions()

        for setting_type, default_func in self._SETTING_TYPES.items():
            # Check if this setting type should be applied
            condition_func = conditions.get(setting_type)
            if condition_func and not condition_func(proof_key):
                continue

            setting_key_full = make_settings_key(settings_key, setting_type)
            if setting_key_full not in self.proof_settings:
                self.proof_settings[setting_key_full] = default_func(proof_key)

        # Category settings for applicable proofs
        if proof_key in ["filtered_character_set", "spacing_proof"]:
            for category_key, default_value in self._CATEGORY_DEFAULTS.items():
                setting_key_full = make_settings_key(settings_key, "cat", category_key)
                if setting_key_full not in self.proof_settings:
                    self.proof_settings[setting_key_full] = default_value

        # OpenType features
        for tag in self._get_font_features():
            if tag not in HIDDEN_FEATURES:
                feature_key = make_feature_key(settings_key, tag)
                if feature_key not in self.proof_settings:
                    self.proof_settings[feature_key] = tag in DEFAULT_ON_FEATURES

    def _get_font_features(self):
        """Get OpenType feature tags from the current font."""
        if not self.font_manager.fonts:
            return []
        try:
            font_path = self.font_manager.fonts[0]
            try:
                mtime = os.path.getmtime(font_path)
            except Exception:
                mtime = 0
            return list(_cached_list_ot_features(font_path, mtime))
        except Exception:
            return []

    def _initialize_proof_type_defaults(self, proof_key):
        """Initialize default settings for a specific proof type."""
        proof_info = get_proof_by_settings_key(proof_key)
        if proof_info is None:
            return
        self._apply_settings_for_key(proof_key, proof_key)

    def _feature_key(self, base_key, tag):
        """Build consistent OpenType feature storage key for a base/unique key."""
        return make_feature_key(base_key, tag)

    def _get_proof_key_for_identifier(self, proof_identifier):
        """Get proof key and font size key for a given proof identifier."""
        display_name_to_settings_key = get_proof_settings_mapping()

        if proof_identifier in display_name_to_settings_key:
            # Direct match
            proof_key = display_name_to_settings_key[proof_identifier]
            return proof_key, make_settings_key(proof_key, "fontSize")

        # Check for numbered variants
        for display_name, settings_key in display_name_to_settings_key.items():
            if proof_identifier.startswith(display_name):
                unique_key = create_unique_proof_key(proof_identifier)
                return settings_key, make_settings_key(unique_key, "fontSize")

        # Fallback
        proof_key = "basic_paragraph_small"
        unique_key = create_unique_proof_key(proof_identifier)
        return proof_key, make_settings_key(unique_key, "fontSize")

    def get_proof_font_size(self, proof_identifier):
        """Get font size for a specific proof from its settings."""
        proof_key, font_size_key = self._get_proof_key_for_identifier(proof_identifier)
        default_font_size = get_proof_default_font_size(proof_key)
        return self.proof_settings.get(font_size_key, default_font_size)

    def _init_proof_instance_settings(self, unique_key, base_proof_key, proof_info):
        """Initialize settings for a specific proof instance using consolidated logic."""
        self._apply_settings_for_key(unique_key, base_proof_key)

    def initialize_settings_for_proof(self, unique_proof_name, base_proof_type):
        """Initialize settings for a newly added proof instance."""
        try:
            if base_proof_type == "Show Baselines/Grid":
                return

            from config import resolve_base_proof_key

            _, base_proof_key = resolve_base_proof_key(base_proof_type)
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
        cols_key = make_settings_key(unique_key, "cols")
        para_key = make_settings_key(unique_key, "para")
        otf_prefix = get_otf_prefix(unique_key)

        result = {"cols": None, "paras": None, "otf": {}}

        # Get columns and paragraphs settings
        if cols_key in self.proof_settings:
            result["cols"] = self.proof_settings[cols_key]

        # Paragraphs only for proofs that declare has_paragraphs
        settings_proof = get_proof_by_settings_key(settings_key)
        if (
            settings_proof
            and settings_proof.get("has_paragraphs", False)
            and (para_key in self.proof_settings)
        ):
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

        for item in proof_options_items:
            if not item["Enabled"]:
                continue

            proof_name = item["Option"]
            unique_key = create_unique_proof_key(proof_name)

            # Determine base proof type via resolver
            from config import resolve_base_proof_key

            _, settings_key = resolve_base_proof_key(proof_name)
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

    def _build_numeric_settings_list(self, settings_key, lookup_key=None):
        """Build list of numeric settings for a proof using consolidated logic."""
        items = []
        lookup_key = lookup_key or settings_key
        storage_proof = get_proof_by_storage_key(lookup_key)
        settings_proof = get_proof_by_settings_key(lookup_key)

        # Define setting configurations with their display names and conditions
        setting_configs = [
            (
                "Font Size",
                "fontSize",
                True,
                lambda: get_proof_default_font_size(lookup_key),
            ),
            (
                "Columns",
                "cols",
                lookup_key not in self._COLUMN_EXCLUDED_PROOFS,
                lambda: storage_proof["default_cols"] if storage_proof else 2,
            ),
            (
                "Paragraphs",
                "para",
                settings_proof and settings_proof.get("has_paragraphs", False),
                lambda: 5,
            ),
            ("Tracking", "tracking", proof_supports_formatting(lookup_key), lambda: 0),
        ]

        for display_name, setting_type, condition, default_func in setting_configs:
            if condition:
                setting_key = make_settings_key(settings_key, setting_type)
                default_value = default_func()
                current_value = self.proof_settings.get(setting_key, default_value)
                items.append(
                    {
                        "Setting": display_name,
                        "Value": current_value,
                        "_key": setting_key,
                    }
                )

        return items

    def get_popover_settings_for_proof(self, proof_key):
        """Get settings data for popover display for a specific proof type."""
        return self._build_numeric_settings_list(proof_key)

    def get_popover_settings_for_proof_instance(self, unique_proof_key, base_proof_key):
        """Get settings data for popover display for a specific proof instance."""
        return self._build_numeric_settings_list(unique_proof_key, base_proof_key)

    def get_opentype_features_for_proof(self, proof_key):
        """Get OpenType features data for popover display for a specific proof type."""
        feature_items = []

        for tag in self._get_font_features():
            if tag in HIDDEN_FEATURES:
                continue

            feature_key = self._feature_key(proof_key, tag)

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
        align_key = make_settings_key(proof_key, "align")
        return self.proof_settings.get(
            align_key, get_default_alignment_for_proof(proof_key)
        )

    def set_alignment_value_for_proof(self, proof_key, align_value):
        """Set alignment value for a specific proof type."""
        if proof_supports_formatting(proof_key):
            self.proof_settings[make_settings_key(proof_key, "align")] = align_value

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
