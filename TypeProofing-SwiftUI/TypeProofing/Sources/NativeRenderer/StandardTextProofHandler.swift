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

        // Manual style pairing: user-defined weighted mixes rendered once per
        // document instead of the automatic per-font partner detection. Only
        // Style Pairing proof instances ever write a pairingMode setting.
        let pairingMode = settingsValue(makeSettingsKey("pairingMode"), default: "automatic", from: context.proofSettings) as String
        if pairingMode == "manual" {
            generateManualPairings(context: context, renderer: renderer, characterSet: characterSet)
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
                params: params,
                context: context,
                forceWordsiv: config.forceWordsiv,
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
        var footerNote: String?
        if config.mixedStyles {
            guard let pairing = StylePairing.detectPairing(
                fontPath: context.indFont,
                axisValues: context.axisValues,
                allFontPaths: context.allFontPaths,
                allAxisValues: context.allAxisValues
            ) else {
                context.diagnostics.debug("No style pairing found for mixed-style proof",
                                          fontPath: context.indFont, proofName: proofName)
                return
            }
            footerNote = "Pairing: \(StylePairing.describe(pairing: pairing))"
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
                variations: context.axisValues,
                hangingPunctuation: params.hangingPunctuation
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
                kernDisabled: kernDisabled,
                paragraphIndent: params.paragraphIndent,
                paragraphSpace: params.paragraphSpace,
                hyphenation: params.hyphenation,
                language: config.language ?? "en"
            )
        }

        let direction: TextDirection
        switch params.direction {
        case "ltr": direction = .ltr
        case "rtl": direction = .rtl
        default: direction = (config.language == "ar" || config.language == "fa") ? .rtl : .ltr
        }
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
            lineHeight: params.lineHeight,
            columnGap: params.columnGap,
            footerNote: footerNote
        )
    }

    private func generateManualPairings(context: ProofContext, renderer: PDFRenderer, characterSet: String) {
        // Pairings can span fonts, so render once per document — the outer
        // per-font/per-axis loop would otherwise repeat them.
        if context.runState.generatedOnce.contains(proofName) { return }
        context.runState.generatedOnce.insert(proofName)

        let json = settingsValue(makeSettingsKey("manualPairings"), default: "", from: context.proofSettings) as String
        let pairings = StylePairing.decodeManualPairings(json: json)
        if pairings.isEmpty {
            context.diagnostics.error("No pairings configured — add a pairing in the proof settings or switch to Automatic",
                                      proofName: proofName)
            return
        }

        let params = resolveParams(
            from: context,
            defaultCols: ProofRegistry.entry(forKey: proofKey)?.defaultCols ?? 2,
            defaultParas: config.defaultParagraphs
        )

        let textContent = TextGeneration.generateTextProofString(
            characterSet: characterSet,
            params: params,
            context: context,
            forceWordsiv: config.forceWordsiv,
            language: config.language,
            hoeflerStyle: config.hoeflerStyle
        )
        if textContent.isEmpty {
            context.diagnostics.debug("Text generation produced empty content",
                                      fontPath: context.indFont, proofName: proofName)
            return
        }

        let direction: TextDirection = params.direction == "rtl" ? .rtl : .ltr

        for pairing in pairings {
            var resolved: [(font: CTFont, weight: Double)] = []
            var labels: [String] = []
            for style in pairing.styles {
                guard let font = FontLoader.makeFont(
                    path: style.fontPath,
                    size: params.fontSize,
                    features: params.otFeatures.isEmpty ? nil : params.otFeatures,
                    variations: style.coordinates
                ) else {
                    context.diagnostics.warning("Could not load style '\(style.label)' for pairing",
                                                fontPath: style.fontPath, proofName: proofName)
                    continue
                }
                resolved.append((font: font, weight: style.weight))
                labels.append(style.label)
            }
            if resolved.count < 2 {
                context.diagnostics.warning("Pairing skipped — needs at least 2 available styles",
                                            proofName: proofName)
                continue
            }

            let attrString = StylePairing.buildWeightedMixedAttributedString(
                text: textContent,
                styles: resolved,
                fontSize: params.fontSize,
                alignment: params.alignment,
                tracking: params.tracking,
                lineHeight: params.lineHeight,
                otFeatures: params.otFeatures.isEmpty ? nil : params.otFeatures
            )

            let totalWeight = resolved.map(\.weight).reduce(0, +)
            let noteParts = zip(labels, resolved).map { label, style -> String in
                let share = totalWeight > 0 ? style.weight / totalWeight : 1.0 / Double(resolved.count)
                return "\(label) \(Int((share * 100).rounded()))%"
            }
            drawContent(
                attrString,
                sectionName: "\(proofName) - \(Int(params.fontSize))pt",
                columns: params.columns,
                direction: direction,
                otFeatures: params.otFeatures,
                tracking: params.tracking,
                context: context,
                renderer: renderer,
                lineHeight: params.lineHeight,
                columnGap: params.columnGap,
                footerNote: "Pairing: " + noteParts.joined(separator: " + ")
            )
        }
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
