import CoreGraphics
import Foundation

class PDFRenderer {
    let context: CGContext
    let url: URL
    private(set) var pageCount: Int = 0

    init(url: URL, mediaBox: CGRect) {
        var box = mediaBox
        guard let ctx = CGContext(url as CFURL, mediaBox: &box, nil) else {
            fatalError("Failed to create PDF context at \(url.path)")
        }
        self.context = ctx
        self.url = url
    }

    func beginPage() {
        context.beginPDFPage(nil)
        pageCount += 1
    }

    func endPage() {
        context.endPDFPage()
    }

    func close() {
        context.closePDF()
    }

    func fillRect(_ rect: CGRect, color: CGColor) {
        context.setFillColor(color)
        context.fill(rect)
    }

    func strokeLine(from: CGPoint, to: CGPoint, color: CGColor, width: CGFloat) {
        context.setStrokeColor(color)
        context.setLineWidth(width)
        context.strokeLineSegments(between: [from, to])
    }

    func saveGState() {
        context.saveGState()
    }

    func restoreGState() {
        context.restoreGState()
    }
}
