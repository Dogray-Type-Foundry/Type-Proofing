import CoreGraphics
import CoreText
import Foundation
import TPNative

struct SubstitutionBridge {

    struct Entry {
        let kind: String
        let inputGlyphIDs: [UInt16]
        let outputGlyphIDs: [UInt16]
        let inputText: String
        let outputNames: [String]
        let backtrackText: String
        let lookaheadText: String
    }

    struct Feature {
        let tag: String
        let entries: [Entry]
        let outputGlyphs: [String]
    }

    static func getSubstitutions(fontPath: String) -> [Feature] {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: fontPath)) else { return [] }
        return data.withUnsafeBytes { buffer -> [Feature] in
            guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return [] }
            guard let jsonPtr = tp_get_substitutions_json(ptr, UInt(buffer.count)) else { return [] }
            defer { wsv_free_string(jsonPtr) }
            let jsonStr = String(cString: jsonPtr)
            guard let jsonData = jsonStr.data(using: .utf8),
                  let array = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] else { return [] }

            return array.compactMap { dict -> Feature? in
                guard let tag = dict["tag"] as? String else { return nil }
                let glyphs = dict["output_glyphs"] as? [String] ?? []

                let rawEntries = dict["entries"] as? [[String: Any]] ?? []
                let entries: [Entry] = rawEntries.compactMap { eDict in
                    let kind = eDict["kind"] as? String ?? "unknown"
                    let inputIDs = (eDict["input"] as? [Any])?.compactMap { ($0 as? NSNumber)?.uint16Value } ?? []
                    let outputIDs = (eDict["output"] as? [Any])?.compactMap { ($0 as? NSNumber)?.uint16Value } ?? []
                    let inputText = eDict["input_text"] as? String ?? ""
                    let outputNames = eDict["output_names"] as? [String] ?? []
                    let backtrackText = eDict["backtrack_text"] as? String ?? ""
                    let lookaheadText = eDict["lookahead_text"] as? String ?? ""
                    if inputIDs.isEmpty && outputIDs.isEmpty { return nil }
                    return Entry(kind: kind, inputGlyphIDs: inputIDs, outputGlyphIDs: outputIDs,
                                 inputText: inputText, outputNames: outputNames,
                                 backtrackText: backtrackText, lookaheadText: lookaheadText)
                }

                if entries.isEmpty && glyphs.isEmpty { return nil }
                return Feature(tag: tag, entries: entries, outputGlyphs: glyphs)
            }
        }
    }
}

struct SubstitutionOverviewHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let features = SubstitutionBridge.getSubstitutions(fontPath: context.indFont)
        if features.isEmpty {
            context.diagnostics.warning("Font has no GSUB substitutions",
                                        fontPath: context.indFont, proofName: proofName)
            return
        }

        let params = resolveParams(from: context, defaultCols: 2)
        let pageSize = PageLayout.pageDimensions[context.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let contentRect = PageLayout.contentRect(pageFormat: context.pageFormat)
        let colRects = PageLayout.columnRects(contentRect: contentRect, columns: params.columns, direction: .ltr)
        let fontName = URL(fileURLWithPath: context.indFont).deletingPathExtension().lastPathComponent
            .components(separatedBy: "-").first ?? "Unknown"

        let fontSize = params.fontSize
        let rowHeight = max(fontSize * 1.35, 58)
        let headerHeight = max(fontSize * 0.38, 16)
        let labelSize = max(8, fontSize * 0.22)
        let annotationSize = max(6, fontSize * 0.18)
        let annotationHeight = max(annotationSize * 1.25, 10)
        let arrowSize = max(15, fontSize * 0.48)
        let arrowWidth = max(fontSize * 0.65, 24)
        let glyphGap = max(fontSize * 0.12, 6)

        var colIdx = 0
        var yTop = colRects[0].maxY

        let suffix = axisLabel(from: context)

        guard let baseFont = FontLoader.makeFont(
            path: context.indFont,
            size: fontSize,
            features: nil,
            variations: context.axisValues
        ) else {
            context.diagnostics.error("Failed to load font",
                                      fontPath: context.indFont, proofName: proofName)
            return
        }

        let headerFont = CTFontCreateWithName("Courier" as CFString, labelSize, nil)
        let annotFont = CTFontCreateWithName("Courier" as CFString, annotationSize, nil)
        let arrowFont = CTFontCreateWithName("Courier" as CFString, arrowSize, nil)
        let black = CGColor(gray: 0, alpha: 1)
        let gray = CGColor(gray: 0.4, alpha: 1)

        func newPage() {
            if renderer.pageCount > 0 { renderer.endPage() }
            renderer.beginPage()
            var sectionName = "\(proofName) - \(Int(fontSize))pt"
            if !suffix.isEmpty { sectionName += " - \(suffix)" }
            PageLayout.drawFooter(
                context: renderer.context,
                pageSize: pageSize,
                title: sectionName,
                fontName: fontName,
                otFeatures: nil,
                tracking: 0,
                pageNumber: renderer.pageCount,
                showPageNumber: true
            )
            colIdx = 0
            yTop = colRects[0].maxY
        }

        func advanceColumn() {
            if colIdx + 1 < colRects.count {
                colIdx += 1
                yTop = colRects[colIdx].maxY
            } else {
                newPage()
            }
        }

        func ensureSpace(_ height: CGFloat) {
            if yTop - height < colRects[colIdx].minY {
                advanceColumn()
            }
        }

        newPage()

        for feature in features {
            let eligibleEntries = feature.entries.filter { !$0.inputGlyphIDs.isEmpty && !$0.outputGlyphIDs.isEmpty }
            if eligibleEntries.isEmpty { continue }

            ensureSpace(headerHeight)
            let col = colRects[colIdx]

            let headerStr = TextRenderer.makeAttributedString(
                text: feature.tag,
                font: headerFont,
                fontSize: labelSize,
                alignment: .left,
                tracking: 0,
                lineHeight: headerHeight,
                foregroundColor: gray
            )
            let headerRect = CGRect(x: col.minX, y: yTop - headerHeight, width: col.width, height: headerHeight + 4)
            TextRenderer.drawText(headerStr, in: headerRect, context: renderer.context)
            yTop -= headerHeight

            for entry in eligibleEntries {
                ensureSpace(rowHeight)
                let col = colRects[colIdx]
                yTop -= rowHeight
                let glyphY = yTop + annotationHeight
                let glyphH = rowHeight - annotationHeight

                let sourceWidth = FontLoader.measureGlyphsByID(entry.inputGlyphIDs, font: baseFont)
                let clampedSourceWidth = min(max(sourceWidth, fontSize * 0.6), col.width * 0.42)
                let resultWidth = col.width - clampedSourceWidth - arrowWidth - glyphGap * 2

                let sourceRect = CGRect(x: col.minX, y: glyphY, width: clampedSourceWidth, height: glyphH)
                FontLoader.drawGlyphsByID(entry.inputGlyphIDs, font: baseFont, in: sourceRect, context: renderer.context)

                let arrowStr = TextRenderer.makeAttributedString(
                    text: "\u{2192}",
                    font: arrowFont,
                    fontSize: arrowSize,
                    alignment: .center,
                    tracking: 0,
                    lineHeight: glyphH,
                    foregroundColor: gray
                )
                let arrowX = col.minX + clampedSourceWidth + glyphGap
                let arrowRect = CGRect(x: arrowX, y: glyphY, width: arrowWidth, height: glyphH + 4)
                TextRenderer.drawText(arrowStr, in: arrowRect, context: renderer.context)

                let featureFont = FontLoader.makeFont(
                    path: context.indFont,
                    size: fontSize,
                    features: [feature.tag: true],
                    variations: context.axisValues
                ) ?? baseFont
                let resultX = arrowX + arrowWidth + glyphGap
                let resultRect = CGRect(x: resultX, y: glyphY, width: resultWidth, height: glyphH)
                FontLoader.drawGlyphsByID(entry.outputGlyphIDs, font: featureFont, in: resultRect, context: renderer.context)

                let inputNames = entry.inputGlyphIDs.map { gid -> String in
                    FontLoader.glyphName(for: gid, font: baseFont) ?? "gid\(gid)"
                }
                let outputNames = entry.outputNames.isEmpty
                    ? entry.outputGlyphIDs.map { "gid\($0)" }
                    : entry.outputNames
                let annotText = "\(inputNames.joined(separator: " ")) -> \(outputNames.joined(separator: " "))"
                let annotStr = TextRenderer.makeAttributedString(
                    text: annotText,
                    font: annotFont,
                    fontSize: annotationSize,
                    alignment: .left,
                    tracking: 0,
                    lineHeight: nil,
                    foregroundColor: gray
                )
                let annotRect = CGRect(x: col.minX, y: yTop, width: col.width, height: annotationHeight + 4)
                TextRenderer.drawText(annotStr, in: annotRect, context: renderer.context)
            }
        }

        renderer.endPage()
    }
}
