"""Tests for settings.py — ProofSettingsManager class."""

import os
import pytest
from unittest.mock import MagicMock, patch

from settings import (
    ProofSettingsManager,
    Settings,
    make_settings_key,
    make_feature_key,
    create_unique_proof_key,
    validate_setting_value,
)
from config import (
    PROOF_REGISTRY,
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
    get_proof_default_font_size,
    proof_supports_formatting,
    get_default_alignment_for_proof,
)


@pytest.fixture
def mock_font_manager():
    fm = MagicMock()
    fm.fonts = ()
    fm.font_info = {}
    return fm


@pytest.fixture
def psm(tmp_settings_path, mock_font_manager):
    """ProofSettingsManager backed by temp settings."""
    settings = Settings(settings_path=tmp_settings_path)
    return ProofSettingsManager(settings, mock_font_manager)


# =============================================================================
# Initialization
# =============================================================================


class TestPSMInitialization:
    def test_proof_settings_populated(self, psm):
        assert isinstance(psm.proof_settings, dict)
        assert len(psm.proof_settings) > 0

    def test_all_proof_types_get_font_size(self, psm):
        for proof_key in PROOF_REGISTRY:
            key = make_settings_key(proof_key, "fontSize")
            assert key in psm.proof_settings, f"Missing fontSize for {proof_key}"

    def test_font_size_defaults_match_registry(self, psm):
        for proof_key, info in PROOF_REGISTRY.items():
            key = make_settings_key(proof_key, "fontSize")
            assert psm.proof_settings[key] == info["default_size"]

    def test_column_excluded_proofs_still_get_cols(self, psm):
        # Excluded proofs should NOT get cols key
        for excluded in ProofSettingsManager._COLUMN_EXCLUDED_PROOFS:
            key = make_settings_key(excluded, "cols")
            assert key not in psm.proof_settings, f"{excluded} should not have cols"

    def test_non_excluded_proofs_get_cols(self, psm):
        for proof_key in PROOF_REGISTRY:
            if proof_key not in ProofSettingsManager._COLUMN_EXCLUDED_PROOFS:
                key = make_settings_key(proof_key, "cols")
                assert key in psm.proof_settings, f"{proof_key} should have cols"

    def test_tracking_only_for_formatting_proofs(self, psm):
        for proof_key in PROOF_REGISTRY:
            key = make_settings_key(proof_key, "tracking")
            if proof_supports_formatting(proof_key):
                assert key in psm.proof_settings
            else:
                assert key not in psm.proof_settings

    def test_alignment_only_for_formatting_proofs(self, psm):
        for proof_key in PROOF_REGISTRY:
            key = make_settings_key(proof_key, "align")
            if proof_supports_formatting(proof_key):
                assert key in psm.proof_settings
                assert psm.proof_settings[key] == get_default_alignment_for_proof(
                    proof_key
                )
            else:
                assert key not in psm.proof_settings

    def test_category_defaults_for_category_proofs(self, psm):
        from config import proof_has_categories

        for proof_key in PROOF_REGISTRY:
            if proof_has_categories(proof_key):
                for cat_key in ProofSettingsManager._CATEGORY_DEFAULTS:
                    setting = make_settings_key(proof_key, "cat", cat_key)
                    assert (
                        setting in psm.proof_settings
                    ), f"Missing category {cat_key} for {proof_key}"

    def test_custom_text_defaults_for_custom_text_proofs(self, psm):
        from config import proof_has_custom_text

        for proof_key in PROOF_REGISTRY:
            if proof_has_custom_text(proof_key):
                ct_key = make_settings_key(proof_key, "customText")
                assert ct_key in psm.proof_settings
                assert psm.proof_settings[ct_key] == ""

                markup_key = make_settings_key(proof_key, "markupEnabled")
                assert markup_key in psm.proof_settings
                assert psm.proof_settings[markup_key] is False


# =============================================================================
# get_proof_font_size
# =============================================================================


class TestGetProofFontSize:
    def test_known_proof_display_name(self, psm):
        size = psm.get_proof_font_size("Filtered Character Set")
        assert size == 78

    def test_custom_proof_falls_back(self, psm):
        size = psm.get_proof_font_size("Basic Paragraph Large 2")
        # Should return the default for basic_paragraph_large since no override set
        assert size == get_proof_default_font_size("basic_paragraph_large")


# =============================================================================
# update / get settings value
# =============================================================================


class TestSettingsValueAccess:
    def test_update_and_get(self, psm):
        psm.update_settings_value("test_key", 42)
        assert psm.get_settings_value("test_key") == 42

    def test_get_missing_returns_default(self, psm):
        assert psm.get_settings_value("nonexistent", "default") == "default"


# =============================================================================
# Numeric setting updates
# =============================================================================


class TestNumericSettings:
    def test_valid_update(self, psm):
        key = make_settings_key("basic_paragraph_small", "fontSize")
        result = psm.update_numeric_setting(key, 16)
        assert result is True
        assert psm.proof_settings[key] == 16

    def test_invalid_update(self, psm):
        key = make_settings_key("basic_paragraph_small", "fontSize")
        result = psm.update_numeric_setting(key, "abc")
        assert result is False

    def test_tracking_accepts_negative(self, psm):
        key = make_settings_key("basic_paragraph_small", "tracking")
        result = psm.update_numeric_setting(key, -5.0)
        assert result is True
        assert psm.proof_settings[key] == -5.0


# =============================================================================
# Alignment
# =============================================================================


class TestAlignment:
    def test_get_alignment_for_formatting_proof(self, psm):
        val = psm.get_alignment_value_for_proof("basic_paragraph_small")
        assert val == "left"

    def test_get_alignment_for_arabic(self, psm):
        val = psm.get_alignment_value_for_proof("ar_paragraph_large")
        assert val == "right"

    def test_set_alignment(self, psm):
        psm.set_alignment_value_for_proof("basic_paragraph_small", "center")
        assert psm.get_alignment_value_for_proof("basic_paragraph_small") == "center"

    def test_no_alignment_for_non_formatting(self, psm):
        val = psm.get_alignment_value_for_proof("filtered_character_set")
        assert val is None


# =============================================================================
# initialize_settings_for_proof (new instance)
# =============================================================================


class TestInitializeForNewProof:
    def test_creates_settings_for_instance(self, psm):
        psm.initialize_settings_for_proof(
            "Basic Paragraph Large 3", "Basic Paragraph Large"
        )
        unique_key = create_unique_proof_key("Basic Paragraph Large 3")
        fs_key = make_settings_key(unique_key, "fontSize")
        assert fs_key in psm.proof_settings
        assert psm.proof_settings[fs_key] == get_proof_default_font_size(
            "basic_paragraph_large"
        )

    def test_skip_baselines(self, psm):
        # Should not crash
        psm.initialize_settings_for_proof("Show Baselines", "Show Baselines/Grid")

    def test_unknown_base_type(self, psm):
        # Should not crash
        psm.initialize_settings_for_proof("Unknown 2", "Unknown Type")


# =============================================================================
# Popover settings list
# =============================================================================


class TestPopoverSettings:
    def test_returns_list(self, psm):
        items = psm.get_popover_settings_for_proof("basic_paragraph_small")
        assert isinstance(items, list)
        assert len(items) > 0

    def test_items_have_required_keys(self, psm):
        items = psm.get_popover_settings_for_proof("basic_paragraph_small")
        for item in items:
            assert "Setting" in item
            assert "Value" in item
            assert "_key" in item

    def test_font_size_always_present(self, psm):
        items = psm.get_popover_settings_for_proof("basic_paragraph_small")
        names = [i["Setting"] for i in items]
        assert "Font Size" in names

    def test_columns_present_for_text_proof(self, psm):
        items = psm.get_popover_settings_for_proof("basic_paragraph_small")
        names = [i["Setting"] for i in items]
        assert "Columns" in names

    def test_no_columns_for_charset(self, psm):
        items = psm.get_popover_settings_for_proof("filtered_character_set")
        names = [i["Setting"] for i in items]
        assert "Columns" not in names

    def test_paragraphs_only_for_has_paragraphs(self, psm):
        items = psm.get_popover_settings_for_proof("generative_text_small")
        names = [i["Setting"] for i in items]
        assert "Paragraphs" in names

        items2 = psm.get_popover_settings_for_proof("basic_paragraph_small")
        names2 = [i["Setting"] for i in items2]
        assert "Paragraphs" not in names2


# =============================================================================
# OpenType features list
# =============================================================================


class TestOpenTypeFeatures:
    def test_no_features_without_fonts(self, psm):
        items = psm.get_opentype_features_for_proof("basic_paragraph_small")
        assert items == []

    def test_with_mock_fonts(self, tmp_settings_path):
        settings = Settings(settings_path=tmp_settings_path)
        fm = MagicMock()
        fm.fonts = ("/fake/font.otf",)

        with patch(
            "settings._cached_list_ot_features",
            return_value=("kern", "liga", "calt", "init"),
        ):
            psm = ProofSettingsManager(settings, fm)
            items = psm.get_opentype_features_for_proof("basic_paragraph_small")

        tags = [i["Feature"] for i in items]
        # "init" is hidden, should not appear
        assert "init" not in [t.split()[0] for t in tags]
        # kern, liga, calt should appear
        assert "kern" in tags
        assert "liga" in tags
        assert "calt" in tags

    def test_spacing_proof_kern_always_off(self, tmp_settings_path):
        settings = Settings(settings_path=tmp_settings_path)
        fm = MagicMock()
        fm.fonts = ("/fake/font.otf",)

        with patch("settings._cached_list_ot_features", return_value=("kern", "liga")):
            psm = ProofSettingsManager(settings, fm)
            items = psm.get_opentype_features_for_proof("spacing_proof")

        kern_items = [i for i in items if "kern" in i["Feature"]]
        assert len(kern_items) == 1
        assert kern_items[0]["Enabled"] is False
        assert kern_items[0].get("_readonly") is True


# =============================================================================
# build_proof_data_for_generation
# =============================================================================


class TestBuildProofData:
    def test_disabled_proofs_excluded(self, psm):
        items = [
            {"Option": "Basic Paragraph Small", "Enabled": False},
        ]
        otf, cols, paras = psm.build_proof_data_for_generation(items)
        assert "Basic Paragraph Small" not in otf

    def test_enabled_proof_included(self, psm):
        items = [
            {"Option": "Basic Paragraph Small", "Enabled": True},
        ]
        otf, cols, paras = psm.build_proof_data_for_generation(items)
        assert "Basic Paragraph Small" in otf
        assert "Basic Paragraph Small" in cols

    def test_has_paragraphs_only_when_declared(self, psm):
        items = [
            {"Option": "Generative Text Small", "Enabled": True},
            {"Option": "Basic Paragraph Small", "Enabled": True},
        ]
        otf, cols, paras = psm.build_proof_data_for_generation(items)
        assert "Generative Text Small" in paras
        assert "Basic Paragraph Small" not in paras


# =============================================================================
# save_all_settings
# =============================================================================


class TestSaveAllSettings:
    def test_saves_proof_options(self, psm):
        items = [
            {
                "Option": "Basic Paragraph Small",
                "Enabled": True,
                "_original_option": "Basic Paragraph Small",
            },
            {
                "Option": "Show Baselines/Grid",
                "Enabled": True,
                "_original_option": "Show Baselines/Grid",
            },
        ]
        psm.save_all_settings(items)
        assert psm.settings.get_proof_option("showBaselines") is True
        assert psm.settings.get_proof_option("basic_paragraph_small") is True

    def test_persists_to_disk(self, psm, tmp_settings_path):
        items = [
            {
                "Option": "Custom Text",
                "Enabled": True,
                "_original_option": "Custom Text",
            },
        ]
        psm.save_all_settings(items)
        assert os.path.exists(tmp_settings_path)
