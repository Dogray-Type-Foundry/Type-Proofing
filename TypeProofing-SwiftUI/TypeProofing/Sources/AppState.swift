import SwiftUI
import UniformTypeIdentifiers
import PythonKit

// MARK: - Supporting Types

struct OTFeature: Identifiable, Codable {
    let id: String   // tag, e.g. "liga"
    var tag: String
    var enabled: Bool
}

struct CategorySettings: Codable {
    var uppercaseBase: Bool = true
    var lowercaseBase: Bool = true
    var numbersSymbols: Bool = true
    var punctuation: Bool = true
    var accented: Bool = false   // matches Python default
}

struct ProofSettings: Codable {
    var fontSize: Double = 12
    var tracking: Double = 0
    var lineHeight: Double = 1.2  // em ratio (multiplied by fontSize for absolute value)
    var columns: Int = 1
    var paragraphs: Int = 5
    var alignment: String = "left"
    var customText: String = ""
    var markupEnabled: Bool = false
    var generateOnce: Bool = false
    var categories: CategorySettings = CategorySettings()
    var otFeatures: [OTFeature] = []
    // Custom Text: default font path for "generate once"
    var defaultFontPath: String = ""
    var defaultFontAxisDict: [String: Double]? = nil
    // Multi-style: which style indices are enabled (key = index as string, default true)
    var enabledStyleIndices: [String: Bool] = [:]
    // Auto-size: fit category on one page (charset) or fit longest line (multi-style)
    var autoSize: Bool = false
}

/// Represents a single font style entry (static font or VF named instance).
struct FontStyleEntry: Identifiable, Equatable {
    var id: Int { index }
    let index: Int           // global index matching Python's style indexing
    let fontPath: String
    let familyName: String
    let styleName: String
    let isVariable: Bool
    let coordinates: [String: Double]?
}

// MARK: - AppState

@MainActor
final class AppState: ObservableObject {
    // Fonts
    @Published var fontPaths: [String] = []
    @Published var loadedFonts: [FontInfo] = []
    @Published var axisValuesByFont: [String: [String: [Double]]] = [:]
    @Published var disabledFontPaths: Set<String> = []
    @Published var fontSortCriteria: [FontSortCriterion] = []
    /// All font styles (static + VF instances) for multi-style and default font pickers
    @Published var fontStyles: [FontStyleEntry] = []
    /// Font styles grouped by family name (for multi-style grouped UI)
    var fontStylesByFamily: [(familyName: String, styles: [FontStyleEntry])] {
        let grouped = Dictionary(grouping: fontStyles, by: \.familyName)
        // Maintain order by first occurrence
        var seen = Set<String>()
        var order: [String] = []
        for style in fontStyles {
            if seen.insert(style.familyName).inserted {
                order.append(style.familyName)
            }
        }
        return order.map { name in (familyName: name, styles: grouped[name]!) }
    }

    // Proofs
    @Published var proofOptions: [ProofOption] = []
    @Published var selectedProof: ProofOption.ID?
    @Published var proofSettingsByProof: [String: ProofSettings] = [:]

    // Page
    @Published var pageFormat: String = "A4Landscape"
    @Published var pageFormats: [String] = []
    @Published var showBaselines: Bool = false

    // Output
    @Published var outputDirectory: String = ""
    @Published var currentPDFPath: String?
    @Published var proofSections: [ProofSection] = []

    // PDF output
    @Published var useCustomOutputLocation: Bool = false
    @Published var customOutputLocation: String = ""

    // UI state
    @Published var showFontPicker = false
    @Published var showAddProofSheet = false
    @Published var showSettingsImporter = false

    // Available OT features from loaded fonts (minus hidden)
    private(set) var availableOTFeatures: [String] = []

    // MARK: - Registry cache

    private(set) var registryByKey: [String: ProofRegistryEntry] = [:]

    // MARK: - Persistence

    private static let settingsURL: URL = {
        let home = FileManager.default.homeDirectoryForCurrentUser
        return home.appendingPathComponent(".type-proofing-swiftui-prefs.json")
    }()

    private var persistTimer: Timer?

    // MARK: - Computed

    var selectedProofOption: ProofOption? {
        guard let id = selectedProof else { return nil }
        return proofOptions.first { $0.id == id }
    }

    var selectedProofSettings: Binding<ProofSettings> {
        Binding(
            get: { [weak self] in
                guard let self,
                      let opt = self.selectedProofOption else {
                    return ProofSettings()
                }
                return self.proofSettingsByProof[opt.name] ?? ProofSettings()
            },
            set: { [weak self] newValue in
                guard let self,
                      let opt = self.selectedProofOption else { return }
                self.proofSettingsByProof[opt.name] = newValue
                self.schedulePersist()
            }
        )
    }

    var selectedRegistryEntry: ProofRegistryEntry? {
        guard let opt = selectedProofOption else { return nil }
        return registryByKey[opt.baseType]
    }

    /// True when at least one loaded font supports the Arabic script.
    var anyFontSupportsArabic: Bool {
        loadedFonts.contains(where: \.supportsArabic)
    }

    /// Font paths that are currently enabled (not in disabledFontPaths).
    var enabledFontPaths: [String] {
        fontPaths.filter { !disabledFontPaths.contains($0) }
    }

    // MARK: - Initialization from Engine

    func loadFromEngine(_ engine: ProofEngine) {
        let registry = engine.getProofRegistry()
        for entry in registry {
            registryByKey[entry.key] = entry
        }

        pageFormats = engine.getPageFormats()

        // Try loading saved state first
        if loadPersistedState() {
            // Validate page format still exists
            if !pageFormats.isEmpty && !pageFormats.contains(pageFormat) {
                pageFormat = pageFormats.first!
            }
            if let first = proofOptions.first, selectedProof == nil {
                selectedProof = first.id
            }
            // Reload font metadata from paths (not persisted)
            if !fontPaths.isEmpty {
                let existingPaths = fontPaths.filter { FileManager.default.fileExists(atPath: $0) }
                if existingPaths.count != fontPaths.count {
                    fontPaths = existingPaths
                }
                if !fontPaths.isEmpty {
                    loadedFonts = engine.getFontMetadata(paths: fontPaths)
                    applySortCriteria()
                    refreshFontStyles(engine: engine)
                    let allFeatures = engine.getAvailableOTFeatures(path: fontPaths[0])
                    availableOTFeatures = allFeatures.filter { !HIDDEN_FEATURES.contains($0) }
                    if outputDirectory.isEmpty {
                        outputDirectory = (fontPaths[0] as NSString).deletingLastPathComponent
                    }
                }
            }
            return
        }

        // Fresh initialization from engine defaults
        if !pageFormats.isEmpty && !pageFormats.contains(pageFormat) {
            pageFormat = pageFormats.first!
        }

        let defaultOrder = engine.getDefaultProofOrder()
        proofOptions = defaultOrder.enumerated().compactMap { (index, displayName) -> ProofOption? in
            guard let entry = registry.first(where: { $0.displayName == displayName }) else {
                return nil
            }
            return ProofOption(
                name: displayName,
                baseType: entry.key,
                enabled: true,
                order: index
            )
        }

        // Initialize default proof settings for each
        for option in proofOptions {
            initializeDefaultSettings(for: option)
        }

        // Select the first option
        if let first = proofOptions.first {
            selectedProof = first.id
        }
    }

    private func initializeDefaultSettings(for option: ProofOption) {
        guard let entry = registryByKey[option.baseType] else { return }
        var settings = ProofSettings()
        settings.fontSize = Double(entry.defaultFontSize)
        settings.columns = entry.defaultColumns
        settings.alignment = entry.isArabic ? "right" : "left"
        settings.paragraphs = entry.hasParagraphs ? 5 : 2
        proofSettingsByProof[option.name] = settings
    }

    // MARK: - Font Management

    func addFonts(urls: [URL], engine: ProofEngine) {
        let paths = urls.map { $0.path }
        let newPaths = paths.filter { !fontPaths.contains($0) }
        guard !newPaths.isEmpty else { return }

        fontPaths.append(contentsOf: newPaths)
        let metadata = engine.getFontMetadata(paths: newPaths)
        loadedFonts.append(contentsOf: metadata)
        applySortCriteria()

        // Initialize axis values for variable fonts
        for font in metadata where font.isVariable {
            if axisValuesByFont[font.id] == nil {
                var axisDefaults: [String: [Double]] = [:]
                for axis in font.axes {
                    // Start with handles at min, default (if distinct), max
                    var initial: [Double] = [axis.minValue]
                    if axis.defaultValue != axis.minValue && axis.defaultValue != axis.maxValue {
                        initial.append(axis.defaultValue)
                    }
                    initial.append(axis.maxValue)
                    axisDefaults[axis.id] = initial
                }
                axisValuesByFont[font.id] = axisDefaults
            }
        }

        // Set output directory from first font if not set
        if outputDirectory.isEmpty, let first = fontPaths.first {
            outputDirectory = (first as NSString).deletingLastPathComponent
        }

        // Load OT features from first font (filtered by HIDDEN_FEATURES)
        if let firstPath = fontPaths.first {
            let allFeatures = engine.getAvailableOTFeatures(path: firstPath)
            availableOTFeatures = allFeatures.filter { !HIDDEN_FEATURES.contains($0) }

            // Apply to all proofs that don't have features yet
            for (name, settings) in proofSettingsByProof where settings.otFeatures.isEmpty {
                proofSettingsByProof[name]?.otFeatures = buildDefaultOTFeatures(
                    for: proofOptions.first(where: { $0.name == name })?.baseType
                )
            }
        }

        refreshFontStyles(engine: engine)
        schedulePersist()
    }

    /// Refresh the flat list of font styles from the current enabled font paths.
    func refreshFontStyles(engine: ProofEngine) {
        let enabledPaths = fontPaths.filter { !disabledFontPaths.contains($0) }
        fontStyles = engine.getFontStyles(paths: enabledPaths)
    }

    private func buildDefaultOTFeatures(for baseType: String?) -> [OTFeature] {
        availableOTFeatures.map { tag in
            var enabled = DEFAULT_ON_FEATURES.contains(tag)
            // Spacing proof: kern always off
            if baseType == "spacing_proof" && tag == "kern" {
                enabled = false
            }
            return OTFeature(id: tag, tag: tag, enabled: enabled)
        }
    }

    func removeFont(at offsets: IndexSet, engine: ProofEngine? = nil) {
        let pathsToRemove = offsets.map { loadedFonts[$0].id }
        loadedFonts.remove(atOffsets: offsets)
        fontPaths.removeAll { pathsToRemove.contains($0) }
        for path in pathsToRemove {
            axisValuesByFont.removeValue(forKey: path)
            disabledFontPaths.remove(path)
        }
        if let engine { refreshFontStyles(engine: engine) }
        schedulePersist()
    }

    func moveFonts(from source: IndexSet, to destination: Int) {
        loadedFonts.move(fromOffsets: source, toOffset: destination)
        fontPaths = loadedFonts.map(\.id)
        schedulePersist()
    }

    func applySortCriteria() {
        guard !fontSortCriteria.isEmpty else { return }
        loadedFonts = loadedFonts.sorted(by: fontSortCriteria)
        fontPaths = loadedFonts.map(\.id)
        schedulePersist()
    }

    func resetFonts() {
        fontPaths.removeAll()
        loadedFonts.removeAll()
        axisValuesByFont.removeAll()
        availableOTFeatures.removeAll()
        outputDirectory = ""
        currentPDFPath = nil
        schedulePersist()
    }

    // MARK: - Proof Reordering

    func moveProofOptions(from source: IndexSet, to destination: Int) {
        proofOptions.move(fromOffsets: source, toOffset: destination)
        for (i, _) in proofOptions.enumerated() {
            proofOptions[i].order = i
        }
        schedulePersist()
    }

    // MARK: - Add/Remove Proof Instance

    func generateUniqueName(for baseType: String) -> String {
        let baseName = registryByKey[baseType]?.displayName ?? baseType
        let existingNames = Set(proofOptions.map(\.name))
        var counter = 2
        var candidate = "\(baseName) \(counter)"
        while existingNames.contains(candidate) {
            counter += 1
            candidate = "\(baseName) \(counter)"
        }
        return candidate
    }

    func addProofInstance(baseType: String) {
        let newName = generateUniqueName(for: baseType)
        let newOption = ProofOption(
            name: newName,
            baseType: baseType,
            enabled: true,
            order: proofOptions.count
        )
        proofOptions.append(newOption)
        initializeDefaultSettings(for: newOption)

        // Copy OT features if available
        if !availableOTFeatures.isEmpty {
            proofSettingsByProof[newName]?.otFeatures = buildDefaultOTFeatures(for: baseType)
        }

        schedulePersist()
    }

    func removeProofOption(at offsets: IndexSet) {
        let names = offsets.map { proofOptions[$0].name }
        proofOptions.remove(atOffsets: offsets)
        for name in names {
            proofSettingsByProof.removeValue(forKey: name)
        }
        for (i, _) in proofOptions.enumerated() {
            proofOptions[i].order = i
        }
        schedulePersist()
    }

    // MARK: - Build ProofConfig for Engine

    func buildProofConfig() -> ProofConfig {
        // axisValuesByFont is already [String: [String: [Double]]] — pass directly
        let axisValuesForEngine = axisValuesByFont

        // Build flat proof_settings dict matching Python key conventions
        let pySettings = buildFlatProofSettings()

        // Determine output dir
        let outDir: String
        if useCustomOutputLocation && !customOutputLocation.isEmpty {
            outDir = customOutputLocation
        } else {
            outDir = outputDirectory
        }

        return ProofConfig(
            fontPaths: enabledFontPaths,
            axisValuesByFont: axisValuesForEngine,
            proofOptions: proofOptions,
            proofSettings: pySettings,
            pageFormat: pageFormat,
            outputDir: outDir,
            showBaselines: showBaselines
        )
    }

    /// Convert the per-proof ProofSettings structs into the flat dictionary
    /// format the Python engine expects: `{proof_key}_fontSize`, `otf_{proof_key}_{tag}`, etc.
    private func buildFlatProofSettings() -> [String: PythonObject] {
        var flat: [String: PythonObject] = [:]

        for option in proofOptions {
            let settingsKey = option.baseType
            guard let settings = proofSettingsByProof[option.name] else { continue }
            guard let entry = registryByKey[option.baseType] else { continue }

            // Font size — always present
            flat["\(settingsKey)_fontSize"] = PythonObject(Int(settings.fontSize))

            // Line height — always send for proofs that support it (em ratio)
            if entry.supportsLineHeight {
                flat["\(settingsKey)_lineHeight"] = PythonObject(settings.lineHeight)
            }

            // Columns — only for proofs that support it
            if entry.supportsCols {
                flat["\(settingsKey)_cols"] = PythonObject(settings.columns)
            }

            // Tracking — only for proofs that support formatting
            if entry.supportsFormatting {
                flat["\(settingsKey)_tracking"] = PythonObject(settings.tracking)
            }

            // Alignment — only for proofs that support formatting
            if entry.supportsFormatting {
                flat["\(settingsKey)_align"] = PythonObject(settings.alignment)
            }

            // Paragraphs — only for proofs that have them
            if entry.hasParagraphs {
                flat["\(settingsKey)_para"] = PythonObject(settings.paragraphs)
            }

            // Character categories
            if entry.hasCategories {
                flat["\(settingsKey)_cat_uppercase_base"] = PythonObject(settings.categories.uppercaseBase)
                flat["\(settingsKey)_cat_lowercase_base"] = PythonObject(settings.categories.lowercaseBase)
                flat["\(settingsKey)_cat_numbers_symbols"] = PythonObject(settings.categories.numbersSymbols)
                flat["\(settingsKey)_cat_punctuation"] = PythonObject(settings.categories.punctuation)
                flat["\(settingsKey)_cat_accented"] = PythonObject(settings.categories.accented)
            }

            // Custom text
            if entry.hasCustomText {
                flat["\(settingsKey)_customText"] = PythonObject(settings.customText)
                flat["\(settingsKey)_markupEnabled"] = PythonObject(settings.markupEnabled)
                if !entry.isMultiStyle {
                    flat["\(settingsKey)_generateOnce"] = PythonObject(settings.generateOnce)
                    // Default font path for "generate once"
                    if !settings.defaultFontPath.isEmpty {
                        flat["\(settingsKey)_defaultFontPath"] = PythonObject(settings.defaultFontPath)
                    }
                    if let axisDict = settings.defaultFontAxisDict {
                        flat["\(settingsKey)_defaultFontAxisDict"] = PythonObject(
                            axisDict.mapValues { PythonObject($0) }
                        )
                    }
                }
            }

            // Multi-style: per-style enabled flags
            if entry.isMultiStyle {
                for (indexStr, enabled) in settings.enabledStyleIndices {
                    flat["\(settingsKey)_style_\(indexStr)"] = PythonObject(enabled)
                }
            }

            // Auto-size (charset: fit category in one page; multi-style: fit in one line)
            if settingsKey == "filtered_character_set" || entry.isMultiStyle {
                flat["\(settingsKey)_autoSize"] = PythonObject(settings.autoSize)
            }

            // OpenType features
            for feature in settings.otFeatures {
                flat["otf_\(settingsKey)_\(feature.tag)"] = PythonObject(feature.enabled)
            }
        }

        return flat
    }

    // MARK: - Settings Persistence

    private func schedulePersist() {
        persistTimer?.invalidate()
        persistTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: false) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.persistState()
            }
        }
    }

    /// Public wrapper for views that need to trigger persistence (e.g. checkbox toggles)
    func schedulePersistPublic() {
        schedulePersist()
    }

    func persistState() {
        let data = PersistedState(
            fontPaths: fontPaths,
            axisValuesByFont: axisValuesByFont,
            disabledFontPaths: Array(disabledFontPaths),
            fontSortCriteria: fontSortCriteria,
            proofOptions: proofOptions.map {
                PersistedProofOption(name: $0.name, baseType: $0.baseType, enabled: $0.enabled, order: $0.order)
            },
            proofSettingsByProof: proofSettingsByProof,
            pageFormat: pageFormat,
            showBaselines: showBaselines,
            useCustomOutputLocation: useCustomOutputLocation,
            customOutputLocation: customOutputLocation
        )

        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let json = try encoder.encode(data)
            try json.write(to: Self.settingsURL, options: .atomic)
        } catch {
            print("Settings save error: \(error)")
        }
    }

    private func loadPersistedState() -> Bool {
        guard FileManager.default.fileExists(atPath: Self.settingsURL.path) else { return false }

        do {
            let json = try Data(contentsOf: Self.settingsURL)
            let data = try JSONDecoder().decode(PersistedState.self, from: json)

            fontPaths = data.fontPaths
            axisValuesByFont = data.axisValuesByFont
            disabledFontPaths = Set(data.disabledFontPaths ?? [])
            fontSortCriteria = data.fontSortCriteria ?? []
            pageFormat = data.pageFormat
            showBaselines = data.showBaselines
            useCustomOutputLocation = data.useCustomOutputLocation
            customOutputLocation = data.customOutputLocation

            proofOptions = data.proofOptions.enumerated().map { (i, po) in
                ProofOption(name: po.name, baseType: po.baseType, enabled: po.enabled, order: po.order)
            }
            proofSettingsByProof = data.proofSettingsByProof

            if let first = proofOptions.first {
                selectedProof = first.id
            }

            // Set output dir from first font
            if outputDirectory.isEmpty, let first = fontPaths.first {
                outputDirectory = (first as NSString).deletingLastPathComponent
            }

            return true
        } catch {
            print("Settings load error: \(error)")
            return false
        }
    }

    func resetAllSettings() {
        proofSettingsByProof.removeAll()
        for option in proofOptions {
            initializeDefaultSettings(for: option)
            if !availableOTFeatures.isEmpty {
                proofSettingsByProof[option.name]?.otFeatures = buildDefaultOTFeatures(for: option.baseType)
            }
        }
        showBaselines = false
        pageFormat = "A4Landscape"
        persistState()
    }

    func setAvailableOTFeatures(_ features: [String]) {
        availableOTFeatures = features
    }
}

// MARK: - Persistence Types

struct PersistedProofOption: Codable {
    let name: String
    let baseType: String
    let enabled: Bool
    let order: Int
}

struct PersistedState: Codable {
    let fontPaths: [String]
    let axisValuesByFont: [String: [String: [Double]]]
    let disabledFontPaths: [String]?
    let fontSortCriteria: [FontSortCriterion]?
    let proofOptions: [PersistedProofOption]
    let proofSettingsByProof: [String: ProofSettings]
    let pageFormat: String
    let showBaselines: Bool
    let useCustomOutputLocation: Bool
    let customOutputLocation: String
}
