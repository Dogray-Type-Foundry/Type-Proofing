"""Tests for settings.py — utility functions (path handling, validation, key construction)."""

import datetime
import os
import pytest
from unittest.mock import patch

from settings import (
    normalize_path,
    get_file_extension,
    is_valid_font_extension,
    make_safe_filename,
    format_file_size,
    clean_font_name,
    format_timestamp,
    is_valid_numeric_input,
    validate_setting_value,
    log_error,
    create_unique_proof_key,
    make_settings_key,
    make_feature_key,
)


# =============================================================================
# normalize_path
# =============================================================================


class TestNormalizePath:
    def test_empty_returns_empty(self):
        assert normalize_path("") == ""
        assert normalize_path(None) == ""

    def test_regular_path(self):
        result = normalize_path("/Users/test/font.otf")
        assert result == "/Users/test/font.otf"

    def test_tilde_expansion(self):
        result = normalize_path("~/fonts/test.otf")
        assert result.startswith("/")
        assert "~" not in result

    def test_file_url(self):
        result = normalize_path("file:///Users/test/font.otf")
        assert result == "/Users/test/font.otf"

    def test_font_specific_file_url(self):
        # font_specific path with file:// URL strips the scheme.
        # AppKit.NSURL is imported locally; our conftest mock makes it a MagicMock
        # which isn't a valid type for isinstance, so we patch AppKit in sys.modules
        # with a real NSURL class.
        import sys

        real_nsurl = type("NSURL", (), {})
        orig = sys.modules.get("AppKit")
        try:
            import types

            fake_appkit = types.ModuleType("AppKit")
            fake_appkit.NSURL = real_nsurl
            sys.modules["AppKit"] = fake_appkit
            result = normalize_path("file:///Users/test/font.otf", font_specific=True)
            assert result == "/Users/test/font.otf"
        finally:
            if orig is not None:
                sys.modules["AppKit"] = orig

    def test_font_specific_plain_path(self):
        import sys

        real_nsurl = type("NSURL", (), {})
        orig = sys.modules.get("AppKit")
        try:
            import types

            fake_appkit = types.ModuleType("AppKit")
            fake_appkit.NSURL = real_nsurl
            sys.modules["AppKit"] = fake_appkit
            result = normalize_path("/Users/test/font.otf", font_specific=True)
            assert result == "/Users/test/font.otf"
        finally:
            if orig is not None:
                sys.modules["AppKit"] = orig


# =============================================================================
# get_file_extension
# =============================================================================


class TestGetFileExtension:
    def test_otf(self):
        assert get_file_extension("font.otf") == ".otf"

    def test_ttf(self):
        assert get_file_extension("font.TTF") == ".ttf"

    def test_no_extension(self):
        assert get_file_extension("fontname") == ""

    def test_empty(self):
        assert get_file_extension("") == ""
        assert get_file_extension(None) == ""

    def test_dotfile(self):
        # os.path.splitext(".hidden") returns (".hidden", "")
        assert get_file_extension(".hidden") == ""


# =============================================================================
# is_valid_font_extension
# =============================================================================


class TestIsValidFontExtension:
    @pytest.mark.parametrize("ext", [".otf", ".ttf", ".woff", ".woff2"])
    def test_valid_extensions(self, ext):
        assert is_valid_font_extension(f"font{ext}") is True

    @pytest.mark.parametrize("ext", [".OTF", ".TTF", ".WOFF", ".WOFF2"])
    def test_case_insensitive(self, ext):
        assert is_valid_font_extension(f"font{ext}") is True

    @pytest.mark.parametrize("ext", [".txt", ".pdf", ".py", ".json", ""])
    def test_invalid_extensions(self, ext):
        assert is_valid_font_extension(f"font{ext}") is False


# =============================================================================
# make_safe_filename
# =============================================================================


class TestMakeSafeFilename:
    def test_clean_name_unchanged(self):
        assert make_safe_filename("MyFont") == "MyFont"

    def test_replaces_invalid_chars(self):
        result = make_safe_filename('Font<Name>:"/\\|?*')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_adds_extension(self):
        result = make_safe_filename("MyFont", ".pdf")
        assert result.endswith(".pdf")

    def test_does_not_double_extension(self):
        result = make_safe_filename("MyFont.pdf", ".pdf")
        assert result == "MyFont.pdf"

    def test_empty_returns_unnamed(self):
        assert make_safe_filename("") == "unnamed"
        assert make_safe_filename(None) == "unnamed"

    def test_truncates_long_names(self):
        long_name = "A" * 300
        result = make_safe_filename(long_name)
        assert len(result) <= 200


# =============================================================================
# format_file_size
# =============================================================================


class TestFormatFileSize:
    def test_zero(self):
        assert format_file_size(0) == "0 B"

    def test_bytes(self):
        assert format_file_size(500) == "500.0 B"

    def test_kilobytes(self):
        assert format_file_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_file_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_file_size(1024**3) == "1.0 GB"

    def test_fraction(self):
        result = format_file_size(1536)
        assert result == "1.5 KB"


# =============================================================================
# clean_font_name
# =============================================================================


class TestCleanFontName:
    def test_removes_regular(self):
        assert "Regular" not in clean_font_name("MyFont Regular")

    def test_removes_normal(self):
        assert "Normal" not in clean_font_name("MyFont Normal")

    def test_empty_returns_unnamed(self):
        assert clean_font_name("") == "Unnamed Font"
        assert clean_font_name(None) == "Unnamed Font"

    def test_clean_name_preserved(self):
        assert clean_font_name("Helvetica Bold") == "Helvetica Bold"


# =============================================================================
# format_timestamp
# =============================================================================


class TestFormatTimestamp:
    def test_custom_datetime(self):
        dt = datetime.datetime(2025, 3, 15, 14, 30)
        result = format_timestamp(dt)
        assert result == "2025-03-15_1430"

    def test_none_uses_now(self):
        result = format_timestamp()
        assert isinstance(result, str)
        assert "_" in result  # YYYY-MM-DD_HHMM format


# =============================================================================
# is_valid_numeric_input
# =============================================================================


class TestIsValidNumericInput:
    def test_integer(self):
        assert is_valid_numeric_input(42) is True

    def test_float(self):
        assert is_valid_numeric_input(3.14) is True

    def test_numeric_string(self):
        assert is_valid_numeric_input("42") is True

    def test_float_string(self):
        assert is_valid_numeric_input("3.14") is True

    def test_negative(self):
        assert is_valid_numeric_input("-5") is True

    def test_non_numeric_string(self):
        assert is_valid_numeric_input("abc") is False

    def test_none(self):
        assert is_valid_numeric_input(None) is False

    def test_empty_string(self):
        assert is_valid_numeric_input("") is False


# =============================================================================
# validate_setting_value
# =============================================================================


class TestValidateSettingValue:
    def test_tracking_accepts_float(self):
        valid, value, err = validate_setting_value("proof_tracking", 2.5)
        assert valid is True
        assert value == 2.5
        assert err is None

    def test_tracking_accepts_negative(self):
        valid, value, err = validate_setting_value("some_tracking", -3.0)
        assert valid is True
        assert value == -3.0

    def test_font_size_rejects_zero(self):
        valid, value, err = validate_setting_value("proof_fontSize", 0)
        assert valid is False

    def test_font_size_rejects_negative(self):
        valid, value, err = validate_setting_value("proof_fontSize", -5)
        assert valid is False

    def test_font_size_accepts_positive(self):
        valid, value, err = validate_setting_value("proof_fontSize", 12)
        assert valid is True
        assert value == 12

    def test_cols_converts_float_to_int(self):
        valid, value, err = validate_setting_value("proof_cols", 2.7)
        assert valid is True
        assert value == 2
        assert isinstance(value, int)

    def test_invalid_string(self):
        valid, value, err = validate_setting_value("proof_fontSize", "abc")
        assert valid is False


# =============================================================================
# create_unique_proof_key
# =============================================================================


class TestCreateUniqueProofKey:
    def test_basic_conversion(self):
        assert (
            create_unique_proof_key("Basic Paragraph Large") == "basic_paragraph_large"
        )

    def test_numbered_variant(self):
        assert (
            create_unique_proof_key("Basic Paragraph Large 2")
            == "basic_paragraph_large_2"
        )

    def test_slash_handling(self):
        assert create_unique_proof_key("Show Baselines/Grid") == "show_baselines_grid"

    def test_hyphen_handling(self):
        assert (
            create_unique_proof_key("Ar-Lat Mixed Paragraph Small")
            == "ar_lat_mixed_paragraph_small"
        )

    def test_already_snake_case(self):
        assert (
            create_unique_proof_key("basic_paragraph_small") == "basic_paragraph_small"
        )


# =============================================================================
# make_settings_key / make_feature_key
# =============================================================================


class TestMakeSettingsKey:
    def test_simple_key(self):
        key = make_settings_key("basic_paragraph_small", "fontSize")
        assert key == "basic_paragraph_small_fontSize"

    def test_with_category(self):
        key = make_settings_key("filtered_character_set", "cat", "uppercase_base")
        assert key == "filtered_character_set_cat_uppercase_base"

    def test_tracking_key(self):
        key = make_settings_key("custom_text", "tracking")
        assert key == "custom_text_tracking"

    def test_cols_key(self):
        key = make_settings_key("basic_paragraph_small", "cols")
        assert key == "basic_paragraph_small_cols"


class TestMakeFeatureKey:
    def test_feature_key(self):
        key = make_feature_key("basic_paragraph_small", "kern")
        assert key == "otf_basic_paragraph_small_kern"

    def test_feature_key_liga(self):
        key = make_feature_key("custom_text", "liga")
        assert key == "otf_custom_text_liga"
