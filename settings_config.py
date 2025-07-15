# Settings Configuration - Unified settings management

import json
import os
from app_config import SETTINGS_PATH
from proof_config import PROOF_REGISTRY, get_proof_display_names
from format_config import DEFAULT_PAGE_FORMAT


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
        from app_config import APP_VERSION

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
