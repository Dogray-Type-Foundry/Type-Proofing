# Proof Type Handlers - Modular proof generation system

from abc import ABC, abstractmethod
from proof_generation import (
    charsetProof,
    spacingProof,
    textProof,
    arabicContextualFormsProof,
)
from script_texts import arabicVocalization, arabicLatinMixed, arabicFarsiUrduNumbers

try:
    from sample_texts import bigRandomNumbers, additionalSmallText
except ImportError:
    bigRandomNumbers = ""
    additionalSmallText = ""


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

    # Configuration mapping for different proof types
    PROOF_CONFIGS = {
        "basic_paragraph_large": {
            "character_set_key": "base_letters",
            "default_columns": 1,
            "default_paragraphs": 2,
        },
        "diacritic_words_large": {
            "character_set_key": "accented_plus",
            "default_columns": 1,
            "default_paragraphs": 3,
            "accents": 3,
        },
        "basic_paragraph_small": {
            "character_set_key": "base_letters",
            "default_columns": 2,
            "default_paragraphs": 5,
        },
        "paired_styles_paragraph_small": {
            "character_set_key": "base_letters",
            "default_columns": 2,
            "default_paragraphs": 5,
            "mixed_styles": True,
            "force_wordsiv": True,
        },
        "generative_text_small": {
            "character_set_key": "base_letters",
            "default_columns": 2,
            "default_paragraphs": 5,
            "force_wordsiv": True,
        },
        "diacritic_words_small": {
            "character_set_key": "accented_plus",
            "default_columns": 2,
            "default_paragraphs": 5,
            "accents": 3,
        },
        "misc_paragraph_small": {
            "character_set_key": "base_letters",
            "default_columns": 2,
            "default_paragraphs": 5,
            "inject_text": (bigRandomNumbers, additionalSmallText),
        },
        "ar_paragraph_large": {
            "character_set_key": "arabic",
            "default_columns": 1,
            "default_paragraphs": 2,
            "language": "ar",
        },
        "fa_paragraph_large": {
            "character_set_key": "farsi",
            "default_columns": 1,
            "default_paragraphs": 2,
            "language": "fa",
        },
        "ar_paragraph_small": {
            "character_set_key": "arabic",
            "default_columns": 2,
            "default_paragraphs": 5,
            "language": "ar",
        },
        "fa_paragraph_small": {
            "character_set_key": "farsi",
            "default_columns": 2,
            "default_paragraphs": 5,
            "language": "fa",
        },
        "ar_latin_mixed": {
            "character_set_key": "arabic",
            "default_columns": 2,
            "default_paragraphs": 5,
            "inject_text": arabicLatinMixed,
            "language": "ar",
        },
        "ar_farsi_urdu_numbers": {
            "character_set_key": "arabic",
            "default_columns": 2,
            "default_paragraphs": 5,
            "inject_text": arabicFarsiUrduNumbers,
            "language": "ar",
        },
        "ar_vocalization": {
            "character_set_key": "arabic",
            "default_columns": 2,
            "default_paragraphs": 5,
            "inject_text": arabicVocalization,
            "language": "ar",
        },
    }

    def __init__(
        self, proof_name, proof_settings, get_proof_font_size_func, proof_key=None
    ):
        super().__init__(proof_name, proof_settings, get_proof_font_size_func)

        # If proof_key is provided, use configuration from PROOF_CONFIGS
        if proof_key and proof_key in self.PROOF_CONFIGS:
            config = self.PROOF_CONFIGS[proof_key]
            self.character_set_key = config["character_set_key"]
            self.default_columns = config.get("default_columns", 2)
            self.default_paragraphs = config.get("default_paragraphs", 5)
            self.mixed_styles = config.get("mixed_styles", False)
            self.force_wordsiv = config.get("force_wordsiv", False)
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
        """Get character set based on the key."""
        if self.character_set_key == "base_letters":
            return context.cat["uniLu"] + context.cat["uniLl"]
        elif self.character_set_key == "accented_plus":
            return context.cat["accented_plus"]
        elif self.character_set_key == "arabic":
            return context.cat.get("ar", "") or context.cat.get("arab", "")
        elif self.character_set_key == "farsi":
            return context.cat.get("fa", "") or context.cat.get("arab", "")
        else:
            return context.cat.get(self.character_set_key, "")

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


class CategoryBasedProofHandler(BaseProofHandler):
    """Base handler for proofs that use character categories."""

    def get_character_category_setting(self, category):
        """Get character category setting value with appropriate defaults."""
        key = f"{self.unique_proof_key}_cat_{category}"
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
        from character_analysis import get_charset_proof_categories

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
    from proof_config import PROOF_REGISTRY

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
