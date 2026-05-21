import CoreGraphics
import Foundation

struct BaselineGrid {

    static func draw(in rect: CGRect, ascent: CGFloat, lineHeight: CGFloat, context: CGContext) {
        guard lineHeight > 2 else { return }

        context.saveGState()
        context.setStrokeColor(CGColor(red: 0.8, green: 0.85, blue: 1.0, alpha: 0.5))
        context.setLineWidth(0.5)

        var y = rect.maxY - ascent
        while y >= rect.minY {
            context.move(to: CGPoint(x: rect.minX, y: y))
            context.addLine(to: CGPoint(x: rect.maxX, y: y))
            y -= lineHeight
        }
        context.strokePath()
        context.restoreGState()
    }
}
