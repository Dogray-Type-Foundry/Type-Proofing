# Script Configuration - Arabic/Farsi script analysis constants

# Arabic/Farsi character templates for script analysis
AR_TEMPLATE = "ابجدهوزحطيكلمنسعفصقرشتثخذضظغء"
FA_TEMPLATE = "یهونملگکقفغعظطضصشسژزرذدخحچجثتپباء"
ARFA_DUAL_JOIN = "بتثپنقفڤسشصضطظكلهةمعغحخجچيئىکگی"
ARFA_RIGHT_JOIN = "اأإآٱرزدذوؤژ"

# Positional forms for Arabic/Farsi contextual analysis
POS_FORMS = ("init", "medi", "fina")


def load_arabic_texts():
    """Load Arabic text constants from prooftexts module."""
    try:
        from importlib import reload
        import prooftexts

        reload(prooftexts)
        # Make Arabic texts available globally
        arabic_vocalization = prooftexts.arabicVocalization
        arabic_latin_mixed = prooftexts.arabicLatinMixed
        arabic_farsi_urdu_numbers = prooftexts.arabicFarsiUrduNumbers

        return {
            "arabic_vocalization": arabic_vocalization,
            "arabic_latin_mixed": arabic_latin_mixed,
            "arabic_farsi_urdu_numbers": arabic_farsi_urdu_numbers,
        }
    except ImportError:
        print(
            "Warning: prooftexts module not found. Arabic text constants not available."
        )
        return {
            "arabic_vocalization": "Arabic vocalization text not available",
            "arabic_latin_mixed": "Arabic-Latin mixed text not available",
            "arabic_farsi_urdu_numbers": "Arabic-Farsi-Urdu numbers text not available",
        }


# Load the texts when module is imported
ARABIC_TEXTS = load_arabic_texts()
