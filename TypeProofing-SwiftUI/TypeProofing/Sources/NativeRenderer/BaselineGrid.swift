import AppKit
import CoreGraphics
import CoreText
import Foundation

struct BaselineGrid {

    private static let baselineColor = CGColor(red: 0, green: 1, blue: 1, alpha: 1)
    private static let columnColor = CGColor(red: 1, green: 0, blue: 1, alpha: 1)
    private static let strokeWidth: CGFloat = 0.5
    private static let indexFontSize: CGFloat = 5

    static func drawBaselines(
        in rect: CGRect,
        positions: [CGFloat],
        context: CGContext
    ) {
        guard !positions.isEmpty else { return }

        context.saveGState()
        context.setStrokeColor(baselineColor)
        context.setLineWidth(strokeWidth)

        for y in positions {
            context.move(to: CGPoint(x: rect.minX, y: y))
            context.addLine(to: CGPoint(x: rect.maxX, y: y))
        }
        context.strokePath()

        let font = CTFontCreateWithName("Helvetica" as CFString, indexFontSize, nil)
        for (i, y) in positions.enumerated() {
            let label = NSAttributedString(
                string: "\(i)",
                attributes: [.font: font, .foregroundColor: baselineColor]
            )
            let line = CTLineCreateWithAttributedString(label)
            context.textPosition = CGPoint(x: rect.minX + 2, y: y + 2)
            CTLineDraw(line, context)
        }

        context.restoreGState()
    }

    static func drawColumns(rects: [CGRect], context: CGContext) {
        context.saveGState()
        context.setStrokeColor(columnColor)
        context.setLineWidth(strokeWidth)

        for rect in rects {
            context.stroke(rect)
        }

        let font = CTFontCreateWithName("Helvetica" as CFString, indexFontSize, nil)
        for (i, rect) in rects.enumerated() {
            let label = NSAttributedString(
                string: "\(i)",
                attributes: [.font: font, .foregroundColor: columnColor]
            )
            let line = CTLineCreateWithAttributedString(label)
            context.textPosition = CGPoint(x: rect.minX + 2, y: rect.minY + 2)
            CTLineDraw(line, context)
        }

        context.restoreGState()
    }

    static func extendPositions(
        from baselines: [CGFloat],
        lineHeight: CGFloat,
        toBottom bottomY: CGFloat
    ) -> [CGFloat] {
        guard let first = baselines.first, lineHeight > 2 else { return baselines }

        var positions: [CGFloat] = []
        var y = first
        while y >= bottomY {
            positions.append(y)
            y -= lineHeight
        }
        return positions
    }
}
