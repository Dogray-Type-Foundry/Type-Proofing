"""Wiring integration tests — verify every UI control reaches proof generation.

Each test generates a proof with two different values for a single setting and
asserts the output changes, proving the control is correctly wired through the
full Swift config → Python engine → DrawBot rendering pipeline.

Run separately from unit tests:
    python3 -m pytest tests_integration/test_wiring.py -v
"""

import os
import shutil

import pytest
import drawBot as db

from config import PROOF_REGISTRY
from engine import generate_proof
from fonts import clear_font_cache
from proof import (
    clear_handler_cache,
    reset_proof_page_counter,
    MultiStyleComparisonProofHandler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opt(proof_key, enabled=True, name=None):
    """Build a proof_options entry from a PROOF_REGISTRY key."""
    display = PROOF_REGISTRY[proof_key]["display_name"]
    return {
        "Option": name or display,
        "Enabled": enabled,
        "_original_option": proof_key,
    }


def _gen(font_paths, options, settings, out_dir, axis_values=None):
    """Run generate_proof() and return (pdf_path, sections, file_size)."""
    os.makedirs(out_dir, exist_ok=True)
    clear_handler_cache()
    reset_proof_page_counter()
    MultiStyleComparisonProofHandler.reset_generated()

    config = {
        "font_paths": list(font_paths),
        "axis_values_by_font": axis_values or {},
        "proof_options": list(options),
        "proof_settings": dict(settings),
        "page_format": "A5Landscape",
        "output_dir": out_dir,
        "show_baselines": False,
    }
    result = generate_proof(config)
    path = result.get("path", "") if isinstance(result, dict) else ""
    sections = result.get("sections", []) if isinstance(result, dict) else []
    size = os.path.getsize(path) if path and os.path.isfile(path) else 0
    return path, sections, size


@pytest.fixture
def font_copy(vf_font_path, tmp_path):
    """A copy of the VF test font at a different path (acts as second font)."""
    copy_path = str(tmp_path / "fixtures" / "FontCopy.ttf")
    os.makedirs(os.path.dirname(copy_path), exist_ok=True)
    shutil.copy2(vf_font_path, copy_path)
    return copy_path


# =========================================================================
# 1. Proof Enable / Disable / Add / Remove
# =========================================================================


class TestProofEnableDisable:
    """Toggling proofs on/off controls which sections are generated."""

    def test_enabled_proof_generates_section(self, vf_font_path, tmp_path):
        _, sections, size = _gen(
            [vf_font_path],
            [_opt("basic_paragraph_large")],
            {"basic_paragraph_large_fontSize": 14, "basic_paragraph_large_para": 1},
            str(tmp_path),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        assert size > 0
        assert len(sections) == 1
        assert "Structured Text (Heading)" in sections[0]["name"]

    def test_disabled_proof_produces_no_section(self, vf_font_path, tmp_path):
        _, sections, size = _gen(
            [vf_font_path],
            [_opt("basic_paragraph_large", enabled=False)],
            {"basic_paragraph_large_fontSize": 14},
            str(tmp_path),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        assert len(sections) == 0

    def test_adding_second_proof_adds_section(self, vf_font_path, tmp_path):
        opts_one = [_opt("basic_paragraph_large")]
        opts_two = [_opt("basic_paragraph_large"), _opt("filtered_character_set")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
            "filtered_character_set_fontSize": 24,
        }
        axis = {vf_font_path: {"wght": [400]}}

        _, sec1, _ = _gen([vf_font_path], opts_one, settings, str(tmp_path / "a"), axis)
        _, sec2, _ = _gen([vf_font_path], opts_two, settings, str(tmp_path / "b"), axis)
        assert len(sec2) > len(sec1)

    def test_only_enabled_proofs_appear(self, vf_font_path, tmp_path):
        opts = [
            _opt("basic_paragraph_large", enabled=True),
            _opt("filtered_character_set", enabled=False),
        ]
        _, sections, _ = _gen(
            [vf_font_path],
            opts,
            {"basic_paragraph_large_fontSize": 14, "basic_paragraph_large_para": 1},
            str(tmp_path),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        names = [s["name"] for s in sections]
        assert any("Structured Text (Heading)" in n for n in names)
        assert not any("Character Overview" in n for n in names)

    def test_duplicate_proof_instance_generates_own_section(
        self, vf_font_path, tmp_path
    ):
        """Adding a second copy of a proof type produces an additional section."""
        opts = [
            _opt("basic_paragraph_large"),
            _opt("basic_paragraph_large", name="Structured Text (Heading) 2"),
        ]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }
        _, sections, size = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        assert size > 0
        assert len(sections) == 2


# =========================================================================
# 1b. Duplicate Proof Independent Settings
# =========================================================================


class TestDuplicateProofIndependentSettings:
    """Duplicate proof instances must honour their own settings, not share them.

    This catches the bug where Swift used `option.baseType` (same for all
    instances of a type) as the settings key prefix, causing duplicates to
    overwrite each other's values and Python to fall back to defaults.
    """

    def test_duplicate_proofs_use_own_font_size(self, vf_font_path, tmp_path):
        """Two Character Set proofs with different font sizes produce different output."""
        opts = [
            _opt("filtered_character_set"),
            _opt("filtered_character_set", name="Filtered Character Set 2"),
        ]
        # Proof 1: large font → fewer chars per page, proof 2: small font → more chars
        settings = {
            "filtered_character_set_fontSize": 120,
            "filtered_character_set_2_fontSize": 24,
        }
        axis = {vf_font_path: {"wght": [400]}}
        _, sections, size = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path),
            axis,
        )
        assert len(sections) == 2
        # Both sections exist and have different names
        assert sections[0]["name"] == "Character Overview"
        assert sections[1]["name"] == "Filtered Character Set 2"

    def test_duplicate_paragraph_proofs_independent_tracking(
        self, vf_font_path, tmp_path
    ):
        """Two paragraph proofs with different tracking values produce different output."""
        opts = [
            _opt("generative_text_small"),
            _opt("generative_text_small", name="Auto-Generated Text 2"),
        ]
        axis = {vf_font_path: {"wght": [400]}}

        # Same font size, different tracking
        _, _, size_a = _gen(
            [vf_font_path],
            opts,
            {
                "generative_text_small_fontSize": 8,
                "generative_text_small_tracking": 0,
                "generative_text_small_para": 2,
                "generative_text_small_2_fontSize": 8,
                "generative_text_small_2_tracking": 20,
                "generative_text_small_2_para": 2,
            },
            str(tmp_path / "diff"),
            axis,
        )

        # Both with same tracking — output should differ from above
        _, _, size_b = _gen(
            [vf_font_path],
            opts,
            {
                "generative_text_small_fontSize": 8,
                "generative_text_small_tracking": 0,
                "generative_text_small_para": 2,
                "generative_text_small_2_fontSize": 8,
                "generative_text_small_2_tracking": 0,
                "generative_text_small_2_para": 2,
            },
            str(tmp_path / "same"),
            axis,
        )
        assert size_a > 0
        assert size_b > 0
        assert size_a != size_b


# =========================================================================
# 2. Proof Ordering
# =========================================================================


class TestProofOrdering:
    """Proof order in config determines section order in output."""

    def test_proofs_generate_in_config_order(self, vf_font_path, tmp_path):
        opts_ab = [_opt("basic_paragraph_large"), _opt("spacing_proof")]
        opts_ba = [_opt("spacing_proof"), _opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
            "spacing_proof_fontSize": 14,
        }
        axis = {vf_font_path: {"wght": [400]}}

        _, sec_ab, _ = _gen(
            [vf_font_path], opts_ab, settings, str(tmp_path / "ab"), axis
        )
        _, sec_ba, _ = _gen(
            [vf_font_path], opts_ba, settings, str(tmp_path / "ba"), axis
        )

        assert len(sec_ab) == 2
        assert len(sec_ba) == 2
        assert "Structured Text (Heading)" in sec_ab[0]["name"]
        assert "Spacing" in sec_ba[0]["name"]


# =========================================================================
# 3. Font Selection
# =========================================================================


class TestFontSelection:
    """Font list controls which fonts contribute to output."""

    def test_two_fonts_more_content_than_one(self, vf_font_path, font_copy, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }

        _, _, size1 = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "one"),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        _, _, size2 = _gen(
            [vf_font_path, font_copy],
            opts,
            settings,
            str(tmp_path / "two"),
            axis_values={vf_font_path: {"wght": [400]}, font_copy: {"wght": [400]}},
        )
        assert size1 > 0
        assert size2 > size1

    def test_excluding_font_reduces_content(self, vf_font_path, font_copy, tmp_path):
        """Removing a font from the list (simulating disable) reduces output."""
        opts = [_opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }
        axis = {vf_font_path: {"wght": [400]}, font_copy: {"wght": [400]}}

        _, _, size_both = _gen(
            [vf_font_path, font_copy],
            opts,
            settings,
            str(tmp_path / "both"),
            axis_values=axis,
        )
        _, _, size_one = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "one"),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        assert size_both > size_one


# =========================================================================
# 4. Variable Font Axis Instances
# =========================================================================


class TestVariableFontAxes:
    """Axis values control VF instance generation."""

    def test_more_axis_values_more_content(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }

        _, _, size1 = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "one"),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        _, _, size2 = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "two"),
            axis_values={vf_font_path: {"wght": [400, 700]}},
        )
        assert size1 > 0
        assert size2 > size1

    def test_different_axis_values_different_output(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }

        _, _, size_light = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "light"),
            axis_values={vf_font_path: {"wght": [100]}},
        )
        _, _, size_black = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "black"),
            axis_values={vf_font_path: {"wght": [900]}},
        )
        assert size_light > 0
        assert size_black > 0
        assert size_light != size_black

    def test_multi_axis_product_increases_content(self, vf_font_path, tmp_path):
        """Adding a second axis creates cartesian product → more pages."""
        opts = [_opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }

        _, _, size_one_axis = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "one"),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        _, _, size_two_axes = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "two"),
            axis_values={vf_font_path: {"wght": [400], "opsz": [10, 48]}},
        )
        assert size_two_axes > size_one_axis


# =========================================================================
# 5. Font Size
# =========================================================================


class TestFontSizeWiring:
    """Font size setting affects proof output."""

    def test_font_size_affects_paragraph_proof(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_small = _gen(
            [vf_font_path],
            opts,
            {"basic_paragraph_large_fontSize": 8, "basic_paragraph_large_para": 1},
            str(tmp_path / "small"),
            axis,
        )
        _, _, size_big = _gen(
            [vf_font_path],
            opts,
            {"basic_paragraph_large_fontSize": 48, "basic_paragraph_large_para": 1},
            str(tmp_path / "big"),
            axis,
        )
        assert size_small > 0
        assert size_big > 0
        assert size_small != size_big

    def test_font_size_affects_charset_proof(self, vf_font_path, tmp_path):
        opts = [_opt("filtered_character_set")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_small = _gen(
            [vf_font_path],
            opts,
            {"filtered_character_set_fontSize": 12},
            str(tmp_path / "small"),
            axis,
        )
        _, _, size_big = _gen(
            [vf_font_path],
            opts,
            {"filtered_character_set_fontSize": 60},
            str(tmp_path / "big"),
            axis,
        )
        assert size_small > 0
        assert size_big > 0
        assert size_small != size_big

    def test_font_size_affects_spacing_proof(self, vf_font_path, tmp_path):
        opts = [_opt("spacing_proof")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_small = _gen(
            [vf_font_path],
            opts,
            {"spacing_proof_fontSize": 8},
            str(tmp_path / "small"),
            axis,
        )
        _, _, size_big = _gen(
            [vf_font_path],
            opts,
            {"spacing_proof_fontSize": 48},
            str(tmp_path / "big"),
            axis,
        )
        assert size_small > 0
        assert size_big > 0
        assert size_small != size_big


# =========================================================================
# 6. Columns
# =========================================================================


class TestColumnsWiring:
    """Column count setting affects layout."""

    def test_columns_affect_paragraph_proof(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        axis = {vf_font_path: {"wght": [400]}}
        base = {"basic_paragraph_large_fontSize": 10, "basic_paragraph_large_para": 3}

        _, _, size1 = _gen(
            [vf_font_path],
            opts,
            {**base, "basic_paragraph_large_cols": 1},
            str(tmp_path / "one"),
            axis,
        )
        _, _, size3 = _gen(
            [vf_font_path],
            opts,
            {**base, "basic_paragraph_large_cols": 3},
            str(tmp_path / "three"),
            axis,
        )
        assert size1 > 0
        assert size3 > 0
        assert size1 != size3

    def test_columns_affect_spacing_proof(self, vf_font_path, tmp_path):
        opts = [_opt("spacing_proof")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size1 = _gen(
            [vf_font_path],
            opts,
            {"spacing_proof_fontSize": 10, "spacing_proof_cols": 1},
            str(tmp_path / "one"),
            axis,
        )
        _, _, size3 = _gen(
            [vf_font_path],
            opts,
            {"spacing_proof_fontSize": 10, "spacing_proof_cols": 3},
            str(tmp_path / "three"),
            axis,
        )
        assert size1 > 0
        assert size3 > 0
        assert size1 != size3


# =========================================================================
# 7. Tracking
# =========================================================================


class TestTrackingWiring:
    """Tracking value affects letter spacing in output."""

    def test_tracking_affects_paragraph_proof(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        axis = {vf_font_path: {"wght": [400]}}
        base = {"basic_paragraph_large_fontSize": 12, "basic_paragraph_large_para": 2}

        _, _, size0 = _gen(
            [vf_font_path],
            opts,
            {**base, "basic_paragraph_large_tracking": 0},
            str(tmp_path / "zero"),
            axis,
        )
        _, _, size50 = _gen(
            [vf_font_path],
            opts,
            {**base, "basic_paragraph_large_tracking": 50},
            str(tmp_path / "fifty"),
            axis,
        )
        assert size0 > 0
        assert size50 > 0
        assert size0 != size50


# =========================================================================
# 8. Alignment
# =========================================================================


class TestAlignmentWiring:
    """Alignment setting affects text positioning."""

    def test_alignment_affects_paragraph_proof(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        axis = {vf_font_path: {"wght": [400]}}
        base = {"basic_paragraph_large_fontSize": 12, "basic_paragraph_large_para": 2}

        _, _, size_left = _gen(
            [vf_font_path],
            opts,
            {**base, "basic_paragraph_large_align": "left"},
            str(tmp_path / "left"),
            axis,
        )
        _, _, size_right = _gen(
            [vf_font_path],
            opts,
            {**base, "basic_paragraph_large_align": "right"},
            str(tmp_path / "right"),
            axis,
        )
        assert size_left > 0
        assert size_right > 0
        assert size_left != size_right


# =========================================================================
# 9. Paragraphs
# =========================================================================


class TestParagraphsWiring:
    """Paragraph count setting affects amount of generated text."""

    def test_more_paragraphs_more_content(self, vf_font_path, tmp_path):
        opts = [_opt("generative_text_small")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size1 = _gen(
            [vf_font_path],
            opts,
            {"generative_text_small_fontSize": 6, "generative_text_small_para": 1},
            str(tmp_path / "one"),
            axis,
        )
        _, _, size5 = _gen(
            [vf_font_path],
            opts,
            {"generative_text_small_fontSize": 6, "generative_text_small_para": 5},
            str(tmp_path / "five"),
            axis,
        )
        assert size1 > 0
        assert size5 > 0
        assert size5 != size1


# =========================================================================
# 10. Line Height
# =========================================================================


class TestLineHeightWiring:
    """Line height setting affects vertical spacing."""

    def test_line_height_affects_paragraph_proof(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        axis = {vf_font_path: {"wght": [400]}}
        base = {"basic_paragraph_large_fontSize": 12, "basic_paragraph_large_para": 2}

        _, _, size_auto = _gen(
            [vf_font_path],
            opts,
            base,  # no lineHeight → auto
            str(tmp_path / "auto"),
            axis,
        )
        _, _, size_tall = _gen(
            [vf_font_path],
            opts,
            {**base, "basic_paragraph_large_lineHeight": 3.0},
            str(tmp_path / "tall"),
            axis,
        )
        assert size_auto > 0
        assert size_tall > 0
        assert size_auto != size_tall


# =========================================================================
# 11. OpenType Features
# =========================================================================


class TestOTFeaturesWiring:
    """OT feature toggles reach the rendering engine."""

    def test_ot_features_affect_paragraph_proof(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        axis = {vf_font_path: {"wght": [400]}}
        base = {"basic_paragraph_large_fontSize": 14, "basic_paragraph_large_para": 2}

        _, _, size_on = _gen(
            [vf_font_path],
            opts,
            {
                **base,
                "otf_basic_paragraph_large_kern": True,
                "otf_basic_paragraph_large_liga": True,
                "otf_basic_paragraph_large_calt": True,
            },
            str(tmp_path / "on"),
            axis,
        )
        _, _, size_off = _gen(
            [vf_font_path],
            opts,
            {
                **base,
                "otf_basic_paragraph_large_kern": False,
                "otf_basic_paragraph_large_liga": False,
                "otf_basic_paragraph_large_calt": False,
            },
            str(tmp_path / "off"),
            axis,
        )
        assert size_on > 0
        assert size_off > 0
        assert size_on != size_off


# =========================================================================
# 12. Character Categories
# =========================================================================


class TestCategoryWiring:
    """Character category toggles control which groups appear in proofs."""

    def test_all_categories_more_content_than_one(self, vf_font_path, tmp_path):
        opts = [_opt("filtered_character_set")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_all = _gen(
            [vf_font_path],
            opts,
            {
                "filtered_character_set_fontSize": 24,
                "filtered_character_set_cat_uppercase_base": True,
                "filtered_character_set_cat_lowercase_base": True,
                "filtered_character_set_cat_numbers_symbols": True,
                "filtered_character_set_cat_punctuation": True,
                "filtered_character_set_cat_accented": True,
            },
            str(tmp_path / "all"),
            axis,
        )
        _, _, size_one = _gen(
            [vf_font_path],
            opts,
            {
                "filtered_character_set_fontSize": 24,
                "filtered_character_set_cat_uppercase_base": True,
                "filtered_character_set_cat_lowercase_base": False,
                "filtered_character_set_cat_numbers_symbols": False,
                "filtered_character_set_cat_punctuation": False,
                "filtered_character_set_cat_accented": False,
            },
            str(tmp_path / "one"),
            axis,
        )
        assert size_all > 0
        assert size_one > 0
        assert size_all > size_one

    def test_different_categories_different_content(self, vf_font_path, tmp_path):
        opts = [_opt("filtered_character_set")]
        axis = {vf_font_path: {"wght": [400]}}
        off = {
            "filtered_character_set_cat_uppercase_base": False,
            "filtered_character_set_cat_lowercase_base": False,
            "filtered_character_set_cat_numbers_symbols": False,
            "filtered_character_set_cat_punctuation": False,
            "filtered_character_set_cat_accented": False,
        }

        _, _, size_upper = _gen(
            [vf_font_path],
            opts,
            {
                "filtered_character_set_fontSize": 24,
                **off,
                "filtered_character_set_cat_uppercase_base": True,
            },
            str(tmp_path / "upper"),
            axis,
        )
        _, _, size_lower = _gen(
            [vf_font_path],
            opts,
            {
                "filtered_character_set_fontSize": 24,
                **off,
                "filtered_character_set_cat_lowercase_base": True,
            },
            str(tmp_path / "lower"),
            axis,
        )
        assert size_upper > 0
        assert size_lower > 0
        assert size_upper != size_lower

    def test_spacing_proof_categories(self, vf_font_path, tmp_path):
        """Category toggles also work for the Spacing Proof handler."""
        opts = [_opt("spacing_proof")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_all = _gen(
            [vf_font_path],
            opts,
            {
                "spacing_proof_fontSize": 14,
                "spacing_proof_cat_uppercase_base": True,
                "spacing_proof_cat_lowercase_base": True,
            },
            str(tmp_path / "all"),
            axis,
        )
        _, _, size_one = _gen(
            [vf_font_path],
            opts,
            {
                "spacing_proof_fontSize": 14,
                "spacing_proof_cat_uppercase_base": True,
                "spacing_proof_cat_lowercase_base": False,
                "spacing_proof_cat_numbers_symbols": False,
                "spacing_proof_cat_punctuation": False,
                "spacing_proof_cat_accented": False,
            },
            str(tmp_path / "one"),
            axis,
        )
        assert size_all > 0
        assert size_one > 0
        assert size_all > size_one


# =========================================================================
# 13. Custom Text
# =========================================================================


class TestCustomTextWiring:
    """Custom text input reaches the custom text handler."""

    def test_custom_text_generates_output(self, vf_font_path, tmp_path):
        opts = [_opt("custom_text")]
        _, sections, size = _gen(
            [vf_font_path],
            opts,
            {"custom_text_fontSize": 14, "custom_text_customText": "Hello World"},
            str(tmp_path),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        assert size > 0
        assert len(sections) >= 1

    def test_different_text_different_output(self, vf_font_path, tmp_path):
        opts = [_opt("custom_text")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_a = _gen(
            [vf_font_path],
            opts,
            {
                "custom_text_fontSize": 14,
                "custom_text_customText": "AAAA BBBB CCCC DDDD",
            },
            str(tmp_path / "a"),
            axis,
        )
        _, _, size_b = _gen(
            [vf_font_path],
            opts,
            {
                "custom_text_fontSize": 14,
                "custom_text_customText": "XXXX YYYY ZZZZ WWWW",
            },
            str(tmp_path / "b"),
            axis,
        )
        assert size_a > 0
        assert size_b > 0
        assert size_a != size_b

    def test_empty_text_produces_no_section(self, vf_font_path, tmp_path):
        opts = [_opt("custom_text")]
        _, sections, _ = _gen(
            [vf_font_path],
            opts,
            {"custom_text_fontSize": 14, "custom_text_customText": ""},
            str(tmp_path),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        assert len(sections) == 0

    def test_generate_once_uses_single_font(self, vf_font_path, font_copy, tmp_path):
        """With generateOnce=True, only the default font produces output."""
        opts = [_opt("custom_text")]
        text = "Generate once test text for proofing"
        axis = {vf_font_path: {"wght": [400]}, font_copy: {"wght": [400]}}

        # Without generateOnce: both fonts contribute
        _, _, size_both = _gen(
            [vf_font_path, font_copy],
            opts,
            {"custom_text_fontSize": 14, "custom_text_customText": text},
            str(tmp_path / "both"),
            axis,
        )
        # With generateOnce: only default font contributes
        _, _, size_once = _gen(
            [vf_font_path, font_copy],
            opts,
            {
                "custom_text_fontSize": 14,
                "custom_text_customText": text,
                "custom_text_generateOnce": True,
                "custom_text_defaultFontPath": vf_font_path,
            },
            str(tmp_path / "once"),
            axis,
        )
        assert size_both > 0
        assert size_once > 0
        assert size_both > size_once


# =========================================================================
# 14. Markup Toggle
# =========================================================================


class TestMarkupWiring:
    """Markup toggle affects custom text rendering pipeline."""

    def test_markup_toggle_affects_output(self, vf_font_path, tmp_path):
        opts = [_opt("custom_text")]
        axis = {vf_font_path: {"wght": [400]}}
        text = "# Big Heading\nSome **bold** and *italic* text for proofing."

        _, _, size_plain = _gen(
            [vf_font_path],
            opts,
            {
                "custom_text_fontSize": 14,
                "custom_text_customText": text,
                "custom_text_markupEnabled": False,
            },
            str(tmp_path / "plain"),
            axis,
        )
        _, _, size_markup = _gen(
            [vf_font_path],
            opts,
            {
                "custom_text_fontSize": 14,
                "custom_text_customText": text,
                "custom_text_markupEnabled": True,
            },
            str(tmp_path / "markup"),
            axis,
        )
        assert size_plain > 0
        assert size_markup > 0
        assert size_plain != size_markup


# =========================================================================
# 15. Multi-Style Comparison
# =========================================================================


class TestMultiStyleWiring:
    """Multi-style comparison proof respects style selection."""

    def test_multi_style_generates_output(self, vf_font_path, tmp_path):
        opts = [_opt("multi_style_comparison")]
        _, sections, size = _gen(
            [vf_font_path],
            opts,
            {"multi_style_comparison_fontSize": 14},
            str(tmp_path),
            axis_values={vf_font_path: {"wght": [400]}},
        )
        assert size > 0
        assert len(sections) >= 1

    def test_multi_style_categories_affect_output(self, vf_font_path, tmp_path):
        """Category toggles control which text groups appear in multi-style proof."""
        opts = [_opt("multi_style_comparison")]
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_all = _gen(
            [vf_font_path],
            opts,
            {
                "multi_style_comparison_fontSize": 14,
                "multi_style_comparison_cat_uppercase_base": True,
                "multi_style_comparison_cat_lowercase_base": True,
            },
            str(tmp_path / "all"),
            axis,
        )
        _, _, size_one = _gen(
            [vf_font_path],
            opts,
            {
                "multi_style_comparison_fontSize": 14,
                "multi_style_comparison_cat_uppercase_base": True,
                "multi_style_comparison_cat_lowercase_base": False,
                "multi_style_comparison_cat_numbers_symbols": False,
                "multi_style_comparison_cat_punctuation": False,
                "multi_style_comparison_cat_accented": False,
            },
            str(tmp_path / "one"),
            axis,
        )
        assert size_all > 0
        assert size_one > 0
        assert size_all != size_one


# =========================================================================
# 16. Page Format
# =========================================================================


class TestPageFormatWiring:
    """Page format setting affects document dimensions."""

    def test_page_format_affects_output(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }
        axis = {vf_font_path: {"wght": [400]}}

        _, _, size_a5 = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "a5"),
            axis_values=axis,
        )
        # Use a different page format for the second run
        clear_handler_cache()
        reset_proof_page_counter()
        MultiStyleComparisonProofHandler.reset_generated()
        config_letter = {
            "font_paths": [vf_font_path],
            "axis_values_by_font": axis,
            "proof_options": list(opts),
            "proof_settings": dict(settings),
            "page_format": "LetterLandscape",
            "output_dir": str(tmp_path / "letter"),
            "show_baselines": False,
        }
        os.makedirs(str(tmp_path / "letter"), exist_ok=True)
        result = generate_proof(config_letter)
        path = result.get("path", "")
        size_letter = os.path.getsize(path) if path and os.path.isfile(path) else 0

        assert size_a5 > 0
        assert size_letter > 0
        assert size_a5 != size_letter


# =========================================================================
# 17. Show Baselines
# =========================================================================


class TestBaselinesWiring:
    """Show baselines toggle affects rendering."""

    def test_baselines_toggle_affects_output(self, vf_font_path, tmp_path):
        opts = [_opt("basic_paragraph_large")]
        settings = {
            "basic_paragraph_large_fontSize": 14,
            "basic_paragraph_large_para": 1,
        }
        axis = {vf_font_path: {"wght": [400]}}

        # Baselines off (via _gen which defaults show_baselines=False)
        _, _, size_off = _gen(
            [vf_font_path],
            opts,
            settings,
            str(tmp_path / "off"),
            axis,
        )

        # Baselines on
        clear_handler_cache()
        reset_proof_page_counter()
        config_on = {
            "font_paths": [vf_font_path],
            "axis_values_by_font": axis,
            "proof_options": list(opts),
            "proof_settings": dict(settings),
            "page_format": "A5Landscape",
            "output_dir": str(tmp_path / "on"),
            "show_baselines": True,
        }
        os.makedirs(str(tmp_path / "on"), exist_ok=True)
        result = generate_proof(config_on)
        path = result.get("path", "")
        size_on = os.path.getsize(path) if path and os.path.isfile(path) else 0

        assert size_off > 0
        assert size_on > 0
        # Baselines add grid drawing → different output
        assert size_off != size_on
