import ProofCore
import SwiftUI
import PDFKit

// MARK: - CompareViewCanvas (iOS)

/// Two synced single-page PDF views for side-by-side/stacked comparison —
/// the UIKit twin of the macOS compare canvas (zoom is synced; iOS PDFView
/// doesn't expose its scroll view, so scroll offsets are independent).
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

            SyncedCompareUIView(
                pdfPath: pdfPath,
                leftPageIndex: leftPageIndex,
                rightPageIndex: rightPageIndex,
                vertical: vertical,
                onPageCount: { count in
                    // Clamp against the *new* document's count — the
                    // onChange below still sees the previous one, and an
                    // out-of-range index left a pane pinned to the old,
                    // deleted document.
                    pageCount = count
                    leftPageIndex = min(leftPageIndex, max(count - 1, 0))
                    rightPageIndex = min(rightPageIndex, max(count - 1, 0))
                }
            )
        }
        .onChange(of: pdfPath) { _, _ in
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

// Single UIViewRepresentable that owns both PDFViews and syncs their zoom.
private struct SyncedCompareUIView: UIViewRepresentable {
    let pdfPath: String
    let leftPageIndex: Int
    let rightPageIndex: Int
    let vertical: Bool
    var onPageCount: (Int) -> Void

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> SyncedCompareContainer {
        SyncedCompareContainer()
    }

    func updateUIView(_ container: SyncedCompareContainer, context: Context) {
        let count = container.loadIfNeeded(path: pdfPath)
        if count != context.coordinator.lastPageCount {
            context.coordinator.lastPageCount = count
            DispatchQueue.main.async { onPageCount(count) }
        }
        container.vertical = vertical
        container.setNeedsLayout()
        container.showPage(leftPageIndex, on: .left)
        container.showPage(rightPageIndex, on: .right)
    }

    class Coordinator {
        var lastPageCount = 0
    }
}

private enum Side { case left, right }

private final class SyncedCompareContainer: UIView {
    let leftPDF = PDFView()
    let rightPDF = PDFView()
    private let dividerView = UIView()
    private var document: PDFDocument?
    private var loadedPath: String?
    private var leftShownPage = -1
    private var rightShownPage = -1
    var vertical = false
    private var syncing = false

    /// Notification-based sync only fires when a gesture *ends* on iOS, so a
    /// display link mirrors the actively-touched side to the other one every
    /// frame instead — live zoom and scroll-position sync.
    private var displayLink: CADisplayLink?
    private var lastActive: Side = .left

    override init(frame: CGRect) {
        super.init(frame: frame)
        for pdfView in [leftPDF, rightPDF] {
            pdfView.autoScales = true
            pdfView.displaysPageBreaks = false
            pdfView.displayMode = .singlePage
            pdfView.backgroundColor = .secondarySystemBackground
            addSubview(pdfView)
        }
        dividerView.backgroundColor = UIColor.separator.withAlphaComponent(0.5)
        addSubview(dividerView)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        displayLink?.invalidate()
        displayLink = nil
        if window != nil {
            let link = CADisplayLink(target: self, selector: #selector(tick))
            link.add(to: .main, forMode: .common)
            displayLink = link
        }
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        let w = bounds.width
        let h = bounds.height
        let d: CGFloat = 2
        if vertical {
            let half = floor((h - d) / 2)
            leftPDF.frame = CGRect(x: 0, y: 0, width: w, height: half)
            dividerView.frame = CGRect(x: 0, y: half, width: w, height: d)
            rightPDF.frame = CGRect(x: 0, y: half + d, width: w, height: h - half - d)
        } else {
            let half = floor((w - d) / 2)
            leftPDF.frame = CGRect(x: 0, y: 0, width: half, height: h)
            dividerView.frame = CGRect(x: half, y: 0, width: d, height: h)
            rightPDF.frame = CGRect(x: half + d, y: 0, width: w - half - d, height: h)
        }
    }

    func loadIfNeeded(path: String) -> Int {
        guard path != loadedPath else { return document?.pageCount ?? 0 }
        loadedPath = path
        leftShownPage = -1
        rightShownPage = -1
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
        // Insert a *copy* of the page: inserting the original re-parents it
        // away from the shared `document` (see the macOS twin for the
        // use-after-free this avoids).
        if let page = document.page(at: index)?.copy() as? PDFPage {
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
    }

    // MARK: Live sync

    /// PDFView doesn't expose its scroll view on iOS; find it in the hierarchy.
    private func scrollView(of pdfView: PDFView) -> UIScrollView? {
        func find(_ view: UIView) -> UIScrollView? {
            for sub in view.subviews {
                if let scroll = sub as? UIScrollView { return scroll }
                if let found = find(sub) { return found }
            }
            return nil
        }
        return find(pdfView)
    }

    private func isInteracting(_ scroll: UIScrollView?) -> Bool {
        guard let scroll else { return false }
        return scroll.isTracking || scroll.isDragging || scroll.isDecelerating || scroll.isZooming
    }

    @objc private func tick() {
        guard !syncing else { return }
        let leftScroll = scrollView(of: leftPDF)
        let rightScroll = scrollView(of: rightPDF)

        // The side the user is touching drives; remember it so deceleration
        // keeps syncing after the finger lifts.
        if isInteracting(leftScroll) { lastActive = .left }
        else if isInteracting(rightScroll) { lastActive = .right }

        let (src, dst) = lastActive == .left ? (leftPDF, rightPDF) : (rightPDF, leftPDF)
        let (srcScroll, dstScroll) = lastActive == .left ? (leftScroll, rightScroll) : (rightScroll, leftScroll)

        syncing = true
        defer { syncing = false }

        if abs(dst.scaleFactor - src.scaleFactor) > 0.0001 {
            dst.autoScales = false
            dst.scaleFactor = src.scaleFactor
        }

        // Mirror the scroll position in normalized page coordinates so both
        // sides show the same region even mid-gesture.
        if let srcScroll, let dstScroll,
           srcScroll.contentSize.width > 0, srcScroll.contentSize.height > 0,
           dstScroll.contentSize.width > 0, dstScroll.contentSize.height > 0 {
            let target = CGPoint(
                x: srcScroll.contentOffset.x / srcScroll.contentSize.width * dstScroll.contentSize.width,
                y: srcScroll.contentOffset.y / srcScroll.contentSize.height * dstScroll.contentSize.height
            )
            if abs(dstScroll.contentOffset.x - target.x) > 0.5 || abs(dstScroll.contentOffset.y - target.y) > 0.5 {
                dstScroll.contentOffset = target
            }
        }
    }
}
