# Character Analysis - Character set analysis and categorization

import unicodedata
from fontTools.unicodedata import script, block
from core_config import AR_TEMPLATE, FA_TEMPLATE, ARFA_DUAL_JOIN, ARFA_RIGHT_JOIN
from font_utils import UPPER_TEMPLATE, LOWER_TEMPLATE


def find_accented(char):
    """Check if character has diacritical marks."""
    decomp = unicodedata.normalize("NFD", char)
    return len(decomp) > 1 and unicodedata.category(decomp[1]) == "Mn"


def categorize(charset):
    """Categorize characters by Unicode category."""
    cat_map = {
        "Lu": "uniLu",  # Letter, uppercase
        "Ll": "uniLl",  # Letter, lowercase
        "Lo": "uniLo",  # Letter, other
        "Po": "uniPo",  # Punctuation, other
        "Pc": "uniPc",  # Punctuation, connector
        "Pd": "uniPd",  # Punctuation, dash
        "Ps": "uniPs",  # Punctuation, open
        "Pe": "uniPe",  # Punctuation, close
        "Pi": "uniPi",  # Punctuation, initial quote
        "Pf": "uniPf",  # Punctuation, final quote
        "Sm": "uniSm",  # Symbol, math
        "Sc": "uniSc",  # Symbol, currency
        "Nd": "uniNd",  # Number, decimal digit
        "No": "uniNo",  # Number, other
        "So": "uniSo",  # Symbol, other
    }

    result = {k: [] for k in cat_map.values()}
    result.update(
        {
            "uniLlBase": [],
            "uniLuBase": [],
            "accented": [],
            "accented_plus": [],  # Expanded accented category
            "latn": [],
            "arab": [],
            "fa": [],
            "ar": [],
            "arabTyped": [],
            "arfaDualJoin": [],
            "arfaRightJoin": [],
        }
    )

    for char in charset:
        cat = unicodedata.category(char)
        if cat in cat_map:
            result[cat_map[cat]].append(char)

        if cat in ("Ll", "Lu"):
            base_key = "uniLlBase" if cat == "Ll" else "uniLuBase"
            target_key = "accented" if find_accented(char) else base_key
            result[target_key].append(char)

        # Script-based categorization
        try:
            char_script = script(char)
            if char_script == "Latn":
                result["latn"].append(char)
            elif char_script == "Arab":
                result["arab"].append(char)
                # Check if it's specifically Arabic block
                if block(char) == "Arabic":
                    result["arabTyped"].append(char)
        except (ImportError, AttributeError):
            # Fallback if fontTools.unicodedata is not available
            pass

        # Template-based categorization for Arabic/Farsi
        if char in AR_TEMPLATE:
            result["ar"].append(char)
        if char in FA_TEMPLATE:
            result["fa"].append(char)
        if char in ARFA_DUAL_JOIN:
            result["arfaDualJoin"].append(char)
        if char in ARFA_RIGHT_JOIN:
            result["arfaRightJoin"].append(char)

    # Convert to strings and add boolean flags
    result_str = {k: "".join(v) for k, v in result.items()}

    # Create expanded accented category (accented + other uppercase/lowercase not in basic templates)
    uc_lc = result_str["uniLu"] + result_str["uniLl"]
    other = ""
    for char in uc_lc:
        if (
            char not in result_str["accented"]
            and char not in LOWER_TEMPLATE
            and char not in UPPER_TEMPLATE
        ):
            other += char

    result_str["accented_plus"] = result_str["accented"] + other

    result_str.update(
        {
            "uppercaseOnly": result_str["uniLl"] == "",
            "lowercaseOnly": result_str["uniLu"] == "",
        }
    )

    return result_str


def check_arabic_support(charset):
    """Check if charset supports Arabic characters."""
    required_chars = {"ب", "ا", "ح", "د", "ر"}  # Arabic test characters
    charset_set = set(charset)
    return required_chars.issubset(charset_set)


def get_character_set(font_path):
    """Get character set from a font file (alias for filteredCharset)."""
    from font_utils import filteredCharset

    return filteredCharset(font_path)
