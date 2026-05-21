import XCTest
@testable import TypeProofing

final class MarkupParserTests: XCTestCase {

    func testPlainText() {
        let tokens = MarkupParser.tokenize("Hello world")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].kind, .plain)
        XCTAssertEqual(tokens[0].text, "Hello world")
    }

    func testBold() {
        let tokens = MarkupParser.tokenize("Some **bold** text")
        XCTAssertEqual(tokens.count, 3)
        XCTAssertEqual(tokens[0].kind, .plain)
        XCTAssertEqual(tokens[0].text, "Some ")
        XCTAssertEqual(tokens[1].kind, .bold)
        XCTAssertEqual(tokens[1].text, "bold")
        XCTAssertEqual(tokens[2].kind, .plain)
        XCTAssertEqual(tokens[2].text, " text")
    }

    func testItalic() {
        let tokens = MarkupParser.tokenize("Some *italic* text")
        XCTAssertEqual(tokens.count, 3)
        XCTAssertEqual(tokens[1].kind, .italic)
        XCTAssertEqual(tokens[1].text, "italic")
    }

    func testBoldItalic() {
        let tokens = MarkupParser.tokenize("***bold italic***")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].kind, .boldItalic)
        XCTAssertEqual(tokens[0].text, "bold italic")
    }

    func testHeading1() {
        let tokens = MarkupParser.tokenize("# Heading One")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].kind, .heading1)
        XCTAssertEqual(tokens[0].text, "Heading One")
    }

    func testHeading2() {
        let tokens = MarkupParser.tokenize("## Heading Two")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].kind, .heading2)
        XCTAssertEqual(tokens[0].text, "Heading Two")
    }

    func testPageBreak() {
        let tokens = MarkupParser.tokenize("#pagebreak()")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].kind, .pageBreak)
    }

    func testColumnBreak() {
        let tokens = MarkupParser.tokenize("#colbreak()")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].kind, .columnBreak)
    }

    func testAttrSpan() {
        let tokens = MarkupParser.tokenize("[text]{wght: 700, style: Bold}")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].kind, .attrSpan)
        XCTAssertEqual(tokens[0].text, "text")
        XCTAssertEqual(tokens[0].attrs["wght"], "700")
        XCTAssertEqual(tokens[0].attrs["style"], "Bold")
    }

    func testEscapedCharacters() {
        let tokens = MarkupParser.tokenize("Use \\*asterisks\\* literally")
        XCTAssertEqual(tokens.count, 1)
        XCTAssertEqual(tokens[0].text, "Use *asterisks* literally")
    }

    func testMultiline() {
        let tokens = MarkupParser.tokenize("Line one\nLine two\n\nLine four")
        let nonNewline = tokens.filter { $0.kind != .plain || $0.text != "\n" }
        XCTAssertEqual(nonNewline.count, 3)
        XCTAssertEqual(nonNewline[0].text, "Line one")
        XCTAssertEqual(nonNewline[1].text, "Line two")
        XCTAssertEqual(nonNewline[2].text, "Line four")
    }

    func testParseHexColor() {
        let rgb = MarkupParser.parseHexColor("#FF8800")
        XCTAssertNotNil(rgb)
        XCTAssertEqual(rgb!.0, 1.0, accuracy: 0.01)
        XCTAssertEqual(rgb!.1, 0x88 / 255.0, accuracy: 0.01)
        XCTAssertEqual(rgb!.2, 0.0, accuracy: 0.01)
    }

    func testParseShortHexColor() {
        let rgb = MarkupParser.parseHexColor("#F80")
        XCTAssertNotNil(rgb)
        XCTAssertEqual(rgb!.0, 1.0, accuracy: 0.01)
        XCTAssertEqual(rgb!.1, 0x88 / 255.0, accuracy: 0.01)
    }

    func testParseAttrs() {
        let attrs = MarkupParser.parseAttrs("wght: 700, style: \"Bold Italic\", feat: liga")
        XCTAssertEqual(attrs["wght"], "700")
        XCTAssertEqual(attrs["style"], "Bold Italic")
        XCTAssertEqual(attrs["feat"], "liga")
    }
}
