# Proof Generation Functions, Text Processing, and Proof Handlers

from __future__ import annotations

import datetime
import os
import random
import traceback
import unicodedata
from typing import Optional, Iterator, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

import drawBot as db
from wordsiv import Vocab, WordSiv
import config as _cc
import config
from config import (
    marginHorizontal,
    marginVertical,
    myFallbackFont,
    useFontContainsCharacters,
    wordsivSeed,
    dualStyleSeed,
    FsSelection,
    posForms,
    DEFAULT_ON_FEATURES,
    DEFAULT_CHARSET_TRACKING,
    FOOTER_FONT_NAME,
    FOOTER_FONT_SIZE,
    FOOTER_FEATURES_FONT_SIZE,
    get_proof_default_font_size,
    get_text_proof_config,
    resolve_character_set_by_key,
)
from fonts import (
    get_ttfont,
    filteredCharset,
    UPPER_TEMPLATE as upperTemplate,
    LOWER_TEMPLATE as lowerTemplate,
)
from settings import make_settings_key, create_unique_proof_key
from config import get_otf_prefix

# product_dict not used in this module

try:
    from drawBotGrid import (
        BaselineGrid,
        columnBaselineGridTextBox,
        baselineGridTextBox,
        columnTextBox,
    )
except ImportError:
    print("Warning: drawBotGrid not found. Grid functionality will be limited.")
    BaselineGrid = None
    columnBaselineGridTextBox = None
    baselineGridTextBox = None
    columnTextBox = None

try:
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
    from accented_dictionary import (
        accentedDict,
        get_accented_words,
        get_accented_characters,
    )
    from text_generators import text_generator, TextGenerator

    class ProofTexts:
        def __init__(self):
            self.bigMixedText = bigMixedText
            self.bigLowerText = bigLowerText
            self.bigUpperText = bigUpperText
            self.smallMixedText = smallMixedText
            self.smallLowerText = smallLowerText
            self.smallUpperText = smallUpperText
            self.bigRandomNumbers = bigRandomNumbers
            self.additionalSmallText = additionalSmallText
            self.arabicVocalization = arabicVocalization
            self.arabicLatinMixed = arabicLatinMixed
            self.arabicFarsiUrduNumbers = arabicFarsiUrduNumbers
            self.accentedDict = accentedDict
            self.get_accented_words = get_accented_words
            self.get_accented_characters = get_accented_characters
            self.text_generator = text_generator
            self.TextGenerator = TextGenerator

    pte = ProofTexts()
except ImportError:
    print("Warning: prooftexts module not found. Using fallback text.")
    pte = None
    bigRandomNumbers = ""
    additionalSmallText = ""

# Module-level page counter to control displayed page numbers independent of DrawBot internals
_PROOF_PAGE_INDEX = 0


def reset_proof_page_counter() -> None:
    """Reset the proof page counter. Call this when starting a new PDF generation."""
    global _PROOF_PAGE_INDEX
    _PROOF_PAGE_INDEX = 0


# =============================================================================
# Internal Helpers
# =============================================================================


def _normalize_axes(
    axesProduct: Any, indFont: str
) -> Iterator[tuple[str, Optional[dict]]]:
    """Yield (suffix, axisDictOrNone) for variable and static fonts uniformly.

    suffix is used only for section title decoration.
    axisDictOrNone is passed to stringMaker's fontVariations when present.
    """
    if axesProduct:
        for axisData in axesProduct:
            try:
                axis_dict = dict(axisData)
            except Exception:
                axis_dict = None
            yield str(axisData), axis_dict
    else:
        # Static font case in this app is represented by empty string ""
        yield get_font_display_name(indFont), None


def _calc_auto_size_for_page(
    text: str,
    font_path: str,
    tracking: float = 0,
    align: str = "center",
    ot_features: Optional[dict] = None,
    axis_dict: Optional[dict] = None,
    min_size: float = 4,
    max_size: float = 200,
) -> float:
    """Binary-search for the largest font size that fits *text* in one page.

    Uses ``db.textSize(fs, width=contentWidth)`` to measure the height
    required at each candidate size, comparing against the available
    content height of the current page format.
    """
    content_w = config.pageDimensions[0] - config.marginHorizontal * 2
    content_h = config.pageDimensions[1] - config.marginVertical * 2

    def _fits(size):
        kwargs = dict(
            txt=text,
            font=font_path,
            fallbackFont=myFallbackFont,
            fontSize=size,
            align=align,
            tracking=size / 1.5 if tracking == 0 else tracking,
            openTypeFeatures=ot_features,
        )
        if axis_dict:
            kwargs["fontVariations"] = axis_dict
        fs = db.FormattedString(**kwargs)
        _, h = db.textSize(fs, width=content_w)
        return h <= content_h

    lo, hi = min_size, max_size
    for _ in range(30):
        mid = (lo + hi) / 2
        if _fits(mid):
            lo = mid
        else:
            hi = mid
        if hi - lo < 0.5:
            break
    return int(lo)


def _calc_auto_size_for_line(
    text: str,
    font_path: str,
    tracking: float = 0,
    ot_features: Optional[dict] = None,
    axis_dict: Optional[dict] = None,
    min_size: float = 4,
    max_size: float = 200,
) -> float:
    """Binary-search for the largest font size where *text* fits in one line.

    Uses ``db.textSize(fs)`` (without width constraint) and checks the
    resulting width against the page content width.
    """
    content_w = config.pageDimensions[0] - config.marginHorizontal * 2

    def _fits(size):
        kwargs = dict(
            txt=text,
            font=font_path,
            fallbackFont=myFallbackFont,
            fontSize=size,
            tracking=tracking,
            openTypeFeatures=ot_features,
        )
        if axis_dict:
            kwargs["fontVariations"] = axis_dict
        fs = db.FormattedString(**kwargs)
        w, _ = db.textSize(fs)
        return w <= content_w

    lo, hi = min_size, max_size
    for _ in range(30):
        mid = (lo + hi) / 2
        if _fits(mid):
            lo = mid
        else:
            hi = mid
        if hi - lo < 0.5:
            break
    return int(lo)


def _render_proof_content(
    textInput: str,
    fontSize: int | float,
    indFont: str,
    axesProduct: Any,
    pairedStaticStyles: Any,
    sectionName: str,
    columns: int,
    alignInput: str = "left",
    trackingInput: int | float = 0,
    otFeatures: Optional[dict] = None,
    mixedStyles: bool = False,
    direction: str = "ltr",
    skip_none_result: bool = False,
    lineHeightInput: Optional[float] = None,
) -> None:
    """Unified helper to render proof content across all axes variations.

    This consolidates the repeated pattern of iterating over axes,
    calling stringMaker, and then drawContent.

    Args:
        textInput: The text content to render
        fontSize: Font size in points
        indFont: Font path/identifier
        axesProduct: Variable font axes product or empty for static
        pairedStaticStyles: Paired styles for mixed style proofs
        sectionName: Base section name (suffix will be appended)
        columns: Number of columns for layout
        alignInput: Text alignment ("left", "center", "right")
        trackingInput: Tracking value
        otFeatures: OpenType features dict
        mixedStyles: Whether to use mixed styles (italic/bold alternation)
        direction: Text direction ("ltr" or "rtl")
        skip_none_result: If True, skip rendering when stringMaker returns None
    """
    for suffix, axisDict in _normalize_axes(axesProduct, indFont):
        formatted_string = stringMaker(
            textInput,
            fontSize,
            indFont,
            axesProduct,
            pairedStaticStyles,
            alignInput,
            trackingInput,
            otFeatures,
            VFAxisInput=axisDict,
            mixedStyles=mixedStyles,
            lineHeightInput=lineHeightInput,
        )

        # Skip if no valid result (e.g., mixed styles with no valid pairing)
        if skip_none_result and formatted_string is None:
            continue

        drawContent(
            formatted_string,
            f"{sectionName} - {suffix}",
            columns,
            indFont,
            direction,
            otFeatures,
            trackingInput,
        )


def get_font_display_name(indFont: str) -> str:
    """Get the display name for a font, extracting the style from the font name."""
    try:
        font_name = db.font(indFont)
        if "-" in font_name:
            return font_name.split("-")[1]
        return font_name
    except (IndexError, AttributeError):
        return "Unknown"


# =============================================================================
# Core Drawing Functions
# =============================================================================


def drawFooter(
    title: str,
    indFont: str,
    otFeatures: Optional[dict] = None,
    tracking: Optional[int | float] = None,
    pageNumber: Optional[int] = None,
) -> None:
    """Draw a simple footer with some minimal but useful info."""
    with db.savedState():
        # get date/time and font name
        now = datetime.datetime.now()
        date_str = now.date()
        time_str = now.strftime("%H:%M")
        fontFileName = os.path.basename(indFont)
        familyName = os.path.splitext(fontFileName)[0].split("-")[0]
        # assemble footer text
        footerText = f"{date_str} {time_str} | {familyName} | {title}"

        # and display formatted string
        footer = db.FormattedString(
            footerText,
            font=FOOTER_FONT_NAME,
            fontSize=FOOTER_FONT_SIZE,
            lineHeight=FOOTER_FONT_SIZE,
        )
        # Use provided pageNumber when available; fallback to DrawBot's pageCount
        current_page_str = (
            str(pageNumber) if pageNumber is not None else str(db.pageCount())
        )
        folio = db.FormattedString(
            current_page_str,
            font=FOOTER_FONT_NAME,
            fontSize=FOOTER_FONT_SIZE,
            lineHeight=FOOTER_FONT_SIZE,
            align="right",
        )

        # Calculate feature info text if OpenType features are provided
        features_text = ""
        if otFeatures:
            features_enabled = []
            features_disabled = []

            for feature, enabled in otFeatures.items():
                if enabled and feature not in DEFAULT_ON_FEATURES:
                    # Feature is ON but usually OFF by default
                    features_enabled.append(feature)
                elif not enabled and feature in DEFAULT_ON_FEATURES:
                    # Feature is OFF but usually ON by default
                    features_disabled.append(feature)

            # Build features text
            features_parts = []
            if features_enabled:
                features_parts.append(f"ON: {', '.join(sorted(features_enabled))}")
            if features_disabled:
                features_parts.append(f"OFF: {', '.join(sorted(features_disabled))}")

            if features_parts:
                features_text = " - ".join(features_parts)

        # Add tracking information if it's not 0
        if tracking is not None and tracking != 0:
            tracking_text = f"Tracking: {tracking}"
            if features_text:
                features_text += f" | {tracking_text}"
            else:
                features_text = tracking_text

        # Main footer line
        db.textBox(
            footer,
            (
                marginHorizontal,
                marginVertical - 18,
                db.width() - marginHorizontal * 2,
                FOOTER_FONT_SIZE,
            ),
        )
        db.textBox(
            folio,
            (
                marginHorizontal,
                marginVertical - 18,
                db.width() - marginHorizontal * 2,
                FOOTER_FONT_SIZE,
            ),
        )

        # Features line (if any features to display)
        if features_text:
            features_footer = db.FormattedString(
                f"OT Fea: {features_text}",
                font=FOOTER_FONT_NAME,
                fontSize=FOOTER_FEATURES_FONT_SIZE,
                lineHeight=FOOTER_FEATURES_FONT_SIZE,
            )
            db.textBox(
                features_footer,
                (
                    marginHorizontal,
                    marginVertical - 28,  # 10 points below main footer
                    db.width() - marginHorizontal * 2,
                    FOOTER_FEATURES_FONT_SIZE,
                ),
            )


def stringMaker(
    textInput,
    fontSizeInput,
    indFont,
    axesProduct,
    pairedStaticStyles,
    alignInput="left",
    trackingInput=0,
    OTFeaInput=None,
    VFAxisInput=None,
    mixedStyles=False,
    lineHeightInput=None,
):
    """Function to create a formatted string to feed into textBox."""
    try:
        kwargs = dict(
            txt="",
            font=indFont,
            fallbackFont=myFallbackFont,
            fontSize=fontSizeInput,
            align=alignInput,
            tracking=trackingInput,
            openTypeFeatures=OTFeaInput,
            fontVariations=VFAxisInput,
        )
        if lineHeightInput:
            kwargs["lineHeight"] = lineHeightInput
        textString = db.FormattedString(**kwargs)

        # Handle mixed styles if requested
        if mixedStyles:
            return _handle_mixed_styles(
                textString,
                textInput,
                indFont,
                axesProduct,
                pairedStaticStyles,
                VFAxisInput,
                mixedStyles,
            )
        else:
            textString.append(txt=textInput)
            return textString

    except Exception as e:
        print(f"Error in stringMaker: {e}")
        traceback.print_exc()
        raise


def _handle_mixed_styles(
    textString,
    textInput,
    indFont,
    axesProduct,
    pairedStaticStyles,
    VFAxisInput,
    mixedStyles,
):
    """Handle mixed upright/italic and regular/bold styles."""
    if not mixedStyles:
        textString.append(txt=textInput)
        return textString

    random.seed(a=dualStyleSeed)
    f = get_ttfont(indFont)
    # Basic font properties used for pairing decisions
    try:
        weight = f["OS/2"].usWeightClass
    except Exception:
        weight = None
    try:
        isItalic = bool(f["OS/2"].fsSelection & FsSelection.ITALIC)
    except Exception:
        isItalic = False
    try:
        subfamilyName = f["name"].getBestSubFamilyName()
    except Exception:
        subfamilyName = ""

    # 1) Static Regular/Bold pairing: generate once using Regular as the base
    if (
        pairedStaticStyles[1]
        and subfamilyName == "Regular"
        and subfamilyName in pairedStaticStyles[1]
    ):
        try:
            rgFont, bdFont = pairedStaticStyles[1][subfamilyName]
            _apply_alternating_fonts(textString, textInput, [rgFont, bdFont])
            return textString
        except Exception:
            # If RB mapping not available, fall through
            pass

    # 2) Static upright/italic pairing.
    # Non-Regular weights: generate on the upright only to avoid duplicates.
    # Regular weight (OS/2 usWeightClass == 400): generate UI on the Italic run so Regular can produce RB above.
    if pairedStaticStyles[0] and weight is not None and weight in pairedStaticStyles[0]:
        try:
            upFont, itFont = pairedStaticStyles[0][weight]
            if weight == 400:
                # For Regular weight, only generate UI when current font is the Italic instance
                if isItalic:
                    _apply_alternating_fonts(textString, textInput, [upFont, itFont])
                    return textString
            else:
                # For non-Regular weights, generate UI once from the upright
                if not isItalic:
                    _apply_alternating_fonts(textString, textInput, [upFont, itFont])
                    return textString
        except Exception:
            # Fall through to other strategies if mapping not available
            pass

    # Variable font italic axis mixing
    if (
        axesProduct
        and VFAxisInput
        and "ital" in VFAxisInput
        and VFAxisInput["ital"] != 0
    ):
        _apply_alternating_variations(
            textString, textInput, VFAxisInput, "ital", [0.0, 1.0]
        )
        return textString

    # Static font regular/bold mixing
    # Note: We intentionally avoid generating RB for Italic to keep RB single-sourced from Regular

    # Variable font weight axis mixing
    if (
        axesProduct
        and VFAxisInput
        and "wght" in VFAxisInput
        and VFAxisInput["wght"] == 700
    ):
        _apply_alternating_variations(
            textString, textInput, VFAxisInput, "wght", [400.0, 700.0]
        )
        return textString

    # No valid pairing found - return None to indicate this font should be skipped
    return None


def _apply_alternating_fonts(textString, textInput, fonts):
    """Apply alternating fonts to words."""
    for i, word in enumerate(textInput.split()):
        if i % random.randrange(1, 5) == 0:
            textString.append(txt="", font=fonts[i % 2])
        textString.append(txt=word + " ")


def _apply_alternating_variations(textString, textInput, VFAxisInput, axis, values):
    """Apply alternating font variations to words."""
    for i, word in enumerate(textInput.split()):
        if i % random.randrange(1, 5) == 0:
            VFAxisInput[axis] = values[i % 2]
            textString.append(txt="", fontVariations=VFAxisInput)
        textString.append(txt=word + " ")


def drawContent(
    textToDraw: db.FormattedString,
    pageTitle: str,
    columnNumber: int,
    currentFont: str,
    direction: str = "ltr",
    otFeatures: Optional[dict] = None,
    tracking: Optional[int | float] = None,
    baseFontSize: Optional[float] = None,
) -> None:
    """Function to draw content with proper layout.

    When *baseFontSize* is given (markup mode), uses ``columnTextBox``
    without baseline-grid snapping so that mixed font sizes flow
    naturally.  Otherwise uses ``columnBaselineGridTextBox`` for the
    standard uniform-size proofs.
    """
    try:
        showBaselines = (
            getattr(db, "showBaselines", True) if hasattr(db, "showBaselines") else True
        )

        global _PROOF_PAGE_INDEX

        while textToDraw:
            db.newPage(*config.pageDimensions)
            _PROOF_PAGE_INDEX += 1
            drawFooter(
                pageTitle,
                currentFont,
                otFeatures,
                tracking,
                pageNumber=_PROOF_PAGE_INDEX,
            )
            db.hyphenation(False)

            if baseFontSize and columnTextBox:
                # Markup mode: skip baseline grid snapping, just flow
                # text through columns so mixed sizes render naturally.
                textToDraw = columnTextBox(
                    textToDraw,
                    (
                        marginHorizontal,
                        marginVertical,
                        db.width() - marginHorizontal * 2,
                        db.height() - marginVertical * 2,
                    ),
                    subdivisions=columnNumber,
                    gutter=20,
                    draw_grid=showBaselines,
                    direction=direction,
                )
            elif BaselineGrid and columnBaselineGridTextBox:
                baselines = BaselineGrid.from_margins(
                    (0, -marginVertical, 0, -marginVertical),
                    textToDraw.fontLineHeight() / 2,
                )

                if showBaselines:
                    baselines.draw(show_index=True)

                textToDraw = columnBaselineGridTextBox(
                    textToDraw,
                    (
                        marginHorizontal,
                        marginVertical,
                        db.width() - marginHorizontal * 2,
                        db.height() - marginVertical * 2,
                    ),
                    baselines,
                    subdivisions=columnNumber,
                    gutter=20,
                    draw_grid=showBaselines,
                    direction=direction,
                )
            else:
                textToDraw = db.textBox(
                    textToDraw,
                    (
                        marginHorizontal,
                        marginVertical,
                        db.width() - marginHorizontal * 2,
                        db.height() - marginVertical * 2,
                    ),
                )

    except Exception as e:
        print(f"Error in drawContent: {e}")
        traceback.print_exc()
        raise


def drawPageSegments(
    page_segments,
    pageTitle: str,
    columnNumber: int,
    currentFont: str,
    direction: str = "ltr",
    otFeatures: Optional[dict] = None,
    tracking: Optional[int | float] = None,
    baseFontSize: Optional[float] = None,
) -> None:
    """Draw markup output: List[List[FormattedString]] (pages → column segments).

    When a page has a single segment (no column breaks), uses the normal
    ``drawContent`` flow with automatic column reflow.  When a page has
    multiple segments, each segment is placed in its own column.

    ``baseFontSize`` is used for baseline grid computation so the grid
    is always based on body-text metrics, not heading metrics.
    """
    gutter = 20
    for page in page_segments:
        if len(page) == 1:
            drawContent(
                page[0],
                pageTitle,
                columnNumber,
                currentFont,
                direction,
                otFeatures,
                tracking,
                baseFontSize=baseFontSize,
            )
        else:
            _draw_column_segments(
                page,
                pageTitle,
                columnNumber,
                currentFont,
                direction,
                otFeatures,
                tracking,
                gutter,
                baseFontSize=baseFontSize,
            )


def _draw_column_segments(
    segments,
    pageTitle: str,
    columnNumber: int,
    currentFont: str,
    direction: str,
    otFeatures: Optional[dict],
    tracking: Optional[int | float],
    gutter: int = 20,
    baseFontSize: Optional[float] = None,
) -> None:
    """Render each FormattedString segment into its own column."""
    global _PROOF_PAGE_INDEX

    box_x = marginHorizontal
    box_y = marginVertical
    box_w = db.width() - marginHorizontal * 2
    box_h = db.height() - marginVertical * 2
    col_count = max(columnNumber, len(segments))
    col_w = (box_w - (col_count - 1) * gutter) / col_count

    showBaselines = (
        getattr(db, "showBaselines", True) if hasattr(db, "showBaselines") else True
    )

    for batch_start in range(0, len(segments), col_count):
        batch = segments[batch_start : batch_start + col_count]
        db.newPage(*config.pageDimensions)
        _PROOF_PAGE_INDEX += 1
        drawFooter(
            pageTitle, currentFont, otFeatures, tracking, pageNumber=_PROOF_PAGE_INDEX
        )
        db.hyphenation(False)

        # Draw column grid lines
        if showBaselines:
            grid_color = (0.5, 0, 0.8, 1)
            with db.savedState():
                db.strokeWidth(0.5)
                db.fill(None)
                db.stroke(*grid_color)
                db.rect(box_x, box_y, box_w, box_h)
                for ci in range(col_count):
                    if direction == "rtl":
                        cl = box_x + box_w - (ci + 1) * col_w - ci * gutter
                    else:
                        cl = box_x + ci * (col_w + gutter)
                    db.line((cl, box_y), (cl, box_y + box_h))
                    db.line((cl + col_w, box_y), (cl + col_w, box_y + box_h))

        for i, segment in enumerate(batch):
            if direction == "rtl":
                col_x = box_x + box_w - (i + 1) * col_w - i * gutter
            else:
                col_x = box_x + i * (col_w + gutter)
            sub_box = (col_x, box_y, col_w, box_h)
            db.textBox(segment, sub_box)


# =============================================================================
# Text Generation Functions
# =============================================================================


def generateTextProofString(
    characterSet,
    para=2,
    casing=False,
    bigProof=True,
    forceWordsiv=False,
    cat=None,
    fullCharacterSet=None,
    lang=None,
    hoeflerStyle=False,
):
    """Generate long text proofing strings either through wordsiv or premade strings."""
    if cat is None:
        return ""

    # Handle Arabic/Farsi languages with specific logic
    if lang in ["ar", "fa"]:
        if hoeflerStyle:
            return _generate_hoefler_style_arabic_text(
                characterSet, para, lang, cat, fullCharacterSet
            )
        return _generate_arabic_farsi_text(
            characterSet, para, bigProof, lang, cat, fullCharacterSet
        )

    textProofString = ""
    upper_set = set(cat["uniLu"])
    lower_set = set(cat["uniLl"])

    # Use pre-made texts if available and conditions are met
    if (
        pte
        and cat["uppercaseOnly"]
        and all(x in upper_set for x in upperTemplate)
        and forceWordsiv is False
    ):
        textProofString = pte.smallUpperText
    elif (
        pte
        and cat["lowercaseOnly"]
        and all(x in lower_set for x in lowerTemplate)
        and forceWordsiv is False
    ):
        textProofString = pte.smallLowerText
    elif (
        pte
        and all(x in upper_set for x in upperTemplate)
        and all(x in lower_set for x in lowerTemplate)
        and forceWordsiv is False
    ):
        textProofString = pte.smallMixedText + " " + pte.smallUpperText
    elif (
        cat["uppercaseOnly"] is False
        and cat["lowercaseOnly"] is False
        or forceWordsiv is True
    ):
        # Use WordSiv for dynamic text generation
        if hoeflerStyle:
            textProofString = _generate_hoefler_style_text(
                cat, para, fullCharacterSet, characterSet
            )
        else:
            textProofString = _generate_wordsiv_text(
                cat, para, fullCharacterSet, characterSet
            )
    elif cat["uppercaseOnly"]:
        textProofString = _generate_uppercase_text(
            cat, para, fullCharacterSet, characterSet
        )
    elif cat["lowercaseOnly"]:
        textProofString = _generate_lowercase_text(
            cat, para, fullCharacterSet, characterSet
        )

    return textProofString


def _generate_wordsiv_text(cat, para, fullCharacterSet, characterSet):
    """Generate text using WordSiv for mixed case scenarios."""
    caplc = []
    for u in cat["uniLuBase"]:
        capAndLower = u + cat["uniLlBase"]
        wsv = WordSiv(vocab="en", seed=wordsivSeed)
        capitalisedList = wsv.words(
            glyphs=capAndLower,
            case="cap",
            n_words=2,
            min_wl=5,
            max_wl=14,
        )
        if capitalisedList:
            capitalisedString = " ".join(str(elem) for elem in capitalisedList)
            caplc.append(capitalisedString + " ")
        lcList = wsv.words(
            glyphs=capAndLower,
            case="lc_force",
            contains=u.lower(),
            n_words=4,
            min_wl=5,
            max_wl=14,
        )
        if lcList:
            lcString = " ".join(str(elem) for elem in lcList)
            caplc.append(lcString + " ")

    caplc_str = "".join(caplc)
    wsvtext = wsv.text(
        glyphs=cat["uniLu"]
        + cat["uniLl"]
        + cat["uniNd"]
        + cat["uniPo"]
        + cat["uniPc"]
        + cat["uniPd"]
        + cat["uniPi"]
        + cat["uniPf"]
        + "()",
        numbers=0.1,
        rnd_punc=0.1,
        n_paras=para,
        para_sep=" ",
    )
    return caplc_str + "\n\n" + wsvtext + "\n\n" + wsvtext.upper()


# Letter shape categories for Hoefler-style proofs
_ROUND_L_LC = "cdeoq"
_ROUND_R_LC = "bop"
_FLAT_L_LC = "bhiklmnpru"
_FLAT_R_LC = "dhimnqu"
_FLAT_L_UC = "BDEFHIKLMNPR"
_FLAT_R_UC = "HIMN"
_ROUND_L_UC = "CGOQ"
_ROUND_R_UC = "DO"

# Path to the custom English Wikipedia word list for Hoefler-style proofs
_ENG_WIKI_PATH = os.path.join(_cc.SCRIPT_DIR, "eng_wiki.tsv")


def _unique_random_word(wsv, recent, glyphs, max_attempts=10, **kwargs):
    """Pick a random filler word that doesn't duplicate any of the *recent* words.

    Tries up to *max_attempts* draws; if every attempt collides it returns the
    last candidate anyway (better a repeat than a gap).
    """
    candidate = None
    for _ in range(max_attempts):
        candidate = wsv.word(glyphs=glyphs, top_k=40, **kwargs)
        if candidate and candidate not in recent:
            break
    return candidate


def _generate_hoefler_style_text(cat, para, fullCharacterSet, characterSet):
    """Generate Hoefler-style proof text where each letter gets contextual words.

    Produces mixed-case and uppercase paragraphs following the pattern from
    https://www.wordsiv.com/examples/hoefler-style-proof/
    Each letter is tested in flat-to-flat, round-to-round, and mixed contexts.
    """
    glyphs = fullCharacterSet if fullCharacterSet else characterSet
    if not glyphs:
        return ""

    uc_glyphs = "".join(
        sorted(c for c in cat.get("uniLuBase", cat.get("uniLu", "")) if c in glyphs)
    )
    if not uc_glyphs:
        return ""

    wsv = WordSiv(glyphs=glyphs, seed=wordsivSeed)
    wsv.add_vocab(
        "eng-wiki",
        Vocab(lang="en", data_file=_ENG_WIKI_PATH, bicameral=True),
    )

    # --- Mixed-case paragraph (Hoefler lc style) ---
    common_cap = {"min_wl": 5, "case": "cap", "glyphs": glyphs, "vocab": "eng-wiki"}
    common_lc = {"min_wl": 5, "case": "lc", "glyphs": glyphs, "vocab": "eng-wiki"}

    # Opening line: two capitalized words per uppercase letter
    cap_words = []
    for g in uc_glyphs:
        try:
            cap_words.append(
                wsv.top_word(idx=0, regexp=rf"{g}[{_ROUND_L_LC}].*", **common_cap)
            )
        except Exception:
            pass
        try:
            cap_words.append(
                wsv.top_word(idx=0, regexp=rf"{g}[{_FLAT_L_LC}].*", **common_cap)
            )
        except Exception:
            pass

    lc_proof = " ".join(c for c in cap_words if c) + "."

    # Per-letter sentences in mixed case
    # Keep a sliding window of recent words to avoid nearby repetition
    _RECENT_WINDOW = 4
    recent_lc = []
    for g_uc in uc_glyphs:
        g_lc = g_uc.lower()
        words = []
        patterns = [
            ("cap", rf"{g_uc}[{_FLAT_L_LC}].*"),
            ("lc", rf"{g_lc}[{_FLAT_L_LC}].*"),
            ("lc", rf"{g_lc}[{_ROUND_L_LC}].*"),
            None,  # random word
            None,  # random word
            ("lc", rf".+[{_FLAT_R_LC}]{g_lc}[{_FLAT_L_LC}].+"),
            ("lc", rf".+[{_ROUND_R_LC}]{g_lc}[{_ROUND_L_LC}].+"),
            None,  # random word
            None,  # random word
            ("lc", rf".+[{_FLAT_R_LC}]{g_lc}"),
            ("lc", rf".+[{_ROUND_R_LC}]{g_lc}"),
            None,  # random word
            ("lc", rf".+[{_FLAT_R_LC}]{g_lc}{g_lc}[{_FLAT_L_LC}].+"),
        ]
        for pat in patterns:
            try:
                if pat is None:
                    w = _unique_random_word(wsv, recent_lc, glyphs, vocab="eng-wiki")
                    words.append(w)
                    if w:
                        recent_lc.append(w)
                        if len(recent_lc) > _RECENT_WINDOW:
                            recent_lc.pop(0)
                else:
                    case_val, regexp = pat
                    kw = common_cap if case_val == "cap" else common_lc
                    words.append(wsv.top_word(regexp=regexp, **kw))
            except Exception:
                pass
        sent = " ".join(w for w in words if w) + "."
        lc_proof += " " + sent

    # --- Uppercase paragraph (Hoefler uc style) ---
    common_uc = {"min_wl": 5, "case": "uc", "glyphs": glyphs, "vocab": "eng-wiki"}
    uc_sents = []
    recent_uc = []
    for g in uc_glyphs:
        words = []
        uc_patterns = [
            rf"{g}[{_FLAT_L_UC}].*",
            rf"{g}[{_ROUND_L_UC}].*",
            None,
            None,
            rf".+[{_FLAT_R_UC}]{g}[{_FLAT_L_UC}].+",
            rf".+[{_ROUND_R_UC}]{g}[{_ROUND_L_UC}].+",
            None,
            None,
            rf".+[{_FLAT_R_UC}]{g}",
            rf".+[{_ROUND_R_UC}]{g}",
            None,
            None,
            rf".+[{_FLAT_R_UC}]{g}{g}[{_FLAT_L_UC}].+",
        ]
        for pat in uc_patterns:
            try:
                if pat is None:
                    w = _unique_random_word(
                        wsv, recent_uc, glyphs, case="uc", vocab="eng-wiki"
                    )
                    words.append(w)
                    if w:
                        recent_uc.append(w)
                        if len(recent_uc) > _RECENT_WINDOW:
                            recent_uc.pop(0)
                else:
                    words.append(wsv.top_word(regexp=pat, **common_uc))
            except Exception:
                pass
        uc_sents.append(" ".join(w for w in words if w) + ".")

    uc_proof = " ".join(uc_sents)

    return lc_proof + "\n\n" + uc_proof


def _generate_uppercase_text(cat, para, fullCharacterSet, characterSet):
    """Generate text for uppercase-only fonts."""
    upperInitials = []
    upperInitialsHelper = (fullCharacterSet or characterSet or "").lower()

    for u in cat["uniLu"]:
        individualUpper = u + upperInitialsHelper
        upperwsv = WordSiv(glyphs=individualUpper, seed=wordsivSeed)
        upperList = upperwsv.words(
            vocab="en", case="cap", n_words=4, min_wl=5, max_wl=14
        )
        if upperList:
            upperInitialsString = " ".join(str(elem) for elem in upperList)
            upperInitials.append(upperInitialsString.upper() + " ")

    upperInitials_str = "".join(upperInitials)
    wsv = WordSiv(glyphs=fullCharacterSet if fullCharacterSet else characterSet)
    wsvtext = wsv.paras(
        vocab="en",
        n_paras=para,
        min_wl=1,
        max_wl=14,
        case="uc",
    )
    return upperInitials_str + "- " + " ".join(str(elem) for elem in wsvtext)


def _generate_lowercase_text(cat, para, fullCharacterSet, characterSet):
    """Generate text for lowercase-only fonts."""
    lowerInitials = []
    lowerHelper = fullCharacterSet or characterSet or ""

    for lower in cat["uniLl"]:
        individualLower = lower.upper() + lowerHelper
        lowerwsv = WordSiv(glyphs=individualLower, seed=wordsivSeed)
        lowerList = lowerwsv.words(
            vocab="en", case="cap", n_words=4, min_wl=5, max_wl=14
        )
        lowerInitialsString = " ".join(str(elem) for elem in (lowerList or []))
        lowerInitials.append(lowerInitialsString.lower() + " ")

    lowerInitials_str = "".join(lowerInitials)
    wsv = WordSiv(glyphs=fullCharacterSet if fullCharacterSet else characterSet)
    wsvtext = wsv.paras(
        vocab="en",
        n_paras=para,
        min_wl=1,
        max_wl=14,
    )
    return lowerInitials_str + " ".join(str(elem) for elem in wsvtext)


def _generate_arabic_farsi_text(
    characterSet, para, bigProof, lang, cat, fullCharacterSet
):
    """Generate Arabic/Farsi text using WordSiv with contextual forms."""
    textProofString = ""

    # Set vocabulary based on language
    vocab = "ar" if lang == "ar" else "fa"

    try:
        # Use fullCharacterSet as glyphs if available, otherwise fall back to characterSet
        glyphs = fullCharacterSet
        wsv = WordSiv(glyphs=glyphs, vocab=vocab, seed=wordsivSeed)

        # Determine number of words based on proof type
        numberOfWords = 4 if bigProof else 6

        # Generate contextual form proofs for each character
        arabWords = ""
        for g in characterSet:
            arabWords += g + ". "

            # Generate words with different positional forms
            for p in posForms:
                try:
                    # Generate words containing the character in specific position
                    if p == "init":
                        # Use startswith for initial form
                        arabList = wsv.words(
                            n_words=numberOfWords,
                            min_wl=5,
                            max_wl=14,
                            startswith=g,
                        )
                    elif p == "medi":
                        # Use inner for medial form
                        arabList = wsv.words(
                            n_words=numberOfWords,
                            min_wl=5,
                            max_wl=14,
                            inner=g,
                        )
                    elif p == "fina":
                        # Use endswith for final form
                        arabList = wsv.words(
                            n_words=numberOfWords,
                            min_wl=5,
                            max_wl=14,
                            endswith=g,
                        )
                    else:
                        # Fallback to contains if position not recognized
                        arabList = wsv.words(
                            n_words=numberOfWords,
                            min_wl=5,
                            max_wl=14,
                            contains=g,
                        )

                    if arabList:
                        arabString = " ".join([str(elem) for elem in arabList])
                        arabWords += arabString + " "
                except Exception as e:
                    # Fallback to simple word generation if positional forms fail
                    try:
                        arabList = wsv.words(
                            n_words=numberOfWords,
                            min_wl=5,
                            max_wl=14,
                            contains=g,
                        )
                        if arabList:
                            arabString = " ".join([str(elem) for elem in arabList])
                            arabWords += arabString + " "
                    except:
                        pass
            arabWords += "\n"

        textProofString = arabWords

    except Exception as e:
        print(f"Error generating {lang} text: {e}")
        # Fallback to character display
        textProofString = " ".join(characterSet)

    return textProofString


def _generate_hoefler_style_arabic_text(characterSet, para, lang, cat, fullCharacterSet):
    """Generate a single flowing Arabic paragraph via cartesian product of shape groups.

    Builds regex character classes from ARABIC_SHAPE_GROUPS (all members of each
    group, not just one representative), then generates words for every combination
    of positionally-compatible group pairs:
      - init × medi  (initial-form exit meeting medial-form entry)
      - medi × medi  (adjacent medial forms)
      - medi × fina  (medial-form exit meeting final-form entry)
      - iso  × init  (isolated non-connector before initial form)
      - fina × iso   (final form before isolated non-connector)
    All words are joined into one continuous paragraph.
    """
    from config import ARABIC_GLYPH_TO_UNICODE, ARABIC_SHAPE_GROUPS

    char_set = set(characterSet)
    vocab = "ar" if lang == "ar" else "fa"

    try:
        wsv = WordSiv(glyphs=fullCharacterSet, vocab=vocab, seed=wordsivSeed)
    except Exception:
        return " ".join(characterSet)

    # Build regex character class strings grouped by positional suffix
    init_classes = []
    medi_classes = []
    fina_classes = []
    iso_classes = []

    for base, suffix, glyph_names in ARABIC_SHAPE_GROUPS:
        chars = ""
        for glyph in glyph_names:
            uc = ARABIC_GLYPH_TO_UNICODE.get(glyph)
            if uc and uc in char_set:
                chars += uc
        if not chars:
            continue

        if suffix == "init":
            init_classes.append(chars)
        elif suffix == "medi":
            medi_classes.append(chars)
        elif suffix == "fina":
            fina_classes.append(chars)
        elif suffix == "":
            iso_classes.append(chars)

    all_words = []
    seen = set()

    def try_word(regexp, min_wl=3):
        try:
            w = str(wsv.top_word(regexp=regexp, min_wl=min_wl))
            if w and w not in seen:
                all_words.append(w)
                seen.add(w)
        except Exception:
            pass

    # init × medi: char from init group starts word, followed by char from medi group
    for ic in init_classes:
        for mc in medi_classes:
            try_word(rf"[{ic}][{mc}].*")

    # medi × medi: adjacent medial-form chars in the middle of a word
    for m1 in medi_classes:
        for m2 in medi_classes:
            try_word(rf".+[{m1}][{m2}].+", min_wl=4)

    # medi × fina: medial-form char followed by final-form char at word end
    for mc in medi_classes:
        for fc in fina_classes:
            try_word(rf".*[{mc}][{fc}]")

    # iso × init: isolated non-connector at word start, followed by initial form
    for oc in iso_classes:
        for ic in init_classes:
            try_word(rf"[{oc}][{ic}].*")

    # fina × iso: final form followed by isolated non-connector at word end
    for fc in fina_classes:
        for oc in iso_classes:
            try_word(rf".*[{fc}][{oc}]")

    return " ".join(all_words) if all_words else " ".join(characterSet)


def generateSpacingString(characterSet):
    """Create the spacing proof string efficiently using list accumulation."""
    lines = []
    append = lines.append
    for char in characterSet:
        if useFontContainsCharacters and not db.fontContainsCharacters(char):
            continue
        if char in ("\n", " "):
            continue

        cat = unicodedata.category(char)
        if cat == "Ll":
            control1, control2 = "n", "o"
        elif cat == "Nd":
            control1, control2 = "0", "1"
        else:
            control1, control2 = "H", "O"

        append(
            f"{control1}{control1}{control1}{char}{control1}{control2}{control1}{char}{control2}{char}{control2}{control2}{control2}"
        )
    return "\n".join(lines) + ("\n" if lines else "")


# =============================================================================
# Proof Generation Functions
# =============================================================================


def charsetProof(
    characterSet: str,
    axesProduct: list,
    indFont: str,
    pairedStaticStyles: tuple,
    otFea: Optional[dict] = None,
    fontSize: Optional[int | float] = None,
    sectionName: str = "Character Overview",
    tracking: Optional[int | float] = None,
) -> None:
    """Generate Filtered Character Set."""
    if not characterSet:
        print("Empty character set, skipping")
        return

    # Use provided font size or fall back to proof type default
    proof_font_size = (
        fontSize
        if fontSize is not None
        else get_proof_default_font_size("filtered_character_set")
    )

    # Use provided tracking or fall back to default
    tracking_value = tracking if tracking is not None else DEFAULT_CHARSET_TRACKING

    try:
        _render_proof_content(
            characterSet,
            proof_font_size,
            indFont,
            axesProduct,
            pairedStaticStyles,
            sectionName,
            columns=1,
            alignInput="center",
            trackingInput=tracking_value,
            otFeatures=otFea,
            mixedStyles=False,
            direction="ltr",
        )
    except Exception as e:
        print(f"Error in charsetProof: {e}")
        traceback.print_exc()


def spacingProof(
    characterSet: str,
    axesProduct: list,
    indFont: str,
    pairedStaticStyles: tuple,
    otFea: Optional[dict] = None,
    fontSize: Optional[int | float] = None,
    columns: Optional[int] = None,
    sectionName: str = "Spacing proof",
    tracking: Optional[int | float] = None,
) -> None:
    """Generate spacing proof."""
    # Use provided font size or fall back to proof type default
    proof_font_size = (
        fontSize
        if fontSize is not None
        else get_proof_default_font_size("spacing_proof")
    )

    # Use provided columns or fall back to default spacing proof columns (2)
    proof_columns = columns if columns is not None else 2

    # Precompute spacing input and used features
    spacingStringInput = generateSpacingString(characterSet)
    used_features = dict(liga=False, kern=False) if otFea is None else otFea

    _render_proof_content(
        spacingStringInput,
        proof_font_size,
        indFont,
        axesProduct,
        pairedStaticStyles,
        sectionName,
        columns=proof_columns,
        alignInput="left",
        trackingInput=tracking if tracking is not None else 0,
        otFeatures=used_features,
        mixedStyles=False,
        direction="ltr",
    )


def textProof(
    characterSet: str,
    axesProduct: list,
    indFont: str,
    pairedStaticStyles: tuple,
    cols: int = 2,
    para: int = 3,
    casing: bool = False,
    textSize: Optional[int | float] = None,
    sectionName: str = "Text Proof",
    mixedStyles: bool = False,
    forceWordsiv: bool = False,
    injectText: Optional[str] = None,
    otFea: Optional[dict] = None,
    accents: int = 0,
    cat: Optional[dict] = None,
    fullCharacterSet: Optional[str] = None,
    lang: Optional[str] = None,
    tracking: int | float = 0,
    align: str = "left",
    hoeflerStyle: bool = False,
    lineHeight: Optional[float] = None,
) -> None:
    """Generate text proof with various options."""
    # Set default textSize if None
    if textSize is None:
        textSize = get_proof_default_font_size("text_proof")

    textStringInput = ""

    if accents and pte:
        # Generate accented text samples
        for a in characterSet:
            accentList = []
            if a.lower() in pte.accentedDict:
                available = []
                for s in pte.accentedDict[a.lower()]:
                    if all(x in fullCharacterSet.lower() for x in s):
                        available.append(s)
                if len(available) < accents:
                    count = len(available)
                else:
                    count = accents
                textStringInput += " |" + a + "| "
                accentList = random.sample(available, k=count)
                for w in accentList:
                    if a.isupper():
                        textStringInput += w.replace("ß", "ẞ").upper() + " "
                    else:
                        textStringInput += w + " "
                if textSize == get_proof_default_font_size("small_text_proof"):
                    textStringInput += "\n"
    elif not injectText:
        # Determine if this is a big or small proof based on font size
        bigProof = textSize == get_proof_default_font_size("large_text_proof")
        textStringInput = generateTextProofString(
            characterSet,
            para,
            casing,
            bigProof=bigProof,
            forceWordsiv=forceWordsiv,
            cat=cat,
            fullCharacterSet=fullCharacterSet,
            lang=lang,
            hoeflerStyle=hoeflerStyle,
        )
    elif injectText:
        # Accept either an iterable of strings (list/tuple) or a single string.
        # Previously, iterating over a single injected string produced one-character-per-line output.
        if isinstance(injectText, (list, tuple)):
            for t in injectText:
                if not t:
                    continue
                textStringInput += t.rstrip() + "\n"
        else:
            # Single block of text
            textStringInput += str(injectText).rstrip() + "\n"

    # Use rtl direction for Arabic/Farsi text
    text_direction = "rtl" if lang in ["ar", "fa"] else "ltr"

    _render_proof_content(
        textStringInput,
        textSize,
        indFont,
        axesProduct,
        pairedStaticStyles,
        sectionName,
        columns=cols,
        alignInput=align,
        trackingInput=tracking,
        otFeatures=otFea,
        mixedStyles=mixedStyles,
        direction=text_direction,
        skip_none_result=mixedStyles,  # Skip None results only for mixed styles
        lineHeightInput=lineHeight,
    )


def generateArabicContextualFormsProof(cat):
    """Generate ARA Character Set proof showing each character in all its forms."""
    contextualProof = ""

    # Get Arabic characters
    arabic_chars = cat.get("arabTyped", "")
    if not arabic_chars:
        return ""

    for char in arabic_chars:
        if char == "ء":  # Hamza special case
            contextualProof += char + " "
        elif char in cat.get("arfaDualJoin", ""):
            # Show character: isolated, then connected forms
            contextualProof += char + " " + char + char + char + " "
        elif char in cat.get("arfaRightJoin", ""):
            # Show character with connecting letter
            contextualProof += char + " " + "ب" + char + " "

    return contextualProof


def arabicContextualFormsProof(
    cat,
    axesProduct,
    indFont,
    pairedStaticStyles,
    otFea=None,
    fontSize=None,
    sectionName="Ar Character Overview",
    tracking=None,
):
    """Generate ARA Character Set proof pages using configurable font size."""
    # Use provided font size or fall back to character set font size
    proof_font_size = (
        fontSize
        if fontSize is not None
        else get_proof_default_font_size("ar_character_set")
    )

    contextualString = generateArabicContextualFormsProof(cat)

    if not contextualString:
        return

    try:
        _render_proof_content(
            contextualString,
            proof_font_size,
            indFont,
            axesProduct,
            pairedStaticStyles,
            sectionName,
            columns=1,
            alignInput="center",
            trackingInput=0,
            otFeatures=otFea,
            mixedStyles=False,
            direction="rtl",
        )
    except Exception as e:
        print(f"Error in arabicContextualFormsProof: {e}")
        traceback.print_exc()


# =============================================================================
# Proof Handler Classes
# =============================================================================


@dataclass
class ProofContext:
    """Context object containing all data needed for proof generation."""

    full_character_set: str
    axes_product: object
    ind_font: str
    paired_static_styles: object
    otfeatures_by_proof: dict
    cols_by_proof: dict
    paras_by_proof: dict
    cat: dict
    proof_name: str | None
    all_fonts: list | None = None
    font_manager: object | None = None


class BaseProofHandler(ABC):
    """Base class for all proof type handlers."""

    def __init__(self, proof_name, proof_settings, get_proof_font_size_func):
        self.proof_name = proof_name
        self.proof_settings = proof_settings
        self.get_proof_font_size = get_proof_font_size_func
        # Use registry key for base proofs; display-name-derived key for numbered variants
        from config import resolve_base_proof_key

        base_display, settings_key = resolve_base_proof_key(proof_name)
        if settings_key and proof_name == base_display:
            self.unique_proof_key = settings_key
        else:
            self.unique_proof_key = create_unique_proof_key(proof_name)

        # Cache commonly accessed settings for performance
        self._cached_font_size = None
        self._cached_tracking = None
        self._cached_align = None
        self._cached_line_height = None
        self._cached_columns = None
        self._cached_paragraphs = None
        self._cached_otfeatures = None

    def get_font_size(self):
        """Get font size for this proof."""
        if self._cached_font_size is None:
            self._cached_font_size = self.get_proof_font_size(self.proof_name)
        return self._cached_font_size

    def get_tracking_value(self):
        """Get tracking value for this proof."""
        if self._cached_tracking is None:
            self._cached_tracking = self.proof_settings.get(
                make_settings_key(self.unique_proof_key, "tracking"), 0
            )
        return self._cached_tracking

    def get_align_value(self):
        """Get alignment value for this proof."""
        if self._cached_align is None:
            self._cached_align = self.proof_settings.get(
                make_settings_key(self.unique_proof_key, "align"), "left"
            )
        return self._cached_align

    def get_line_height_value(self):
        """Get line height in points for this proof (em ratio * fontSize). None = auto."""
        if self._cached_line_height is None:
            val = self.proof_settings.get(
                make_settings_key(self.unique_proof_key, "lineHeight"), 0
            )
            if val and val > 0:
                # Value is an em ratio; convert to absolute points
                font_size = self.get_font_size()
                self._cached_line_height = val * font_size
            else:
                self._cached_line_height = None
        return self._cached_line_height

    def get_line_height_ratio(self):
        """Get the raw em ratio for line height. None = auto."""
        val = self.proof_settings.get(
            make_settings_key(self.unique_proof_key, "lineHeight"), 0
        )
        if val and val > 0:
            return val
        return None

    def get_columns_value(self, default=None):
        """Get columns value for this proof from settings."""
        if self._cached_columns is None:
            self._cached_columns = self.proof_settings.get(
                make_settings_key(self.unique_proof_key, "cols"), default
            )
        return self._cached_columns

    def get_paragraphs_value(self, default=None):
        """Get paragraphs value for this proof from settings."""
        if self._cached_paragraphs is None:
            self._cached_paragraphs = self.proof_settings.get(
                make_settings_key(self.unique_proof_key, "para"), default
            )
        return self._cached_paragraphs

    def get_otfeatures(self, fallback=None):
        """Get OT features for this proof from settings."""
        if self._cached_otfeatures is None:
            prefix = get_otf_prefix(self.unique_proof_key)
            features = {}
            for key, value in self.proof_settings.items():
                if key.startswith(prefix):
                    tag = key[len(prefix) :]
                    features[tag] = bool(value)
            self._cached_otfeatures = features if features else (fallback or {})
        return self._cached_otfeatures

    def get_auto_size(self):
        """Check if auto-size is enabled for this proof."""
        key = make_settings_key(self.unique_proof_key, "autoSize")
        return bool(self.proof_settings.get(key, False))

    def get_section_name(self, font_size):
        """Get section name for this proof."""
        return f"{self.proof_name} - {font_size}pt"

    def get_common_proof_params(self, context, default_columns=2, default_paragraphs=5):
        """Extract common proof parameters to reduce code duplication."""
        cols = self.get_columns_value(default=default_columns)
        if cols is None:
            cols = default_columns
        paras = self.get_paragraphs_value(default=default_paragraphs)
        if paras is None:
            paras = default_paragraphs
        return {
            "font_size": self.get_font_size(),
            "columns": cols,
            "paragraphs": paras,
            "section_name": self.get_section_name(self.get_font_size()),
            "tracking_value": self.get_tracking_value(),
            "align_value": self.get_align_value(),
            "line_height": self.get_line_height_value(),
            "otfeatures": self.get_otfeatures(),
        }

    @abstractmethod
    def generate_proof(self, context):
        """Generate the proof. Must be implemented by subclasses.

        Args:
            context: ProofContext object containing all necessary data
        """
        pass

    def generate_text_proof(
        self,
        context,
        character_set,
        default_columns=2,
        default_paragraphs=3,
        mixed_styles=False,
        force_wordsiv=False,
        inject_text=None,
        accents=0,
        language=None,
        hoefler_style=False,
    ):
        """Template method for generating text-based proofs."""
        params = self.get_common_proof_params(
            context, default_columns, default_paragraphs
        )

        textProof(
            character_set,
            context.axes_product,
            context.ind_font,
            context.paired_static_styles if mixed_styles else None,
            params["columns"],
            params["paragraphs"],
            False,  # casing
            params["font_size"],
            params["section_name"],
            mixed_styles,
            force_wordsiv,
            inject_text,
            params["otfeatures"],
            accents,
            context.cat,
            context.full_character_set,
            language,
            params["tracking_value"],
            params["align_value"],
            hoeflerStyle=hoefler_style,
            lineHeight=params["line_height"],
        )


class StandardTextProofHandler(BaseProofHandler):
    """Standard handler for text-based proofs with configurable parameters."""

    # Configuration mapping is provided via proof_config.get_text_proof_config

    def __init__(
        self, proof_name, proof_settings, get_proof_font_size_func, proof_key=None
    ):
        super().__init__(proof_name, proof_settings, get_proof_font_size_func)

        # If proof_key is provided, use configuration from registry helper
        if proof_key:
            config = get_text_proof_config(proof_key)
        else:
            config = None

        if config:
            self.character_set_key = config["character_set_key"]
            self.default_columns = config.get("default_columns", 2)
            self.default_paragraphs = config.get("default_paragraphs", 5)
            self.mixed_styles = config.get("mixed_styles", False)
            self.force_wordsiv = config.get("force_wordsiv", False)
            self.hoefler_style = config.get("hoefler_style", False)
            # Some configs refer to centralized text content by key
            inject_key = config.get("inject_text_key")
            if inject_key:
                # First try core_config for named text blocks
                injected = getattr(_cc, inject_key, None)
                if injected is None and inject_key == "misc_small_injects":
                    # Fallback to sample_texts tuple when available
                    if bigRandomNumbers or additionalSmallText:
                        injected = (bigRandomNumbers, additionalSmallText)
                self.inject_text = injected
            else:
                # Keep misc_paragraph_small fallback using sample_texts if available
                if proof_key == "misc_paragraph_small" and (
                    bigRandomNumbers or additionalSmallText
                ):
                    self.inject_text = (bigRandomNumbers, additionalSmallText)
                else:
                    self.inject_text = config.get("inject_text", None)
            self.accents = config.get("accents", 0)
            self.language = config.get("language", None)
        else:
            # Fallback to default values for backward compatibility
            self.character_set_key = "base_letters"
            self.default_columns = 2
            self.default_paragraphs = 5
            self.mixed_styles = False
            self.force_wordsiv = False
            self.hoefler_style = False
            self.inject_text = None
            self.accents = 0
            self.language = None

    def get_character_set(self, context):
        """Get character set based on the key using centralized resolver."""
        return resolve_character_set_by_key(context.cat, self.character_set_key)

    def generate_proof(self, context):
        character_set = self.get_character_set(context)
        if not character_set and self.language in ["ar", "fa"]:
            return  # Skip if no Arabic/Farsi characters

        self.generate_text_proof(
            context,
            character_set,
            self.default_columns,
            self.default_paragraphs,
            self.mixed_styles,
            self.force_wordsiv,
            self.inject_text,
            self.accents,
            self.language,
            self.hoefler_style,
        )


class CategoryBasedProofHandler(BaseProofHandler):
    """Base handler for proofs that use character categories."""

    def get_character_category_setting(self, category):
        """Get character category setting value with appropriate defaults."""
        key = make_settings_key(self.unique_proof_key, "cat", category)
        # Default values: most categories enabled except accented
        defaults = {
            "uppercase_base": True,
            "lowercase_base": True,
            "numbers_symbols": True,
            "punctuation": True,
            "accented": False,
        }
        return self.proof_settings.get(key, defaults.get(category, True))

    def get_proof_sections(self, context):
        """Get proof sections based on user settings."""
        from fonts import get_charset_proof_categories

        categories = get_charset_proof_categories(context.cat)
        proof_sections = []

        # Check each category setting and add if enabled
        category_mapping = [
            ("uppercase_base", "Uppercase Base", categories["uppercase_base"]),
            ("lowercase_base", "Lowercase Base", categories["lowercase_base"]),
            ("numbers_symbols", "Numbers & Symbols", categories["numbers_symbols"]),
            ("punctuation", "Punctuation", categories["punctuation"]),
            ("accented", "Accented Characters", categories["accented"]),
        ]

        for category_key, section_label, character_set in category_mapping:
            if self.get_character_category_setting(category_key) and character_set:
                proof_sections.append((section_label, character_set))

        return proof_sections


class FilteredCharacterSetHandler(CategoryBasedProofHandler):
    """Handler for Filtered Character Set proof type."""

    def generate_proof(self, context):
        base_font_size = self.get_font_size()
        otfeatures = self.get_otfeatures()
        auto_size = self.get_auto_size()

        for section_label, character_set in self.get_proof_sections(context):
            if character_set:  # Only generate if characters exist
                if auto_size:
                    font_size = _calc_auto_size_for_page(
                        character_set,
                        context.ind_font,
                        tracking=0,
                        align="center",
                        ot_features=otfeatures,
                    )
                else:
                    font_size = base_font_size
                tracking_value = font_size / 1.5
                section_name = f"Character Set - {section_label} - {font_size}pt"
                charsetProof(
                    character_set,
                    context.axes_product,
                    context.ind_font,
                    None,  # pairedStaticStyles
                    otfeatures,
                    font_size,
                    sectionName=section_name,
                    tracking=tracking_value,
                )


class SpacingProofHandler(CategoryBasedProofHandler):
    """Handler for Spacing Proof type."""

    def generate_proof(self, context):
        params = self.get_common_proof_params(context, default_columns=2)
        otfeatures = params["otfeatures"]

        for section_label, character_set in self.get_proof_sections(context):
            if character_set:  # Only generate if characters exist
                section_name = f"Spacing - {section_label} - {params['font_size']}pt"
                spacingProof(
                    character_set,
                    context.axes_product,
                    context.ind_font,
                    None,  # pairedStaticStyles
                    otfeatures,
                    params["font_size"],
                    params["columns"],
                    sectionName=section_name,
                    tracking=params["tracking_value"],
                )


class ArCharacterSetHandler(BaseProofHandler):
    """Handler for Arabic Character Set proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()

        arabicContextualFormsProof(
            context.cat,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            self.get_otfeatures(),
            font_size,
            sectionName=section_name,
            tracking=tracking_value,
        )


class CustomTextProofHandler(BaseProofHandler):
    """Handler for Custom Text proof type — renders user-provided text."""

    def generate_proof(self, context):
        custom_text_key = make_settings_key(self.unique_proof_key, "customText")
        custom_text = self.proof_settings.get(custom_text_key, "")
        if not custom_text:
            print(f"No custom text provided for '{self.proof_name}', skipping")
            return

        # Generate Once: skip fonts that aren't the selected default
        once_key = make_settings_key(self.unique_proof_key, "generateOnce")
        generate_once = self.proof_settings.get(once_key, False)
        override_axis_dict = None
        if generate_once:
            path_key = make_settings_key(self.unique_proof_key, "defaultFontPath")
            axis_key = make_settings_key(self.unique_proof_key, "defaultFontAxisDict")
            default_font_path = self.proof_settings.get(path_key, "")
            default_axis_dict = self.proof_settings.get(axis_key, None)
            # Fallback: if no path stored or path not in loaded fonts, use first font
            all_fonts = context.all_fonts or [context.ind_font]
            if not default_font_path or default_font_path not in all_fonts:
                default_font_path = all_fonts[0]
            if context.ind_font != default_font_path:
                return
            if default_axis_dict is not None:
                override_axis_dict = default_axis_dict

        markup_key = make_settings_key(self.unique_proof_key, "markupEnabled")
        markup_enabled = self.proof_settings.get(markup_key, False)

        params = self.get_common_proof_params(context, default_columns=1)

        if markup_enabled:
            from markup_parser import parse_custom_text

            if generate_once and override_axis_dict is not None:
                axes_iter = [(str(override_axis_dict), override_axis_dict)]
            else:
                axes_iter = _normalize_axes(context.axes_product, context.ind_font)

            line_height_ratio = self.get_line_height_ratio()

            for suffix, axisDict in axes_iter:
                page_segments = parse_custom_text(
                    raw_text=custom_text,
                    base_font_size=params["font_size"],
                    base_font=context.ind_font,
                    all_fonts=context.all_fonts or [context.ind_font],
                    font_manager=context.font_manager,
                    base_tracking=params["tracking_value"],
                    base_align=params["align_value"],
                    base_otfeatures=params["otfeatures"],
                    base_axis_dict=axisDict,
                    base_line_height_ratio=line_height_ratio,
                )
                drawPageSegments(
                    page_segments,
                    f"{params['section_name']} - {suffix}",
                    params["columns"],
                    context.ind_font,
                    "ltr",
                    params["otfeatures"],
                    params["tracking_value"],
                    baseFontSize=params["font_size"],
                )
        else:
            if generate_once and override_axis_dict is not None:
                axes_product = [list(override_axis_dict.items())]
            else:
                axes_product = context.axes_product
            _render_proof_content(
                custom_text,
                params["font_size"],
                context.ind_font,
                axes_product,
                context.paired_static_styles,
                params["section_name"],
                columns=params["columns"],
                alignInput=params["align_value"],
                trackingInput=params["tracking_value"],
                otFeatures=params["otfeatures"],
                mixedStyles=False,
                direction="ltr",
                lineHeightInput=params["line_height"],
            )


class MultiStyleComparisonProofHandler(CategoryBasedProofHandler):
    """Handler for Multi-Style Comparison proof — shows one line per font/style,
    grouped by text type (character categories and/or custom text)."""

    # Track which proof instances have already been generated in the current
    # PDF run so that the per-font loop in run_proof doesn't duplicate output.
    _generated_instances: set = None

    @classmethod
    def reset_generated(cls):
        """Reset the per-run deduplication set."""
        cls._generated_instances = set()

    def generate_proof(self, context):
        # Deduplicate: only generate once across all fonts in the loop
        if MultiStyleComparisonProofHandler._generated_instances is None:
            MultiStyleComparisonProofHandler._generated_instances = set()
        if self.proof_name in MultiStyleComparisonProofHandler._generated_instances:
            return
        MultiStyleComparisonProofHandler._generated_instances.add(self.proof_name)

        all_fonts = context.all_fonts or [context.ind_font]
        font_manager = context.font_manager

        font_size = self.get_font_size()
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()
        otfeatures = self.get_otfeatures()
        auto_size = self.get_auto_size()

        # Collect the text groups to render
        text_groups = self._collect_text_groups(all_fonts)
        if not text_groups:
            print(f"No text groups selected for '{self.proof_name}', skipping")
            return

        # Collect (label, font_path, axis_variations) tuples for all styles
        styles = self._collect_styles(all_fonts, font_manager)

        # Auto-size: find the largest size where the longest text fits in one line
        if auto_size and text_groups and styles:
            min_size = float("inf")
            for _, group_text in text_groups:
                for _, font_path, axis_dict in styles:
                    sz = _calc_auto_size_for_line(
                        group_text,
                        font_path,
                        tracking=tracking_value,
                        ot_features=otfeatures,
                        axis_dict=axis_dict,
                    )
                    if sz < min_size:
                        min_size = sz
            if min_size < float("inf"):
                font_size = min_size

        # Render each text group
        for group_label, group_text in text_groups:
            section_name = f"{self.proof_name} - {group_label} - {font_size}pt"
            formatted = self._build_multi_style_string(
                group_text,
                styles,
                font_size,
                tracking_value,
                align_value,
                otfeatures,
            )
            drawContent(
                formatted,
                section_name,
                1,  # single column
                styles[0][1] if styles else context.ind_font,
                "ltr",
                otfeatures,
                tracking_value,
            )

    def _collect_text_groups(self, all_fonts):
        """Collect text groups from category settings and custom text."""
        groups = []

        # Build a merged category dict from all loaded fonts
        merged_cat = self._build_merged_categories(all_fonts)

        # Get category-based sections if any are enabled
        if merged_cat:
            from fonts import get_charset_proof_categories

            categories = get_charset_proof_categories(merged_cat)
            category_mapping = [
                ("uppercase_base", "Uppercase Base", categories["uppercase_base"]),
                ("lowercase_base", "Lowercase Base", categories["lowercase_base"]),
                (
                    "numbers_symbols",
                    "Numbers & Symbols",
                    categories["numbers_symbols"],
                ),
                ("punctuation", "Punctuation", categories["punctuation"]),
                ("accented", "Accented Characters", categories["accented"]),
            ]
            for category_key, label, character_set in category_mapping:
                if self.get_character_category_setting(category_key) and character_set:
                    groups.append((label, character_set))

        # Add custom text lines if present (each line becomes its own group)
        custom_text_key = make_settings_key(self.unique_proof_key, "customText")
        custom_text = self.proof_settings.get(custom_text_key, "")
        if custom_text:
            lines = [line for line in custom_text.splitlines() if line.strip()]
            for i, line in enumerate(lines, 1):
                label = f"Custom Text {i}" if len(lines) > 1 else "Custom Text"
                groups.append((label, line))

        return groups

    def _build_merged_categories(self, all_fonts):
        """Build a merged categorize() dict from all loaded fonts."""
        from fonts import categorize as _categorize

        merged = None
        for font_path in all_fonts:
            charset = filteredCharset(font_path)
            cat = _categorize(charset)
            if merged is None:
                merged = {
                    k: set(v) if isinstance(v, str) else v for k, v in cat.items()
                }
            else:
                for k, v in cat.items():
                    if isinstance(v, str):
                        merged[k] = merged.get(k, set()) | set(v)
        if merged is None:
            return None
        # Convert sets back to sorted strings
        result = {}
        for k, v in merged.items():
            if isinstance(v, set):
                result[k] = "".join(sorted(v, key=ord))
            else:
                result[k] = v
        return result

    def _collect_styles(self, all_fonts, font_manager):
        """Collect (display_label, font_path, axis_dict_or_None) for each enabled style.

        Uses the same named-instance enumeration as the UI
        (``_build_available_styles`` in app.py) so that style indices match
        the checkboxes the user sees.
        """
        from fonts import get_ttfont

        styles = []
        index = 0
        for font_path in all_fonts:
            tt = get_ttfont(font_path)
            if tt and "fvar" in tt:
                name_table = tt["name"]
                family_name = name_table.getBestFamilyName() or get_font_display_name(
                    font_path
                )
                for inst in tt["fvar"].instances:
                    coords = dict(inst.coordinates)
                    inst_name = name_table.getName(inst.subfamilyNameID, 3, 1, 0x0409)
                    style_name = (
                        str(inst_name)
                        if inst_name
                        else ", ".join(f"{k}:{v}" for k, v in coords.items())
                    )
                    if self._is_style_enabled(index):
                        label = f"{family_name} — {style_name}"
                        styles.append((label, font_path, coords))
                    index += 1
            else:
                if self._is_style_enabled(index):
                    styles.append((get_font_display_name(font_path), font_path, None))
                index += 1
        return styles

    def _is_style_enabled(self, index):
        """Check if a style at the given index is enabled in settings."""
        setting_key = make_settings_key(self.unique_proof_key, "style", str(index))
        return self.proof_settings.get(setting_key, True)

    def _build_multi_style_string(
        self,
        text,
        styles,
        font_size,
        tracking,
        align,
        otfeatures,
    ):
        """Build a single FormattedString with one line per style."""
        formatted = db.FormattedString(
            txt="",
            font=styles[0][1] if styles else "",
            fallbackFont=myFallbackFont,
            fontSize=font_size,
            align=align,
            tracking=tracking,
            openTypeFeatures=otfeatures,
        )
        for i, (label, font_path, axis_dict) in enumerate(styles):
            kwargs = dict(font=font_path, openTypeFeatures=otfeatures)
            if axis_dict:
                kwargs["fontVariations"] = axis_dict
            formatted.append(txt=text, **kwargs)
            if i < len(styles) - 1:
                formatted.append(txt="\n")
        return formatted


# =============================================================================
# Handler Registry and Factory
# =============================================================================


# Registry mapping proof types to their handler classes
PROOF_HANDLER_REGISTRY = {
    "Character Overview": FilteredCharacterSetHandler,
    "Spacing Test": SpacingProofHandler,
    "Ar Character Overview": ArCharacterSetHandler,
    "Custom Text": CustomTextProofHandler,
    "Style Comparison": MultiStyleComparisonProofHandler,
    # All other text-based proofs use StandardTextProofHandler with configuration
}


# Handler cache for performance optimization
_handler_cache = {}


def get_proof_handler(proof_type, proof_name, proof_settings, get_proof_font_size_func):
    """Factory function to create the appropriate proof handler with caching.

    Args:
        proof_type: The base proof type (e.g., "Structured Text (Heading)")
        proof_name: The specific proof instance name (may include numbers)
        proof_settings: Dictionary of proof settings
        get_proof_font_size_func: Function to get font size for a proof

    Returns:
        Instance of the appropriate proof handler, or None if not found
    """
    # Create cache key based on proof type and name
    cache_key = f"{proof_type}::{proof_name}"

    # Check cache first
    if cache_key in _handler_cache:
        # Update settings in cached handler (they may have changed)
        cached_handler = _handler_cache[cache_key]
        cached_handler.proof_settings = proof_settings
        cached_handler._cached_tracking = None  # Reset cache
        cached_handler._cached_align = None
        cached_handler._cached_font_size = None
        cached_handler._cached_line_height = None
        cached_handler._cached_columns = None
        cached_handler._cached_paragraphs = None
        cached_handler._cached_otfeatures = None
        return cached_handler

    # Check if this is a special handler in the registry
    handler_class = PROOF_HANDLER_REGISTRY.get(proof_type)
    if handler_class:
        try:
            handler = handler_class(
                proof_name, proof_settings, get_proof_font_size_func
            )
            _handler_cache[cache_key] = handler
            return handler
        except Exception as e:
            print(f"Error creating handler for '{proof_type}': {e}")
            return None

    # For text-based proofs, use StandardTextProofHandler with configuration
    from config import PROOF_REGISTRY

    # Find the proof key by looking up the display name in the registry
    proof_key = None
    for key, proof_info in PROOF_REGISTRY.items():
        if proof_info["display_name"] == proof_type:
            proof_key = key
            break

    if proof_key:
        try:
            handler = StandardTextProofHandler(
                proof_name, proof_settings, get_proof_font_size_func, proof_key
            )
            _handler_cache[cache_key] = handler
            return handler
        except Exception as e:
            print(f"Error creating StandardTextProofHandler for '{proof_type}': {e}")
            return None

    print(f"No handler found for proof type: {proof_type}")
    return None


def clear_handler_cache():
    """Clear the handler cache. Call when settings change significantly."""
    global _handler_cache
    _handler_cache.clear()
