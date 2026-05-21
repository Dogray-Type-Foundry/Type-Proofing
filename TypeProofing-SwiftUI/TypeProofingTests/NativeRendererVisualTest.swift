import XCTest
@testable import TypeProofing

final class NativeRendererVisualTest: XCTestCase {

    private let fontPath = NSString(string: "~/local/github/Type-Proofing/SetsGroteskVF.ttf").expandingTildeInPath
    private let outputDir = NSString(string: "~/Desktop").expandingTildeInPath

    func testVisualVerification() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        let url = URL(fileURLWithPath: outputDir).appendingPathComponent("Phase2_Visual_Test.pdf")
        let pageSize = PageLayout.pageDimensions["A4Landscape"]!
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: pageSize))
        let black = CGColor(gray: 0, alpha: 1)
        let gray = CGColor(gray: 0.6, alpha: 1)
        let content = PageLayout.contentRect(pageFormat: "A4Landscape")

        // --- Page 1: Variable font weight axis ---
        renderer.beginPage()
        PageLayout.drawFooter(
            context: renderer.context, pageSize: pageSize,
            title: "Page 1 — Variable Weight Axis", fontName: "Sets Grotesk VF",
            otFeatures: nil, tracking: 0, pageNumber: 1, showPageNumber: true
        )

        let weights: [(String, Double)] = [
            ("wght 100", 100), ("wght 300", 300), ("wght 400", 400),
            ("wght 700", 700), ("wght 900", 900),
        ]
        let sampleText = "Hamburgefontsiv"
        let rowHeight: CGFloat = 72
        var y = content.maxY - rowHeight

        for (label, weight) in weights {
            guard let font = FontLoader.makeFont(path: fontPath, size: 48, features: nil, variations: ["wght": weight]) else { continue }

            let labelAttr = TextRenderer.makeAttributedString(
                text: label, font: CTFontCreateWithName("Courier" as CFString, 10, nil),
                fontSize: 10, alignment: .left, tracking: 0, lineHeight: nil, foregroundColor: gray
            )
            TextRenderer.drawText(labelAttr, in: CGRect(x: content.minX, y: y + 2, width: 100, height: 14), context: renderer.context)

            let textAttr = TextRenderer.makeAttributedString(
                text: sampleText, font: font, fontSize: 48,
                alignment: .left, tracking: 0, lineHeight: nil, foregroundColor: black
            )
            TextRenderer.drawText(textAttr, in: CGRect(x: content.minX + 100, y: y, width: content.width - 100, height: rowHeight), context: renderer.context)

            renderer.strokeLine(
                from: CGPoint(x: content.minX, y: y),
                to: CGPoint(x: content.maxX, y: y),
                color: CGColor(gray: 0.85, alpha: 1), width: 0.25
            )
            y -= rowHeight
        }

        renderer.endPage()

        // --- Page 2: OT features ---
        renderer.beginPage()
        PageLayout.drawFooter(
            context: renderer.context, pageSize: pageSize,
            title: "Page 2 — OpenType Features", fontName: "Sets Grotesk VF",
            otFeatures: nil, tracking: 0, pageNumber: 2, showPageNumber: true
        )

        let featureTests: [(String, [String: Bool], String)] = [
            ("Default (liga on)", [:], "fi fl ffi office waffle"),
            ("liga OFF", ["liga": false], "fi fl ffi office waffle"),
            ("smcp ON", ["smcp": true], "Small Caps Test ABC xyz"),
            ("onum ON", ["onum": true], "0123456789 $1,250.00"),
            ("kern OFF", ["kern": false], "AV AW To VA We"),
        ]

        y = content.maxY - rowHeight
        for (label, features, text) in featureTests {
            guard let font = FontLoader.makeFont(path: fontPath, size: 36, features: features.isEmpty ? nil : features, variations: ["wght": 400]) else { continue }

            let labelAttr = TextRenderer.makeAttributedString(
                text: label, font: CTFontCreateWithName("Courier" as CFString, 10, nil),
                fontSize: 10, alignment: .left, tracking: 0, lineHeight: nil, foregroundColor: gray
            )
            TextRenderer.drawText(labelAttr, in: CGRect(x: content.minX, y: y + 8, width: 120, height: 14), context: renderer.context)

            let kernDisabled = features["kern"] == false
            let textAttr = TextRenderer.makeAttributedString(
                text: text, font: font, fontSize: 36,
                alignment: .left, tracking: 0, lineHeight: nil, foregroundColor: black,
                kernDisabled: kernDisabled
            )
            TextRenderer.drawText(textAttr, in: CGRect(x: content.minX + 120, y: y, width: content.width - 120, height: rowHeight), context: renderer.context)

            renderer.strokeLine(
                from: CGPoint(x: content.minX, y: y),
                to: CGPoint(x: content.maxX, y: y),
                color: CGColor(gray: 0.85, alpha: 1), width: 0.25
            )
            y -= rowHeight
        }

        renderer.endPage()

        // --- Page 3: Tracking + line height ---
        renderer.beginPage()
        PageLayout.drawFooter(
            context: renderer.context, pageSize: pageSize,
            title: "Page 3 — Tracking & Line Height", fontName: "Sets Grotesk VF",
            otFeatures: nil, tracking: 0, pageNumber: 3, showPageNumber: true
        )

        guard let baseFont = FontLoader.makeFont(path: fontPath, size: 24, features: nil, variations: ["wght": 400]) else {
            XCTFail("Font load failed"); return
        }

        let trackingTests: [(String, CGFloat)] = [
            ("Tracking 0", 0), ("Tracking 12", 12), ("Tracking 24", 24), ("Tracking 48", 48),
        ]

        let paraText = "The quick brown fox jumps over the lazy dog."
        y = content.maxY - 50

        for (label, tracking) in trackingTests {
            let labelAttr = TextRenderer.makeAttributedString(
                text: label, font: CTFontCreateWithName("Courier" as CFString, 10, nil),
                fontSize: 10, alignment: .left, tracking: 0, lineHeight: nil, foregroundColor: gray
            )
            TextRenderer.drawText(labelAttr, in: CGRect(x: content.minX, y: y + 2, width: 120, height: 14), context: renderer.context)

            let textAttr = TextRenderer.makeAttributedString(
                text: paraText, font: baseFont, fontSize: 24,
                alignment: .left, tracking: tracking, lineHeight: nil, foregroundColor: black
            )
            TextRenderer.drawText(textAttr, in: CGRect(x: content.minX + 120, y: y - 26, width: content.width - 120, height: 40), context: renderer.context)

            y -= 55
        }

        y -= 20
        let lineHeightTests: [(String, CGFloat)] = [
            ("lineHeight 28", 28), ("lineHeight 36", 36), ("lineHeight 48", 48),
        ]
        let multiLine = "This is a multi-line paragraph to test fixed line height. Each line should snap to the exact specified height with no variation."

        for (label, lh) in lineHeightTests {
            let labelAttr = TextRenderer.makeAttributedString(
                text: label, font: CTFontCreateWithName("Courier" as CFString, 10, nil),
                fontSize: 10, alignment: .left, tracking: 0, lineHeight: nil, foregroundColor: gray
            )
            TextRenderer.drawText(labelAttr, in: CGRect(x: content.minX, y: y + 2, width: 120, height: 14), context: renderer.context)

            let textAttr = TextRenderer.makeAttributedString(
                text: multiLine, font: baseFont, fontSize: 24,
                alignment: .left, tracking: 0, lineHeight: lh, foregroundColor: black
            )
            let boxHeight: CGFloat = lh * 3.5
            TextRenderer.drawText(textAttr, in: CGRect(x: content.minX + 120, y: y - boxHeight + 14, width: content.width - 120, height: boxHeight), context: renderer.context)

            y -= boxHeight + 10
        }

        renderer.endPage()

        // --- Page 4: Two-column overflow with footer features line ---
        renderer.beginPage()
        PageLayout.drawFooter(
            context: renderer.context, pageSize: pageSize,
            title: "Page 4 — 2-Column Layout + Features Footer", fontName: "Sets Grotesk VF",
            otFeatures: ["smcp": true, "onum": true, "kern": false],
            tracking: 12, pageNumber: 4, showPageNumber: true
        )

        let columns = PageLayout.columnRects(contentRect: content, columns: 2)
        for col in columns {
            renderer.strokeLine(from: CGPoint(x: col.minX, y: col.minY), to: CGPoint(x: col.minX, y: col.maxY), color: CGColor(gray: 0.9, alpha: 1), width: 0.25)
            renderer.strokeLine(from: CGPoint(x: col.maxX, y: col.minY), to: CGPoint(x: col.maxX, y: col.maxY), color: CGColor(gray: 0.9, alpha: 1), width: 0.25)
        }

        let longText = String(repeating: "Pack my box with five dozen liquor jugs. The quick brown fox jumps over the lazy dog. ", count: 8)
        guard let colFont = FontLoader.makeFont(path: fontPath, size: 18, features: nil, variations: ["wght": 400]) else {
            XCTFail("Font load failed"); return
        }
        let colAttr = TextRenderer.makeAttributedString(
            text: longText, font: colFont, fontSize: 18,
            alignment: .justified, tracking: 0, lineHeight: 24, foregroundColor: black
        )
        var overflow: NSAttributedString? = colAttr
        for col in columns {
            guard let remaining = overflow else { break }
            overflow = TextRenderer.drawText(remaining, in: col, context: renderer.context)
        }

        renderer.endPage()

        // --- Page 5: RTL columns ---
        renderer.beginPage()
        PageLayout.drawFooter(
            context: renderer.context, pageSize: pageSize,
            title: "Page 5 — RTL 3-Column Layout", fontName: "Sets Grotesk VF",
            otFeatures: nil, tracking: 0, pageNumber: 5, showPageNumber: true
        )

        let rtlCols = PageLayout.columnRects(contentRect: content, columns: 3, direction: .rtl)
        for (i, col) in rtlCols.enumerated() {
            renderer.strokeLine(from: CGPoint(x: col.minX, y: col.minY), to: CGPoint(x: col.minX, y: col.maxY), color: CGColor(gray: 0.85, alpha: 1), width: 0.5)
            renderer.strokeLine(from: CGPoint(x: col.maxX, y: col.minY), to: CGPoint(x: col.maxX, y: col.maxY), color: CGColor(gray: 0.85, alpha: 1), width: 0.5)

            let colLabel = TextRenderer.makeAttributedString(
                text: "Column \(i + 1) (RTL order)", font: CTFontCreateWithName("Courier" as CFString, 10, nil),
                fontSize: 10, alignment: .center, tracking: 0, lineHeight: nil, foregroundColor: gray
            )
            TextRenderer.drawText(colLabel, in: CGRect(x: col.minX, y: col.maxY - 16, width: col.width, height: 14), context: renderer.context)

            let sampleAttr = TextRenderer.makeAttributedString(
                text: "Column \(i + 1) text fills this area. The reading order flows right to left.",
                font: colFont, fontSize: 18, alignment: .left, tracking: 0, lineHeight: 24, foregroundColor: black
            )
            TextRenderer.drawText(sampleAttr, in: CGRect(x: col.minX, y: col.minY, width: col.width, height: col.height - 24), context: renderer.context)
        }

        renderer.endPage()

        renderer.close()

        XCTAssertEqual(renderer.pageCount, 5)
        print("Visual test PDF: \(url.path)")
    }
}
