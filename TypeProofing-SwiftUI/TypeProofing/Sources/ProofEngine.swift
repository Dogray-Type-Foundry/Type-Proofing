import Foundation
import CryptoKit
import CoreGraphics
import CoreText
import TPNative

// MARK: - Swift Data Models

struct FontInfo: Identifiable {
    let id: String           // file path
    let name: String
    let isVariable: Bool
    let axes: [FontAxis]
    let supportsArabic: Bool
    let familyName: String
    let weight: Int
    let width: Int
    let slant: Double
    let opticalSize: Double
}

struct FontAxis: Identifiable {
    let id: String           // tag, e.g. "wght"
    let name: String
    let minValue: Double
    let maxValue: Double
    let defaultValue: Double
    var currentValue: Double
    let instanceValues: [Double]  // named instance values for this axis (markers/snap)
}

struct ProofOption: Identifiable, Equatable {
    let id = UUID()
    var name: String
    var baseType: String     // original proof type key
    var enabled: Bool
    var order: Int
}

enum ProofCost: String, Codable {
    case fast
    case wordsiv
}

struct ProofRegistryEntry {
    let key: String
    let displayName: String
    let isArabic: Bool
    let defaultColumns: Int
    let hasParagraphs: Bool
    let defaultParagraphs: Int
    let defaultFontSize: Int
    let hasCustomText: Bool
    let hasCategories: Bool
    let isMultiStyle: Bool
    let defaultEnabled: Bool
    let displayOrder: Int
    let previewCost: ProofCost
    let hasTextConfig: Bool

    /// Proofs that don't support tracking/alignment/line height
    /// (character-set style proofs)
    private static let noFormattingKeys: Set<String> = [
        "filtered_character_set", "spacing_proof", "ar_character_set", "substitution_overview"
    ]

    var supportsFormatting: Bool {
        !Self.noFormattingKeys.contains(key)
    }

    var supportsCols: Bool {
        // Spacing proof supports columns but not other formatting
        supportsFormatting || key == "spacing_proof" || key == "substitution_overview"
    }

    var supportsLineHeight: Bool {
        !Self.noFormattingKeys.contains(key)
    }

    private static let hyphenationKeys: Set<String> = [
        "basic_paragraph_large", "basic_paragraph_small",
        "paired_styles_paragraph_small", "misc_paragraph_small",
        "generative_text_small"
    ]

    var supportsHyphenation: Bool {
        Self.hyphenationKeys.contains(key)
    }
}

// MARK: - Constants

let HIDDEN_FEATURES: Set<String> = [
    "init", "medi", "med2", "fina", "fin2", "fin3", "isol", "curs", "aalt", "rand"
]

let DEFAULT_ON_FEATURES: Set<String> = [
    "ccmp", "kern", "calt", "rlig", "liga", "mark", "mkmk",
    "clig", "dist", "rclt", "rvrn", "curs", "locl"
]

struct ProofSection: Equatable {
    let name: String
    let firstPage: Int   // 0-based page index
}

struct PreviewNavigationRequest: Equatable {
    let id = UUID()
    let proofID: ProofOption.ID
    let proofName: String
    let pageIndex: Int
}

struct PageFormatDimensions {
    let width: CGFloat
    let height: CGFloat
}

struct PreviewFragmentResult {
    let path: String
    let pageCount: Int
    let sections: [ProofSection]
    let proofName: String
    let baseType: String
    let errorMessage: String?
}

struct DiagnosticEvent: Identifiable, Equatable {
    let id = UUID()
    let level: String
    let category: String
    let message: String
    let fontPath: String?
    let proofName: String?
    let details: [String: String]
    let timestamp: String
}

struct ProofRunSummary: Equatable {
    var fontCount: Int = 0
    var enabledProofCount: Int = 0
    var enabledProofs: [String] = []
    var totalAxisInstances: Int = 0
    var estimatedWorkItems: Int = 0
    var pageFormat: String = ""
    var outputDir: String = ""
    var showBaselines: Bool = false
    var showFooter: Bool = true
    var warnings: [String] = []
}

struct GenerationProgress: Equatable {
    var proofName: String = ""
    var proofIndex: Int = 0
    var proofCount: Int = 0
    var fontPath: String = ""
    var fontIndex: Int = 0
    var fontCount: Int = 0
}

// MARK: - ProofConfig

struct ProofConfig {
    var fontPaths: [String]
    var axisValuesByFont: [String: [String: [Double]]]
    var proofOptions: [ProofOption]
    var proofSettings: [String: Any]
    var pageFormat: String
    var outputDir: String
    var showBaselines: Bool = false
    var showFooter: Bool = true
    var debugMode: Bool = false
    var previewMode: Bool = false
    var targetProofName: String = ""
    var targetProofBaseType: String = ""
    var fragmentOutputDir: String = ""

    func toDictionary() -> [String: Any] {
        let options = proofOptions.map { opt in
            [
                "Option": opt.name,
                "Enabled": opt.enabled,
                "_original_option": opt.baseType,
            ]
        }

        return [
            "font_paths": fontPaths,
            "axis_values_by_font": axisValuesByFont,
            "proof_options": options,
            "proof_settings": proofSettings,
            "page_format": pageFormat,
            "output_dir": outputDir,
            "show_baselines": showBaselines,
            "show_footer": showFooter,
            "debug_mode": debugMode,
            "preview_mode": previewMode,
            "target_proof_name": targetProofName,
            "target_proof_base_type": targetProofBaseType,
            "fragment_output_dir": fragmentOutputDir,
        ]
    }

    func fingerprint() -> String {
        guard let data = try? JSONSerialization.data(
            withJSONObject: toDictionary(),
            options: [.sortedKeys]
        ) else {
            return UUID().uuidString
        }
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    func previewFragmentConfig(
        proofName: String,
        baseType: String,
        outputDir: String
    ) -> ProofConfig {
        var copy = self
        copy.previewMode = true
        copy.targetProofName = proofName
        copy.targetProofBaseType = baseType
        copy.fragmentOutputDir = outputDir
        return copy
    }

}

// MARK: - ProofEngine

@MainActor
final class ProofEngine: ObservableObject {

    // ── Published state ─────────────────────────────────────────────────
    @Published var isReady = false
    @Published var isGenerating = false
    @Published var lastPDFPath: String?
    @Published var errorMessage: String?
    @Published var diagnostics: [DiagnosticEvent] = []
    @Published var generationProgress: GenerationProgress?
    @Published var proofRunSummary: ProofRunSummary?
    @Published var debugMode = false
    @Published private(set) var proofRegistryCount = 0

    private var generationTask: Task<(result: NativeProofOrchestrator.Result?, diagnostics: [DiagnosticEvent]), Never>?

    // ── Lifecycle ───────────────────────────────────────────────────────

    init() {
        Task { await self.bootstrap() }
    }

    private func bootstrap() async {
        self.proofRegistryCount = ProofRegistry.entries.count
        print("Native engine loaded — \(proofRegistryCount) proof types")
        self.isReady = true
    }

    // MARK: - Proof Generation

    func generateProof(config: ProofConfig) async -> (path: String, sections: [ProofSection], wasCancelled: Bool)? {
        isGenerating = true
        errorMessage = nil
        diagnostics.removeAll()
        generationProgress = nil
        defer { isGenerating = false }

        await Task.yield()

        var config = config
        config.debugMode = debugMode

        let task = Task.detached(priority: .userInitiated) {
            NativeProofOrchestrator.generate(
                config: config,
                progress: { progress in
                    Task { @MainActor in self.generationProgress = progress }
                },
                isCancelled: { Task.isCancelled }
            )
        }
        generationTask = task
        let output = await task.value
        let wasCancelled = task.isCancelled
        generationTask = nil

        diagnostics.append(contentsOf: output.diagnostics)

        guard let result = output.result else {
            if !wasCancelled {
                errorMessage = output.diagnostics.first(where: { $0.level == "error" })?.message
                    ?? "Proof generation produced no output"
            }
            return nil
        }

        lastPDFPath = result.path
        generationProgress = nil
        return (path: result.path, sections: result.sections, wasCancelled: wasCancelled)
    }

    func cancelGeneration() {
        generationTask?.cancel()
        generationTask = nil
        diagnostics.append(DiagnosticEvent(
            level: "info",
            category: "cancelled",
            message: "Generation cancelled.",
            fontPath: nil,
            proofName: nil,
            details: [:],
            timestamp: ""
        ))
    }

    func refreshRunSummary(config: ProofConfig) {
        let enabledProofs = config.proofOptions.filter(\.enabled)
        let fontCount = config.fontPaths.count

        var totalInstances = 0
        for path in config.fontPaths {
            if let axisValues = config.axisValuesByFont[path], !axisValues.isEmpty {
                var combos = 1
                for (_, values) in axisValues {
                    combos *= max(1, values.count)
                }
                totalInstances += combos
            } else {
                totalInstances += 1
            }
        }

        let estimatedItems = totalInstances * enabledProofs.count

        var warnings: [String] = []
        if fontCount == 0 {
            warnings.append("No fonts loaded")
        }
        if enabledProofs.isEmpty {
            warnings.append("No proofs enabled")
        }

        proofRunSummary = ProofRunSummary(
            fontCount: fontCount,
            enabledProofCount: enabledProofs.count,
            enabledProofs: enabledProofs.map(\.name),
            totalAxisInstances: totalInstances,
            estimatedWorkItems: estimatedItems,
            pageFormat: config.pageFormat,
            outputDir: config.outputDir,
            showBaselines: config.showBaselines,
            warnings: warnings
        )
    }

    func generatePreviewFragment(config: ProofConfig, timeoutSeconds: TimeInterval) async -> (fragment: PreviewFragmentResult?, diagnostics: [DiagnosticEvent]) {
        // The detached worker doesn't inherit the caller's cancellation, so
        // forward it explicitly — `isCancelled` checks the worker's own flag.
        let worker = Task.detached(priority: .userInitiated) {
            NativeProofOrchestrator.generateFragment(
                config: config,
                isCancelled: { Task.isCancelled }
            )
        }
        let output = await withTaskCancellationHandler(operation: {
            await worker.value
        }, onCancel: {
            worker.cancel()
        })

        return (output.fragment, output.diagnostics)
    }

    // MARK: - Font Queries

    private func loadFontData(path: String) -> (info: UnsafeMutablePointer<TPFontInfo>, charset: String, axesJSON: String)? {
        FontLoader.withFontBytes(path: path, fallback: nil) { ptr, len -> (UnsafeMutablePointer<TPFontInfo>, String, String)? in
            guard let infoPtr = tp_load_font(ptr, len) else { return nil }

            let charsetPtr = tp_get_charset(ptr, len)
            let charset = charsetPtr != nil ? String(cString: charsetPtr!) : ""
            if charsetPtr != nil { wsv_free_string(charsetPtr) }

            let axesPtr = tp_get_axes_json(ptr, len)
            let axesJSON = axesPtr != nil ? String(cString: axesPtr!) : "[]"
            if axesPtr != nil { wsv_free_string(axesPtr) }

            return (infoPtr, charset, axesJSON)
        }
    }

    func getFontMetadata(paths: [String]) -> [FontInfo] {
        paths.compactMap { path -> FontInfo? in
            guard let (infoPtr, charset, axesJSON) = loadFontData(path: path) else { return nil }
            defer { tp_free_font_info(infoPtr) }
            let info = infoPtr.pointee

            let familyName = info.family_name != nil ? String(cString: info.family_name) : ""
            let name = URL(fileURLWithPath: path).deletingPathExtension().lastPathComponent

            var axes: [FontAxis] = []
            if let axesData = info.axes_json != nil ? String(cString: info.axes_json).data(using: .utf8) : nil,
               let axesArray = try? JSONSerialization.jsonObject(with: axesData) as? [[String: Any]] {
                // Parse named instance values from tp_get_axes_json
                var instanceValuesByTag: [String: [Double]] = [:]
                if let genData = axesJSON.data(using: .utf8),
                   let genArray = try? JSONSerialization.jsonObject(with: genData) as? [[String: Any]] {
                    for item in genArray {
                        if let tag = item["tag"] as? String, let vals = item["values"] as? [Double] {
                            instanceValuesByTag[tag] = vals
                        }
                    }
                }

                for axisDict in axesArray {
                    guard let tag = axisDict["tag"] as? String,
                          let minVal = (axisDict["min"] as? NSNumber)?.doubleValue,
                          let maxVal = (axisDict["max"] as? NSNumber)?.doubleValue,
                          let defVal = (axisDict["default"] as? NSNumber)?.doubleValue else { continue }
                    axes.append(FontAxis(
                        id: tag, name: tag,
                        minValue: minVal, maxValue: maxVal,
                        defaultValue: defVal, currentValue: defVal,
                        instanceValues: instanceValuesByTag[tag] ?? []
                    ))
                }
            }

            let supportsArabic = charset.unicodeScalars.contains { s in
                (0x0600...0x06FF).contains(s.value) || (0x0750...0x077F).contains(s.value) ||
                (0xFB50...0xFDFF).contains(s.value) || (0xFE70...0xFEFF).contains(s.value)
            }

            return FontInfo(
                id: path, name: name, isVariable: info.is_variable,
                axes: axes, supportsArabic: supportsArabic,
                familyName: familyName, weight: Int(info.weight),
                width: Int(info.width), slant: info.slant, opticalSize: info.optical_size
            )
        }
    }

    func getAvailableOTFeatures(path: String) -> [String] {
        FontLoader.withFontBytes(path: path, fallback: []) { ptr, len -> [String] in
            guard let infoPtr = tp_load_font(ptr, len) else { return [] }
            defer { tp_free_font_info(infoPtr) }
            guard let json = infoPtr.pointee.features_json else { return [] }
            let jsonStr = String(cString: json)
            guard let jsonData = jsonStr.data(using: .utf8),
                  let array = try? JSONSerialization.jsonObject(with: jsonData) as? [String] else { return [] }
            return array
        }
    }

    func getAvailableSubstitutionFeatures(path: String) -> [String] {
        SubstitutionBridge.getSubstitutions(fontPath: path).map(\.tag)
    }

    // MARK: - Config Queries

    func getProofRegistry() -> [ProofRegistryEntry] {
        let order = ProofRegistry.defaultProofOrder
        return order.compactMap { key -> ProofRegistryEntry? in
            guard let info = ProofRegistry.entry(forKey: key) else { return nil }
            let displayOrder = order.firstIndex(of: key) ?? 999
            let cost: ProofCost = info.textConfig?.forceWordsiv == true ? .wordsiv : .fast
            return ProofRegistryEntry(
                key: key,
                displayName: info.displayName,
                isArabic: info.isArabic,
                defaultColumns: info.defaultCols,
                hasParagraphs: info.hasParagraphs,
                defaultParagraphs: info.textConfig?.defaultParagraphs ?? (info.hasParagraphs ? 5 : 2),
                defaultFontSize: info.defaultSize,
                hasCustomText: info.hasCustomText,
                hasCategories: info.hasCategories,
                isMultiStyle: info.multiStyle,
                defaultEnabled: info.defaultEnabled,
                displayOrder: displayOrder,
                previewCost: cost,
                hasTextConfig: info.textConfig != nil
            )
        }
    }

    func getPageFormats() -> [String] {
        PageLayout.pageFormatOrder
    }

    func getPageFormatDimensions() -> [String: PageFormatDimensions] {
        PageLayout.pageDimensions.mapValues { size in
            PageFormatDimensions(width: size.width, height: size.height)
        }
    }

    func getDefaultProofOrder(includeArabic: Bool = true) -> [String] {
        ProofRegistry.defaultProofOrder(includeArabic: includeArabic)
    }

    func generateRandomWords(fontPath: String, paragraphs: Int = 3) -> String {
        guard let (infoPtr, charset, _) = loadFontData(path: fontPath) else { return "" }
        tp_free_font_info(infoPtr)
        let bridge = WordSivBridge(seed: UInt64.random(in: 0..<UInt64.max))
        return bridge.text(glyphs: charset, paragraphs: paragraphs)
    }

    /// Fetches the plain-text extract of a random Wikipedia article in the given
    /// language (e.g. "en", "ar", "fa"). Returns nil on any network/parse error.
    /// Capped to a few paragraphs so a single proof doesn't balloon.
    func fetchWikipediaText(language: String) async -> String? {
        let lang = language.isEmpty ? "en" : language
        var components = URLComponents(string: "https://\(lang).wikipedia.org/w/api.php")
        components?.queryItems = [
            URLQueryItem(name: "action", value: "query"),
            URLQueryItem(name: "format", value: "json"),
            URLQueryItem(name: "generator", value: "random"),
            URLQueryItem(name: "grnnamespace", value: "0"),
            URLQueryItem(name: "grnlimit", value: "1"),
            URLQueryItem(name: "prop", value: "extracts"),
            URLQueryItem(name: "explaintext", value: "1"),
            URLQueryItem(name: "exsectionformat", value: "plain"),
        ]
        guard let url = components?.url else { return nil }

        var request = URLRequest(url: url)
        request.setValue("TypeProofing/2.0 (type@jmsole.cl)", forHTTPHeaderField: "User-Agent")

        guard let (data, _) = try? await URLSession.shared.data(for: request),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let query = json["query"] as? [String: Any],
              let pages = query["pages"] as? [String: Any],
              let page = pages.values.first as? [String: Any],
              let extract = page["extract"] as? String else {
            return nil
        }

        let trimmed = extract.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return nil }
        if trimmed.count <= 1800 { return trimmed }
        let clipped = trimmed.prefix(1800)
        if let lastSpace = clipped.lastIndex(of: " ") {
            return String(clipped[..<lastSpace])
        }
        return String(clipped)
    }

    func getFontStyles(
        paths: [String],
        mode: StyleSourceMode = .namedInstances,
        axisValuesByFont: [String: [String: [Double]]] = [:]
    ) -> [FontStyleEntry] {
        var entries: [FontStyleEntry] = []
        var globalIndex = 0

        for path in paths {
            guard let data = FontLoader.fontData(path: path) else { continue }
            let rustInfo: (familyName: String, subfamilyName: String, isVariable: Bool) = data.withUnsafeBytes { buffer in
                guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self),
                      let infoPtr = tp_load_font(ptr, UInt(buffer.count)) else {
                    return ("", "", false)
                }
                defer { tp_free_font_info(infoPtr) }
                let info = infoPtr.pointee
                let family = info.family_name != nil ? String(cString: info.family_name) : ""
                let sub = info.subfamily_name != nil ? String(cString: info.subfamily_name) : "Regular"
                return (family, sub, info.is_variable)
            }

            if !rustInfo.isVariable {
                entries.append(FontStyleEntry(
                    index: globalIndex, fontPath: path,
                    familyName: rustInfo.familyName, styleName: rustInfo.subfamilyName,
                    isVariable: false, coordinates: nil
                ))
                globalIndex += 1
                continue
            }

            switch mode {
            case .namedInstances:
                let instanceEntries = namedInstanceEntries(data: data, path: path, familyName: rustInfo.familyName, subfamilyName: rustInfo.subfamilyName, globalIndex: &globalIndex)
                entries.append(contentsOf: instanceEntries)

            case .customPositions:
                let customEntries = customPositionEntries(data: data, path: path, familyName: rustInfo.familyName, subfamilyName: rustInfo.subfamilyName, axisValues: axisValuesByFont[path], globalIndex: &globalIndex)
                entries.append(contentsOf: customEntries)
            }
        }
        return entries
    }

    private func namedInstanceEntries(data: Data, path: String, familyName: String, subfamilyName: String, globalIndex: inout Int) -> [FontStyleEntry] {
        let instances: [[String: Any]]? = data.withUnsafeBytes { buffer in
            guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self),
                  let jsonPtr = tp_get_named_instances_json(ptr, UInt(buffer.count)) else { return nil }
            defer { wsv_free_string(jsonPtr) }
            let jsonStr = String(cString: jsonPtr)
            guard let jsonData = jsonStr.data(using: .utf8),
                  let arr = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] else { return nil }
            return arr
        }

        guard let instances, !instances.isEmpty else {
            let entry = FontStyleEntry(
                index: globalIndex, fontPath: path,
                familyName: familyName, styleName: subfamilyName,
                isVariable: true, coordinates: nil
            )
            globalIndex += 1
            return [entry]
        }

        var entries: [FontStyleEntry] = []
        for inst in instances {
            let name = inst["name"] as? String ?? ""
            let coordsDict = inst["coordinates"] as? [String: Double] ?? [:]
            entries.append(FontStyleEntry(
                index: globalIndex, fontPath: path,
                familyName: familyName, styleName: name,
                isVariable: true, coordinates: coordsDict
            ))
            globalIndex += 1
        }
        return entries
    }

    private func customPositionEntries(data: Data, path: String, familyName: String, subfamilyName: String, axisValues: [String: [Double]]?, globalIndex: inout Int) -> [FontStyleEntry] {
        var axisArrays: [(tag: String, values: [Double])] = []

        if let userValues = axisValues, !userValues.isEmpty {
            for (tag, values) in userValues.sorted(by: { $0.key < $1.key }) {
                axisArrays.append((tag, values))
            }
        }

        if axisArrays.isEmpty {
            let entry = FontStyleEntry(
                index: globalIndex, fontPath: path,
                familyName: familyName, styleName: subfamilyName,
                isVariable: true, coordinates: nil
            )
            globalIndex += 1
            return [entry]
        }

        var combinations: [[(String, Double)]] = [[]]
        for (tag, values) in axisArrays {
            var next: [[(String, Double)]] = []
            for combo in combinations {
                for val in values {
                    next.append(combo + [(tag, val)])
                }
            }
            combinations = next
        }

        var entries: [FontStyleEntry] = []
        for combo in combinations {
            let coords = Dictionary(uniqueKeysWithValues: combo)
            let styleParts = combo.map { "\($0.0)=\(Int($0.1))" }
            let styleName = styleParts.joined(separator: " ")
            entries.append(FontStyleEntry(
                index: globalIndex, fontPath: path,
                familyName: familyName, styleName: styleName,
                isVariable: true, coordinates: coords
            ))
            globalIndex += 1
        }
        return entries
    }
}
