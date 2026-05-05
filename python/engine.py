"""
engine.py — Headless proof generation entry point.

Called from Swift via PythonKit. No UI imports (Vanilla, AppKit, etc.).
Replicates the proof generation logic from app.py without any GUI dependencies.
"""

import datetime
import os
import traceback

import drawBot as db
from config import (
    PROOF_REGISTRY,
    DEFAULT_ON_FEATURES,
    PAGE_FORMAT_OPTIONS,
    get_proof_settings_mapping,
    get_proof_display_names,
    resolve_base_proof_key,
    setup_page_format,
)
from fonts import (
    FontManager,
    filteredCharset,
    categorize,
    variableFont,
    pairStaticStyles,
    product_dict,
    get_font_info,
    check_arabic_support,
    get_ttfont,
)
from settings import Settings, ProofSettingsManager, log_error
from diagnostics import DiagnosticsCollector
from generation_config import GenerationConfig, validate_generation_config
from proof import (
    ProofContext,
    get_proof_handler,
    clear_handler_cache,
    MultiStyleComparisonProofHandler,
    reset_proof_page_counter,
)


# ---------------------------------------------------------------------------
# Lightweight PDF helpers (no AppKit / PDFKit needed)
# ---------------------------------------------------------------------------


def _begin_pdf(page_format, show_baselines=True):
    """Initialize a new DrawBot drawing with the given page format."""
    setup_page_format(page_format)
    reset_proof_page_counter()
    db.showBaselines = show_baselines
    db.newDrawing()


def _end_pdf(output_dir, family_name, now=None):
    """Finalize the DrawBot drawing and save the PDF.

    Returns the absolute path to the saved PDF, or None on failure.
    """
    if now is None:
        now = datetime.datetime.now()

    timestamp = now.strftime("%Y-%m-%d_%H%M")
    filename = f"{timestamp}_{family_name}-proof.pdf"
    pdf_path = os.path.join(output_dir, filename)

    try:
        os.makedirs(output_dir, exist_ok=True)
        db.saveImage(pdf_path)
        db.endDrawing()
        return pdf_path
    except Exception as exc:
        log_error(f"Error saving PDF: {exc}", traceback.format_exc())
        try:
            db.endDrawing()
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Core proof generation
# ---------------------------------------------------------------------------


def _emit_progress(event_callback, **payload):
    if event_callback:
        event_callback({"type": "progress", **payload})


def _diagnose_missing_enabled_features(
    diagnostics,
    proof_name,
    font_path,
    selected_features,
):
    if not selected_features:
        return
    try:
        available = set(db.listOpenTypeFeatures(font_path))
    except Exception:
        return
    missing = sorted(
        tag for tag, enabled in selected_features.items() if enabled and tag not in available
    )
    if missing:
        diagnostics.add(
            "warning",
            "missing_feature",
            f"{len(missing)} enabled OpenType feature(s) are not available in this font.",
            font_path=font_path,
            proof_name=proof_name,
            details={"features": missing},
        )


def _diagnose_custom_text_fallbacks(
    diagnostics,
    proof_name,
    font_path,
    charset,
    handler,
):
    settings_key = getattr(handler, "unique_proof_key", "")
    if not settings_key:
        return
    custom_text = handler.proof_settings.get(f"{settings_key}_customText", "")
    if not custom_text:
        return
    charset_set = set(charset)
    missing = sorted(
        {char for char in custom_text if not char.isspace() and char not in charset_set},
        key=ord,
    )
    if missing:
        diagnostics.add(
            "info",
            "fallback_glyph",
            f"Custom text contains {len(missing)} character(s) missing from this font.",
            font_path=font_path,
            proof_name=proof_name,
            details={"characters": missing[:25]},
        )


def generate_proof(config: dict, event_callback=None) -> str:
    """Generate a proof PDF from a configuration dictionary.

    Args:
        config: dict with keys:
            font_paths          – list[str] of absolute font file paths
            axis_values_by_font – dict[str, dict[str, list]] per-font axis overrides
            proof_options       – list[dict] with keys "Option", "Enabled",
                                  and optional "_original_option"
            proof_settings      – dict of proof-specific settings (font sizes,
                                  columns, tracking, OT features, categories, …)
            page_format         – str (e.g. "A4Landscape")
            output_dir          – str, directory to write the PDF into
                                  (optional; defaults to the first font's dir)

    Returns:
        str – absolute path to the generated PDF, or empty string on failure.
    """
    typed_config = GenerationConfig.from_dict(config)
    diagnostics = DiagnosticsCollector(
        debug=typed_config.debug_mode,
        sink=event_callback,
    )
    try:
        for warning in validate_generation_config(typed_config):
            diagnostics.add("warning", "config", warning)

        font_paths = typed_config.font_paths
        if not font_paths:
            print("Error: No font paths provided")
            diagnostics.add("error", "config", "No font paths provided")
            return {"path": "", "sections": [], "diagnostics": diagnostics.to_list()}

        axis_values_by_font = typed_config.axis_values_by_font
        proof_options = config.get("proof_options", [])
        proof_settings = typed_config.proof_settings.flat
        page_format = typed_config.page_format
        output_dir = typed_config.output_dir
        show_baselines = typed_config.show_baselines

        # Build a minimal Settings + FontManager without touching disk
        settings = Settings.__new__(Settings)
        settings.settings_path = None
        settings.user_settings_file = None
        settings.data = {
            "fonts": {"paths": list(font_paths)},
            "page_format": page_format,
        }
        settings.get_fonts = lambda: list(font_paths)
        settings.get_page_format = lambda: page_format
        settings.get_proof_settings = lambda: dict(proof_settings)
        settings.get_font_axis_values = lambda fp: axis_values_by_font.get(fp, {})

        font_manager = FontManager(settings)
        # Override axis values with those supplied by the caller
        for fp, axes in axis_values_by_font.items():
            font_manager.axis_values_by_font[fp] = axes

        # Build a ProofSettingsManager so handlers can look up sizes, etc.
        psm = ProofSettingsManager(settings, font_manager)
        # Merge caller-supplied proof_settings on top of defaults
        psm.proof_settings.update(proof_settings)

        # Determine output directory
        if not output_dir:
            output_dir = os.path.dirname(os.path.abspath(font_paths[0]))

        now = datetime.datetime.now()
        summary = typed_config.build_summary()
        diagnostics.debug_event("summary", "Proof run summary prepared", details=summary)

        # --- Initialize PDF generation ---
        _begin_pdf(page_format, show_baselines=show_baselines)

        paired_static_styles = pairStaticStyles(font_manager.fonts)

        # Default OT features from first font
        feature_tags = (
            db.listOpenTypeFeatures(font_manager.fonts[0]) if font_manager.fonts else []
        )
        default_otfeatures = {tag: tag in DEFAULT_ON_FEATURES for tag in feature_tags}

        # Reset multi-style dedup so it generates once per PDF run
        MultiStyleComparisonProofHandler.reset_generated()

        # Track which pages belong to which proof section
        sections = []  # list of {"name": str, "first_page": int}

        # --- Loop: proof options → fonts ---
        enabled_options = [item for item in proof_options if item.get("Enabled", False)]
        proof_count = len(enabled_options)
        for proof_index, item in enumerate(enabled_options, 1):
            if not item.get("Enabled", False):
                continue

            proof_name = item.get("Option", "")
            base_proof_type = item.get("_original_option", proof_name)

            # Resolve proof key → display name for get_proof_handler(),
            # which indexes handlers by display name.
            registry_entry = PROOF_REGISTRY.get(base_proof_type)
            if registry_entry:
                base_proof_type = registry_entry["display_name"]

            handler = get_proof_handler(
                base_proof_type,
                proof_name,
                psm.proof_settings,
                psm.get_proof_font_size,
            )
            if not handler:
                print(f"Warning: No handler for '{base_proof_type}'")
                diagnostics.add(
                    "warning",
                    "skipped_proof",
                    f"No handler for '{base_proof_type}'",
                    proof_name=proof_name,
                )
                continue

            page_before = db.pageCount()

            for font_index, ind_font in enumerate(font_manager.fonts, 1):
                _emit_progress(
                    event_callback,
                    proof_name=proof_name,
                    proof_index=proof_index,
                    proof_count=proof_count,
                    font_path=ind_font,
                    font_index=font_index,
                    font_count=len(font_manager.fonts),
                )
                diagnostics.debug_event(
                    "progress",
                    "Starting proof/font combination",
                    font_path=ind_font,
                    proof_name=proof_name,
                    details={
                        "proof_index": proof_index,
                        "proof_count": proof_count,
                        "font_index": font_index,
                        "font_count": len(font_manager.fonts),
                    },
                )
                full_charset = filteredCharset(ind_font)
                cat = categorize(full_charset)
                variable_dict = db.listFontVariations(ind_font)

                # Prefer per-font axes if supplied
                axes_dict = font_manager.get_axis_values_for_font(ind_font)
                if axes_dict:
                    axes_product = list(product_dict(**axes_dict))
                elif not bool(variable_dict):
                    axes_product = ""
                else:
                    axes_product = variableFont(ind_font)[0]

                proof_context = ProofContext(
                    full_character_set=full_charset,
                    axes_product=axes_product,
                    ind_font=ind_font,
                    paired_static_styles=paired_static_styles,
                    otfeatures_by_proof={},
                    cols_by_proof={},
                    paras_by_proof={},
                    cat=cat,
                    proof_name=proof_name,
                    all_fonts=list(font_manager.fonts),
                    font_manager=font_manager,
                )

                try:
                    _diagnose_missing_enabled_features(
                        diagnostics,
                        proof_name,
                        ind_font,
                        handler.get_otfeatures(),
                    )
                    _diagnose_custom_text_fallbacks(
                        diagnostics,
                        proof_name,
                        ind_font,
                        full_charset,
                        handler,
                    )
                    handler.generate_proof(proof_context)
                except Exception as exc:
                    print(f"Error generating proof '{proof_name}': {exc}")
                    traceback.print_exc()
                    diagnostics.add(
                        "error",
                        "generation_error",
                        str(exc),
                        font_path=ind_font,
                        proof_name=proof_name,
                        details={"traceback": traceback.format_exc()},
                    )
                    continue

            page_after = db.pageCount()
            if page_after > page_before:
                sections.append({"name": proof_name, "first_page": page_before})
            else:
                diagnostics.add(
                    "info",
                    "skipped_proof",
                    "Proof produced no pages.",
                    proof_name=proof_name,
                )

        # --- Finalize ---
        family_name = font_manager.get_family_name() or "proof"
        pdf_path = _end_pdf(output_dir, family_name, now)
        elapsed = datetime.datetime.now() - now
        print(f"Proof generated in {elapsed}")
        diagnostics.debug_event(
            "performance",
            "Proof generation finished",
            details={"elapsed_seconds": elapsed.total_seconds()},
        )
        return {
            "path": pdf_path or "",
            "sections": sections,
            "diagnostics": diagnostics.to_list(),
            "summary": summary,
        }

    except Exception as exc:
        log_error(f"generate_proof failed: {exc}", traceback.format_exc())
        diagnostics.add(
            "error",
            "generation_error",
            str(exc),
            details={"traceback": traceback.format_exc()},
        )
        try:
            db.endDrawing()
        except Exception:
            pass
        return {"path": "", "sections": [], "diagnostics": diagnostics.to_list()}


# ---------------------------------------------------------------------------
# Font query helpers (called from Swift UI without a full proof run)
# ---------------------------------------------------------------------------


# ── Font sort property lookup tables ─────────────────────────────────────────
# Keywords matched case-insensitively against font name/subfamily/filename.
# Longer keywords are checked first so "ExtraBold" matches before "Bold".

_WEIGHT_KEYWORDS = [
    ("air", 1),
    ("hairline", 2),
    ("extrathin", 3),
    ("thin", 4),
    ("extralight", 5),
    ("ultralight", 5),
    ("light", 6),
    ("book", 7),
    ("regular", 8),
    ("medium", 9),
    ("semibold", 10),
    ("demibold", 11),
    ("extrabold", 13),
    ("ultrabold", 13),
    ("bold", 12),
    ("heavy", 14),
    ("black", 15),
    ("ultra", 16),
]

_WEIGHT_CLASS_MAP = {
    100: 4,
    200: 5,
    250: 5,
    300: 6,
    350: 7,
    400: 8,
    500: 9,
    600: 10,
    700: 12,
    800: 13,
    900: 15,
    950: 16,
}

_WIDTH_KEYWORDS = [
    ("skyline", 1),
    ("compressed", 2),
    ("extracondensed", 3),
    ("ultracondensed", 3),
    ("condensed", 4),
    ("semicondensed", 5),
    ("compact", 6),
    ("normal", 7),
    ("semiexpanded", 8),
    ("expanded", 9),
    ("wide", 10),
    ("extrawide", 11),
    ("extended", 12),
    ("extraextended", 13),
    ("ultraextended", 14),
    ("extraexpanded", 15),
    ("ultraexpanded", 16),
]

_WIDTH_CLASS_MAP = {
    1: 3,
    2: 3,
    3: 4,
    4: 5,
    5: 7,
    6: 8,
    7: 9,
    8: 15,
    9: 16,
}

_OPTICAL_SIZE_KEYWORDS = [
    ("micro", 1),
    ("caption", 2),
    ("text", 3),
    ("deck", 4),
    ("headline", 5),
    ("display", 6),
    ("banner", 7),
    ("poster", 8),
    ("big", 9),
    ("xs", 1),
    ("xl", 5),
]

_OPTICAL_SIZE_LETTERS = {"s": 2, "m": 3, "l": 4}

_SLANT_KEYWORDS = ["italic", "oblique", "slanted", "ital"]


def _match_keyword(text, keyword_table):
    """Search text for the first matching keyword, return its ordinal or None."""
    lower = text.lower()
    for keyword, ordinal in keyword_table:
        if keyword in lower:
            return ordinal
    return None


def _match_optical_letter(text):
    """Match single-letter optical size tokens (S, M, L) as standalone words."""
    import re

    lower = text.lower()
    for letter, ordinal in _OPTICAL_SIZE_LETTERS.items():
        if re.search(r"(?:^|[\s\-_])" + re.escape(letter) + r"(?:$|[\s\-_])", lower):
            return ordinal
    return None


def _get_font_sort_names(font_path, ttfont):
    """Collect all name strings useful for keyword matching."""
    parts = []
    try:
        name_table = ttfont["name"]
        for name_id in (17, 2, 4, 6):
            rec = name_table.getName(name_id, 3, 1, 0x0409)
            if rec:
                parts.append(str(rec))
    except Exception:
        pass
    parts.append(os.path.splitext(os.path.basename(font_path))[0])
    return " ".join(parts)


def _extract_sort_properties(font_path, font_info):
    """Extract sort values for weight, width, slant, optical_size, family_name.

    Weight and width use a composite: OS/2_value * 100 + name_ordinal.
    OS/2 numeric values (usWeightClass, usWidthClass) are the primary sort
    signal; name-based keyword ordinals only break ties when OS/2 values
    are identical across fonts.
    """
    family_name = ""
    os2_weight = 400  # default usWeightClass (Regular)
    os2_width = 5  # default usWidthClass (Normal)
    name_weight = 8  # Regular ordinal
    name_width = 7  # Normal ordinal
    slant_ord = 0.0
    opsz_ord = 0.0

    try:
        f = get_ttfont(font_path)
        if not f:
            return (
                family_name,
                os2_weight * 100 + name_weight,
                os2_width * 100 + name_width,
                slant_ord,
                opsz_ord,
            )

        family_name = f["name"].getBestFamilyName() or ""
        names_text = _get_font_sort_names(font_path, f)

        # ── OS/2 values (primary sort signal) ──
        if "OS/2" in f:
            os2_weight = f["OS/2"].usWeightClass
            os2_width = f["OS/2"].usWidthClass

        # ── Name-based weight ordinal (tiebreaker) ──
        kw_weight = _match_keyword(names_text, _WEIGHT_KEYWORDS)
        if kw_weight is not None:
            name_weight = kw_weight
        else:
            name_weight = _WEIGHT_CLASS_MAP.get(os2_weight, 8)
            if os2_weight not in _WEIGHT_CLASS_MAP:
                for threshold, ordinal in sorted(_WEIGHT_CLASS_MAP.items()):
                    if os2_weight <= threshold:
                        name_weight = ordinal
                        break

        # ── Name-based width ordinal (tiebreaker) ──
        kw_width = _match_keyword(names_text, _WIDTH_KEYWORDS)
        if kw_width is not None:
            name_width = kw_width
        else:
            name_width = _WIDTH_CLASS_MAP.get(os2_width, 7)

        # ── Slant (binary) ──
        if any(kw in names_text.lower() for kw in _SLANT_KEYWORDS):
            slant_ord = 1.0
        elif "OS/2" in f and (f["OS/2"].fsSelection & 1):
            slant_ord = 1.0
        elif "post" in f and f["post"].italicAngle != 0:
            slant_ord = 1.0

        # ── Optical Size (name-based only, no OS/2 equivalent) ──
        kw_opsz = _match_keyword(names_text, _OPTICAL_SIZE_KEYWORDS)
        if kw_opsz is not None:
            opsz_ord = float(kw_opsz)
        else:
            letter_opsz = _match_optical_letter(names_text)
            if letter_opsz is not None:
                opsz_ord = float(letter_opsz)

        # ── Variable font axis defaults (fallback when OS/2 is absent) ──
        axes = font_info.get("axes", {})
        if axes:
            if "wght" in axes and "OS/2" not in f:
                vals = axes["wght"]
                os2_weight = int(vals[1] if len(vals) > 2 else vals[0])
                if kw_weight is None:
                    name_weight = _WEIGHT_CLASS_MAP.get(os2_weight, 8)
            if "wdth" in axes and "OS/2" not in f:
                vals = axes["wdth"]
                os2_width = int(vals[1] if len(vals) > 2 else vals[0])
                if kw_width is None:
                    name_width = _WIDTH_CLASS_MAP.get(os2_width, 7)
            if "ital" in axes:
                vals = axes["ital"]
                if (vals[1] if len(vals) > 2 else vals[0]) > 0:
                    slant_ord = 1.0
            if "slnt" in axes:
                vals = axes["slnt"]
                if abs(vals[1] if len(vals) > 2 else vals[0]) > 0:
                    slant_ord = 1.0
            if "opsz" in axes and kw_opsz is None:
                vals = axes["opsz"]
                opsz_ord = float(vals[1] if len(vals) > 2 else vals[0])

    except Exception as e:
        log_error(f"Error extracting sort properties for {font_path}: {e}")

    return (
        family_name,
        os2_weight * 100 + name_weight,
        os2_width * 100 + name_width,
        slant_ord,
        opsz_ord,
    )


def get_font_metadata(font_paths):
    """Return metadata for each font path.

    Args:
        font_paths: list of absolute font file paths.

    Returns:
        list of dicts, each with:
            path, name, is_variable, axes (dict tag→[min,default,max]),
            supports_arabic (bool), family_name (str),
            weight (int), width (int), slant (float), optical_size (float)
    """
    results = []
    for fp in font_paths:
        info = get_font_info(fp)
        charset = filteredCharset(fp)

        family_name, weight, width, slant, optical_size = _extract_sort_properties(
            fp, info
        )

        results.append(
            {
                "path": fp,
                "name": info.get("name", os.path.basename(fp)),
                "is_variable": bool(info.get("axes")),
                "axes": info.get("axes", {}),
                "axis_instances": info.get("axis_instances", {}),
                "supports_arabic": check_arabic_support(charset),
                "family_name": family_name,
                "weight": weight,
                "width": width,
                "slant": float(slant),
                "optical_size": float(optical_size),
            }
        )
    return results


def get_font_axes(font_path):
    """Return axis tag → [min, default, max] for a variable font."""
    info = get_font_info(font_path)
    return info.get("axes", {})


def get_charset_categories(font_path):
    """Return character categories for a font."""
    charset = filteredCharset(font_path)
    return categorize(charset)


def get_available_ot_features(font_path):
    """Return list of OpenType feature tags available in the font."""
    return list(db.listOpenTypeFeatures(font_path))


def get_available_substitution_features(font_path):
    """Return visible GSUB substitution feature tags available in the font."""
    from opentype_substitutions import get_substitution_features

    return get_substitution_features(font_path)


def get_font_substitutions(font_path):
    """Return plain GSUB substitution data grouped by feature tag."""
    from opentype_substitutions import get_font_substitutions as _get

    return _get(font_path)


def get_proof_registry():
    """Return the full proof registry dict for the Swift UI to consume.

    Includes a ``display_order`` index so the caller can sort entries in the
    canonical order defined by ``get_proof_display_names``.
    """
    ordered_names = get_proof_display_names(include_arabic=True)
    order_map = {name: i for i, name in enumerate(ordered_names)}
    result = {}
    for key, info in PROOF_REGISTRY.items():
        entry = dict(info)
        entry["display_order"] = order_map.get(info["display_name"], 999)
        result[key] = entry
    return result


def get_page_formats():
    """Return available page format names."""
    return list(PAGE_FORMAT_OPTIONS)


def get_proof_run_summary(config):
    """Return a lightweight summary for the configured proof run."""
    typed_config = GenerationConfig.from_dict(config)
    summary = typed_config.build_summary()
    warnings = list(summary.get("warnings", []))
    warnings.extend(validate_generation_config(typed_config))
    summary["warnings"] = warnings
    return summary


def get_font_styles(font_paths):
    """Return a flat list of font styles (static + VF named instances) for UI consumption.

    Each entry has:
        index (int) — global 0-based index matching the Python proof handler's style indexing
        font_path (str) — path to the font file
        family_name (str) — font family name (used for grouping)
        style_name (str) — style/instance name
        is_variable (bool) — whether this is a VF instance
        coordinates (dict or None) — axis coordinates for VF instances
    """
    results = []
    for font_path in font_paths:
        tt = get_ttfont(font_path)
        if tt and "fvar" in tt:
            name_table = tt["name"]
            family_name = (
                name_table.getBestFamilyName()
                or os.path.splitext(os.path.basename(font_path))[0].split("-")[0]
            )
            family_styles = []
            for inst in tt["fvar"].instances:
                coords = {k: float(v) for k, v in inst.coordinates.items()}
                inst_name = name_table.getName(inst.subfamilyNameID, 3, 1, 0x0409)
                style_name = (
                    str(inst_name)
                    if inst_name
                    else ", ".join(f"{k}:{v}" for k, v in coords.items())
                )
                family_styles.append(
                    {
                        "font_path": font_path,
                        "family_name": family_name,
                        "style_name": style_name,
                        "is_variable": True,
                        "coordinates": coords,
                    }
                )
            # Sort instances alphabetically by style name
            family_styles.sort(key=lambda s: s["style_name"].lower())
            results.extend(family_styles)
        else:
            display_name = os.path.splitext(os.path.basename(font_path))[0]
            # Try to extract family name from filename
            family_name = display_name.split("-")[0]
            style_name = (
                display_name.split("-")[1] if "-" in display_name else "Regular"
            )
            results.append(
                {
                    "font_path": font_path,
                    "family_name": family_name,
                    "style_name": style_name,
                    "is_variable": False,
                    "coordinates": None,
                }
            )
    # Assign sequential indices after sorting
    for i, entry in enumerate(results):
        entry["index"] = i
    return results


def get_default_proof_order(include_arabic=True):
    """Return proof display names in their default order."""
    return get_proof_display_names(include_arabic=include_arabic)
