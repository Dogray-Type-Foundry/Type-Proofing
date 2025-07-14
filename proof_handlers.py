# Proof Type Handlers - Modular proof generation system

from abc import ABC, abstractmethod
from proof_generation import (
    charsetProof,
    spacingProof,
    textProof,
    arabicContextualFormsProof,
)
from config import arabicVocalization, arabicLatinMixed, arabicFarsiUrduNumbers


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

    def get_font_size(self):
        """Get font size for this proof."""
        return self.get_proof_font_size(self.proof_name)

    def get_tracking_value(self):
        """Get tracking value for this proof."""
        return self.proof_settings.get(f"{self.unique_proof_key}_tracking", 0)

    def get_align_value(self):
        """Get alignment value for this proof."""
        return self.proof_settings.get(f"{self.unique_proof_key}_align", "left")

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
            from importlib import reload
            import prooftexts

            reload(prooftexts)
            import prooftexts as pte
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


def get_proof_handler(proof_type, proof_name, proof_settings, get_proof_font_size_func):
    """Factory function to create the appropriate proof handler.

    Args:
        proof_type: The base proof type (e.g., "Basic Paragraph Large")
        proof_name: The specific proof instance name (may include numbers)
        proof_settings: Dictionary of proof settings
        get_proof_font_size_func: Function to get font size for a proof

    Returns:
        Instance of the appropriate proof handler, or None if not found
    """
    handler_class = PROOF_HANDLER_REGISTRY.get(proof_type)
    if handler_class:
        return handler_class(proof_name, proof_settings, get_proof_font_size_func)
    return None
