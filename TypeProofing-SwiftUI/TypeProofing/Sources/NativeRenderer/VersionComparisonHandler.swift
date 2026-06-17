import CoreGraphics
import CoreText
import Foundation

/// Overlays the same text rendered in an "old" (baseline) font and the loaded
/// "new" font, line for line, so version differences are visible.
///
/// The baseline font is laid out normally with a framesetter (so columns,
/// alignment, line height, gaps and indents all behave like any text proof).
/// For each baseline line, the identical substring is then stamped in the new
/// font at the same line origin. Because the line breaks come from the
/// baseline, lines never reflow against each other, while spacing and kerning
/// drift *within* a line so the differences show. Old is drawn in red and new
/// in blue with a multiply blend: coincident outlines read near-black, and any
/// divergence shows as a red or blue fringe.
struct VersionComparisonHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    private static let oldColor = CGColor(red: 0.85, green: 0.10, blue: 0.10, alpha: 1)
    private static let newColor = CGColor(red: 0.10, green: 0.45, blue: 0.95, alpha: 1)

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let baselinePath = settingsValue(makeSettingsKey("baselineFontPath"),
                                         default: "", from: context.proofSettings) as String
        guard !baselinePath.isEmpty else {
            context.diagnostics.error(
                "No baseline font chosen — pick an old-version font to compare against",
                proofName: proofName)
            return
        }
        guard FileManager.default.fileExists(atPath: baselinePath) else {
            context.diagnostics.error("Baseline font file not found", proofName: proofName,
                                      details: ["path": baselinePath])
            return
        }

        let params = resolveParams(from: context, defaultCols: 1)
        let fontSize = params.fontSize
        let features = params.otFeatures.isEmpty ? nil : params.otFeatures

        guard let newFont = FontLoader.makeFont(
            path: context.indFont, size: fontSize, features: features,
            variations: context.axisValues, hangingPunctuation: params.hangingPunctuation) else {
            context.diagnostics.error("Could not load the loaded font", proofName: proofName)
            return
        }
        guard let oldFont = FontLoader.makeFont(
            path: baselinePath, size: fontSize, features: features,
            variations: nil, hangingPunctuation: params.hangingPunctuation) else {
            context.diagnostics.error("Could not load the baseline font", proofName: proofName)
            return
        }

        let text = resolveText(params: params, context: context)
        guard !text.isEmpty else {
            context.diagnostics.debug("No text to render", proofName: proofName)
            return
        }

        let direction: TextDirection
        switch params.direction {
        case "ltr": direction = .ltr
        case "rtl": direction = .rtl
        default: direction = Self.isRTL(text) ? .rtl : .ltr
        }

        let kernDisabled = params.otFeatures["kern"] == false
        let oldAttr = TextRenderer.makeAttributedString(
            text: text, font: oldFont, fontSize: fontSize, alignment: params.alignment,
            tracking: params.tracking, lineHeight: params.lineHeight,
            foregroundColor: Self.oldColor, kernDisabled: kernDisabled,
            paragraphIndent: params.paragraphIndent, paragraphSpace: params.paragraphSpace,
            hyphenation: params.hyphenation)

        drawOverlay(oldAttr: oldAttr, newFont: newFont, params: params, direction: direction,
                    kernDisabled: kernDisabled, baselinePath: baselinePath,
                    context: context, renderer: renderer)
    }

    /// Custom text if the user provided any, otherwise auto-generated text.
    private func resolveText(params: ProofParams, context: ProofContext) -> String {
        let custom = settingsValue(makeSettingsKey("customText"), default: "", from: context.proofSettings) as String
        if !custom.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return custom
        }

        let config = ProofRegistry.entry(forKey: proofKey)?.textConfig
        let charsetKey = config?.characterSetKey ?? "base_letters"
        let characterSet = context.cat.resolveCharacterSet(forKey: charsetKey)
        return TextGeneration.generateTextProofString(
            characterSet: characterSet,
            paragraphs: params.paragraphs,
            forceWordsiv: config?.forceWordsiv ?? true,
            cat: context.cat,
            fullCharacterSet: context.fullCharacterSet,
            language: config?.language,
            hoeflerStyle: config?.hoeflerStyle ?? false,
            generativeLanguage: params.generativeLanguage,
            wordDiversity: params.wordDiversity,
            vocabularySize: params.vocabularySize,
            minWordLength: params.minWordLength,
            maxWordLength: params.maxWordLength,
            biasChars: params.biasChars,
            biasStrength: params.biasStrength,
            wordsPerSentence: params.wordsPerSentence,
            sentencesPerParagraph: params.sentencesPerParagraph
        )
    }

    private func drawOverlay(
        oldAttr: NSAttributedString, newFont: CTFont, params: ProofParams,
        direction: TextDirection, kernDisabled: Bool, baselinePath: String,
        context: ProofContext, renderer: PDFRenderer
    ) {
        let pageSize = PageLayout.pageDimensions[context.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let contentRect = PageLayout.contentRect(pageFormat: context.pageFormat)
        let colRects = PageLayout.columnRects(
            contentRect: contentRect, columns: params.columns,
            gutter: params.columnGap, direction: direction)

        let fontName = URL(fileURLWithPath: context.indFont).deletingPathExtension()
            .lastPathComponent.components(separatedBy: "-").first ?? "Unknown"
        let baselineName = URL(fileURLWithPath: baselinePath).deletingPathExtension().lastPathComponent
        let suffix = axisLabel(from: context)
        let fullTitle = suffix.isEmpty ? proofName : "\(proofName) - \(suffix)"
        let footerNote = "old (red): \(baselineName)  |  new (blue): \(fontName)"

        var overflow: NSAttributedString? = oldAttr
        while overflow != nil {
            let lengthBefore = overflow?.length ?? 0
            renderer.beginPage()
            PageLayout.drawFooter(
                context: renderer.context, pageSize: pageSize, title: fullTitle,
                fontName: fontName, otFeatures: params.otFeatures.isEmpty ? nil : params.otFeatures,
                tracking: params.tracking, pageNumber: renderer.pageCount,
                showPageNumber: true, lineHeight: params.lineHeight, footerNote: footerNote)

            for colRect in colRects {
                guard let remaining = overflow else { break }
                overflow = drawColumn(remaining, in: colRect, newFont: newFont, params: params,
                                      kernDisabled: kernDisabled, context: renderer.context)
            }

            renderer.endPage()

            if let remaining = overflow, remaining.length >= lengthBefore {
                context.diagnostics.error("Text does not fit the column layout — output truncated",
                                          proofName: proofName)
                break
            }
        }
    }

    /// Draws one column of baseline (red) text and overlays the new font (blue)
    /// per line. Returns the text that didn't fit, or nil if everything fit.
    private func drawColumn(
        _ attr: NSAttributedString, in colRect: CGRect, newFont: CTFont,
        params: ProofParams, kernDisabled: Bool, context: CGContext
    ) -> NSAttributedString? {
        let framesetter = CTFramesetterCreateWithAttributedString(attr)
        let path = CGMutablePath()
        path.addRect(colRect)
        let frame = CTFramesetterCreateFrame(framesetter, CFRange(location: 0, length: 0), path, nil)

        context.saveGState()
        context.setBlendMode(.multiply)

        CTFrameDraw(frame, context)

        let lines = CTFrameGetLines(frame)
        let lineCount = CFArrayGetCount(lines)
        if lineCount > 0 {
            var origins = [CGPoint](repeating: .zero, count: lineCount)
            CTFrameGetLineOrigins(frame, CFRange(location: 0, length: lineCount), &origins)
            let fullString = attr.string as NSString

            for i in 0..<lineCount {
                let line = unsafeBitCast(CFArrayGetValueAtIndex(lines, i), to: CTLine.self)
                let range = CTLineGetStringRange(line)
                guard range.length > 0 else { continue }
                let substring = fullString.substring(
                    with: NSRange(location: range.location, length: range.length))

                let newAttr = TextRenderer.makeAttributedString(
                    text: substring, font: newFont, fontSize: params.fontSize, alignment: .left,
                    tracking: params.tracking, lineHeight: nil,
                    foregroundColor: Self.newColor, kernDisabled: kernDisabled)
                let newLine = CTLineCreateWithAttributedString(newAttr)

                context.textPosition = CGPoint(
                    x: colRect.minX + origins[i].x, y: colRect.minY + origins[i].y)
                CTLineDraw(newLine, context)
            }
        }

        context.restoreGState()

        let visible = CTFrameGetVisibleStringRange(frame)
        let drawn = visible.location + visible.length
        if drawn < attr.length {
            return attr.attributedSubstring(
                from: NSRange(location: drawn, length: attr.length - drawn))
        }
        return nil
    }

    private static func isRTL(_ text: String) -> Bool {
        for scalar in text.unicodeScalars {
            let v = scalar.value
            if (0x0600...0x06FF).contains(v) || (0x0750...0x077F).contains(v)
                || (0x08A0...0x08FF).contains(v) || (0xFB50...0xFDFF).contains(v)
                || (0xFE70...0xFEFF).contains(v) {
                return true
            }
        }
        return false
    }
}
