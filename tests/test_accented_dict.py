"""Tests for accented_dictionary.py — word lists and lookup functions."""

import pytest
from accented_dictionary import (
    accentedDict,
    get_accented_words,
    get_accented_characters,
    get_random_accented_words,
)


class TestAccentedDictionary:
    def test_dict_not_empty(self):
        assert len(accentedDict) > 0

    def test_dict_has_common_accented_chars(self):
        for char in ["\u00e9", "\u00f1", "\u00fc", "\u00e0", "\u00e8"]:  # é ñ ü à è
            assert char in accentedDict, f"Missing {char}"

    def test_all_keys_are_single_chars_or_short(self):
        for key in accentedDict:
            assert len(key) <= 3  # Some digraphs like ij, š' exist

    def test_all_values_are_sequences(self):
        for key, value in accentedDict.items():
            assert isinstance(value, (list, tuple)), f"{key} value is {type(value)}"

    def test_values_are_non_empty(self):
        for key, value in accentedDict.items():
            assert len(value) > 0, f"{key} has empty word list"


class TestGetAccentedWords:
    def test_known_character(self):
        words = get_accented_words("\u00e9")  # é
        assert len(words) > 0
        assert all(isinstance(w, str) for w in words)

    def test_words_contain_character(self):
        char = "\u00e9"
        words = get_accented_words(char)
        # At least some words should contain the accented character
        found = any(char in w for w in words)
        assert found, f"No words contain '{char}'"

    def test_unknown_character(self):
        words = get_accented_words("X")
        assert words == [] or words == ()

    def test_returns_consistent_type(self):
        words = get_accented_words("\u00e9")
        assert isinstance(words, (list, tuple))


class TestGetAccentedCharacters:
    def test_returns_list(self):
        chars = get_accented_characters()
        assert isinstance(chars, list)

    def test_matches_dict_keys(self):
        chars = get_accented_characters()
        assert set(chars) == set(accentedDict.keys())

    def test_not_empty(self):
        assert len(get_accented_characters()) > 0


class TestGetRandomAccentedWords:
    def test_returns_words(self):
        words = get_random_accented_words(10)
        assert len(words) == 10

    def test_respects_count(self):
        words = get_random_accented_words(5)
        assert len(words) == 5

    def test_returns_strings(self):
        words = get_random_accented_words(10)
        assert all(isinstance(w, str) for w in words)

    def test_large_count_clamped(self):
        # Requesting more than available should not crash
        words = get_random_accented_words(100000)
        assert len(words) > 0
