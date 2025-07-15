# Application Configuration - Core app constants and paths

import os

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Store settings file in user's home directory
SETTINGS_PATH = os.path.expanduser("~/.type-proofing-prefs.json")
WINDOW_TITLE = "Type Proofing"

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


# Application version
APP_VERSION = "1.0"
