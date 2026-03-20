"""Tests for markup_parser.py — tokenizer, attribute parsing, and escape/restore."""

import pytest
from markup_parser import (
    _escape,
    _restore,
    _tokenize,
    _parse_attrs,
    _parse_hex_color,
    Token,
)


# =============================================================================
# _escape / _restore
# =============================================================================


class TestEscapeRestore:
    def test_escape_backslash(self):
        result = _escape("hello\\\\world")
        assert "\\" not in result or "\ue000" in result

    def test_escape_star(self):
        result = _escape("hello\\*world")
        assert "\\*" not in result

    def test_escape_hash(self):
        result = _escape("hello\\#world")
        assert "\\#" not in result

    def test_escape_brackets(self):
        result = _escape("\\[text\\]")
        assert "\\[" not in result
        assert "\\]" not in result

    def test_restore_undoes_escape(self):
        """Escape then restore should return original text."""
        original = "Normal text without escapes"
        assert _restore(_escape(original)) == original

    def test_restore_backslash(self):
        escaped = _escape("test\\\\end")
        restored = _restore(escaped)
        assert restored == "test\\end"

    def test_restore_star(self):
        escaped = _escape("test\\*end")
        restored = _restore(escaped)
        assert restored == "test*end"

    def test_round_trip_all_escapes(self):
        original = "\\\\\\*\\#\\[\\]\\{\\}"
        result = _restore(_escape(original))
        assert result == "\\*#[]{}"


# =============================================================================
# Token dataclass
# =============================================================================


class TestToken:
    def test_creation(self):
        t = Token(kind="plain", text="hello")
        assert t.kind == "plain"
        assert t.text == "hello"
        assert t.attrs == {}

    def test_with_attrs(self):
        t = Token(kind="attr_span", text="styled", attrs={"size": "24"})
        assert t.attrs == {"size": "24"}


# =============================================================================
# _tokenize
# =============================================================================


class TestTokenize:
    def test_plain_text(self):
        tokens = _tokenize("Hello world")
        plain_tokens = [t for t in tokens if t.kind == "plain" and t.text.strip()]
        assert any("Hello world" in t.text for t in plain_tokens)

    def test_heading1(self):
        tokens = _tokenize("# My Heading")
        headings = [t for t in tokens if t.kind == "heading1"]
        assert len(headings) == 1
        assert headings[0].text == "My Heading"

    def test_heading2(self):
        tokens = _tokenize("## Sub Heading")
        headings = [t for t in tokens if t.kind == "heading2"]
        assert len(headings) == 1
        assert headings[0].text == "Sub Heading"

    def test_bold(self):
        tokens = _tokenize("This is **bold** text")
        bold_tokens = [t for t in tokens if t.kind == "bold"]
        assert len(bold_tokens) == 1
        assert bold_tokens[0].text == "bold"

    def test_italic(self):
        tokens = _tokenize("This is *italic* text")
        italic_tokens = [t for t in tokens if t.kind == "italic"]
        assert len(italic_tokens) == 1
        assert italic_tokens[0].text == "italic"

    def test_bold_italic(self):
        tokens = _tokenize("This is ***bold italic*** text")
        bi_tokens = [t for t in tokens if t.kind == "bold_italic"]
        assert len(bi_tokens) == 1
        assert bi_tokens[0].text == "bold italic"

    def test_attr_span(self):
        tokens = _tokenize("[styled text]{size: 24, color: #FF0000}")
        attr_tokens = [t for t in tokens if t.kind == "attr_span"]
        assert len(attr_tokens) == 1
        assert attr_tokens[0].text == "styled text"
        assert "size" in attr_tokens[0].attrs
        assert "color" in attr_tokens[0].attrs

    def test_multiline(self):
        text = "Line one\nLine two\nLine three"
        tokens = _tokenize(text)
        newlines = [t for t in tokens if t.kind == "plain" and t.text == "\n"]
        assert len(newlines) == 2  # Two newlines between three lines

    def test_empty_input(self):
        tokens = _tokenize("")
        # Should produce no content tokens
        content = [t for t in tokens if t.text.strip()]
        assert len(content) == 0

    def test_escaped_star(self):
        tokens = _tokenize("This is \\*not italic\\*")
        italic_tokens = [t for t in tokens if t.kind == "italic"]
        assert len(italic_tokens) == 0
        # The restored text should contain literal asterisks
        all_text = "".join(t.text for t in tokens)
        assert "*not italic*" in all_text

    def test_mixed_formatting(self):
        text = "Normal **bold** and *italic* and ***both***"
        tokens = _tokenize(text)
        kinds = {t.kind for t in tokens}
        assert "bold" in kinds
        assert "italic" in kinds
        assert "bold_italic" in kinds
        assert "plain" in kinds

    def test_heading_not_inline(self):
        # Heading markers only work at start of a line
        tokens = _tokenize("# Title\nParagraph text")
        headings = [t for t in tokens if t.kind == "heading1"]
        assert len(headings) == 1
        assert headings[0].text == "Title"


# =============================================================================
# _parse_attrs
# =============================================================================


class TestParseAttrs:
    def test_single_attr(self):
        result = _parse_attrs("size: 24")
        assert result == {"size": "24"}

    def test_multiple_attrs(self):
        result = _parse_attrs("size: 24, color: #FF0000")
        assert result == {"size": "24", "color": "#FF0000"}

    def test_strips_whitespace(self):
        result = _parse_attrs("  size : 24 , color : red ")
        assert result["size"] == "24"
        assert result["color"] == "red"

    def test_quoted_value(self):
        result = _parse_attrs('style: "Bold Italic"')
        assert result["style"] == "Bold Italic"

    def test_axis_values(self):
        result = _parse_attrs("wght: 700, opsz: 12.5")
        assert result["wght"] == "700"
        assert result["opsz"] == "12.5"

    def test_empty_string(self):
        result = _parse_attrs("")
        assert result == {}

    def test_malformed_skipped(self, capsys):
        result = _parse_attrs("badattr, size: 24")
        assert "size" in result
        assert "badattr" not in result
        captured = capsys.readouterr()
        assert "malformed" in captured.out.lower()

    def test_feat_attribute(self):
        # Comma is the attribute separator, so "feat: smcp,onum" splits into two attrs.
        # Only "feat: smcp" is well-formed; "onum" alone is malformed.
        result = _parse_attrs("feat: smcp,onum")
        assert result["feat"] == "smcp"

    def test_feat_attribute_single(self):
        result = _parse_attrs("feat: smcp")
        assert result["feat"] == "smcp"


# =============================================================================
# _parse_hex_color
# =============================================================================


class TestParseHexColor:
    def test_six_digit(self):
        r, g, b = _parse_hex_color("#FF0000")
        assert abs(r - 1.0) < 0.01
        assert abs(g - 0.0) < 0.01
        assert abs(b - 0.0) < 0.01

    def test_three_digit(self):
        r, g, b = _parse_hex_color("#F00")
        assert abs(r - 1.0) < 0.01
        assert abs(g - 0.0) < 0.01
        assert abs(b - 0.0) < 0.01

    def test_white(self):
        r, g, b = _parse_hex_color("#FFFFFF")
        assert abs(r - 1.0) < 0.01
        assert abs(g - 1.0) < 0.01
        assert abs(b - 1.0) < 0.01

    def test_black(self):
        r, g, b = _parse_hex_color("#000000")
        assert r == 0.0
        assert g == 0.0
        assert b == 0.0

    def test_no_hash(self):
        r, g, b = _parse_hex_color("00FF00")
        assert abs(g - 1.0) < 0.01

    def test_invalid_length(self, capsys):
        result = _parse_hex_color("#FFFF")
        assert result is None

    def test_invalid_chars(self, capsys):
        result = _parse_hex_color("#GGGGGG")
        assert result is None

    def test_leading_whitespace(self):
        r, g, b = _parse_hex_color("  #FF0000  ")
        assert abs(r - 1.0) < 0.01

    def test_mixed_case(self):
        r1, g1, b1 = _parse_hex_color("#ff0000")
        r2, g2, b2 = _parse_hex_color("#FF0000")
        assert r1 == r2 and g1 == g2 and b1 == b2
