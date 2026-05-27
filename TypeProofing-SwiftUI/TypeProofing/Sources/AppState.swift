import SwiftUI
import UniformTypeIdentifiers

// MARK: - View Mode

enum ViewMode: String, CaseIterable {
    case page
    case grid
    case compare
}

// MARK: - Proof Key Utilities

/// Mirror Python's `create_unique_proof_key()` so Swift and Python
/// agree on the settings-key prefix for every proof instance.
func pythonProofKey(for name: String) -> String {
    name.lowercased()
        .replacingOccurrences(of: " ", with: "_")
        .replacingOccurrences(of: "/", with: "_")
        .replacingOccurrences(of: "-", with: "_")
}

func pythonSettingsKey(for option: ProofOption, entry: ProofRegistryEntry) -> String {
    if option.name == entry.displayName {
        return option.baseType
    }
    return pythonProofKey(for: option.name)
}

// MARK: - Supporting Types

struct OTFeature: Identifiable, Codable {
    let id: String   // tag, e.g. "liga"
    var tag: String
    var enabled: Bool
}

struct SubstitutionFeature: Identifiable, Codable {
    let id: String
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
    var substitutionFeatures: [SubstitutionFeature] = []
    // Custom Text: default font path for "generate once"
    var defaultFontPath: String = ""
    var defaultFontAxisDict: [String: Double]? = nil
    // Multi-style: which style indices are enabled (key = index as string, default true)
    var enabledStyleIndices: [String: Bool] = [:]
    // Auto-size: fit category on one page (charset) or fit longest line (multi-style)
    var autoSize: Bool = false
    // Multi-style: show fallback glyphs for missing characters
    var showFallback: Bool = false
    // WS-3E: New typesetting controls
    var columnGap: Double = 20
    var direction: String = "auto"
    var paragraphIndent: Double = 0
    var paragraphSpace: Double = 0
    var hyphenation: Bool = false
    var hangingPunctuation: Bool = false

    init() {}

    enum CodingKeys: String, CodingKey {
        case fontSize
        case tracking
        case lineHeight
        case columns
        case paragraphs
        case alignment
        case customText
        case markupEnabled
        case generateOnce
        case categories
        case otFeatures
        case substitutionFeatures
        case defaultFontPath
        case defaultFontAxisDict
        case enabledStyleIndices
        case autoSize
        case showFallback
        case columnGap
        case direction
        case paragraphIndent
        case paragraphSpace
        case hyphenation
        case hangingPunctuation
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        fontSize = try container.decodeIfPresent(Double.self, forKey: .fontSize) ?? 12
        tracking = try container.decodeIfPresent(Double.self, forKey: .tracking) ?? 0
        lineHeight = try container.decodeIfPresent(Double.self, forKey: .lineHeight) ?? 1.2
        columns = try container.decodeIfPresent(Int.self, forKey: .columns) ?? 1
        paragraphs = try container.decodeIfPresent(Int.self, forKey: .paragraphs) ?? 5
        alignment = try container.decodeIfPresent(String.self, forKey: .alignment) ?? "left"
        customText = try container.decodeIfPresent(String.self, forKey: .customText) ?? ""
        markupEnabled = try container.decodeIfPresent(Bool.self, forKey: .markupEnabled) ?? false
        generateOnce = try container.decodeIfPresent(Bool.self, forKey: .generateOnce) ?? false
        categories = try container.decodeIfPresent(CategorySettings.self, forKey: .categories) ?? CategorySettings()
        otFeatures = try container.decodeIfPresent([OTFeature].self, forKey: .otFeatures) ?? []
        substitutionFeatures = try container.decodeIfPresent([SubstitutionFeature].self, forKey: .substitutionFeatures) ?? []
        defaultFontPath = try container.decodeIfPresent(String.self, forKey: .defaultFontPath) ?? ""
        defaultFontAxisDict = try container.decodeIfPresent([String: Double].self, forKey: .defaultFontAxisDict)
        enabledStyleIndices = try container.decodeIfPresent([String: Bool].self, forKey: .enabledStyleIndices) ?? [:]
        autoSize = try container.decodeIfPresent(Bool.self, forKey: .autoSize) ?? false
        showFallback = try container.decodeIfPresent(Bool.self, forKey: .showFallback) ?? false
        columnGap = try container.decodeIfPresent(Double.self, forKey: .columnGap) ?? 20
        direction = try container.decodeIfPresent(String.self, forKey: .direction) ?? "auto"
        paragraphIndent = try container.decodeIfPresent(Double.self, forKey: .paragraphIndent) ?? 0
        paragraphSpace = try container.decodeIfPresent(Double.self, forKey: .paragraphSpace) ?? 0
        hyphenation = try container.decodeIfPresent(Bool.self, forKey: .hyphenation) ?? false
        hangingPunctuation = try container.decodeIfPresent(Bool.self, forKey: .hangingPunctuation) ?? false
    }
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
    @Published var viewMode: ViewMode = .page
    @Published var compareVertical: Bool = false

    // Output
    @Published var outputDirectory: String = ""
    @Published var currentPDFPath: String?
    @Published var proofSections: [ProofSection] = []
    @Published var previewPDFPath: String?
    @Published var previewSections: [ProofSection] = []
    @Published var finalPDFPath: String?
    @Published var finalSections: [ProofSection] = []
    @Published var finalGeneratedConfigFingerprint: String?
    @Published var currentConfigFingerprint: String?
    @Published var previewNavigationRequest: PreviewNavigationRequest?

    // PDF output
    @Published var useCustomOutputLocation: Bool = false
    @Published var customOutputLocation: String = ""

    // UI state
    @Published var showFontPicker = false
    @Published var showAddProofSheet = false
    @Published var showSettingsImporter = false
    @Published var showSidebar = true
    @Published var showThumbnailStrip = true
    @Published var showInspector = true
    @Published var fontsSectionExpanded = true
    @Published var proofsSectionExpanded = true
    @Published var outputSectionExpanded = true
    @Published var sidebarWidth: CGFloat = 240
    @Published var thumbnailStripWidth: CGFloat = 140
    @Published var inspectorWidth: CGFloat = 300

    // Available OT features from loaded fonts (minus hidden)
    private(set) var availableOTFeatures: [String] = []
    private(set) var availableSubstitutionFeatures: [String] = []
    private(set) var anyFontSupportsOpbd: Bool = false

    // MARK: - Registry cache

    private(set) var registryByKey: [String: ProofRegistryEntry] = [:]

    var isRegistryLoaded: Bool {
        !registryByKey.isEmpty
    }

    // MARK: - Persistence

    private static let settingsURL: URL = {
        let home = FileManager.default.homeDirectoryForCurrentUser
        return home.appendingPathComponent(".type-proofing-swiftui-prefs.json")
    }()

    private var persistTimer: Timer?
    weak var previewCoordinator: PreviewCoordinator?

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
                self.previewCoordinator?.proofSettingsChanged(proofID: opt.id)
                self.schedulePersist(notifyPreview: false)
            }
        )
    }

    var selectedRegistryEntry: ProofRegistryEntry? {
        guard let opt = selectedProofOption else { return nil }
        return registryByKey[opt.baseType]
    }

    var isFinalPDFStale: Bool {
        guard finalPDFPath != nil,
              let finalGeneratedConfigFingerprint else { return false }
        let current = currentConfigFingerprint ?? buildProofConfig().fingerprint()
        return current != finalGeneratedConfigFingerprint
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
                    availableSubstitutionFeatures = engine.getAvailableSubstitutionFeatures(path: fontPaths[0])
                    if outputDirectory.isEmpty {
                        outputDirectory = (fontPaths[0] as NSString).deletingLastPathComponent
                    }
                }
            }
            refreshCurrentConfigFingerprint()
            return
        }

        // Fresh initialization from engine defaults
        if !pageFormats.isEmpty && !pageFormats.contains(pageFormat) {
            pageFormat = pageFormats.first!
        }

        proofOptions = makeDefaultProofOptions()

        // Initialize default proof settings for each
        for option in proofOptions {
            initializeDefaultSettings(for: option)
        }

        // Select the first option
        if let first = proofOptions.first {
            selectedProof = first.id
        }
        refreshCurrentConfigFingerprint()
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

    private func makeDefaultProofOptions() -> [ProofOption] {
        registryByKey.values.sorted { lhs, rhs in
            if lhs.displayOrder == rhs.displayOrder {
                return lhs.displayName < rhs.displayName
            }
            return lhs.displayOrder < rhs.displayOrder
        }.enumerated().map { index, entry in
            ProofOption(
                name: entry.displayName,
                baseType: entry.key,
                enabled: entry.defaultEnabled,
                order: index
            )
        }
    }

    private func resetProofDefaults() {
        proofOptions = makeDefaultProofOptions()
        for index in proofOptions.indices {
            proofOptions[index].enabled = false
        }
        proofSettingsByProof.removeAll()
        for option in proofOptions {
            initializeDefaultSettings(for: option)
            if !availableOTFeatures.isEmpty {
                proofSettingsByProof[option.name]?.otFeatures = buildDefaultOTFeatures(for: option.baseType)
            }
            if !availableSubstitutionFeatures.isEmpty {
                proofSettingsByProof[option.name]?.substitutionFeatures = buildDefaultSubstitutionFeatures(for: option.baseType)
            }
        }
        selectedProof = proofOptions.first?.id
    }

    private func clearGeneratedOutput() {
        currentPDFPath = nil
        proofSections = []
        previewPDFPath = nil
        previewSections = []
        previewNavigationRequest = nil
        finalPDFPath = nil
        finalSections = []
        finalGeneratedConfigFingerprint = nil
    }

    func requestPreviewNavigation(to proofID: ProofOption.ID) {
        guard let option = proofOptions.first(where: { $0.id == proofID }),
              option.enabled,
              let section = previewSections.first(where: { $0.name == option.name })
        else { return }
        previewNavigationRequest = PreviewNavigationRequest(
            proofID: proofID,
            proofName: option.name,
            pageIndex: section.firstPage
        )
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
            availableSubstitutionFeatures = engine.getAvailableSubstitutionFeatures(path: firstPath)
            anyFontSupportsOpbd = fontPaths.contains { FontLoader.fontSupportsOpbd(path: $0) }

            // Sync OT features with what the font actually has, preserving enabled states
            for (name, _) in proofSettingsByProof {
                let baseType = proofOptions.first(where: { $0.name == name })?.baseType
                proofSettingsByProof[name]?.otFeatures = syncOTFeatures(
                    existing: proofSettingsByProof[name]?.otFeatures ?? [],
                    available: availableOTFeatures,
                    baseType: baseType
                )
                if proofSettingsByProof[name]?.substitutionFeatures.isEmpty ?? true {
                    proofSettingsByProof[name]?.substitutionFeatures = buildDefaultSubstitutionFeatures(for: baseType)
                }
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
            if baseType == "spacing_proof" && tag == "kern" {
                enabled = false
            }
            return OTFeature(id: tag, tag: tag, enabled: enabled)
        }
    }

    private func syncOTFeatures(existing: [OTFeature], available: [String], baseType: String?) -> [OTFeature] {
        if existing.isEmpty { return buildDefaultOTFeatures(for: baseType) }
        let existingByTag = Dictionary(existing.map { ($0.tag, $0.enabled) }, uniquingKeysWith: { first, _ in first })
        return available.map { tag in
            let enabled = existingByTag[tag] ?? DEFAULT_ON_FEATURES.contains(tag)
            return OTFeature(id: tag, tag: tag, enabled: enabled)
        }
    }

    private func supportsSubstitutionCategories(_ baseType: String?) -> Bool {
        baseType == "filtered_character_set" ||
            baseType == "spacing_proof" ||
            baseType == "multi_style_comparison" ||
            baseType == "substitution_overview"
    }

    private func buildDefaultSubstitutionFeatures(for baseType: String?) -> [SubstitutionFeature] {
        guard supportsSubstitutionCategories(baseType) else { return [] }
        return availableSubstitutionFeatures.map { tag in
            SubstitutionFeature(id: tag, tag: tag, enabled: baseType == "substitution_overview")
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
        disabledFontPaths.removeAll()
        fontStyles.removeAll()
        availableOTFeatures.removeAll()
        availableSubstitutionFeatures.removeAll()
        anyFontSupportsOpbd = false
        outputDirectory = ""
        useCustomOutputLocation = false
        customOutputLocation = ""
        clearGeneratedOutput()
        schedulePersist()
    }

    // MARK: - Proof Reordering

    func moveProofOptions(from source: IndexSet, to destination: Int) {
        proofOptions.move(fromOffsets: source, toOffset: destination)
        for (i, _) in proofOptions.enumerated() {
            proofOptions[i].order = i
        }
        refreshCurrentConfigFingerprint()
        previewCoordinator?.proofOrderChanged()
        schedulePersist(notifyPreview: false)
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
        if !availableSubstitutionFeatures.isEmpty {
            proofSettingsByProof[newName]?.substitutionFeatures = buildDefaultSubstitutionFeatures(for: baseType)
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

    func refreshCurrentConfigFingerprint() {
        currentConfigFingerprint = buildProofConfig().fingerprint()
    }

    func previewFingerprint(for option: ProofOption) -> String {
        guard let entry = registryByKey[option.baseType] else {
            return buildProofConfig().fingerprint()
        }
        let settingsKey = pythonSettingsKey(for: option, entry: entry)
        let flatSettings = buildFlatProofSettings().filter { key, _ in
            key.hasPrefix("\(settingsKey)_") ||
                key.hasPrefix("otf_\(settingsKey)_")
        }
        let payload: [String: Any] = [
            "font_paths": enabledFontPaths,
            "axis_values_by_font": axisValuesByFont.filter { enabledFontPaths.contains($0.key) },
            "proof_option": [
                "Option": option.name,
                "Enabled": option.enabled,
                "_original_option": option.baseType,
            ],
            "proof_settings": flatSettings,
            "page_format": pageFormat,
            "show_baselines": showBaselines,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]) else {
            return UUID().uuidString
        }
        return data.base64EncodedString()
    }

    func makeRunSummary() -> ProofRunSummary {
        let enabledProofs = proofOptions.filter(\.enabled)
        let axisCounts = enabledFontPaths.map { path -> Int in
            guard let axes = axisValuesByFont[path], !axes.isEmpty else { return 1 }
            return axes.values.reduce(1) { partial, values in
                partial * max(1, values.count)
            }
        }
        let totalAxisInstances = axisCounts.reduce(0, +)
        let outputDir = useCustomOutputLocation && !customOutputLocation.isEmpty
            ? customOutputLocation
            : outputDirectory
        var warnings: [String] = []
        if totalAxisInstances >= 40 {
            warnings.append("Variable font settings will generate \(totalAxisInstances) font instances.")
        }
        if enabledProofs.count >= 12 {
            warnings.append("\(enabledProofs.count) proof sections are enabled.")
        }
        if outputDir.isEmpty {
            warnings.append("No output directory is available.")
        }

        return ProofRunSummary(
            fontCount: enabledFontPaths.count,
            enabledProofCount: enabledProofs.count,
            enabledProofs: enabledProofs.map(\.name),
            totalAxisInstances: totalAxisInstances,
            estimatedWorkItems: enabledProofs.count * max(1, totalAxisInstances),
            pageFormat: pageFormat,
            outputDir: outputDir,
            showBaselines: showBaselines,
            warnings: warnings
        )
    }

    /// Convert the per-proof ProofSettings structs into the flat dictionary
    /// format the Python engine expects: `{proof_key}_fontSize`, `otf_{proof_key}_{tag}`, etc.
    private func buildFlatProofSettings() -> [String: Any] {
        var flat: [String: Any] = [:]

        for option in proofOptions {
            guard let settings = proofSettingsByProof[option.name] else { continue }
            guard let entry = registryByKey[option.baseType] else { continue }
            let settingsKey = pythonSettingsKey(for: option, entry: entry)

            // Font size — always present
            flat["\(settingsKey)_fontSize"] = Int(settings.fontSize)

            // Line height — always send for proofs that support it (em ratio)
            if entry.supportsLineHeight {
                flat["\(settingsKey)_lineHeight"] = settings.lineHeight
            }

            // Columns — only for proofs that support it
            if entry.supportsCols {
                flat["\(settingsKey)_cols"] = settings.columns
                flat["\(settingsKey)_columnGap"] = settings.columnGap
            }

            // Tracking — only for proofs that support formatting
            if entry.supportsFormatting {
                flat["\(settingsKey)_tracking"] = settings.tracking
            }

            // Alignment — only for proofs that support formatting
            if entry.supportsFormatting {
                flat["\(settingsKey)_align"] = settings.alignment
                flat["\(settingsKey)_direction"] = settings.direction
                flat["\(settingsKey)_paragraphIndent"] = settings.paragraphIndent
                flat["\(settingsKey)_paragraphSpace"] = settings.paragraphSpace
                flat["\(settingsKey)_hyphenation"] = settings.hyphenation
                flat["\(settingsKey)_hangingPunctuation"] = settings.hangingPunctuation
            }

            // Paragraphs — only for proofs that have them
            if entry.hasParagraphs {
                flat["\(settingsKey)_para"] = settings.paragraphs
            }

            // Character categories
            if entry.hasCategories {
                flat["\(settingsKey)_cat_uppercase_base"] = settings.categories.uppercaseBase
                flat["\(settingsKey)_cat_lowercase_base"] = settings.categories.lowercaseBase
                flat["\(settingsKey)_cat_numbers_symbols"] = settings.categories.numbersSymbols
                flat["\(settingsKey)_cat_punctuation"] = settings.categories.punctuation
                flat["\(settingsKey)_cat_accented"] = settings.categories.accented
            }
            if supportsSubstitutionCategories(option.baseType) {
                for feature in settings.substitutionFeatures {
                    flat["\(settingsKey)_sub_\(feature.tag)"] = feature.enabled
                }
            }

            // Custom text
            if entry.hasCustomText {
                flat["\(settingsKey)_customText"] = settings.customText
                flat["\(settingsKey)_markupEnabled"] = settings.markupEnabled
                if !entry.isMultiStyle {
                    flat["\(settingsKey)_generateOnce"] = settings.generateOnce
                    // Default font path for "generate once"
                    if !settings.defaultFontPath.isEmpty {
                        flat["\(settingsKey)_defaultFontPath"] = settings.defaultFontPath
                    }
                    if let axisDict = settings.defaultFontAxisDict {
                        flat["\(settingsKey)_defaultFontAxisDict"] = axisDict
                    }
                }
            }

            // Multi-style: per-style enabled flags
            if entry.isMultiStyle {
                for (indexStr, enabled) in settings.enabledStyleIndices {
                    flat["\(settingsKey)_style_\(indexStr)"] = enabled
                }
            }

            // Auto-size (charset: fit category in one page; multi-style: fit in one line)
            if option.baseType == "filtered_character_set" || entry.isMultiStyle {
                flat["\(settingsKey)_autoSize"] = settings.autoSize
            }

            // Multi-style: show/hide fallback glyphs for missing characters
            if entry.isMultiStyle {
                flat["\(settingsKey)_showFallback"] = settings.showFallback
            }

            // OpenType features
            for feature in settings.otFeatures {
                flat["otf_\(settingsKey)_\(feature.tag)"] = feature.enabled
            }
        }

        return flat
    }

    // MARK: - Settings Persistence

    private func schedulePersist(notifyPreview: Bool = true) {
        refreshCurrentConfigFingerprint()
        if notifyPreview {
            previewCoordinator?.stateChanged(debounced: true)
        }
        persistTimer?.invalidate()
        persistTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: false) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.persistState()
            }
        }
    }

    /// Public wrapper for views that need to trigger persistence (e.g. checkbox toggles)
    func schedulePersistPublic(notifyPreview: Bool = true) {
        schedulePersist(notifyPreview: notifyPreview)
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
        guard isRegistryLoaded else { return }

        resetProofDefaults()
        showBaselines = false
        pageFormat = pageFormats.contains("A4Landscape") ? "A4Landscape" : (pageFormats.first ?? "A4Landscape")
        useCustomOutputLocation = false
        customOutputLocation = ""
        if let first = fontPaths.first {
            outputDirectory = (first as NSString).deletingLastPathComponent
        } else {
            outputDirectory = ""
        }
        clearGeneratedOutput()
        persistState()
    }

    func setAvailableOTFeatures(_ features: [String]) {
        availableOTFeatures = features
    }

    func setAvailableSubstitutionFeatures(_ features: [String]) {
        availableSubstitutionFeatures = features
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
