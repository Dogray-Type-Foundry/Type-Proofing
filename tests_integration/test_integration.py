"""Integration tests — real libraries (drawBot, fontTools, wordsiv), real fonts.

These tests exercise full user-facing workflows:
  1. Load font → extract charset → categorize → build proof categories
  2. Variable font axis detection and combination generation
  3. Text generation (wordsiv, sample texts, spacing, Arabic forms)
  4. Markup parsing full chain → FormattedString
  5. Settings round-trip through ProofSettingsManager
  6. Proof handler factory → handler configuration → proof data pipeline
  7. Headless PDF generation via drawBot
"""

import os
import unicodedata

import pytest
import drawBot as db
from fontTools.ttLib import TTFont

from fonts import (
    filteredCharset,
    categorize,
    check_arabic_support,
    get_charset_proof_categories,
    get_font_family_name,
    get_all_font_axes,
    variableFont,
    product_dict,
    find_accented,
    parse_axis_value,
    format_axis_values,
    parse_axis_values_string,
    FontManager,
)
from config import (
    PROOF_REGISTRY,
    get_proof_display_names,
    get_proof_settings_mapping,
    get_proof_default_font_size,
    proof_supports_formatting,
    get_text_proof_config,
    resolve_base_proof_key,
    resolve_character_set_by_key,
)
from settings import (
    Settings,
    ProofSettingsManager,
    normalize_path,
    make_settings_key,
    create_unique_proof_key,
)
from proof import (
    ProofContext,
    get_proof_handler,
    clear_handler_cache,
    BaseProofHandler,
    StandardTextProofHandler,
    FilteredCharacterSetHandler,
    CustomTextProofHandler,
    MultiStyleComparisonProofHandler,
    generateArabicContextualFormsProof,
    generateSpacingString,
    generateTextProofString,
    reset_proof_page_counter,
    get_font_display_name,
    _normalize_axes,
)
from markup_parser import (
    _escape,
    _restore,
    _tokenize,
    _parse_attrs,
    _parse_hex_color,
    parse_custom_text,
)


# =============================================================================
# 1. Font Loading → Character Analysis Pipeline
# =============================================================================


class TestFontCharacterAnalysis:
    """Load a real font, extract charset, categorize, build proof categories."""

    def test_filtered_charset_returns_string(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        assert isinstance(charset, str)
        assert len(charset) > 50  # SetGroteskVF has 482 cmap entries

    def test_charset_contains_basic_latin(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789":
            assert ch in charset, f"Missing basic Latin char: {ch!r}"

    def test_categorize_real_charset(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)

        # Must have all expected keys
        expected_keys = {
            "uniLu",
            "uniLl",
            "uniLuBase",
            "uniLlBase",
            "uniLo",
            "uniPo",
            "uniPc",
            "uniPd",
            "uniPs",
            "uniPe",
            "uniPi",
            "uniPf",
            "uniSm",
            "uniSc",
            "uniNd",
            "uniNo",
            "uniSo",
            "accented",
            "accented_plus",
            "latn",
            "arab",
            "fa",
            "ar",
            "arabTyped",
            "arfaDualJoin",
            "arfaRightJoin",
            "uppercaseOnly",
            "lowercaseOnly",
        }
        assert expected_keys.issubset(set(cat.keys()))

        # SetGroteskVF is Latin, so uppercase and lowercase exist
        assert len(cat["uniLu"]) >= 26
        assert len(cat["uniLl"]) >= 26
        assert cat["uppercaseOnly"] is False
        assert cat["lowercaseOnly"] is False

    def test_categorize_detects_latin_script(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        assert len(cat["latn"]) > 0
        assert len(cat["arab"]) == 0  # No Arabic in SetGroteskVF

    def test_categorize_separates_base_and_accented(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        # Base chars should not overlap with accented
        base_upper = set(cat["uniLuBase"])
        accented = set(cat["accented"])
        assert base_upper.isdisjoint(accented)

    def test_check_arabic_support_latin_font(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        assert check_arabic_support(charset) is False

    def test_proof_categories_structure(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        categories = get_charset_proof_categories(cat)

        assert "uppercase_base" in categories
        assert "lowercase_base" in categories
        assert "numbers_symbols" in categories
        assert "punctuation" in categories
        assert "accented" in categories

        # Each value is a string of characters
        assert isinstance(categories["uppercase_base"], str)
        assert "A" in categories["uppercase_base"]

    def test_proof_categories_uppercase_sorted(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        categories = get_charset_proof_categories(cat)
        upper = categories["uppercase_base"]
        assert upper == "".join(sorted(upper, key=ord))

    def test_full_pipeline_font_to_categories(self, vf_font_path):
        """End-to-end: font file → charset → categorize → proof categories."""
        charset = filteredCharset(vf_font_path)
        assert len(charset) > 0

        cat = categorize(charset)
        assert cat["uniLu"]  # Has uppercase
        assert cat["uniNd"]  # Has digits

        categories = get_charset_proof_categories(cat)
        # All default categories should have content for a Latin font
        assert len(categories["uppercase_base"]) >= 26
        assert len(categories["lowercase_base"]) >= 26
        assert len(categories["numbers_symbols"]) >= 10


# =============================================================================
# 2. Variable Font Axis Detection
# =============================================================================


class TestVariableFontAxes:
    """Test axis detection and combination generation on a real VF."""

    def test_variable_font_detects_axes(self, vf_font_path):
        axes_product, axes_dict = variableFont(vf_font_path)
        assert "wght" in axes_dict
        assert "opsz" in axes_dict

    def test_variable_font_axis_values(self, vf_font_path):
        axes_product, axes_dict = variableFont(vf_font_path)
        # wght: 100–900 with default 400
        wght_vals = axes_dict["wght"]
        assert min(wght_vals) == 100
        assert max(wght_vals) == 900

    def test_variable_font_product_combinations(self, vf_font_path):
        axes_product, axes_dict = variableFont(vf_font_path)
        assert isinstance(axes_product, list)
        assert len(axes_product) > 0
        # Each combination is a dict mapping axis tag → value
        combo = axes_product[0]
        assert isinstance(combo, dict)
        assert "wght" in combo
        assert "opsz" in combo

    def test_get_all_font_axes(self, vf_font_path):
        axes = get_all_font_axes([vf_font_path])
        assert "wght" in axes
        assert "opsz" in axes

    def test_get_font_family_name(self, vf_font_path):
        name = get_font_family_name(vf_font_path)
        assert "SetGrotesk" in name or "Set Grotesk" in name.replace("-", " ")

    def test_font_manager_with_real_font(self, vf_font_path):
        fm = FontManager()
        fm.add_fonts([vf_font_path])
        assert vf_font_path in fm.fonts
        axes = fm.get_all_axes()
        assert "wght" in axes


# =============================================================================
# 3. Text Generation Pipeline (wordsiv + sample_texts)
# =============================================================================


class TestTextGeneration:
    """Test text generation with real wordsiv and real character sets."""

    @pytest.fixture
    def real_cat(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        return categorize(charset)

    @pytest.fixture
    def real_charset(self, vf_font_path):
        return filteredCharset(vf_font_path)

    def test_generate_text_proof_basic(self, real_charset, real_cat):
        text = generateTextProofString(
            characterSet=real_cat["latn"],
            para=2,
            cat=real_cat,
            fullCharacterSet=real_charset,
        )
        assert isinstance(text, str)
        assert len(text) > 20

    def test_generate_text_proof_hoefler(self, real_charset, real_cat):
        text = generateTextProofString(
            characterSet=real_cat["latn"],
            para=2,
            cat=real_cat,
            fullCharacterSet=real_charset,
            hoeflerStyle=True,
        )
        assert isinstance(text, str)
        assert len(text) > 20

    def test_generate_text_proof_force_wordsiv(self, real_charset, real_cat):
        text = generateTextProofString(
            characterSet=real_cat["latn"],
            para=2,
            cat=real_cat,
            fullCharacterSet=real_charset,
            forceWordsiv=True,
        )
        assert isinstance(text, str)
        assert len(text) > 0

    def test_spacing_string_real_charset(self, real_charset):
        spacing = generateSpacingString(real_charset)
        assert isinstance(spacing, str)
        assert len(spacing) > 0
        # Each line is a spacing pattern: control+char combinations
        lines = spacing.strip().split("\n")
        assert len(lines) > 10  # Should have many lines for 482 chars

    def test_spacing_string_structure(self, real_charset):
        spacing = generateSpacingString(real_charset)
        lines = spacing.strip().split("\n")
        for line in lines[:5]:
            # Each line should contain control chars + the test char
            assert len(line) > 5

    def test_arabic_contextual_forms_empty(self):
        cat = {"arabTyped": "", "arfaDualJoin": "", "arfaRightJoin": ""}
        result = generateArabicContextualFormsProof(cat)
        assert result == ""

    def test_generate_text_empty_cat_returns_empty(self):
        result = generateTextProofString("ABC", cat=None)
        assert result == ""


# =============================================================================
# 4. Markup Parsing Full Chain
# =============================================================================


class TestMarkupIntegration:
    """Full markup parsing chain with real drawBot FormattedString."""

    def test_tokenize_complex_markup(self):
        text = "# Heading\nPlain text **bold** and *italic* words."
        tokens = _tokenize(text)
        kinds = [t.kind for t in tokens]
        assert "heading1" in kinds
        assert "bold" in kinds
        assert "italic" in kinds
        assert "plain" in kinds

    def test_tokenize_attr_span(self):
        text = "[styled text]{size: 24, color: #ff0000}"
        tokens = _tokenize(text)
        attr_tokens = [t for t in tokens if t.kind == "attr_span"]
        assert len(attr_tokens) == 1
        assert attr_tokens[0].text == "styled text"
        assert "size" in attr_tokens[0].attrs

    def test_parse_attrs_full(self):
        result = _parse_attrs("size: 24, color: #ff0000, feat: liga")
        assert result["size"] == "24"
        assert result["color"] == "#ff0000"
        assert result["feat"] == "liga"

    def test_parse_hex_color_integration(self):
        assert _parse_hex_color("#ff0000") == (1.0, 0.0, 0.0)
        assert _parse_hex_color("#00ff00") == (0.0, 1.0, 0.0)
        assert _parse_hex_color("#fff") == (1.0, 1.0, 1.0)

    def test_escape_restore_round_trip(self):
        original = r"Some \*escaped\* text with \#hash and \[brackets\]"
        escaped = _escape(original)
        assert "\\*" not in escaped
        result = _restore(escaped)
        assert "*escaped*" in result
        assert "#hash" in result
        assert "[brackets]" in result

    def test_full_markup_to_formatted_string(self, vf_font_path):
        """Full chain: markup → tokenize → build FormattedString via drawBot."""
        markup = "Hello **bold** world"
        result = parse_custom_text(
            markup,
            base_font_size=24,
            base_font=vf_font_path,
            all_fonts=[vf_font_path],
            font_manager=None,
            base_tracking=0,
            base_align="left",
            base_otfeatures={},
            base_axis_dict=None,
        )
        assert result is not None

    def test_markup_with_heading(self, vf_font_path):
        markup = "# Big Heading\nNormal paragraph text."
        result = parse_custom_text(
            markup,
            base_font_size=12,
            base_font=vf_font_path,
            all_fonts=[vf_font_path],
            font_manager=None,
            base_tracking=0,
            base_align="left",
            base_otfeatures={},
            base_axis_dict=None,
        )
        assert result is not None

    def test_markup_with_attributes(self, vf_font_path):
        markup = "[custom text]{size: 36}"
        result = parse_custom_text(
            markup,
            base_font_size=12,
            base_font=vf_font_path,
            all_fonts=[vf_font_path],
            font_manager=None,
            base_tracking=0,
            base_align="left",
            base_otfeatures={},
            base_axis_dict=None,
        )
        assert result is not None

    def test_markup_plain_text(self, vf_font_path):
        markup = "Just plain text, no formatting."
        result = parse_custom_text(
            markup,
            base_font_size=16,
            base_font=vf_font_path,
            all_fonts=[vf_font_path],
            font_manager=None,
            base_tracking=0,
            base_align="left",
            base_otfeatures={},
            base_axis_dict=None,
        )
        assert result is not None


# =============================================================================
# 5. Settings Round-Trip
# =============================================================================


class TestSettingsRoundTrip:
    """Verify settings save/load cycle with ProofSettingsManager."""

    def test_settings_save_and_reload(self, tmp_settings_path):
        s1 = Settings(settings_path=tmp_settings_path)
        s1.set("test_key", "test_value")
        s1.set_proof_option("basic_paragraph_small", True)
        s1.save()

        s2 = Settings(settings_path=tmp_settings_path)
        s2.load()
        assert s2.get("test_key") == "test_value"
        assert s2.get_proof_option("basic_paragraph_small") is True

    def test_proof_settings_manager_initialization(self, tmp_settings_path):
        settings = Settings(settings_path=tmp_settings_path)
        fm = FontManager()
        psm = ProofSettingsManager(settings, font_manager=fm)
        # __init__ already calls initialize_proof_settings()
        assert len(psm.proof_settings) > 0

    def test_build_proof_data_structure(self, tmp_settings_path):
        settings = Settings(settings_path=tmp_settings_path)
        fm = FontManager()
        psm = ProofSettingsManager(settings, font_manager=fm)

        items = [
            {
                "Option": "Basic Paragraph Small",
                "Enabled": True,
                "_original_option": "Basic Paragraph Small",
            },
            {
                "Option": "Filtered Character Set",
                "Enabled": True,
                "_original_option": "Filtered Character Set",
            },
            {
                "Option": "Custom Text",
                "Enabled": False,
                "_original_option": "Custom Text",
            },
        ]
        otf, cols, paras = psm.build_proof_data_for_generation(items)

        # Only enabled proofs should be in the output
        assert "Basic Paragraph Small" in otf
        assert "Filtered Character Set" in otf
        assert "Custom Text" not in otf

        # OT features are dicts
        assert isinstance(otf["Basic Paragraph Small"], dict)

    def test_font_size_settings_persistence(self, tmp_settings_path):
        settings = Settings(settings_path=tmp_settings_path)
        fm = FontManager()
        psm = ProofSettingsManager(settings, font_manager=fm)

        # Update a font size
        key = make_settings_key("basic_paragraph_small", "fontSize")
        psm.proof_settings[key] = 42
        settings.set("proof_settings", psm.proof_settings)
        settings.save()

        # Reload
        s2 = Settings(settings_path=tmp_settings_path)
        s2.load()
        reloaded = s2.get("proof_settings", {})
        assert reloaded.get(key) == 42

    def test_settings_column_values(self, tmp_settings_path):
        settings = Settings(settings_path=tmp_settings_path)
        fm = FontManager()
        psm = ProofSettingsManager(settings, font_manager=fm)

        items = [
            {
                "Option": "Basic Paragraph Small",
                "Enabled": True,
                "_original_option": "Basic Paragraph Small",
            },
        ]
        _, cols, _ = psm.build_proof_data_for_generation(items)
        if "Basic Paragraph Small" in cols:
            assert isinstance(cols["Basic Paragraph Small"], (int, float))


# =============================================================================
# 6. Proof Handler Factory → Configuration Pipeline
# =============================================================================


class TestProofHandlerPipeline:
    """Test the handler factory and proof data pipeline with real config."""

    @pytest.fixture(autouse=True)
    def clear(self):
        clear_handler_cache()
        yield
        clear_handler_cache()

    def test_all_registry_proofs_get_handlers(self):
        """Every proof type in the registry should produce a valid handler."""
        mapping = get_proof_settings_mapping()
        for display_name, settings_key in mapping.items():
            handler = get_proof_handler(
                display_name,
                display_name,
                {},
                get_proof_default_font_size,
            )
            assert isinstance(
                handler, BaseProofHandler
            ), f"No handler for {display_name}"
            clear_handler_cache()

    def test_handler_font_size_from_config(self):
        handler = get_proof_handler(
            "Basic Paragraph Small",
            "Basic Paragraph Small",
            {},
            get_proof_default_font_size,
        )
        size = handler.get_font_size()
        # get_font_size calls the func with the display name
        expected = get_proof_default_font_size("Basic Paragraph Small")
        assert size == expected

    def test_handler_common_params_with_real_data(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        handler = get_proof_handler(
            "Filtered Character Set",
            "Filtered Character Set",
            {},
            get_proof_default_font_size,
        )
        ctx = ProofContext(
            full_character_set=charset,
            axes_product=None,
            ind_font=vf_font_path,
            paired_static_styles=None,
            otfeatures_by_proof={"Filtered Character Set": {"kern": True}},
            cols_by_proof={"Filtered Character Set": 2},
            paras_by_proof={},
            cat=cat,
            proof_name="Filtered Character Set",
        )
        params = handler.get_common_proof_params(
            ctx, default_columns=1, default_paragraphs=5
        )
        assert params["font_size"] > 0
        assert params["columns"] == 2
        assert params["otfeatures"] == {"kern": True}

    def test_standard_text_handler_gets_character_set(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        handler = get_proof_handler(
            "Basic Paragraph Large",
            "Basic Paragraph Large",
            {},
            get_proof_default_font_size,
        )
        assert isinstance(handler, StandardTextProofHandler)
        ctx = ProofContext(
            full_character_set=charset,
            axes_product=None,
            ind_font=vf_font_path,
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat=cat,
            proof_name="Basic Paragraph Large",
        )
        cs = handler.get_character_set(ctx)
        assert isinstance(cs, str)
        assert len(cs) > 0

    def test_category_handler_sections_with_real_font(self, vf_font_path):
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        handler = get_proof_handler(
            "Filtered Character Set",
            "Filtered Character Set",
            {},
            get_proof_default_font_size,
        )
        ctx = ProofContext(
            full_character_set=charset,
            axes_product=None,
            ind_font=vf_font_path,
            paired_static_styles=None,
            otfeatures_by_proof={},
            cols_by_proof={},
            paras_by_proof={},
            cat=cat,
            proof_name="Filtered Character Set",
        )
        sections = handler.get_proof_sections(ctx)
        labels = [s[0] for s in sections]
        assert "Uppercase Base" in labels
        assert "Lowercase Base" in labels

    def test_end_to_end_settings_to_handler(self, tmp_settings_path, vf_font_path):
        """Full pipeline: settings → proof data → handler → params."""
        settings = Settings(settings_path=tmp_settings_path)
        fm = FontManager()
        psm = ProofSettingsManager(settings, font_manager=fm)

        items = [
            {
                "Option": "Basic Paragraph Small",
                "Enabled": True,
                "_original_option": "Basic Paragraph Small",
            },
        ]
        otf, cols, paras = psm.build_proof_data_for_generation(items)

        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)

        handler = get_proof_handler(
            "Basic Paragraph Small",
            "Basic Paragraph Small",
            psm.proof_settings,
            get_proof_default_font_size,
        )
        ctx = ProofContext(
            full_character_set=charset,
            axes_product=None,
            ind_font=vf_font_path,
            paired_static_styles=None,
            otfeatures_by_proof=otf,
            cols_by_proof=cols,
            paras_by_proof=paras,
            cat=cat,
            proof_name="Basic Paragraph Small",
        )
        params = handler.get_common_proof_params(
            ctx, default_columns=2, default_paragraphs=5
        )
        assert params["font_size"] > 0
        assert isinstance(params["otfeatures"], dict)


# =============================================================================
# 7. Headless drawBot PDF Generation
# =============================================================================


class TestDrawBotPDFGeneration:
    """Test actual PDF generation through drawBot headless mode."""

    def test_basic_page_creation(self, tmp_pdf_path):
        db.newDrawing()
        db.newPage(612, 792)
        db.font("Helvetica", 12)
        db.text("Test", (72, 700))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)
        assert os.path.getsize(tmp_pdf_path) > 0

    def test_formatted_string_with_real_font(self, vf_font_path, tmp_pdf_path):
        db.newDrawing()
        db.newPage(612, 792)
        fs = db.FormattedString(
            txt="Hello Type Proofing",
            font=vf_font_path,
            fontSize=24,
        )
        db.textBox(fs, (72, 72, 468, 648))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)
        assert os.path.getsize(tmp_pdf_path) > 100

    def test_variable_font_axis_rendering(self, vf_font_path, tmp_pdf_path):
        """Render the same text at different weight axis values."""
        db.newDrawing()
        for wght in [100, 400, 900]:
            db.newPage(612, 792)
            fs = db.FormattedString(
                txt=f"Weight {wght}",
                font=vf_font_path,
                fontSize=36,
                fontVariations=dict(wght=wght),
            )
            db.textBox(fs, (72, 350, 468, 100))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)
        # Should have 3 pages
        assert os.path.getsize(tmp_pdf_path) > 200

    def test_multi_page_pdf(self, vf_font_path, tmp_pdf_path):
        db.newDrawing()
        for i in range(5):
            db.newPage(612, 792)
            db.font(vf_font_path, 14)
            db.text(f"Page {i + 1}", (72, 700))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)
        assert os.path.getsize(tmp_pdf_path) > 500

    def test_opentype_features_applied(self, vf_font_path, tmp_pdf_path):
        db.newDrawing()
        db.newPage(612, 792)
        fs = db.FormattedString(
            txt="1/2 3/4",
            font=vf_font_path,
            fontSize=48,
            openTypeFeatures=dict(frac=True),
        )
        db.textBox(fs, (72, 350, 468, 100))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)

    def test_font_charset_to_pdf(self, vf_font_path, tmp_pdf_path):
        """Full flow: extract charset → generate spacing string → render to PDF."""
        charset = filteredCharset(vf_font_path)
        spacing = generateSpacingString(charset)

        db.newDrawing()
        db.newPage(612, 792)
        fs = db.FormattedString(
            txt=spacing[:500],  # First 500 chars to keep test fast
            font=vf_font_path,
            fontSize=10,
        )
        db.textBox(fs, (72, 72, 468, 648))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)
        assert os.path.getsize(tmp_pdf_path) > 200

    def test_text_generation_to_pdf(self, vf_font_path, tmp_pdf_path):
        """Full flow: font → charset → categorize → generate text → render PDF."""
        charset = filteredCharset(vf_font_path)
        cat = categorize(charset)
        text = generateTextProofString(
            characterSet=cat["latn"],
            para=1,
            cat=cat,
            fullCharacterSet=charset,
        )
        assert len(text) > 0

        db.newDrawing()
        db.newPage(612, 792)
        fs = db.FormattedString(
            txt=text[:1000],
            font=vf_font_path,
            fontSize=10,
        )
        db.textBox(fs, (72, 72, 468, 648))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)

    def test_markup_to_pdf(self, vf_font_path, tmp_pdf_path):
        """Full flow: markup string → parse → FormattedString → render PDF."""
        markup = "# SetGrotesk Heading\nSome **bold** and *italic* text for proofing."
        fs = parse_custom_text(
            markup,
            base_font_size=14,
            base_font=vf_font_path,
            all_fonts=[vf_font_path],
            font_manager=None,
            base_tracking=0,
            base_align="left",
            base_otfeatures={},
            base_axis_dict=None,
        )

        db.newDrawing()
        db.newPage(612, 792)
        db.textBox(fs, (72, 72, 468, 648))
        db.saveImage(tmp_pdf_path)
        db.endDrawing()
        assert os.path.isfile(tmp_pdf_path)
        assert os.path.getsize(tmp_pdf_path) > 200
