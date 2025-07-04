# Configuration and Constants for Font Proofing Application

import json
import os
from pathlib import Path

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Store settings file next to the script
SETTINGS_PATH = os.path.join(SCRIPT_DIR, "drawbot_proof_settings.json")
WINDOW_TITLE = "DrawBot Proof Generator with Preview"

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
        self.data = self.load()

    def load(self):
        """Load settings from file."""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
                return {}
        return {}

    def save(self):
        """Save settings to file."""
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.data, f, indent=2)
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

    def get_font_size(self, size_type):
        """Get font size by type."""
        size_map = {
            "charset": ("charsetFontSize", charsetFontSize),
            "spacing": ("spacingFontSize", spacingFontSize),
            "large": ("largeTextFontSize", largeTextFontSize),
            "small": ("smallTextFontSize", smallTextFontSize),
        }
        key, default = size_map.get(size_type, (size_type, None))
        return self.get(key, default)

    def set_font_size(self, size_type, value):
        """Set font size by type."""
        size_map = {
            "charset": "charsetFontSize",
            "spacing": "spacingFontSize",
            "large": "largeTextFontSize",
            "small": "smallTextFontSize",
        }
        key = size_map.get(size_type, size_type)
        self.set(key, value)

    def get_proof_option(self, proof_name):
        """Get proof option by name."""
        return self.get(proof_name, False)

    def set_proof_option(self, proof_name, enabled):
        """Set proof option by name."""
        self.set(proof_name, enabled)
