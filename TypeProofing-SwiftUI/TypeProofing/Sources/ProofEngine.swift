import Foundation
import PythonKit

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

    /// Proofs that don't support tracking/alignment (character-set style proofs)
    private static let noFormattingKeys: Set<String> = [
        "filtered_character_set", "spacing_proof", "ar_character_set"
    ]

    /// Proofs that don't support line height
    private static let noLineHeightKeys: Set<String> = [
        "filtered_character_set", "spacing_proof", "ar_character_set"
    ]

    var supportsFormatting: Bool {
        !Self.noFormattingKeys.contains(key)
    }

    var supportsCols: Bool {
        // Spacing proof supports columns but not other formatting
        supportsFormatting || key == "spacing_proof"
    }

    var supportsLineHeight: Bool {
        !Self.noLineHeightKeys.contains(key)
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

struct ProofSection {
    let name: String
    let firstPage: Int   // 0-based page index
}

// MARK: - ProofConfig

struct ProofConfig {
    var fontPaths: [String]
    var axisValuesByFont: [String: [String: [Double]]]
    var proofOptions: [ProofOption]
    var proofSettings: [String: PythonObject]
    var pageFormat: String
    var outputDir: String
    var showBaselines: Bool = false

    /// Convert the whole config into a Python dict for `engine.generate_proof()`.
    func toPythonDict() -> PythonObject {
        // proof_options list[dict]
        let pyOptions: [PythonObject] = proofOptions.map { opt in
            let d: [String: PythonObject] = [
                "Option": PythonObject(opt.name),
                "Enabled": PythonObject(opt.enabled),
                "_original_option": PythonObject(opt.baseType),
            ]
            return PythonObject(d)
        }

        // axis_values_by_font dict[str, dict[str, list]]
        var pyAxes = [String: PythonObject]()
        for (fontPath, axes) in axisValuesByFont {
            var inner = [String: PythonObject]()
            for (tag, values) in axes {
                inner[tag] = PythonObject(values)
            }
            pyAxes[fontPath] = PythonObject(inner)
        }

        let configDict: [String: PythonObject] = [
            "font_paths": PythonObject(fontPaths),
            "axis_values_by_font": PythonObject(pyAxes),
            "proof_options": PythonObject(pyOptions),
            "proof_settings": PythonObject(proofSettings),
            "page_format": PythonObject(pageFormat),
            "output_dir": PythonObject(outputDir),
            "show_baselines": PythonObject(showBaselines),
        ]
        return PythonObject(configDict)
    }
}

// MARK: - ProofEngine

/// The **only** Swift file that imports PythonKit. Every SwiftUI view talks
/// to `ProofEngine`; never directly to Python.
@MainActor
final class ProofEngine: ObservableObject {

    // ── Published state ─────────────────────────────────────────────────
    @Published var isReady = false
    @Published var isGenerating = false
    @Published var lastPDFPath: String?
    @Published var errorMessage: String?
    @Published private(set) var proofRegistryCount = 0

    // ── Python modules (lazy-loaded after init) ─────────────────────────
    private var engineModule: PythonObject?
    private var configModule: PythonObject?
    private var fontsModule: PythonObject?

    // ── Lifecycle ───────────────────────────────────────────────────────

    init() {
        // Run initialization off the main actor to avoid blocking launch
        Task { await self.bootstrap() }
    }

    private func bootstrap() async {
        do {
            PythonSetup.initialize()

            let engine  = Python.import("engine")
            let config  = Python.import("config")
            let fonts   = Python.import("fonts")

            self.engineModule = engine
            self.configModule = config
            self.fontsModule  = fonts

            // Quick sanity check — ask for the registry size
            let registry = engine.get_proof_registry()
            let count = Int(Python.len(registry)) ?? 0
            self.proofRegistryCount = count

            print("Python engine loaded — \(count) proof types")
            self.isReady = true
        } catch {
            let msg = "Python init failed: \(error)"
            print(msg)
            self.errorMessage = msg
        }
    }

    // MARK: - Proof Generation

    /// Generate a proof PDF and return its path (or `nil` on failure).
    ///
    /// All PythonKit calls MUST stay on the main thread (which holds the
    /// Python GIL). Using Task.detached would move work to a cooperative
    /// background thread and crash with SIGSEGV inside _PyObject_Malloc.
    func generateProof(config: ProofConfig) async -> (path: String, sections: [ProofSection])? {
        guard let engine = engineModule else { return nil }

        isGenerating = true
        errorMessage = nil
        defer { isGenerating = false }

        // Yield once so SwiftUI can redraw the spinner, then run Python
        // synchronously on the main actor (which owns the GIL).
        await Task.yield()

        let pyDict = config.toPythonDict()
        let result = engine.generate_proof(pyDict)

        // Parse dict return: {"path": str, "sections": [{"name": str, "first_page": int}, ...]}
        guard let path = String(result["path"]),
              !path.isEmpty, path != "None" else {
            errorMessage = "Proof generation failed"
            return nil
        }

        var sections: [ProofSection] = []
        if let pySections = Array<PythonObject>(result["sections"]) {
            for item in pySections {
                if let name = String(item["name"]),
                   let firstPage = Int(item["first_page"]) {
                    sections.append(ProofSection(name: name, firstPage: firstPage))
                }
            }
        }

        lastPDFPath = path
        return (path: path, sections: sections)
    }

    // MARK: - Font Queries

    func getFontMetadata(paths: [String]) -> [FontInfo] {
        guard let engine = engineModule else { return [] }
        let result = engine.get_font_metadata(paths)
        guard let list = Array<PythonObject>(result) else { return [] }

        return list.compactMap { item -> FontInfo? in
            guard let path = String(item["path"]),
                  let name = String(item["name"]) else { return nil }

            let isVariable = Bool(item["is_variable"]) ?? false
            let supportsArabic = Bool(item["supports_arabic"]) ?? false

            // Parse axes dict → [FontAxis]
            var axes: [FontAxis] = []
            // Parse per-axis named instance values
            var axisInstances: [String: [Double]] = [:]
            if let instDict = Dictionary<String, PythonObject>(item["axis_instances"]) {
                for (tag, values) in instDict {
                    if let vals = Array<Double>(values) {
                        axisInstances[tag] = vals
                    }
                }
            }
            if let axesDict = Dictionary<String, PythonObject>(item["axes"]) {
                for (tag, values) in axesDict {
                    if let vals = Array<Double>(values), vals.count >= 2 {
                        let minVal = vals[0]
                        let maxVal = vals[vals.count - 1]
                        let defVal = vals.count >= 3 ? vals[1] : minVal
                        axes.append(FontAxis(
                            id: tag,
                            name: tag,
                            minValue: minVal,
                            maxValue: maxVal,
                            defaultValue: defVal,
                            currentValue: defVal,
                            instanceValues: axisInstances[tag] ?? []
                        ))
                    }
                }
            }
            let familyName = String(item["family_name"]) ?? ""
            let weight = Int(item["weight"]) ?? 400
            let width = Int(item["width"]) ?? 5
            let slant = Double(item["slant"]) ?? 0
            let opticalSize = Double(item["optical_size"]) ?? 0

            return FontInfo(id: path, name: name, isVariable: isVariable,
                            axes: axes, supportsArabic: supportsArabic,
                            familyName: familyName, weight: weight,
                            width: width, slant: slant, opticalSize: opticalSize)
        }
    }

    func getFontAxes(path: String) -> [FontAxis] {
        guard let engine = engineModule else { return [] }
        let result = engine.get_font_axes(path)
        guard let dict = Dictionary<String, PythonObject>(result) else { return [] }

        return dict.compactMap { (tag, values) in
            guard let vals = Array<Double>(values), vals.count >= 2 else { return nil }
            return FontAxis(
                id: tag, name: tag,
                minValue: vals[0],
                maxValue: vals[vals.count - 1],
                defaultValue: vals.count > 2 ? vals[1] : vals[0],
                currentValue: vals.count > 2 ? vals[1] : vals[0],
                instanceValues: []
            )
        }
    }

    func getAvailableOTFeatures(path: String) -> [String] {
        guard let engine = engineModule else { return [] }
        let result = engine.get_available_ot_features(path)
        return Array<String>(result) ?? []
    }

    // MARK: - Config Queries

    func getProofRegistry() -> [ProofRegistryEntry] {
        guard let engine = engineModule else { return [] }
        let registry = engine.get_proof_registry()
        guard let dict = Dictionary<String, PythonObject>(registry) else { return [] }

        return dict.compactMap { (key, info) -> ProofRegistryEntry? in
            guard let displayName = String(info["display_name"]) else { return nil }
            return ProofRegistryEntry(
                key: key,
                displayName: displayName,
                isArabic: Bool(info.get("is_arabic", false)) ?? false,
                hasSettings: Bool(info.get("has_settings", false)) ?? false,
                defaultColumns: Int(info.get("default_cols", 2)) ?? 2,
                hasParagraphs: Bool(info.get("has_paragraphs", false)) ?? false,
                defaultFontSize: Int(info.get("default_size", 12)) ?? 12,
                hasCustomText: Bool(info.get("has_custom_text", false)) ?? false,
                hasCategories: Bool(info.get("has_categories", false)) ?? false,
                isMultiStyle: Bool(info.get("multi_style", false)) ?? false
            )
        }
    }

    func getPageFormats() -> [String] {
        guard let engine = engineModule else { return [] }
        return Array<String>(engine.get_page_formats()) ?? []
    }

    func getDefaultProofOrder(includeArabic: Bool = true) -> [String] {
        guard let engine = engineModule else { return [] }
        return Array<String>(engine.get_default_proof_order(include_arabic: includeArabic)) ?? []
    }

    func getFontStyles(paths: [String]) -> [FontStyleEntry] {
        guard let engine = engineModule else { return [] }
        let result = engine.get_font_styles(paths)
        guard let list = Array<PythonObject>(result) else { return [] }

        return list.compactMap { item -> FontStyleEntry? in
            guard let index = Int(item["index"]),
                  let fontPath = String(item["font_path"]),
                  let familyName = String(item["family_name"]),
                  let styleName = String(item["style_name"]) else { return nil }
            let isVariable = Bool(item["is_variable"]) ?? false
            var coordinates: [String: Double]? = nil
            if isVariable, let coordDict = Dictionary<String, PythonObject>(item["coordinates"]) {
                coordinates = coordDict.compactMapValues { Double($0) }
            }
            return FontStyleEntry(
                index: index,
                fontPath: fontPath,
                familyName: familyName,
                styleName: styleName,
                isVariable: isVariable,
                coordinates: coordinates
            )
        }
    }
}
