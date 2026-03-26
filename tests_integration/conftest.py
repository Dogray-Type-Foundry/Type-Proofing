"""Shared fixtures for integration tests — using REAL libraries, no mocks.

NOTE: These tests must be run separately from the unit tests in tests/,
because the unit-test conftest installs sys.modules mocks that conflict
with the real libraries used here.

    python3 -m pytest tests_integration/       # integration only
    python3 -m pytest tests/                   # unit only
"""

import os
import sys
import importlib
import tempfile
from unittest.mock import MagicMock

import pytest

# Ensure the python/ directory is on the path.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

# ---------------------------------------------------------------------------
# Evict any MagicMock stubs that the unit-test conftest.py may have installed
# so that integration tests always use real libraries.
# ---------------------------------------------------------------------------
_REAL_MODULES = [
    "drawBot",
    "drawBotGrid",
    "vanilla",
    "AppKit",
    "Foundation",
    "objc",
    "PyObjCTools",
    "PyObjCTools.AppHelper",
    "wordsiv",
]

for _mod_name in _REAL_MODULES:
    _existing = sys.modules.get(_mod_name)
    if _existing is not None and isinstance(_existing, MagicMock):
        del sys.modules[_mod_name]

# Force-reload project modules that may have cached mock references.
_APP_MODULES = [
    "fonts",
    "proof",
    "markup_parser",
    "config",
    "settings",
    "sample_texts",
    "script_texts",
]
for _mod_name in _APP_MODULES:
    if _mod_name in sys.modules:
        importlib.reload(sys.modules[_mod_name])

# Paths to real font files shipped with the project.
SETGROTESK_VF = os.path.join(PROJECT_ROOT, "SetGroteskVF.ttf")
ADOBE_BLANK = os.path.join(PROJECT_ROOT, "AdobeBlank.otf")


@pytest.fixture
def vf_font_path():
    """Path to the SetGroteskVF variable font (wght + opsz, 482 chars)."""
    assert os.path.isfile(SETGROTESK_VF), f"Missing test font: {SETGROTESK_VF}"
    return SETGROTESK_VF


@pytest.fixture
def blank_font_path():
    """Path to AdobeBlank (static, massive cmap, all blank outlines)."""
    assert os.path.isfile(ADOBE_BLANK), f"Missing test font: {ADOBE_BLANK}"
    return ADOBE_BLANK


@pytest.fixture
def tmp_settings_path(tmp_path):
    """Temporary path for a settings JSON file."""
    return str(tmp_path / "integration-prefs.json")


@pytest.fixture
def tmp_pdf_path(tmp_path):
    """Temporary path for a PDF output file."""
    return str(tmp_path / "test_output.pdf")
