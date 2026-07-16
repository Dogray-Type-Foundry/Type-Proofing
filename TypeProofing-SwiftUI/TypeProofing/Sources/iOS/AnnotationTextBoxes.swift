import PDFKit
import PencilKit
import ProofCore
import UIKit

// MARK: - Ink space

/// Ink is drawn in a coordinate space scaled up from page points, so
/// PencilKit's clamped minimum tool widths land proportionally thinner on
/// the page (4× space → quarter-width lines; monoline ≈ hairline). Display
/// divides the canvas zoom by this; the export bake scales the CTM down by
/// it. Tool *maximums* shrink by the same factor — the marker tops out
/// around 6 page-points.
enum InkSpace {
    static let scale: CGFloat = 4
}

// MARK: - Palette

/// Note defaults. Hex values are what the store persists and what the export
/// bake resolves.
enum TextBoxPalette {
    static let colors: [String] = ["#EB5545", "#2F6FED", "#2DA44E", "#1C1C1E"]
    static let defaultColorHex = "#EB5545"
    static let defaultSize: CGFloat = 12
    static let sizeRange: ClosedRange<CGFloat> = 4...72
    static let placementSize = CGSize(width: 220, height: 30)
}

extension UIColor {
    convenience init(annotationHex hex: String) {
        var value: UInt64 = 0
        Scanner(string: hex.hasPrefix("#") ? String(hex.dropFirst()) : hex).scanHexInt64(&value)
        self.init(
            red: CGFloat((value >> 16) & 0xFF) / 255,
            green: CGFloat((value >> 8) & 0xFF) / 255,
            blue: CGFloat(value & 0xFF) / 255,
            alpha: 1
        )
    }
}

// MARK: - AnnotationPageOverlayView

/// Per-page overlay: the PencilKit canvas, the settled-ink vector display,
/// and the note interaction layer. Note *text* is rendered by PDFKit itself
/// (freeText annotations, attached by the provider) — the views here are
/// transparent hit targets carrying selection chrome and, while editing, a
/// floating text editor. Coordinate space is the page at 1:1 in PDF points;
/// box rects convert to PDF bottom-left coordinates at the store boundary.
final class AnnotationPageOverlayView: UIView {
    let canvas = PKCanvasView()
    /// Vector display for settled ink (sharp at any zoom); the canvas is
    /// only shown while markup mode is live on this page.
    private let inkView = TiledInkView()

    /// Fired with the full box list (PDF coordinates) after any box mutation.
    var onBoxesChanged: (([TextBox]) -> Void)?
    /// Fired when box text editing ends — used to re-anchor the tool picker.
    var onEditingEnded: (() -> Void)?
    /// Resolves a box id to its live PDFKit freeText annotation.
    var annotationForBox: ((UUID) -> PDFAnnotation?)?

    private var boxViews: [TextBoxView] = []
    private var zoomScale: CGFloat = 1
    private var lastLayoutSize: CGSize = .zero

    override init(frame: CGRect) {
        super.init(frame: frame)
        inkView.inkSpaceScale = InkSpace.scale
        addSubview(inkView)
        canvas.backgroundColor = .clear
        canvas.isOpaque = false
        canvas.isScrollEnabled = false
        canvas.bouncesZoom = false
        canvas.drawingPolicy = .default
        canvas.isHidden = true
        addSubview(canvas)
        let deselectTap = UITapGestureRecognizer(target: self, action: #selector(handleBackgroundTap(_:)))
        deselectTap.cancelsTouchesInView = false
        addGestureRecognizer(deselectTap)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        inkView.frame = bounds
        layoutCanvas()
        // Only re-derive box frames when the page geometry itself changed —
        // an unconditional pass here would snap boxes back to their stored
        // rects in the middle of a drag.
        if bounds.size != lastLayoutSize {
            lastLayoutSize = bounds.size
            for view in boxViews {
                view.frame = viewRect(from: view.box.rect)
            }
        }
    }

    // MARK: Zoom sharpness (ink)

    /// The PDF view scales this whole overlay with a transform, which
    /// bitmap-stretches PencilKit's Metal layer and blurs settled ink
    /// (FB13286723; `contentScaleFactor` is ignored by that layer). The fix:
    /// PKCanvasView is a scroll view — give it the matching `zoomScale`
    /// (triggering PencilKit's real re-render) and counter-transform the
    /// view so the two scalings don't compound. Stroke coordinates stay in
    /// ink-space points throughout.
    func applyZoom(_ pdfScale: CGFloat) {
        // Cap matches the viewer's 800% zoom ceiling.
        zoomScale = min(max(pdfScale, 1), 8)
        layoutCanvas()
        for view in boxViews {
            view.setDisplayZoom(zoomScale)
        }
    }

    /// Requested zoom, capped to a GPU pixel budget (PencilKit's live "wet
    /// stroke" layer silently stops rendering when the backing store gets too
    /// large — strokes vanish while drawing) and quantized to half-steps
    /// (fractional scales misalign the wet and settled layers slightly).
    private func effectiveCanvasScale() -> CGFloat {
        guard !bitmapEraserActive else { return 1 }
        let longSide = max(bounds.width, bounds.height) * traitCollection.displayScale
        let budgetCap = longSide > 0 ? 8192 / longSide : zoomScale
        let capped = min(zoomScale, max(1, budgetCap))
        return max(1, (capped * 2).rounded(.down) / 2)
    }

    private var lastCanvasLayout: (size: CGSize, scale: CGFloat) = (.zero, 0)
    private var bitmapEraserActive = false

    /// The bitmap ("pixel") eraser's live preview doesn't render under the
    /// zoomScale counter-transform — strokes vanish while erasing. Run the
    /// canvas plain (momentarily softer at high zoom) while it's selected.
    func setBitmapEraserSuspension(_ active: Bool) {
        guard bitmapEraserActive != active else { return }
        bitmapEraserActive = active
        layoutCanvas()
    }

    private func layoutCanvas() {
        guard bounds.width > 0, bounds.height > 0 else { return }
        let scale = effectiveCanvasScale()
        // Re-running this mid-stroke shifts live ink — skip when settled.
        guard lastCanvasLayout != (bounds.size, scale) else { return }
        lastCanvasLayout = (bounds.size, scale)
        // Drawing coordinates are page points × InkSpace.scale; dividing the
        // canvas zoom by it keeps the visual size while thinning the inks.
        let canvasZoom = scale / InkSpace.scale
        canvas.transform = .identity
        canvas.bounds = CGRect(x: 0, y: 0, width: bounds.width * scale, height: bounds.height * scale)
        canvas.center = CGPoint(x: bounds.midX, y: bounds.midY)
        canvas.minimumZoomScale = canvasZoom
        canvas.maximumZoomScale = canvasZoom
        canvas.zoomScale = canvasZoom
        // Setting zoomScale can nudge contentOffset, which offsets every
        // stroke from the pencil tip — pin it back.
        canvas.setContentOffset(.zero, animated: false)
        canvas.transform = CGAffineTransform(scaleX: 1 / scale, y: 1 / scale)
        // The zoom range arms the scroll view's own pinch, which would zoom
        // just the ink instead of the page. Zooming is programmatic only.
        canvas.pinchGestureRecognizer?.isEnabled = false
    }

    /// Live canvas while marking up; tiled vector display when settled.
    func setLiveDrawingActive(_ active: Bool) {
        canvas.isHidden = !active
        inkView.isHidden = active
        if !active {
            refreshInkDisplay()
        }
    }

    func refreshInkDisplay() {
        inkView.setDrawing(canvas.drawing)
    }

    // MARK: Box lifecycle

    /// Replaces all box hit views from the store model. Called at load and on
    /// external clears only — never in response to this view's own edits.
    func setBoxes(_ boxes: [TextBox]) {
        for view in boxViews { view.removeFromSuperview() }
        boxViews = boxes.map(makeBoxView)
        for view in boxViews {
            view.frame = viewRect(from: view.box.rect)
            addSubview(view)
        }
    }

    var hasBoxes: Bool { !boxViews.isEmpty }

    func deselectBoxes() {
        for view in boxViews {
            view.deselect()
        }
    }

    /// Drops a new note centered on the given point (PDF page coordinates,
    /// bottom-left origin) and starts editing it immediately.
    func placeBox(atPDFPoint point: CGPoint) {
        let size = TextBoxPalette.placementSize
        let viewCenter = CGPoint(x: point.x, y: bounds.height - point.y)
        let origin = CGPoint(
            x: min(max(0, viewCenter.x - size.width / 2), bounds.width - size.width),
            y: min(max(0, viewCenter.y - size.height / 2), bounds.height - size.height)
        )
        let box = TextBox(
            rect: pdfRect(from: CGRect(origin: origin, size: size)),
            text: "",
            fontSize: TextBoxPalette.defaultSize,
            colorHex: TextBoxPalette.defaultColorHex
        )
        let view = makeBoxView(box)
        view.frame = viewRect(from: box.rect)
        addSubview(view)
        boxViews.append(view)
        view.beginEditing()
    }

    private func makeBoxView(_ box: TextBox) -> TextBoxView {
        let view = TextBoxView(box: box)
        view.setDisplayZoom(zoomScale)
        view.onSelected = { [weak self] boxView in
            guard let self else { return }
            for other in self.boxViews where other !== boxView {
                other.deselect()
            }
        }
        // Drags/pinches update the PDFKit annotation live; the store commit
        // happens once at gesture end (onChanged).
        view.onLiveGeometry = { [weak self] boxView in
            guard let self, let annotation = self.annotationForBox?(boxView.box.id) else { return }
            annotation.bounds = self.pdfRect(from: boxView.frame)
            annotation.font = boxView.noteFont
        }
        view.onEditingBegan = { [weak self] boxView in
            // PDFKit keeps rendering the note under the editor — hide it
            // (skip-render-while-editing) so the text isn't doubled.
            self?.annotationForBox?(boxView.box.id)?.shouldDisplay = false
        }
        view.onChanged = { [weak self] _ in self?.commitBoxes() }
        view.onDelete = { [weak self] boxView in
            guard let self else { return }
            boxView.removeFromSuperview()
            self.boxViews.removeAll { $0 === boxView }
            self.commitBoxes()
        }
        view.onEditingEnded = { [weak self] boxView in
            guard let self else { return }
            // Boxes left empty are cancelled, not saved.
            if boxView.currentText.isEmpty {
                boxView.removeFromSuperview()
                self.boxViews.removeAll { $0 === boxView }
            }
            self.commitBoxes()
            self.annotationForBox?(boxView.box.id)?.shouldDisplay = true
            self.onEditingEnded?()
        }
        return view
    }

    private func commitBoxes() {
        let boxes: [TextBox] = boxViews.map { view in
            // Sync the view's own model rect, or the next geometry-driven
            // layout pass snaps the box back to where it used to be.
            view.setRect(pdfRect(from: view.frame))
            return view.box
        }
        onBoxesChanged?(boxes.filter { !$0.text.isEmpty })
    }

    @objc private func handleBackgroundTap(_ gesture: UITapGestureRecognizer) {
        let point = gesture.location(in: self)
        guard !boxViews.contains(where: { $0.frame.insetBy(dx: -16, dy: -16).contains(point) })
        else { return }
        deselectBoxes()
    }

    // MARK: Coordinates (view top-left ↔ PDF bottom-left)

    private func viewRect(from pdfRect: CGRect) -> CGRect {
        CGRect(x: pdfRect.minX, y: bounds.height - pdfRect.maxY,
               width: pdfRect.width, height: pdfRect.height)
    }

    private func pdfRect(from viewRect: CGRect) -> CGRect {
        CGRect(x: viewRect.minX, y: bounds.height - viewRect.maxY,
               width: viewRect.width, height: viewRect.height)
    }
}

// MARK: - TextBoxView

/// A note's interaction layer: a transparent hit view over the PDFKit-
/// rendered text. Idle → tap selects (dashed outline, 4 corner handles, ✕);
/// tap again edits in a floating text view; drag moves; corner handles
/// resize (reflow, font unchanged); pinch scales the type from the size at
/// gesture start. All geometry is total-delta from gesture start (Apple's
/// PDFAnnotationEditor pattern — drift-免疫) and commits once at gesture end.
final class TextBoxView: UIView {
    enum Mode { case idle, selected, editing }

    private(set) var box: TextBox
    private(set) var mode: Mode = .idle
    var onSelected: ((TextBoxView) -> Void)?
    var onChanged: ((TextBoxView) -> Void)?
    var onDelete: ((TextBoxView) -> Void)?
    var onEditingBegan: ((TextBoxView) -> Void)?
    var onEditingEnded: ((TextBoxView) -> Void)?
    var onLiveGeometry: ((TextBoxView) -> Void)?

    var currentText: String { box.text }

    var noteFont: UIFont {
        box.fontName.flatMap { UIFont(name: $0, size: box.fontSize) }
            ?? .systemFont(ofSize: box.fontSize, weight: .medium)
    }

    private let chrome = CAShapeLayer()
    private var handles: [ResizeHandle] = []
    private let deleteBadge = UIButton(type: .custom)
    private var editor: UITextView?
    private weak var sizeLabel: UILabel?
    private weak var sizeStepper: UIStepper?
    private var displayZoom: CGFloat = 1

    // Gesture baselines (total-delta-from-start; never incremental).
    private var dragStartFrame: CGRect = .zero
    private var pinchStartFontSize: CGFloat = 0
    private var pinchStartFrame: CGRect = .zero

    init(box: TextBox) {
        self.box = box
        super.init(frame: .zero)
        backgroundColor = .clear

        chrome.fillColor = nil
        chrome.isHidden = true
        layer.addSublayer(chrome)

        deleteBadge.setImage(UIImage(systemName: "xmark.circle.fill"), for: .normal)
        deleteBadge.tintColor = .secondaryLabel
        deleteBadge.backgroundColor = .white
        deleteBadge.layer.cornerRadius = 11
        deleteBadge.bounds = CGRect(x: 0, y: 0, width: 22, height: 22)
        deleteBadge.isHidden = true
        deleteBadge.addAction(UIAction { [weak self] _ in
            guard let self else { return }
            self.onDelete?(self)
        }, for: .touchUpInside)
        addSubview(deleteBadge)

        for corner in ResizeHandle.Corner.allCases {
            let handle = ResizeHandle(corner: corner)
            handle.isHidden = true
            handle.addGestureRecognizer(
                UIPanGestureRecognizer(target: self, action: #selector(handleCornerResize(_:)))
            )
            addSubview(handle)
            handles.append(handle)
        }

        let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap))
        let pan = UIPanGestureRecognizer(target: self, action: #selector(handlePan(_:)))
        let pinch = UIPinchGestureRecognizer(target: self, action: #selector(handlePinch(_:)))
        // Fingers manage notes; the Pencil draws (taps still select).
        pan.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        pinch.allowedTouchTypes = [NSNumber(value: UITouch.TouchType.direct.rawValue)]
        for gesture in [tap, pan, pinch] {
            gesture.delegate = self
            addGestureRecognizer(gesture)
        }
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        editor?.frame = bounds
        updateChrome()
    }

    /// Selected-state chrome sits just outside the bounds.
    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        let slop: CGFloat = mode == .selected ? 16 : 0
        return bounds.insetBy(dx: -slop, dy: -slop - 12).contains(point)
    }

    func setRect(_ rect: CGRect) {
        box.rect = rect
    }

    func setDisplayZoom(_ zoom: CGFloat) {
        displayZoom = max(zoom, 0.5)
        updateChrome()
        if let editor {
            applyEditorRenderScale(editor)
        }
    }

    // MARK: State

    func beginEditing() {
        guard mode != .editing else { return }
        setMode(.editing)
    }

    func deselect() {
        if mode == .editing {
            editor?.resignFirstResponder()
        }
        setMode(.idle)
    }

    private func setMode(_ newMode: Mode) {
        guard mode != newMode else { return }
        let previous = mode
        mode = newMode
        if newMode == .editing {
            onEditingBegan?(self)
            presentEditor()
        } else if previous == .editing {
            dismissEditor()
        }
        updateChrome()
    }

    /// Capso-style chrome: dashed accent outline outset from the text, four
    /// corner handles, ✕ above. Everything divided by the PDF zoom so it
    /// stays the same size on screen at any magnification.
    private func updateChrome() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        defer { CATransaction.commit() }

        let showChrome = mode != .idle
        chrome.isHidden = !showChrome
        deleteBadge.isHidden = mode != .selected
        for handle in handles {
            handle.isHidden = mode != .selected
        }
        guard showChrome else { return }

        let inverseZoom = 1 / displayZoom
        let outset = 6 * inverseZoom
        let rect = bounds.insetBy(dx: -outset, dy: -outset)
        chrome.path = UIBezierPath(roundedRect: rect, cornerRadius: 6 * inverseZoom).cgPath
        chrome.strokeColor = tintColor.cgColor
        chrome.lineWidth = max(0.3, 1.2 * inverseZoom)
        chrome.lineDashPattern = mode == .selected
            ? [NSNumber(value: 5 * inverseZoom), NSNumber(value: 3.5 * inverseZoom)]
            : nil

        deleteBadge.center = CGPoint(x: rect.midX, y: rect.minY - 18 * inverseZoom)
        deleteBadge.transform = CGAffineTransform(scaleX: inverseZoom, y: inverseZoom)
        for handle in handles {
            handle.center = handle.corner.position(in: rect)
            handle.transform = CGAffineTransform(scaleX: inverseZoom, y: inverseZoom)
        }
    }

    // MARK: Editing (floating editor over the hidden annotation)

    private func presentEditor() {
        let textView = UITextView()
        textView.backgroundColor = .clear
        textView.isScrollEnabled = false
        textView.textContainerInset = UIEdgeInsets(top: 2, left: 0, bottom: 2, right: 0)
        textView.textContainer.lineFragmentPadding = 2
        textView.text = box.text
        textView.font = noteFont
        textView.textColor = UIColor(annotationHex: box.colorHex)
        textView.delegate = self
        textView.inputAccessoryView = makeAccessoryBar()
        textView.frame = bounds
        addSubview(textView)
        editor = textView
        applyEditorRenderScale(textView)
        textView.becomeFirstResponder()
    }

    private func dismissEditor() {
        editor?.removeFromSuperview()
        editor = nil
    }

    /// The editor is the one remaining raster-text surface under the PDF
    /// zoom transform — bump its layer scales so typing isn't blurry.
    /// (TextKit adds fragment views asynchronously; run a second pass.)
    private func applyEditorRenderScale(_ editorView: UITextView) {
        let scale = min(displayZoom, 4) * traitCollection.displayScale
        func apply(_ view: UIView) {
            if abs(view.contentScaleFactor - scale) > 0.01 {
                view.contentScaleFactor = scale
                view.layer.contentsScale = scale
                view.setNeedsDisplay()
            }
            for subview in view.subviews { apply(subview) }
        }
        apply(editorView)
        DispatchQueue.main.async { [weak editorView] in
            if let editorView { apply(editorView) }
        }
    }

    private var minBoxHeight: CGFloat {
        // Real line metrics, not fontSize — fontSize alone clips descenders.
        noteFont.lineHeight * 1.3
    }

    private func growToFitEditor() {
        guard let editor else { return }
        let fitted = editor.sizeThatFits(
            CGSize(width: frame.width, height: .greatestFiniteMagnitude)
        ).height
        if frame.height < fitted {
            frame.size.height = fitted
            onLiveGeometry?(self)
        }
    }

    // MARK: Gestures

    @objc private func handleTap() {
        switch mode {
        case .idle:
            setMode(.selected)
            onSelected?(self)
        case .selected:
            setMode(.editing)
        case .editing:
            break
        }
    }

    @objc private func handlePan(_ gesture: UIPanGestureRecognizer) {
        guard mode != .editing, let container = superview else { return }
        switch gesture.state {
        case .began:
            if mode == .idle {
                setMode(.selected)
                onSelected?(self)
            }
            dragStartFrame = frame
        case .changed:
            let translation = gesture.translation(in: container)
            var origin = CGPoint(x: dragStartFrame.origin.x + translation.x,
                                 y: dragStartFrame.origin.y + translation.y)
            origin.x = min(max(-frame.width / 2, origin.x), container.bounds.width - frame.width / 2)
            origin.y = min(max(-frame.height / 2, origin.y), container.bounds.height - frame.height / 2)
            frame.origin = origin
            onLiveGeometry?(self)
        case .ended, .cancelled:
            onChanged?(self)
        default:
            break
        }
    }

    /// Pinch scales the type: fontSize = size-at-gesture-start × scale
    /// (baseline capture — no compounding drift), box scaled with it about
    /// its center so the text never re-wraps mid-gesture.
    @objc private func handlePinch(_ gesture: UIPinchGestureRecognizer) {
        guard mode == .selected else { return }
        switch gesture.state {
        case .began:
            pinchStartFontSize = box.fontSize
            pinchStartFrame = frame
        case .changed:
            let range = TextBoxPalette.sizeRange
            let target = min(max(pinchStartFontSize * gesture.scale, range.lowerBound), range.upperBound)
            let factor = target / pinchStartFontSize
            box.fontSize = target
            frame = CGRect(
                x: pinchStartFrame.midX - pinchStartFrame.width * factor / 2,
                y: pinchStartFrame.midY - pinchStartFrame.height * factor / 2,
                width: pinchStartFrame.width * factor,
                height: pinchStartFrame.height * factor
            )
            updateChrome()
            onLiveGeometry?(self)
        case .ended, .cancelled:
            onChanged?(self)
        default:
            break
        }
    }

    /// Corner drag resizes the box (text reflows; font size unchanged),
    /// anchored so the opposite corner stays put.
    @objc private func handleCornerResize(_ gesture: UIPanGestureRecognizer) {
        guard let handle = gesture.view as? ResizeHandle, let container = superview else { return }
        switch gesture.state {
        case .began:
            dragStartFrame = frame
        case .changed:
            let translation = gesture.translation(in: container)
            var newFrame = dragStartFrame
            if handle.corner.isLeft {
                let dx = min(translation.x, newFrame.width - 60)
                newFrame.origin.x += dx
                newFrame.size.width -= dx
            } else {
                newFrame.size.width = max(60, newFrame.width + translation.x)
            }
            if handle.corner.isTop {
                let dy = min(translation.y, newFrame.height - minBoxHeight)
                newFrame.origin.y += dy
                newFrame.size.height -= dy
            } else {
                newFrame.size.height = max(minBoxHeight, newFrame.height + translation.y)
            }
            frame = newFrame
            onLiveGeometry?(self)
        case .ended, .cancelled:
            onChanged?(self)
        default:
            break
        }
    }

    // MARK: Accessory palette

    private func makeAccessoryBar() -> UIToolbar {
        let bar = UIToolbar(frame: CGRect(x: 0, y: 0, width: 520, height: 44))

        let label = UILabel()
        label.font = .monospacedDigitSystemFont(ofSize: 13, weight: .regular)
        label.text = "\(Int(box.fontSize)) pt"
        sizeLabel = label

        let stepper = UIStepper()
        stepper.minimumValue = TextBoxPalette.sizeRange.lowerBound
        stepper.maximumValue = TextBoxPalette.sizeRange.upperBound
        stepper.stepValue = 1
        stepper.value = box.fontSize
        stepper.addTarget(self, action: #selector(sizeStepped(_:)), for: .valueChanged)
        sizeStepper = stepper

        var items: [UIBarButtonItem] = [
            UIBarButtonItem(customView: label),
            UIBarButtonItem(customView: stepper),
            UIBarButtonItem(title: "Font", primaryAction: UIAction { [weak self] _ in
                self?.presentFontPicker()
            }),
            .flexibleSpace(),
        ]
        for hex in TextBoxPalette.colors {
            let swatch = UIImage(systemName: "circle.fill")?
                .withTintColor(UIColor(annotationHex: hex), renderingMode: .alwaysOriginal)
            items.append(UIBarButtonItem(primaryAction: UIAction(image: swatch) { [weak self] _ in
                guard let self else { return }
                self.box.colorHex = hex
                self.applyStyleToEditor()
            }))
        }
        items.append(.flexibleSpace())
        let trash = UIBarButtonItem(systemItem: .trash, primaryAction: UIAction { [weak self] _ in
            guard let self else { return }
            self.editor?.resignFirstResponder()
            self.onDelete?(self)
        })
        trash.tintColor = .systemRed
        items.append(trash)
        items.append(UIBarButtonItem(systemItem: .done, primaryAction: UIAction { [weak self] _ in
            self?.editor?.resignFirstResponder()
        }))
        bar.items = items
        return bar
    }

    @objc private func sizeStepped(_ stepper: UIStepper) {
        box.fontSize = stepper.value
        applyStyleToEditor()
    }

    private func applyStyleToEditor() {
        editor?.font = noteFont
        editor?.textColor = UIColor(annotationHex: box.colorHex)
        sizeLabel?.text = "\(Int(box.fontSize)) pt"
        sizeStepper?.value = box.fontSize
        growToFitEditor()
        if let editor {
            applyEditorRenderScale(editor)
        }
    }

    private func presentFontPicker() {
        var configuration = UIFontPickerViewController.Configuration()
        configuration.includeFaces = true
        let picker = UIFontPickerViewController(configuration: configuration)
        picker.delegate = self
        var presenter = window?.rootViewController
        while let presented = presenter?.presentedViewController {
            presenter = presented
        }
        presenter?.present(picker, animated: true)
    }
}

extension TextBoxView: UIGestureRecognizerDelegate {
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {
        // Chrome (handles, ✕) owns its touches; the box gestures must not
        // also fire while dragging a handle.
        var view = touch.view
        while let current = view, current !== self {
            if current is ResizeHandle || current === deleteBadge {
                return false
            }
            view = current.superview
        }
        return true
    }
}

extension TextBoxView: UITextViewDelegate {
    func textViewDidChange(_ textView: UITextView) {
        growToFitEditor()
        applyEditorRenderScale(textView)
    }

    func textViewDidEndEditing(_ textView: UITextView) {
        box.text = textView.text.trimmingCharacters(in: .whitespacesAndNewlines)
        setMode(.selected)
        onEditingEnded?(self)
    }
}

extension TextBoxView: UIFontPickerViewControllerDelegate {
    func fontPickerViewControllerDidPickFont(_ viewController: UIFontPickerViewController) {
        if let descriptor = viewController.selectedFontDescriptor {
            box.fontName = UIFont(descriptor: descriptor, size: box.fontSize).fontName
            applyStyleToEditor()
        }
        viewController.dismiss(animated: true)
    }
}

// MARK: - ResizeHandle

private final class ResizeHandle: UIView {
    enum Corner: CaseIterable {
        case topLeft, topRight, bottomLeft, bottomRight

        var isTop: Bool { self == .topLeft || self == .topRight }
        var isLeft: Bool { self == .topLeft || self == .bottomLeft }

        func position(in rect: CGRect) -> CGPoint {
            CGPoint(x: isLeft ? rect.minX : rect.maxX,
                    y: isTop ? rect.minY : rect.maxY)
        }
    }

    let corner: Corner

    init(corner: Corner) {
        self.corner = corner
        super.init(frame: CGRect(x: 0, y: 0, width: 44, height: 44))
        let dot = UIView(frame: CGRect(x: 17, y: 17, width: 10, height: 10))
        dot.backgroundColor = .white
        dot.layer.cornerRadius = 5
        dot.layer.borderWidth = 1.5
        dot.layer.borderColor = UIColor.tintColor.cgColor
        dot.isUserInteractionEnabled = false
        addSubview(dot)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }
}
