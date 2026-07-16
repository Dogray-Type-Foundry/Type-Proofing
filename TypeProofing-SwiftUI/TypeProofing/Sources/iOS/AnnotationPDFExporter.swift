import CoreText
import CoreTransferable
import PencilKit
import ProofCore
import UIKit
import UniformTypeIdentifiers

/// ShareLink payload: bakes the markup into a fresh copy of the proof PDF
/// when (and only when) the user actually exports. The on-disk preview is
/// never modified.
struct AnnotatedProofExport: Transferable {
    let sourcePath: String
    let annotations: [UUID: SectionAnnotations]
    let sections: [ProofSection]

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(exportedContentType: .pdf) { export in
            let url = try AnnotationPDFExporter.bake(
                source: URL(fileURLWithPath: export.sourcePath),
                annotations: export.annotations,
                sections: export.sections
            )
            return SentTransferredFile(url, allowAccessingOriginalFile: true)
        }
    }
}

/// Bakes the annotation store into a PDF as flat page content: ink strokes
/// replayed as vector CGPaths (never `PKDrawing.image()` — that's a bitmap),
/// text boxes as real CoreText text. Recipients can't move or delete the
/// markup; that is intended.
enum AnnotationPDFExporter {

    static func bake(
        source: URL,
        annotations: [UUID: SectionAnnotations],
        sections: [ProofSection]
    ) throws -> URL {
        guard let document = CGPDFDocument(source as CFURL), document.numberOfPages > 0 else {
            throw CocoaError(.fileReadCorruptFile)
        }
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("Annotated Proof.pdf")
        try? FileManager.default.removeItem(at: outputURL)
        guard let context = CGContext(outputURL as CFURL, mediaBox: nil, nil) else {
            throw CocoaError(.fileWriteUnknown)
        }

        for pageNumber in 1...document.numberOfPages {
            guard let page = document.page(at: pageNumber) else { continue }
            var mediaBox = page.getBoxRect(.mediaBox)
            context.beginPage(mediaBox: &mediaBox)
            context.drawPDFPage(page)
            if let key = AnnotationStore.resolve(page: pageNumber - 1, in: sections),
               let markup = annotations[key.optionID]?.pages[key.offset] {
                draw(markup, in: context, pageHeight: mediaBox.height)
            }
            context.endPage()
        }
        context.closePDF()
        return outputURL
    }

    // MARK: - Page markup

    private static func draw(_ markup: PageAnnotations, in context: CGContext, pageHeight: CGFloat) {
        if let data = markup.drawingData, let drawing = try? PKDrawing(data: data) {
            context.saveGState()
            // PencilKit canvas space is top-left/y-down; PDF is bottom-left/y-up.
            context.translateBy(x: 0, y: pageHeight)
            context.scaleBy(x: 1, y: -1)
            // Drawing coordinates are page points × drawingSpaceScale.
            let inkScale = markup.drawingSpaceScale ?? 1
            context.scaleBy(x: 1 / inkScale, y: 1 / inkScale)
            for stroke in drawing.strokes {
                InkStrokeRenderer.draw(stroke, in: context)
            }
            context.restoreGState()
        }
        for box in markup.textBoxes {
            draw(box, in: context)
        }
    }

    // MARK: - Text boxes

    private static func draw(_ box: TextBox, in context: CGContext) {
        guard !box.text.isEmpty else { return }
        let font = box.fontName.flatMap { UIFont(name: $0, size: box.fontSize) }
            ?? .systemFont(ofSize: box.fontSize, weight: .medium)
        let attributed = NSAttributedString(string: box.text, attributes: [
            .font: font,
            .foregroundColor: UIColor(annotationHex: box.colorHex),
        ])
        let framesetter = CTFramesetterCreateWithAttributedString(attributed)
        // Mirror the on-screen UITextView insets (container 2pt + fragment
        // padding 5pt horizontally, 4pt vertically).
        let rect = box.rect.insetBy(dx: 7, dy: 4)
        let frame = CTFramesetterCreateFrame(
            framesetter, CFRange(location: 0, length: 0),
            CGPath(rect: rect, transform: nil), nil
        )
        context.saveGState()
        context.textMatrix = .identity
        CTFrameDraw(frame, context)
        context.restoreGState()
    }
}
