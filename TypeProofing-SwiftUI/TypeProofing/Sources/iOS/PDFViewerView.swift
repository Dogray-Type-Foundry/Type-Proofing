import ProofCore
import SwiftUI
import PDFKit

// MARK: - PDFViewCoordinator (iOS)

/// iOS counterpart of the macOS coordinator: owns the PDFView, tracks zoom,
/// and reloads documents while preserving the reading position. Same name as
/// the macOS type — each is compiled only for its own destination.
final class PDFViewCoordinator: ObservableObject, PreviewNavigationHandling {
    weak var pdfView: PDFView? {
        didSet { observeScaleChanges() }
    }

    @Published var zoomPercent: Int = 100
    /// The currently displayed document — published so the thumbnail strip
    /// rebuilds when a (re)load lands.
    @Published private(set) var loadedDocument: PDFDocument?
    @Published private(set) var currentPageIndex: Int = 0

    var sections: [ProofSection] = []
    var lastLoadedPDFPath: String?
    var requestedPDFPath: String?
    var lastHandledNavigationRequestID: UUID?
    private var observers: [NSObjectProtocol] = []

    deinit {
        for obs in observers { NotificationCenter.default.removeObserver(obs) }
    }

    private func observeScaleChanges() {
        for obs in observers { NotificationCenter.default.removeObserver(obs) }
        observers.removeAll()
        guard let pdfView else { return }
        syncZoomPercent()
        observers.append(NotificationCenter.default.addObserver(
            forName: .PDFViewScaleChanged, object: pdfView, queue: .main
        ) { [weak self] _ in self?.syncZoomPercent() })
        observers.append(NotificationCenter.default.addObserver(
            forName: .PDFViewPageChanged, object: pdfView, queue: .main
        ) { [weak self] _ in self?.syncCurrentPage() })
    }

    private func syncCurrentPage() {
        guard let pdfView, let document = pdfView.document,
              let page = pdfView.currentPage else { return }
        let index = document.index(for: page)
        if index != NSNotFound, index != currentPageIndex {
            currentPageIndex = index
        }
    }

    func documentCleared() {
        loadedDocument = nil
        currentPageIndex = 0
    }

    func syncZoomPercent() {
        guard let pdfView else { return }
        let pct = Int((pdfView.scaleFactor * 100).rounded())
        if pct != zoomPercent { zoomPercent = pct }
    }

    /// Where the reader is: current page plus zoom, so a preview regeneration
    /// doesn't jump back to page 1.
    private struct Anchor {
        let sectionName: String?
        let offset: Int
        let absolutePage: Int
        let scaleFactor: CGFloat
        let autoScales: Bool
    }

    private var pendingAnchor: Anchor?
    /// Page to show once the next document load lands — set by the grid view,
    /// whose taps happen while no PDFView exists.
    var pendingPageIndex: Int?

    private func currentAnchor() -> Anchor? {
        guard let pdfView,
              let document = pdfView.document,
              let page = pdfView.currentPage else { return nil }
        let pageIndex = document.index(for: page)
        guard pageIndex != NSNotFound else { return nil }

        var currentSection: ProofSection?
        for section in sections.sorted(by: { $0.firstPage < $1.firstPage }) {
            if section.firstPage <= pageIndex {
                currentSection = section
            } else {
                break
            }
        }
        return Anchor(
            sectionName: currentSection?.name,
            offset: currentSection.map { max(0, pageIndex - $0.firstPage) } ?? 0,
            absolutePage: pageIndex,
            scaleFactor: pdfView.scaleFactor,
            autoScales: pdfView.autoScales
        )
    }

    private func restore(in document: PDFDocument, sections: [ProofSection]) {
        guard let pdfView, let anchor = pendingAnchor, document.pageCount > 0 else { return }
        pendingAnchor = nil
        let targetIndex: Int
        if let sectionName = anchor.sectionName,
           let section = sections.first(where: { $0.name == sectionName }) {
            targetIndex = min(section.firstPage + anchor.offset, document.pageCount - 1)
        } else {
            targetIndex = min(anchor.absolutePage, document.pageCount - 1)
        }
        guard let page = document.page(at: max(0, targetIndex)) else { return }
        pdfView.autoScales = anchor.autoScales
        if !anchor.autoScales {
            pdfView.scaleFactor = anchor.scaleFactor
        }
        pdfView.go(to: page)
    }

    func loadDocument(path: String, sections: [ProofSection]) {
        guard requestedPDFPath != path else { return }
        requestedPDFPath = path
        let url = URL(fileURLWithPath: path)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let document = PDFDocument(url: url)
            DispatchQueue.main.async {
                guard let self, self.requestedPDFPath == path else { return }
                guard let document, let pdfView = self.pdfView else { return }
                if self.pendingAnchor == nil {
                    self.pendingAnchor = self.currentAnchor()
                }
                pdfView.document = document
                self.lastLoadedPDFPath = path
                if self.pendingPageIndex == nil {
                    self.restore(in: document, sections: sections)
                }
                self.sections = sections
                self.loadedDocument = document
                if let pending = self.pendingPageIndex {
                    self.pendingPageIndex = nil
                    let index = min(max(pending, 0), document.pageCount - 1)
                    if let page = document.page(at: index) {
                        pdfView.go(to: PDFDestination(
                            page: page,
                            at: CGPoint(x: 0, y: page.bounds(for: pdfView.displayBox).height)
                        ))
                    }
                }
                self.syncCurrentPage()
            }
        }
    }

    func handleNavigation(_ request: PreviewNavigationRequest) {
        guard let pdfView, let document = pdfView.document,
              request.id != lastHandledNavigationRequestID,
              document.pageCount > 0 else { return }
        let pageIndex = min(max(request.pageIndex, 0), document.pageCount - 1)
        guard let page = document.page(at: pageIndex) else { return }
        lastHandledNavigationRequestID = request.id
        pdfView.go(to: PDFDestination(page: page, at: CGPoint(x: 0, y: page.bounds(for: pdfView.displayBox).height)))
    }
}

// MARK: - PDFKitView

/// Wraps a bare PDFView; document loading is driven through the coordinator.
struct PDFKitView: UIViewRepresentable {
    let pdfPath: String?
    let sections: [ProofSection]
    let pdfCoordinator: PDFViewCoordinator

    func makeUIView(context: Context) -> PDFView {
        let pdfView = PDFView()
        pdfView.autoScales = true
        pdfView.displaysPageBreaks = true
        pdfView.displayMode = .singlePageContinuous
        pdfView.displayDirection = .vertical
        pdfView.backgroundColor = .secondarySystemBackground
        pdfCoordinator.pdfView = pdfView
        pdfCoordinator.lastLoadedPDFPath = nil
        pdfCoordinator.requestedPDFPath = nil
        return pdfView
    }

    func updateUIView(_ pdfView: PDFView, context: Context) {
        if let path = pdfPath {
            if pdfCoordinator.lastLoadedPDFPath != path {
                pdfCoordinator.loadDocument(path: path, sections: sections)
            } else {
                pdfCoordinator.sections = sections
            }
        } else {
            pdfView.document = nil
            pdfCoordinator.lastLoadedPDFPath = nil
            pdfCoordinator.requestedPDFPath = nil
            pdfCoordinator.sections = []
            pdfCoordinator.lastHandledNavigationRequestID = nil
            pdfCoordinator.documentCleared()
        }
    }
}

// MARK: - ThumbnailStrip

/// Custom thumbnail minimap: lazy per-page thumbnails (rendered off the main
/// thread), section headers, tap-to-jump, current-page highlight.
/// (PDFKit's PDFThumbnailView is designed as a horizontal filmstrip on iOS
/// and misbehaves badly in a vertical column.)
struct ThumbnailStrip: View {
    let sections: [ProofSection]
    @ObservedObject var pdfCoordinator: PDFViewCoordinator

    private var sectionNamesByFirstPage: [Int: String] {
        Dictionary(sections.map { ($0.firstPage, $0.name) }) { first, _ in first }
    }

    var body: some View {
        if let document = pdfCoordinator.loadedDocument {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(0..<document.pageCount, id: \.self) { index in
                            if let page = document.page(at: index) {
                                if let sectionName = sectionNamesByFirstPage[index] {
                                    Text(sectionName.uppercased())
                                        .font(.system(size: 9, weight: .semibold))
                                        .foregroundStyle(.secondary)
                                        .lineLimit(1)
                                        .padding(.top, 6)
                                }
                                ThumbnailCell(
                                    page: page,
                                    pageIndex: index,
                                    isCurrent: index == pdfCoordinator.currentPageIndex
                                ) {
                                    pdfCoordinator.pdfView?.go(to: page)
                                }
                                .id(index)
                            }
                        }
                    }
                    .padding(8)
                }
                .onChange(of: pdfCoordinator.currentPageIndex) { _, index in
                    withAnimation { proxy.scrollTo(index, anchor: .center) }
                }
            }
            // New document → drop all cached thumbnail images.
            .id(ObjectIdentifier(document))
            .background(Color(.secondarySystemBackground).opacity(0.5))
        } else {
            Color.clear
        }
    }
}

private struct ThumbnailCell: View {
    let page: PDFPage
    let pageIndex: Int
    let isCurrent: Bool
    let action: () -> Void

    @State private var image: UIImage?

    var body: some View {
        Button(action: action) {
            VStack(spacing: 2) {
                Group {
                    if let image {
                        Image(uiImage: image)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                    } else {
                        Color(.tertiarySystemFill)
                            .aspectRatio(pageAspectRatio, contentMode: .fit)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 3))
                .overlay(
                    RoundedRectangle(cornerRadius: 3)
                        .stroke(
                            isCurrent ? Color.accentColor : Color.primary.opacity(0.12),
                            lineWidth: isCurrent ? 2 : 0.5
                        )
                )

                Text("\(pageIndex + 1)")
                    .font(.system(size: 9).monospacedDigit())
                    .foregroundStyle(isCurrent ? Color.accentColor : .secondary)
            }
        }
        .buttonStyle(.plain)
        .task {
            guard image == nil else { return }
            let page = page
            image = await Task.detached(priority: .utility) {
                page.thumbnail(of: CGSize(width: 180, height: 240), for: .mediaBox)
            }.value
        }
    }

    private var pageAspectRatio: CGFloat {
        let bounds = page.bounds(for: .mediaBox)
        return bounds.height > 0 ? bounds.width / bounds.height : 0.7
    }
}

// MARK: - PDFFloatingToolbar

/// Floating controls over the PDF, mirroring the macOS toolbar: liquid-glass
/// pills for panel toggles, view modes, and zoom.
struct PDFFloatingToolbar: View {
    @EnvironmentObject var ui: UIState
    @EnvironmentObject var page: PageState
    @Binding var columnVisibility: NavigationSplitViewVisibility
    @Binding var showThumbnails: Bool
    @ObservedObject var pdfCoordinator: PDFViewCoordinator

    private var sidebarVisible: Bool { columnVisibility != .detailOnly }

    var body: some View {
        HStack(spacing: 12) {
            HStack(spacing: 2) {
                toolbarButton("sidebar.leading", active: sidebarVisible, help: "Toggle sidebar") {
                    withAnimation {
                        columnVisibility = sidebarVisible ? .detailOnly : .all
                    }
                }
                toolbarButton("rectangle.split.3x1", active: showThumbnails, help: "Toggle thumbnails") {
                    showThumbnails.toggle()
                }
                toolbarButton("sidebar.trailing", active: ui.showInspector, help: "Toggle settings") {
                    ui.showInspector.toggle()
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .liquidGlassCapsule()

            HStack(spacing: 2) {
                toolbarButton("doc.richtext", active: page.viewMode == .page, help: "Page view") {
                    page.viewMode = .page
                }
                toolbarButton("square.grid.2x2", active: page.viewMode == .grid, help: "Grid view") {
                    page.viewMode = .grid
                }
                toolbarButton("arrow.left.arrow.right", active: page.viewMode == .compare, help: "Compare view") {
                    page.viewMode = .compare
                }

                if page.viewMode == .compare {
                    Divider()
                        .frame(height: 16)
                        .padding(.horizontal, 4)
                    toolbarButton(
                        page.compareVertical ? "rectangle.split.1x2" : "rectangle.split.2x1",
                        active: false,
                        help: page.compareVertical ? "Side by side" : "Stacked"
                    ) {
                        page.compareVertical.toggle()
                    }
                }

                Divider()
                    .frame(height: 16)
                    .padding(.horizontal, 4)

                toolbarButton("line.3.horizontal", active: page.showBaselines, help: "Baseline grid") {
                    page.showBaselines.toggle()
                }
                toolbarButton("text.append", active: page.showFooter, help: page.showFooter ? "Hide footer" : "Show footer") {
                    page.showFooter.toggle()
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .liquidGlassCapsule()

            HStack(spacing: 2) {
                Button { zoom(by: -0.1) } label: {
                    Image(systemName: "minus")
                        .frame(width: 32, height: 30)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)

                Text("\(pdfCoordinator.zoomPercent)%")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .frame(minWidth: 44)

                Button { zoom(by: 0.1) } label: {
                    Image(systemName: "plus")
                        .frame(width: 32, height: 30)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)

                Button { pdfCoordinator.pdfView?.autoScales = true } label: {
                    Image(systemName: "arrow.up.left.and.arrow.down.right")
                        .frame(width: 32, height: 30)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .liquidGlassCapsule()
        }
        .padding(.top, 10)
    }

    private func toolbarButton(_ systemImage: String, active: Bool, help: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .frame(width: 32, height: 30)
                .foregroundStyle(active ? Color.accentColor : .secondary)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(help)
    }

    private func zoom(by delta: CGFloat) {
        guard let pdfView = pdfCoordinator.pdfView else { return }
        pdfView.autoScales = false
        pdfView.scaleFactor = max(0.1, min(pdfView.scaleFactor + delta, 5.0))
    }
}
