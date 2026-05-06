import SwiftUI
import PDFKit

// MARK: - PDFViewerView

/// Wraps PDFKit's PDFView with a custom resizable thumbnail sidebar.
struct PDFViewerView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        if state.previewPDFPath != nil {
            PDFSplitContainer(
                pdfPath: state.previewPDFPath,
                sections: state.previewSections,
                navigationRequest: state.previewNavigationRequest
            )
        } else {
            VStack(spacing: 12) {
                Image(systemName: "doc.richtext")
                    .font(.system(size: 48))
                    .foregroundStyle(.secondary)
                Text(state.enabledFontPaths.isEmpty ? "No Fonts Loaded" : "Preview Not Ready")
                    .font(.title3)
                    .foregroundStyle(.secondary)
                Text(state.enabledFontPaths.isEmpty ? "Load fonts to start preview generation" : "Preview fragments will appear here as they finish")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

// MARK: - Split Container (NSSplitView wrapper)

struct PDFSplitContainer: NSViewRepresentable {
    let pdfPath: String?
    let sections: [ProofSection]
    let navigationRequest: PreviewNavigationRequest?

    private static let defaultThumbWidth: CGFloat = 220

    func makeNSView(context: Context) -> NSView {
        let container = NSView()

        let splitView = WiderDividerSplitView()
        splitView.isVertical = true
        splitView.dividerStyle = .thin
        splitView.delegate = context.coordinator

        // Thumbnail sidebar (index 0)
        let thumbnailSidebar = ThumbnailSidebarView(defaultWidth: Self.defaultThumbWidth)

        // PDF view (index 1)
        let pdfView = PDFView()
        pdfView.autoScales = true
        pdfView.displaysPageBreaks = true
        pdfView.displayMode = .singlePageContinuous

        splitView.addSubview(thumbnailSidebar)
        splitView.addSubview(pdfView)

        splitView.setHoldingPriority(.defaultLow, forSubviewAt: 0)
        splitView.setHoldingPriority(.defaultHigh, forSubviewAt: 1)

        // Layout split view filling the container
        splitView.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(splitView)
        NSLayoutConstraint.activate([
            splitView.topAnchor.constraint(equalTo: container.topAnchor),
            splitView.bottomAnchor.constraint(equalTo: container.bottomAnchor),
            splitView.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            splitView.trailingAnchor.constraint(equalTo: container.trailingAnchor),
        ])

        // Open at default width after layout
        DispatchQueue.main.async {
            splitView.setPosition(Self.defaultThumbWidth, ofDividerAt: 0)
        }

        context.coordinator.pdfView = pdfView
        context.coordinator.thumbnailSidebar = thumbnailSidebar
        context.coordinator.splitView = splitView

        return container
    }

    func updateNSView(_ container: NSView, context: Context) {
        guard let pdfView = context.coordinator.pdfView,
              let thumbnailSidebar = context.coordinator.thumbnailSidebar else { return }

        if let path = pdfPath {
            let url = URL(fileURLWithPath: path)
            if let document = PDFDocument(url: url) {
                let anchor = context.coordinator.currentAnchor()
                pdfView.document = document
                context.coordinator.restore(anchor: anchor, in: document, sections: sections)
                thumbnailSidebar.thumbnailList.update(
                    document: document,
                    sections: sections,
                    pdfView: pdfView,
                    availableWidth: thumbnailSidebar.thumbnailAvailableWidth
                )
                context.coordinator.sections = sections
                context.coordinator.handleNavigation(
                    navigationRequest,
                    in: document,
                    thumbnailSidebar: thumbnailSidebar
                )
            }
        } else {
            pdfView.document = nil
            context.coordinator.sections = []
            thumbnailSidebar.thumbnailList.update(
                document: nil,
                sections: [],
                pdfView: pdfView,
                availableWidth: thumbnailSidebar.thumbnailAvailableWidth
            )
            context.coordinator.lastHandledNavigationRequestID = nil
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    class Coordinator: NSObject, NSSplitViewDelegate {
        var pdfView: PDFView?
        var thumbnailSidebar: ThumbnailSidebarView?
        var splitView: NSSplitView?
        var sections: [ProofSection] = []
        var lastHandledNavigationRequestID: UUID?

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
            in document: PDFDocument,
            thumbnailSidebar: ThumbnailSidebarView
        ) {
            guard let request,
                  request.id != lastHandledNavigationRequestID,
                  document.pageCount > 0 else { return }
            let pageIndex = min(max(request.pageIndex, 0), document.pageCount - 1)
            guard let page = document.page(at: pageIndex) else { return }
            lastHandledNavigationRequestID = request.id
            pdfView?.goToPageTop(page)
            thumbnailSidebar.scrollToPage(pageIndex)
        }

        func splitView(_ splitView: NSSplitView, constrainMinCoordinate proposedMinimumPosition: CGFloat, ofSubviewAt dividerIndex: Int) -> CGFloat {
            100
        }

        func splitView(_ splitView: NSSplitView, constrainMaxCoordinate proposedMaximumPosition: CGFloat, ofSubviewAt dividerIndex: Int) -> CGFloat {
            min(proposedMaximumPosition, 420)
        }

        func splitView(_ splitView: NSSplitView, resizeSubviewsWithOldSize oldSize: NSSize) {
            let dividerThickness = splitView.dividerThickness
            let newSize = splitView.bounds.size

            guard splitView.subviews.count == 2 else {
                splitView.adjustSubviews()
                return
            }

            let thumbnailView = splitView.subviews[0]
            let pdfSubview = splitView.subviews[1]

            let thumbWidth = thumbnailView.frame.width
            let pdfWidth = max(0, newSize.width - thumbWidth - dividerThickness)

            thumbnailView.frame = NSRect(x: 0, y: 0, width: thumbWidth, height: newSize.height)
            pdfSubview.frame = NSRect(x: thumbWidth + dividerThickness, y: 0, width: pdfWidth, height: newSize.height)

            if let thumbnailSidebar {
                thumbnailSidebar.needsLayout = true
                thumbnailSidebar.layoutSubtreeIfNeeded()
                thumbnailSidebar.thumbnailList.updateAvailableWidth(thumbnailSidebar.thumbnailAvailableWidth)
            }
        }
    }
}

// MARK: - Wider Divider Split View

/// NSSplitView subclass with a wider effective drag area for easier resizing.
final class WiderDividerSplitView: NSSplitView {
    override var dividerThickness: CGFloat { 8 }

    override func drawDivider(in rect: NSRect) {
        // Draw a thin visual line centered within the wider hit area
        let lineRect = NSRect(
            x: rect.origin.x + (rect.width - 1) / 2,
            y: rect.origin.y,
            width: 1,
            height: rect.height
        )
        NSColor.separatorColor.setFill()
        lineRect.fill()
    }
}

// MARK: - Thumbnail Sidebar View

/// AppKit frame-layout sidebar used inside NSSplitView.
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

    private let thumbnailSpacing: CGFloat = 4
    private let pageNumberHeight: CGFloat = 16
    private let sectionSpacing: CGFloat = 12

    func update(document: PDFDocument?, sections: [ProofSection], pdfView: PDFView, availableWidth: CGFloat) {
        self.document = document
        self.pdfView = pdfView
        self.sections = sections
        self.availableWidth = max(availableWidth, 80)
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
                pdfView: pdfView
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
}

// MARK: - Page Thumbnail Button

final class PageThumbnailButton: NSButton {
    private let page: PDFPage
    private weak var pdfView: PDFView?

    init(page: PDFPage, frame: NSRect, pdfView: PDFView?) {
        self.page = page
        self.pdfView = pdfView
        super.init(frame: frame)

        isBordered = false
        imagePosition = .imageOnly
        imageScaling = .scaleProportionallyUpOrDown
        target = self
        action = #selector(clicked)

        let thumbSize = NSSize(width: frame.width * 2, height: frame.height * 2)
        image = page.thumbnail(of: thumbSize, for: .mediaBox)

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
