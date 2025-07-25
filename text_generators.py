# Text Generators - Functions for dynamic text generation and manipulation

import random
from sample_texts import *
from script_texts import *
from accented_dictionary import accentedDict


class TextGenerator:
    """Handles dynamic text generation for proof documents"""

    def __init__(self):
        self.sample_texts = {
            "bigMixed": bigMixedText,
            "bigLower": bigLowerText,
            "bigUpper": bigUpperText,
            "smallMixed": smallMixedText,
            "smallLower": smallLowerText,
            "smallUpper": smallUpperText,
            "additional": additionalSmallText,
        }

        self.script_texts = {
            "arabic_vocalization": arabicVocalization,
            "arabic_latin_mixed": arabicLatinMixed,
            "arabic_farsi_urdu_numbers": arabicFarsiUrduNumbers,
        }

    def get_text_sample(self, text_type, case="mixed"):
        """Get a specific text sample by type and case"""
        if text_type == "big":
            if case == "mixed":
                return self.sample_texts["bigMixed"]
            elif case == "lower":
                return self.sample_texts["bigLower"]
            elif case == "upper":
                return self.sample_texts["bigUpper"]
        elif text_type == "small":
            if case == "mixed":
                return self.sample_texts["smallMixed"]
            elif case == "lower":
                return self.sample_texts["smallLower"]
            elif case == "upper":
                return self.sample_texts["smallUpper"]
        elif text_type == "additional":
            return self.sample_texts["additional"]
        elif text_type == "numbers":
            return bigRandomNumbers

        return ""

    def get_script_text(self, script_type):
        """Get script-specific text samples"""
        return self.script_texts.get(script_type, "")

    def generate_accented_text(self, character_list=None, word_count=50):
        """Generate text using accented characters"""
        if character_list is None:
            character_list = list(accentedDict.keys())

        words = []
        for char in character_list[:10]:  # Limit to first 10 characters
            if char in accentedDict:
                words.extend(accentedDict[char][:5])  # Take first 5 words per character

        random.shuffle(words)
        return " ".join(words[:word_count])

    def generate_random_numbers(self, count=100):
        """Generate random number sequences"""
        numbers = []
        for _ in range(count):
            # Mix of different number formats
            if random.choice([True, False]):
                numbers.append(str(random.randint(0, 9999)))
            else:
                numbers.append(f"{random.randint(0, 99)}.{random.randint(0, 99)}")
        return " ".join(numbers)

    def mix_texts(self, *text_types):
        """Mix multiple text types together"""
        combined = []
        for text_type in text_types:
            text = self.get_text_sample(text_type)
            if text:
                combined.append(text[:500])  # Take first 500 chars of each
        return "\n\n".join(combined)

    def get_character_set_sample(self, start_char, end_char, repeat=3):
        """Generate character set samples for testing"""
        chars = []
        for i in range(ord(start_char), ord(end_char) + 1):
            chars.append(chr(i) * repeat)
        return " ".join(chars)


# Global instance for easy access
text_generator = TextGenerator()
