import SwiftUI
import PDFKit

// MARK: - PDFViewCoordinator

/// Shared coordinator that bridges the PDFView and ThumbnailSidebarView,
/// now that they live in separate NSViewRepresentable wrappers.
class PDFViewCoordinator: ObservableObject {
    weak var pdfView: PDFView? {
        didSet { observeScaleChanges() }
    }
    weak var thumbnailSidebar: ThumbnailSidebarView?

    @Published var zoomPercent: Int = 100

    var sections: [ProofSection] = []
    var lastLoadedPDFPath: String?
    var lastHandledNavigationRequestID: UUID?
    private var scaleObservers: [NSObjectProtocol] = []

    private func observeScaleChanges() {
        for obs in scaleObservers { NotificationCenter.default.removeObserver(obs) }
        scaleObservers.removeAll()
        guard let pdfView else { return }
        syncZoomPercent()

        let update: @Sendable (Notification) -> Void = { [weak self] _ in
            DispatchQueue.main.async { self?.syncZoomPercent() }
        }

        scaleObservers.append(NotificationCenter.default.addObserver(
            forName: .PDFViewScaleChanged, object: pdfView, queue: .main
        ) { [weak self] _ in self?.syncZoomPercent() })

        if let scrollView = pdfView.documentView?.enclosingScrollView {
            scrollView.contentView.postsBoundsChangedNotifications = true
            scaleObservers.append(NotificationCenter.default.addObserver(
                forName: NSScrollView.didEndLiveMagnifyNotification, object: scrollView, queue: .main
            ) { [weak self] _ in self?.syncZoomPercent() })
            scaleObservers.append(NotificationCenter.default.addObserver(
                forName: NSView.boundsDidChangeNotification, object: scrollView.contentView, queue: .main
            ) { [weak self] _ in self?.syncZoomPercent() })
        }
    }

    func syncZoomPercent() {
        guard let pdfView else { return }
        let pct = Int((pdfView.scaleFactor * 100).rounded())
        if pct != zoomPercent { zoomPercent = pct }
    }

    func lateBindScrollObservers() {
        guard let pdfView, let scrollView = pdfView.documentView?.enclosingScrollView else { return }
        let alreadyBound = scaleObservers.count > 1
        if alreadyBound { return }
        scrollView.contentView.postsBoundsChangedNotifications = true
        scaleObservers.append(NotificationCenter.default.addObserver(
            forName: NSScrollView.didEndLiveMagnifyNotification, object: scrollView, queue: .main
        ) { [weak self] _ in self?.syncZoomPercent() })
        scaleObservers.append(NotificationCenter.default.addObserver(
            forName: NSView.boundsDidChangeNotification, object: scrollView.contentView, queue: .main
        ) { [weak self] _ in self?.syncZoomPercent() })
    }

    deinit {
        for obs in scaleObservers { NotificationCenter.default.removeObserver(obs) }
    }

    struct Anchor {
        let sectionName: String?
        let offset: Int
        let absolutePage: Int
    }

    func currentAnchor() -> Anchor? {
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
            absolutePage: pageIndex
        )
    }

    func restore(anchor: Anchor?, in document: PDFDocument, sections: [ProofSection]) {
        guard let pdfView, let anchor, document.pageCount > 0 else { return }
        let targetIndex: Int
        if let sectionName = anchor.sectionName,
           let section = sections.first(where: { $0.name == sectionName }) {
            targetIndex = min(section.firstPage + anchor.offset, document.pageCount - 1)
        } else {
            targetIndex = min(anchor.absolutePage, document.pageCount - 1)
        }
        if let page = document.page(at: max(0, targetIndex)) {
            pdfView.go(to: page)
        }
    }

    func handleNavigation(
        _ request: PreviewNavigationRequest?,
        in document: PDFDocument
    ) {
        guard let request,
              request.id != lastHandledNavigationRequestID,
              document.pageCount > 0 else { return }
        let pageIndex = min(max(request.pageIndex, 0), document.pageCount - 1)
        guard let page = document.page(at: pageIndex) else { return }
        lastHandledNavigationRequestID = request.id
        pdfView?.goToPageTop(page)
        thumbnailSidebar?.scrollToPage(pageIndex)
    }

    func updateThumbnails(document: PDFDocument?, sections: [ProofSection], forceRebuild: Bool) {
        guard let thumbnailSidebar, let pdfView else { return }
        thumbnailSidebar.thumbnailList.update(
            document: document,
            sections: sections,
            pdfView: pdfView,
            availableWidth: thumbnailSidebar.thumbnailAvailableWidth,
            forceRebuild: forceRebuild
        )
    }
}

// MARK: - PDFCanvasView

/// Wraps a bare PDFView. Document loading and thumbnail updates are driven from here.
struct PDFCanvasView: NSViewRepresentable {
    let pdfPath: String?
    let sections: [ProofSection]
    let navigationRequest: PreviewNavigationRequest?
    let pdfCoordinator: PDFViewCoordinator

    func makeNSView(context: Context) -> PDFView {
        let pdfView = PDFView()
        pdfView.autoScales = true
        pdfView.displaysPageBreaks = true
        pdfView.displayMode = .singlePageContinuous
        pdfCoordinator.pdfView = pdfView
        pdfCoordinator.lastLoadedPDFPath = nil
        return pdfView
    }

    func updateNSView(_ pdfView: PDFView, context: Context) {
        pdfCoordinator.lateBindScrollObservers()
        if let path = pdfPath {
            let url = URL(fileURLWithPath: path)
            let documentChanged = pdfCoordinator.lastLoadedPDFPath != path
            if let document = documentChanged ? PDFDocument(url: url) : pdfView.document {
                if documentChanged {
                    let anchor = pdfCoordinator.currentAnchor()
                    pdfView.document = document
                    pdfCoordinator.lastLoadedPDFPath = path
                    pdfCoordinator.restore(anchor: anchor, in: document, sections: sections)
                }
                let sectionsChanged = pdfCoordinator.sections != sections
                pdfCoordinator.updateThumbnails(
                    document: document,
                    sections: sections,
                    forceRebuild: documentChanged || sectionsChanged
                )
                pdfCoordinator.sections = sections
                pdfCoordinator.handleNavigation(navigationRequest, in: document)
            }
        } else {
            pdfView.document = nil
            pdfCoordinator.lastLoadedPDFPath = nil
            pdfCoordinator.sections = []
            pdfCoordinator.updateThumbnails(document: nil, sections: [], forceRebuild: true)
            pdfCoordinator.lastHandledNavigationRequestID = nil
        }
    }
}

// MARK: - ThumbnailStripView

/// Wraps the ThumbnailSidebarView as a standalone column.
struct ThumbnailStripView: NSViewRepresentable {
    let pdfPath: String?
    let sections: [ProofSection]
    let pdfCoordinator: PDFViewCoordinator

    func makeNSView(context: Context) -> ThumbnailSidebarView {
        let sidebar = ThumbnailSidebarView(defaultWidth: 160)
        pdfCoordinator.thumbnailSidebar = sidebar
        return sidebar
    }

    func updateNSView(_ sidebar: ThumbnailSidebarView, context: Context) {
        guard let pdfView = pdfCoordinator.pdfView else { return }
        let document = pdfView.document
        let pathChanged = context.coordinator.lastPath != pdfPath
        let sectionsChanged = context.coordinator.lastSections != sections
        if pathChanged || sectionsChanged {
            sidebar.thumbnailList.update(
                document: document,
                sections: sections,
                pdfView: pdfView,
                availableWidth: sidebar.thumbnailAvailableWidth,
                forceRebuild: pathChanged || sectionsChanged
            )
            context.coordinator.lastPath = pdfPath
            context.coordinator.lastSections = sections
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    class Coordinator {
        var lastPath: String?
        var lastSections: [ProofSection] = []
    }
}

// MARK: - GridViewCanvas

struct GridViewCanvas: View {
    let pdfPath: String
    let sections: [ProofSection]
    let pdfCoordinator: PDFViewCoordinator
    @EnvironmentObject var page: PageState

    @State private var document: PDFDocument?

    var body: some View {
        ScrollView {
            if let document, document.pageCount > 0 {
                let pageCount = document.pageCount
                let sectionMap = buildSectionMap(pageCount: pageCount)

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: 12)], spacing: 12) {
                    ForEach(0..<pageCount, id: \.self) { pageIndex in
                        VStack(spacing: 0) {
                            if let sectionName = sectionMap[pageIndex] {
                                Text(sectionName)
                                    .font(.system(size: 11, weight: .medium))
                                    .tracking(0.88)
                                    .foregroundStyle(.secondary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.bottom, 4)
                            }

                            Button {
                                page.viewMode = .page
                                if let page = document.page(at: pageIndex) {
                                    pdfCoordinator.pdfView?.go(to: page)
                                }
                            } label: {
                                GridThumbnailView(document: document, pageIndex: pageIndex)
                            }
                            .buttonStyle(.plain)

                            Text("\(pageIndex + 1)")
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(.tertiary)
                                .padding(.top, 2)
                        }
                    }
                }
                .padding(16)
            } else {
                Text("No pages to display")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .scrollEdgeEffectStyle(.soft, for: .all)
        .onAppear { loadDocument() }
        .onChange(of: pdfPath) { _ in loadDocument() }
    }

    private func loadDocument() {
        let url = URL(fileURLWithPath: pdfPath)
        document = PDFDocument(url: url)
    }

    private func buildSectionMap(pageCount: Int) -> [Int: String] {
        var map: [Int: String] = [:]
        for section in sections {
            let idx = min(max(section.firstPage, 0), pageCount - 1)
            map[idx] = section.name
        }
        return map
    }
}

private struct GridThumbnailView: View {
    let document: PDFDocument
    let pageIndex: Int

    var body: some View {
        if let page = document.page(at: pageIndex) {
            let bounds = page.bounds(for: .mediaBox)
            let aspect = bounds.width / max(bounds.height, 1)
            let image = page.thumbnail(of: NSSize(width: 360, height: 360 / aspect), for: .mediaBox)
            Image(nsImage: image)
                .resizable()
                .aspectRatio(aspect, contentMode: .fit)
                .clipShape(RoundedRectangle(cornerRadius: 4))
                .overlay(
                    RoundedRectangle(cornerRadius: 4)
                        .stroke(Color.primary.opacity(0.1), lineWidth: 0.5)
                )
        }
    }
}

// MARK: - CompareViewCanvas

struct CompareViewCanvas: View {
    let pdfPath: String
    let pdfCoordinator: PDFViewCoordinator
    let vertical: Bool

    @State private var pageCount: Int = 0
    @State private var leftPageIndex: Int = 0
    @State private var rightPageIndex: Int = 1

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                pageControls(index: $leftPageIndex)
                Divider().frame(height: 20)
                pageControls(index: $rightPageIndex)
            }
            .padding(.vertical, 6)

            SyncedCompareNSView(
                pdfPath: pdfPath,
                leftPageIndex: leftPageIndex,
                rightPageIndex: rightPageIndex,
                vertical: vertical,
                onPageCount: { pageCount = $0 }
            )
        }
        .onChange(of: pdfPath) { _ in
            leftPageIndex = 0
            rightPageIndex = min(1, max(pageCount - 1, 0))
        }
    }

    private func pageControls(index: Binding<Int>) -> some View {
        HStack {
            Spacer()
            Button { if index.wrappedValue > 0 { index.wrappedValue -= 1 } } label: {
                Image(systemName: "chevron.left")
            }
            .disabled(index.wrappedValue <= 0)

            Text("Page \(index.wrappedValue + 1) of \(pageCount)")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.secondary)

            Button {
                if index.wrappedValue < pageCount - 1 { index.wrappedValue += 1 }
            } label: {
                Image(systemName: "chevron.right")
            }
            .disabled(index.wrappedValue >= pageCount - 1)
            Spacer()
        }
    }
}

// Single NSViewRepresentable that owns both PDFViews and syncs them in AppKit.
private struct SyncedCompareNSView: NSViewRepresentable {
    let pdfPath: String
    let leftPageIndex: Int
    let rightPageIndex: Int
    let vertical: Bool
    var onPageCount: (Int) -> Void

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> SyncedCompareContainer {
        SyncedCompareContainer()
    }

    func updateNSView(_ container: SyncedCompareContainer, context: Context) {
        let count = container.loadIfNeeded(path: pdfPath)
        if count != context.coordinator.lastPageCount {
            context.coordinator.lastPageCount = count
            DispatchQueue.main.async { onPageCount(count) }
        }
        container.vertical = vertical
        container.needsLayout = true
        container.showPage(leftPageIndex, on: .left)
        container.showPage(rightPageIndex, on: .right)
    }

    class Coordinator {
        var lastPageCount = 0
    }
}

private enum Side { case left, right }

private final class SyncedCompareContainer: NSView {
    let leftPDF = PDFView()
    let rightPDF = PDFView()
    private let dividerView = NSView()
    private var document: PDFDocument?
    private var loadedPath: String?
    private var leftShownPage = -1
    private var rightShownPage = -1
    var vertical = false
    private var observers: [NSObjectProtocol] = []
    private var syncing = false
    private var didSetupSync = false

    override init(frame: NSRect) {
        super.init(frame: frame)
        for pdfView in [leftPDF, rightPDF] {
            pdfView.autoScales = true
            pdfView.displaysPageBreaks = false
            pdfView.displayMode = .singlePage
            addSubview(pdfView)
        }
        dividerView.wantsLayer = true
        dividerView.layer?.backgroundColor = NSColor.separatorColor.withAlphaComponent(0.5).cgColor
        addSubview(dividerView)
    }

    required init?(coder: NSCoder) { fatalError() }

    override var isFlipped: Bool { true }

    override func layout() {
        super.layout()
        let w = bounds.width
        let h = bounds.height
        let d: CGFloat = 2
        if vertical {
            let half = floor((h - d) / 2)
            leftPDF.frame = NSRect(x: 0, y: 0, width: w, height: half)
            dividerView.frame = NSRect(x: 0, y: half, width: w, height: d)
            rightPDF.frame = NSRect(x: 0, y: half + d, width: w, height: h - half - d)
        } else {
            let half = floor((w - d) / 2)
            leftPDF.frame = NSRect(x: 0, y: 0, width: half, height: h)
            dividerView.frame = NSRect(x: half, y: 0, width: d, height: h)
            rightPDF.frame = NSRect(x: half + d, y: 0, width: w - half - d, height: h)
        }
    }

    func loadIfNeeded(path: String) -> Int {
        guard path != loadedPath else { return document?.pageCount ?? 0 }
        loadedPath = path
        leftShownPage = -1
        rightShownPage = -1
        didSetupSync = false
        let url = URL(fileURLWithPath: path)
        document = PDFDocument(url: url)
        return document?.pageCount ?? 0
    }

    func showPage(_ index: Int, on side: Side) {
        guard let document, index >= 0, index < document.pageCount else { return }
        let pdfView = side == .left ? leftPDF : rightPDF
        let shown = side == .left ? leftShownPage : rightShownPage
        guard index != shown else { return }

        let singleDoc = PDFDocument()
        if let page = document.page(at: index) {
            singleDoc.insert(page, at: 0)
        }

        syncing = true
        let otherView = side == .left ? rightPDF : leftPDF
        let otherHasDoc = otherView.document != nil && (otherView.document?.pageCount ?? 0) > 0
        pdfView.document = singleDoc
        if otherHasDoc {
            pdfView.autoScales = false
            pdfView.scaleFactor = otherView.scaleFactor
        }
        syncing = false

        switch side {
        case .left: leftShownPage = index
        case .right: rightShownPage = index
        }

        if !didSetupSync { setupSync() }
    }

    private func setupSync() {
        for obs in observers { NotificationCenter.default.removeObserver(obs) }
        observers.removeAll()
        didSetupSync = true

        for (pdfView, side) in [(leftPDF, Side.left), (rightPDF, Side.right)] {
            let scaleObs = NotificationCenter.default.addObserver(
                forName: .PDFViewScaleChanged, object: pdfView, queue: .main
            ) { [weak self] _ in self?.handleSync(from: side) }
            observers.append(scaleObs)

            if let scrollView = pdfView.documentView?.enclosingScrollView {
                scrollView.contentView.postsBoundsChangedNotifications = true
                let boundsObs = NotificationCenter.default.addObserver(
                    forName: NSView.boundsDidChangeNotification,
                    object: scrollView.contentView, queue: .main
                ) { [weak self] _ in self?.handleSync(from: side) }
                observers.append(boundsObs)
            }
        }
    }

    private func handleSync(from source: Side) {
        guard !syncing else { return }
        syncing = true
        defer { syncing = false }

        let (src, dst) = source == .left ? (leftPDF, rightPDF) : (rightPDF, leftPDF)

        if abs(dst.scaleFactor - src.scaleFactor) > 0.001 {
            dst.scaleFactor = src.scaleFactor
        }

        guard let srcScroll = src.documentView?.enclosingScrollView,
              let dstScroll = dst.documentView?.enclosingScrollView else { return }
        let srcOrigin = srcScroll.contentView.bounds.origin
        let dstOrigin = dstScroll.contentView.bounds.origin
        if abs(srcOrigin.x - dstOrigin.x) > 0.5 || abs(srcOrigin.y - dstOrigin.y) > 0.5 {
            dstScroll.contentView.scroll(to: srcOrigin)
            dstScroll.reflectScrolledClipView(dstScroll.contentView)
        }
    }

    deinit {
        for obs in observers { NotificationCenter.default.removeObserver(obs) }
    }
}

// MARK: - PDFPlaceholderView

struct PDFPlaceholderView: View {
    let hasFonts: Bool

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "doc.richtext")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text(hasFonts ? "Preview Not Ready" : "No Fonts Loaded")
                .font(.title3)
                .foregroundStyle(.secondary)
            Text(hasFonts ? "Preview fragments will appear here as they finish" : "Load fonts to start preview generation")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Thumbnail Sidebar View

/// AppKit frame-layout sidebar containing a scrollable ThumbnailListView.
final class ThumbnailSidebarView: NSView {
    let thumbnailList: ThumbnailListView

    private let thumbnailScroll = NSScrollView()

    var thumbnailAvailableWidth: CGFloat {
        let contentWidth = thumbnailScroll.contentView.bounds.width
        return max(contentWidth > 0 ? contentWidth : bounds.width, 80)
    }

    init(defaultWidth: CGFloat) {
        thumbnailList = ThumbnailListView(frame: NSRect(x: 0, y: 0, width: defaultWidth, height: 1))
        super.init(frame: NSRect(x: 0, y: 0, width: defaultWidth, height: 1))

        thumbnailScroll.hasVerticalScroller = true
        thumbnailScroll.autohidesScrollers = true
        thumbnailScroll.drawsBackground = false
        thumbnailScroll.documentView = thumbnailList

        addSubview(thumbnailScroll)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layout() {
        super.layout()

        let width = max(bounds.width, 80)
        let height = max(bounds.height, 0)
        thumbnailScroll.frame = NSRect(x: 0, y: 0, width: width, height: height)
        thumbnailList.updateAvailableWidth(thumbnailAvailableWidth)
    }

    func scrollToPage(_ pageIndex: Int) {
        layoutSubtreeIfNeeded()
        thumbnailList.updateAvailableWidth(thumbnailAvailableWidth)

        guard let rect = thumbnailList.navigationRect(forPageAt: pageIndex) else { return }
        let clipView = thumbnailScroll.contentView
        let maxY = max(thumbnailList.bounds.height - clipView.bounds.height, 0)
        let targetY = min(max(rect.minY - 8, 0), maxY)
        clipView.scroll(to: NSPoint(x: 0, y: targetY))
        thumbnailScroll.reflectScrolledClipView(thumbnailScroll.contentView)
    }

    override var isFlipped: Bool { true }
}

// MARK: - Custom Thumbnail List View

/// A vertical stack of eagerly rendered PDF page thumbnails.
final class ThumbnailListView: NSView {
    private var document: PDFDocument?
    private weak var pdfView: PDFView?
    private var sections: [ProofSection] = []
    private var thumbnailViews: [NSView] = []
    private var navigationRectsByPage: [Int: NSRect] = [:]
    private var availableWidth: CGFloat = 160
    private var lastDocumentURL: URL?
    private var lastPageCount = 0
    private var thumbnailCache: [ThumbnailCacheKey: NSImage] = [:]

    private let thumbnailSpacing: CGFloat = 4
    private let pageNumberHeight: CGFloat = 16
    private let sectionSpacing: CGFloat = 12

    func update(
        document: PDFDocument?,
        sections: [ProofSection],
        pdfView: PDFView,
        availableWidth: CGFloat,
        forceRebuild: Bool
    ) {
        let nextWidth = max(availableWidth, 80)
        let documentURL = document?.documentURL
        let pageCount = document?.pageCount ?? 0
        let needsRebuild = forceRebuild
            || documentURL != lastDocumentURL
            || pageCount != lastPageCount
            || sections != self.sections
            || abs(nextWidth - self.availableWidth) > 1

        guard needsRebuild else { return }

        self.document = document
        self.pdfView = pdfView
        self.sections = sections
        self.availableWidth = nextWidth
        self.lastDocumentURL = documentURL
        self.lastPageCount = pageCount
        rebuildThumbnails()
    }

    func updateAvailableWidth(_ width: CGFloat) {
        let nextWidth = max(width, 80)
        guard abs(nextWidth - availableWidth) > 1 else { return }
        availableWidth = nextWidth
        rebuildThumbnails()
    }

    private func rebuildThumbnails() {
        for view in thumbnailViews { view.removeFromSuperview() }
        thumbnailViews.removeAll()
        navigationRectsByPage.removeAll()

        guard let document else {
            frame = NSRect(x: 0, y: 0, width: availableWidth, height: 1)
            return
        }

        let pageCount = document.pageCount
        guard pageCount > 0 else {
            frame = NSRect(x: 0, y: 0, width: availableWidth, height: 1)
            return
        }

        var sectionStartPages: [Int: String] = [:]
        for section in sections {
            let pageIndex = min(max(section.firstPage, 0), pageCount - 1)
            sectionStartPages[pageIndex] = section.name
        }

        let padding: CGFloat = 8
        let effectiveThumbWidth = max(1, availableWidth - padding * 2)
        var yOffset: CGFloat = 8

        for pageIndex in 0..<pageCount {
            if let sectionName = sectionStartPages[pageIndex] {
                if pageIndex > 0 { yOffset += sectionSpacing }

                let labelRect = NSRect(x: 8, y: yOffset, width: availableWidth - 16, height: 14)
                let label = NSTextField(labelWithString: sectionName)
                label.font = NSFont.systemFont(ofSize: 10, weight: .semibold)
                label.textColor = .secondaryLabelColor
                label.lineBreakMode = .byTruncatingTail
                label.frame = labelRect
                addSubview(label)
                thumbnailViews.append(label)
                navigationRectsByPage[pageIndex] = labelRect
                yOffset += 18
            }

            guard let page = document.page(at: pageIndex) else { continue }
            let pageBounds = page.bounds(for: .mediaBox)
            let aspect = max(pageBounds.width / max(pageBounds.height, 1), 0.01)
            let thumbHeight = effectiveThumbWidth / aspect
            let thumbRect = NSRect(x: padding, y: yOffset, width: effectiveThumbWidth, height: thumbHeight)

            let thumbView = PageThumbnailButton(
                page: page,
                frame: thumbRect,
                pdfView: pdfView,
                cachedImage: thumbnailImage(
                    for: page,
                    pageIndex: pageIndex,
                    width: effectiveThumbWidth,
                    height: thumbHeight
                )
            )
            addSubview(thumbView)
            thumbnailViews.append(thumbView)
            if navigationRectsByPage[pageIndex] == nil {
                navigationRectsByPage[pageIndex] = thumbRect
            }
            yOffset += thumbHeight + 2

            let pageLabel = NSTextField(labelWithString: "\(pageIndex + 1)")
            pageLabel.font = NSFont.monospacedDigitSystemFont(ofSize: 9, weight: .regular)
            pageLabel.textColor = .tertiaryLabelColor
            pageLabel.alignment = .center
            pageLabel.frame = NSRect(x: padding, y: yOffset, width: effectiveThumbWidth, height: pageNumberHeight)
            addSubview(pageLabel)
            thumbnailViews.append(pageLabel)
            yOffset += pageNumberHeight + thumbnailSpacing
        }

        frame = NSRect(x: 0, y: 0, width: availableWidth, height: yOffset + 8)
        needsDisplay = true
    }

    func navigationRect(forPageAt pageIndex: Int) -> NSRect? {
        navigationRectsByPage[pageIndex]
    }

    override var isFlipped: Bool { true }

    private func thumbnailImage(for page: PDFPage, pageIndex: Int, width: CGFloat, height: CGFloat) -> NSImage {
        let key = ThumbnailCacheKey(
            documentPath: document?.documentURL?.path ?? "",
            pageIndex: pageIndex,
            width: Int((width * 2).rounded())
        )
        if let cached = thumbnailCache[key] {
            return cached
        }

        let image = page.thumbnail(
            of: NSSize(width: width * 2, height: height * 2),
            for: .mediaBox
        )
        thumbnailCache[key] = image
        if thumbnailCache.count > 500 {
            thumbnailCache.removeAll(keepingCapacity: true)
            thumbnailCache[key] = image
        }
        return image
    }
}

// MARK: - Page Thumbnail Button

private struct ThumbnailCacheKey: Hashable {
    let documentPath: String
    let pageIndex: Int
    let width: Int
}

final class PageThumbnailButton: NSButton {
    private let page: PDFPage
    private weak var pdfView: PDFView?

    init(page: PDFPage, frame: NSRect, pdfView: PDFView?, cachedImage: NSImage) {
        self.page = page
        self.pdfView = pdfView
        super.init(frame: frame)

        isBordered = false
        imagePosition = .imageOnly
        imageScaling = .scaleProportionallyUpOrDown
        target = self
        action = #selector(clicked)

        image = cachedImage

        wantsLayer = true
        layer?.borderWidth = 0.5
        layer?.borderColor = NSColor.separatorColor.cgColor
        layer?.cornerRadius = 3
    }

    required init?(coder: NSCoder) { fatalError() }

    @objc private func clicked() {
        pdfView?.go(to: page)
    }
}

// MARK: - PDF Navigation

private extension PDFView {
    func goToPageTop(_ page: PDFPage) {
        let pageBounds = page.bounds(for: .mediaBox)
        let destination = PDFDestination(page: page, at: NSPoint(x: pageBounds.minX, y: pageBounds.maxY))
        go(to: destination)

        DispatchQueue.main.async { [weak self] in
            self?.alignPageTopWithViewport(page)
        }
    }

    func alignPageTopWithViewport(_ page: PDFPage) {
        guard let documentView,
              let clipView = documentView.enclosingScrollView?.contentView else { return }

        layoutSubtreeIfNeeded()
        documentView.layoutSubtreeIfNeeded()

        let pageBounds = page.bounds(for: .mediaBox)
        let pageRectInPDFView = convert(pageBounds, from: page)
        let pageRect = documentView.convert(pageRectInPDFView, from: self)
        let visibleHeight = clipView.bounds.height
        let maxY = max(documentView.bounds.height - visibleHeight, 0)

        let targetY: CGFloat
        if documentView.isFlipped {
            targetY = pageRect.minY
        } else {
            targetY = pageRect.maxY - visibleHeight
        }

        let clampedY = min(max(targetY, 0), maxY)
        clipView.scroll(to: NSPoint(x: clipView.bounds.origin.x, y: clampedY))
        documentView.enclosingScrollView?.reflectScrolledClipView(clipView)
    }
}
