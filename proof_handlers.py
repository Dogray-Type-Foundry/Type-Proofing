# Proof Type Handlers - Modular proof generation system

from abc import ABC, abstractmethod
from proof_generation import (
    charsetProof,
    spacingProof,
    textProof,
    arabicContextualFormsProof,
)
from script_texts import arabicVocalization, arabicLatinMixed, arabicFarsiUrduNumbers


def create_unique_proof_key(proof_name):
    """Create a unique key from proof name for settings storage."""
    unique_proof_key = (
        proof_name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    )
    return unique_proof_key


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
                f"{self.unique_proof_key}_tracking", 0
            )
        return self._cached_tracking

    def get_align_value(self):
        """Get alignment value for this proof."""
        if self._cached_align is None:
            self._cached_align = self.proof_settings.get(
                f"{self.unique_proof_key}_align", "left"
            )
        return self._cached_align

    def get_section_name(self, font_size):
        """Get section name for this proof."""
        return f"{self.proof_name} - {font_size}pt"

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
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, default_columns)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        # Use provided paragraphs or get from context
        paragraphs = context.paras_by_proof.get(context.proof_name, default_paragraphs)

        textProof(
            character_set,
            context.axes_product,
            context.ind_font,
            context.paired_static_styles if mixed_styles else None,
            columns,
            paragraphs,
            False,  # casing
            font_size,
            section_name,
            mixed_styles,
            force_wordsiv,
            inject_text,
            context.otfeatures_by_proof.get(context.proof_name, {}),
            accents,
            context.cat,
            context.full_character_set,
            language,
            tracking_value,
            align_value,
        )


class ProofContext:
    """Context object containing all data needed for proof generation."""

    def __init__(
        self,
        full_character_set,
        axes_product,
        ind_font,
        paired_static_styles,
        otfeatures_by_proof,
        cols_by_proof,
        paras_by_proof,
        cat,
        proof_name,
    ):
        self.full_character_set = full_character_set
        self.axes_product = axes_product
        self.ind_font = ind_font
        self.paired_static_styles = paired_static_styles
        self.otfeatures_by_proof = otfeatures_by_proof
        self.cols_by_proof = cols_by_proof
        self.paras_by_proof = paras_by_proof
        self.cat = cat
        self.proof_name = proof_name


class FilteredCharacterSetHandler(BaseProofHandler):
    """Handler for Filtered Character Set proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()

        charsetProof(
            context.full_character_set,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            context.otfeatures_by_proof.get(context.proof_name, {}),
            font_size,
            sectionName=section_name,
            tracking=tracking_value,
        )


class SpacingProofHandler(BaseProofHandler):
    """Handler for Spacing Proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()

        spacingProof(
            context.full_character_set,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            context.otfeatures_by_proof.get(context.proof_name, {}),
            font_size,
            columns,
            sectionName=section_name,
            tracking=tracking_value,
        )


class BasicParagraphLargeHandler(BaseProofHandler):
    """Handler for Basic Paragraph Large proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 1)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            context.cat["uniLu"] + context.cat["uniLl"],
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            2,
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            None,  # lang
            tracking_value,
            align_value,
        )


class DiacriticWordsLargeHandler(BaseProofHandler):
    """Handler for Diacritic Words Large proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 1)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            context.cat["accented_plus"],
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            3,
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            3,
            context.cat,
            context.full_character_set,
            None,  # lang
            tracking_value,
            align_value,
        )


class BasicParagraphSmallHandler(BaseProofHandler):
    """Handler for Basic Paragraph Small proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            context.cat["uniLu"] + context.cat["uniLl"],
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            5,
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            None,  # lang
            tracking_value,
            align_value,
        )


class PairedStylesParagraphSmallHandler(BaseProofHandler):
    """Handler for Paired Styles Paragraph Small proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            context.cat["uniLu"] + context.cat["uniLl"],
            context.axes_product,
            context.ind_font,
            context.paired_static_styles,
            columns,
            5,
            False,
            font_size,
            section_name,
            True,  # mixedStyles=True for SmallPairedStylesProof
            True,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            None,  # lang
            tracking_value,
            align_value,
        )


class GenerativeTextSmallHandler(BaseProofHandler):
    """Handler for Generative Text Small proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        paragraphs = context.paras_by_proof.get(context.proof_name, 5)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            context.cat["uniLu"] + context.cat["uniLl"],
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            paragraphs,
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            True,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            None,  # lang
            tracking_value,
            align_value,
        )


class DiacriticWordsSmallHandler(BaseProofHandler):
    """Handler for Diacritic Words Small proof type."""

    def generate_proof(self, context):
        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            context.cat["accented_plus"],
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            4,
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            4,
            context.cat,
            context.full_character_set,
            None,  # lang
            tracking_value,
            align_value,
        )


class MiscParagraphSmallHandler(BaseProofHandler):
    """Handler for Misc Paragraph Small proof type."""

    def generate_proof(self, context):
        try:
            from proof_generation import pte
        except ImportError:
            pte = None

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            context.cat["uniLu"] + context.cat["uniLl"],
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            5,
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            (  # injectText
                pte.bigRandomNumbers if pte else "",
                pte.additionalSmallText if pte else "",
            ),
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            None,  # lang
            tracking_value,
            align_value,
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


class ArParagraphLargeHandler(BaseProofHandler):
    """Handler for Arabic Paragraph Large proof type."""

    def generate_proof(self, context):
        arabic_chars = context.cat.get("ar", "") or context.cat.get("arab", "")
        if not arabic_chars:
            return

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 1)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            arabic_chars,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            2,  # Fixed paragraph count for big text
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            "ar",
            tracking_value,
            align_value,
        )


class FaParagraphLargeHandler(BaseProofHandler):
    """Handler for Farsi Paragraph Large proof type."""

    def generate_proof(self, context):
        farsi_chars = context.cat.get("fa", "") or context.cat.get("arab", "")
        if not farsi_chars:
            return

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 1)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            farsi_chars,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            2,  # Fixed paragraph count for big text
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            "fa",
            tracking_value,
            align_value,
        )


class ArParagraphSmallHandler(BaseProofHandler):
    """Handler for Arabic Paragraph Small proof type."""

    def generate_proof(self, context):
        arabic_chars = context.cat.get("ar", "") or context.cat.get("arab", "")
        if not arabic_chars:
            return

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            arabic_chars,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            5,  # Standard paragraph count for small text
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            "ar",
            tracking_value,
            align_value,
        )


class FaParagraphSmallHandler(BaseProofHandler):
    """Handler for Farsi Paragraph Small proof type."""

    def generate_proof(self, context):
        farsi_chars = context.cat.get("fa", "") or context.cat.get("arab", "")
        if not farsi_chars:
            return

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            farsi_chars,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            5,  # Standard paragraph count for small text
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            None,  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            "fa",
            tracking_value,
            align_value,
        )


class ArVocalizationParagraphSmallHandler(BaseProofHandler):
    """Handler for Arabic Vocalization Paragraph Small proof type."""

    def generate_proof(self, context):
        arabic_chars = context.cat.get("ar", "") or context.cat.get("arab", "")
        if not arabic_chars:
            return

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            arabic_chars,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            3,  # Specific paragraph count for vocalization
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            (arabicVocalization,),  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            "ar",
            tracking_value,
            align_value,
        )


class ArLatMixedParagraphSmallHandler(BaseProofHandler):
    """Handler for Arabic-Latin Mixed Paragraph Small proof type."""

    def generate_proof(self, context):
        arabic_chars = context.cat.get("ar", "") or context.cat.get("arab", "")
        if not arabic_chars:
            return

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            arabic_chars,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            3,  # Specific paragraph count for mixed text
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            (arabicLatinMixed,),  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            "ar",
            tracking_value,
            align_value,
        )


class ArNumbersSmallHandler(BaseProofHandler):
    """Handler for Arabic Numbers Small proof type."""

    def generate_proof(self, context):
        arabic_chars = context.cat.get("ar", "") or context.cat.get("arab", "")
        if not arabic_chars:
            return

        font_size = self.get_font_size()
        columns = context.cols_by_proof.get(context.proof_name, 2)
        section_name = self.get_section_name(font_size)
        tracking_value = self.get_tracking_value()
        align_value = self.get_align_value()

        textProof(
            arabic_chars,
            context.axes_product,
            context.ind_font,
            None,  # pairedStaticStyles
            columns,
            3,  # Specific paragraph count for numbers
            False,
            font_size,
            section_name,
            False,  # mixedStyles=False
            False,  # forceWordsiv
            (arabicFarsiUrduNumbers,),  # injectText
            context.otfeatures_by_proof.get(context.proof_name, {}),
            0,
            context.cat,
            context.full_character_set,
            "ar",
            tracking_value,
            align_value,
        )


# Registry mapping proof types to their handler classes
PROOF_HANDLER_REGISTRY = {
    "Filtered Character Set": FilteredCharacterSetHandler,
    "Spacing Proof": SpacingProofHandler,
    "Basic Paragraph Large": BasicParagraphLargeHandler,
    "Diacritic Words Large": DiacriticWordsLargeHandler,
    "Basic Paragraph Small": BasicParagraphSmallHandler,
    "Paired Styles Paragraph Small": PairedStylesParagraphSmallHandler,
    "Generative Text Small": GenerativeTextSmallHandler,
    "Diacritic Words Small": DiacriticWordsSmallHandler,
    "Misc Paragraph Small": MiscParagraphSmallHandler,
    "Ar Character Set": ArCharacterSetHandler,
    "Ar Paragraph Large": ArParagraphLargeHandler,
    "Fa Paragraph Large": FaParagraphLargeHandler,
    "Ar Paragraph Small": ArParagraphSmallHandler,
    "Fa Paragraph Small": FaParagraphSmallHandler,
    "Ar Vocalization Paragraph Small": ArVocalizationParagraphSmallHandler,
    "Ar-Lat Mixed Paragraph Small": ArLatMixedParagraphSmallHandler,
    "Ar Numbers Small": ArNumbersSmallHandler,
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

    # Create new handler if not in cache
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
    return None


def clear_handler_cache():
    """Clear the handler cache. Call when settings change significantly."""
    global _handler_cache
    _handler_cache.clear()
