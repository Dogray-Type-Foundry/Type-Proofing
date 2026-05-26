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
    let hasSettings: Bool
    let defaultColumns: Int
    let hasParagraphs: Bool
    let defaultFontSize: Int
    let hasCustomText: Bool
    let hasCategories: Bool
    let isMultiStyle: Bool
    let defaultEnabled: Bool
    let displayOrder: Int
    let previewCost: ProofCost

    /// Proofs that don't support tracking/alignment (character-set style proofs)
    private static let noFormattingKeys: Set<String> = [
        "filtered_character_set", "spacing_proof", "ar_character_set", "substitution_overview"
    ]

    /// Proofs that don't support line height
    private static let noLineHeightKeys: Set<String> = [
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
        !Self.noLineHeightKeys.contains(key)
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

    static func fromDictionary(_ dict: [String: Any]) -> DiagnosticEvent? {
        guard let level = dict["level"] as? String,
              let category = dict["category"] as? String,
              let message = dict["message"] as? String else { return nil }
        let rawDetails = dict["details"] as? [String: Any] ?? [:]
        return DiagnosticEvent(
            level: level,
            category: category,
            message: message,
            fontPath: dict["font_path"] as? String,
            proofName: dict["proof_name"] as? String,
            details: rawDetails.mapValues(Self.stringifyDetailValue),
            timestamp: dict["timestamp"] as? String ?? ""
        )
    }

    private static func stringifyDetailValue(_ value: Any) -> String {
        if let string = value as? String {
            return string
        }
        if value is NSNull {
            return "null"
        }
        if let number = value as? NSNumber {
            if CFGetTypeID(number) == CFBooleanGetTypeID() {
                return number.boolValue ? "true" : "false"
            }
            return number.stringValue
        }
        if JSONSerialization.isValidJSONObject(value),
           let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
           let string = String(data: data, encoding: .utf8) {
            return string
        }
        return String(describing: value)
    }
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
    var warnings: [String] = []

    static func fromDictionary(_ dict: [String: Any]) -> ProofRunSummary {
        ProofRunSummary(
            fontCount: dict["font_count"] as? Int ?? 0,
            enabledProofCount: dict["enabled_proof_count"] as? Int ?? 0,
            enabledProofs: dict["enabled_proofs"] as? [String] ?? [],
            totalAxisInstances: dict["total_axis_instances"] as? Int ?? 0,
            estimatedWorkItems: dict["estimated_work_items"] as? Int ?? 0,
            pageFormat: dict["page_format"] as? String ?? "",
            outputDir: dict["output_dir"] as? String ?? "",
            showBaselines: dict["show_baselines"] as? Bool ?? false,
            warnings: dict["warnings"] as? [String] ?? []
        )
    }
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
            "debug_mode": debugMode,
            "preview_mode": previewMode,
            "target_proof_name": targetProofName,
            "target_proof_base_type": targetProofBaseType,
            "fragment_output_dir": fragmentOutputDir,
        ]
    }

    func toJSONData() throws -> Data {
        try JSONSerialization.data(withJSONObject: toDictionary(), options: [])
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
    var usesWorkerGeneration = true

    private var generationTask: Task<Void, Never>?

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

    func generateProof(config: ProofConfig) async -> (path: String, sections: [ProofSection])? {
        isGenerating = true
        errorMessage = nil
        diagnostics.removeAll()
        generationProgress = nil
        defer { isGenerating = false }

        await Task.yield()

        var config = config
        config.debugMode = debugMode

        let output = await Task.detached(priority: .userInitiated) {
            NativeProofOrchestrator.generate(
                config: config,
                progress: { progress in
                    Task { @MainActor in self.generationProgress = progress }
                },
                isCancelled: { Task.isCancelled }
            )
        }.value

        diagnostics.append(contentsOf: output.diagnostics)

        guard let result = output.result else {
            if !Task.isCancelled {
                errorMessage = output.diagnostics.first(where: { $0.level == "error" })?.message
                    ?? "Proof generation produced no output"
            }
            return nil
        }

        lastPDFPath = result.path
        generationProgress = nil
        return (path: result.path, sections: result.sections)
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
        let output = await withTaskCancellationHandler(operation: {
            await Task.detached(priority: .userInitiated) {
                NativeProofOrchestrator.generateFragment(
                    config: config,
                    isCancelled: { Task.isCancelled }
                )
            }.value
        }, onCancel: { })

        return (output.fragment, output.diagnostics)
    }

    // MARK: - Font Queries

    private var fontInfoCache: [String: (info: TPFontInfo, charset: String, axesJSON: String)] = [:]

    private func loadFontData(path: String) -> (info: UnsafeMutablePointer<TPFontInfo>, charset: String, axesJSON: String)? {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return nil }
        return data.withUnsafeBytes { buffer -> (UnsafeMutablePointer<TPFontInfo>, String, String)? in
            guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return nil }
            let len = UInt(buffer.count)
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

    func getFontAxes(path: String) -> [FontAxis] {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return [] }
        return data.withUnsafeBytes { buffer -> [FontAxis] in
            guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return [] }
            guard let infoPtr = tp_load_font(ptr, UInt(buffer.count)) else { return [] }
            defer { tp_free_font_info(infoPtr) }
            let info = infoPtr.pointee
            guard let json = info.axes_json else { return [] }
            let jsonStr = String(cString: json)
            guard let jsonData = jsonStr.data(using: .utf8),
                  let array = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] else { return [] }
            return array.compactMap { dict -> FontAxis? in
                guard let tag = dict["tag"] as? String,
                      let minVal = (dict["min"] as? NSNumber)?.doubleValue,
                      let maxVal = (dict["max"] as? NSNumber)?.doubleValue,
                      let defVal = (dict["default"] as? NSNumber)?.doubleValue else { return nil }
                return FontAxis(id: tag, name: tag, minValue: minVal, maxValue: maxVal,
                                defaultValue: defVal, currentValue: defVal, instanceValues: [])
            }
        }
    }

    func getAvailableOTFeatures(path: String) -> [String] {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return [] }
        return data.withUnsafeBytes { buffer -> [String] in
            guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return [] }
            guard let infoPtr = tp_load_font(ptr, UInt(buffer.count)) else { return [] }
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
                hasSettings: info.hasSettings,
                defaultColumns: info.defaultCols,
                hasParagraphs: info.hasParagraphs,
                defaultFontSize: info.defaultSize,
                hasCustomText: info.hasCustomText,
                hasCategories: info.hasCategories,
                isMultiStyle: info.multiStyle,
                defaultEnabled: info.defaultEnabled,
                displayOrder: displayOrder,
                previewCost: cost
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

    func generateWordomat(fontPath: String, paragraphs: Int = 3) -> String {
        guard let (_, charset, _) = loadFontData(path: fontPath) else { return "" }
        let bridge = WordSivBridge(seed: UInt64.random(in: 0..<UInt64.max))
        return bridge.text(glyphs: charset, paragraphs: paragraphs)
    }

    func getFontStyles(paths: [String]) -> [FontStyleEntry] {
        var entries: [FontStyleEntry] = []
        var globalIndex = 0

        for path in paths {
            guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { continue }
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

            // Variable font: enumerate named instances via CoreText
            let url = URL(fileURLWithPath: path) as CFURL
            guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url) as? [CTFontDescriptor],
                  let desc = descriptors.first else {
                entries.append(FontStyleEntry(
                    index: globalIndex, fontPath: path,
                    familyName: rustInfo.familyName, styleName: rustInfo.subfamilyName,
                    isVariable: true, coordinates: nil
                ))
                globalIndex += 1
                continue
            }

            let ctFont = CTFontCreateWithFontDescriptor(desc, 12, nil)
            guard let ctAxes = CTFontCopyVariationAxes(ctFont) as? [[String: Any]] else {
                entries.append(FontStyleEntry(
                    index: globalIndex, fontPath: path,
                    familyName: rustInfo.familyName, styleName: rustInfo.subfamilyName,
                    isVariable: true, coordinates: nil
                ))
                globalIndex += 1
                continue
            }

            // Map axis identifiers to tag strings
            let axisIDToTag: [Int: String] = Dictionary(uniqueKeysWithValues: ctAxes.compactMap { axis -> (Int, String)? in
                guard let id = axis[kCTFontVariationAxisIdentifierKey as String] as? Int,
                      let tag = axis[kCTFontVariationAxisNameKey as String] as? String else { return nil }
                // Convert 4-byte int ID to tag string
                let tagStr = String(UnicodeScalar((id >> 24) & 0xFF)!) +
                             String(UnicodeScalar((id >> 16) & 0xFF)!) +
                             String(UnicodeScalar((id >> 8) & 0xFF)!) +
                             String(UnicodeScalar(id & 0xFF)!)
                return (id, tagStr)
            })

            // Get named instances from the fvar table via CoreText
            // CoreText doesn't directly expose named instances, but we can use the font's variation data
            // Use the Rust axes JSON which has generation values (min, [default], max)
            if let genData = data.withUnsafeBytes({ buffer -> String? in
                guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return nil }
                guard let jsonPtr = tp_get_axes_json(ptr, UInt(buffer.count)) else { return nil }
                defer { wsv_free_string(jsonPtr) }
                return String(cString: jsonPtr)
            }), let jsonData = genData.data(using: .utf8),
               let genAxes = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] {

                // Build the Cartesian product of all axis values to create "instances"
                var axisValuesArrays: [(tag: String, values: [Double])] = []
                for axis in genAxes {
                    guard let tag = axis["tag"] as? String,
                          let values = axis["values"] as? [Double] else { continue }
                    axisValuesArrays.append((tag, values))
                }

                // Cartesian product
                var combinations: [[(String, Double)]] = [[]]
                for (tag, values) in axisValuesArrays {
                    var newCombinations: [[(String, Double)]] = []
                    for combo in combinations {
                        for val in values {
                            newCombinations.append(combo + [(tag, val)])
                        }
                    }
                    combinations = newCombinations
                }

                for combo in combinations {
                    let coords = Dictionary(uniqueKeysWithValues: combo)
                    let styleParts = combo.map { "\($0.0)=\(Int($0.1))" }
                    let styleName = styleParts.joined(separator: " ")
                    entries.append(FontStyleEntry(
                        index: globalIndex, fontPath: path,
                        familyName: rustInfo.familyName, styleName: styleName,
                        isVariable: true, coordinates: coords
                    ))
                    globalIndex += 1
                }
            } else {
                entries.append(FontStyleEntry(
                    index: globalIndex, fontPath: path,
                    familyName: rustInfo.familyName, styleName: rustInfo.subfamilyName,
                    isVariable: true, coordinates: nil
                ))
                globalIndex += 1
            }
        }
        return entries
    }
}
