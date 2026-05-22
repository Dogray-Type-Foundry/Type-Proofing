import CoreGraphics
import CoreText
import Foundation

struct ArCharacterSetHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let params = resolveParams(from: context, defaultCols: 1)
        let contextualString = generateArabicContextualForms(cat: context.cat)
        if contextualString.isEmpty {
            context.diagnostics.warning("Font does not contain Arabic characters",
                                        fontPath: context.indFont, proofName: proofName)
            return
        }

        guard let font = FontLoader.makeFont(
            path: context.indFont,
            size: params.fontSize,
            features: params.otFeatures.isEmpty ? nil : params.otFeatures,
            variations: context.axisValues
        ) else {
            context.diagnostics.error("Failed to load font",
                                      fontPath: context.indFont, proofName: proofName)
            return
        }

        let attrString = TextRenderer.makeAttributedString(
            text: contextualString,
            font: font,
            fontSize: params.fontSize,
            alignment: .center,
            tracking: 0,
            lineHeight: nil,
            foregroundColor: CGColor(gray: 0, alpha: 1),
            kernDisabled: false
        )

        let sectionName = "\(proofName) - \(Int(params.fontSize))pt"

        drawContent(
            attrString,
            sectionName: sectionName,
            columns: 1,
            direction: .rtl,
            otFeatures: params.otFeatures,
            tracking: 0,
            context: context,
            renderer: renderer
        )
    }

    private func generateArabicContextualForms(cat: CharacterCategories) -> String {
        let arabicChars = cat.arabTyped
        if arabicChars.isEmpty { return "" }

        let dualJoin = Set(cat.arfaDualJoin)
        let rightJoin = Set(cat.arfaRightJoin)
        var result = ""

        for char in arabicChars {
            if char == "ء" {
                result += "\(char) "
            } else if dualJoin.contains(char) {
                result += "\(char) \(char)\(char)\(char) "
            } else if rightJoin.contains(char) {
                result += "\(char) ب\(char) "
            }
        }

        return result
    }
}
