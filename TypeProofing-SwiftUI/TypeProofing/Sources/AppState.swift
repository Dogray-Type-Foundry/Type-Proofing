import SwiftUI
import UniformTypeIdentifiers

// MARK: - View Mode

enum ViewMode: String, CaseIterable {
    case page
    case grid
    case compare
}

// MARK: - Proof Key Utilities

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
    let id: String
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
    var accented: Bool = false
}

struct ProofSettings: Codable {
    var fontSize: Double = 12
    var tracking: Double = 0
    var lineHeight: Double = 1.2
    var columns: Int = 1
    var paragraphs: Int = 5
    var alignment: String = "left"
    var customText: String = ""
    var markupEnabled: Bool = false
    var generateOnce: Bool = false
    var categories: CategorySettings = CategorySettings()
    var otFeatures: [OTFeature] = []
    var substitutionFeatures: [SubstitutionFeature] = []
    var defaultFontPath: String = ""
    var defaultFontAxisDict: [String: Double]? = nil
    var enabledStyleIndices: [String: Bool] = [:]
    var autoSize: Bool = false
    var showFallback: Bool = false
    var columnGap: Double = 20
    var direction: String = "auto"
    var paragraphIndent: Double = 0
    var paragraphSpace: Double = 0
    var hyphenation: Bool = false
    var hangingPunctuation: Bool = false

    init() {}

    enum CodingKeys: String, CodingKey {
        case fontSize, tracking, lineHeight, columns, paragraphs, alignment
        case customText, markupEnabled, generateOnce, categories
        case otFeatures, substitutionFeatures
        case defaultFontPath, defaultFontAxisDict, enabledStyleIndices
        case autoSize, showFallback
        case columnGap, direction, paragraphIndent, paragraphSpace
        case hyphenation, hangingPunctuation
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

struct FontStyleEntry: Identifiable, Equatable {
    var id: Int { index }
    let index: Int
    let fontPath: String
    let familyName: String
    let styleName: String
    let isVariable: Bool
    let coordinates: [String: Double]?
}

enum StyleSourceMode: String, Codable {
    case namedInstances
    case customPositions
}

// MARK: - FontState

@MainActor
final class FontState: ObservableObject {
    @Published var fontPaths: [String] = []
    @Published var loadedFonts: [FontInfo] = []
    @Published var axisValuesByFont: [String: [String: [Double]]] = [:]
    @Published var disabledFontPaths: Set<String> = []
    @Published var fontSortCriteria: [FontSortCriterion] = []
    @Published var fontStyles: [FontStyleEntry] = []
    @Published var styleSourceMode: StyleSourceMode = .namedInstances

    var availableOTFeatures: [String] = []
    var availableSubstitutionFeatures: [String] = []
    var anyFontSupportsOpbd: Bool = false

    var fontStylesByFamily: [(familyName: String, styles: [FontStyleEntry])] {
        let grouped = Dictionary(grouping: fontStyles, by: \.familyName)
        var seen = Set<String>()
        var order: [String] = []
        for style in fontStyles {
            if seen.insert(style.familyName).inserted {
                order.append(style.familyName)
            }
        }
        return order.map { name in (familyName: name, styles: grouped[name]!) }
    }

    var anyFontSupportsArabic: Bool {
        loadedFonts.contains(where: \.supportsArabic)
    }

    var enabledFontPaths: [String] {
        fontPaths.filter { !disabledFontPaths.contains($0) }
    }
}

// MARK: - ProofState

@MainActor
final class ProofState: ObservableObject {
    @Published var proofOptions: [ProofOption] = []
    @Published var selectedProof: ProofOption.ID?
    @Published var proofSettingsByProof: [String: ProofSettings] = [:]

    var registryByKey: [String: ProofRegistryEntry] = [:]

    var onSettingsChanged: ((ProofOption.ID) -> Void)?

    var isRegistryLoaded: Bool { !registryByKey.isEmpty }

    var selectedProofOption: ProofOption? {
        guard let id = selectedProof else { return nil }
        return proofOptions.first { $0.id == id }
    }

    var selectedRegistryEntry: ProofRegistryEntry? {
        guard let opt = selectedProofOption else { return nil }
        return registryByKey[opt.baseType]
    }

    var selectedProofSettings: Binding<ProofSettings> {
        Binding(
            get: { [weak self] in
                guard let self, let opt = self.selectedProofOption else { return ProofSettings() }
                return self.proofSettingsByProof[opt.name] ?? ProofSettings()
            },
            set: { [weak self] newValue in
                guard let self, let opt = self.selectedProofOption else { return }
                self.proofSettingsByProof[opt.name] = newValue
                self.onSettingsChanged?(opt.id)
            }
        )
    }
}

// MARK: - PreviewState

@MainActor
final class PreviewState: ObservableObject {
    @Published var previewPDFPath: String?
    @Published var previewSections: [ProofSection] = []
    @Published var previewNavigationRequest: PreviewNavigationRequest?
    @Published var currentPDFPath: String?
    @Published var proofSections: [ProofSection] = []
    @Published var finalPDFPath: String?
    @Published var finalSections: [ProofSection] = []
    @Published var finalGeneratedConfigFingerprint: String?
    @Published var currentConfigFingerprint: String?
}

// MARK: - PageState

@MainActor
final class PageState: ObservableObject {
    @Published var pageFormat: String = "A4Landscape"
    @Published var pageFormats: [String] = []
    @Published var showBaselines: Bool = false
    @Published var viewMode: ViewMode = .page
    @Published var compareVertical: Bool = false
}

// MARK: - UIState

@MainActor
final class UIState: ObservableObject {
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
}

// MARK: - OutputState

@MainActor
final class OutputState: ObservableObject {
    @Published var outputDirectory: String = ""
    @Published var useCustomOutputLocation: Bool = false
    @Published var customOutputLocation: String = ""
}

// MARK: - AppState

@MainActor
final class AppState: ObservableObject {
    let fonts = FontState()
    let proofs = ProofState()
    let preview = PreviewState()
    let page = PageState()
    let ui = UIState()
    let output = OutputState()

    @Published private(set) var cachedRunSummary = ProofRunSummary()

    private static let settingsURL: URL = {
        let home = FileManager.default.homeDirectoryForCurrentUser
        return home.appendingPathComponent(".type-proofing-swiftui-prefs.json")
    }()

    private var persistTimer: Timer?
    weak var previewCoordinator: PreviewCoordinator?
    weak var pdfCoordinator: PDFViewCoordinator?

    init() {
        proofs.onSettingsChanged = { [weak self] proofID in
            self?.previewCoordinator?.proofSettingsChanged(proofID: proofID)
            self?.schedulePersist(notifyPreview: false)
        }
    }

    // MARK: - Cross-Cutting Computed

    var isFinalPDFStale: Bool {
        guard preview.finalPDFPath != nil,
              let generated = preview.finalGeneratedConfigFingerprint else { return false }
        let current = preview.currentConfigFingerprint ?? buildProofConfig().fingerprint()
        return current != generated
    }

    // MARK: - Initialization from Engine

    func loadFromEngine(_ engine: ProofEngine) {
        let registry = engine.getProofRegistry()
        for entry in registry {
            proofs.registryByKey[entry.key] = entry
        }

        page.pageFormats = engine.getPageFormats()

        if loadPersistedState() {
            if !page.pageFormats.isEmpty && !page.pageFormats.contains(page.pageFormat) {
                page.pageFormat = page.pageFormats.first!
            }
            if let first = proofs.proofOptions.first, proofs.selectedProof == nil {
                proofs.selectedProof = first.id
            }
            if !fonts.fontPaths.isEmpty {
                let existingPaths = fonts.fontPaths.filter { FileManager.default.fileExists(atPath: $0) }
                if existingPaths.count != fonts.fontPaths.count {
                    fonts.fontPaths = existingPaths
                }
                if !fonts.fontPaths.isEmpty {
                    fonts.loadedFonts = engine.getFontMetadata(paths: fonts.fontPaths)
                    applySortCriteria()
                    refreshFontStyles(engine: engine)
                    let allFeatures = engine.getAvailableOTFeatures(path: fonts.fontPaths[0])
                    fonts.availableOTFeatures = allFeatures.filter { !HIDDEN_FEATURES.contains($0) }
                    fonts.availableSubstitutionFeatures = engine.getAvailableSubstitutionFeatures(path: fonts.fontPaths[0])
                    if output.outputDirectory.isEmpty {
                        output.outputDirectory = (fonts.fontPaths[0] as NSString).deletingLastPathComponent
                    }
                }
            }
            refreshCurrentConfigFingerprint()
            return
        }

        if !page.pageFormats.isEmpty && !page.pageFormats.contains(page.pageFormat) {
            page.pageFormat = page.pageFormats.first!
        }

        proofs.proofOptions = makeDefaultProofOptions()

        for option in proofs.proofOptions {
            initializeDefaultSettings(for: option)
        }

        if let first = proofs.proofOptions.first {
            proofs.selectedProof = first.id
        }
        refreshCurrentConfigFingerprint()
    }

    private func initializeDefaultSettings(for option: ProofOption) {
        guard let entry = proofs.registryByKey[option.baseType] else { return }
        var settings = ProofSettings()
        settings.fontSize = Double(entry.defaultFontSize)
        settings.columns = entry.defaultColumns
        settings.alignment = entry.isArabic ? "right" : "left"
        settings.paragraphs = entry.hasParagraphs ? 5 : 2
        proofs.proofSettingsByProof[option.name] = settings
    }

    private func makeDefaultProofOptions() -> [ProofOption] {
        proofs.registryByKey.values.sorted { lhs, rhs in
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
        proofs.proofOptions = makeDefaultProofOptions()
        for index in proofs.proofOptions.indices {
            proofs.proofOptions[index].enabled = false
        }
        proofs.proofSettingsByProof.removeAll()
        for option in proofs.proofOptions {
            initializeDefaultSettings(for: option)
            if !fonts.availableOTFeatures.isEmpty {
                proofs.proofSettingsByProof[option.name]?.otFeatures = buildDefaultOTFeatures(for: option.baseType)
            }
            if !fonts.availableSubstitutionFeatures.isEmpty {
                proofs.proofSettingsByProof[option.name]?.substitutionFeatures = buildDefaultSubstitutionFeatures(for: option.baseType)
            }
        }
        proofs.selectedProof = proofs.proofOptions.first?.id
    }

    private func clearGeneratedOutput() {
        preview.currentPDFPath = nil
        preview.proofSections = []
        preview.previewPDFPath = nil
        preview.previewSections = []
        preview.previewNavigationRequest = nil
        preview.finalPDFPath = nil
        preview.finalSections = []
        preview.finalGeneratedConfigFingerprint = nil
    }

    func requestPreviewNavigation(to proofID: ProofOption.ID) {
        guard let option = proofs.proofOptions.first(where: { $0.id == proofID }),
              option.enabled,
              let section = preview.previewSections.first(where: { $0.name == option.name })
        else { return }
        let request = PreviewNavigationRequest(
            proofID: proofID,
            proofName: option.name,
            pageIndex: section.firstPage
        )
        let coordinator = pdfCoordinator
        Task { @MainActor in
            guard let pdfView = coordinator?.pdfView,
                  let document = pdfView.document else { return }
            coordinator?.handleNavigation(request, in: document)
        }
    }

    // MARK: - Font Management

    func addFonts(urls: [URL], engine: ProofEngine) {
        let paths = urls.map { $0.path }
        let newPaths = paths.filter { !fonts.fontPaths.contains($0) }
        guard !newPaths.isEmpty else { return }

        fonts.fontPaths.append(contentsOf: newPaths)
        let metadata = engine.getFontMetadata(paths: newPaths)
        fonts.loadedFonts.append(contentsOf: metadata)
        applySortCriteria()

        for font in metadata where font.isVariable {
            if fonts.axisValuesByFont[font.id] == nil {
                var axisDefaults: [String: [Double]] = [:]
                for axis in font.axes {
                    var initial: [Double] = [axis.minValue]
                    if axis.defaultValue != axis.minValue && axis.defaultValue != axis.maxValue {
                        initial.append(axis.defaultValue)
                    }
                    initial.append(axis.maxValue)
                    axisDefaults[axis.id] = initial
                }
                fonts.axisValuesByFont[font.id] = axisDefaults
            }
        }

        if output.outputDirectory.isEmpty, let first = fonts.fontPaths.first {
            output.outputDirectory = (first as NSString).deletingLastPathComponent
        }

        if let firstPath = fonts.fontPaths.first {
            let allFeatures = engine.getAvailableOTFeatures(path: firstPath)
            fonts.availableOTFeatures = allFeatures.filter { !HIDDEN_FEATURES.contains($0) }
            fonts.availableSubstitutionFeatures = engine.getAvailableSubstitutionFeatures(path: firstPath)
            fonts.anyFontSupportsOpbd = fonts.fontPaths.contains { FontLoader.fontSupportsOpbd(path: $0) }

            for (name, _) in proofs.proofSettingsByProof {
                let baseType = proofs.proofOptions.first(where: { $0.name == name })?.baseType
                proofs.proofSettingsByProof[name]?.otFeatures = syncOTFeatures(
                    existing: proofs.proofSettingsByProof[name]?.otFeatures ?? [],
                    available: fonts.availableOTFeatures,
                    baseType: baseType
                )
                if proofs.proofSettingsByProof[name]?.substitutionFeatures.isEmpty ?? true {
                    proofs.proofSettingsByProof[name]?.substitutionFeatures = buildDefaultSubstitutionFeatures(for: baseType)
                }
            }
        }

        refreshFontStyles(engine: engine)
        schedulePersist()
    }

    func refreshFontStyles(engine: ProofEngine) {
        fonts.fontStyles = engine.getFontStyles(
            paths: fonts.enabledFontPaths,
            mode: fonts.styleSourceMode,
            axisValuesByFont: fonts.axisValuesByFont
        )
    }

    private func buildDefaultOTFeatures(for baseType: String?) -> [OTFeature] {
        fonts.availableOTFeatures.map { tag in
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
        return fonts.availableSubstitutionFeatures.map { tag in
            SubstitutionFeature(id: tag, tag: tag, enabled: baseType == "substitution_overview")
        }
    }

    func removeFont(at offsets: IndexSet, engine: ProofEngine? = nil) {
        let pathsToRemove = offsets.map { fonts.loadedFonts[$0].id }
        fonts.loadedFonts.remove(atOffsets: offsets)
        fonts.fontPaths.removeAll { pathsToRemove.contains($0) }
        for path in pathsToRemove {
            fonts.axisValuesByFont.removeValue(forKey: path)
            fonts.disabledFontPaths.remove(path)
        }
        if let engine { refreshFontStyles(engine: engine) }
        schedulePersist()
    }

    func moveFonts(from source: IndexSet, to destination: Int) {
        fonts.loadedFonts.move(fromOffsets: source, toOffset: destination)
        fonts.fontPaths = fonts.loadedFonts.map(\.id)
        schedulePersist()
    }

    func applySortCriteria() {
        guard !fonts.fontSortCriteria.isEmpty else { return }
        fonts.loadedFonts = fonts.loadedFonts.sorted(by: fonts.fontSortCriteria)
        fonts.fontPaths = fonts.loadedFonts.map(\.id)
        schedulePersist()
    }

    func resetFonts() {
        fonts.fontPaths.removeAll()
        fonts.loadedFonts.removeAll()
        fonts.axisValuesByFont.removeAll()
        fonts.disabledFontPaths.removeAll()
        fonts.fontStyles.removeAll()
        fonts.availableOTFeatures.removeAll()
        fonts.availableSubstitutionFeatures.removeAll()
        fonts.anyFontSupportsOpbd = false
        output.outputDirectory = ""
        output.useCustomOutputLocation = false
        output.customOutputLocation = ""
        clearGeneratedOutput()
        schedulePersist()
    }

    // MARK: - Proof Reordering

    func moveProofOptions(from source: IndexSet, to destination: Int) {
        proofs.proofOptions.move(fromOffsets: source, toOffset: destination)
        for (i, _) in proofs.proofOptions.enumerated() {
            proofs.proofOptions[i].order = i
        }
        refreshCurrentConfigFingerprint()
        previewCoordinator?.proofOrderChanged()
        schedulePersist(notifyPreview: false)
    }

    // MARK: - Add/Remove Proof Instance

    func generateUniqueName(for baseType: String) -> String {
        let baseName = proofs.registryByKey[baseType]?.displayName ?? baseType
        let existingNames = Set(proofs.proofOptions.map(\.name))
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
            order: proofs.proofOptions.count
        )
        proofs.proofOptions.append(newOption)
        initializeDefaultSettings(for: newOption)

        if !fonts.availableOTFeatures.isEmpty {
            proofs.proofSettingsByProof[newName]?.otFeatures = buildDefaultOTFeatures(for: baseType)
        }
        if !fonts.availableSubstitutionFeatures.isEmpty {
            proofs.proofSettingsByProof[newName]?.substitutionFeatures = buildDefaultSubstitutionFeatures(for: baseType)
        }

        schedulePersist()
    }

    func removeProofOption(at offsets: IndexSet) {
        let names = offsets.map { proofs.proofOptions[$0].name }
        proofs.proofOptions.remove(atOffsets: offsets)
        for name in names {
            proofs.proofSettingsByProof.removeValue(forKey: name)
        }
        for (i, _) in proofs.proofOptions.enumerated() {
            proofs.proofOptions[i].order = i
        }
        schedulePersist()
    }

    // MARK: - Build ProofConfig for Engine

    func buildProofConfig() -> ProofConfig {
        let axisValuesForEngine = fonts.axisValuesByFont
        let pySettings = buildFlatProofSettings()

        let outDir: String
        if output.useCustomOutputLocation && !output.customOutputLocation.isEmpty {
            outDir = output.customOutputLocation
        } else {
            outDir = output.outputDirectory
        }

        return ProofConfig(
            fontPaths: fonts.enabledFontPaths,
            axisValuesByFont: axisValuesForEngine,
            proofOptions: proofs.proofOptions,
            proofSettings: pySettings,
            pageFormat: page.pageFormat,
            outputDir: outDir,
            showBaselines: page.showBaselines
        )
    }

    func refreshCurrentConfigFingerprint() {
        preview.currentConfigFingerprint = buildProofConfig().fingerprint()
        cachedRunSummary = makeRunSummary()
    }

    func previewFingerprint(for option: ProofOption) -> String {
        previewFingerprint(for: option, flatSettings: buildFlatProofSettings())
    }

    func previewFingerprint(for option: ProofOption, flatSettings: [String: Any]) -> String {
        guard let entry = proofs.registryByKey[option.baseType] else {
            return buildProofConfig().fingerprint()
        }
        let settingsKey = pythonSettingsKey(for: option, entry: entry)
        let filtered = flatSettings.filter { key, _ in
            key.hasPrefix("\(settingsKey)_") ||
                key.hasPrefix("otf_\(settingsKey)_")
        }
        let payload: [String: Any] = [
            "font_paths": fonts.enabledFontPaths,
            "axis_values_by_font": fonts.axisValuesByFont.filter { fonts.enabledFontPaths.contains($0.key) },
            "proof_option": [
                "Option": option.name,
                "Enabled": option.enabled,
                "_original_option": option.baseType,
            ],
            "proof_settings": filtered,
            "page_format": page.pageFormat,
            "show_baselines": page.showBaselines,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]) else {
            return UUID().uuidString
        }
        return data.base64EncodedString()
    }

    func makeRunSummary() -> ProofRunSummary {
        let enabledProofs = proofs.proofOptions.filter(\.enabled)
        let axisCounts = fonts.enabledFontPaths.map { path -> Int in
            guard let axes = fonts.axisValuesByFont[path], !axes.isEmpty else { return 1 }
            return axes.values.reduce(1) { partial, values in
                partial * max(1, values.count)
            }
        }
        let totalAxisInstances = axisCounts.reduce(0, +)
        let outputDir = output.useCustomOutputLocation && !output.customOutputLocation.isEmpty
            ? output.customOutputLocation
            : output.outputDirectory
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
            fontCount: fonts.enabledFontPaths.count,
            enabledProofCount: enabledProofs.count,
            enabledProofs: enabledProofs.map(\.name),
            totalAxisInstances: totalAxisInstances,
            estimatedWorkItems: enabledProofs.count * max(1, totalAxisInstances),
            pageFormat: page.pageFormat,
            outputDir: outputDir,
            showBaselines: page.showBaselines,
            warnings: warnings
        )
    }

    func buildFlatProofSettings() -> [String: Any] {
        var flat: [String: Any] = [:]

        for option in proofs.proofOptions {
            guard let settings = proofs.proofSettingsByProof[option.name] else { continue }
            guard let entry = proofs.registryByKey[option.baseType] else { continue }
            let settingsKey = pythonSettingsKey(for: option, entry: entry)

            flat["\(settingsKey)_fontSize"] = Int(settings.fontSize)

            if entry.supportsLineHeight {
                flat["\(settingsKey)_lineHeight"] = settings.lineHeight
            }

            if entry.supportsCols {
                flat["\(settingsKey)_cols"] = settings.columns
                flat["\(settingsKey)_columnGap"] = settings.columnGap
            }

            if entry.supportsFormatting {
                flat["\(settingsKey)_tracking"] = settings.tracking
                flat["\(settingsKey)_align"] = settings.alignment
                flat["\(settingsKey)_direction"] = settings.direction
                flat["\(settingsKey)_paragraphIndent"] = settings.paragraphIndent
                flat["\(settingsKey)_paragraphSpace"] = settings.paragraphSpace
                flat["\(settingsKey)_hyphenation"] = settings.hyphenation
                flat["\(settingsKey)_hangingPunctuation"] = settings.hangingPunctuation
            }

            if entry.hasParagraphs {
                flat["\(settingsKey)_para"] = settings.paragraphs
            }

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

            if entry.hasCustomText {
                flat["\(settingsKey)_customText"] = settings.customText
                flat["\(settingsKey)_markupEnabled"] = settings.markupEnabled
                if !entry.isMultiStyle {
                    flat["\(settingsKey)_generateOnce"] = settings.generateOnce
                    if !settings.defaultFontPath.isEmpty {
                        flat["\(settingsKey)_defaultFontPath"] = settings.defaultFontPath
                    }
                    if let axisDict = settings.defaultFontAxisDict {
                        flat["\(settingsKey)_defaultFontAxisDict"] = axisDict
                    }
                }
            }

            if entry.isMultiStyle {
                flat["\(settingsKey)_styleSourceMode"] = fonts.styleSourceMode.rawValue
                for (indexStr, enabled) in settings.enabledStyleIndices {
                    flat["\(settingsKey)_style_\(indexStr)"] = enabled
                }
            }

            if option.baseType == "filtered_character_set" || entry.isMultiStyle {
                flat["\(settingsKey)_autoSize"] = settings.autoSize
            }

            if entry.isMultiStyle {
                flat["\(settingsKey)_showFallback"] = settings.showFallback
            }

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

    func schedulePersistPublic(notifyPreview: Bool = true) {
        schedulePersist(notifyPreview: notifyPreview)
    }

    func persistState() {
        let data = PersistedState(
            fontPaths: fonts.fontPaths,
            axisValuesByFont: fonts.axisValuesByFont,
            disabledFontPaths: Array(fonts.disabledFontPaths),
            fontSortCriteria: fonts.fontSortCriteria,
            styleSourceMode: fonts.styleSourceMode,
            proofOptions: proofs.proofOptions.map {
                PersistedProofOption(name: $0.name, baseType: $0.baseType, enabled: $0.enabled, order: $0.order)
            },
            proofSettingsByProof: proofs.proofSettingsByProof,
            pageFormat: page.pageFormat,
            showBaselines: page.showBaselines,
            useCustomOutputLocation: output.useCustomOutputLocation,
            customOutputLocation: output.customOutputLocation
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

            fonts.fontPaths = data.fontPaths
            fonts.axisValuesByFont = data.axisValuesByFont
            fonts.disabledFontPaths = Set(data.disabledFontPaths ?? [])
            fonts.fontSortCriteria = data.fontSortCriteria ?? []
            fonts.styleSourceMode = data.styleSourceMode ?? .namedInstances
            page.pageFormat = data.pageFormat
            page.showBaselines = data.showBaselines
            output.useCustomOutputLocation = data.useCustomOutputLocation
            output.customOutputLocation = data.customOutputLocation

            proofs.proofOptions = data.proofOptions.enumerated().map { (i, po) in
                ProofOption(name: po.name, baseType: po.baseType, enabled: po.enabled, order: po.order)
            }
            proofs.proofSettingsByProof = data.proofSettingsByProof

            if let first = proofs.proofOptions.first {
                proofs.selectedProof = first.id
            }

            if output.outputDirectory.isEmpty, let first = fonts.fontPaths.first {
                output.outputDirectory = (first as NSString).deletingLastPathComponent
            }

            return true
        } catch {
            print("Settings load error: \(error)")
            return false
        }
    }

    func resetAllSettings() {
        guard proofs.isRegistryLoaded else { return }

        resetProofDefaults()
        page.showBaselines = false
        page.pageFormat = page.pageFormats.contains("A4Landscape") ? "A4Landscape" : (page.pageFormats.first ?? "A4Landscape")
        output.useCustomOutputLocation = false
        output.customOutputLocation = ""
        if let first = fonts.fontPaths.first {
            output.outputDirectory = (first as NSString).deletingLastPathComponent
        } else {
            output.outputDirectory = ""
        }
        clearGeneratedOutput()
        persistState()
    }

    func setAvailableOTFeatures(_ features: [String]) {
        fonts.availableOTFeatures = features
    }

    func setAvailableSubstitutionFeatures(_ features: [String]) {
        fonts.availableSubstitutionFeatures = features
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
    let styleSourceMode: StyleSourceMode?
    let proofOptions: [PersistedProofOption]
    let proofSettingsByProof: [String: ProofSettings]
    let pageFormat: String
    let showBaselines: Bool
    let useCustomOutputLocation: Bool
    let customOutputLocation: String
}
