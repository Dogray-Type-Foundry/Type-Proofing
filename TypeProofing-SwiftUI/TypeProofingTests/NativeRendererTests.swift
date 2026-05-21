import XCTest
@testable import TypeProofing

final class NativeRendererTests: XCTestCase {

    private let fontPath = NSString(string: "~/local/github/Type-Proofing/SetsGroteskVF.ttf").expandingTildeInPath

    func testPDFCreation() throws {
        let url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("test_pdf_creation.pdf")
        let pageSize = CGSize(width: 842, height: 595)
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: pageSize))

        renderer.beginPage()
        renderer.fillRect(CGRect(x: 50, y: 50, width: 100, height: 100), color: CGColor(red: 1, green: 0, blue: 0, alpha: 1))
        renderer.strokeLine(from: CGPoint(x: 0, y: 297), to: CGPoint(x: 842, y: 297), color: CGColor(gray: 0.5, alpha: 1), width: 0.5)
        renderer.endPage()

        renderer.beginPage()
        renderer.fillRect(CGRect(x: 200, y: 200, width: 200, height: 200), color: CGColor(red: 0, green: 0, blue: 1, alpha: 1))
        renderer.endPage()

        renderer.close()

        XCTAssertEqual(renderer.pageCount, 2)
        XCTAssertTrue(FileManager.default.fileExists(atPath: url.path))
        let data = try Data(contentsOf: url)
        XCTAssertGreaterThan(data.count, 100)
        print("PDF created: \(url.path)")
    }

    func testFontLoading() {
        let fontURL = URL(fileURLWithPath: fontPath)
        XCTAssertTrue(FontLoader.register(url: fontURL))

        let font = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: nil)
        XCTAssertNotNil(font)

        let fontWithVariation = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: ["wght": 700])
        XCTAssertNotNil(fontWithVariation)

        XCTAssertTrue(FontLoader.fontContains(font!, characters: "A"))
        XCTAssertFalse(FontLoader.fontContains(font!, characters: "\u{1F600}"))

        FontLoader.unregister(url: fontURL)
    }

    func testTextMeasurement() {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        guard let font = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: nil) else {
            XCTFail("Font load failed"); return
        }

        let attrStr = TextRenderer.makeAttributedString(
            text: "Hello",
            font: font,
            fontSize: 48,
            alignment: .left,
            tracking: 0,
            lineHeight: nil,
            foregroundColor: CGColor(gray: 0, alpha: 1)
        )

        let size = TextRenderer.measureText(attrStr, width: nil)
        XCTAssertGreaterThan(size.width, 0)
        XCTAssertGreaterThan(size.height, 0)

        let constrainedSize = TextRenderer.measureText(attrStr, width: 200)
        XCTAssertGreaterThan(constrainedSize.height, 0)
    }

    func testOverflowDetection() {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        guard let font = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: nil) else {
            XCTFail("Font load failed"); return
        }

        let longText = String(repeating: "Pack my box with five dozen liquor jugs. ", count: 20)
        let attrStr = TextRenderer.makeAttributedString(
            text: longText,
            font: font,
            fontSize: 48,
            alignment: .left,
            tracking: 0,
            lineHeight: nil,
            foregroundColor: CGColor(gray: 0, alpha: 1)
        )

        let url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("test_overflow.pdf")
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: CGSize(width: 842, height: 595)))

        renderer.beginPage()
        let smallBox = CGRect(x: 50, y: 50, width: 300, height: 150)
        let overflow = TextRenderer.drawText(attrStr, in: smallBox, context: renderer.context)
        renderer.endPage()
        renderer.close()

        XCTAssertNotNil(overflow, "Expected overflow from small text box")
        XCTAssertGreaterThan(overflow!.length, 0)
    }

    func testColumnLayout() {
        let content = PageLayout.contentRect(pageFormat: "A4Landscape")
        XCTAssertEqual(content.origin.x, 40)
        XCTAssertEqual(content.origin.y, 50)
        XCTAssertEqual(content.width, 762)
        XCTAssertEqual(content.height, 495)

        let cols = PageLayout.columnRects(contentRect: content, columns: 3)
        XCTAssertEqual(cols.count, 3)

        let totalWidth = cols.reduce(0) { $0 + $1.width } + 2 * PageLayout.defaultGutter
        XCTAssertEqual(totalWidth, content.width, accuracy: 0.01)

        for i in 0..<cols.count - 1 {
            XCTAssertFalse(cols[i].intersects(cols[i + 1]))
        }
    }

    func testRTLColumns() {
        let content = PageLayout.contentRect(pageFormat: "A4Landscape")
        let rtlCols = PageLayout.columnRects(contentRect: content, columns: 2, direction: .rtl)
        let ltrCols = PageLayout.columnRects(contentRect: content, columns: 2, direction: .ltr)

        XCTAssertEqual(rtlCols[0].minX, ltrCols[1].minX, accuracy: 0.01)
        XCTAssertEqual(rtlCols[1].minX, ltrCols[0].minX, accuracy: 0.01)
    }

    func testFullPipelineSmoke() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        guard let font = FontLoader.makeFont(path: fontPath, size: 48, features: ["liga": true], variations: ["wght": 400]) else {
            XCTFail("Font load failed"); return
        }

        let url = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("smoke_test.pdf")
        let pageSize = PageLayout.pageDimensions["A4Landscape"]!
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: pageSize))

        let text = "The quick brown fox jumps over the lazy dog. " +
            String(repeating: "Pack my box with five dozen liquor jugs. ", count: 20)
        let attrStr = TextRenderer.makeAttributedString(
            text: text,
            font: font,
            fontSize: 48,
            alignment: .left,
            tracking: 0,
            lineHeight: nil,
            foregroundColor: CGColor(gray: 0, alpha: 1)
        )

        let content = PageLayout.contentRect(pageFormat: "A4Landscape")
        let columns = PageLayout.columnRects(contentRect: content, columns: 2)
        var overflow: NSAttributedString? = attrStr
        var pageNum = 1

        while overflow != nil {
            renderer.beginPage()
            PageLayout.drawFooter(
                context: renderer.context,
                pageSize: pageSize,
                title: "Smoke Test - 48pt",
                fontName: "Sets Grotesk VF",
                otFeatures: ["smcp": true, "kern": false],
                tracking: 0,
                pageNumber: pageNum,
                showPageNumber: true
            )

            for col in columns {
                guard let text = overflow else { break }
                overflow = TextRenderer.drawText(text, in: col, context: renderer.context)
            }

            renderer.endPage()
            pageNum += 1
            if pageNum > 10 { break }
        }

        renderer.close()

        XCTAssertTrue(FileManager.default.fileExists(atPath: url.path))
        XCTAssertGreaterThanOrEqual(renderer.pageCount, 2, "Expected multi-page PDF from overflow")
        print("Smoke test PDF: \(url.path)")
    }

    func testKernDisable() {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        guard let font = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: nil) else {
            XCTFail("Font load failed"); return
        }

        let withKern = TextRenderer.makeAttributedString(
            text: "AV", font: font, fontSize: 48, alignment: .left,
            tracking: 0, lineHeight: nil, foregroundColor: CGColor(gray: 0, alpha: 1),
            kernDisabled: false
        )
        let withoutKern = TextRenderer.makeAttributedString(
            text: "AV", font: font, fontSize: 48, alignment: .left,
            tracking: 0, lineHeight: nil, foregroundColor: CGColor(gray: 0, alpha: 1),
            kernDisabled: true
        )

        let widthKerned = TextRenderer.measureText(withKern, width: nil).width
        let widthUnkerned = TextRenderer.measureText(withoutKern, width: nil).width
        XCTAssertNotEqual(widthKerned, widthUnkerned, accuracy: 0.01, "Kern disable should change width of 'AV'")
    }

    func testVariableFontAxes() {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        guard let lightFont = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: ["wght": 100]),
              let heavyFont = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: ["wght": 900])
        else {
            XCTFail("Font load failed"); return
        }

        let lightStr = TextRenderer.makeAttributedString(
            text: "Hello", font: lightFont, fontSize: 48, alignment: .left,
            tracking: 0, lineHeight: nil, foregroundColor: CGColor(gray: 0, alpha: 1)
        )
        let heavyStr = TextRenderer.makeAttributedString(
            text: "Hello", font: heavyFont, fontSize: 48, alignment: .left,
            tracking: 0, lineHeight: nil, foregroundColor: CGColor(gray: 0, alpha: 1)
        )

        let lightWidth = TextRenderer.measureText(lightStr, width: nil).width
        let heavyWidth = TextRenderer.measureText(heavyStr, width: nil).width
        XCTAssertNotEqual(lightWidth, heavyWidth, accuracy: 0.1, "Different weights should produce different widths")
    }
}
