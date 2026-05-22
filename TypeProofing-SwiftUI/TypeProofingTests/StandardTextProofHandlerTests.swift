import XCTest
@testable import TypeProofing

final class StandardTextProofHandlerTests: XCTestCase {

    private let fontPath = NSString(string: "~/local/github/Type-Proofing/SetsGroteskVF.ttf").expandingTildeInPath
    private let outputDir = NSString(string: "~/Desktop").expandingTildeInPath

    private func makeContext(fontSize: Int = 10) -> ProofContext {
        let latin = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        let numbers = "0123456789"
        let punct = ".,;:!?-'\"()"
        return ProofContext(
            fullCharacterSet: latin + numbers + punct + " ",
            indFont: fontPath,
            axisValues: ["wght": 400],
            otFeatures: [:],
            cat: CharacterCategories(
                uniLu: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                uniLl: "abcdefghijklmnopqrstuvwxyz",
                uniLuBase: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                uniLlBase: "abcdefghijklmnopqrstuvwxyz",
                uniNd: numbers,
                uniPo: ".,;:!?",
                uniPc: "",
                uniPd: "-",
                uniPi: "'\"",
                uniPf: "'\"",
                uppercaseOnly: false,
                lowercaseOnly: false
            ),
            pageFormat: "A4Landscape",
            proofSettings: [
                "basic_paragraph_small_fontSize": fontSize,
                "basic_paragraph_small_cols": 2,
            ],
            showBaselines: false,
            allAxisValues: nil,
            allFontPaths: [fontPath],
            axisValuesByFont: [:],
            diagnostics: DiagnosticCollector()
        )
    }

    func testBasicParagraphSmall() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        let url = URL(fileURLWithPath: outputDir).appendingPathComponent("Phase3_BasicParagraphSmall.pdf")
        let pageSize = PageLayout.pageDimensions["A4Landscape"]!
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: pageSize))

        let handler = StandardTextProofHandler(proofName: "Structured Text (Text)", proofKey: "basic_paragraph_small")
        let context = makeContext()

        handler.generateProof(context: context, renderer: renderer)
        renderer.close()

        XCTAssertGreaterThanOrEqual(renderer.pageCount, 1, "Expected at least 1 page")
        XCTAssertTrue(FileManager.default.fileExists(atPath: url.path))
        print("Basic paragraph proof: \(url.path)")
    }

    func testBasicParagraphLarge() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        let url = URL(fileURLWithPath: outputDir).appendingPathComponent("Phase3_BasicParagraphLarge.pdf")
        let pageSize = PageLayout.pageDimensions["A4Landscape"]!
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: pageSize))

        let handler = StandardTextProofHandler(proofName: "Structured Text (Heading)", proofKey: "basic_paragraph_large")
        var context = makeContext(fontSize: 28)
        // Override the settings key for this handler
        let settings: [String: Any] = [
            "basic_paragraph_large_fontSize": 28,
            "basic_paragraph_large_cols": 1,
        ]
        context = ProofContext(
            fullCharacterSet: context.fullCharacterSet,
            indFont: context.indFont,
            axisValues: context.axisValues,
            otFeatures: context.otFeatures,
            cat: context.cat,
            pageFormat: context.pageFormat,
            proofSettings: settings,
            showBaselines: false,
            allAxisValues: nil,
            allFontPaths: [fontPath],
            axisValuesByFont: [:],
            diagnostics: DiagnosticCollector()
        )

        handler.generateProof(context: context, renderer: renderer)
        renderer.close()

        XCTAssertGreaterThanOrEqual(renderer.pageCount, 1)
        print("Large paragraph proof: \(url.path)")
    }

    func testWordsivTextGeneration() {
        let cat = CharacterCategories(
            uniLu: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            uniLl: "abcdefghijklmnopqrstuvwxyz",
            uniLuBase: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            uniLlBase: "abcdefghijklmnopqrstuvwxyz",
            uniNd: "0123456789",
            uniPo: ".,;:!?",
            uniPd: "-",
            uppercaseOnly: false,
            lowercaseOnly: false
        )
        let text = TextGeneration.generateTextProofString(
            characterSet: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            paragraphs: 2,
            forceWordsiv: true,
            cat: cat,
            fullCharacterSet: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?- "
        )
        XCTAssertFalse(text.isEmpty, "WordSiv should generate text")
        XCTAssertGreaterThan(text.count, 50, "Expected substantial generated text")
    }
}
