import CoreGraphics
import CoreText
import Foundation

struct FilteredCharacterSetHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let params = resolveParams(from: context, defaultCols: 1)
        let categories = CharacterCategorizer.proofCategories(from: context.cat)
        let autoSize = settingsValue(makeSettingsKey("autoSize"), default: false, from: context.proofSettings)

        let sections = enabledCategorySections(categories: categories, settings: context.proofSettings)
        for (label, charset) in sections {
            if charset.isEmpty { continue }

            let fontSize: CGFloat
            if autoSize {
                fontSize = AutoSizing.fitToPage(
                    text: charset,
                    fontPath: context.indFont,
                    pageFormat: context.pageFormat,
                    otFeatures: params.otFeatures.isEmpty ? nil : params.otFeatures,
                    variations: context.axisValues
                )
            } else {
                fontSize = params.fontSize
            }
            let tracking = fontSize / 1.5
            let sectionName = "Character Set - \(label) - \(Int(fontSize))pt"

            guard let font = FontLoader.makeFont(
                path: context.indFont,
                size: fontSize,
                features: params.otFeatures.isEmpty ? nil : params.otFeatures,
                variations: context.axisValues
            ) else {
                context.diagnostics.error("Failed to load font",
                                          fontPath: context.indFont, proofName: proofName)
                continue
            }

            let attrString = TextRenderer.makeAttributedString(
                text: charset,
                font: font,
                fontSize: fontSize,
                alignment: .center,
                tracking: tracking,
                lineHeight: nil,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: false
            )

            drawContent(
                attrString,
                sectionName: sectionName,
                columns: 1,
                direction: .ltr,
                otFeatures: params.otFeatures,
                tracking: tracking,
                context: context,
                renderer: renderer
            )
        }
    }

}

struct SpacingProofHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let params = resolveParams(from: context, defaultCols: 2)
        let categories = CharacterCategorizer.proofCategories(from: context.cat)

        let sections = enabledCategorySections(categories: categories, settings: context.proofSettings)
        for (label, charset) in sections {
            if charset.isEmpty { continue }

            let spacingText = CharacterCategorizer.generateSpacingString(characterSet: charset)
            if spacingText.isEmpty { continue }

            let sectionName = "Spacing - \(label) - \(Int(params.fontSize))pt"

            var features = params.otFeatures
            if features.isEmpty {
                features = ["liga": false, "kern": false]
            }

            guard let font = FontLoader.makeFont(
                path: context.indFont,
                size: params.fontSize,
                features: features,
                variations: context.axisValues
            ) else {
                context.diagnostics.error("Failed to load font",
                                          fontPath: context.indFont, proofName: proofName)
                continue
            }

            let kernDisabled = features["kern"] == false
            let attrString = TextRenderer.makeAttributedString(
                text: spacingText,
                font: font,
                fontSize: params.fontSize,
                alignment: .left,
                tracking: params.tracking,
                lineHeight: nil,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: kernDisabled
            )

            drawContent(
                attrString,
                sectionName: sectionName,
                columns: params.columns,
                direction: .ltr,
                otFeatures: features,
                tracking: params.tracking,
                context: context,
                renderer: renderer,
                columnGap: params.columnGap
            )
        }
    }

}
