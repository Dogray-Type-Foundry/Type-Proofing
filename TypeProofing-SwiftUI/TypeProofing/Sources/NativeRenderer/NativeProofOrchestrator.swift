import CoreGraphics
import Foundation
import TPNative

struct NativeProofOrchestrator {

    struct Result {
        let path: String
        let sections: [ProofSection]
    }

    static func generate(
        config: ProofConfig,
        progress: @Sendable (GenerationProgress) -> Void,
        isCancelled: @Sendable () -> Bool
    ) -> Result? {
        MultiStyleComparisonHandler.resetGenerated()
        let enabledProofs = config.proofOptions.filter(\.enabled)
        guard !config.fontPaths.isEmpty, !enabledProofs.isEmpty else { return nil }

        let outputDir = config.outputDir.isEmpty
            ? FileManager.default.temporaryDirectory.path
            : config.outputDir
        let timestamp = ISO8601DateFormatter().string(from: Date())
            .replacingOccurrences(of: ":", with: "-")
        let pdfPath = (outputDir as NSString).appendingPathComponent("TypeProofing_\(timestamp).pdf")

        let pageSize = PageLayout.pageDimensions[config.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let mediaBox = CGRect(origin: .zero, size: pageSize)
        let renderer = PDFRenderer(url: URL(fileURLWithPath: pdfPath), mediaBox: mediaBox)

        var sections: [ProofSection] = []
        let fontCount = config.fontPaths.count

        for (fontIndex, fontPath) in config.fontPaths.enumerated() {
            if isCancelled() { break }

            guard let fontData = try? Data(contentsOf: URL(fileURLWithPath: fontPath)) else { continue }
            let charset = fontData.withUnsafeBytes { buffer -> String in
                guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return "" }
                guard let charsetPtr = tp_get_charset(ptr, UInt(buffer.count)) else { return "" }
                defer { wsv_free_string(charsetPtr) }
                return String(cString: charsetPtr)
            }
            let cat = CharacterCategorizer.categorize(charset: charset)

            let axisCombinations = buildAxisCombinations(config: config, fontPath: fontPath)

            for axisValues in axisCombinations {
                if isCancelled() { break }

                let globalFeatures = buildGlobalOTFeatures(config: config)

                for (proofIndex, option) in enabledProofs.enumerated() {
                    if isCancelled() { break }

                    progress(GenerationProgress(
                        proofName: option.name,
                        proofIndex: proofIndex,
                        proofCount: enabledProofs.count,
                        fontPath: fontPath,
                        fontIndex: fontIndex,
                        fontCount: fontCount
                    ))

                    let proofKey = settingsKey(for: option)
                    let perProofFeatures = extractOTFeatures(proofKey: proofKey, settings: config.proofSettings)
                    let otFeatures = perProofFeatures.isEmpty ? globalFeatures : perProofFeatures

                    let proofContext = ProofContext(
                        fullCharacterSet: charset,
                        indFont: fontPath,
                        axisValues: axisValues.isEmpty ? nil : axisValues,
                        otFeatures: otFeatures,
                        cat: cat,
                        pageFormat: config.pageFormat,
                        proofSettings: config.proofSettings,
                        showBaselines: config.showBaselines,
                        allAxisValues: config.axisValuesByFont[fontPath],
                        allFontPaths: config.fontPaths,
                        axisValuesByFont: config.axisValuesByFont
                    )

                    let pagesBefore = renderer.pageCount
                    if let handler = makeHandler(proofName: option.name, proofKey: proofKey, baseType: option.baseType) {
                        handler.generateProof(context: proofContext, renderer: renderer)
                    }
                    if renderer.pageCount > pagesBefore {
                        sections.append(ProofSection(name: option.name, firstPage: pagesBefore))
                    }
                }
            }
        }

        renderer.close()

        if renderer.pageCount == 0 {
            try? FileManager.default.removeItem(atPath: pdfPath)
            return nil
        }

        return Result(path: pdfPath, sections: sections)
    }

    static func generateFragment(
        config: ProofConfig,
        isCancelled: @Sendable () -> Bool
    ) -> PreviewFragmentResult? {
        guard !config.fontPaths.isEmpty else { return nil }

        MultiStyleComparisonHandler.resetGenerated()

        let outputDir = config.fragmentOutputDir.isEmpty
            ? FileManager.default.temporaryDirectory.path
            : config.fragmentOutputDir
        let pdfPath = (outputDir as NSString).appendingPathComponent("preview_\(UUID().uuidString).pdf")

        let pageSize = PageLayout.pageDimensions[config.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let mediaBox = CGRect(origin: .zero, size: pageSize)
        let renderer = PDFRenderer(url: URL(fileURLWithPath: pdfPath), mediaBox: mediaBox)

        let proofKey = settingsKey(for: config.targetProofName, baseType: config.targetProofBaseType)
        let globalFeatures = buildGlobalOTFeatures(config: config)
        let perProofFeatures = extractOTFeatures(proofKey: proofKey, settings: config.proofSettings)
        let otFeatures = perProofFeatures.isEmpty ? globalFeatures : perProofFeatures

        var sections: [ProofSection] = []

        for fontPath in config.fontPaths {
            if isCancelled() { break }

            guard let fontData = try? Data(contentsOf: URL(fileURLWithPath: fontPath)) else { continue }
            let charset = fontData.withUnsafeBytes { buffer -> String in
                guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return "" }
                guard let charsetPtr = tp_get_charset(ptr, UInt(buffer.count)) else { return "" }
                defer { wsv_free_string(charsetPtr) }
                return String(cString: charsetPtr)
            }
            let cat = CharacterCategorizer.categorize(charset: charset)

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
                    allAxisValues: config.axisValuesByFont[fontPath],
                    allFontPaths: config.fontPaths,
                    axisValuesByFont: config.axisValuesByFont
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
            return PreviewFragmentResult(
                path: "", pageCount: 0, sections: [],
                proofName: config.targetProofName, baseType: config.targetProofBaseType,
                errorMessage: nil
            )
        }

        return PreviewFragmentResult(
            path: pdfPath, pageCount: renderer.pageCount, sections: sections,
            proofName: config.targetProofName, baseType: config.targetProofBaseType,
            errorMessage: nil
        )
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

    private static func buildGlobalOTFeatures(config: ProofConfig) -> [String: Bool] {
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
