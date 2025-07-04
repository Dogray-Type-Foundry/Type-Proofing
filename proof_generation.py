# Proof Generation Functions and Text Processing

import datetime
import os
import random
import traceback
import unicodedata

# Third-party imports
import drawBot as db
from wordsiv import WordSiv

# Local imports
from config import (
    charsetFontSize,
    spacingFontSize,
    largeTextFontSize,
    smallTextFontSize,
    marginHorizontal,
    marginVertical,
    pageDimensions,
    myFallbackFont,
    useFontContainsCharacters,
    wordsivSeed,
    dualStyleSeed,
    FsSelection,
)
from font_analysis import get_ttfont, upperTemplate, lowerTemplate, product_dict

# Import drawbot grid extension
try:
    from drawBotGrid import BaselineGrid, columnBaselineGridTextBox
except ImportError:
    print("Warning: drawBotGrid not found. Grid functionality will be limited.")
    BaselineGrid = None
    columnBaselineGridTextBox = None

# Import proof texts
try:
    from importlib import reload
    import prooftexts

    reload(prooftexts)
    import prooftexts as pte
except ImportError:
    print("Warning: prooftexts module not found. Using fallback text.")
    pte = None


def drawFooter(title, indFont):
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
    upit=False,
    rgbd=False,
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
        if upit or rgbd:
            return _handle_mixed_styles(
                textString,
                textInput,
                indFont,
                axesProduct,
                pairedStaticStyles,
                VFAxisInput,
                upit,
                rgbd,
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
    upit,
    rgbd,
):
    """Handle mixed upright/italic and regular/bold styles."""
    random.seed(a=dualStyleSeed)
    f = get_ttfont(indFont)

    # Static font upright/italic mixing
    if upit and pairedStaticStyles[0] and f["OS/2"].fsSelection & FsSelection.ITALIC:
        upFont, itFont = pairedStaticStyles[0][f["OS/2"].usWeightClass]
        _apply_alternating_fonts(textString, textInput, [upFont, itFont])

    # Variable font italic axis mixing
    elif (
        axesProduct
        and upit
        and VFAxisInput
        and "ital" in VFAxisInput
        and VFAxisInput["ital"] != 0
    ):
        _apply_alternating_variations(
            textString, textInput, VFAxisInput, "ital", [0.0, 1.0]
        )

    # Static font regular/bold mixing
    elif rgbd and pairedStaticStyles[1] and f["name"].getBestSubFamilyName() == "Bold":
        rgFont, bdFont = pairedStaticStyles[1][f["name"].getBestFamilyName()]
        _apply_alternating_fonts(textString, textInput, [rgFont, bdFont])

    # Variable font weight axis mixing
    elif (
        axesProduct
        and rgbd
        and VFAxisInput
        and "wght" in VFAxisInput
        and VFAxisInput["wght"] == 700
    ):
        _apply_alternating_variations(
            textString, textInput, VFAxisInput, "wght", [400.0, 700.0]
        )

    else:
        textString.append(txt=textInput)

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


def drawContent(textToDraw, pageTitle, columnNumber, currentFont):
    """Function to draw content with proper layout."""
    try:
        showBaselines = (
            getattr(db, "showBaselines", True) if hasattr(db, "showBaselines") else True
        )

        while textToDraw:
            db.newPage(pageDimensions)
            drawFooter(pageTitle, currentFont)
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
):
    """Generate long text proofing strings either through wordsiv or premade strings."""
    if cat is None:
        return ""

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


def generateSpacingString(characterSet):
    """Create empty formatted string that we will fill with spacing strings."""
    spacingString = ""
    for char in characterSet:
        # determine control characters for each character
        if useFontContainsCharacters and not db.fontContainsCharacters(char):
            continue

        # ignoring linebreaks and space characters
        if char not in ["\n", " "]:
            control1 = "H"
            control2 = "O"
            if unicodedata.category(char) == "Ll":
                control1 = "n"
                control2 = "o"
            elif unicodedata.category(char) == "Nd":
                control1 = "0"
                control2 = "1"

            perCharSpacingString = f"{control1}{control1}{control1}{char}{control1}{control2}{control1}{char}{control2}{char}{control2}{control2}{control2}\n"
            spacingString += perCharSpacingString
    return spacingString


def charsetProof(characterSet, axesProduct, indFont, pairedStaticStyles, otFea=None):
    """Generate character set proof."""
    if not characterSet:
        print("Empty character set, skipping")
        return

    sectionName = "Character set proof"
    try:
        if axesProduct:
            axisDict = {}
            for axisData in axesProduct:
                axisDict = dict(axisData)
                charsetString = stringMaker(
                    characterSet,
                    charsetFontSize,
                    indFont,
                    axesProduct,
                    pairedStaticStyles,
                    "center",
                    24,
                    otFea,
                    axisDict,
                )
                drawContent(
                    charsetString, sectionName + " - " + str(axisData), 1, indFont
                )
        elif axesProduct == "":
            charsetString = stringMaker(
                characterSet,
                charsetFontSize,
                indFont,
                axesProduct,
                pairedStaticStyles,
                "center",
                24,
                otFea,
            )
            drawContent(
                charsetString,
                sectionName + " - " + db.font(indFont).split("-")[1],
                1,
                indFont,
            )
    except Exception as e:
        print(f"Error in charsetProof: {e}")
        traceback.print_exc()


def spacingProof(characterSet, axesProduct, indFont, pairedStaticStyles, otFea=None):
    """Generate spacing proof."""
    sectionName = "Spacing proof"
    if axesProduct:
        axisDict = {}
        for axisData in axesProduct:
            axisDict = dict(axisData)
            spacingStringInput = generateSpacingString(characterSet)
            spacingString = stringMaker(
                spacingStringInput,
                spacingFontSize,
                indFont,
                axesProduct,
                pairedStaticStyles,
                OTFeaInput=dict(liga=False, kern=False) if otFea is None else otFea,
                VFAxisInput=axisDict,
            )
            drawContent(spacingString, sectionName + " - " + str(axisData), 2, indFont)

    elif axesProduct == "":
        spacingStringInput = generateSpacingString(characterSet)
        spacingString = stringMaker(
            spacingStringInput,
            spacingFontSize,
            indFont,
            axesProduct,
            pairedStaticStyles,
            OTFeaInput=dict(liga=False, kern=False) if otFea is None else otFea,
        )
        drawContent(
            spacingString,
            sectionName + " - " + db.font(indFont).split("-")[1],
            2,
            indFont,
        )


def textProof(
    characterSet,
    axesProduct,
    indFont,
    pairedStaticStyles,
    cols=2,
    para=3,
    casing=False,
    textSize=smallTextFontSize,
    sectionName="Text Proof",
    upit=False,
    rgbd=False,
    forceWordsiv=False,
    injectText=None,
    otFea=None,
    accents=0,
    cat=None,
    fullCharacterSet=None,
):
    """Generate text proof with various options."""
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
                if textSize == smallTextFontSize:
                    textStringInput += "\n"
    elif not injectText:
        textStringInput = generateTextProofString(
            characterSet,
            para,
            casing,
            forceWordsiv=forceWordsiv,
            cat=cat,
            fullCharacterSet=fullCharacterSet,
        )
    elif injectText:
        for t in injectText:
            textStringInput += t + "\n"

    # Generate proof for each axis variation
    if axesProduct:
        axisDict = {}
        for axisData in axesProduct:
            axisDict = dict(axisData)
            textString = stringMaker(
                textStringInput,
                textSize,
                indFont,
                axesProduct,
                pairedStaticStyles,
                OTFeaInput=otFea,
                VFAxisInput=axisDict,
                upit=upit,
                rgbd=rgbd,
            )
            drawContent(
                textString,
                sectionName + " - " + str(axisData),
                columnNumber=cols,
                currentFont=indFont,
            )
    elif axesProduct == "":
        textString = stringMaker(
            textStringInput,
            textSize,
            indFont,
            axesProduct,
            pairedStaticStyles,
            OTFeaInput=otFea,
            upit=upit,
            rgbd=rgbd,
        )
        drawContent(
            textString,
            sectionName + " - " + db.font(indFont).split("-")[1],
            columnNumber=cols,
            currentFont=indFont,
        )
