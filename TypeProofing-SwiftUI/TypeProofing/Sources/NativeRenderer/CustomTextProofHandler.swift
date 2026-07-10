import CoreGraphics
import CoreText
import Foundation

struct CustomTextProofHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let customTextKey = makeSettingsKey("customText")
        guard let customText = context.proofSettings[customTextKey] as? String,
              !customText.isEmpty else {
            context.diagnostics.error("No custom text provided", proofName: proofName)
            return
        }

        let generateOnceKey = makeSettingsKey("generateOnce")
        let generateOnce = context.proofSettings[generateOnceKey] as? Bool ?? false

        if generateOnce {
            if context.runState.generatedOnce.contains(proofName) {
                return
            }
            context.runState.generatedOnce.insert(proofName)
        }

        let defaultFontPath: String
        let defaultAxisValues: [String: Double]?
        if generateOnce {
            let path = context.proofSettings[makeSettingsKey("defaultFontPath")] as? String ?? ""
            defaultFontPath = path.isEmpty ? context.indFont : path
            defaultAxisValues = context.proofSettings[makeSettingsKey("defaultFontAxisDict")] as? [String: Double]
        } else {
            defaultFontPath = context.indFont
            defaultAxisValues = context.axisValues
        }

        let params = resolveParams(from: context, defaultCols: 1)
        let markupKey = makeSettingsKey("markupEnabled")
        let markupEnabled = context.proofSettings[markupKey] as? Bool ?? false

        let sectionName = "\(proofName) - \(Int(params.fontSize))pt"

        if markupEnabled {
            let tokens = MarkupParser.tokenize(customText)
            let config = MarkupRenderer.RenderConfig(
                fontPath: defaultFontPath,
                fontSize: params.fontSize,
                alignment: params.alignment,
                tracking: params.tracking,
                lineHeight: params.lineHeight,
                otFeatures: params.otFeatures.isEmpty ? nil : params.otFeatures,
                variations: defaultAxisValues,
                allFontPaths: context.allFontPaths
            )
            let pageSegments = MarkupRenderer.buildPages(tokens: tokens, config: config)
            drawMarkupPages(pageSegments, sectionName: sectionName, params: params, context: context, renderer: renderer)
        } else {
            guard let font = FontLoader.makeFont(
                path: defaultFontPath,
                size: params.fontSize,
                features: params.otFeatures.isEmpty ? nil : params.otFeatures,
                variations: defaultAxisValues,
                hangingPunctuation: params.hangingPunctuation
            ) else {
                context.diagnostics.error("Failed to load font",
                                          fontPath: defaultFontPath, proofName: proofName)
                return
            }

            let kernDisabled = params.otFeatures["kern"] == false
            let attrString = TextRenderer.makeAttributedString(
                text: customText,
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
                language: "en"
            )

            let direction: TextDirection
            switch params.direction {
            case "ltr": direction = .ltr
            case "rtl": direction = .rtl
            default: direction = .ltr
            }

            drawContent(
                attrString,
                sectionName: sectionName,
                columns: params.columns,
                direction: direction,
                otFeatures: params.otFeatures,
                tracking: params.tracking,
                context: context,
                renderer: renderer,
                columnGap: params.columnGap
            )
        }
    }

    private func drawMarkupPages(
        _ segments: MarkupRenderer.PageSegments,
        sectionName: String,
        params: ProofParams,
        context: ProofContext,
        renderer: PDFRenderer
    ) {
        let pageSize = PageLayout.pageDimensions[context.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let contentRect = PageLayout.contentRect(pageFormat: context.pageFormat)
        let fontName = URL(fileURLWithPath: context.indFont).deletingPathExtension().lastPathComponent
            .components(separatedBy: "-").first ?? "Unknown"

        for page in segments.pages {
            let colRects = PageLayout.columnRects(contentRect: contentRect, columns: params.columns, direction: .ltr)
            var colIdx = 0
            var pageOpen = false

            func openPage() {
                renderer.beginPage()
                pageOpen = true
                if context.showFooter {
                    PageLayout.drawFooter(
                        context: renderer.context,
                        pageSize: pageSize,
                        title: sectionName,
                        fontName: fontName,
                        otFeatures: params.otFeatures.isEmpty ? nil : params.otFeatures,
                        tracking: params.tracking,
                        pageNumber: renderer.pageCount,
                        showPageNumber: true
                    )
                }
            }

            // Each segment starts in the next free column (colIdx), which is
            // exactly the #colbreak() semantics; the page is only begun/ended
            // here, never mid-segment.
            for segment in page {
                if segment.length == 0 { continue }

                var overflow: NSAttributedString? = segment
                while overflow != nil {
                    if colIdx >= colRects.count {
                        renderer.endPage()
                        pageOpen = false
                        colIdx = 0
                    }
                    if !pageOpen { openPage() }
                    let lengthBefore = overflow!.length
                    overflow = TextRenderer.drawText(overflow!, in: colRects[colIdx], context: renderer.context)
                    // A column pass that consumes no characters would loop forever.
                    if let remaining = overflow, remaining.length >= lengthBefore {
                        context.diagnostics.error("Text does not fit the column layout — output truncated",
                                                  proofName: proofName)
                        overflow = nil
                    }
                    colIdx += 1
                }
            }
            if pageOpen {
                renderer.endPage()
            }
        }
    }
}
