"""Tests for fonts.py — character analysis, axis utilities, and FontManager."""

import pytest
from unittest.mock import MagicMock, patch

from fonts import (
    find_accented,
    categorize,
    check_arabic_support,
    get_charset_proof_categories,
    parse_axis_value,
    format_axis_values,
    parse_axis_values_string,
    product_dict,
    get_font_family_name,
)


# =============================================================================
# find_accented
# =============================================================================


class TestFindAccented:
    def test_plain_ascii_not_accented(self):
        assert find_accented("A") is False
        assert find_accented("z") is False
        assert find_accented("5") is False

    def test_accented_characters(self):
        assert find_accented("\u00e9") is True  # é
        assert find_accented("\u00e8") is True  # è
        assert find_accented("\u00f1") is True  # ñ
        assert find_accented("\u00fc") is True  # ü
        assert find_accented("\u010d") is True  # č

    def test_combined_diacritics(self):
        assert find_accented("\u00e0") is True  # à

    def test_non_latin_not_accented(self):
        # Arabic letters don't decompose to base + Mn
        assert find_accented("\u0628") is False  # ب


# =============================================================================
# categorize
# =============================================================================


class TestCategorize:
    @pytest.fixture
    def latin_cat(self):
        charset = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:;!?-$+="
        )
        return categorize(charset)

    def test_uppercase_populated(self, latin_cat):
        assert "A" in latin_cat["uniLu"]
        assert "Z" in latin_cat["uniLu"]

    def test_lowercase_populated(self, latin_cat):
        assert "a" in latin_cat["uniLl"]
        assert "z" in latin_cat["uniLl"]

    def test_digits_in_nd(self, latin_cat):
        for d in "0123456789":
            assert d in latin_cat["uniNd"]

    def test_punctuation(self, latin_cat):
        assert "." in latin_cat["uniPo"]
        assert "-" in latin_cat["uniPd"]

    def test_symbols(self, latin_cat):
        assert "$" in latin_cat["uniSc"]
        assert "+" in latin_cat["uniSm"]

    def test_uppercase_only_flag(self):
        cat = categorize("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        assert cat["uppercaseOnly"] is True
        assert cat["lowercaseOnly"] is False

    def test_lowercase_only_flag(self):
        cat = categorize("abcdefghijklmnopqrstuvwxyz")
        assert cat["lowercaseOnly"] is True
        assert cat["uppercaseOnly"] is False

    def test_mixed_case_flags(self, latin_cat):
        assert latin_cat["uppercaseOnly"] is False
        assert latin_cat["lowercaseOnly"] is False

    def test_base_vs_accented(self):
        charset = "ABCabc\u00e9\u00e8\u00c9"
        cat = categorize(charset)
        assert "A" in cat["uniLuBase"]
        assert "a" in cat["uniLlBase"]
        assert "\u00e9" in cat["accented"]
        assert "\u00e8" in cat["accented"]

    def test_latin_script_detection(self, latin_cat):
        assert "A" in latin_cat["latn"]
        assert "a" in latin_cat["latn"]

    def test_arabic_script_detection(self):
        charset = "\u0627\u0628\u062a\u062b\u062c\u062d\u062e\u062f\u0630\u0631\u0632"
        cat = categorize(charset)
        assert len(cat["arab"]) > 0

    def test_accented_plus_includes_non_template(self):
        # Characters in Lu/Ll but not in the basic A-Z/a-z templates
        charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ\u00c6\u00d8abcdefghijklmnopqrstuvwxyz\u00e6\u00f8\u00e9"
        cat = categorize(charset)
        # Æ, Ø, æ, ø are not in UPPER_TEMPLATE/LOWER_TEMPLATE and not accented
        # They should appear in accented_plus
        assert "\u00c6" in cat["accented_plus"] or "\u00f8" in cat["accented_plus"]

    def test_empty_charset(self):
        cat = categorize("")
        assert cat["uniLu"] == ""
        assert cat["uniLl"] == ""
        assert cat["uppercaseOnly"] is True  # Both are empty, so ""=="" is True
        assert cat["lowercaseOnly"] is True


# =============================================================================
# check_arabic_support
# =============================================================================


class TestCheckArabicSupport:
    def test_full_arabic_support(self):
        charset = (
            "\u0627\u0628\u062d\u062f\u0631\u0632\u0633\u0634"  # includes ب ا ح د ر
        )
        assert check_arabic_support(charset) is True

    def test_missing_chars(self):
        charset = "\u0627\u0628"  # Only alif and ba, missing ح د ر
        assert check_arabic_support(charset) is False

    def test_latin_only(self):
        assert check_arabic_support("ABCDEFGHIJKabcdefghijk") is False

    def test_empty(self):
        assert check_arabic_support("") is False


# =============================================================================
# get_charset_proof_categories
# =============================================================================


class TestGetCharsetProofCategories:
    def test_returns_all_category_keys(self, sample_cat):
        result = get_charset_proof_categories(sample_cat)
        assert "uppercase_base" in result
        assert "lowercase_base" in result
        assert "numbers_symbols" in result
        assert "punctuation" in result
        assert "accented" in result

    def test_uppercase_sorted_by_codepoint(self, sample_cat):
        result = get_charset_proof_categories(sample_cat)
        uc = result["uppercase_base"]
        assert uc == "".join(sorted(uc, key=ord))

    def test_lowercase_sorted_by_codepoint(self, sample_cat):
        result = get_charset_proof_categories(sample_cat)
        lc = result["lowercase_base"]
        assert lc == "".join(sorted(lc, key=ord))

    def test_numbers_symbols_combined(self, sample_cat):
        result = get_charset_proof_categories(sample_cat)
        ns = result["numbers_symbols"]
        # Should contain digits
        for d in "0123456789":
            assert d in ns
        # Should contain math symbols
        assert "+" in ns

    def test_punctuation_combined(self, sample_cat):
        result = get_charset_proof_categories(sample_cat)
        p = result["punctuation"]
        assert "." in p
        assert "-" in p


# =============================================================================
# parse_axis_value
# =============================================================================


class TestParseAxisValue:
    def test_integer_string(self):
        assert parse_axis_value("400") == 400
        assert isinstance(parse_axis_value("400"), int)

    def test_float_string(self):
        assert parse_axis_value("12.5") == 12.5
        assert isinstance(parse_axis_value("12.5"), float)

    def test_non_numeric_string(self):
        assert parse_axis_value("bold") == "bold"

    def test_negative(self):
        assert parse_axis_value("-10") == -10


# =============================================================================
# format_axis_values
# =============================================================================


class TestFormatAxisValues:
    def test_single_value(self):
        assert format_axis_values([400]) == "400"

    def test_multiple_values(self):
        assert format_axis_values([100, 400, 700]) == "100,400,700"

    def test_float_values(self):
        assert format_axis_values([12.5, 100]) == "12.5,100"

    def test_empty(self):
        assert format_axis_values([]) == ""


# =============================================================================
# parse_axis_values_string
# =============================================================================


class TestParseAxisValuesString:
    def test_comma_separated_ints(self):
        assert parse_axis_values_string("100,400,700") == [100, 400, 700]

    def test_with_spaces(self):
        assert parse_axis_values_string("100, 400, 700") == [100, 400, 700]

    def test_float_values(self):
        result = parse_axis_values_string("12.5, 100")
        assert result == [12.5, 100]

    def test_empty_string(self):
        assert parse_axis_values_string("") == []

    def test_round_trip(self):
        original = [100, 400, 700]
        formatted = format_axis_values(original)
        parsed = parse_axis_values_string(formatted)
        assert parsed == original


# =============================================================================
# product_dict
# =============================================================================


class TestProductDict:
    def test_single_axis(self):
        result = list(product_dict(wght=[400, 700]))
        assert result == [{"wght": 400}, {"wght": 700}]

    def test_two_axes(self):
        result = list(product_dict(wght=[400, 700], wdth=[75, 100]))
        assert len(result) == 4
        assert {"wght": 400, "wdth": 75} in result
        assert {"wght": 700, "wdth": 100} in result

    def test_empty(self):
        result = list(product_dict())
        assert result == [{}]

    def test_single_value_axis(self):
        result = list(product_dict(wght=[400]))
        assert result == [{"wght": 400}]


# =============================================================================
# get_font_family_name
# =============================================================================


class TestGetFontFamilyName:
    def test_with_hyphen(self):
        assert get_font_family_name("/path/to/MyFont-Regular.otf") == "MyFont"

    def test_without_hyphen(self):
        assert get_font_family_name("/path/to/MyFont.otf") == "MyFont"

    def test_nested_path(self):
        assert get_font_family_name("/a/b/c/Source Sans-Bold.ttf") == "Source Sans"

    def test_just_filename(self):
        assert get_font_family_name("Font-Italic.otf") == "Font"


# =============================================================================
# FontManager (basic tests with mocking)
# =============================================================================


class TestFontManager:
    @pytest.fixture
    def fm(self):
        from fonts import FontManager

        return FontManager(settings=None)

    def test_initial_state(self, fm):
        assert fm.fonts == ()
        assert fm.font_info == {}
        assert fm.axis_values_by_font == {}

    def test_get_all_axes_empty(self, fm):
        assert fm.get_all_axes() == []

    def test_remove_from_empty(self, fm):
        fm.remove_fonts_by_indices([0])  # Should not crash
        assert fm.fonts == ()
