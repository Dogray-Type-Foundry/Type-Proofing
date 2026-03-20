"""Shared fixtures and drawBot mocking for the Type Proofing test suite."""

import sys
import os
import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# drawBot / Vanilla / AppKit stubs — must be installed before any project
# module is imported because fonts.py, proof.py, ui.py, markup_parser.py and
# others do ``import drawBot as db`` at module level.
# ---------------------------------------------------------------------------

_drawbot_mock = MagicMock()
_drawbot_mock.FormattedString = MagicMock
_drawbot_mock.listFontVariations.return_value = {}
_drawbot_mock.listOpenTypeFeatures.return_value = []
_drawbot_mock.fontContainsCharacters.return_value = True
_drawbot_mock.font.return_value = "MockFont-Regular"
_drawbot_mock.pageCount.return_value = 1
_drawbot_mock.width.return_value = 842
_drawbot_mock.height.return_value = 595

sys.modules.setdefault("drawBot", _drawbot_mock)
sys.modules.setdefault("drawBotGrid", MagicMock())
sys.modules.setdefault("vanilla", MagicMock())
sys.modules.setdefault("AppKit", MagicMock())
sys.modules.setdefault("Foundation", MagicMock())
sys.modules.setdefault("objc", MagicMock())
sys.modules.setdefault("PyObjCTools", MagicMock())
sys.modules.setdefault("PyObjCTools.AppHelper", MagicMock())

# wordsiv — mock it to avoid slow vocabulary loading that can hang tests.
_wordsiv_mock = MagicMock()
_wordsiv_mock.WordSiv.return_value = MagicMock(
    paragraph=MagicMock(return_value="Mock paragraph text."),
    sentence=MagicMock(return_value="Mock sentence."),
    word=MagicMock(return_value="mock"),
)
_wordsiv_mock.Vocab = MagicMock
sys.modules.setdefault("wordsiv", _wordsiv_mock)

# Ensure the project root is on the path so imports like ``import config`` work.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_settings_path(tmp_path):
    """Return a temporary path for settings JSON."""
    return str(tmp_path / "test-prefs.json")


@pytest.fixture
def default_settings(tmp_settings_path):
    """Return a Settings instance backed by a temp file."""
    from settings import Settings

    return Settings(settings_path=tmp_settings_path)


@pytest.fixture
def sample_cat():
    """Return a sample categorize() output for a basic Latin font."""
    return {
        "uniLu": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "uniLl": "abcdefghijklmnopqrstuvwxyz",
        "uniLuBase": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "uniLlBase": "abcdefghijklmnopqrstuvwxyz",
        "uniLo": "",
        "uniPo": ".,:;!?",
        "uniPc": "_",
        "uniPd": "-",
        "uniPs": "([{",
        "uniPe": ")]}",
        "uniPi": "\u201c\u2018",
        "uniPf": "\u201d\u2019",
        "uniSm": "+-=<>",
        "uniSc": "$\u20ac\u00a3",
        "uniNd": "0123456789",
        "uniNo": "",
        "uniSo": "",
        "accented": "\u00e9\u00e8\u00ea\u00eb\u00e0\u00e1\u00e2\u00e4",
        "accented_plus": "\u00e9\u00e8\u00ea\u00eb\u00e0\u00e1\u00e2\u00e4",
        "latn": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "arab": "",
        "fa": "",
        "ar": "",
        "arabTyped": "",
        "arfaDualJoin": "",
        "arfaRightJoin": "",
        "uppercaseOnly": False,
        "lowercaseOnly": False,
    }


@pytest.fixture
def sample_arabic_cat():
    """Return a sample categorize() output for a font with Arabic support."""
    return {
        "uniLu": "",
        "uniLl": "",
        "uniLuBase": "",
        "uniLlBase": "",
        "uniLo": "\u0627\u0628\u062a\u062b\u062c\u062d\u062e\u062f\u0630\u0631\u0632\u0633",
        "uniPo": "",
        "uniPc": "",
        "uniPd": "",
        "uniPs": "",
        "uniPe": "",
        "uniPi": "",
        "uniPf": "",
        "uniSm": "",
        "uniSc": "",
        "uniNd": "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
        "uniNo": "",
        "uniSo": "",
        "accented": "",
        "accented_plus": "",
        "latn": "",
        "arab": "\u0627\u0628\u062a\u062b\u062c\u062d\u062e\u062f\u0630\u0631\u0632\u0633",
        "fa": "\u0627\u0628\u062a\u062b\u062c\u062d\u062e\u062f",
        "ar": "\u0627\u0628\u062a\u062b\u062c\u062d\u062e\u062f\u0630\u0631\u0632\u0633",
        "arabTyped": "\u0627\u0628\u062a\u062b\u062c\u062d\u062e\u062f\u0630\u0631\u0632\u0633",
        "arfaDualJoin": "\u0628\u062a\u062b\u062c\u062d\u062e\u0633",
        "arfaRightJoin": "\u0627\u062f\u0630\u0631\u0632",
        "uppercaseOnly": False,
        "lowercaseOnly": False,
    }
