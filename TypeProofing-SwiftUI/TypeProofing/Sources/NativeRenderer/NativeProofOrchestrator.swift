import CoreGraphics
import Foundation
import TPNative

struct NativeProofOrchestrator {

    struct Result {
        let path: String
        let sections: [ProofSection]
    }

    /// Charset extraction runs the whole font through the Rust parser, and it
    /// used to happen per preview fragment. Cache the derived charset and
    /// categories with the same mtime/size-invalidated key as the font bytes.
    private final class CharsetData {
        let charset: String
        let cat: CharacterCategories
        init(charset: String, cat: CharacterCategories) {
            self.charset = charset
            self.cat = cat
        }
    }

    private static let charsetCache = NSCache<NSString, CharsetData>()

    private static func charsetAndCategories(fontPath: String) -> (charset: String, cat: CharacterCategories)? {
        let key = FontLoader.fontCacheKey(for: fontPath) as NSString
        if let cached = charsetCache.object(forKey: key) {
            return (cached.charset, cached.cat)
        }
        guard let fontData = FontLoader.fontData(path: fontPath) else { return nil }
        let charset = fontData.withUnsafeBytes { buffer -> String in
            guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return "" }
            guard let charsetPtr = tp_get_charset(ptr, UInt(buffer.count)) else { return "" }
            defer { wsv_free_string(charsetPtr) }
            return String(cString: charsetPtr)
        }
        let cat = CharacterCategorizer.categorize(charset: charset)
        charsetCache.setObject(CharsetData(charset: charset, cat: cat), forKey: key)
        return (charset, cat)
    }

    static func generate(
        config: ProofConfig,
        progress: @Sendable (GenerationProgress) -> Void,
        isCancelled: @Sendable () -> Bool
    ) -> (result: Result?, diagnostics: [DiagnosticEvent]) {
        let collector = DiagnosticCollector()
        collector.debugMode = config.debugMode
        let runState = ProofRunState()
        let enabledProofs = config.proofOptions.filter(\.enabled)
        guard !config.fontPaths.isEmpty, !enabledProofs.isEmpty else {
            if config.fontPaths.isEmpty {
                collector.warning("No fonts loaded")
            }
            if enabledProofs.isEmpty {
                collector.warning("No proofs enabled")
            }
            return (nil, collector.collected)
        }

        let outputDir = config.outputDir.isEmpty
            ? FileManager.default.temporaryDirectory.path
            : config.outputDir
        let timestamp = ISO8601DateFormatter().string(from: Date())
            .replacingOccurrences(of: ":", with: "-")
        let pdfPath = (outputDir as NSString).appendingPathComponent("TypeProofing_\(timestamp).pdf")

        let pageSize = PageLayout.pageDimensions[config.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let mediaBox = CGRect(origin: .zero, size: pageSize)
        guard let renderer = PDFRenderer(url: URL(fileURLWithPath: pdfPath), mediaBox: mediaBox) else {
            collector.error("Could not create PDF file at \(pdfPath)")
            return (nil, collector.collected)
        }

        var sections: [ProofSection] = []
        let fontCount = config.fontPaths.count

        // Precompute per-font data once so we can iterate proofs in the outer
        // loop. This makes the PDF page order match the preview, which groups
        // pages by proof (each proof section shows all styles consecutively)
        // rather than by font style.
        struct FontRenderData {
            let fontPath: String
            let fontIndex: Int
            let charset: String
            let cat: CharacterCategories
            let axisCombinations: [[String: Double]]
        }

        var fontDataList: [FontRenderData] = []
        for (fontIndex, fontPath) in config.fontPaths.enumerated() {
            if isCancelled() { break }
            guard let (charset, cat) = charsetAndCategories(fontPath: fontPath) else {
                collector.error("Failed to read font file", fontPath: fontPath)
                continue
            }
            let axisCombinations = buildAxisCombinations(config: config, fontPath: fontPath)
            fontDataList.append(FontRenderData(
                fontPath: fontPath, fontIndex: fontIndex,
                charset: charset, cat: cat, axisCombinations: axisCombinations
            ))
        }

        let globalFeatures = buildGlobalOTFeatures()

        for (proofIndex, option) in enabledProofs.enumerated() {
            if isCancelled() { break }

            let proofKey = settingsKey(for: option)
            let perProofFeatures = extractOTFeatures(proofKey: proofKey, settings: config.proofSettings)
            let otFeatures = perProofFeatures.isEmpty ? globalFeatures : perProofFeatures
            let proofPagesBefore = renderer.pageCount

            for fontData in fontDataList {
                if isCancelled() { break }

                progress(GenerationProgress(
                    proofName: option.name,
                    proofIndex: proofIndex,
                    proofCount: enabledProofs.count,
                    fontPath: fontData.fontPath,
                    fontIndex: fontData.fontIndex,
                    fontCount: fontCount
                ))

                for axisValues in fontData.axisCombinations {
                    if isCancelled() { break }

                    let proofContext = ProofContext(
                        fullCharacterSet: fontData.charset,
                        indFont: fontData.fontPath,
                        axisValues: axisValues.isEmpty ? nil : axisValues,
                        otFeatures: otFeatures,
                        cat: fontData.cat,
                        pageFormat: config.pageFormat,
                        proofSettings: config.proofSettings,
                        showBaselines: config.showBaselines,
                        showFooter: config.showFooter,
                        allAxisValues: config.axisValuesByFont[fontData.fontPath],
                        allFontPaths: config.fontPaths,
                        axisValuesByFont: config.axisValuesByFont,
                        diagnostics: collector,
                        runState: runState
                    )

                    if let handler = makeHandler(proofName: option.name, proofKey: proofKey, baseType: option.baseType) {
                        handler.generateProof(context: proofContext, renderer: renderer)
                    }
                }
            }

            // One section per proof, matching the preview's section model.
            if renderer.pageCount > proofPagesBefore {
                sections.append(ProofSection(name: option.name, firstPage: proofPagesBefore))
            }
        }

        renderer.close()

        if renderer.pageCount == 0 {
            try? FileManager.default.removeItem(atPath: pdfPath)
            return (nil, collector.collected)
        }

        return (Result(path: pdfPath, sections: sections), collector.collected)
    }

    static func generateFragment(
        config: ProofConfig,
        isCancelled: @Sendable () -> Bool
    ) -> (fragment: PreviewFragmentResult?, diagnostics: [DiagnosticEvent]) {
        let collector = DiagnosticCollector()
        collector.debugMode = config.debugMode
        guard !config.fontPaths.isEmpty else {
            collector.error("No fonts loaded", proofName: config.targetProofName)
            return (nil, collector.collected)
        }

        let runState = ProofRunState()

        let outputDir = config.fragmentOutputDir.isEmpty
            ? FileManager.default.temporaryDirectory.path
            : config.fragmentOutputDir
        let pdfPath = (outputDir as NSString).appendingPathComponent("preview_\(UUID().uuidString).pdf")

        let pageSize = PageLayout.pageDimensions[config.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let mediaBox = CGRect(origin: .zero, size: pageSize)
        guard let renderer = PDFRenderer(url: URL(fileURLWithPath: pdfPath), mediaBox: mediaBox) else {
            collector.error("Could not create PDF file at \(pdfPath)",
                            proofName: config.targetProofName)
            return (nil, collector.collected)
        }

        let proofKey = settingsKey(for: config.targetProofName, baseType: config.targetProofBaseType)
        let globalFeatures = buildGlobalOTFeatures()
        let perProofFeatures = extractOTFeatures(proofKey: proofKey, settings: config.proofSettings)
        let otFeatures = perProofFeatures.isEmpty ? globalFeatures : perProofFeatures

        collector.debug("Generating fragment for '\(config.targetProofName)' (\(config.targetProofBaseType))",
                        proofName: config.targetProofName,
                        details: ["fonts": "\(config.fontPaths.count)", "proofKey": proofKey])

        var sections: [ProofSection] = []

        for fontPath in config.fontPaths {
            if isCancelled() { break }

            guard let (charset, cat) = charsetAndCategories(fontPath: fontPath) else {
                collector.error("Failed to read font file",
                               fontPath: fontPath, proofName: config.targetProofName)
                continue
            }

            let axisCombinations = buildAxisCombinations(config: config, fontPath: fontPath)

            for axisValues in axisCombinations {
                if isCancelled() { break }

                let proofContext = ProofContext(
                    fullCharacterSet: charset,
                    indFont: fontPath,
                    axisValues: axisValues.isEmpty ? nil : axisValues,
                    otFeatures: otFeatures,
                    cat: cat,
                    pageFormat: config.pageFormat,
                    proofSettings: config.proofSettings,
                    showBaselines: config.showBaselines,
                    showFooter: config.showFooter,
                    allAxisValues: config.axisValuesByFont[fontPath],
                    allFontPaths: config.fontPaths,
                    axisValuesByFont: config.axisValuesByFont,
                    diagnostics: collector,
                    runState: runState
                )

                let pagesBefore = renderer.pageCount
                if let handler = makeHandler(proofName: config.targetProofName, proofKey: proofKey, baseType: config.targetProofBaseType) {
                    handler.generateProof(context: proofContext, renderer: renderer)
                }
                if renderer.pageCount > pagesBefore && sections.isEmpty {
                    sections.append(ProofSection(name: config.targetProofName, firstPage: pagesBefore))
                }
            }
        }

        renderer.close()

        if renderer.pageCount == 0 {
            try? FileManager.default.removeItem(atPath: pdfPath)
            let errorMsg = collector.firstError ?? "No content generated"
            return (PreviewFragmentResult(
                path: "", pageCount: 0, sections: [],
                proofName: config.targetProofName, baseType: config.targetProofBaseType,
                errorMessage: errorMsg
            ), collector.collected)
        }

        return (PreviewFragmentResult(
            path: pdfPath, pageCount: renderer.pageCount, sections: sections,
            proofName: config.targetProofName, baseType: config.targetProofBaseType,
            errorMessage: nil
        ), collector.collected)
    }

    // MARK: - Handler Factory

    private static func makeHandler(proofName: String, proofKey: String, baseType: String) -> (any ProofHandler)? {
        switch baseType {
        case "filtered_character_set":
            return FilteredCharacterSetHandler(proofName: proofName, proofKey: proofKey)
        case "spacing_proof":
            return SpacingProofHandler(proofName: proofName, proofKey: proofKey)
        case "ar_character_set":
            return ArCharacterSetHandler(proofName: proofName, proofKey: proofKey)
        case "custom_text":
            return CustomTextProofHandler(proofName: proofName, proofKey: proofKey)
        case "substitution_overview":
            return SubstitutionOverviewHandler(proofName: proofName, proofKey: proofKey)
        case "multi_style_comparison":
            return MultiStyleComparisonHandler(proofName: proofName, proofKey: proofKey)
        case "version_comparison":
            return VersionComparisonHandler(proofName: proofName, proofKey: proofKey)
        default:
            if ProofRegistry.entry(forKey: baseType)?.textConfig != nil {
                return StandardTextProofHandler(proofName: proofName, proofKey: proofKey)
            }
            return nil
        }
    }

    // MARK: - Helpers

    private static func buildAxisCombinations(config: ProofConfig, fontPath: String) -> [[String: Double]] {
        guard let axisValues = config.axisValuesByFont[fontPath], !axisValues.isEmpty else {
            return [[:]]
        }

        var combinations: [[String: Double]] = [[:]]
        for (tag, values) in axisValues.sorted(by: { $0.key < $1.key }) {
            guard !values.isEmpty else { continue }
            var newCombinations: [[String: Double]] = []
            for combo in combinations {
                for val in values {
                    var newCombo = combo
                    newCombo[tag] = val
                    newCombinations.append(newCombo)
                }
            }
            combinations = newCombinations
        }
        return combinations
    }

    private static func extractOTFeatures(proofKey: String, settings: [String: Any]) -> [String: Bool] {
        let prefix = "otf_\(proofKey)_"
        var features: [String: Bool] = [:]
        for (key, value) in settings {
            if key.hasPrefix(prefix), let boolVal = value as? Bool {
                let tag = String(key.dropFirst(prefix.count))
                features[tag] = boolVal
            }
        }
        return features
    }

    private static func buildGlobalOTFeatures() -> [String: Bool] {
        var features: [String: Bool] = [:]
        for tag in DEFAULT_ON_FEATURES {
            features[tag] = true
        }
        return features
    }

    private static func settingsKey(for option: ProofOption) -> String {
        settingsKey(for: option.name, baseType: option.baseType)
    }

    private static func settingsKey(for name: String, baseType: String) -> String {
        if let entry = ProofRegistry.entry(forKey: baseType), name == entry.displayName {
            return baseType
        }
        return pythonProofKey(for: name)
    }
}
