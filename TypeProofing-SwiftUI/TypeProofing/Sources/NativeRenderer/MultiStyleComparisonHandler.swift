import CoreGraphics
import CoreText
import Foundation
import TPNative

struct MultiStyleComparisonHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    private static var generatedInstances: Set<String> = []

    static func resetGenerated() {
        generatedInstances = []
    }

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        if MultiStyleComparisonHandler.generatedInstances.contains(proofName) {
            context.diagnostics.debug("Already generated, skipping duplicate",
                                      proofName: proofName)
            return
        }
        MultiStyleComparisonHandler.generatedInstances.insert(proofName)

        let params = resolveParams(from: context, defaultCols: 1)

        let allFonts = context.allFontPaths.isEmpty ? [context.indFont] : context.allFontPaths
        let mergedCat = buildMergedCategories(fontPaths: allFonts)
        let categories = CharacterCategorizer.proofCategories(from: mergedCat)

        let sections = enabledSections(categories: categories, settings: context.proofSettings)
        let customText = settingsValue(makeSettingsKey("customText"), default: "", from: context.proofSettings) as String

        var textGroups: [(String, String)] = []
        for (label, charset) in sections where !charset.isEmpty {
            textGroups.append((label, charset))
        }
        if !customText.isEmpty {
            let lines = customText.components(separatedBy: .newlines).filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
            for (i, line) in lines.enumerated() {
                let label = lines.count > 1 ? "Custom Text \(i + 1)" : "Custom Text"
                textGroups.append((label, line))
            }
        }
        if textGroups.isEmpty {
            context.diagnostics.error(
                "No text categories enabled and no custom text provided",
                proofName: proofName)
            return
        }

        let styles = collectStyles(allFonts: allFonts, context: context)
        if styles.count < 2 {
            let reason = allFonts.count == 1
                ? "Requires at least 2 styles — load a variable font or multiple fonts"
                : "Requires at least 2 enabled styles"
            context.diagnostics.error(reason, proofName: proofName,
                                      details: ["stylesFound": "\(styles.count)", "fontsLoaded": "\(allFonts.count)"])
            return
        }

        let fontSize = params.fontSize
        let showFallback = settingsValue(makeSettingsKey("showFallback"), default: false, from: context.proofSettings) as Bool

        for (groupLabel, groupText) in textGroups {
            let attrString = buildMultiStyleString(
                text: groupText,
                styles: styles,
                fontSize: fontSize,
                tracking: params.tracking,
                alignment: params.alignment,
                lineHeight: params.lineHeight,
                otFeatures: params.otFeatures,
                showFallback: showFallback
            )

            let sectionName = "\(proofName) - \(groupLabel) - \(Int(fontSize))pt"
            drawContent(
                attrString,
                sectionName: sectionName,
                columns: params.columns,
                direction: .ltr,
                otFeatures: params.otFeatures,
                tracking: params.tracking,
                context: context,
                renderer: renderer,
                lineHeight: params.lineHeight
            )
        }
    }

    private func buildMultiStyleString(
        text: String,
        styles: [StyleEntry],
        fontSize: CGFloat,
        tracking: CGFloat,
        alignment: CTTextAlignment,
        lineHeight: CGFloat?,
        otFeatures: [String: Bool],
        showFallback: Bool
    ) -> NSAttributedString {
        let result = NSMutableAttributedString()

        for (i, style) in styles.enumerated() {
            guard let font = FontLoader.makeFont(
                path: style.fontPath,
                size: fontSize,
                features: otFeatures.isEmpty ? nil : otFeatures,
                variations: style.variations
            ) else { continue }

            let renderedText: String
            if showFallback {
                renderedText = text
            } else {
                renderedText = Self.filterSupportedCharacters(text, font: font)
            }

            if renderedText.isEmpty { continue }

            let line = TextRenderer.makeAttributedString(
                text: renderedText,
                font: font,
                fontSize: fontSize,
                alignment: alignment,
                tracking: tracking,
                lineHeight: lineHeight,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: false
            )
            result.append(line)

            if i < styles.count - 1 {
                let newline = NSAttributedString(string: "\n")
                result.append(newline)
            }
        }

        return result
    }

    private static func filterSupportedCharacters(_ text: String, font: CTFont) -> String {
        String(text.filter { char in
            let s = String(char)
            let utf16 = Array(s.utf16)
            var glyphs = [CGGlyph](repeating: 0, count: utf16.count)
            return CTFontGetGlyphsForCharacters(font, utf16, &glyphs, utf16.count)
        })
    }

    private struct StyleEntry {
        let fontPath: String
        let variations: [String: Double]?
        let label: String
    }

    private func buildMergedCategories(fontPaths: [String]) -> CharacterCategories {
        var merged = CharacterCategories()
        for fontPath in fontPaths {
            guard let fontData = try? Data(contentsOf: URL(fileURLWithPath: fontPath)) else { continue }
            let charset = fontData.withUnsafeBytes { buffer -> String in
                guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return "" }
                guard let charsetPtr = tp_get_charset(ptr, UInt(buffer.count)) else { return "" }
                defer { wsv_free_string(charsetPtr) }
                return String(cString: charsetPtr)
            }
            let cat = CharacterCategorizer.categorize(charset: charset)
            merged.uniLu = String(Set(merged.uniLu + cat.uniLu).sorted())
            merged.uniLl = String(Set(merged.uniLl + cat.uniLl).sorted())
            merged.uniLuBase = String(Set(merged.uniLuBase + cat.uniLuBase).sorted())
            merged.uniLlBase = String(Set(merged.uniLlBase + cat.uniLlBase).sorted())
            merged.uniNd = String(Set(merged.uniNd + cat.uniNd).sorted())
            merged.uniNo = String(Set(merged.uniNo + cat.uniNo).sorted())
            merged.uniPo = String(Set(merged.uniPo + cat.uniPo).sorted())
            merged.uniPc = String(Set(merged.uniPc + cat.uniPc).sorted())
            merged.uniPd = String(Set(merged.uniPd + cat.uniPd).sorted())
            merged.uniPs = String(Set(merged.uniPs + cat.uniPs).sorted())
            merged.uniPe = String(Set(merged.uniPe + cat.uniPe).sorted())
            merged.uniPi = String(Set(merged.uniPi + cat.uniPi).sorted())
            merged.uniPf = String(Set(merged.uniPf + cat.uniPf).sorted())
            merged.uniSm = String(Set(merged.uniSm + cat.uniSm).sorted())
            merged.uniSc = String(Set(merged.uniSc + cat.uniSc).sorted())
            merged.uniSo = String(Set(merged.uniSo + cat.uniSo).sorted())
            merged.accentedPlus = String(Set(merged.accentedPlus + cat.accentedPlus).sorted())
        }
        return merged
    }

    private func collectStyles(allFonts: [String], context: ProofContext) -> [StyleEntry] {
        var styles: [StyleEntry] = []
        var styleIndex = 0

        for fontPath in allFonts {
            guard let fontData = try? Data(contentsOf: URL(fileURLWithPath: fontPath)) else {
                if isStyleEnabled(styleIndex, settings: context.proofSettings) {
                    let displayName = URL(fileURLWithPath: fontPath).deletingPathExtension().lastPathComponent
                    styles.append(StyleEntry(fontPath: fontPath, variations: nil, label: displayName))
                }
                styleIndex += 1
                continue
            }

            let axesJSON: String? = fontData.withUnsafeBytes { buffer in
                guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return nil }
                guard let jsonPtr = tp_get_axes_json(ptr, UInt(buffer.count)) else { return nil }
                defer { wsv_free_string(jsonPtr) }
                return String(cString: jsonPtr)
            }

            var axisArrays: [(tag: String, values: [Double])] = []
            if let json = axesJSON,
               let jsonData = json.data(using: .utf8),
               let axes = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] {
                for axis in axes {
                    guard let tag = axis["tag"] as? String,
                          let values = axis["values"] as? [Double],
                          !values.isEmpty else { continue }
                    axisArrays.append((tag, values))
                }
            }

            if axisArrays.isEmpty {
                if let userValues = context.axisValuesByFont[fontPath], !userValues.isEmpty {
                    for (tag, values) in userValues.sorted(by: { $0.key < $1.key }) where values.count > 1 {
                        axisArrays.append((tag, values))
                    }
                }
            }

            if axisArrays.isEmpty {
                if isStyleEnabled(styleIndex, settings: context.proofSettings) {
                    let displayName = URL(fileURLWithPath: fontPath).deletingPathExtension().lastPathComponent
                    styles.append(StyleEntry(fontPath: fontPath, variations: nil, label: displayName))
                }
                styleIndex += 1
            } else {
                var combinations: [[(String, Double)]] = [[]]
                for (tag, values) in axisArrays {
                    var next: [[(String, Double)]] = []
                    for combo in combinations {
                        for val in values {
                            next.append(combo + [(tag, val)])
                        }
                    }
                    combinations = next
                }

                let familyName = URL(fileURLWithPath: fontPath).deletingPathExtension().lastPathComponent
                    .components(separatedBy: "-").first ?? "Unknown"
                for combo in combinations {
                    if isStyleEnabled(styleIndex, settings: context.proofSettings) {
                        let coords = Dictionary(uniqueKeysWithValues: combo)
                        let label = "\(familyName) \u{2014} " + combo.map { "\($0.0)=\(Int($0.1))" }.joined(separator: " ")
                        styles.append(StyleEntry(fontPath: fontPath, variations: coords, label: label))
                    }
                    styleIndex += 1
                }
            }
        }

        return styles
    }

    private func isStyleEnabled(_ index: Int, settings: [String: Any]) -> Bool {
        let key = makeSettingsKey("style", String(index))
        return settings[key] as? Bool ?? true
    }

    private func enabledSections(
        categories: CharacterCategorizer.ProofCategories,
        settings: [String: Any]
    ) -> [(String, String)] {
        let mapping: [(String, String, String)] = [
            ("uppercase_base", "Uppercase", categories.uppercaseBase),
            ("lowercase_base", "Lowercase", categories.lowercaseBase),
            ("numbers_symbols", "Numbers & Symbols", categories.numbersSymbols),
            ("punctuation", "Punctuation", categories.punctuation),
            ("accented", "Accented", categories.accented),
        ]

        let defaults: [String: Bool] = [
            "uppercase_base": true,
            "lowercase_base": true,
            "numbers_symbols": true,
            "punctuation": true,
            "accented": false,
        ]

        return mapping.compactMap { key, label, charset in
            let settingsKey = makeSettingsKey("cat", key)
            let enabled = settings[settingsKey] as? Bool ?? defaults[key] ?? true
            return enabled ? (label, charset) : nil
        }
    }
}
