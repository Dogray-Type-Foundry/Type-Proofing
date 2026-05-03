"""Extract OpenType GSUB substitutions as plain Python data."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from fontTools.ttLib import TTFont

from config import HIDDEN_FEATURES
from fonts import get_ttfont


SKIPPED_FEATURES = HIDDEN_FEATURES | {"aalt"}


def get_substitution_features(font_path: str) -> list[str]:
    """Return visible GSUB feature tags that produce output glyphs."""
    data = get_font_substitutions(font_path)
    return [feature["feature_tag"] for feature in data]


def get_font_substitutions(font_path: str) -> list[dict[str, Any]]:
    """Return GSUB substitutions grouped by feature tag.

    The payload deliberately contains only strings, lists, numbers, and
    booleans so it is safe to pass through PythonKit and into DrawBot code.
    """
    try:
        mtime = os.path.getmtime(font_path)
    except Exception:
        mtime = 0
    return _cached_font_substitutions(font_path, mtime)


@lru_cache(maxsize=16)
def _cached_font_substitutions(font_path: str, mtime: float) -> list[dict[str, Any]]:
    tt = get_ttfont(font_path)
    if not tt or "GSUB" not in tt:
        return []

    glyph_to_char = _build_glyph_to_char(tt)
    gsub = tt["GSUB"].table
    feature_list = getattr(gsub, "FeatureList", None)
    lookup_list = getattr(gsub, "LookupList", None)
    if not feature_list or not lookup_list:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for feature_record in feature_list.FeatureRecord:
        tag = feature_record.FeatureTag
        if tag in SKIPPED_FEATURES:
            continue
        entries = grouped.setdefault(tag, [])
        for lookup_index in feature_record.Feature.LookupListIndex:
            lookup = lookup_list.Lookup[lookup_index]
            entries.extend(
                _extract_lookup_entries(
                    lookup,
                    tag,
                    lookup_list,
                    glyph_to_char,
                    source_lookup_index=lookup_index,
                )
            )

    result = []
    for tag in sorted(grouped):
        entries = _dedupe_entries(grouped[tag])
        output_glyphs = sorted(
            {
                glyph
                for entry in entries
                for glyph in entry.get("output_glyphs", [])
                if glyph
            }
        )
        if not output_glyphs:
            continue
        result.append(
            {
                "feature_tag": tag,
                "label": tag,
                "output_glyphs": output_glyphs,
                "entries": entries,
            }
        )
    return result


def _extract_lookup_entries(
    lookup,
    feature_tag: str,
    lookup_list,
    glyph_to_char: dict[str, str],
    source_lookup_index: int,
    depth: int = 0,
) -> list[dict[str, Any]]:
    if depth > 3:
        return []

    lookup_type = lookup.LookupType
    entries: list[dict[str, Any]] = []
    for subtable in lookup.SubTable:
        if lookup_type == 1:
            entries.extend(
                _extract_single_substitutions(
                    subtable, feature_tag, lookup_type, source_lookup_index, glyph_to_char
                )
            )
        elif lookup_type == 4:
            entries.extend(
                _extract_ligature_substitutions(
                    subtable, feature_tag, lookup_type, source_lookup_index, glyph_to_char
                )
            )
        elif lookup_type in (5, 6):
            entries.extend(
                _extract_context_substitutions(
                    subtable,
                    feature_tag,
                    lookup_type,
                    lookup_list,
                    glyph_to_char,
                    source_lookup_index,
                    depth,
                )
            )
    return entries


def _extract_single_substitutions(
    subtable,
    feature_tag: str,
    lookup_type: int,
    lookup_index: int,
    glyph_to_char: dict[str, str],
) -> list[dict[str, Any]]:
    mapping = getattr(subtable, "mapping", None)
    if not mapping:
        return []
    entries = []
    for input_glyph, output_glyph in mapping.items():
        entries.append(
            _entry(
                feature_tag,
                lookup_type,
                "single",
                [input_glyph],
                [output_glyph],
                lookup_index,
                glyph_to_char,
            )
        )
    return entries


def _extract_ligature_substitutions(
    subtable,
    feature_tag: str,
    lookup_type: int,
    lookup_index: int,
    glyph_to_char: dict[str, str],
) -> list[dict[str, Any]]:
    ligatures = getattr(subtable, "ligatures", None)
    if not ligatures:
        return []
    entries = []
    for first_glyph, ligature_records in ligatures.items():
        for ligature in ligature_records:
            input_glyphs = [first_glyph] + list(ligature.Component)
            entries.append(
                _entry(
                    feature_tag,
                    lookup_type,
                    "ligature",
                    input_glyphs,
                    [ligature.LigGlyph],
                    lookup_index,
                    glyph_to_char,
                )
            )
    return entries


def _extract_context_substitutions(
    subtable,
    feature_tag: str,
    lookup_type: int,
    lookup_list,
    glyph_to_char: dict[str, str],
    lookup_index: int,
    depth: int,
) -> list[dict[str, Any]]:
    records = getattr(subtable, "SubstLookupRecord", None)
    if not records:
        return []

    entries = []
    context = _format3_context(subtable)
    for record in records:
        if record.LookupListIndex == lookup_index:
            continue
        nested_lookup = lookup_list.Lookup[record.LookupListIndex]
        nested_entries = _extract_lookup_entries(
            nested_lookup,
            feature_tag,
            lookup_list,
            glyph_to_char,
            source_lookup_index=record.LookupListIndex,
            depth=depth + 1,
        )
        for nested in nested_entries:
            nested = dict(nested)
            nested["kind"] = f"contextual_{nested['kind']}"
            nested["lookup_type"] = lookup_type
            nested["context_glyphs"] = context
            nested["substitution_index"] = getattr(record, "SequenceIndex", 0)
            nested["overview_eligible"] = bool(context and nested.get("output_glyphs"))
            entries.append(nested)
    return entries


def _format3_context(subtable) -> dict[str, list[str]]:
    """Return context only for format 3 coverage-based subtables."""
    if getattr(subtable, "Format", None) != 3:
        return {}

    def first_glyphs(coverages):
        result = []
        for coverage in coverages or []:
            glyphs = list(getattr(coverage, "glyphs", []) or [])
            if len(glyphs) != 1:
                return []
            result.append(glyphs[0])
        return result

    return {
        "backtrack": first_glyphs(getattr(subtable, "BacktrackCoverage", [])),
        "input": first_glyphs(getattr(subtable, "InputCoverage", [])),
        "lookahead": first_glyphs(getattr(subtable, "LookAheadCoverage", [])),
    }


def _entry(
    feature_tag: str,
    lookup_type: int,
    kind: str,
    input_glyphs: list[str],
    output_glyphs: list[str],
    lookup_index: int,
    glyph_to_char: dict[str, str],
) -> dict[str, Any]:
    input_text = "".join(glyph_to_char.get(glyph, "") for glyph in input_glyphs)
    return {
        "feature_tag": feature_tag,
        "lookup_type": lookup_type,
        "lookup_index": lookup_index,
        "kind": kind,
        "input_glyphs": list(input_glyphs),
        "output_glyphs": list(output_glyphs),
        "input_text": input_text,
        "label": f"{feature_tag}: {' '.join(output_glyphs)}",
        "category_eligible": bool(output_glyphs),
        "overview_eligible": bool(input_text),
    }


def _build_glyph_to_char(tt: TTFont) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        cmap = tt.getBestCmap() or {}
    except Exception:
        cmap = {}
    for codepoint, glyph_name in cmap.items():
        result.setdefault(glyph_name, chr(codepoint))
    return result


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for entry in entries:
        key = (
            entry.get("feature_tag"),
            entry.get("kind"),
            tuple(entry.get("input_glyphs", [])),
            tuple(entry.get("output_glyphs", [])),
            repr(entry.get("context_glyphs", {})),
            entry.get("substitution_index"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result
