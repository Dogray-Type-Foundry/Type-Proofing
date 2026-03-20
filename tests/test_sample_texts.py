"""Tests for sample_texts.py and script_texts.py — text constant integrity."""

import pytest
from sample_texts import (
    bigMixedText,
    bigLowerText,
    bigUpperText,
    smallMixedText,
    smallLowerText,
    smallUpperText,
    bigRandomNumbers,
    additionalSmallText,
)
from script_texts import (
    arabicVocalization,
    arabicLatinMixed,
    arabicFarsiUrduNumbers,
)


# =============================================================================
# sample_texts constants
# =============================================================================


class TestSampleTexts:
    def test_big_mixed_text_non_empty(self):
        assert len(bigMixedText) > 100

    def test_big_lower_text_non_empty(self):
        assert len(bigLowerText) > 100

    def test_big_upper_text_non_empty(self):
        assert len(bigUpperText) > 100

    def test_small_mixed_text_non_empty(self):
        assert len(smallMixedText) > 50

    def test_small_lower_text_non_empty(self):
        assert len(smallLowerText) > 50

    def test_small_upper_text_non_empty(self):
        assert len(smallUpperText) > 50

    def test_big_random_numbers_non_empty(self):
        assert len(bigRandomNumbers) > 10

    def test_additional_small_text_non_empty(self):
        assert len(additionalSmallText) > 10

    def test_big_lower_is_lowercase(self):
        # Most alphabetic chars should be lowercase
        alpha = [c for c in bigLowerText if c.isalpha()]
        lower = [c for c in alpha if c.islower()]
        ratio = len(lower) / len(alpha) if alpha else 0
        assert ratio > 0.95, f"Only {ratio:.0%} lowercase"

    def test_big_upper_is_uppercase(self):
        alpha = [c for c in bigUpperText if c.isalpha()]
        upper = [c for c in alpha if c.isupper()]
        ratio = len(upper) / len(alpha) if alpha else 0
        assert ratio > 0.95, f"Only {ratio:.0%} uppercase"

    def test_big_mixed_has_both_cases(self):
        has_upper = any(c.isupper() for c in bigMixedText)
        has_lower = any(c.islower() for c in bigMixedText)
        assert has_upper and has_lower

    def test_big_random_numbers_contains_digits(self):
        digits = [c for c in bigRandomNumbers if c.isdigit()]
        assert len(digits) > 10


# =============================================================================
# script_texts constants
# =============================================================================


class TestScriptTexts:
    def test_arabic_vocalization_non_empty(self):
        assert len(arabicVocalization) > 100

    def test_arabic_latin_mixed_non_empty(self):
        assert len(arabicLatinMixed) > 100

    def test_arabic_farsi_urdu_numbers_non_empty(self):
        assert len(arabicFarsiUrduNumbers) > 10

    def test_arabic_vocalization_has_arabic(self):
        has_arabic = any("\u0600" <= c <= "\u06ff" for c in arabicVocalization)
        assert has_arabic

    def test_arabic_latin_mixed_has_both_scripts(self):
        has_arabic = any("\u0600" <= c <= "\u06ff" for c in arabicLatinMixed)
        has_latin = any(c.isascii() and c.isalpha() for c in arabicLatinMixed)
        assert has_arabic and has_latin

    def test_arabic_numbers_has_arabic_digits(self):
        # Arabic-Indic digits: U+0660-U+0669
        has_arabic_digits = any(
            "\u0660" <= c <= "\u0669" for c in arabicFarsiUrduNumbers
        )
        assert has_arabic_digits
