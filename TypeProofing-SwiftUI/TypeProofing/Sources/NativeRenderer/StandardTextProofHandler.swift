import CoreGraphics
import CoreText
import Foundation

struct StandardTextProofHandler: ProofHandler {
    let proofName: String
    let proofKey: String
    let config: TextProofConfig

    init(proofName: String, proofKey: String) {
        self.proofName = proofName
        self.proofKey = proofKey
        self.config = ProofRegistry.entry(forKey: proofKey)?.textConfig ?? TextProofConfig()
    }

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let characterSet = context.cat.resolveCharacterSet(forKey: config.characterSetKey)
        if characterSet.isEmpty && config.language != nil {
            context.diagnostics.debug("No character set for language '\(config.language!)'",
                                      fontPath: context.indFont, proofName: proofName)
            return
        }

        if config.mixedStyles
            && StylePairing.shouldSkipFont(fontPath: context.indFont, allFontPaths: context.allFontPaths) {
            return
        }

        let params = resolveParams(
            from: context,
            defaultCols: ProofRegistry.entry(forKey: proofKey)?.defaultCols ?? 2,
            defaultParas: config.defaultParagraphs
        )

        let textContent: String
        if config.accents > 0 {
            textContent = generateAccentedText(
                characterSet: characterSet,
                accents: config.accents,
                fullCharacterSet: context.fullCharacterSet,
                isSmall: params.fontSize <= 12
            )
        } else if let injectKey = config.injectTextKey,
                  let injected = PremadeTexts.resolveInjectText(forKey: injectKey) {
            textContent = injected
        } else {
            textContent = TextGeneration.generateTextProofString(
                characterSet: characterSet,
                paragraphs: params.paragraphs,
                forceWordsiv: config.forceWordsiv,
                cat: context.cat,
                fullCharacterSet: context.fullCharacterSet,
                language: config.language,
                hoeflerStyle: config.hoeflerStyle
            )
        }

        if textContent.isEmpty {
            context.diagnostics.debug("Text generation produced empty content",
                                      fontPath: context.indFont, proofName: proofName)
            return
        }

        let attrString: NSAttributedString
        if config.mixedStyles {
            guard let pairing = StylePairing.detectPairing(
                fontPath: context.indFont,
                axisValues: context.axisValues,
                allFontPaths: context.allFontPaths
            ) else {
                context.diagnostics.debug("No style pairing found for mixed-style proof",
                                          fontPath: context.indFont, proofName: proofName)
                return
            }
            attrString = StylePairing.buildMixedStyleAttributedString(
                text: textContent,
                fontPath: context.indFont,
                fontSize: params.fontSize,
                alignment: params.alignment,
                tracking: params.tracking,
                lineHeight: params.lineHeight,
                baseVariations: context.axisValues,
                pairing: pairing,
                otFeatures: params.otFeatures.isEmpty ? nil : params.otFeatures
            )
        } else {
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

            let kernDisabled = params.otFeatures["kern"] == false
            attrString = TextRenderer.makeAttributedString(
                text: textContent,
                font: font,
                fontSize: params.fontSize,
                alignment: params.alignment,
                tracking: params.tracking,
                lineHeight: params.lineHeight,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: kernDisabled
            )
        }

        let direction: TextDirection = (config.language == "ar" || config.language == "fa") ? .rtl : .ltr
        let sectionName = "\(proofName) - \(Int(params.fontSize))pt"

        drawContent(
            attrString,
            sectionName: sectionName,
            columns: params.columns,
            direction: direction,
            otFeatures: params.otFeatures,
            tracking: params.tracking,
            context: context,
            renderer: renderer,
            lineHeight: params.lineHeight
        )
    }

    private func generateAccentedText(
        characterSet: String,
        accents: Int,
        fullCharacterSet: String,
        isSmall: Bool
    ) -> String {
        let normalizedFull = fullCharacterSet.lowercased().precomposedStringWithCanonicalMapping
        let fullLower = Set(normalizedFull)
        var result = ""

        for char in characterSet {
            var available = PremadeTexts.accentedWords(for: char).filter { word in
                word.precomposedStringWithCanonicalMapping.allSatisfy { fullLower.contains($0) }
            }
            let count = min(accents, available.count)
            if count == 0 { continue }

            result += " |\(char)| "
            available.shuffle()
            let selected = available.prefix(count)
            for word in selected {
                if char.isUppercase {
                    result += word.replacingOccurrences(of: "ß", with: "ẞ").uppercased() + " "
                } else {
                    result += word + " "
                }
            }
            if isSmall { result += "\n" }
        }
        return result
    }
}
