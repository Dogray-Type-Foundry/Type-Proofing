"""Tests for preview-specific engine metadata."""

from engine import get_page_format_dimensions, get_proof_registry


def test_registry_exports_preview_cost():
    registry = get_proof_registry()

    assert registry["filtered_character_set"]["preview_cost"] == "fast"
    assert registry["basic_paragraph_small"]["preview_cost"] == "wordsiv"
    assert registry["generative_text_small"]["preview_cost"] == "wordsiv"


def test_page_format_dimensions_export_matches_swift_shape():
    dimensions = get_page_format_dimensions()

    assert dimensions["A4Landscape"] == [842, 595]
    assert dimensions["A4Portrait"] == [595, 842]
