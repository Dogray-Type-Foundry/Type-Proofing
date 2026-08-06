import Combine
import PDFKit
import PencilKit
import ProofCore
import UIKit

/// Supplies one annotation overlay (PencilKit canvas + text boxes) per
/// visible PDF page via PDFKit's `PDFPageOverlayViewProvider`, round-tripping
/// with the `AnnotationStore` keyed by (section optionID, page offset) so
/// markup survives recomposition shifting the section's start page.
///
/// While markup mode is on the preview pipeline is paused (see ContentView),
/// so page content can never regenerate under wet ink; pages whose fragment
/// isn't ready (placeholders) refuse markup entirely.
@MainActor
final class AnnotationOverlayProvider: NSObject {
    private let store: AnnotationStore
    private let pdfCoordinator: PDFViewCoordinator
    private let previewCoordinator: PreviewCoordinator
    private weak var pdfView: PDFView?

    private var overlays: [PDFPage: AnnotationPageOverlayView] = [:]
    private var toolPicker: PKToolPicker?
    private var zoomRefreshTask: Task<Void, Never>?
    private var suppressCommits = false
    private var notificationObservers: [NSObjectProtocol] = []
    private var storeSubscription: AnyCancellable?
    private(set) var isMarkupActive = false

    init(store: AnnotationStore,
         pdfCoordinator: PDFViewCoordinator,
         previewCoordinator: PreviewCoordinator) {
        self.store = store
        self.pdfCoordinator = pdfCoordinator
        self.previewCoordinator = previewCoordinator
        super.init()
        // The store can change under live overlays (Clear Annotations in the
        // sidebar/settings) — wipe any overlay whose markup was cleared.
        storeSubscription = store.$sections.sink { [weak self] sections in
            self?.syncOverlays(with: sections)
            self?.pruneFreeTextAnnotations(with: sections)
        }
    }

    deinit {
        for observer in notificationObservers {
            NotificationCenter.default.removeObserver(observer)
        }
    }

    func attach(to pdfView: PDFView) {
        self.pdfView = pdfView
        pdfView.pageOverlayViewProvider = self
        pdfCoordinator.placeNoteAction = { [weak self] in
            self?.placeNoteOnCurrentPage()
        }
        pdfCoordinator.onDocumentLoaded = { [weak self] in
            self?.rebuildFreeTextAnnotations()
        }
        for observer in notificationObservers {
            NotificationCenter.default.removeObserver(observer)
        }
        notificationObservers = [
            NotificationCenter.default.addObserver(
                forName: .PDFViewScaleChanged, object: pdfView, queue: .main
            ) { [weak self] _ in
                MainActor.assumeIsolated { self?.scheduleZoomRefresh() }
            },
            NotificationCenter.default.addObserver(
                forName: .PDFViewPageChanged, object: pdfView, queue: .main
            ) { [weak self] _ in
                MainActor.assumeIsolated { self?.anchorToolPicker() }
            },
            // Document swaps don't reliably emit willEndDisplaying for old
            // pages — drop stale overlays or the map leaks dead PDFPages.
            // (Ink is already committed continuously, so nothing is lost.)
            NotificationCenter.default.addObserver(
                forName: .PDFViewDocumentChanged, object: pdfView, queue: .main
            ) { [weak self] _ in
                MainActor.assumeIsolated { self?.dropAllOverlays() }
            },
        ]
    }

    private func dropAllOverlays() {
        for overlay in overlays.values {
            toolPicker?.removeObserver(overlay.canvas)
        }
        overlays.removeAll()
    }

    // MARK: - Markup mode

    func setMarkupActive(_ active: Bool) {
        guard active != isMarkupActive else { return }
        isMarkupActive = active
        pdfView?.isInMarkupMode = active
        for (page, overlay) in overlays {
            let live = active && isPageDrawable(page)
            overlay.isUserInteractionEnabled = live
            overlay.setLiveDrawingActive(live)
        }
        guard let picker = ensureToolPicker() else { return }
        if active {
            for overlay in overlays.values { picker.addObserver(overlay.canvas) }
            anchorToolPicker()
        } else if let anchor = overlays.values.first(where: \.canvas.isFirstResponder) {
            picker.setVisible(false, forFirstResponder: anchor.canvas)
            anchor.canvas.resignFirstResponder()
        }
    }

    /// Drops a note at the center of the page under the viewport, focused for
    /// typing. Placement-by-tap was abandoned: PDFKit's markup-mode touch
    /// routing swallowed the taps, and a direct action is more discoverable.
    private func placeNoteOnCurrentPage() {
        guard isMarkupActive, let pdfView, let page = pdfView.currentPage,
              let overlay = overlays[page], overlay.isUserInteractionEnabled else { return }
        let viewCenter = CGPoint(x: pdfView.bounds.midX, y: pdfView.bounds.midY)
        overlay.placeBox(atPDFPoint: pdfView.convert(viewCenter, to: page))
    }

    /// The tool set is vector-faithful only: each of these replays as flat
    /// vector paths in the export. Textured inks (pencil, watercolor, crayon)
    /// cannot, so the picker is restricted — which needs iPadOS 18.
    private func ensureToolPicker() -> PKToolPicker? {
        if let toolPicker { return toolPicker }
        guard #available(iOS 18.0, *) else { return nil }
        // Lasso is vector-safe too: moves/pastes bake into stroke transforms,
        // which the export replays. The inks start at the absolute thinnest
        // width PencilKit supports (probed via the tool's own clamping —
        // hardcoded guesses get silently raised) — proof annotation wants
        // fine lines.
        let minPenWidth = PKInkingTool(.pen, color: .black, width: 0).width
        let minMonolineWidth = PKInkingTool(.monoline, color: .black, width: 0).width
        let picker = PKToolPicker(toolItems: [
            PKToolPickerInkingItem(type: .pen, color: .black, width: minPenWidth, identifier: "tp.pen"),
            PKToolPickerInkingItem(type: .monoline, color: .black, width: minMonolineWidth, identifier: "tp.monoline"),
            PKToolPickerInkingItem(type: .marker),
            PKToolPickerEraserItem(type: .vector),
            PKToolPickerLassoItem(),
            PKToolPickerRulerItem(),
        ])
        picker.addObserver(self)
        toolPicker = picker
        return picker
    }

    /// The bitmap ("pixel") eraser's live preview is invisible under the
    /// zoom counter-transform — suspend it on all overlays while that tool
    /// is selected. Reading the tool off a live canvas (async, after the
    /// picker has propagated it) works for both eraser modes of the item.
    private func updateEraserSuspension() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            let tool = self.overlays.values.first?.canvas.tool
            let bitmapEraser = (tool as? PKEraserTool)?.eraserType == .bitmap
            for overlay in self.overlays.values {
                overlay.setBitmapEraserSuspension(bitmapEraser)
            }
        }
    }

    /// The picker's visibility is tied to a first responder; keep that
    /// anchored to the current page's canvas as the user scrolls.
    private func anchorToolPicker() {
        guard isMarkupActive, let pdfView,
              let picker = ensureToolPicker() else { return }
        // A placeholder page's overlay is non-interactive and can't hold
        // first-responder status — falling back keeps the picker visible
        // while scrolling across it.
        let current = pdfView.currentPage.flatMap { overlays[$0] }
            .flatMap { $0.isUserInteractionEnabled ? $0 : nil }
        guard let overlay = current ?? overlays.values.first(where: \.isUserInteractionEnabled)
        else { return }
        picker.setVisible(true, forFirstResponder: overlay.canvas)
        if !overlay.canvas.isFirstResponder {
            overlay.canvas.becomeFirstResponder()
        }
    }

    // MARK: - Store round-trip

    private func annotationKey(for page: PDFPage) -> (optionID: UUID, offset: Int)? {
        guard let document = pdfView?.document else { return nil }
        let index = document.index(for: page)
        guard index != NSNotFound else { return nil }
        return AnnotationStore.resolve(page: index, in: pdfCoordinator.sections)
    }

    /// Placeholder/stale pages must not accept markup: freezing them would
    /// lock in content the user never saw rendered.
    private func isPageDrawable(_ page: PDFPage) -> Bool {
        guard let key = annotationKey(for: page) else { return false }
        return previewCoordinator.isFragmentReady(key.optionID)
    }

    private func load(_ overlay: AnnotationPageOverlayView, for page: PDFPage) {
        guard let key = annotationKey(for: page),
              let stored = store.page(key.optionID, offset: key.offset) else { return }
        if let data = stored.drawingData, var drawing = try? PKDrawing(data: data) {
            // Migrate drawings stored in another space (legacy 1×) into the
            // canvas's ink space; re-saved in the new space on next commit.
            let storedScale = stored.drawingSpaceScale ?? 1
            if storedScale != InkSpace.scale {
                let factor = InkSpace.scale / storedScale
                drawing = drawing.transformed(using: CGAffineTransform(scaleX: factor, y: factor))
            }
            suppressCommits = true
            overlay.canvas.drawing = drawing
            suppressCommits = false
            overlay.refreshInkDisplay()
        }
        overlay.setBoxes(stored.textBoxes)
    }

    private func commitInk(_ canvas: PKCanvasView, for page: PDFPage) {
        guard let key = annotationKey(for: page) else { return }
        let drawing = canvas.drawing
        let data = drawing.strokes.isEmpty ? nil : drawing.dataRepresentation()
        if data == nil && store.page(key.optionID, offset: key.offset) == nil { return }
        store.setDrawing(data, optionID: key.optionID, pageOffset: key.offset,
                         pageSize: page.bounds(for: .mediaBox).size,
                         spaceScale: InkSpace.scale)
    }

    private func commitBoxes(_ boxes: [TextBox], for page: PDFPage) {
        guard let key = annotationKey(for: page) else { return }
        store.setTextBoxes(boxes, optionID: key.optionID, pageOffset: key.offset,
                           pageSize: page.bounds(for: .mediaBox).size)
        reconcileFreeText(boxes, on: page)
    }

    // MARK: - Native freeText display

    // Note text is displayed by PDFKit itself via in-memory freeText
    // annotations (per Apple's PDFAnnotationEditor sample): tile-rendered
    // like the page's own text, so it's sharp at any zoom with no raster
    // machinery. The sidecar store stays the source of truth; the preview
    // file on disk never contains these.
    private var freeTextAnnotations: [UUID: PDFAnnotation] = [:]

    func freeTextAnnotation(for boxID: UUID) -> PDFAnnotation? {
        freeTextAnnotations[boxID]
    }

    private func makeFreeTextAnnotation(for box: TextBox) -> PDFAnnotation {
        let annotation = SystemFontFreeTextAnnotation(
            bounds: box.rect, forType: .freeText, withProperties: nil)
        annotation.isReadOnly = true
        annotation.color = .clear
        let border = PDFBorder()
        border.lineWidth = 0
        annotation.border = border
        annotation.alignment = .left
        updateFreeTextAnnotation(annotation, from: box)
        return annotation
    }

    private func updateFreeTextAnnotation(_ annotation: PDFAnnotation, from box: TextBox) {
        annotation.bounds = box.rect
        annotation.contents = box.text
        annotation.font = box.fontName.flatMap { UIFont(name: $0, size: box.fontSize) }
            ?? .systemFont(ofSize: box.fontSize, weight: .medium)
        annotation.fontColor = UIColor(annotationHex: box.colorHex)
    }

    /// Documents are swapped wholesale on recompose; annotations die with
    /// the old document and are re-attached to the new one from the store.
    private func rebuildFreeTextAnnotations() {
        guard let document = pdfView?.document else { return }
        freeTextAnnotations = [:]
        let sections = pdfCoordinator.sections
        for pageIndex in 0..<document.pageCount {
            guard let key = AnnotationStore.resolve(page: pageIndex, in: sections),
                  let stored = store.page(key.optionID, offset: key.offset),
                  !stored.textBoxes.isEmpty,
                  let pdfPage = document.page(at: pageIndex) else { continue }
            for box in stored.textBoxes {
                let annotation = makeFreeTextAnnotation(for: box)
                pdfPage.addAnnotation(annotation)
                freeTextAnnotations[box.id] = annotation
            }
        }
    }

    private func reconcileFreeText(_ boxes: [TextBox], on pdfPage: PDFPage) {
        var stale = freeTextAnnotations.filter { $0.value.page === pdfPage }
        for box in boxes {
            if let annotation = freeTextAnnotations[box.id] {
                updateFreeTextAnnotation(annotation, from: box)
                annotation.shouldDisplay = true
                stale.removeValue(forKey: box.id)
            } else {
                let annotation = makeFreeTextAnnotation(for: box)
                pdfPage.addAnnotation(annotation)
                freeTextAnnotations[box.id] = annotation
            }
        }
        for (id, annotation) in stale {
            pdfPage.removeAnnotation(annotation)
            freeTextAnnotations.removeValue(forKey: id)
        }
    }

    /// External clears (sidebar/settings) remove boxes on pages that may not
    /// even have live overlays — sweep against the whole store.
    private func pruneFreeTextAnnotations(with sections: [UUID: SectionAnnotations]) {
        let validIDs = Set(sections.values.flatMap { section in
            section.pages.values.flatMap { $0.textBoxes.map(\.id) }
        })
        for (id, annotation) in freeTextAnnotations where !validIDs.contains(id) {
            annotation.page?.removeAnnotation(annotation)
            freeTextAnnotations.removeValue(forKey: id)
        }
    }

    private func syncOverlays(with sections: [UUID: SectionAnnotations]) {
        for (page, overlay) in overlays {
            guard overlay.hasBoxes || !overlay.canvas.drawing.strokes.isEmpty,
                  let key = annotationKey(for: page),
                  sections[key.optionID]?.pages[key.offset] == nil else { continue }
            suppressCommits = true
            overlay.canvas.drawing = PKDrawing()
            suppressCommits = false
            overlay.refreshInkDisplay()
            overlay.setBoxes([])
        }
    }

    // MARK: - Zoom sharpness

    /// Debounced: the counter-transform keeps geometry correct at any outer
    /// scale, so the re-render can wait for the gesture to settle instead of
    /// re-laying-out the canvas mid-pinch (or mid-stroke).
    private func scheduleZoomRefresh() {
        zoomRefreshTask?.cancel()
        zoomRefreshTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 150_000_000)
            guard !Task.isCancelled else { return }
            self?.refreshCanvasRenderScale()
        }
    }

    /// See AnnotationPageOverlayView.applyZoom — each overlay re-renders its
    /// ink and notes at the PDF view's current scale.
    private func refreshCanvasRenderScale() {
        guard let pdfView else { return }
        for overlay in overlays.values {
            overlay.applyZoom(pdfView.scaleFactor)
        }
    }
}

// MARK: - PDFPageOverlayViewProvider

extension AnnotationOverlayProvider: PDFPageOverlayViewProvider {
    func pdfView(_ view: PDFView, overlayViewFor page: PDFPage) -> UIView? {
        if let existing = overlays[page] { return existing }
        let overlay = AnnotationPageOverlayView(frame: .zero)
        overlay.canvas.delegate = self
        let live = isMarkupActive && isPageDrawable(page)
        overlay.isUserInteractionEnabled = live
        overlay.setLiveDrawingActive(live)
        // Match the tool already in use on other pages.
        if let liveOverlay = overlays.values.first {
            overlay.canvas.tool = liveOverlay.canvas.tool
        }
        if isMarkupActive, let picker = ensureToolPicker() {
            picker.addObserver(overlay.canvas)
        }
        overlay.annotationForBox = { [weak self] boxID in
            self?.freeTextAnnotation(for: boxID)
        }
        overlay.onBoxesChanged = { [weak self] boxes in
            self?.commitBoxes(boxes, for: page)
        }
        overlay.onEditingEnded = { [weak self] in
            self?.anchorToolPicker()
        }
        load(overlay, for: page)
        overlays[page] = overlay
        if let pdfView {
            overlay.applyZoom(pdfView.scaleFactor)
        }
        return overlay
    }

    func pdfView(_ pdfView: PDFView, willEndDisplayingOverlayView overlayView: UIView, for page: PDFPage) {
        guard let overlay = overlayView as? AnnotationPageOverlayView else { return }
        commitInk(overlay.canvas, for: page)
        toolPicker?.removeObserver(overlay.canvas)
        overlays.removeValue(forKey: page)
    }
}

// MARK: - PKToolPickerObserver

extension AnnotationOverlayProvider: PKToolPickerObserver {
    func toolPickerSelectedToolItemDidChange(_ toolPicker: PKToolPicker) {
        updateEraserSuspension()
    }

    // Also fires when the pixel/object mode flips *inside* the eraser item,
    // which doesn't change the selected item.
    func toolPickerSelectedToolDidChange(_ toolPicker: PKToolPicker) {
        updateEraserSuspension()
    }
}

// MARK: - PKCanvasViewDelegate

extension AnnotationOverlayProvider: PKCanvasViewDelegate {
    func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
        guard !suppressCommits,
              let entry = overlays.first(where: { $0.value.canvas === canvasView })
        else { return }
        entry.value.deselectBoxes()
        commitInk(canvasView, for: entry.key)
    }
}

// MARK: - SystemFontFreeTextAnnotation

/// PDFKit renders freeText annotations by font PostScript *name*; the system
/// font's name is private, so it silently falls back to Times. Draw the text
/// ourselves with the actual UIFont — via the exporter's CoreText path, so
/// screen and export stay identical. The context is in PDF page space.
private final class SystemFontFreeTextAnnotation: PDFAnnotation {
    override func draw(with box: PDFDisplayBox, in context: CGContext) {
        guard shouldDisplay, let text = contents, !text.isEmpty, let font else { return }
        AnnotationPDFExporter.drawText(
            text, font: font, color: fontColor ?? .black,
            in: bounds, context: context)
    }
}
