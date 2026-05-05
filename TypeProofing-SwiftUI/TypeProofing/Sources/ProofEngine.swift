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
    let defaultEnabled: Bool
    let displayOrder: Int

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
            details: rawDetails.mapValues { value in
                if let string = value as? String { return string }
                if let data = try? JSONSerialization.data(withJSONObject: value),
                   let string = String(data: data, encoding: .utf8) {
                    return string
                }
                return String(describing: value)
            },
            timestamp: dict["timestamp"] as? String ?? ""
        )
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
        ]
    }

    func toJSONData() throws -> Data {
        try JSONSerialization.data(withJSONObject: toDictionary(), options: [])
    }

    /// Convert the whole config into a Python dict for PythonKit fallback calls.
    func toPythonDict() -> PythonObject {
        PythonObject.fromSwift(toDictionary())
    }
}

private extension PythonObject {
    static func fromSwift(_ value: Any) -> PythonObject {
        switch value {
        case let value as String:
            return PythonObject(value)
        case let value as Bool:
            return PythonObject(value)
        case let value as Int:
            return PythonObject(value)
        case let value as Double:
            return PythonObject(value)
        case let value as Float:
            return PythonObject(Double(value))
        case let value as [String: [String: [Double]]]:
            return PythonObject(value.mapValues { axes in
                PythonObject(axes.mapValues { PythonObject($0) })
            })
        case let value as [String: [Double]]:
            return PythonObject(value.mapValues { PythonObject($0) })
        case let value as [String: Double]:
            return PythonObject(value.mapValues { PythonObject($0) })
        case let value as [String: Bool]:
            return PythonObject(value.mapValues { PythonObject($0) })
        case let value as [String: Any]:
            return PythonObject(value.mapValues { PythonObject.fromSwift($0) })
        case let value as [Any]:
            return PythonObject(value.map { PythonObject.fromSwift($0) })
        case let value as [String]:
            return PythonObject(value)
        case let value as [Double]:
            return PythonObject(value)
        default:
            return PythonObject(String(describing: value))
        }
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
    @Published var diagnostics: [DiagnosticEvent] = []
    @Published var generationProgress: GenerationProgress?
    @Published var proofRunSummary: ProofRunSummary?
    @Published var debugMode = false
    @Published private(set) var proofRegistryCount = 0
    var usesWorkerGeneration = true

    // ── Python modules (lazy-loaded after init) ─────────────────────────
    private var engineModule: PythonObject?
    private var configModule: PythonObject?
    private var fontsModule: PythonObject?
    private var currentWorker: Process?

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
        diagnostics.removeAll()
        generationProgress = nil
        defer { isGenerating = false }

        // Yield once so SwiftUI can redraw the spinner, then run Python
        // or launch the worker after the UI has reflected the new state.
        await Task.yield()

        var config = config
        config.debugMode = debugMode

        if usesWorkerGeneration, let workerResult = await generateProofWithWorker(config: config) {
            lastPDFPath = workerResult.path
            generationProgress = nil
            return workerResult
        }

        // Fallback: run synchronously through PythonKit on the main actor.
        let pyDict = config.toPythonDict()
        let result = engine.generate_proof(pyDict)
        if let summaryDict = Self.pythonObjectToDictionary(result["summary"]) {
            proofRunSummary = ProofRunSummary.fromDictionary(summaryDict)
        }
        diagnostics.append(contentsOf: Self.parseDiagnostics(result["diagnostics"]))

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
        generationProgress = nil
        return (path: path, sections: sections)
    }

    func cancelGeneration() {
        currentWorker?.terminate()
        currentWorker = nil
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
        guard let engine = engineModule else { return }
        var config = config
        config.debugMode = debugMode
        let result = engine.get_proof_run_summary(config.toPythonDict())
        if let dict = Self.pythonObjectToDictionary(result) {
            proofRunSummary = ProofRunSummary.fromDictionary(dict)
        }
    }

    private func generateProofWithWorker(config: ProofConfig) async -> (path: String, sections: [ProofSection])? {
        guard let workerURL = resolveWorkerScriptURL(),
              let pythonURL = resolvePythonExecutableURL() else { return nil }

        let configURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("type-proofing-\(UUID().uuidString).json")

        do {
            try config.toJSONData().write(to: configURL, options: .atomic)
        } catch {
            errorMessage = "Could not write worker config: \(error)"
            return nil
        }

        let process = Process()
        process.executableURL = pythonURL
        process.arguments = [workerURL.path, "--config", configURL.path]
        process.environment = workerEnvironment()

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe
        let shouldCaptureWorkerOutput = config.debugMode

        return await withCheckedContinuation { continuation in
            let lock = NSLock()
            var stdoutBuffer = Data()
            var stderrBuffer = Data()
            var completedResult: (path: String, sections: [ProofSection])?
            var didResume = false

            func resumeOnce(_ value: (path: String, sections: [ProofSection])?) {
                lock.lock()
                guard !didResume else {
                    lock.unlock()
                    return
                }
                didResume = true
                lock.unlock()
                continuation.resume(returning: value)
            }

            func handleLine(_ lineData: Data) {
                guard !lineData.isEmpty else { return }
                guard let object = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                      let type = object["type"] as? String else {
                    if shouldCaptureWorkerOutput,
                       let message = String(data: lineData, encoding: .utf8),
                       !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Task { @MainActor in
                            self.diagnostics.append(DiagnosticEvent(
                                level: "debug",
                                category: "worker_output",
                                message: message,
                                fontPath: nil,
                                proofName: nil,
                                details: [:],
                                timestamp: ""
                            ))
                        }
                    }
                    return
                }

                switch type {
                case "started":
                    break
                case "progress":
                    let progress = GenerationProgress(
                        proofName: object["proof_name"] as? String ?? "",
                        proofIndex: object["proof_index"] as? Int ?? 0,
                        proofCount: object["proof_count"] as? Int ?? 0,
                        fontPath: object["font_path"] as? String ?? "",
                        fontIndex: object["font_index"] as? Int ?? 0,
                        fontCount: object["font_count"] as? Int ?? 0
                    )
                    Task { @MainActor in self.generationProgress = progress }
                case "diagnostic":
                    if let eventDict = object["event"] as? [String: Any],
                       let event = DiagnosticEvent.fromDictionary(eventDict) {
                        Task { @MainActor in self.diagnostics.append(event) }
                    }
                case "completed":
                    if let result = object["result"] as? [String: Any] {
                        let parsed = Self.parseWorkerResult(result)
                        lock.lock()
                        completedResult = parsed.result
                        lock.unlock()
                        if let summary = parsed.summary {
                            Task { @MainActor in self.proofRunSummary = summary }
                        }
                    }
                case "failed":
                    let message = object["message"] as? String ?? "Worker generation failed"
                    Task { @MainActor in self.errorMessage = message }
                case "cancelled":
                    Task { @MainActor in
                        self.errorMessage = "Generation cancelled"
                    }
                default:
                    break
                }
            }

            func consumeStdout(_ data: Data) {
                lock.lock()
                stdoutBuffer.append(data)
                let parts = stdoutBuffer.split(separator: UInt8(ascii: "\n"), omittingEmptySubsequences: false)
                let completeCount = stdoutBuffer.last == UInt8(ascii: "\n") ? parts.count : max(0, parts.count - 1)
                let complete = Array(parts.prefix(completeCount)).map { Data($0) }
                stdoutBuffer = stdoutBuffer.last == UInt8(ascii: "\n")
                    ? Data()
                    : parts.last.map { Data($0) } ?? Data()
                lock.unlock()
                for line in complete {
                    handleLine(line)
                }
            }

            stdoutPipe.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                if !data.isEmpty {
                    consumeStdout(data)
                }
            }
            stderrPipe.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                if data.isEmpty { return }
                lock.lock()
                stderrBuffer.append(data)
                lock.unlock()
            }

            process.terminationHandler = { _ in
                stdoutPipe.fileHandleForReading.readabilityHandler = nil
                stderrPipe.fileHandleForReading.readabilityHandler = nil
                lock.lock()
                let remainingStdout = stdoutBuffer
                let stderr = String(data: stderrBuffer, encoding: .utf8) ?? ""
                let result = completedResult
                lock.unlock()
                if !remainingStdout.isEmpty {
                    handleLine(remainingStdout)
                }
                if result == nil, !stderr.isEmpty {
                    Task { @MainActor in
                        self.diagnostics.append(DiagnosticEvent(
                            level: "error",
                            category: "worker",
                            message: stderr,
                            fontPath: nil,
                            proofName: nil,
                            details: [:],
                            timestamp: ""
                        ))
                    }
                }
                try? FileManager.default.removeItem(at: configURL)
                Task { @MainActor in self.currentWorker = nil }
                resumeOnce(result)
            }

            do {
                currentWorker = process
                try process.run()
            } catch {
                currentWorker = nil
                try? FileManager.default.removeItem(at: configURL)
                errorMessage = "Could not launch proof worker: \(error)"
                resumeOnce(nil)
            }
        }
    }

    private func resolveWorkerScriptURL() -> URL? {
        if let resourcePath = Bundle.main.resourcePath {
            let bundled = URL(fileURLWithPath: resourcePath)
                .appendingPathComponent("python-lib/worker.py")
            if FileManager.default.fileExists(atPath: bundled.path) {
                return bundled
            }
        }
        let dev = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
            .appendingPathComponent("python/worker.py")
        return FileManager.default.fileExists(atPath: dev.path) ? dev : nil
    }

    private func resolvePythonExecutableURL() -> URL? {
        let candidates = [
            Bundle.main.privateFrameworksPath.map {
                "\($0)/Python.framework/Versions/3.13/bin/python3.13"
            },
            "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13",
            "/usr/bin/python3",
        ].compactMap { $0 }

        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }
        return nil
    }

    private func workerEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["PYTHONNOUSERSITE"] = "1"
        if let frameworksPath = Bundle.main.privateFrameworksPath {
            let pythonHome = "\(frameworksPath)/Python.framework/Versions/3.13"
            env["PYTHONHOME"] = pythonHome
            env["PYTHON_LIBRARY"] = "\(pythonHome)/lib/libpython3.13.dylib"
        }
        if let resourcePath = Bundle.main.resourcePath {
            env["PYTHONPATH"] = "\(resourcePath)/python-lib"
        }
        return env
    }

    nonisolated private static func parseWorkerResult(_ result: [String: Any]) -> (result: (path: String, sections: [ProofSection])?, summary: ProofRunSummary?) {
        let path = result["path"] as? String ?? ""
        let rawSections = result["sections"] as? [[String: Any]] ?? []
        let sections = rawSections.compactMap { item -> ProofSection? in
            guard let name = item["name"] as? String,
                  let firstPage = item["first_page"] as? Int else { return nil }
            return ProofSection(name: name, firstPage: firstPage)
        }
        let summary = (result["summary"] as? [String: Any]).map(ProofRunSummary.fromDictionary)
        let parsedResult = path.isEmpty ? nil : (path: path, sections: sections)
        return (parsedResult, summary)
    }

    nonisolated private static func parseDiagnostics(_ object: PythonObject) -> [DiagnosticEvent] {
        guard let list = pythonObjectToArray(object) else { return [] }
        return list.compactMap { DiagnosticEvent.fromDictionary($0) }
    }

    nonisolated private static func pythonObjectToDictionary(_ object: PythonObject) -> [String: Any]? {
        let json = Python.import("json")
        guard let text = String(json.dumps(object)) else { return nil }
        guard let data = text.data(using: .utf8) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
    }

    nonisolated private static func pythonObjectToArray(_ object: PythonObject) -> [[String: Any]]? {
        let json = Python.import("json")
        guard let text = String(json.dumps(object)) else { return nil }
        guard let data = text.data(using: .utf8) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]]
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

    func getAvailableSubstitutionFeatures(path: String) -> [String] {
        guard let engine = engineModule else { return [] }
        let result = engine.get_available_substitution_features(path)
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
                isMultiStyle: Bool(info.get("multi_style", false)) ?? false,
                defaultEnabled: Bool(info.get("default_enabled", true)) ?? true,
                displayOrder: Int(info.get("display_order", 999)) ?? 999
            )
        }.sorted { $0.displayOrder < $1.displayOrder }
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
