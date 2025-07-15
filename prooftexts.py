# Proof Texts Module - Main interface for text samples and generators
# This module provides access to all text samples and generation utilities

# Import all text samples and utilities
from sample_texts import (
    bigMixedText, bigLowerText, bigUpperText, 
    smallMixedText, smallLowerText, smallUpperText,
    bigRandomNumbers, additionalSmallText
)

from script_texts import (
    arabicVocalization, arabicLatinMixed, arabicFarsiUrduNumbers
)

from accented_dictionary import accentedDict, get_accented_words, get_accented_characters

from text_generators import text_generator, TextGenerator

# Backward compatibility - make all text samples available at module level
__all__ = [
    'bigMixedText', 'bigLowerText', 'bigUpperText',
    'smallMixedText', 'smallLowerText', 'smallUpperText', 
    'bigRandomNumbers', 'additionalSmallText',
    'arabicVocalization', 'arabicLatinMixed', 'arabicFarsiUrduNumbers',
    'accentedDict', 'get_accented_words', 'get_accented_characters',
    'text_generator', 'TextGenerator'
]

# Convenience functions
def get_all_text_types():
    """Get list of all available text types"""
    return [
        'bigMixed', 'bigLower', 'bigUpper',
        'smallMixed', 'smallLower', 'smallUpper',
        'additional', 'numbers'
    ]

def get_all_script_types():
    """Get list of all available script types"""
    return ['arabic_vocalization', 'arabic_latin_mixed', 'arabic_farsi_urdu_numbers']
