import Foundation
import CoreGraphics

// MARK: - Annotation Models

/// A typed note placed on a proof page. `rect` is in PDF page coordinates
/// (points, bottom-left origin).
public struct TextBox: Codable, Equatable, Identifiable {
    public let id: UUID
    public var rect: CGRect
    public var text: String
    public var fontSize: CGFloat
    public var colorHex: String
    /// PostScript name; nil = system font. Optional so pre-existing sidecar
    /// files keep decoding.
    public var fontName: String?

    public init(id: UUID = UUID(), rect: CGRect, text: String, fontSize: CGFloat,
                colorHex: String, fontName: String? = nil) {
        self.id = id
        self.rect = rect
        self.text = text
        self.fontSize = fontSize
        self.colorHex = colorHex
        self.fontName = fontName
    }
}

/// Markup for a single page. `drawingData` is an opaque
/// `PKDrawing.dataRepresentation()` blob — ProofCore never imports PencilKit.
public struct PageAnnotations: Codable, Equatable {
    public var drawingData: Data?
    public var textBoxes: [TextBox]
    /// Page size at annotation time; sanity check when re-attaching overlays.
    public var pageSize: CGSize
    /// Drawing coordinates per page point (nil = 1, legacy page-point space).
    /// Ink is drawn in a scaled-up space so PencilKit's minimum tool widths
    /// land thinner on the page.
    public var drawingSpaceScale: CGFloat?

    public init(drawingData: Data? = nil, textBoxes: [TextBox] = [], pageSize: CGSize,
                drawingSpaceScale: CGFloat? = nil) {
        self.drawingData = drawingData
        self.textBoxes = textBoxes
        self.pageSize = pageSize
        self.drawingSpaceScale = drawingSpaceScale
    }

    public var isEmpty: Bool { drawingData == nil && textBoxes.isEmpty }
}

/// Annotated pages of one proof section, keyed by page offset within the
/// section (0 = the section's first page). Recomposition only shifts where a
/// section *starts*, so section-relative keys survive it.
public struct SectionAnnotations: Codable, Equatable {
    public var pages: [Int: PageAnnotations]

    public init(pages: [Int: PageAnnotations] = [:]) {
        self.pages = pages
    }
}

// MARK: - AnnotationStore

/// Holds all Pencil/text markup, keyed by `ProofOption.id`. Persisted as a
/// sidecar `annotations.json` next to `prefs.json` — drawing blobs can reach
/// hundreds of KB and must not travel with exported settings.
@MainActor
public final class AnnotationStore: ObservableObject {
    @Published public private(set) var sections: [UUID: SectionAnnotations] = [:]

    private let fileURL: URL
    private var saveTimer: Timer?

    public init(fileURL: URL) {
        self.fileURL = fileURL
    }

    // MARK: Queries

    /// Gates global controls (font, axes, page format) while any markup exists.
    public var hasAnyAnnotations: Bool { !sections.isEmpty }

    /// A section with any markup is frozen: its settings can't be edited and
    /// its fragment never regenerates.
    public func isSectionFrozen(_ optionID: UUID) -> Bool {
        sections[optionID] != nil
    }

    public func page(_ optionID: UUID, offset: Int) -> PageAnnotations? {
        sections[optionID]?.pages[offset]
    }

    /// Absolute page indices carrying annotations, resolved against the
    /// composed section list. Drives the badge dots.
    public func annotatedPages(in proofSections: [ProofSection]) -> Set<Int> {
        var result: Set<Int> = []
        for section in proofSections {
            guard let id = section.optionID, let annotated = sections[id] else { continue }
            for offset in annotated.pages.keys {
                result.insert(section.firstPage + offset)
            }
        }
        return result
    }

    /// Resolves an absolute page index to its (section, offset) annotation key:
    /// the last section whose `firstPage <= page`.
    nonisolated public static func resolve(page: Int, in proofSections: [ProofSection]) -> (optionID: UUID, offset: Int)? {
        guard let section = proofSections.last(where: { $0.firstPage <= page }),
              let id = section.optionID else { return nil }
        return (id, page - section.firstPage)
    }

    // MARK: Mutation

    /// Pass `nil` (or let the page become empty) to clear; empty pages and
    /// sections are removed so freeze state relaxes automatically.
    public func setDrawing(_ data: Data?, optionID: UUID, pageOffset: Int, pageSize: CGSize,
                           spaceScale: CGFloat = 1) {
        var page = sections[optionID]?.pages[pageOffset] ?? PageAnnotations(pageSize: pageSize)
        page.drawingData = data
        page.pageSize = pageSize
        page.drawingSpaceScale = data == nil ? nil : spaceScale
        setPage(page, optionID: optionID, pageOffset: pageOffset)
    }

    public func setTextBoxes(_ boxes: [TextBox], optionID: UUID, pageOffset: Int, pageSize: CGSize) {
        if boxes.isEmpty && sections[optionID]?.pages[pageOffset] == nil { return }
        var page = sections[optionID]?.pages[pageOffset] ?? PageAnnotations(pageSize: pageSize)
        page.textBoxes = boxes
        page.pageSize = pageSize
        setPage(page, optionID: optionID, pageOffset: pageOffset)
    }

    public func clearSection(_ optionID: UUID) {
        guard sections.removeValue(forKey: optionID) != nil else { return }
        scheduleSave()
    }

    public func clearAll() {
        guard !sections.isEmpty else { return }
        sections = [:]
        scheduleSave()
    }

    /// Drops annotations whose section no longer exists (deleted options,
    /// settings import/reset) so `hasAnyAnnotations` can't get stuck true.
    public func prune(validOptionIDs: Set<UUID>) {
        let stale = sections.keys.filter { !validOptionIDs.contains($0) }
        guard !stale.isEmpty else { return }
        for key in stale {
            sections.removeValue(forKey: key)
        }
        scheduleSave()
    }

    private func setPage(_ page: PageAnnotations, optionID: UUID, pageOffset: Int) {
        var section = sections[optionID] ?? SectionAnnotations()
        if page.isEmpty {
            section.pages.removeValue(forKey: pageOffset)
        } else {
            section.pages[pageOffset] = page
        }
        if section.pages.isEmpty {
            sections.removeValue(forKey: optionID)
        } else {
            sections[optionID] = section
        }
        scheduleSave()
    }

    // MARK: Persistence

    public func load(validOptionIDs: Set<UUID>) {
        // Keyed by uuidString: UUID dictionary keys encode as a flat
        // [key, value, …] array in Codable, not a JSON object.
        guard let data = try? Data(contentsOf: fileURL),
              let decoded = try? JSONDecoder().decode([String: SectionAnnotations].self, from: data) else { return }
        sections = decoded.reduce(into: [:]) { result, entry in
            guard let id = UUID(uuidString: entry.key), validOptionIDs.contains(id) else { return }
            result[id] = entry.value
        }
        #if DEBUG
        if decoded.count != sections.count {
            print("Annotations: dropped \(decoded.count - sections.count) section(s) with no matching proof option")
        }
        #endif
    }

    private func scheduleSave() {
        saveTimer?.invalidate()
        saveTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: false) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.save()
            }
        }
    }

    public func flushPendingSave() {
        guard saveTimer?.isValid == true else { return }
        saveTimer?.invalidate()
        save()
    }

    private func save() {
        saveTimer = nil
        do {
            if sections.isEmpty {
                try? FileManager.default.removeItem(at: fileURL)
            } else {
                let keyed = Dictionary(uniqueKeysWithValues: sections.map { ($0.key.uuidString, $0.value) })
                let data = try JSONEncoder().encode(keyed)
                try data.write(to: fileURL, options: .atomic)
            }
        } catch {
            print("Annotations save error: \(error)")
        }
    }
}
