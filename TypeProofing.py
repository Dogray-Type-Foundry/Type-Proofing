#!/usr/bin/env python3
"""
Type Proofing Application - Main Entry Point

This is the main entry point for the font proofing application.
The application has been modularized into the following components:

- config.py: Configuration constants and settings management
- font_analysis.py: Font processing and character set analysis
- proof_generation.py: Proof generation functions and text processing
- ui_interface.py: User interface components and main application window
- utils.py: Core utility functions for file operations, validation, error handling
- ui_utils.py: UI-specific utilities and drawing helpers

Usage:
    python "Type Proofing.py"

Dependencies:
    - drawBot
    - fontTools
    - wordsiv
    - vanilla
    - AppKit/Foundation (macOS)
    - drawBotGrid (custom extension)
    - prooftexts (local module)
"""

import logging
from utils import log_error

# Configure logging
log = logging.getLogger("wordsiv")
log.setLevel(logging.ERROR)

# Import and run the main application
if __name__ == "__main__":
    try:
        from ui_interface import ProofWindow
        from PyObjCTools import AppHelper

        # Create and show the main window
        window = ProofWindow()

        # Start the application event loop
        AppHelper.runEventLoop()

    except ImportError as e:
        log_error(f"Import error: {e}")
    except KeyboardInterrupt:
        print("\nApplication interrupted by user.")
    except Exception as e:
        error_msg = f"Error starting application: {e}"
        import traceback

        log_error(error_msg, traceback.format_exc())
