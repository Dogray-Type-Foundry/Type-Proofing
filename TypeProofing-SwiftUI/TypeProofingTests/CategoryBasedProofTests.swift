import XCTest
@testable import TypeProofing

final class CategoryBasedProofTests: XCTestCase {

    private let fontPath = NSString(string: "~/local/github/Type-Proofing/SetsGroteskVF.ttf").expandingTildeInPath
    private let outputDir = NSString(string: "~/Desktop").expandingTildeInPath

    // MARK: - CharacterCategorizer

    func testCategorizeBasicLatin() {
        let charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'\"()+=$€"
        let cat = CharacterCategorizer.categorize(charset: charset)

        XCTAssertEqual(cat.uniLu, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        XCTAssertEqual(cat.uniLl, "abcdefghijklmnopqrstuvwxyz")
        XCTAssertEqual(cat.uniLuBase, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        XCTAssertEqual(cat.uniLlBase, "abcdefghijklmnopqrstuvwxyz")
        XCTAssertEqual(cat.uniNd, "0123456789")
        XCTAssertTrue(cat.uniPo.contains("."))
        XCTAssertTrue(cat.uniPd.contains("-"))
        XCTAssertTrue(cat.uniSm.contains("+"))
        XCTAssertTrue(cat.uniSc.contains("$"))
        XCTAssertTrue(cat.uniSc.contains("€"))
        XCTAssertFalse(cat.uppercaseOnly)
        XCTAssertFalse(cat.lowercaseOnly)
        XCTAssertTrue(cat.accentedPlus.isEmpty)
    }

    func testCategorizeWithAccented() {
        let charset = "ABCÀÁÂÃabcàáâã"
        let cat = CharacterCategorizer.categorize(charset: charset)

        XCTAssertEqual(cat.uniLuBase, "ABC")
        XCTAssertEqual(cat.uniLlBase, "abc")
        XCTAssertTrue(cat.accentedPlus.contains("À"))
        XCTAssertTrue(cat.accentedPlus.contains("á"))
        XCTAssertFalse(cat.accentedPlus.contains("A"))
    }

    func testProofCategories() {
        let charset = "ABCabc0123.,;-+$"
        let cat = CharacterCategorizer.categorize(charset: charset)
        let proof = CharacterCategorizer.proofCategories(from: cat)

        XCTAssertEqual(proof.uppercaseBase, "ABC")
        XCTAssertEqual(proof.lowercaseBase, "abc")
        XCTAssertTrue(proof.numbersSymbols.contains("0123"))
        XCTAssertTrue(proof.punctuation.contains("."))
        XCTAssertTrue(proof.punctuation.contains("-"))
        XCTAssertTrue(proof.accented.isEmpty)
    }

    // MARK: - Spacing String

    func testGenerateSpacingString() {
        let result = CharacterCategorizer.generateSpacingString(characterSet: "A")
        XCTAssertEqual(result, "HHHAHOHAOAOOO\n")
    }

    func testSpacingStringLowercase() {
        let result = CharacterCategorizer.generateSpacingString(characterSet: "a")
        XCTAssertEqual(result, "nnnanonaoaooo\n")
    }

    func testSpacingStringDigit() {
        let result = CharacterCategorizer.generateSpacingString(characterSet: "5")
        XCTAssertEqual(result, "0005010515111\n")
    }

    func testSpacingStringMultiple() {
        let result = CharacterCategorizer.generateSpacingString(characterSet: "Ab")
        let lines = result.split(separator: "\n")
        XCTAssertEqual(lines.count, 2)
        XCTAssertTrue(lines[0].hasPrefix("HHH"))
        XCTAssertTrue(lines[1].hasPrefix("nnn"))
    }

    func testSpacingStringSkipsSpaceAndNewline() {
        let result = CharacterCategorizer.generateSpacingString(characterSet: "A \nB")
        let lines = result.split(separator: "\n")
        XCTAssertEqual(lines.count, 2)
    }

    // MARK: - FilteredCharacterSetHandler PDF

    func testFilteredCharacterSetProof() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        let url = URL(fileURLWithPath: outputDir).appendingPathComponent("Phase3_FilteredCharset.pdf")
        let pageSize = PageLayout.pageDimensions["A4Landscape"]!
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: pageSize))

        let charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-'\"()+=$€ÀÁÂÃÄÅàáâãäå"
        let cat = CharacterCategorizer.categorize(charset: charset)
        let context = ProofContext(
            fullCharacterSet: charset,
            indFont: fontPath,
            axisValues: ["wght": 400],
            otFeatures: [:],
            cat: cat,
            pageFormat: "A4Landscape",
            proofSettings: [
                "filtered_character_set_fontSize": 36,
                "filtered_character_set_cat_accented": true,
            ],
            showBaselines: false,
            allAxisValues: nil,
            allFontPaths: [fontPath],
            axisValuesByFont: [:],
            diagnostics: DiagnosticCollector()
        )

        let handler = FilteredCharacterSetHandler(proofName: "Filtered Character Set", proofKey: "filtered_character_set")
        handler.generateProof(context: context, renderer: renderer)
        renderer.close()

        XCTAssertGreaterThanOrEqual(renderer.pageCount, 1, "Expected at least 1 page")
        XCTAssertTrue(FileManager.default.fileExists(atPath: url.path))
        print("Filtered charset proof: \(url.path)")
    }

    // MARK: - Auto Sizing

    func testAutoSizeFitToPage() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        let text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        let size = AutoSizing.fitToPage(
            text: text,
            fontPath: fontPath,
            pageFormat: "A4Landscape",
            variations: ["wght": 400]
        )
        XCTAssertGreaterThan(size, 10, "Should find a reasonable font size")
        XCTAssertLessThanOrEqual(size, 200, "Should not exceed max")
    }

    func testAutoSizeFitToLine() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        let text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        let size = AutoSizing.fitToLine(
            text: text,
            fontPath: fontPath,
            pageFormat: "A4Landscape",
            variations: ["wght": 400]
        )
        XCTAssertGreaterThan(size, 10)
        XCTAssertLessThanOrEqual(size, 200)
    }

    // MARK: - SpacingProofHandler PDF

    func testSpacingProof() throws {
        let fontURL = URL(fileURLWithPath: fontPath)
        FontLoader.register(url: fontURL)
        defer { FontLoader.unregister(url: fontURL) }

        let url = URL(fileURLWithPath: outputDir).appendingPathComponent("Phase3_SpacingProof.pdf")
        let pageSize = PageLayout.pageDimensions["A4Landscape"]!
        let renderer = PDFRenderer(url: url, mediaBox: CGRect(origin: .zero, size: pageSize))

        let charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        let cat = CharacterCategorizer.categorize(charset: charset)
        let context = ProofContext(
            fullCharacterSet: charset,
            indFont: fontPath,
            axisValues: ["wght": 400],
            otFeatures: [:],
            cat: cat,
            pageFormat: "A4Landscape",
            proofSettings: [
                "spacing_proof_fontSize": 12,
            ],
            showBaselines: false,
            allAxisValues: nil,
            allFontPaths: [fontPath],
            axisValuesByFont: [:],
            diagnostics: DiagnosticCollector()
        )

        let handler = SpacingProofHandler(proofName: "Spacing Proof", proofKey: "spacing_proof")
        handler.generateProof(context: context, renderer: renderer)
        renderer.close()

        XCTAssertGreaterThanOrEqual(renderer.pageCount, 1, "Expected at least 1 page")
        XCTAssertTrue(FileManager.default.fileExists(atPath: url.path))
        print("Spacing proof: \(url.path)")
    }
}
