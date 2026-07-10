import AppKit
import CoreGraphics
import CoreText
import Foundation

struct CharacterCategories {
    var uniLu: String = ""
    var uniLl: String = ""
    var uniLo: String = ""
    var uniLuBase: String = ""
    var uniLlBase: String = ""
    var uniNd: String = ""
    var uniNo: String = ""
    var uniPo: String = ""
    var uniPc: String = ""
    var uniPd: String = ""
    var uniPs: String = ""
    var uniPe: String = ""
    var uniPi: String = ""
    var uniPf: String = ""
    var uniSm: String = ""
    var uniSc: String = ""
    var uniSo: String = ""
    var uppercaseOnly: Bool = false
    var lowercaseOnly: Bool = false
    var accentedPlus: String = ""
    var ar: String = ""
    var fa: String = ""
    var arabTyped: String = ""
    var arfaDualJoin: String = ""
    var arfaRightJoin: String = ""

    func resolveCharacterSet(forKey key: String) -> String {
        switch key {
        case "base_letters": return uniLu + uniLl
        case "accented_plus": return accentedPlus
        case "arabic": return ar
        case "farsi": return fa.isEmpty ? ar : fa
        default: return ""
        }
    }
}

final class DiagnosticCollector: @unchecked Sendable {
    private var events: [DiagnosticEvent] = []
    var debugMode: Bool = false

    func emit(level: String, category: String, message: String,
              fontPath: String? = nil, proofName: String? = nil,
              details: [String: String] = [:]) {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withTime, .withColonSeparatorInTime]
        events.append(DiagnosticEvent(
            level: level, category: category, message: message,
            fontPath: fontPath, proofName: proofName,
            details: details, timestamp: formatter.string(from: Date())
        ))
    }

    func error(_ message: String, category: String = "generation",
               fontPath: String? = nil, proofName: String? = nil,
               details: [String: String] = [:]) {
        emit(level: "error", category: category, message: message,
             fontPath: fontPath, proofName: proofName, details: details)
    }

    func warning(_ message: String, category: String = "generation",
                 fontPath: String? = nil, proofName: String? = nil,
                 details: [String: String] = [:]) {
        emit(level: "warning", category: category, message: message,
             fontPath: fontPath, proofName: proofName, details: details)
    }

    func debug(_ message: String, category: String = "generation",
               fontPath: String? = nil, proofName: String? = nil,
               details: [String: String] = [:]) {
        guard debugMode else { return }
        emit(level: "debug", category: category, message: message,
             fontPath: fontPath, proofName: proofName, details: details)
    }

    func info(_ message: String, category: String = "generation",
              fontPath: String? = nil, proofName: String? = nil,
              details: [String: String] = [:]) {
        emit(level: "info", category: category, message: message,
             fontPath: fontPath, proofName: proofName, details: details)
    }

    var collected: [DiagnosticEvent] { events }

    var firstError: String? {
        events.first(where: { $0.level == "error" })?.message
    }
}

/// Mutable state scoped to a single document or fragment generation run.
/// "Generate once" proofs track which instances they've already rendered so
/// the per-font/per-axis loop doesn't repeat them. Must never be shared
/// across runs: previews generate fragments concurrently.
final class ProofRunState {
    var generatedOnce: Set<String> = []
}

struct ProofContext {
    let fullCharacterSet: String
    let indFont: String
    let axisValues: [String: Double]?
    let otFeatures: [String: Bool]
    let cat: CharacterCategories
    let pageFormat: String
    let proofSettings: [String: Any]
    let showBaselines: Bool
    let showFooter: Bool
    let allAxisValues: [String: [Double]]?
    let allFontPaths: [String]
    let axisValuesByFont: [String: [String: [Double]]]
    let diagnostics: DiagnosticCollector
    var runState = ProofRunState()
}

struct ProofParams {
    let fontSize: CGFloat
    let columns: Int
    let paragraphs: Int
    let tracking: CGFloat
    let alignment: CTTextAlignment
    let lineHeight: CGFloat?
    let otFeatures: [String: Bool]
    let columnGap: CGFloat
    let direction: String
    let paragraphIndent: CGFloat
    let paragraphSpace: CGFloat
    let hyphenation: Bool
    let hangingPunctuation: Bool
    let generativeLanguage: String
    let wordDiversity: Double
    let vocabularySize: Int
    let minWordLength: Int
    let maxWordLength: Int
    let biasChars: String
    let biasStrength: Double
    let wordsPerSentence: Int
    let sentencesPerParagraph: Int
}

protocol ProofHandler {
    var proofName: String { get }
    var proofKey: String { get }

    func generateProof(context: ProofContext, renderer: PDFRenderer)
}

extension ProofHandler {

    func resolveAlignment(_ value: String) -> CTTextAlignment {
        switch value {
        case "right": return .right
        case "center": return .center
        case "justified": return .justified
        default: return .left
        }
    }

    func makeSettingsKey(_ parts: String...) -> String {
        ([proofKey] + parts).joined(separator: "_")
    }

    func settingsValue<T>(_ key: String, default defaultValue: T, from settings: [String: Any]) -> T {
        settings[key] as? T ?? defaultValue
    }

    func resolveParams(from context: ProofContext, defaultCols: Int = 2, defaultParas: Int = 5) -> ProofParams {
        let settings = context.proofSettings
        let fontSize = settingsValue(makeSettingsKey("fontSize"), default: 10, from: settings) as Int
        let cols = settingsValue(makeSettingsKey("cols"), default: defaultCols, from: settings)
        let paras = settingsValue(makeSettingsKey("para"), default: defaultParas, from: settings)
        let tracking = settingsValue(makeSettingsKey("tracking"), default: 0, from: settings) as Int
        let alignStr = settingsValue(makeSettingsKey("align"), default: "left", from: settings) as String
        let lineHeightRatio = settingsValue(makeSettingsKey("lineHeight"), default: 0.0, from: settings) as Double

        let lineHeight: CGFloat? = lineHeightRatio > 0 ? CGFloat(lineHeightRatio) * CGFloat(fontSize) : nil

        let columnGap = settingsValue(makeSettingsKey("columnGap"), default: 20.0, from: settings) as Double
        let directionStr = settingsValue(makeSettingsKey("direction"), default: "auto", from: settings) as String
        let paragraphIndent = settingsValue(makeSettingsKey("paragraphIndent"), default: 0.0, from: settings) as Double
        let paragraphSpace = settingsValue(makeSettingsKey("paragraphSpace"), default: 0.0, from: settings) as Double
        let hyphenation = settingsValue(makeSettingsKey("hyphenation"), default: false, from: settings) as Bool
        let hangingPunctuation = settingsValue(makeSettingsKey("hangingPunctuation"), default: false, from: settings) as Bool
        let generativeLanguage = settingsValue(makeSettingsKey("generativeLanguage"), default: "en", from: settings) as String
        let wordDiversity = settingsValue(makeSettingsKey("wordDiversity"), default: 0.0, from: settings) as Double
        let vocabularySize = settingsValue(makeSettingsKey("vocabularySize"), default: 0, from: settings) as Int
        let minWordLength = settingsValue(makeSettingsKey("minWordLength"), default: 1, from: settings) as Int
        let maxWordLength = settingsValue(makeSettingsKey("maxWordLength"), default: 0, from: settings) as Int
        let biasChars = settingsValue(makeSettingsKey("biasChars"), default: "", from: settings) as String
        let biasStrength = settingsValue(makeSettingsKey("biasStrength"), default: 0.0, from: settings) as Double
        let wordsPerSentence = settingsValue(makeSettingsKey("wordsPerSentence"), default: 15, from: settings) as Int
        let sentencesPerParagraph = settingsValue(makeSettingsKey("sentencesPerParagraph"), default: 4, from: settings) as Int

        let prefix = "otf_\(proofKey)_"
        var features: [String: Bool] = [:]
        for (key, value) in settings {
            if key.hasPrefix(prefix), let boolVal = value as? Bool {
                let tag = String(key.dropFirst(prefix.count))
                features[tag] = boolVal
            }
        }
        if features.isEmpty {
            features = context.otFeatures
        }

        return ProofParams(
            fontSize: CGFloat(fontSize),
            columns: cols,
            paragraphs: paras,
            tracking: CGFloat(tracking),
            alignment: resolveAlignment(alignStr),
            lineHeight: lineHeight,
            otFeatures: features,
            columnGap: CGFloat(columnGap),
            direction: directionStr,
            paragraphIndent: CGFloat(paragraphIndent),
            paragraphSpace: CGFloat(paragraphSpace),
            hyphenation: hyphenation,
            hangingPunctuation: hangingPunctuation,
            generativeLanguage: generativeLanguage,
            wordDiversity: wordDiversity,
            vocabularySize: vocabularySize,
            minWordLength: minWordLength,
            maxWordLength: maxWordLength,
            biasChars: biasChars,
            biasStrength: biasStrength,
            wordsPerSentence: wordsPerSentence,
            sentencesPerParagraph: sentencesPerParagraph
        )
    }

    func axisLabel(from context: ProofContext) -> String {
        if let axisValues = context.axisValues, !axisValues.isEmpty {
            return axisValues.sorted(by: { $0.key < $1.key })
                .map { "\($0.key)=\(Int($0.value))" }
                .joined(separator: " ")
        }
        let filename = URL(fileURLWithPath: context.indFont).deletingPathExtension().lastPathComponent
        let parts = filename.components(separatedBy: "-")
        if parts.count > 1 {
            return parts.dropFirst().joined(separator: " ")
        }
        return ""
    }

    func drawContent(
        _ attrString: NSAttributedString,
        sectionName: String,
        columns: Int,
        direction: TextDirection,
        otFeatures: [String: Bool],
        tracking: CGFloat,
        context: ProofContext,
        renderer: PDFRenderer,
        lineHeight footerLineHeight: CGFloat? = nil,
        columnGap: CGFloat? = nil,
        footerNote: String? = nil
    ) {
        let pageSize = PageLayout.pageDimensions[context.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let contentRect = PageLayout.contentRect(pageFormat: context.pageFormat)
        let gutter = columnGap ?? PageLayout.defaultGutter
        let colRects = PageLayout.columnRects(contentRect: contentRect, columns: columns, gutter: gutter, direction: direction)
        let fontName = URL(fileURLWithPath: context.indFont).deletingPathExtension().lastPathComponent
            .components(separatedBy: "-").first ?? "Unknown"

        let suffix = axisLabel(from: context)
        let fullTitle = suffix.isEmpty ? sectionName : "\(sectionName) - \(suffix)"

        let paginator = TextRenderer.Paginator(attrString)

        // repeat-while: an empty string still produces one (blank) page,
        // matching the previous overflow-based loop.
        repeat {
            renderer.beginPage()
            if context.showFooter {
                PageLayout.drawFooter(
                    context: renderer.context,
                    pageSize: pageSize,
                    title: fullTitle,
                    fontName: fontName,
                    otFeatures: otFeatures.isEmpty ? nil : otFeatures,
                    tracking: tracking,
                    pageNumber: renderer.pageCount,
                    showPageNumber: true,
                    lineHeight: footerLineHeight,
                    footerNote: footerNote
                )
            }

            if context.showBaselines, case let remaining = paginator.remainingText(), remaining.length > 0 {
                let actualBaselines = TextRenderer.baselineOrigins(for: remaining, in: colRects[0])
                let pageRect = CGRect(origin: .zero, size: pageSize)

                if !actualBaselines.isEmpty {
                    var lineHeight: CGFloat = 0
                    if let paraStyle = remaining.attribute(.paragraphStyle, at: 0, effectiveRange: nil) as? NSParagraphStyle,
                       paraStyle.minimumLineHeight > 0 {
                        lineHeight = paraStyle.minimumLineHeight
                    } else if actualBaselines.count >= 2 {
                        lineHeight = actualBaselines[0] - actualBaselines[1]
                    }

                    if lineHeight > 2 {
                        let positions = BaselineGrid.extendPositions(
                            from: actualBaselines, lineHeight: lineHeight, toBottom: contentRect.minY)
                        BaselineGrid.drawBaselines(in: pageRect, positions: positions, context: renderer.context)
                    } else {
                        BaselineGrid.drawBaselines(in: pageRect, positions: actualBaselines, context: renderer.context)
                    }
                }

                BaselineGrid.drawColumns(rects: colRects, context: renderer.context)
            }

            var consumedThisPage = 0
            for col in colRects {
                if paginator.isFinished { break }
                consumedThisPage += paginator.draw(in: col, context: renderer.context)
            }

            renderer.endPage()

            // A page pass that consumes no characters (e.g. column too small
            // for a single line) would otherwise loop forever.
            if !paginator.isFinished && consumedThisPage == 0 {
                context.diagnostics.error("Text does not fit the column layout — output truncated",
                                          proofName: proofName)
                break
            }
        } while !paginator.isFinished
    }
}
