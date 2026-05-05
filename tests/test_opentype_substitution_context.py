"""Tests for contextual GSUB substitution extraction."""

from types import SimpleNamespace


def test_nested_context_entry_must_match_sequence_index():
    from opentype_substitutions import _nested_entry_matches_context

    context = {
        "backtrack": [],
        "input": ["alef-ar", "beh-ar", "meem-ar"],
        "lookahead": [],
    }

    assert _nested_entry_matches_context(
        {"input_glyphs": ["beh-ar"]},
        context,
        1,
    )
    assert not _nested_entry_matches_context(
        {"input_glyphs": ["f"]},
        context,
        1,
    )


def test_nested_context_entry_can_match_sequence_slice():
    from opentype_substitutions import _nested_entry_matches_context

    context = {
        "backtrack": [],
        "input": ["f", "i", "space"],
        "lookahead": [],
    }

    assert _nested_entry_matches_context(
        {"input_glyphs": ["f", "i"]},
        context,
        0,
    )
    assert not _nested_entry_matches_context(
        {"input_glyphs": ["i", "space"]},
        context,
        0,
    )


def test_extract_context_substitutions_filters_unrelated_nested_mappings():
    from opentype_substitutions import _extract_context_substitutions

    def coverage(*glyphs):
        return SimpleNamespace(glyphs=list(glyphs))

    context_subtable = SimpleNamespace(
        Format=3,
        BacktrackCoverage=[],
        InputCoverage=[coverage("alef-ar"), coverage("beh-ar")],
        LookAheadCoverage=[coverage("meem-ar")],
        SubstLookupRecord=[SimpleNamespace(LookupListIndex=1, SequenceIndex=1)],
    )
    nested_lookup = SimpleNamespace(
        LookupType=1,
        SubTable=[
            SimpleNamespace(
                mapping={
                    "f": "f.alt",
                    "beh-ar": "beh-ar.init",
                }
            )
        ],
    )
    lookup_list = SimpleNamespace(
        Lookup=[
            SimpleNamespace(LookupType=6, SubTable=[context_subtable]),
            nested_lookup,
        ]
    )

    entries = _extract_context_substitutions(
        context_subtable,
        "calt",
        6,
        lookup_list,
        {},
        lookup_index=0,
        depth=0,
    )

    assert len(entries) == 1
    assert entries[0]["input_glyphs"] == ["beh-ar"]
    assert entries[0]["output_glyphs"] == ["beh-ar.init"]
    assert entries[0]["substitution_index"] == 1


def test_format3_context_uses_coverage_for_non_chaining_context():
    from opentype_substitutions import _format3_context

    def coverage(*glyphs):
        return SimpleNamespace(glyphs=list(glyphs))

    subtable = SimpleNamespace(
        Format=3,
        Coverage=[coverage("f"), coverage("i")],
    )

    assert _format3_context(subtable) == {
        "backtrack": [],
        "input": ["f", "i"],
        "lookahead": [],
    }
