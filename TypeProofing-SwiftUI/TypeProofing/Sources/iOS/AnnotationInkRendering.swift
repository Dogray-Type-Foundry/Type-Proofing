import PencilKit
import UIKit

// MARK: - InkStrokeRenderer

/// Replays PKStrokes as flat vector CGPaths. Shared by the PDF export bake
/// and the on-screen tiled display — both must never rasterize
/// (`PKDrawing.image()` is a bitmap).
enum InkStrokeRenderer {
    static func draw(_ stroke: PKStroke, in context: CGContext) {
        let points = Array(stroke.path.interpolatedPoints(by: .distance(0.75)))
        guard let first = points.first else { return }
        // Resolve dynamic ink colors to their light-mode appearance — proof
        // pages are white regardless of the annotating device's theme.
        let color = stroke.ink.color
            .resolvedColor(with: UITraitCollection(userInterfaceStyle: .light))
            .cgColor

        context.saveGState()
        context.concatenate(stroke.transform)
        if let mask = stroke.mask {
            context.addPath(mask.cgPath)
            context.clip()
        }
        context.setAlpha(first.opacity)
        context.setLineCap(.round)
        context.setLineJoin(.round)
        switch stroke.ink.inkType {
        case .pen:
            // Pressure-variable width: stroke short polyline runs of
            // near-constant width. Round joins survive arbitrarily tight
            // turns and round caps can't cancel under winding rules — the
            // offset-outline-polygon approach produced spikes on hairpins
            // and notched end caps.
            context.setStrokeColor(color)
            context.setFillColor(color)   // single-point dots fill an ellipse
            let translucent = first.opacity < 0.99
            if translucent {
                // Runs overlap at their shared points; group them so the
                // overlaps don't double-darken.
                context.beginTransparencyLayer(auxiliaryInfo: nil)
            }
            strokeVariableWidthRuns(points, in: context)
            if translucent {
                context.endTransparencyLayer()
            }
        default:
            // Monoline and marker are uniform-width single paths.
            context.setStrokeColor(color)
            context.setLineWidth(max(0.25, first.size.width))
            let path = CGMutablePath()
            path.move(to: first.location)
            for point in points.dropFirst() {
                path.addLine(to: point.location)
            }
            context.addPath(path)
            context.strokePath()
        }
        context.restoreGState()
    }

    /// Splits the interpolated centerline into runs whose width stays within
    /// ~15% of the run's starting width, and strokes each run as one round-
    /// capped polyline. Consecutive runs share their boundary point, so the
    /// caps blend into a continuous variable-width stroke.
    private static func strokeVariableWidthRuns(_ points: [PKStrokePoint], in context: CGContext) {
        guard points.count > 1 else {
            if let point = points.first {
                context.fillEllipse(in: CGRect(
                    x: point.location.x - point.size.width / 2,
                    y: point.location.y - point.size.height / 2,
                    width: point.size.width,
                    height: point.size.height
                ))
            }
            return
        }
        var runStart = 0
        var runWidth = points[0].size.width
        for index in 1..<points.count {
            let width = points[index].size.width
            let drifted = abs(width - runWidth) > max(0.1, runWidth * 0.15)
            guard drifted || index == points.count - 1 else { continue }
            let path = CGMutablePath()
            path.move(to: points[runStart].location)
            for pointIndex in (runStart + 1)...index {
                path.addLine(to: points[pointIndex].location)
            }
            context.setLineWidth(max(0.25, runWidth))
            context.addPath(path)
            context.strokePath()
            runStart = index
            runWidth = width
        }
    }
}

// MARK: - TiledInkView

/// Settled-ink display: draws the PKDrawing as vector paths through a
/// CATiledLayer — the same mechanism PDFKit uses for page text — so strokes
/// stay sharp at any zoom with no GPU texture ceiling. Shown whenever markup
/// mode is off; the live PKCanvasView takes over while drawing.
final class TiledInkView: UIView {
    override class var layerClass: AnyClass { CATiledLayer.self }

    /// Drawing-space points per page point (InkSpace.scale of the content).
    var inkSpaceScale: CGFloat = 1

    private let lock = NSLock()
    private var strokes: [PKStroke] = []

    override init(frame: CGRect) {
        super.init(frame: frame)
        isOpaque = false
        isUserInteractionEnabled = false
        if let tiled = layer as? CATiledLayer {
            tiled.tileSize = CGSize(width: 512, height: 512)
            tiled.levelsOfDetail = 2
            tiled.levelsOfDetailBias = 5
        }
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    func setDrawing(_ drawing: PKDrawing) {
        lock.lock()
        strokes = drawing.strokes
        lock.unlock()
        layer.setNeedsDisplay()
    }

    // Called per tile, potentially on several background threads.
    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        lock.lock()
        let snapshot = strokes
        let scale = inkSpaceScale
        lock.unlock()
        guard !snapshot.isEmpty else { return }
        context.scaleBy(x: 1 / scale, y: 1 / scale)
        for stroke in snapshot {
            InkStrokeRenderer.draw(stroke, in: context)
        }
    }
}
