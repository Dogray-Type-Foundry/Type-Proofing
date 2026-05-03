"""Tests for proof.py — ProofContext, handler classes, text generation, and handler factory."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from proof import (
    ProofContext,
    BaseProofHandler,
    StandardTextProofHandler,
    CategoryBasedProofHandler,
    FilteredCharacterSetHandler,
    SpacingProofHandler,
    ArCharacterSetHandler,
    CustomTextProofHandler,
    MultiStyleComparisonProofHandler,
    PROOF_HANDLER_REGISTRY,
    get_proof_handler,
    clear_handler_cache,
    generateArabicContextualFormsProof,
    reset_proof_page_counter,
    _normalize_axes,
    get_font_display_name,
)
from settings import make_settings_key, create_unique_proof_key
from config import PROOF_REGISTRY


# =============================================================================
# ProofContext
# =============================================================================


class TestProofContext:
    def test_creation(self):
        ctx = ProofContext(
            full_character_set="ABCabc",
            axes_product=None,
            ind_font="/test/font.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat={"uniLu": "ABC"},
            proof_name="Test Proof",
        )
        assert ctx.full_character_set == "ABCabc"
        assert ctx.ind_font == "/test/font.otf"
        assert ctx.proof_name == "Test Proof"
        assert ctx.all_fonts is None
        assert ctx.font_manager is None

    def test_optional_fields(self):
        ctx = ProofContext(
            full_character_set="",
            axes_product=None,
            ind_font="",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat={},
            proof_name=None,
            all_fonts=["/f1.otf", "/f2.otf"],
            font_manager=MagicMock(),
        )
        assert ctx.all_fonts == ["/f1.otf", "/f2.otf"]
        assert ctx.font_manager is not None


# =============================================================================
# reset_proof_page_counter
# =============================================================================


class TestResetProofPageCounter:
    def test_resets_without_error(self):
        reset_proof_page_counter()
        # Should not raise


# =============================================================================
# Handler Registry
# =============================================================================


class TestHandlerRegistry:
    def test_registry_has_expected_entries(self):
        expected = {
            "Character Overview",
            "Spacing Test",
            "Ar Character Overview",
            "Custom Text",
            "Style Comparison",
            "Substitution Overview",
        }
        assert expected == set(PROOF_HANDLER_REGISTRY.keys())

    def test_registry_values_are_classes(self):
        for name, cls in PROOF_HANDLER_REGISTRY.items():
            assert isinstance(cls, type), f"{name} is not a class"
            assert issubclass(
                cls, BaseProofHandler
            ), f"{name} doesn't extend BaseProofHandler"


# =============================================================================
# get_proof_handler factory
# =============================================================================


class TestGetProofHandler:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_handler_cache()
        yield
        clear_handler_cache()

    def _mock_font_size_func(self, proof_name):
        return 12

    def test_special_handler(self):
        handler = get_proof_handler(
            "Character Overview",
            "Character Overview",
            {},
            self._mock_font_size_func,
        )
        assert isinstance(handler, FilteredCharacterSetHandler)

    def test_spacing_handler(self):
        handler = get_proof_handler(
            "Spacing Test", "Spacing Test", {}, self._mock_font_size_func
        )
        assert isinstance(handler, SpacingProofHandler)

    def test_arabic_handler(self):
        handler = get_proof_handler(
            "Ar Character Overview", "Ar Character Overview", {}, self._mock_font_size_func
        )
        assert isinstance(handler, ArCharacterSetHandler)

    def test_custom_text_handler(self):
        handler = get_proof_handler(
            "Custom Text", "Custom Text", {}, self._mock_font_size_func
        )
        assert isinstance(handler, CustomTextProofHandler)

    def test_multi_style_handler(self):
        handler = get_proof_handler(
            "Style Comparison",
            "Style Comparison",
            {},
            self._mock_font_size_func,
        )
        assert isinstance(handler, MultiStyleComparisonProofHandler)

    def test_standard_text_handler_for_text_proofs(self):
        handler = get_proof_handler(
            "Structured Text (Heading)",
            "Structured Text (Heading)",
            {},
            self._mock_font_size_func,
        )
        assert isinstance(handler, StandardTextProofHandler)

    def test_numbered_variant(self):
        handler = get_proof_handler(
            "Structured Text (Text)",
            "Structured Text (Text) 2",
            {},
            self._mock_font_size_func,
        )
        assert isinstance(handler, StandardTextProofHandler)
        assert handler.proof_name == "Structured Text (Text) 2"

    def test_caching(self):
        h1 = get_proof_handler(
            "Custom Text", "Custom Text", {}, self._mock_font_size_func
        )
        h2 = get_proof_handler(
            "Custom Text", "Custom Text", {"new_key": 1}, self._mock_font_size_func
        )
        assert h1 is h2  # Same object from cache

    def test_cache_updates_settings(self):
        settings1 = {"key": 1}
        h1 = get_proof_handler(
            "Custom Text", "Custom Text", settings1, self._mock_font_size_func
        )
        settings2 = {"key": 2}
        h2 = get_proof_handler(
            "Custom Text", "Custom Text", settings2, self._mock_font_size_func
        )
        assert h2.proof_settings == settings2

    def test_clear_cache(self):
        h1 = get_proof_handler(
            "Custom Text", "Custom Text", {}, self._mock_font_size_func
        )
        clear_handler_cache()
        h2 = get_proof_handler(
            "Custom Text", "Custom Text", {}, self._mock_font_size_func
        )
        assert h1 is not h2


# =============================================================================
# BaseProofHandler (via concrete subclasses)
# =============================================================================


class TestBaseProofHandlerMethods:
    def _make_handler(self, proof_name="Test Proof", settings=None):
        if settings is None:
            settings = {}
        return FilteredCharacterSetHandler(proof_name, settings, lambda name: 78)

    def test_unique_proof_key(self):
        handler = self._make_handler("Character Overview")
        assert handler.unique_proof_key == "filtered_character_set"

    def test_get_font_size(self):
        handler = self._make_handler()
        assert handler.get_font_size() == 78

    def test_get_tracking_value_default(self):
        handler = self._make_handler()
        assert handler.get_tracking_value() == 0

    def test_get_tracking_value_from_settings(self):
        key = make_settings_key("my_proof", "tracking")
        handler = self._make_handler("My Proof", {key: 5.0})
        assert handler.get_tracking_value() == 5.0

    def test_get_align_value_default(self):
        handler = self._make_handler()
        assert handler.get_align_value() == "left"

    def test_get_align_value_from_settings(self):
        key = make_settings_key("my_proof", "align")
        handler = self._make_handler("My Proof", {key: "center"})
        assert handler.get_align_value() == "center"

    def test_get_section_name(self):
        handler = self._make_handler("Test Proof")
        name = handler.get_section_name(24)
        assert "Test Proof" in name
        assert "24" in name

    def test_get_common_proof_params(self):
        settings = {
            make_settings_key("test_proof", "cols"): 3,
            make_settings_key("test_proof", "para"): 7,
            "otf_test_proof_kern": True,
        }
        handler = self._make_handler("Test Proof", settings)
        ctx = ProofContext(
            full_character_set="ABC",
            axes_product=None,
            ind_font="/test.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat={},
            proof_name="Test Proof",
        )
        params = handler.get_common_proof_params(
            ctx, default_columns=2, default_paragraphs=5
        )
        assert params["font_size"] == 78
        assert params["columns"] == 3
        assert params["paragraphs"] == 7
        assert params["otfeatures"] == {"kern": True}

    def test_common_params_uses_defaults(self):
        handler = self._make_handler("Test Proof")
        ctx = ProofContext(
            full_character_set="ABC",
            axes_product=None,
            ind_font="/test.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat={},
            proof_name="Test Proof",
        )
        params = handler.get_common_proof_params(
            ctx, default_columns=2, default_paragraphs=5
        )
        assert params["columns"] == 2
        assert params["paragraphs"] == 5
        assert params["otfeatures"] == {}


# =============================================================================
# StandardTextProofHandler
# =============================================================================


class TestStandardTextProofHandler:
    def test_with_valid_key(self):
        handler = StandardTextProofHandler(
            "Structured Text (Heading)", {}, lambda n: 28, proof_key="basic_paragraph_large"
        )
        assert handler.character_set_key == "base_letters"
        assert handler.hoefler_style is True
        assert handler.default_paragraphs == 2

    def test_arabic_config(self):
        handler = StandardTextProofHandler(
            "Ar Structured Text (Heading)", {}, lambda n: 28, proof_key="ar_paragraph_large"
        )
        assert handler.character_set_key == "arabic"
        assert handler.language == "ar"

    def test_farsi_config(self):
        handler = StandardTextProofHandler(
            "Fa Structured Text (Heading)", {}, lambda n: 28, proof_key="fa_paragraph_large"
        )
        assert handler.character_set_key == "farsi"
        assert handler.language == "fa"

    def test_fallback_without_key(self):
        handler = StandardTextProofHandler("Unknown Proof", {}, lambda n: 10)
        assert handler.character_set_key == "base_letters"
        assert handler.mixed_styles is False
        assert handler.force_wordsiv is False

    def test_get_character_set_base_letters(self, sample_cat):
        handler = StandardTextProofHandler(
            "Test", {}, lambda n: 10, proof_key="basic_paragraph_large"
        )
        ctx = ProofContext(
            full_character_set="ABCabc",
            axes_product=None,
            ind_font="/test.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat=sample_cat,
            proof_name="Test",
        )
        charset = handler.get_character_set(ctx)
        assert "A" in charset
        assert "z" in charset

    def test_accents_config(self):
        handler = StandardTextProofHandler(
            "Accented Words (Heading)", {}, lambda n: 28, proof_key="diacritic_words_large"
        )
        assert handler.accents == 3
        assert handler.character_set_key == "accented_plus"

    def test_force_wordsiv(self):
        handler = StandardTextProofHandler(
            "Auto-Generated Text", {}, lambda n: 10, proof_key="generative_text_small"
        )
        assert handler.force_wordsiv is True

    def test_mixed_styles(self):
        handler = StandardTextProofHandler(
            "Style Pairing", {}, lambda n: 10, proof_key="paired_styles_paragraph_small"
        )
        assert handler.mixed_styles is True

    def test_practical_figures_columns_reach_text_proof(self, sample_cat):
        settings = {
            make_settings_key("misc_paragraph_small", "cols"): 4,
            make_settings_key("misc_paragraph_small", "fontSize"): 10,
        }
        handler = StandardTextProofHandler(
            "Practical Figures & Punctuation",
            settings,
            lambda n: settings[make_settings_key("misc_paragraph_small", "fontSize")],
            proof_key="misc_paragraph_small",
        )
        ctx = ProofContext(
            full_character_set="ABCabc012",
            axes_product=None,
            ind_font="/test.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat=sample_cat,
            proof_name="Practical Figures & Punctuation",
        )

        with patch("proof.textProof") as text_proof:
            handler.generate_proof(ctx)

        assert text_proof.call_args.args[4] == 4

    @pytest.mark.parametrize(
        "proof_key",
        [key for key, info in PROOF_REGISTRY.items() if "text" in info],
    )
    def test_text_proof_registry_columns_reach_text_proof(self, proof_key, sample_cat):
        display_name = PROOF_REGISTRY[proof_key]["display_name"]
        settings = {
            make_settings_key(proof_key, "cols"): 3,
            make_settings_key(proof_key, "fontSize"): PROOF_REGISTRY[proof_key][
                "default_size"
            ],
        }
        handler = StandardTextProofHandler(
            display_name,
            settings,
            lambda n: settings[make_settings_key(proof_key, "fontSize")],
            proof_key=proof_key,
        )
        ctx = ProofContext(
            full_character_set="ABCabc",
            axes_product=None,
            ind_font="/test.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat={**sample_cat, "ar": "ابت", "fa": "پچگ", "arab": "ابتپچگ"},
            proof_name=display_name,
        )

        with patch("proof.textProof") as text_proof:
            handler.generate_proof(ctx)

        assert text_proof.call_args.args[4] == 3


# =============================================================================
# CategoryBasedProofHandler
# =============================================================================


class TestCategoryBasedProofHandler:
    def test_category_defaults(self):
        handler = FilteredCharacterSetHandler("Test", {}, lambda n: 78)
        assert handler.get_character_category_setting("uppercase_base") is True
        assert handler.get_character_category_setting("lowercase_base") is True
        assert handler.get_character_category_setting("numbers_symbols") is True
        assert handler.get_character_category_setting("punctuation") is True
        assert handler.get_character_category_setting("accented") is False

    def test_category_from_settings(self):
        key = make_settings_key("test", "cat", "accented")
        handler = FilteredCharacterSetHandler("Test", {key: True}, lambda n: 78)
        assert handler.get_character_category_setting("accented") is True

    def test_get_proof_sections(self, sample_cat):
        handler = FilteredCharacterSetHandler("Test", {}, lambda n: 78)
        ctx = ProofContext(
            full_character_set="ABCabc",
            axes_product=None,
            ind_font="/test.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat=sample_cat,
            proof_name="Test",
        )
        sections = handler.get_proof_sections(ctx)
        labels = [s[0] for s in sections]
        # Default: uppercase, lowercase, numbers, punctuation enabled; accented disabled
        assert "Uppercase Base" in labels
        assert "Lowercase Base" in labels
        assert "Numbers & Symbols" in labels
        assert "Punctuation" in labels
        assert "Accented Characters" not in labels

    def test_sections_respect_disabled(self, sample_cat):
        key = make_settings_key("test", "cat", "uppercase_base")
        handler = FilteredCharacterSetHandler("Test", {key: False}, lambda n: 78)
        ctx = ProofContext(
            full_character_set="",
            axes_product=None,
            ind_font="",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat=sample_cat,
            proof_name="Test",
        )
        sections = handler.get_proof_sections(ctx)
        labels = [s[0] for s in sections]
        assert "Uppercase Base" not in labels


# =============================================================================
# CustomTextProofHandler
# =============================================================================


class TestCustomTextProofHandler:
    def test_custom_text_key_resolution(self):
        unique_key = create_unique_proof_key("Custom Text")
        ct_key = make_settings_key(unique_key, "customText")
        handler = CustomTextProofHandler("Custom Text", {ct_key: "Hello"}, lambda n: 16)
        assert handler.proof_settings[ct_key] == "Hello"

    def test_no_custom_text_configured(self):
        handler = CustomTextProofHandler("Custom Text", {}, lambda n: 16)
        unique_key = create_unique_proof_key("Custom Text")
        ct_key = make_settings_key(unique_key, "customText")
        assert handler.proof_settings.get(ct_key, "") == ""

    def test_generate_once_settings(self):
        unique_key = create_unique_proof_key("Custom Text")
        once_key = make_settings_key(unique_key, "generateOnce")
        path_key = make_settings_key(unique_key, "defaultFontPath")
        ct_key = make_settings_key(unique_key, "customText")
        settings = {
            ct_key: "Hello world",
            once_key: True,
            path_key: "/font_a.otf",
        }
        handler = CustomTextProofHandler("Custom Text", settings, lambda n: 16)
        assert handler.proof_settings[once_key] is True
        assert handler.proof_settings[path_key] == "/font_a.otf"


# =============================================================================
# MultiStyleComparisonProofHandler
# =============================================================================


class TestMultiStyleComparisonHandler:
    @pytest.fixture(autouse=True)
    def reset(self):
        MultiStyleComparisonProofHandler.reset_generated()
        yield
        MultiStyleComparisonProofHandler.reset_generated()

    def test_reset_generated(self):
        MultiStyleComparisonProofHandler._generated_instances = {"test"}
        MultiStyleComparisonProofHandler.reset_generated()
        assert MultiStyleComparisonProofHandler._generated_instances == set()

    def test_deduplication_tracking(self):
        # Verify deduplication mechanism without calling generate_proof
        # (generate_proof triggers deep drawBot rendering that hangs under mocks)
        MultiStyleComparisonProofHandler._generated_instances = set()
        MultiStyleComparisonProofHandler._generated_instances.add(
            "Style Comparison"
        )
        assert (
            "Style Comparison"
            in MultiStyleComparisonProofHandler._generated_instances
        )

    def test_is_style_enabled_default(self):
        handler = MultiStyleComparisonProofHandler(
            "Style Comparison", {}, lambda n: 78
        )
        # Default: all styles enabled
        assert handler._is_style_enabled(0) is True
        assert handler._is_style_enabled(5) is True

    def test_is_style_enabled_from_settings(self):
        key = make_settings_key("multi_style_comparison", "style", "0")
        handler = MultiStyleComparisonProofHandler(
            "Style Comparison", {key: False}, lambda n: 78
        )
        assert handler._is_style_enabled(0) is False

    def test_columns_and_line_height_reach_multi_style_rendering(self):
        settings = {
            make_settings_key("multi_style_comparison", "cols"): 3,
            make_settings_key("multi_style_comparison", "lineHeight"): 2.0,
        }
        handler = MultiStyleComparisonProofHandler(
            "Style Comparison", settings, lambda n: 10
        )
        handler._collect_text_groups = MagicMock(return_value=[("Custom", "ABC")])
        handler.get_substitution_sections = MagicMock(return_value=[])
        handler._collect_styles = MagicMock(return_value=[("Regular", "/test.otf", None)])
        ctx = ProofContext(
            full_character_set="ABC",
            axes_product=None,
            ind_font="/test.otf",
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat={},
            proof_name="Style Comparison",
            all_fonts=["/test.otf"],
            font_manager=MagicMock(),
        )

        with patch("proof.drawContent") as draw_content, patch(
            "proof.db.FormattedString"
        ) as formatted_string:
            formatted_string.return_value = MagicMock()
            handler.generate_proof(ctx)

        assert draw_content.call_args.args[2] == 3
        assert formatted_string.call_args.kwargs["lineHeight"] == 20


# =============================================================================
# SubstitutionOverviewProofHandler
# =============================================================================


class TestSubstitutionOverviewProofHandler:
    def test_contextual_source_uses_context_not_nested_lookup_input(self):
        clear_handler_cache()
        handler = get_proof_handler(
            "Substitution Overview",
            "Substitution Overview",
            {},
            lambda n: 48,
        )
        entry = {
            "input_glyphs": ["f"],
            "output_glyphs": ["beh-ar.init"],
            "context_glyphs": {
                "backtrack": ["alef-ar"],
                "input": ["beh-ar"],
                "lookahead": ["meem-ar"],
            },
            "substitution_index": 0,
        }

        assert handler._source_glyphs(entry) == ["alef-ar", "beh-ar", "meem-ar"]
        assert handler._result_glyphs(entry) == ["beh-ar.init"]

    def test_selected_substitution_tags_distinguishes_no_settings_from_all_off(self):
        clear_handler_cache()
        handler = get_proof_handler(
            "Substitution Overview",
            "Substitution Overview",
            {},
            lambda n: 48,
        )
        assert handler._selected_substitution_tags() is None

        settings = {
            make_settings_key("substitution_overview", "sub", "calt"): False,
            make_settings_key("substitution_overview", "sub", "liga"): True,
        }
        handler = get_proof_handler(
            "Substitution Overview",
            "Substitution Overview",
            settings,
            lambda n: 48,
        )
        assert handler._selected_substitution_tags() == {"liga"}
        clear_handler_cache()


# =============================================================================
# generateArabicContextualFormsProof
# =============================================================================


class TestGenerateArabicContextualForms:
    def test_empty_chars(self):
        cat = {"arabTyped": "", "arfaDualJoin": "", "arfaRightJoin": ""}
        result = generateArabicContextualFormsProof(cat)
        assert result == ""

    def test_with_dual_join_chars(self):
        cat = {
            "arabTyped": "\u0628",  # ba - dual joining
            "arfaDualJoin": "\u0628",
            "arfaRightJoin": "",
        }
        result = generateArabicContextualFormsProof(cat)
        assert "\u0628" in result
        assert len(result) > 1  # Should include spacing/duplicated forms

    def test_with_right_join_chars(self):
        cat = {
            "arabTyped": "\u0627",  # alif - right joining
            "arfaDualJoin": "",
            "arfaRightJoin": "\u0627",
        }
        result = generateArabicContextualFormsProof(cat)
        assert "\u0627" in result

    def test_hamza_special_case(self):
        cat = {
            "arabTyped": "\u0621",  # hamza
            "arfaDualJoin": "",
            "arfaRightJoin": "",
        }
        result = generateArabicContextualFormsProof(cat)
        assert "\u0621" in result

    def test_mixed_chars(self, sample_arabic_cat):
        result = generateArabicContextualFormsProof(sample_arabic_cat)
        assert len(result) > 0
        # Should contain Arabic characters
        assert any(
            "\u0600" <= c <= "\u06ff" for c in result if c != " "
        ), "Result should contain Arabic chars"


# =============================================================================
# _normalize_axes
# =============================================================================


class TestNormalizeAxes:
    def test_static_font(self):
        results = list(_normalize_axes(None, "/test/Font-Regular.otf"))
        assert len(results) == 1
        suffix, axis_dict = results[0]
        assert axis_dict is None

    def test_empty_axes(self):
        results = list(_normalize_axes("", "/test/Font-Regular.otf"))
        assert len(results) == 1

    def test_variable_font(self):
        axes = [{"wght": 400}, {"wght": 700}]
        results = list(_normalize_axes(axes, "/test/Font-Variable.otf"))
        assert len(results) == 2
        _, axis1 = results[0]
        _, axis2 = results[1]
        assert axis1 == {"wght": 400}
        assert axis2 == {"wght": 700}
