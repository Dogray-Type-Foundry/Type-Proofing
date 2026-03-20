# Markup Parser — Lightweight markdown-like styling for Custom Text proofs

from __future__ import annotations

import re
from dataclasses import dataclass, field

import drawBot as db
from config import FALLBACK_FONT
from fonts import get_ttfont


# =============================================================================
# Escape / Restore
# =============================================================================

_ESCAPE_PAIRS = [
    ("\\\\", "\ue000"),  # Must be first
    ("\\*", "\ue001"),
    ("\\#", "\ue002"),
    ("\\[", "\ue003"),
    ("\\]", "\ue004"),
    ("\\{", "\ue005"),
    ("\\}", "\ue006"),
]

_RESTORE_MAP = {
    "\ue000": "\\",
    "\ue001": "*",
    "\ue002": "#",
    "\ue003": "[",
    "\ue004": "]",
    "\ue005": "{",
    "\ue006": "}",
}


def _escape(text):
    for old, new in _ESCAPE_PAIRS:
        text = text.replace(old, new)
    return text


def _restore(text):
    for placeholder, literal in _RESTORE_MAP.items():
        text = text.replace(placeholder, literal)
    return text


# =============================================================================
# Tokeniser
# =============================================================================


@dataclass
class Token:
    kind: str  # heading1, heading2, bold, italic, bold_italic, attr_span, plain
    text: str = ""
    attrs: dict = field(default_factory=dict)


_INLINE_RE = re.compile(
    r"\*\*\*(.+?)\*\*\*" r"|\*\*(.+?)\*\*" r"|\*(.+?)\*" r"|\[([^\]]+)\]\{([^}]+)\}"
)


def _tokenize(raw_text):
    escaped = _escape(raw_text)
    lines = escaped.split("\n")
    tokens = []

    for i, line in enumerate(lines):
        if line.strip() == "":
            pass  # blank line — surrounding \n tokens form paragraph breaks
        elif line.startswith("## "):
            tokens.append(Token(kind="heading2", text=_restore(line[3:])))
        elif line.startswith("# "):
            tokens.append(Token(kind="heading1", text=_restore(line[2:])))
        else:
            _tokenize_inline(line, tokens)

        # Preserve newlines between lines (except after the last line)
        if i < len(lines) - 1:
            tokens.append(Token(kind="plain", text="\n"))

    return tokens


def _tokenize_inline(line, tokens):
    last_end = 0
    for m in _INLINE_RE.finditer(line):
        if m.start() > last_end:
            tokens.append(
                Token(kind="plain", text=_restore(line[last_end : m.start()]))
            )

        if m.group(1) is not None:
            tokens.append(Token(kind="bold_italic", text=_restore(m.group(1))))
        elif m.group(2) is not None:
            tokens.append(Token(kind="bold", text=_restore(m.group(2))))
        elif m.group(3) is not None:
            tokens.append(Token(kind="italic", text=_restore(m.group(3))))
        elif m.group(4) is not None:
            attrs = _parse_attrs(m.group(5))
            tokens.append(
                Token(kind="attr_span", text=_restore(m.group(4)), attrs=attrs)
            )

        last_end = m.end()

    if last_end < len(line):
        tokens.append(Token(kind="plain", text=_restore(line[last_end:])))


# =============================================================================
# Attribute Parsing
# =============================================================================


def _parse_attrs(attr_string):
    attr_string = _restore(attr_string)
    result = {}

    # Split on commas that are outside quotes
    parts = []
    current = []
    in_quotes = False
    for ch in attr_string:
        if ch == '"' and not in_quotes:
            in_quotes = True
            current.append(ch)
        elif ch == '"' and in_quotes:
            in_quotes = False
            current.append(ch)
        elif ch == "," and not in_quotes:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())

    for part in parts:
        if ":" not in part:
            print(f"Markup warning: malformed attribute '{part}', skipping")
            continue
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        result[key] = value

    return result


def _parse_hex_color(hex_str):
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        print(f"Markup warning: invalid hex color '#{hex_str}'")
        return None
    try:
        r = int(hex_str[0:2], 16) / 255
        g = int(hex_str[2:4], 16) / 255
        b = int(hex_str[4:6], 16) / 255
        return (r, g, b)
    except ValueError:
        print(f"Markup warning: invalid hex color '#{hex_str}'")
        return None


# =============================================================================
# Font Resolution
# =============================================================================


def _find_style_variant(base_font, all_fonts, target_subfamily):
    base_tt = get_ttfont(base_font)
    if base_tt is None:
        return None
    base_family = base_tt["name"].getBestFamilyName()

    for font_path in all_fonts:
        if font_path == base_font:
            continue
        tt = get_ttfont(font_path)
        if tt is None:
            continue
        if tt["name"].getBestFamilyName() == base_family:
            if tt["name"].getBestSubFamilyName() == target_subfamily:
                return font_path
    return None


def _resolve_font_by_name(name, all_fonts):
    name_cleaned = name.strip().strip('"').strip("'")

    for font_path in all_fonts:
        tt = get_ttfont(font_path)
        if tt is None:
            continue
        subfamily = tt["name"].getBestSubFamilyName()
        if subfamily and subfamily.lower() == name_cleaned.lower():
            return font_path
        # Check PostScript name
        try:
            ps_name = db.font(font_path)
            if ps_name and (
                ps_name.lower() == name_cleaned.lower()
                or ps_name.lower().endswith(f"-{name_cleaned.replace(' ', '').lower()}")
            ):
                return font_path
        except Exception:
            pass

    print(f"Markup warning: could not resolve font style '{name}'")
    return None


def _resolve_bold_font(base_font, all_fonts, font_manager, base_axis_dict):
    variations = db.listFontVariations(base_font)
    if "wght" in variations:
        merged = dict(base_axis_dict) if base_axis_dict else {}
        merged["wght"] = 700
        return {"fontVariations": merged}

    bold_path = _find_style_variant(base_font, all_fonts, "Bold")
    if bold_path:
        return {"font": bold_path}
    return {}


def _resolve_italic_font(base_font, all_fonts, font_manager, base_axis_dict):
    variations = db.listFontVariations(base_font)
    if "ital" in variations:
        merged = dict(base_axis_dict) if base_axis_dict else {}
        merged["ital"] = 1
        return {"fontVariations": merged}
    if "slnt" in variations:
        merged = dict(base_axis_dict) if base_axis_dict else {}
        merged["slnt"] = variations["slnt"]["minValue"]
        return {"fontVariations": merged}

    italic_path = _find_style_variant(base_font, all_fonts, "Italic")
    if italic_path:
        return {"font": italic_path}
    return {}


def _merge_overrides(*override_dicts):
    result = {}
    merged_variations = None
    for d in override_dicts:
        if "fontVariations" in d:
            if merged_variations is None:
                merged_variations = dict(d["fontVariations"])
            else:
                merged_variations.update(d["fontVariations"])
        for k, v in d.items():
            if k != "fontVariations":
                result[k] = v
    if merged_variations is not None:
        result["fontVariations"] = merged_variations
    return result


def _resolve_bold_italic_font(base_font, all_fonts, font_manager, base_axis_dict):
    bold = _resolve_bold_font(base_font, all_fonts, font_manager, base_axis_dict)
    italic = _resolve_italic_font(base_font, all_fonts, font_manager, base_axis_dict)

    # Static fonts: both return {"font": ...} — look for Bold Italic specifically
    if "font" in bold and "font" in italic:
        bi_path = _find_style_variant(base_font, all_fonts, "Bold Italic")
        if bi_path:
            return {"font": bi_path}
        return bold  # fallback to bold only

    return _merge_overrides(bold, italic)


# =============================================================================
# Attribute Override Builder
# =============================================================================


def _build_attr_overrides(attrs, base_font, all_fonts, base_axis_dict, base_otfeatures):
    overrides = {}
    variations = dict(base_axis_dict) if base_axis_dict else {}
    has_variations = False

    for key, value in attrs.items():
        if key in ("wght", "opsz", "wdth"):
            try:
                variations[key] = float(value)
                has_variations = True
            except ValueError:
                print(f"Markup warning: invalid numeric value for {key}: {value}")
        elif key == "style":
            font_path = _resolve_font_by_name(value, all_fonts)
            if font_path:
                overrides["font"] = font_path
        elif key == "feat":
            features = dict(base_otfeatures) if base_otfeatures else {}
            for feat_tag in value.split(","):
                feat_tag = feat_tag.strip()
                if feat_tag:
                    features[feat_tag] = True
            overrides["openTypeFeatures"] = features
        elif key == "size":
            try:
                overrides["fontSize"] = float(value)
            except ValueError:
                print(f"Markup warning: invalid size value: {value}")
        elif key == "color":
            color = _parse_hex_color(value)
            if color:
                overrides["fill"] = color
        elif key == "tracking":
            try:
                overrides["tracking"] = float(value)
            except ValueError:
                print(f"Markup warning: invalid tracking value: {value}")
        else:
            print(f"Markup warning: unknown attribute '{key}', skipping")

    if has_variations:
        overrides["fontVariations"] = variations

    return overrides


# =============================================================================
# FormattedString Builder
# =============================================================================


def _build_formatted_string(
    tokens,
    base_font_size,
    base_font,
    all_fonts,
    font_manager,
    base_tracking,
    base_align,
    base_otfeatures,
    base_axis_dict,
):
    base_kwargs = {
        "font": base_font,
        "fallbackFont": FALLBACK_FONT,
        "fontSize": base_font_size,
        "align": base_align,
        "tracking": base_tracking,
        "openTypeFeatures": base_otfeatures,
    }
    if base_axis_dict:
        base_kwargs["fontVariations"] = base_axis_dict

    fs = db.FormattedString(txt="", **base_kwargs)

    for token in tokens:
        try:
            if token.kind == "plain":
                fs.append(txt=token.text, **base_kwargs)

            elif token.kind in ("heading1", "heading2"):
                multiplier = 2.5 if token.kind == "heading1" else 1.8
                h_kwargs = dict(base_kwargs)
                h_kwargs["fontSize"] = min(base_font_size * multiplier, 90)
                fs.append(txt=token.text, **h_kwargs)

            elif token.kind == "bold":
                b_kwargs = dict(base_kwargs)
                b_kwargs.update(
                    _resolve_bold_font(
                        base_font, all_fonts, font_manager, base_axis_dict
                    )
                )
                fs.append(txt=token.text, **b_kwargs)

            elif token.kind == "italic":
                i_kwargs = dict(base_kwargs)
                i_kwargs.update(
                    _resolve_italic_font(
                        base_font, all_fonts, font_manager, base_axis_dict
                    )
                )
                fs.append(txt=token.text, **i_kwargs)

            elif token.kind == "bold_italic":
                bi_kwargs = dict(base_kwargs)
                bi_kwargs.update(
                    _resolve_bold_italic_font(
                        base_font, all_fonts, font_manager, base_axis_dict
                    )
                )
                fs.append(txt=token.text, **bi_kwargs)

            elif token.kind == "attr_span":
                a_kwargs = dict(base_kwargs)
                a_kwargs.update(
                    _build_attr_overrides(
                        token.attrs,
                        base_font,
                        all_fonts,
                        base_axis_dict,
                        base_otfeatures,
                    )
                )
                fs.append(txt=token.text, **a_kwargs)

        except Exception as e:
            print(f"Markup warning: error processing '{token.text}': {e}")
            fs.append(txt=token.text, **base_kwargs)

    return fs


# =============================================================================
# Public API
# =============================================================================


def parse_custom_text(
    raw_text,
    base_font_size,
    base_font,
    all_fonts,
    font_manager,
    base_tracking,
    base_align,
    base_otfeatures,
    base_axis_dict,
):
    """Parse markdown-like text and return a styled FormattedString.

    Prints warnings to stdout (debug panel) for malformed syntax.
    On any parse error for a given span, falls back to rendering it unstyled.
    """
    try:
        tokens = _tokenize(raw_text)
        return _build_formatted_string(
            tokens,
            base_font_size,
            base_font,
            all_fonts,
            font_manager,
            base_tracking,
            base_align,
            base_otfeatures,
            base_axis_dict,
        )
    except Exception as e:
        print(f"Markup error: {e}, falling back to plain text")
        kwargs = {
            "font": base_font,
            "fallbackFont": FALLBACK_FONT,
            "fontSize": base_font_size,
            "align": base_align,
            "tracking": base_tracking,
            "openTypeFeatures": base_otfeatures,
        }
        if base_axis_dict:
            kwargs["fontVariations"] = base_axis_dict
        return db.FormattedString(txt=raw_text, **kwargs)
