"""Tests for settings.py — Settings class (JSON persistence, defaults, merge, etc.)."""

import json
import os
import pytest

from settings import Settings
from config import (
    APP_VERSION,
    DEFAULT_PAGE_FORMAT,
    PROOF_REGISTRY,
    get_proof_display_names,
)


# =============================================================================
# Settings initialization and defaults
# =============================================================================


class TestSettingsDefaults:
    def test_creates_default_structure(self, default_settings):
        data = default_settings.data
        assert "version" in data
        assert "fonts" in data
        assert "proof_options" in data
        assert "proof_settings" in data
        assert "proof_order" in data
        assert "pdf_output" in data
        assert "page_format" in data

    def test_default_version(self, default_settings):
        assert default_settings.data["version"] == APP_VERSION

    def test_default_fonts_empty(self, default_settings):
        assert default_settings.data["fonts"]["paths"] == []
        assert default_settings.data["fonts"]["axis_values"] == {}

    def test_default_page_format(self, default_settings):
        assert default_settings.data["page_format"] == DEFAULT_PAGE_FORMAT

    def test_default_proof_options_all_false(self, default_settings):
        opts = default_settings.data["proof_options"]
        assert opts["show_baselines"] is False
        for key in PROOF_REGISTRY:
            assert opts[key] is False

    def test_default_proof_order_matches_registry(self, default_settings):
        order = default_settings.data["proof_order"]
        expected = get_proof_display_names(include_arabic=True)
        assert order == expected

    def test_default_pdf_output(self, default_settings):
        pdf = default_settings.data["pdf_output"]
        assert pdf["use_custom_location"] is False
        assert pdf["custom_location"] == ""


# =============================================================================
# Save and load round-trip
# =============================================================================


class TestSettingsSaveLoad:
    def test_save_creates_file(self, tmp_settings_path):
        s = Settings(settings_path=tmp_settings_path)
        s.save()
        assert os.path.exists(tmp_settings_path)

    def test_round_trip(self, tmp_settings_path):
        s = Settings(settings_path=tmp_settings_path)
        s.set("page_format", "A3Landscape")
        s.save()

        s2 = Settings(settings_path=tmp_settings_path)
        assert s2.get("page_format") == "A3Landscape"

    def test_saves_valid_json(self, tmp_settings_path):
        s = Settings(settings_path=tmp_settings_path)
        s.save()
        with open(tmp_settings_path, "r") as f:
            data = json.load(f)
        assert isinstance(data, dict)


# =============================================================================
# get / set / update
# =============================================================================


class TestSettingsGetSet:
    def test_get_existing_key(self, default_settings):
        assert default_settings.get("page_format") == DEFAULT_PAGE_FORMAT

    def test_get_missing_key_default(self, default_settings):
        assert default_settings.get("nonexistent", "fallback") == "fallback"

    def test_set_and_get(self, default_settings):
        default_settings.set("custom_key", 42)
        assert default_settings.get("custom_key") == 42

    def test_update_multiple(self, default_settings):
        default_settings.update({"key_a": 1, "key_b": 2})
        assert default_settings.get("key_a") == 1
        assert default_settings.get("key_b") == 2


# =============================================================================
# Nested value accessors
# =============================================================================


class TestNestedValues:
    def test_get_nested_value(self, default_settings):
        val = default_settings._get_nested_value("fonts.paths", [])
        assert val == []

    def test_set_nested_value(self, tmp_settings_path):
        s = Settings(settings_path=tmp_settings_path)
        s._set_nested_value("fonts.paths", ["/test/font.otf"], auto_save=False)
        assert s._get_nested_value("fonts.paths") == ["/test/font.otf"]

    def test_get_nested_missing_returns_default(self, default_settings):
        val = default_settings._get_nested_value("nonexistent.path", "default")
        assert val == "default"


# =============================================================================
# Proof option accessors
# =============================================================================


class TestProofOptions:
    def test_get_default_false(self, default_settings):
        assert default_settings.get_proof_option("filtered_character_set") is False

    def test_set_and_get(self, default_settings):
        default_settings.set_proof_option("filtered_character_set", True)
        assert default_settings.get_proof_option("filtered_character_set") is True

    def test_unknown_option_default(self, default_settings):
        assert default_settings.get_proof_option("nonexistent") is False


# =============================================================================
# Proof order
# =============================================================================


class TestProofOrder:
    def test_get_default_order(self, default_settings):
        order = default_settings.get_proof_order()
        assert isinstance(order, list)
        assert len(order) > 0

    def test_set_custom_order(self, default_settings):
        custom = ["Proof A", "Proof B"]
        default_settings.set_proof_order(custom)
        assert default_settings.get_proof_order() == custom

    def test_set_order_is_copy(self, default_settings):
        custom = ["A", "B"]
        default_settings.set_proof_order(custom)
        custom.append("C")
        assert default_settings.get_proof_order() == ["A", "B"]


# =============================================================================
# Page format
# =============================================================================


class TestPageFormat:
    def test_get_default(self, default_settings):
        assert default_settings.get_page_format() == DEFAULT_PAGE_FORMAT

    def test_set_and_get(self, default_settings):
        default_settings.set_page_format("A3Landscape")
        assert default_settings.get_page_format() == "A3Landscape"


# =============================================================================
# Font management
# =============================================================================


class TestFontSettings:
    def test_get_empty_fonts(self, default_settings):
        assert default_settings.get_fonts() == []

    def test_set_and_get_fonts(self, default_settings):
        paths = ["/path/to/font1.otf", "/path/to/font2.ttf"]
        default_settings.set_fonts(paths)
        assert default_settings.get_fonts() == paths

    def test_get_font_axis_values_empty(self, default_settings):
        assert default_settings.get_font_axis_values("/nonexistent.otf") == {}

    def test_set_and_get_axis_values(self, default_settings):
        values = {"wght": [400, 700], "wdth": [75, 100, 125]}
        default_settings.set_font_axis_values("/test.otf", values)
        assert default_settings.get_font_axis_values("/test.otf") == values


# =============================================================================
# Proof settings
# =============================================================================


class TestProofSettings:
    def test_get_empty(self, default_settings):
        assert default_settings.get_proof_settings() == {}

    def test_set_and_get(self, default_settings):
        settings = {"some_key": 42, "other_key": "value"}
        default_settings.set_proof_settings(settings)
        assert default_settings.get_proof_settings() == settings


# =============================================================================
# PDF output
# =============================================================================


class TestPdfOutput:
    def test_set_custom_location(self, default_settings):
        default_settings.set_pdf_output_custom_location("/custom/path")
        loc = default_settings._get_nested_value("pdf_output.custom_location")
        assert loc == "/custom/path"


# =============================================================================
# Reset and export/import
# =============================================================================


class TestResetAndExport:
    def test_reset_to_defaults(self, tmp_settings_path):
        s = Settings(settings_path=tmp_settings_path)
        s.set("page_format", "A3Landscape")
        s.reset_to_defaults()
        assert s.get("page_format") == DEFAULT_PAGE_FORMAT

    def test_export_to_file(self, default_settings, tmp_path):
        export_path = str(tmp_path / "exported.json")
        result = default_settings.export_to_file(export_path)
        assert result is True
        assert os.path.exists(export_path)
        with open(export_path) as f:
            data = json.load(f)
        assert data["page_format"] == DEFAULT_PAGE_FORMAT

    def test_load_from_file(self, tmp_settings_path, tmp_path):
        # Create source file
        source = str(tmp_path / "source.json")
        data = {"page_format": "LetterLandscape", "version": APP_VERSION}
        with open(source, "w") as f:
            json.dump(data, f)

        s = Settings(settings_path=tmp_settings_path)
        result = s.load_from_file(source)
        assert result is True
        assert s.get("page_format") == "LetterLandscape"

    def test_load_from_nonexistent_file(self, default_settings):
        result = default_settings.load_from_file("/nonexistent/path.json")
        assert result is False


# =============================================================================
# Merge logic
# =============================================================================


class TestSettingsMerge:
    def test_merge_preserves_user_values(self, tmp_settings_path, tmp_path):
        # Write a partial settings file
        partial = {
            "page_format": "A3Landscape",
            "version": APP_VERSION,
        }
        source = str(tmp_path / "partial.json")
        with open(source, "w") as f:
            json.dump(partial, f)

        s = Settings(settings_path=tmp_settings_path)
        s.load_from_file(source)
        assert s.get("page_format") == "A3Landscape"
        # Defaults should fill in missing keys
        assert "fonts" in s.data
        assert "proof_options" in s.data

    def test_merge_dict_recursive(self, default_settings):
        d1 = {"a": {"b": 1, "c": 2}}
        d2 = {"a": {"c": 3, "d": 4}}
        result = default_settings._merge_dict(d1, d2)
        assert result == {"a": {"b": 1, "c": 3, "d": 4}}


# =============================================================================
# Validate fonts
# =============================================================================


class TestValidateFonts:
    def test_empty_fonts_valid(self, default_settings):
        data = {"fonts": {"paths": []}}
        assert default_settings._validate_fonts(data) is True

    def test_nonexistent_fonts_invalid(self, default_settings):
        data = {"fonts": {"paths": ["/nonexistent/font.otf"]}}
        assert default_settings._validate_fonts(data) is False

    def test_existing_font_valid(self, default_settings, tmp_path):
        font_path = str(tmp_path / "test.otf")
        with open(font_path, "w") as f:
            f.write("fake font")
        data = {"fonts": {"paths": [font_path]}}
        assert default_settings._validate_fonts(data) is True

    def test_no_fonts_key(self, default_settings):
        data = {}
        assert default_settings._validate_fonts(data) is True
