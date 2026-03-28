"""Tests for config.py — application constants, proof registry, and helper functions."""

import pytest
from config import (
    PROOF_REGISTRY,
    APP_VERSION,
    DEFAULT_PAGE_FORMAT,
    PAGE_FORMAT_OPTIONS,
    PAGE_DIMENSIONS,
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
    FsSelection,
    AR_TEMPLATE,
    FA_TEMPLATE,
    ARFA_DUAL_JOIN,
    ARFA_RIGHT_JOIN,
    filter_visible_features,
    get_proof_display_names,
    resolve_base_proof_key,
    get_proof_settings_mapping,
    get_proof_default_columns,
    get_proof_paragraph_settings,
    get_proof_by_display_name,
    get_proof_by_settings_key,
    get_proof_by_storage_key,
    get_arabic_proof_display_names,
    get_base_proof_display_names,
    get_proof_default_font_size,
    proof_supports_formatting,
    get_proof_info,
    get_display_name,
    get_otf_prefix,
    get_default_alignment_for_proof,
    proof_has_custom_text,
    proof_has_categories,
    proof_is_multi_style,
    get_text_proof_config,
    resolve_character_set_by_key,
    load_arabic_texts,
)


# =============================================================================
# Constants integrity
# =============================================================================


class TestConstants:
    def test_app_version_format(self):
        parts = APP_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_default_page_format_in_options(self):
        assert DEFAULT_PAGE_FORMAT in PAGE_FORMAT_OPTIONS

    def test_page_dimensions_match_options(self):
        for fmt in PAGE_FORMAT_OPTIONS:
            assert fmt in PAGE_DIMENSIONS
            w, h = PAGE_DIMENSIONS[fmt]
            assert w > 0 and h > 0

    def test_page_format_dimensions_match_orientation(self):
        for fmt, (w, h) in PAGE_DIMENSIONS.items():
            if "Landscape" in fmt:
                assert w > h, f"{fmt} should be landscape: {w}x{h}"
            elif "Portrait" in fmt:
                assert h > w, f"{fmt} should be portrait: {w}x{h}"

    def test_default_on_features_are_strings(self):
        for feat in DEFAULT_ON_FEATURES:
            assert isinstance(feat, str)
            assert len(feat) == 4

    def test_hidden_features_are_strings(self):
        for feat in HIDDEN_FEATURES:
            assert isinstance(feat, str)
            assert len(feat) == 4

    def test_fs_selection_bits(self):
        assert FsSelection.ITALIC == 1
        assert FsSelection.BOLD == 32
        assert FsSelection.REGULAR == 64

    def test_arabic_templates_non_empty(self):
        assert len(AR_TEMPLATE) > 0
        assert len(FA_TEMPLATE) > 0
        assert len(ARFA_DUAL_JOIN) > 0
        assert len(ARFA_RIGHT_JOIN) > 0


# =============================================================================
# PROOF_REGISTRY structure
# =============================================================================


class TestProofRegistry:
    REQUIRED_FIELDS = {
        "display_name",
        "is_arabic",
        "has_settings",
        "default_cols",
        "default_size",
    }

    def test_registry_not_empty(self):
        assert len(PROOF_REGISTRY) > 0

    def test_all_entries_have_required_fields(self):
        for key, info in PROOF_REGISTRY.items():
            missing = self.REQUIRED_FIELDS - set(info.keys())
            assert not missing, f"{key} missing fields: {missing}"

    def test_display_names_are_unique(self):
        names = [info["display_name"] for info in PROOF_REGISTRY.values()]
        assert len(names) == len(set(names))

    def test_keys_are_snake_case(self):
        import re

        for key in PROOF_REGISTRY:
            assert re.match(r"^[a-z][a-z0-9_]*$", key), f"Key not snake_case: {key}"

    def test_default_cols_positive(self):
        for key, info in PROOF_REGISTRY.items():
            assert info["default_cols"] > 0, f"{key} has invalid default_cols"

    def test_default_size_positive(self):
        for key, info in PROOF_REGISTRY.items():
            assert info["default_size"] > 0, f"{key} has invalid default_size"

    def test_text_config_structure(self):
        for key, info in PROOF_REGISTRY.items():
            text_config = info.get("text")
            if text_config is not None:
                assert (
                    "character_set_key" in text_config
                ), f"{key} text config missing character_set_key"
                assert (
                    "default_paragraphs" in text_config
                ), f"{key} text config missing default_paragraphs"

    def test_expected_proof_count(self):
        assert len(PROOF_REGISTRY) == 21


# =============================================================================
# filter_visible_features
# =============================================================================


class TestFilterVisibleFeatures:
    def test_filters_hidden(self):
        tags = ["kern", "liga", "init", "medi", "calt"]
        result = filter_visible_features(tags)
        assert "kern" in result
        assert "liga" in result
        assert "calt" in result
        assert "init" not in result
        assert "medi" not in result

    def test_empty_input(self):
        assert filter_visible_features([]) == []

    def test_no_hidden(self):
        tags = ["kern", "liga", "calt"]
        assert filter_visible_features(tags) == tags

    def test_all_hidden(self):
        tags = list(HIDDEN_FEATURES)
        assert filter_visible_features(tags) == []


# =============================================================================
# get_proof_display_names
# =============================================================================


class TestGetProofDisplayNames:
    def test_returns_list(self):
        result = get_proof_display_names()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_includes_arabic_by_default(self):
        result = get_proof_display_names()
        arabic_names = get_arabic_proof_display_names()
        for name in arabic_names:
            assert name in result

    def test_excludes_arabic_when_requested(self):
        result = get_proof_display_names(include_arabic=False)
        arabic_names = get_arabic_proof_display_names()
        for name in arabic_names:
            assert name not in result

    def test_all_names_from_registry(self):
        result = get_proof_display_names()
        all_display_names = {info["display_name"] for info in PROOF_REGISTRY.values()}
        for name in result:
            assert name in all_display_names


# =============================================================================
# resolve_base_proof_key
# =============================================================================


class TestResolveBaseProofKey:
    def test_exact_match(self):
        display_name, key = resolve_base_proof_key("Character Overview")
        assert display_name == "Character Overview"
        assert key == "filtered_character_set"

    def test_numbered_variant(self):
        display_name, key = resolve_base_proof_key("Structured Text (Heading) 2")
        assert display_name == "Structured Text (Heading)"
        assert key == "basic_paragraph_large"

    def test_unknown_returns_none(self):
        display_name, key = resolve_base_proof_key("Nonexistent Proof")
        assert display_name is None
        assert key is None

    def test_all_registry_entries_resolve(self):
        for proof_key, info in PROOF_REGISTRY.items():
            display, key = resolve_base_proof_key(info["display_name"])
            assert display == info["display_name"]
            assert key == proof_key


# =============================================================================
# get_proof_settings_mapping
# =============================================================================


class TestGetProofSettingsMapping:
    def test_returns_dict(self):
        mapping = get_proof_settings_mapping()
        assert isinstance(mapping, dict)

    def test_all_registry_entries_present(self):
        mapping = get_proof_settings_mapping()
        for key, info in PROOF_REGISTRY.items():
            assert info["display_name"] in mapping
            assert mapping[info["display_name"]] == key

    def test_mapping_is_bijective(self):
        mapping = get_proof_settings_mapping()
        values = list(mapping.values())
        assert len(values) == len(set(values))


# =============================================================================
# get_proof_default_columns / get_proof_paragraph_settings
# =============================================================================


class TestProofDefaultColumns:
    def test_returns_dict(self):
        result = get_proof_default_columns()
        assert isinstance(result, dict)

    def test_keys_end_with_cols(self):
        for key in get_proof_default_columns():
            assert key.endswith("_cols")

    def test_values_are_positive_ints(self):
        for _, val in get_proof_default_columns().items():
            assert isinstance(val, int)
            assert val > 0


class TestProofParagraphSettings:
    def test_only_includes_has_paragraphs(self):
        result = get_proof_paragraph_settings()
        for key in result:
            # Extract proof key by removing _para suffix
            proof_key = key.replace("_para", "")
            info = PROOF_REGISTRY.get(proof_key)
            assert info is not None
            assert info["has_paragraphs"] is True

    def test_generative_text_has_paragraphs(self):
        result = get_proof_paragraph_settings()
        assert "generative_text_small_para" in result


# =============================================================================
# get_proof_by_* lookups
# =============================================================================


class TestProofLookups:
    def test_by_display_name_found(self):
        result = get_proof_by_display_name("Custom Text")
        assert result is not None
        assert result["display_name"] == "Custom Text"

    def test_by_display_name_not_found(self):
        assert get_proof_by_display_name("Nonexistent") is None

    def test_by_settings_key(self):
        result = get_proof_by_settings_key("custom_text")
        assert result is not None
        assert result["display_name"] == "Custom Text"

    def test_by_storage_key(self):
        result = get_proof_by_storage_key("spacing_proof")
        assert result is not None
        assert result["display_name"] == "Spacing Test"

    def test_by_settings_key_not_found(self):
        assert get_proof_by_settings_key("nonexistent_key") is None


# =============================================================================
# Arabic / non-Arabic partitioning
# =============================================================================


class TestArabicPartitioning:
    def test_arabic_names_are_arabic(self):
        for name in get_arabic_proof_display_names():
            info = get_proof_by_display_name(name)
            assert info["is_arabic"] is True

    def test_base_names_are_not_arabic(self):
        for name in get_base_proof_display_names():
            info = get_proof_by_display_name(name)
            assert info["is_arabic"] is False

    def test_combined_equals_all(self):
        all_names = set(get_proof_display_names(include_arabic=True))
        arabic = set(get_arabic_proof_display_names())
        base = set(get_base_proof_display_names())
        assert arabic | base == all_names
        assert arabic & base == set()


# =============================================================================
# get_proof_default_font_size
# =============================================================================


class TestGetProofDefaultFontSize:
    def test_known_proofs(self):
        assert get_proof_default_font_size("filtered_character_set") == 78
        assert get_proof_default_font_size("spacing_proof") == 14
        assert get_proof_default_font_size("basic_paragraph_large") == 28
        assert get_proof_default_font_size("basic_paragraph_small") == 10

    def test_unknown_falls_back_to_8(self):
        assert get_proof_default_font_size("nonexistent") == 8


# =============================================================================
# proof_supports_formatting
# =============================================================================


class TestProofSupportsFormatting:
    def test_excluded_proofs(self):
        assert proof_supports_formatting("filtered_character_set") is False
        assert proof_supports_formatting("spacing_proof") is False
        assert proof_supports_formatting("ar_character_set") is False

    def test_included_proofs(self):
        assert proof_supports_formatting("basic_paragraph_large") is True
        assert proof_supports_formatting("custom_text") is True
        assert proof_supports_formatting("multi_style_comparison") is True


# =============================================================================
# get_display_name / get_otf_prefix / get_default_alignment_for_proof
# =============================================================================


class TestDisplayNameAndPrefix:
    def test_display_name_known(self):
        assert get_display_name("custom_text") == "Custom Text"

    def test_display_name_unknown_returns_key(self):
        assert get_display_name("unknown_key") == "unknown_key"

    def test_otf_prefix(self):
        assert get_otf_prefix("basic_paragraph_small") == "otf_basic_paragraph_small_"
        assert get_otf_prefix("kern_test") == "otf_kern_test_"

    def test_default_alignment_latin(self):
        assert get_default_alignment_for_proof("basic_paragraph_small") == "left"

    def test_default_alignment_arabic(self):
        assert get_default_alignment_for_proof("ar_paragraph_large") == "right"
        assert get_default_alignment_for_proof("ar_character_set") == "right"


# =============================================================================
# proof_has_custom_text / proof_has_categories / proof_is_multi_style
# =============================================================================


class TestProofFlags:
    def test_custom_text_flag(self):
        assert proof_has_custom_text("custom_text") is True
        assert proof_has_custom_text("multi_style_comparison") is True
        assert proof_has_custom_text("basic_paragraph_small") is False

    def test_categories_flag(self):
        assert proof_has_categories("filtered_character_set") is True
        assert proof_has_categories("spacing_proof") is True
        assert proof_has_categories("multi_style_comparison") is True
        assert proof_has_categories("basic_paragraph_small") is False

    def test_multi_style_flag(self):
        assert proof_is_multi_style("multi_style_comparison") is True
        assert proof_is_multi_style("custom_text") is False
        assert proof_is_multi_style("basic_paragraph_small") is False

    def test_unknown_key_returns_false(self):
        assert proof_has_custom_text("nonexistent") is False
        assert proof_has_categories("nonexistent") is False
        assert proof_is_multi_style("nonexistent") is False


# =============================================================================
# get_text_proof_config
# =============================================================================


class TestGetTextProofConfig:
    def test_returns_config_for_text_proofs(self):
        cfg = get_text_proof_config("basic_paragraph_large")
        assert cfg is not None
        assert cfg["character_set_key"] == "base_letters"

    def test_returns_none_for_non_text_proofs(self):
        assert get_text_proof_config("filtered_character_set") is None
        assert get_text_proof_config("custom_text") is None

    def test_returns_none_for_unknown(self):
        assert get_text_proof_config("nonexistent") is None

    def test_arabic_config_has_language(self):
        cfg = get_text_proof_config("ar_paragraph_large")
        assert cfg is not None
        assert cfg["language"] == "ar"

    def test_farsi_config_has_language(self):
        cfg = get_text_proof_config("fa_paragraph_large")
        assert cfg is not None
        assert cfg["language"] == "fa"


# =============================================================================
# resolve_character_set_by_key
# =============================================================================


class TestResolveCharacterSetByKey:
    def test_base_letters(self, sample_cat):
        result = resolve_character_set_by_key(sample_cat, "base_letters")
        assert "A" in result
        assert "z" in result

    def test_accented_plus(self, sample_cat):
        result = resolve_character_set_by_key(sample_cat, "accented_plus")
        assert isinstance(result, str)

    def test_arabic(self, sample_arabic_cat):
        result = resolve_character_set_by_key(sample_arabic_cat, "arabic")
        assert len(result) > 0

    def test_farsi(self, sample_arabic_cat):
        result = resolve_character_set_by_key(sample_arabic_cat, "farsi")
        assert len(result) > 0

    def test_unknown_key_returns_empty(self, sample_cat):
        result = resolve_character_set_by_key(sample_cat, "nonexistent_key")
        assert result == ""


# =============================================================================
# load_arabic_texts
# =============================================================================


class TestLoadArabicTexts:
    def test_returns_dict(self):
        result = load_arabic_texts()
        assert isinstance(result, dict)
        assert "arabic_vocalization" in result
        assert "arabic_latin_mixed" in result
        assert "arabic_farsi_urdu_numbers" in result

    def test_values_are_strings(self):
        for key, value in load_arabic_texts().items():
            assert isinstance(value, str)
            assert len(value) > 0
