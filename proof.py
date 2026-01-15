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
from wordsiv import WordSiv
import config as _cc
from config import (
    marginHorizontal,
    marginVertical,
    pageDimensions,
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
    UPPER_TEMPLATE as upperTemplate,
    LOWER_TEMPLATE as lowerTemplate,
)
from settings import make_settings_key, create_unique_proof_key

# product_dict not used in this module

try:
    from drawBotGrid import BaselineGrid, columnBaselineGridTextBox
except ImportError:
    print("Warning: drawBotGrid not found. Grid functionality will be limited.")
    BaselineGrid = None
    columnBaselineGridTextBox = None

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
    from ui import text_generator, TextGenerator

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
):
    """Function to create a formatted string to feed into textBox."""
    try:
        textString = db.FormattedString(
            txt="",
            font=indFont,
            fallbackFont=myFallbackFont,
            fontSize=fontSizeInput,
            align=alignInput,
            tracking=trackingInput,
            openTypeFeatures=OTFeaInput,
            fontVariations=VFAxisInput,
        )

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
) -> None:
    """Function to draw content with proper layout."""
    try:
        showBaselines = (
            getattr(db, "showBaselines", True) if hasattr(db, "showBaselines") else True
        )

        global _PROOF_PAGE_INDEX

        while textToDraw:
            db.newPage(pageDimensions)
            _PROOF_PAGE_INDEX += 1
            drawFooter(
                pageTitle,
                currentFont,
                otFeatures,
                tracking,
                pageNumber=_PROOF_PAGE_INDEX,
            )
            db.hyphenation(False)

            if BaselineGrid and columnBaselineGridTextBox:
                baselines = BaselineGrid.from_margins(
                    (0, -marginVertical, 0, -marginVertical),
                    textToDraw.fontLineHeight() / 2,
                )

                if getattr(db, "showBaselines", True):
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
                    draw_grid=getattr(db, "showBaselines", True),
                    direction=direction,
                )
            else:
                # Fallback to simple text box without grid
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
):
    """Generate long text proofing strings either through wordsiv or premade strings."""
    if cat is None:
        return ""

    # Handle Arabic/Farsi languages with specific logic
    if lang in ["ar", "fa"]:
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
    sectionName: str = "Filtered Character Set",
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
    sectionName="Ar Character Set",
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


class BaseProofHandler(ABC):
    """Base class for all proof type handlers."""

    def __init__(self, proof_name, proof_settings, get_proof_font_size_func):
        self.proof_name = proof_name
        self.proof_settings = proof_settings
        self.get_proof_font_size = get_proof_font_size_func
        self.unique_proof_key = create_unique_proof_key(proof_name)

        # Cache commonly accessed settings for performance
        self._cached_font_size = None
        self._cached_tracking = None
        self._cached_align = None

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

    def get_section_name(self, font_size):
        """Get section name for this proof."""
        return f"{self.proof_name} - {font_size}pt"

    def get_common_proof_params(self, context, default_columns=2, default_paragraphs=5):
        """Extract common proof parameters to reduce code duplication."""
        return {
            "font_size": self.get_font_size(),
            "columns": context.cols_by_proof.get(context.proof_name, default_columns),
            "paragraphs": context.paras_by_proof.get(
                context.proof_name, default_paragraphs
            ),
            "section_name": self.get_section_name(self.get_font_size()),
            "tracking_value": self.get_tracking_value(),
            "align_value": self.get_align_value(),
            "otfeatures": context.otfeatures_by_proof.get(context.proof_name, {}),
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
        font_size = self.get_font_size()
        tracking_value = font_size / 1.5
        otfeatures = context.otfeatures_by_proof.get(context.proof_name, {})

        for section_label, character_set in self.get_proof_sections(context):
            if character_set:  # Only generate if characters exist
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
            context.otfeatures_by_proof.get(context.proof_name, {}),
            font_size,
            sectionName=section_name,
            tracking=tracking_value,
        )


# =============================================================================
# Handler Registry and Factory
# =============================================================================


# Registry mapping proof types to their handler classes
PROOF_HANDLER_REGISTRY = {
    "Filtered Character Set": FilteredCharacterSetHandler,
    "Spacing Proof": SpacingProofHandler,
    "Ar Character Set": ArCharacterSetHandler,
    # All other text-based proofs use StandardTextProofHandler with configuration
}


# Handler cache for performance optimization
_handler_cache = {}


def get_proof_handler(proof_type, proof_name, proof_settings, get_proof_font_size_func):
    """Factory function to create the appropriate proof handler with caching.

    Args:
        proof_type: The base proof type (e.g., "Basic Paragraph Large")
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
