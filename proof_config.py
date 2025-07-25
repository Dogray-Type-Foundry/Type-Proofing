# Proof Configuration - Proof type definitions and registry

# =============================================================================
# CENTRALIZED PROOF REGISTRY - Single Source of Truth
# =============================================================================

# Single source of truth for all proof definitions
PROOF_REGISTRY = {
    "filtered_character_set": {
        "display_name": "Filtered Character Set",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 78,  # charsetFontSize
    },
    "spacing_proof": {
        "display_name": "Spacing Proof",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 14,  # spacingFontSize
    },
    "basic_paragraph_large": {
        "display_name": "Basic Paragraph Large",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
    },
    "diacritic_words_large": {
        "display_name": "Diacritic Words Large",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
    },
    "basic_paragraph_small": {
        "display_name": "Basic Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "paired_styles_paragraph_small": {
        "display_name": "Paired Styles Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "generative_text_small": {
        "display_name": "Generative Text Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": True,
        "default_size": 10,  # smallTextFontSize
    },
    "diacritic_words_small": {
        "display_name": "Diacritic Words Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "misc_paragraph_small": {
        "display_name": "Misc Paragraph Small",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "ar_character_set": {
        "display_name": "Ar Character Set",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 78,  # charsetFontSize
    },
    "ar_paragraph_large": {
        "display_name": "Ar Paragraph Large",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
    },
    "fa_paragraph_large": {
        "display_name": "Fa Paragraph Large",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 1,
        "has_paragraphs": False,
        "default_size": 28,  # largeTextFontSize
    },
    "ar_paragraph_small": {
        "display_name": "Ar Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "fa_paragraph_small": {
        "display_name": "Fa Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "ar_vocalization_paragraph_small": {
        "display_name": "Ar Vocalization Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "ar_lat_mixed_paragraph_small": {
        "display_name": "Ar-Lat Mixed Paragraph Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
    "ar_numbers_small": {
        "display_name": "Ar Numbers Small",
        "is_arabic": True,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 10,  # smallTextFontSize
    },
}

# =============================================================================
# PROOF REGISTRY HELPER FUNCTIONS
# =============================================================================


def get_proof_display_names(include_arabic=True):
    """Get list of proof display names in default order."""
    proof_order = [
        "filtered_character_set",
        "spacing_proof",
        "basic_paragraph_large",
        "diacritic_words_large",
        "basic_paragraph_small",
        "paired_styles_paragraph_small",
        "generative_text_small",
        "diacritic_words_small",
        "misc_paragraph_small",
        "ar_character_set",
        "ar_paragraph_large",
        "fa_paragraph_large",
        "ar_paragraph_small",
        "fa_paragraph_small",
        "ar_vocalization_paragraph_small",
        "ar_lat_mixed_paragraph_small",
        "ar_numbers_small",
    ]

    result = []
    for proof_key in proof_order:
        if proof_key in PROOF_REGISTRY:
            proof_info = PROOF_REGISTRY[proof_key]
            if include_arabic or not proof_info["is_arabic"]:
                result.append(proof_info["display_name"])

    return result


def get_proof_settings_mapping():
    """Get mapping from display names to proof keys."""
    return {
        proof_info["display_name"]: proof_key
        for proof_key, proof_info in PROOF_REGISTRY.items()
    }


def get_proof_popover_mapping():
    """Get mapping from display names to proof keys (for popover compatibility)."""
    return get_proof_settings_mapping()


def get_proof_storage_mapping():
    """Get mapping from proof keys to storage keys (now the same)."""
    return {proof_key: proof_key for proof_key in PROOF_REGISTRY.keys()}


def get_proof_default_columns():
    """Get default column counts for all proofs."""
    return {
        f"{proof_key}_cols": proof_info["default_cols"]
        for proof_key, proof_info in PROOF_REGISTRY.items()
    }


def get_proof_paragraph_settings():
    """Get proof types that have paragraph settings."""
    return {
        f"{proof_key}_para": 3  # Default paragraph count
        for proof_key, proof_info in PROOF_REGISTRY.items()
        if proof_info["has_paragraphs"]
    }


def get_proof_by_display_name(display_name):
    """Get proof info by display name."""
    for proof_key, proof_info in PROOF_REGISTRY.items():
        if proof_info["display_name"] == display_name:
            return proof_info
    return None


def get_proof_by_settings_key(settings_key):
    """Get proof info by settings key (now same as proof key)."""
    return PROOF_REGISTRY.get(settings_key)


def get_proof_by_storage_key(storage_key):
    """Get proof info by storage key (now same as proof key)."""
    return PROOF_REGISTRY.get(storage_key)


def get_arabic_proof_display_names():
    """Get list of Arabic proof display names only."""
    return [
        proof_info["display_name"]
        for proof_info in PROOF_REGISTRY.values()
        if proof_info["is_arabic"]
    ]


def get_base_proof_display_names():
    """Get list of non-Arabic proof display names only."""
    return [
        proof_info["display_name"]
        for proof_info in PROOF_REGISTRY.values()
        if not proof_info["is_arabic"]
    ]


def get_proof_default_font_size(proof_key):
    """Get default font size for a proof type from the registry."""
    proof_info = PROOF_REGISTRY.get(proof_key)
    if proof_info:
        return proof_info["default_size"]
    return 8  # Fallback to small text size


def proof_supports_formatting(proof_key):
    """Check if a proof type supports text formatting (tracking, alignment)."""
    # Character Set, Spacing Proof, and Arabic Character Set don't support formatting (they handle it per category)
    return proof_key not in [
        "filtered_character_set",
        "spacing_proof",
        "ar_character_set",
    ]


def get_proof_info(proof_key):
    """Get proof info by proof key (alias for backward compatibility)."""
    return PROOF_REGISTRY.get(proof_key)


def get_display_name(proof_key):
    """Get display name for a proof key (alias for backward compatibility)."""
    proof_info = PROOF_REGISTRY.get(proof_key)
    return proof_info["display_name"] if proof_info else proof_key


def get_otf_prefix(proof_key):
    """Get OpenType feature prefix for a proof key."""
    return f"otf_{proof_key}_"
