# Plan: Markdown-like Styling for Custom Text Proof

## Overview

Add a lightweight markup parser to the Custom Text proof that converts user-entered styled text into a drawBot `FormattedString` with per-run formatting. The parser lives in a single new module and is called only from `CustomTextProofHandler`.

## Syntax Specification

```
Block-level (must be the first content on a line):
  # Heading 1         → fontSize = min(baseSize × 2.5, 90)
  ## Heading 2        → fontSize = min(baseSize × 1.8, 90)

Inline:
  **bold text**       → wght:700 (VF) or matched bold font (static), no-op if unavailable
  *italic text*       → ital:1 or slnt:<negative> (VF) or matched italic font (static), no-op if unavailable
  ***bold italic***   → both of the above combined
  [text]{attr: val}   → inline attribute span (see below)

Attribute keys:
  wght: 700           → fontVariations wght
  opsz: 48            → fontVariations opsz
  wdth: 75            → fontVariations wdth
  style: "Bold"       → resolve font file by subfamily or full PostScript name from loaded fonts
  feat: smcp          → openTypeFeatures (single)
  feat: "smcp, onum"  → openTypeFeatures (multiple)
  size: 24            → fontSize override (in points)
  color: #FF0000      → fillColor (hex → RGB tuple)
  tracking: 2         → tracking value (same unit as app stepper: drawBot points)

Escaping:
  \*                  → literal *
  \#                  → literal #
  \[  \]  \{  \}      → literal bracket/brace
  \\                  → literal \

Everything else is rendered as plain paragraph text at the proof's base font size.
Blank lines create paragraph breaks (rendered as \n\n).
```

## Plain Text / Markdown Toggle

A checkbox labeled **"Enable Markup"** in the popover, visible only for Custom Text proofs (not Multi-Style Comparison). Positioned next to the "Custom Text:" label.

**UI change (app.py):**
- Add `popover.markupToggle = vanilla.CheckBox((200, 350, -10, 20), "Enable Markup", callback=self.markupToggleCallback)` — shares the y-position with `customTextLabel`
- Hidden by default; shown only when `proof_has_custom_text(proof_key)` is True **and** `proof_is_multi_style(proof_key)` is False (i.e. only for Custom Text, not Multi-Style Comparison)
- Add `markupToggleCallback` that saves to `proof_settings[make_settings_key(proof_key, "markupEnabled")]`

**Settings (settings.py):**
- In `_apply_settings_for_key()`: for proofs with `has_custom_text`, initialize `markupEnabled` to `False` (default: plain text)

**Handler (proof.py):**
- `CustomTextProofHandler.generate_proof()` reads the `markupEnabled` setting. If `False`, uses the existing plain-text `_render_proof_content()` path. If `True`, calls `parse_custom_text()`.

This means zero behavior change for users who never touch the checkbox.

## Architecture

**One new file:** `markup_parser.py` in the project root.

**Changed files:**
- `proof.py` — `CustomTextProofHandler.generate_proof()` conditionally calls parser
- `app.py` — Add markup toggle checkbox to popover, show/hide logic, callback
- `settings.py` — Initialize `markupEnabled` default for custom text proofs
- `README.md` — Document the syntax

**No changes to:** `config.py`, `ui.py`, `fonts.py`, `pdf_manager.py`.

## Module: `markup_parser.py`

### Public API

```python
def parse_custom_text(
    raw_text: str,
    base_font_size: float,
    base_font: str,
    all_fonts: list[str],
    font_manager: object,
    base_tracking: float,
    base_align: str,
    base_otfeatures: dict,
    base_axis_dict: dict | None,
) -> db.FormattedString:
    """Parse markdown-like text and return a styled FormattedString.
    
    Prints warnings to stdout (debug panel) for malformed syntax.
    On any parse error for a given span, falls back to rendering it unstyled.
    """
```

### Internal Structure

1. **`_tokenize(raw_text) -> list[Token]`**
   - **Escape pass first:** Replace `\\`, `\*`, `\#`, `\[`, `\]`, `\{`, `\}` with unique placeholders (e.g. private-use Unicode chars). Restore them to literal characters in the final output.
   - Splits input into a flat list of tokens. Each token is a dataclass:
     - `Token(kind, text, attrs)` where `kind` is one of: `heading1`, `heading2`, `bold`, `italic`, `bold_italic`, `attr_span`, `plain`, `paragraph_break`
   - Process line by line:
     - Lines starting with `# ` → `heading1` token
     - Lines starting with `## ` → `heading2` token
     - Blank lines → `paragraph_break` token
     - Within a line, use regex to find `***...***`, `**...**`, `*...*`, and `[...]{...}` spans in order, splitting remaining text into `plain` tokens
   - Regex pattern for inline spans (processed left-to-right):
     ```
     \*\*\*(.+?)\*\*\*  |  \*\*(.+?)\*\*  |  \*(.+?)\*  |  \[([^\]]+)\]\{([^}]+)\}
     ```
   - If a `*` or `[` is unclosed within a line, emit the raw text as `plain` and `print()` a warning (goes to debug panel)

2. **`_parse_attrs(attr_string) -> dict`**
   - Parses the `key: value, key: value` string inside `{...}`
   - Splits on `,` then each piece on first `:`
   - Strips whitespace, handles quoted values
   - Special case: `feat: "smcp, onum"` — the quoted value is not split on the inner comma
   - Returns `{"wght": "700", "feat": "smcp, onum", ...}`
   - On malformed attr, prints a warning and returns empty dict

3. **`_resolve_font_by_name(name, all_fonts) -> str | None`**
   - For `style: "Bold Italic"` — iterate loaded font paths:
     - Check `db.font(font_path)` PostScript name (exact match, or endswith `-{name}` with spaces removed)
     - Check fontTools `name.getBestSubFamilyName()` (case-insensitive match)
     - Check full PostScript name (case-insensitive)
   - Return the font path or `None` (prints warning)

4. **`_resolve_bold_font(base_font, all_fonts, font_manager, base_axis_dict) -> dict`**
   - Variable fonts with `wght` axis: return `{"fontVariations": {**base_axis_dict, "wght": 700}}`
   - Static fonts: search loaded fonts for same family with subfamily "Bold" → return `{"font": bold_path}`
   - If neither found: return `{}` (no change)

5. **`_resolve_italic_font(base_font, all_fonts, font_manager, base_axis_dict) -> dict`**
   - Variable fonts with `ital` axis: return `{"fontVariations": {**base_axis_dict, "ital": 1}}`
   - Variable fonts with `slnt` axis: return `{"fontVariations": {**base_axis_dict, "slnt": min_value}}` (min_value from axis range, which is negative)
   - Static fonts: search loaded fonts for same family with subfamily "Italic" → return `{"font": italic_path}`
   - If neither found: return `{}`

6. **`_build_formatted_string(tokens, ...) -> db.FormattedString`**
   - Creates a base `FormattedString` with the proof's default parameters
   - Iterates tokens and calls `.append(txt=..., **overrides)` per token:
     - `heading1`: `fontSize=min(base_font_size * 2.5, 90)` + newline after
     - `heading2`: `fontSize=min(base_font_size * 1.8, 90)` + newline after
     - `bold`: merge `_resolve_bold_font()` overrides
     - `italic`: merge `_resolve_italic_font()` overrides
     - `bold_italic`: merge both bold + italic overrides
     - `attr_span`: build overrides dict from parsed attrs:
       - `wght/opsz/wdth` → `fontVariations={...merged with base...}`
       - `style` → `font=_resolve_font_by_name(...)`
       - `feat` → `openTypeFeatures={feat: True, ...}`
       - `size` → `fontSize=int(val)`
       - `color` → `fillColor=_parse_hex_color(val)`
       - `tracking` → `tracking=float(val)`
     - `plain`: append with no overrides (inherits current defaults)
     - `paragraph_break`: append `\n\n`
   - After each styled token, append a zero-width reset `append(txt="", **base_defaults)` to restore the base style

7. **`_parse_hex_color(hex_str) -> tuple | None`**
   - `#RGB` → expand to 6-digit
   - `#RRGGBB` → `(R/255, G/255, B/255)`
   - Invalid → warning, returns `None`

## Changes to `proof.py`

In `CustomTextProofHandler.generate_proof()`:

```python
markup_key = make_settings_key(self.unique_proof_key, "markupEnabled")
markup_enabled = self.proof_settings.get(markup_key, False)

if markup_enabled:
    from markup_parser import parse_custom_text
    for suffix, axisDict in _normalize_axes(context.axes_product, context.ind_font):
        formatted = parse_custom_text(
            raw_text=custom_text,
            base_font_size=params["font_size"],
            base_font=context.ind_font,
            all_fonts=context.all_fonts or [context.ind_font],
            font_manager=context.font_manager,
            base_tracking=params["tracking_value"],
            base_align=params["align_value"],
            base_otfeatures=params["otfeatures"],
            base_axis_dict=axisDict,
        )
        drawContent(
            formatted,
            f"{params['section_name']} - {suffix}",
            params["columns"],
            context.ind_font,
            "ltr",
            params["otfeatures"],
            params["tracking_value"],
        )
else:
    # Existing plain text path — unchanged
    _render_proof_content(...)
```

## Changes to `app.py`

In `create_proof_settings_popover()`, after the custom text editor:
- Add `popover.markupToggle` checkbox at `(200, 350, -10, 20)`, hidden by default

In `proofTypeSelectionCallback()` and `update_proof_settings_popover_for_instance()`:
- Show `markupToggle` when `proof_has_custom_text(key) and not proof_is_multi_style(key)`
- Load saved value from `proof_settings[make_settings_key(key, "markupEnabled")]`
- Hide for all other proofs

Add `markupToggleCallback(self, sender)`:
- Save `sender.get()` to `proof_settings[make_settings_key(self.current_proof_key, "markupEnabled")]`

## Changes to `settings.py`

In `_apply_settings_for_key()`, in the block that handles `has_custom_text`:
- Also initialize `markupEnabled` key to `False`

## Changes to `README.md`

Add a "Custom Text Markup" subsection documenting the syntax, escaping, and toggle.

## Verification Criteria

1. **Toggle off (default):** plain text renders exactly as before — no regression
2. **Toggle on, no markup:** plain text still renders normally
3. **`# Heading`:** renders at `min(baseSize * 2.5, 90)` on its own line
4. **`## Heading`:** renders at `min(baseSize * 1.8, 90)` on its own line
5. **`**bold**`:** wght:700 (VF) or Bold font (static), or no-op if unavailable
6. **`*italic*`:** ital:1 / slnt:negative (VF) or Italic font (static), or no-op
7. **`***bold italic***`:** both combined
8. **`[text]{wght: 700, size: 24}`:** applies both overrides to that span only
9. **`[text]{style: "Bold"}`:** resolves from loaded fonts by subfamily or PostScript name
10. **`[text]{feat: smcp}`:** enables feature for that span
11. **`[text]{color: #FF0000}`:** renders in red
12. **`\*escaped\*`:** renders as `*escaped*`
13. **Malformed markup:** renders raw text + prints warning to debug panel
14. **After any styled span:** subsequent plain text reverts to base style
15. **Multi-Style Comparison:** custom text NOT affected (no toggle shown, no parser)

## Files Touched

| File | Change |
| --- | --- |
| `markup_parser.py` | **New** — ~250 lines |
| `proof.py` | ~20 lines in `CustomTextProofHandler.generate_proof()` |
| `app.py` | ~15 lines: checkbox widget + show/hide + callback |
| `settings.py` | ~2 lines: `markupEnabled` default |
| `README.md` | ~40 lines documenting syntax |

## What This Plan Does NOT Do

- No changes to `config.py`, `ui.py`, `fonts.py`, `pdf_manager.py`
- No new dependencies
- No effect on any proof type other than Custom Text
- Default behavior unchanged (toggle defaults to off)
