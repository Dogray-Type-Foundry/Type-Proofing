import SwiftUI
import PDFKit

// MARK: - PDFViewerView

/// Wraps PDFKit's PDFView with a custom resizable thumbnail sidebar.
struct PDFViewerView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        if state.currentPDFPath != nil {
            PDFSplitContainer(
                pdfPath: state.currentPDFPath,
                sections: state.proofSections
            )
        } else {
            VStack(spacing: 12) {
                Image(systemName: "doc.richtext")
                    .font(.system(size: 48))
                    .foregroundStyle(.secondary)
                Text("No PDF Generated Yet")
                    .font(.title3)
                    .foregroundStyle(.secondary)
                Text("Load fonts and press Generate to create a proof")
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

    private static let defaultThumbWidth: CGFloat = 160

    func makeNSView(context: Context) -> NSView {
        let container = NSView()

        let splitView = WiderDividerSplitView()
        splitView.isVertical = true
        splitView.dividerStyle = .thin
        splitView.delegate = context.coordinator

        // Thumbnail sidebar (index 0)
        let thumbnailScroll = NSScrollView()
        thumbnailScroll.hasVerticalScroller = true
        thumbnailScroll.autohidesScrollers = true
        thumbnailScroll.drawsBackground = false

        let thumbnailList = ThumbnailListView()
        thumbnailScroll.documentView = thumbnailList
        thumbnailList.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            thumbnailList.topAnchor.constraint(equalTo: thumbnailScroll.contentView.topAnchor),
            thumbnailList.leadingAnchor.constraint(equalTo: thumbnailScroll.contentView.leadingAnchor),
            thumbnailList.trailingAnchor.constraint(equalTo: thumbnailScroll.contentView.trailingAnchor),
        ])

        // PDF view (index 1)
        let pdfView = PDFView()
        pdfView.autoScales = true
        pdfView.displaysPageBreaks = true
        pdfView.displayMode = .singlePageContinuous

        splitView.addSubview(thumbnailScroll)
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
        context.coordinator.thumbnailList = thumbnailList
        context.coordinator.thumbnailScroll = thumbnailScroll
        context.coordinator.splitView = splitView

        return container
    }

    func updateNSView(_ container: NSView, context: Context) {
        guard let pdfView = context.coordinator.pdfView,
              let thumbnailList = context.coordinator.thumbnailList else { return }

        if let path = pdfPath {
            let url = URL(fileURLWithPath: path)
            if let document = PDFDocument(url: url) {
                pdfView.document = document
                thumbnailList.update(document: document, sections: sections, pdfView: pdfView)
            }
        } else {
            pdfView.document = nil
            thumbnailList.update(document: nil, sections: [], pdfView: pdfView)
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    class Coordinator: NSObject, NSSplitViewDelegate {
        var pdfView: PDFView?
        var thumbnailList: ThumbnailListView?
        var thumbnailScroll: NSScrollView?
        var splitView: NSSplitView?

        func splitView(_ splitView: NSSplitView, constrainMinCoordinate proposedMinimumPosition: CGFloat, ofSubviewAt dividerIndex: Int) -> CGFloat {
            100
        }

        func splitView(_ splitView: NSSplitView, constrainMaxCoordinate proposedMaximumPosition: CGFloat, ofSubviewAt dividerIndex: Int) -> CGFloat {
            min(proposedMaximumPosition, 300)
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

// MARK: - Custom Thumbnail List View

/// A vertical stack of thumbnails grouped by section headers.
final class ThumbnailListView: NSView {
    private var document: PDFDocument?
    private weak var pdfView: PDFView?
    private var sections: [ProofSection] = []
    private var thumbnailViews: [NSView] = []

    private let thumbnailWidth: CGFloat = 140
    private let thumbnailSpacing: CGFloat = 4
    private let pageNumberHeight: CGFloat = 16
    private let sectionSpacing: CGFloat = 12

    func update(document: PDFDocument?, sections: [ProofSection], pdfView: PDFView) {
        self.document = document
        self.pdfView = pdfView
        self.sections = sections
        rebuildThumbnails()
    }

    private func rebuildThumbnails() {
        // Remove old views
        for view in thumbnailViews { view.removeFromSuperview() }
        thumbnailViews.removeAll()

        guard let document else {
            frame.size.height = 0
            return
        }

        let pageCount = document.pageCount
        guard pageCount > 0 else { return }

        // Build a map: page index → section name (for the first page of each section)
        var sectionStartPages: [Int: String] = [:]
        for (i, section) in sections.enumerated() {
            // First section uses firstPage as-is; subsequent sections need -1
            // because DrawBot's pageCount() is 1-based after the first proof.
            let adjustedPage = i == 0 ? section.firstPage : max(0, section.firstPage - 1)
            sectionStartPages[adjustedPage] = section.name
        }

        let containerWidth = max(bounds.width, 80)
        let padding: CGFloat = 8
        let effectiveThumbWidth = containerWidth - padding * 2
        var yOffset: CGFloat = 8

        for pageIndex in 0..<pageCount {
            // Section header
            if let sectionName = sectionStartPages[pageIndex] {
                if pageIndex > 0 { yOffset += sectionSpacing }

                let label = NSTextField(labelWithString: sectionName)
                label.font = NSFont.systemFont(ofSize: 10, weight: .semibold)
                label.textColor = .secondaryLabelColor
                label.lineBreakMode = .byTruncatingTail
                label.frame = NSRect(x: 8, y: yOffset, width: containerWidth - 16, height: 14)
                addSubview(label)
                thumbnailViews.append(label)
                yOffset += 18
            }

            // Thumbnail
            guard let page = document.page(at: pageIndex) else { continue }
            let pageBounds = page.bounds(for: .mediaBox)
            let aspect = pageBounds.width / pageBounds.height
            let thumbHeight = effectiveThumbWidth / aspect

            let thumbView = PageThumbnailButton(
                page: page,
                pageIndex: pageIndex,
                frame: NSRect(
                    x: padding,
                    y: yOffset,
                    width: effectiveThumbWidth,
                    height: thumbHeight
                ),
                pdfView: pdfView
            )
            addSubview(thumbView)
            thumbnailViews.append(thumbView)
            yOffset += thumbHeight + 2

            // Page number label
            let pageLabel = NSTextField(labelWithString: "\(pageIndex + 1)")
            pageLabel.font = NSFont.monospacedDigitSystemFont(ofSize: 9, weight: .regular)
            pageLabel.textColor = .tertiaryLabelColor
            pageLabel.alignment = .center
            pageLabel.frame = NSRect(x: padding, y: yOffset, width: effectiveThumbWidth, height: pageNumberHeight)
            addSubview(pageLabel)
            thumbnailViews.append(pageLabel)
            yOffset += pageNumberHeight + thumbnailSpacing
        }

        yOffset += 8
        frame = NSRect(x: 0, y: 0, width: containerWidth, height: yOffset)
        needsLayout = true
    }

    override func resizeSubviews(withOldSize oldSize: NSSize) {
        super.resizeSubviews(withOldSize: oldSize)
        if abs(bounds.width - oldSize.width) > 1 {
            rebuildThumbnails()
        }
    }

    override var isFlipped: Bool { true }
}

// MARK: - Page Thumbnail Button

final class PageThumbnailButton: NSButton {
    private let page: PDFPage
    private let pageIndex: Int
    private weak var pdfView: PDFView?

    init(page: PDFPage, pageIndex: Int, frame: NSRect, pdfView: PDFView?) {
        self.page = page
        self.pageIndex = pageIndex
        self.pdfView = pdfView
        super.init(frame: frame)

        isBordered = false
        imagePosition = .imageOnly
        imageScaling = .scaleProportionallyUpOrDown
        target = self
        action = #selector(clicked)

        // Generate thumbnail image
        let thumbSize = NSSize(width: frame.width * 2, height: frame.height * 2) // retina
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
