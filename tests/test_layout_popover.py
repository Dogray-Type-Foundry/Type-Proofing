"""Tests for _layout_popover dynamic popover sizing."""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure Quartz is mocked before importing app (pdf_manager imports Quartz.PDFKit)
sys.modules.setdefault("Quartz", MagicMock())
sys.modules.setdefault("Quartz.PDFKit", MagicMock())
sys.modules.setdefault("Quartz.CoreGraphics", MagicMock())

from config import (
    proof_supports_formatting,
    proof_has_categories,
    proof_has_custom_text,
    proof_is_multi_style,
)


def _make_mock_self():
    """Create a mock object with a proof_settings_popover that tracks setPosSize/resize calls."""
    obj = MagicMock()
    popover = MagicMock()
    obj.proof_settings_popover = popover
    return obj, popover


def _call_layout_popover(base_proof_key, is_instance=False):
    """Call _layout_popover and return the height passed to resize()."""
    # Import the actual method from the source file
    import app

    obj, popover = _make_mock_self()

    # Call the unbound method on our mock
    app.ProofWindow._layout_popover(obj, base_proof_key, is_instance=is_instance)

    # Extract the height from the resize call
    popover.resize.assert_called_once()
    width, height = popover.resize.call_args[0]
    assert width == 400
    return height


# =============================================================================
# Height calculation tests — type selection mode (is_instance=False)
# =============================================================================


class TestLayoutPopoverTypeSelectionMode:
    """Test popover heights in type-selection mode (proof type dropdown visible)."""

    def test_simple_proof_height(self):
        """basic_paragraph_large: formatting only, no categories/custom/styles."""
        height = _call_layout_popover("basic_paragraph_large")
        # proofType(55) + numeric(170) + align(30) + features(180) = 445 (+ 10 top padding embedded)
        assert height == 445

    def test_categories_proof_height(self):
        """filtered_character_set: has categories, no formatting."""
        height = _call_layout_popover("filtered_character_set")
        # proofType(55) + numeric(170) + categories(150) + features(180) = 555
        # Actually: no alignment for filtered_character_set
        assert height == 545

    def test_custom_text_proof_height(self):
        """custom_text: formatting + custom text editor + generate once controls."""
        height = _call_layout_popover("custom_text")
        assert height == 680

    def test_multi_style_proof_height(self):
        """multi_style_comparison: formatting + categories + custom text + styles."""
        height = _call_layout_popover("multi_style_comparison")
        assert height == 995

    def test_simple_is_smaller_than_categories(self):
        """Simple proof should be shorter than one with categories."""
        simple = _call_layout_popover("basic_paragraph_large")
        categories = _call_layout_popover("filtered_character_set")
        assert simple < categories

    def test_multi_style_is_tallest(self):
        """Multi-style comparison should be the tallest popover."""
        simple = _call_layout_popover("basic_paragraph_large")
        custom = _call_layout_popover("custom_text")
        multi = _call_layout_popover("multi_style_comparison")
        assert multi > custom > simple


# =============================================================================
# Height calculation tests — instance mode (is_instance=True)
# =============================================================================


class TestLayoutPopoverInstanceMode:
    """Test popover heights in instance mode (proof type dropdown hidden)."""

    def test_instance_mode_shorter_than_type_selection(self):
        """Instance mode hides proof type selector, so height should be less."""
        type_h = _call_layout_popover("basic_paragraph_large", is_instance=False)
        inst_h = _call_layout_popover("basic_paragraph_large", is_instance=True)
        assert inst_h < type_h

    def test_instance_mode_difference_is_proof_type_section(self):
        """The height difference should be exactly the proof type section (55pt)."""
        type_h = _call_layout_popover("basic_paragraph_large", is_instance=False)
        inst_h = _call_layout_popover("basic_paragraph_large", is_instance=True)
        assert type_h - inst_h == 55

    def test_instance_simple_proof_height(self):
        """Instance mode for basic_paragraph_large."""
        height = _call_layout_popover("basic_paragraph_large", is_instance=True)
        assert height == 390

    def test_instance_multi_style_height(self):
        """Instance mode for multi_style_comparison."""
        height = _call_layout_popover("multi_style_comparison", is_instance=True)
        assert height == 940


# =============================================================================
# Control positioning tests
# =============================================================================


class TestControlPositioning:
    """Verify that controls are repositioned correctly."""

    def test_features_always_last(self):
        """featuresLabel and featuresList should always be the last controls positioned."""
        import app

        obj, popover = _make_mock_self()
        app.ProofWindow._layout_popover(obj, "basic_paragraph_large")

        # featuresLabel should be positioned before featuresList
        label_calls = popover.featuresLabel.setPosSize.call_args_list
        list_calls = popover.featuresList.setPosSize.call_args_list
        assert len(label_calls) == 1
        assert len(list_calls) == 1

        label_y = label_calls[0][0][0][1]
        list_y = list_calls[0][0][0][1]
        assert list_y > label_y

    def test_numeric_settings_always_present(self):
        """numericLabel and numericList should always be positioned."""
        import app

        obj, popover = _make_mock_self()
        app.ProofWindow._layout_popover(obj, "basic_paragraph_large")

        popover.numericLabel.setPosSize.assert_called_once()
        popover.numericList.setPosSize.assert_called_once()

    def test_categories_positioned_when_applicable(self):
        """Category checkboxes should be positioned for filtered_character_set."""
        import app

        obj, popover = _make_mock_self()
        app.ProofWindow._layout_popover(obj, "filtered_character_set")

        popover.categoryLabel.setPosSize.assert_called_once()
        popover.categoryUppercase.setPosSize.assert_called_once()
        popover.categoryAccented.setPosSize.assert_called_once()

    def test_categories_not_positioned_for_simple_proof(self):
        """Category controls should NOT be positioned for basic_paragraph_large."""
        import app

        obj, popover = _make_mock_self()
        app.ProofWindow._layout_popover(obj, "basic_paragraph_large")

        popover.categoryLabel.setPosSize.assert_not_called()
        popover.categoryUppercase.setPosSize.assert_not_called()

    def test_custom_text_controls_positioned(self):
        """Custom text controls should be positioned for custom_text proof."""
        import app

        obj, popover = _make_mock_self()
        app.ProofWindow._layout_popover(obj, "custom_text")

        popover.customTextLabel.setPosSize.assert_called_once()
        popover.customTextEditor.setPosSize.assert_called_once()
        popover.markupToggle.setPosSize.assert_called_once()
        popover.generateOnceToggle.setPosSize.assert_called_once()

    def test_styles_positioned_for_multi_style(self):
        """Styles list should be positioned for multi_style_comparison."""
        import app

        obj, popover = _make_mock_self()
        app.ProofWindow._layout_popover(obj, "multi_style_comparison")

        popover.stylesLabel.setPosSize.assert_called_once()
        popover.stylesList.setPosSize.assert_called_once()

    def test_styles_not_positioned_for_non_multi_style(self):
        """Styles list should NOT be positioned for custom_text proof."""
        import app

        obj, popover = _make_mock_self()
        app.ProofWindow._layout_popover(obj, "custom_text")

        popover.stylesLabel.setPosSize.assert_not_called()
        popover.stylesList.setPosSize.assert_not_called()
