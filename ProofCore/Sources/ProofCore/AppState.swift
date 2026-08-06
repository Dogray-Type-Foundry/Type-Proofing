import SwiftUI
import UniformTypeIdentifiers

// MARK: - View Mode

public enum ViewMode: String, CaseIterable {
    case page
    case grid
    case compare
}

// MARK: - Proof Key Utilities

public func pythonProofKey(for name: String) -> String {
    name.lowercased()
        .replacingOccurrences(of: " ", with: "_")
        .replacingOccurrences(of: "/", with: "_")
        .replacingOccurrences(of: "-", with: "_")
}

public func pythonSettingsKey(for option: ProofOption, entry: ProofRegistryEntry) -> String {
    if option.name == entry.displayName {
        return option.baseType
    }
    return pythonProofKey(for: option.name)
}

// MARK: - Supporting Types

public struct OTFeature: Identifiable, Codable {
    public let id: String
    public var tag: String
    public var enabled: Bool
}

/// Substitution features are just OT features surfaced by the GSUB scan —
/// same shape, same persistence format.
public typealias SubstitutionFeature = OTFeature

public struct CategorySettings: Codable {
    public var uppercaseBase: Bool = true
    public var lowercaseBase: Bool = true
    public var numbersSymbols: Bool = true
    public var punctuation: Bool = true
    public var accented: Bool = false
}

public struct ProofSettings: Codable {
    public var fontSize: Double = 12
    public var tracking: Double = 0
    public var lineHeight: Double = 1.2
    public var columns: Int = 1
    public var paragraphs: Int = 5
    public var alignment: String = "left"
    public var customText: String = ""
    public var markupEnabled: Bool = false
    public var generateOnce: Bool = false
    public var categories: CategorySettings = CategorySettings()
    public var otFeatures: [OTFeature] = []
    public var substitutionFeatures: [SubstitutionFeature] = []
    public var defaultFontPath: String = ""
    public var defaultFontAxisDict: [String: Double]? = nil
    public var enabledStyleIndices: [String: Bool] = [:]
    public var autoSize: Bool = false
    public var showFallback: Bool = false
    public var columnGap: Double = 20
    public var direction: String = "auto"
    public var paragraphIndent: Double = 0
    public var paragraphSpace: Double = 0
    public var hyphenation: Bool = false
    public var hangingPunctuation: Bool = false
    public var generativeLanguage: String = "en"
    public var wordDiversity: Double = 0
    public var vocabularySize: Int = 0
    public var minWordLength: Int = 1
    public var maxWordLength: Int = 0
    public var biasChars: String = ""
    public var biasStrength: Double = 0
    public var wordsPerSentence: Int = 15
    public var sentencesPerParagraph: Int = 4
    public var pairingMode: String = "automatic"
    public var manualPairings: [ManualPairing] = []
    public var baselineFontPath: String = ""
    /// Security-scoped bookmark for the baseline font — the picker's grant
    /// doesn't survive relaunch on iPad without it.
    public var baselineFontBookmark: Data? = nil

    public init() {}

    public enum CodingKeys: String, CodingKey {
        case fontSize, tracking, lineHeight, columns, paragraphs, alignment
        case customText, markupEnabled, generateOnce, categories
        case otFeatures, substitutionFeatures
        case defaultFontPath, defaultFontAxisDict, enabledStyleIndices
        case autoSize, showFallback
        case columnGap, direction, paragraphIndent, paragraphSpace
        case hyphenation, hangingPunctuation, generativeLanguage
        case wordDiversity, vocabularySize, minWordLength, maxWordLength
        case biasChars, biasStrength
        case wordsPerSentence, sentencesPerParagraph
        case pairingMode, manualPairings
        case baselineFontPath, baselineFontBookmark
    }

    public init(from decoder: Decoder) throws {
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
        // Entries without "|" are from the old positional-index scheme, which
        // silently re-targeted other styles after any font reorder — drop them
        // (one-time reset to all-enabled) rather than misapply them.
        enabledStyleIndices = (try container.decodeIfPresent([String: Bool].self, forKey: .enabledStyleIndices) ?? [:])
            .filter { $0.key.contains("|") }
        autoSize = try container.decodeIfPresent(Bool.self, forKey: .autoSize) ?? false
        showFallback = try container.decodeIfPresent(Bool.self, forKey: .showFallback) ?? false
        columnGap = try container.decodeIfPresent(Double.self, forKey: .columnGap) ?? 20
        direction = try container.decodeIfPresent(String.self, forKey: .direction) ?? "auto"
        paragraphIndent = try container.decodeIfPresent(Double.self, forKey: .paragraphIndent) ?? 0
        paragraphSpace = try container.decodeIfPresent(Double.self, forKey: .paragraphSpace) ?? 0
        hyphenation = try container.decodeIfPresent(Bool.self, forKey: .hyphenation) ?? false
        hangingPunctuation = try container.decodeIfPresent(Bool.self, forKey: .hangingPunctuation) ?? false
        generativeLanguage = try container.decodeIfPresent(String.self, forKey: .generativeLanguage) ?? "en"
        wordDiversity = try container.decodeIfPresent(Double.self, forKey: .wordDiversity) ?? 0
        vocabularySize = try container.decodeIfPresent(Int.self, forKey: .vocabularySize) ?? 0
        minWordLength = try container.decodeIfPresent(Int.self, forKey: .minWordLength) ?? 1
        maxWordLength = try container.decodeIfPresent(Int.self, forKey: .maxWordLength) ?? 0
        biasChars = try container.decodeIfPresent(String.self, forKey: .biasChars) ?? ""
        biasStrength = try container.decodeIfPresent(Double.self, forKey: .biasStrength) ?? 0
        wordsPerSentence = try container.decodeIfPresent(Int.self, forKey: .wordsPerSentence) ?? 15
        sentencesPerParagraph = try container.decodeIfPresent(Int.self, forKey: .sentencesPerParagraph) ?? 4
        pairingMode = try container.decodeIfPresent(String.self, forKey: .pairingMode) ?? "automatic"
        manualPairings = try container.decodeIfPresent([ManualPairing].self, forKey: .manualPairings) ?? []
        baselineFontPath = try container.decodeIfPresent(String.self, forKey: .baselineFontPath) ?? ""
        baselineFontBookmark = try container.decodeIfPresent(Data.self, forKey: .baselineFontBookmark)
    }
}

public struct FontStyleEntry: Identifiable, Equatable {
    public var id: Int { index }
    public let index: Int
    public let fontPath: String
    public let familyName: String
    public let styleName: String
    public let isVariable: Bool
    public let coordinates: [String: Double]?
}

public enum StyleSourceMode: String, Codable {
    case namedInstances
    case customPositions
}

// MARK: - FontState

@MainActor
public final class FontState: ObservableObject {
    @Published public var fontPaths: [String] = []
    @Published public var loadedFonts: [FontInfo] = []
    @Published public var axisValuesByFont: [String: [String: [Double]]] = [:]
    @Published public var disabledFontPaths: Set<String> = []
    @Published public var fontSortCriteria: [FontSortCriterion] = []
    @Published public var fontStyles: [FontStyleEntry] = []
    @Published public var styleSourceMode: StyleSourceMode = .namedInstances

    /// Security-scoped bookmark per font path — lets a sandboxed app (iPad)
    /// re-open user-picked files across launches. Not published: pure
    /// persistence bookkeeping, always mutated alongside `fontPaths`.
    public var fontBookmarks: [String: Data] = [:]

    public var availableOTFeatures: [String] = []
    public var availableSubstitutionFeatures: [String] = []
    public var anyFontSupportsOpbd: Bool = false

    public var fontStylesByFamily: [(familyName: String, styles: [FontStyleEntry])] {
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

    public var anyFontSupportsArabic: Bool {
        loadedFonts.contains(where: \.supportsArabic)
    }

    public var enabledFontPaths: [String] {
        fontPaths.filter { !disabledFontPaths.contains($0) }
    }
}

// MARK: - ProofState

@MainActor
public final class ProofState: ObservableObject {
    @Published public var proofOptions: [ProofOption] = []
    @Published public var selectedProof: ProofOption.ID?
    @Published public var proofSettingsByProof: [String: ProofSettings] = [:]

    @Published public var registryByKey: [String: ProofRegistryEntry] = [:]

    public var onSettingsChanged: ((ProofOption.ID) -> Void)?

    public var isRegistryLoaded: Bool { !registryByKey.isEmpty }

    public var selectedProofOption: ProofOption? {
        guard let id = selectedProof else { return nil }
        return proofOptions.first { $0.id == id }
    }

    public var selectedRegistryEntry: ProofRegistryEntry? {
        guard let opt = selectedProofOption else { return nil }
        return registryByKey[opt.baseType]
    }

    public var selectedProofSettings: Binding<ProofSettings> {
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
public final class PreviewState: ObservableObject {
    @Published public var previewPDFPath: String?
    @Published public var previewSections: [ProofSection] = []
    @Published public var finalPDFPath: String?
    @Published public var finalSections: [ProofSection] = []
    @Published public var finalGeneratedConfigFingerprint: String?
    @Published public var currentConfigFingerprint: String?
}

// MARK: - PageState

@MainActor
public final class PageState: ObservableObject {
    @Published public var pageFormat: String = "A4Landscape"
    @Published public var pageFormats: [String] = []
    @Published public var showBaselines: Bool = false
    @Published public var showFooter: Bool = true
    @Published public var viewMode: ViewMode = .page
    @Published public var compareVertical: Bool = false
}

// MARK: - UIState

@MainActor
public final class UIState: ObservableObject {
    @Published public var showFontPicker = false
    @Published public var showAddProofSheet = false
    @Published public var showSettingsImporter = false
    /// Non-nil while the settings exporter is presented; holds the JSON
    /// snapshot taken when the user chose Export.
    @Published public var settingsExportRequest: Data? = nil
    @Published public var showSidebar = true
    @Published public var showThumbnailStrip = true
    @Published public var showInspector = true
    @Published public var fontsSectionExpanded = true
    @Published public var proofsSectionExpanded = true
    @Published public var outputSectionExpanded = true
    @Published public var sidebarWidth: CGFloat = 240
    @Published public var thumbnailStripWidth: CGFloat = 140
    @Published public var inspectorWidth: CGFloat = 300
    /// Pencil markup mode (iPad page view). Not persisted; always false on
    /// macOS. While on, the preview pipeline is paused and Generate is gated.
    @Published public var isMarkupActive = false
}

// MARK: - OutputState

@MainActor
public final class OutputState: ObservableObject {
    @Published public var outputDirectory: String = ""
    @Published public var useCustomOutputLocation: Bool = false
    @Published public var customOutputLocation: String = ""
}

// MARK: - AppState

@MainActor
public final class AppState: ObservableObject {
    public let fonts = FontState()
    public let proofs = ProofState()
    public let preview = PreviewState()
    public let page = PageState()
    public let ui = UIState()
    public let output = OutputState()
    public let annotations = AnnotationStore(fileURL: supportDirectory.appendingPathComponent("annotations.json"))

    @Published public private(set) var cachedRunSummary = ProofRunSummary()

    private static let supportDirectory: URL = {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("TypeProofing", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    private static let settingsURL = supportDirectory.appendingPathComponent("prefs.json")

    private var persistTimer: Timer?
    private var fontStylesRefreshTimer: Timer?
    weak public var previewCoordinator: PreviewCoordinator?
    weak public var pdfCoordinator: (any PreviewNavigationHandling)?

    public init() {
        proofs.onSettingsChanged = { [weak self] proofID in
            self?.previewCoordinator?.proofSettingsChanged(proofID: proofID)
            self?.schedulePersist(notifyPreview: false)
        }
        // Persistence is debounced by 3s — flush on quit so recent changes
        // aren't lost.
        #if os(macOS)
        NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.flushPendingPersist()
        }
        #endif
    }

    // MARK: - Cross-Cutting Computed

    /// Enabled proofs that can actually render with the loaded fonts. Arabic
    /// proofs are hidden from the sidebar when no font supports Arabic — they
    /// must not generate either, or the preview/final PDF fills with failed
    /// placeholder sections the user can't see or disable.
    public var renderableEnabledProofs: [ProofOption] {
        proofs.proofOptions.filter { option in
            guard option.enabled else { return false }
            if !fonts.anyFontSupportsArabic,
               proofs.registryByKey[option.baseType]?.isArabic == true {
                return false
            }
            return true
        }
    }

    public var isFinalPDFStale: Bool {
        guard preview.finalPDFPath != nil,
              let generated = preview.finalGeneratedConfigFingerprint else { return false }
        let current = preview.currentConfigFingerprint ?? buildProofConfig().fingerprint()
        return current != generated
    }

    // MARK: - Initialization from Engine

    public func loadFromEngine(_ engine: ProofEngine) {
        let registry = engine.getProofRegistry()
        for entry in registry {
            proofs.registryByKey[entry.key] = entry
        }

        page.pageFormats = engine.getPageFormats()

        if loadPersistedState() {
            annotations.load(validOptionIDs: Set(proofs.proofOptions.map(\.id)))
            if !page.pageFormats.isEmpty && !page.pageFormats.contains(page.pageFormat) {
                page.pageFormat = page.pageFormats.first!
            }
            if let first = proofs.proofOptions.first, proofs.selectedProof == nil {
                proofs.selectedProof = first.id
            }
            if !fonts.fontPaths.isEmpty {
                let existingPaths = fonts.fontPaths.filter {
                    FontAccessStore.shared.restoreAccess(
                        to: FontFileReference(path: $0, bookmark: fonts.fontBookmarks[$0])
                    )
                }
                if existingPaths.count != fonts.fontPaths.count {
                    fonts.fontPaths = existingPaths
                    fonts.fontBookmarks = fonts.fontBookmarks.filter { existingPaths.contains($0.key) }
                    fonts.axisValuesByFont = fonts.axisValuesByFont.filter { existingPaths.contains($0.key) }
                    fonts.disabledFontPaths = fonts.disabledFontPaths.filter { existingPaths.contains($0) }
                }
                if !fonts.fontPaths.isEmpty {
                    fonts.loadedFonts = engine.getFontMetadata(paths: fonts.fontPaths)
                    applySortCriteria()
                    refreshFontStyles(engine: engine)
                    applyAvailableFontFeatures(engine: engine)
                    if output.outputDirectory.isEmpty {
                        output.outputDirectory = defaultOutputDirectory(forFontAt: fonts.fontPaths[0])
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
        settings.paragraphs = entry.defaultParagraphs
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
        preview.previewPDFPath = nil
        preview.previewSections = []
        preview.finalPDFPath = nil
        preview.finalSections = []
        preview.finalGeneratedConfigFingerprint = nil
    }

    public func requestPreviewNavigation(to proofID: ProofOption.ID) {
        guard let option = proofs.proofOptions.first(where: { $0.id == proofID }),
              option.enabled,
              // Match by ID: name matching silently no-ops right after a
              // rename, until the debounced re-render catches up.
              let section = preview.previewSections.first(where: { $0.optionID == option.id })
                  ?? preview.previewSections.first(where: { $0.name == option.name })
        else { return }
        let request = PreviewNavigationRequest(
            proofID: proofID,
            proofName: option.name,
            pageIndex: section.firstPage
        )
        let coordinator = pdfCoordinator
        Task { @MainActor in
            coordinator?.handleNavigation(request)
        }
    }

    // MARK: - Font Management

    public func addFonts(urls: [URL], engine: ProofEngine) {
        let paths = urls.map { $0.path }
        let newPaths = paths.filter { !fonts.fontPaths.contains($0) }
        guard !newPaths.isEmpty else { return }

        for url in urls where newPaths.contains(url.path) {
            let ref = FontFileReference(url: url)
            fonts.fontBookmarks[ref.path] = ref.bookmark
            FontAccessStore.shared.restoreAccess(to: ref)
        }

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
            output.outputDirectory = defaultOutputDirectory(forFontAt: first)
        }

        applyAvailableFontFeatures(engine: engine)

        refreshFontStyles(engine: engine)
        schedulePersist()
    }

    /// Derives the available OT + substitution features from the first loaded font,
    /// the opbd-support flag across all loaded fonts, and reconciles each proof's
    /// OT/substitution feature lists against what the fonts actually support.
    /// Call after `fonts.fontPaths` and `fonts.loadedFonts` have been updated.
    public func applyAvailableFontFeatures(engine: ProofEngine) {
        // Prefer the first *enabled* font — proofs render with enabled fonts,
        // so a disabled first font must not dictate the feature list.
        guard let firstPath = fonts.enabledFontPaths.first ?? fonts.fontPaths.first else {
            fonts.availableOTFeatures = []
            fonts.availableSubstitutionFeatures = []
            fonts.anyFontSupportsOpbd = false
            return
        }

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

    public func refreshFontStyles(engine: ProofEngine) {
        fonts.fontStyles = engine.getFontStyles(
            paths: fonts.enabledFontPaths,
            mode: fonts.styleSourceMode,
            axisValuesByFont: fonts.axisValuesByFont
        )
    }

    /// Debounced variant for high-frequency callers like axis-slider drags, where
    /// `refreshFontStyles` (which re-reads every font from disk via FFI) would
    /// otherwise run on every tick and make dragging choppy.
    public func scheduleRefreshFontStyles(engine: ProofEngine) {
        fontStylesRefreshTimer?.invalidate()
        fontStylesRefreshTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: false) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.refreshFontStyles(engine: engine)
            }
        }
    }

    private func buildDefaultOTFeatures(for baseType: String?) -> [OTFeature] {
        fonts.availableOTFeatures.map { tag in
            var enabled = DEFAULT_ON_FEATURES.contains(tag)
            // Spacing measurements need kern and liga off by default.
            if baseType == "spacing_proof" && (tag == "kern" || tag == "liga") {
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

    public func removeFont(at offsets: IndexSet, engine: ProofEngine? = nil) {
        let pathsToRemove = offsets.map { fonts.loadedFonts[$0].id }
        fonts.loadedFonts.remove(atOffsets: offsets)
        fonts.fontPaths.removeAll { pathsToRemove.contains($0) }
        for path in pathsToRemove {
            fonts.axisValuesByFont.removeValue(forKey: path)
            fonts.disabledFontPaths.remove(path)
            fonts.fontBookmarks.removeValue(forKey: path)
            FontAccessStore.shared.releaseAccess(toPath: path)
        }
        // Settings referencing the removed font would silently keep using it
        // (or fail to load it on iPad once access is released).
        for name in proofs.proofSettingsByProof.keys {
            guard var settings = proofs.proofSettingsByProof[name] else { continue }
            var changed = false
            if pathsToRemove.contains(settings.defaultFontPath) {
                settings.defaultFontPath = ""
                settings.defaultFontAxisDict = nil
                changed = true
            }
            if pathsToRemove.contains(settings.baselineFontPath) {
                settings.baselineFontPath = ""
                changed = true
            }
            let pruned = settings.enabledStyleIndices.filter { entry in
                !pathsToRemove.contains(where: { entry.key.hasPrefix($0 + "|") })
            }
            if pruned.count != settings.enabledStyleIndices.count {
                settings.enabledStyleIndices = pruned
                changed = true
            }
            if changed {
                proofs.proofSettingsByProof[name] = settings
            }
        }
        if let engine {
            refreshFontStyles(engine: engine)
            applyAvailableFontFeatures(engine: engine)
        }
        schedulePersist()
    }

    public func moveFonts(from source: IndexSet, to destination: Int) {
        fonts.loadedFonts.move(fromOffsets: source, toOffset: destination)
        fonts.fontPaths = fonts.loadedFonts.map(\.id)
        schedulePersist()
    }

    public func applySortCriteria() {
        guard !fonts.fontSortCriteria.isEmpty else { return }
        fonts.loadedFonts = fonts.loadedFonts.sorted(by: fonts.fontSortCriteria)
        fonts.fontPaths = fonts.loadedFonts.map(\.id)
        schedulePersist()
    }

    public func resetFonts() {
        fonts.fontPaths.removeAll()
        fonts.fontBookmarks.removeAll()
        FontAccessStore.shared.releaseAll()
        fonts.loadedFonts.removeAll()
        fonts.axisValuesByFont.removeAll()
        fonts.disabledFontPaths.removeAll()
        fonts.fontStyles.removeAll()
        fonts.availableOTFeatures.removeAll()
        fonts.availableSubstitutionFeatures.removeAll()
        fonts.anyFontSupportsOpbd = false
        fonts.fontSortCriteria.removeAll()
        fonts.styleSourceMode = .namedInstances
        output.outputDirectory = ""
        output.useCustomOutputLocation = false
        output.customOutputLocation = ""
        clearGeneratedOutput()
        schedulePersist()
    }

    // MARK: - Proof Reordering

    public func moveProofOptions(from source: IndexSet, to destination: Int) {
        proofs.proofOptions.move(fromOffsets: source, toOffset: destination)
        for (i, _) in proofs.proofOptions.enumerated() {
            proofs.proofOptions[i].order = i
        }
        refreshCurrentConfigFingerprint()
        previewCoordinator?.proofOrderChanged()
        schedulePersist(notifyPreview: false)
    }

    // MARK: - Add/Remove Proof Instance

    public func generateUniqueName(for baseType: String) -> String {
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

    public func addProofInstance(baseType: String) {
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

    public func renameProofOption(id: ProofOption.ID, to newName: String) {
        guard let index = proofs.proofOptions.firstIndex(where: { $0.id == id }) else { return }
        let oldName = proofs.proofOptions[index].name
        let trimmed = newName.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty, trimmed != oldName else { return }

        let otherNames = Set(proofs.proofOptions.filter { $0.id != id }.map(\.name))
        var candidate = trimmed
        var counter = 2
        while otherNames.contains(candidate) {
            candidate = "\(trimmed) \(counter)"
            counter += 1
        }

        proofs.proofOptions[index].name = candidate
        if let settings = proofs.proofSettingsByProof.removeValue(forKey: oldName) {
            proofs.proofSettingsByProof[candidate] = settings
        }
        schedulePersist()
    }

    public func removeProofOption(at offsets: IndexSet) {
        let names = offsets.map { proofs.proofOptions[$0].name }
        for offset in offsets {
            annotations.clearSection(proofs.proofOptions[offset].id)
        }
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

    public func buildProofConfig() -> ProofConfig {
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
            proofOptions: renderableEnabledProofs,
            proofSettings: pySettings,
            pageFormat: page.pageFormat,
            outputDir: outDir,
            showBaselines: page.showBaselines,
            showFooter: page.showFooter
        )
    }

    public func refreshCurrentConfigFingerprint() {
        preview.currentConfigFingerprint = buildProofConfig().fingerprint()
        cachedRunSummary = makeRunSummary()
    }

    public func previewFingerprint(for option: ProofOption) -> String {
        previewFingerprint(for: option, flatSettings: buildFlatProofSettings())
    }

    public func previewFingerprint(for option: ProofOption, flatSettings: [String: Any]) -> String {
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
            "show_footer": page.showFooter,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]) else {
            return UUID().uuidString
        }
        return data.base64EncodedString()
    }

    public func makeRunSummary() -> ProofRunSummary {
        let enabledProofs = renderableEnabledProofs
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
            showFooter: page.showFooter,
            warnings: warnings
        )
    }

    public func buildFlatProofSettings() -> [String: Any] {
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

            if entry.hasParagraphs || entry.hasTextConfig {
                flat["\(settingsKey)_para"] = settings.paragraphs
            }

            if entry.hasTextConfig {
                flat["\(settingsKey)_generativeLanguage"] = settings.generativeLanguage
                flat["\(settingsKey)_wordDiversity"] = settings.wordDiversity
                flat["\(settingsKey)_vocabularySize"] = settings.vocabularySize
                flat["\(settingsKey)_minWordLength"] = settings.minWordLength
                flat["\(settingsKey)_maxWordLength"] = settings.maxWordLength
                flat["\(settingsKey)_biasChars"] = settings.biasChars
                flat["\(settingsKey)_biasStrength"] = settings.biasStrength
                flat["\(settingsKey)_wordsPerSentence"] = settings.wordsPerSentence
                flat["\(settingsKey)_sentencesPerParagraph"] = settings.sentencesPerParagraph
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

            if option.baseType == "paired_styles_paragraph_small" {
                flat["\(settingsKey)_pairingMode"] = settings.pairingMode
                let encoder = JSONEncoder()
                encoder.outputFormatting = [.sortedKeys]
                if let data = try? encoder.encode(settings.manualPairings),
                   let json = String(data: data, encoding: .utf8) {
                    flat["\(settingsKey)_manualPairings"] = json
                }
            }

            if option.baseType == "version_comparison" {
                flat["\(settingsKey)_baselineFontPath"] = settings.baselineFontPath
                flat["\(settingsKey)_customText"] = settings.customText
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
        // The fingerprint (full-config JSON + SHA256) is intentionally NOT
        // refreshed here — schedulePersist runs on every keystroke/slider tick.
        // It refreshes when the debounced persist fires below, when the preview
        // invalidates, and at the explicit structural-change call sites.
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

    public func schedulePersistPublic(notifyPreview: Bool = true) {
        schedulePersist(notifyPreview: notifyPreview)
    }

    public func flushPendingPersist() {
        annotations.flushPendingSave()
        guard persistTimer?.isValid == true else { return }
        persistTimer?.invalidate()
        persistTimer = nil
        persistState()
    }

    private func currentPersistedState() -> PersistedState {
        PersistedState(
            fontPaths: fonts.fontPaths,
            fontBookmarks: fonts.fontBookmarks,
            axisValuesByFont: fonts.axisValuesByFont,
            disabledFontPaths: Array(fonts.disabledFontPaths),
            fontSortCriteria: fonts.fontSortCriteria,
            styleSourceMode: fonts.styleSourceMode,
            proofOptions: proofs.proofOptions.map {
                PersistedProofOption(id: $0.id, name: $0.name, baseType: $0.baseType, enabled: $0.enabled, order: $0.order)
            },
            proofSettingsByProof: proofs.proofSettingsByProof,
            pageFormat: page.pageFormat,
            showBaselines: page.showBaselines,
            showFooter: page.showFooter,
            useCustomOutputLocation: output.useCustomOutputLocation,
            customOutputLocation: output.customOutputLocation
        )
    }

    public func persistState() {
        refreshCurrentConfigFingerprint()
        let data = currentPersistedState()

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
            apply(data)
            return true
        } catch {
            print("Settings load error: \(error)")
            return false
        }
    }

    private func apply(_ data: PersistedState) {
        fonts.fontPaths = data.fontPaths
        fonts.fontBookmarks = data.fontBookmarks ?? [:]
        fonts.axisValuesByFont = data.axisValuesByFont
        fonts.disabledFontPaths = Set(data.disabledFontPaths ?? [])
        fonts.fontSortCriteria = data.fontSortCriteria ?? []
        fonts.styleSourceMode = data.styleSourceMode ?? .namedInstances
        page.pageFormat = data.pageFormat
        page.showBaselines = data.showBaselines
        page.showFooter = data.showFooter ?? true
        output.useCustomOutputLocation = data.useCustomOutputLocation
        output.customOutputLocation = data.customOutputLocation

        proofs.proofOptions = data.proofOptions.map { po in
            // Legacy prefs files carry no IDs; fresh ones orphan any stored
            // annotations, which load()/prune() then drop.
            ProofOption(id: po.id ?? UUID(), name: po.name, baseType: po.baseType, enabled: po.enabled, order: po.order)
        }
        proofs.proofSettingsByProof = data.proofSettingsByProof

        if let first = proofs.proofOptions.first {
            proofs.selectedProof = first.id
        }

        if output.outputDirectory.isEmpty, let first = fonts.fontPaths.first {
            output.outputDirectory = defaultOutputDirectory(forFontAt: first)
        }

        // Version-comparison baseline fonts live outside the font list; their
        // sandbox access must be re-established from the stored bookmark.
        for settings in proofs.proofSettingsByProof.values where !settings.baselineFontPath.isEmpty {
            FontAccessStore.shared.restoreAccess(to: FontFileReference(
                path: settings.baselineFontPath, bookmark: settings.baselineFontBookmark))
        }
    }

    /// Imports a settings file in the app's own persisted format (the same
    /// JSON `exportState`/`persistState` write), then re-runs the engine-
    /// dependent side effects that startup normally performs — font metadata,
    /// sorting, style refresh, available OT features.
    @discardableResult
    public func importState(from url: URL, engine: ProofEngine) -> Bool {
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }

        guard let json = try? Data(contentsOf: url),
              let data = try? JSONDecoder().decode(PersistedState.self, from: json) else {
            print("Settings import failed: not a Type Proofing settings file")
            return false
        }
        apply(data)

        fonts.fontPaths = fonts.fontPaths.filter {
            FontAccessStore.shared.restoreAccess(
                to: FontFileReference(path: $0, bookmark: fonts.fontBookmarks[$0])
            )
        }
        fonts.fontBookmarks = fonts.fontBookmarks.filter { fonts.fontPaths.contains($0.key) }
        fonts.axisValuesByFont = fonts.axisValuesByFont.filter { fonts.fontPaths.contains($0.key) }
        fonts.disabledFontPaths = fonts.disabledFontPaths.filter { fonts.fontPaths.contains($0) }
        if fonts.fontPaths.isEmpty {
            fonts.loadedFonts = []
            output.outputDirectory = ""
        } else {
            fonts.loadedFonts = engine.getFontMetadata(paths: fonts.fontPaths)
            applySortCriteria()
            refreshFontStyles(engine: engine)
            applyAvailableFontFeatures(engine: engine)
            // Recompute unconditionally: a mid-session import swaps the font
            // set, and keeping the previous session's directory would write
            // PDFs next to fonts that are no longer loaded.
            if !output.useCustomOutputLocation {
                output.outputDirectory = defaultOutputDirectory(forFontAt: fonts.fontPaths[0])
            }
        }

        annotations.prune(validOptionIDs: Set(proofs.proofOptions.map(\.id)))
        clearGeneratedOutput()
        persistState()
        previewCoordinator?.stateChanged(debounced: false)
        return true
    }

    /// The current settings encoded in the persisted-state format.
    public func exportedSettingsJSON() -> Data? {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try? encoder.encode(currentPersistedState())
    }

    /// Writes the current settings to `url` in the persisted-state format.
    public func exportState(to url: URL) {
        do {
            guard let json = exportedSettingsJSON() else { return }
            try json.write(to: url, options: .atomic)
        } catch {
            print("Settings export error: \(error)")
        }
    }

    public func resetAllSettings() {
        guard proofs.isRegistryLoaded else { return }

        // Reset during markup would leave the pipeline paused with dead
        // option IDs on screen — any stroke drawn after that would create a
        // phantom, unclearable annotation. End the markup session first.
        ui.isMarkupActive = false
        annotations.clearAll()
        resetProofDefaults()
        page.showBaselines = false
        page.showFooter = true
        page.pageFormat = page.pageFormats.contains("A4Landscape") ? "A4Landscape" : (page.pageFormats.first ?? "A4Landscape")
        output.useCustomOutputLocation = false
        output.customOutputLocation = ""
        if let first = fonts.fontPaths.first {
            output.outputDirectory = defaultOutputDirectory(forFontAt: first)
        } else {
            output.outputDirectory = ""
        }
        clearGeneratedOutput()
        persistState()
    }
}

// MARK: - Persistence Types

public struct PersistedProofOption: Codable {
    public let id: UUID?    // optional: absent in pre-annotation prefs files
    public let name: String
    public let baseType: String
    public let enabled: Bool
    public let order: Int
}

public struct PersistedState: Codable {
    public let fontPaths: [String]
    public let fontBookmarks: [String: Data]?
    public let axisValuesByFont: [String: [String: [Double]]]
    public let disabledFontPaths: [String]?
    public let fontSortCriteria: [FontSortCriterion]?
    public let styleSourceMode: StyleSourceMode?
    public let proofOptions: [PersistedProofOption]
    public let proofSettingsByProof: [String: ProofSettings]
    public let pageFormat: String
    public let showBaselines: Bool
    public let showFooter: Bool?
    public let useCustomOutputLocation: Bool
    public let customOutputLocation: String
}
