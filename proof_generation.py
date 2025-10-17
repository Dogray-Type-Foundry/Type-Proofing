# Proof Generation Functions and Text Processing

import datetime
import os
import random
import traceback
import unicodedata
import drawBot as db
from wordsiv import WordSiv
from core_config import (
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
)
from proof_config import get_proof_default_font_size
from font_utils import (
    get_ttfont,
    UPPER_TEMPLATE as upperTemplate,
    LOWER_TEMPLATE as lowerTemplate,
)

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


# Internal helpers
def _normalize_axes(axesProduct, indFont):
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
        from proof_generation import get_font_display_name  # local import safe

        yield get_font_display_name(indFont), None


def get_font_display_name(indFont):
    """Get the display name for a font, extracting the style from the font name."""
    try:
        font_name = db.font(indFont)
        if "-" in font_name:
            return font_name.split("-")[1]
        return font_name
    except (IndexError, AttributeError):
        return "Unknown"


def drawFooter(title, indFont, otFeatures=None, tracking=None):
    """Draw a simple footer with some minimal but useful info."""
    with db.savedState():
        # get date and font name
        today = datetime.date.today()
        fontFileName = os.path.basename(indFont)
        familyName = os.path.splitext(fontFileName)[0].split("-")[0]
        # assemble footer text
        footerText = f"{today} | {familyName} | {title}"

        # and display formatted string
        footer = db.FormattedString(
            footerText, font="Courier", fontSize=9, lineHeight=9
        )
        folio = db.FormattedString(
            str(db.pageCount()),
            font="Courier",
            fontSize=9,
            lineHeight=9,
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
                9,
            ),
        )
        db.textBox(
            folio,
            (
                marginHorizontal,
                marginVertical - 18,
                db.width() - marginHorizontal * 2,
                9,
            ),
        )

        # Features line (if any features to display)
        if features_text:
            features_footer = db.FormattedString(
                f"OT Fea: {features_text}",
                font="Courier",
                fontSize=7,
                lineHeight=7,
            )
            db.textBox(
                features_footer,
                (
                    marginHorizontal,
                    marginVertical - 28,  # 10 points below main footer
                    db.width() - marginHorizontal * 2,
                    7,
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

    else:
        # No valid pairing found - return None to indicate this font should be skipped
        return None

    return textString


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
    textToDraw,
    pageTitle,
    columnNumber,
    currentFont,
    direction="ltr",
    otFeatures=None,
    tracking=None,
):
    """Function to draw content with proper layout."""
    try:
        showBaselines = (
            getattr(db, "showBaselines", True) if hasattr(db, "showBaselines") else True
        )

        while textToDraw:
            db.newPage(pageDimensions)
            drawFooter(pageTitle, currentFont, otFeatures, tracking)
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


def charsetProof(
    characterSet,
    axesProduct,
    indFont,
    pairedStaticStyles,
    otFea=None,
    fontSize=None,
    sectionName="Filtered Character Set",
    tracking=None,
):
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
    tracking_value = tracking if tracking is not None else 24

    # sectionName parameter is now passed from the caller
    try:
        for suffix, axisDict in _normalize_axes(axesProduct, indFont):
            charsetString = (
                stringMaker(
                    characterSet,
                    proof_font_size,
                    indFont,
                    axesProduct,
                    pairedStaticStyles,
                    "center",
                    tracking_value,
                    otFea,
                    VFAxisInput=axisDict,
                    mixedStyles=False,
                )
                if axisDict is not None
                else stringMaker(
                    characterSet,
                    proof_font_size,
                    indFont,
                    axesProduct,
                    pairedStaticStyles,
                    "center",
                    tracking_value,
                    otFea,
                    mixedStyles=False,
                )
            )
            drawContent(
                charsetString,
                sectionName + " - " + suffix,
                1,
                indFont,
                "ltr",
                otFea,
                tracking,
            )
    except Exception as e:
        print(f"Error in charsetProof: {e}")
        traceback.print_exc()


def spacingProof(
    characterSet,
    axesProduct,
    indFont,
    pairedStaticStyles,
    otFea=None,
    fontSize=None,
    columns=None,
    sectionName="Spacing proof",
    tracking=None,
):
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

    for suffix, axisDict in _normalize_axes(axesProduct, indFont):
        spacingString = (
            stringMaker(
                spacingStringInput,
                proof_font_size,
                indFont,
                axesProduct,
                pairedStaticStyles,
                OTFeaInput=used_features,
                VFAxisInput=axisDict,
                mixedStyles=False,
            )
            if axisDict is not None
            else stringMaker(
                spacingStringInput,
                proof_font_size,
                indFont,
                axesProduct,
                pairedStaticStyles,
                OTFeaInput=used_features,
                mixedStyles=False,
            )
        )
        drawContent(
            spacingString,
            sectionName + " - " + suffix,
            proof_columns,
            indFont,
            "ltr",
            used_features,
            tracking,
        )


def textProof(
    characterSet,
    axesProduct,
    indFont,
    pairedStaticStyles,
    cols=2,
    para=3,
    casing=False,
    textSize=None,
    sectionName="Text Proof",
    mixedStyles=False,
    forceWordsiv=False,
    injectText=None,
    otFea=None,
    accents=0,
    cat=None,
    fullCharacterSet=None,
    lang=None,
    tracking=0,
    align="left",
):
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

    for suffix, axisDict in _normalize_axes(axesProduct, indFont):
        textString = (
            stringMaker(
                textStringInput,
                textSize,
                indFont,
                axesProduct,
                pairedStaticStyles,
                alignInput=align,
                trackingInput=tracking,
                OTFeaInput=otFea,
                VFAxisInput=axisDict,
                mixedStyles=mixedStyles,
            )
            if axisDict is not None
            else stringMaker(
                textStringInput,
                textSize,
                indFont,
                axesProduct,
                pairedStaticStyles,
                alignInput=align,
                trackingInput=tracking,
                OTFeaInput=otFea,
                mixedStyles=mixedStyles,
            )
        )
        # Skip this font if no valid pairing found for mixed styles
        if mixedStyles and textString is None:
            continue
        drawContent(
            textString,
            sectionName + " - " + suffix,
            columnNumber=cols,
            currentFont=indFont,
            direction=text_direction,
            otFeatures=otFea,
            tracking=tracking,
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
        for suffix, axisDict in _normalize_axes(axesProduct, indFont):
            formattedString = (
                stringMaker(
                    contextualString,
                    proof_font_size,
                    indFont,
                    axesProduct,
                    pairedStaticStyles,
                    "center",
                    0,
                    otFea,
                    VFAxisInput=axisDict,
                    mixedStyles=False,
                )
                if axisDict is not None
                else stringMaker(
                    contextualString,
                    proof_font_size,
                    indFont,
                    axesProduct,
                    pairedStaticStyles,
                    "center",
                    0,
                    otFea,
                    mixedStyles=False,
                )
            )
            drawContent(
                formattedString,
                sectionName + " - " + suffix,
                1,
                indFont,
                direction="rtl",
                otFeatures=otFea,
                tracking=tracking,
            )
    except Exception as e:
        print(f"Error in arabicContextualFormsProof: {e}")
        traceback.print_exc()
