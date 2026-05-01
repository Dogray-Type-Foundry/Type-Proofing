"""Tests for GSUB substitution extraction."""

import os

import pytest


FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "SetsGroteskXS-Regular.ttf",
)


pytestmark = pytest.mark.skipif(
    not os.path.exists(FONT_PATH),
    reason="SetsGroteskXS-Regular.ttf is not available",
)


def test_extracts_visible_substitution_features():
    from opentype_substitutions import get_substitution_features

    features = get_substitution_features(FONT_PATH)

    assert "aalt" not in features
    assert "calt" in features
    assert "ss01" in features


def test_substitution_payload_is_plain_data():
    from opentype_substitutions import get_font_substitutions

    data = get_font_substitutions(FONT_PATH)
    calt = next(feature for feature in data if feature["feature_tag"] == "calt")

    assert calt["output_glyphs"]
    assert all(isinstance(glyph, str) for glyph in calt["output_glyphs"])
    assert all(isinstance(entry["input_glyphs"], list) for entry in calt["entries"])
    assert all(isinstance(entry["output_glyphs"], list) for entry in calt["entries"])
