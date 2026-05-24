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

struct ProofContext {
    let fullCharacterSet: String
    let indFont: String
    let axisValues: [String: Double]?
    let otFeatures: [String: Bool]
    let cat: CharacterCategories
    let pageFormat: String
    let proofSettings: [String: Any]
    let showBaselines: Bool
    let allAxisValues: [String: [Double]]?
    let allFontPaths: [String]
    let axisValuesByFont: [String: [String: [Double]]]
    let diagnostics: DiagnosticCollector
}

struct ProofParams {
    let fontSize: CGFloat
    let columns: Int
    let paragraphs: Int
    let tracking: CGFloat
    let alignment: CTTextAlignment
    let lineHeight: CGFloat?
    let otFeatures: [String: Bool]
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
            otFeatures: features
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
        lineHeight footerLineHeight: CGFloat? = nil
    ) {
        let pageSize = PageLayout.pageDimensions[context.pageFormat]
            ?? PageLayout.pageDimensions["A4Landscape"]!
        let contentRect = PageLayout.contentRect(pageFormat: context.pageFormat)
        let colRects = PageLayout.columnRects(contentRect: contentRect, columns: columns, direction: direction)
        let fontName = URL(fileURLWithPath: context.indFont).deletingPathExtension().lastPathComponent
            .components(separatedBy: "-").first ?? "Unknown"

        let suffix = axisLabel(from: context)
        let fullTitle = suffix.isEmpty ? sectionName : "\(sectionName) - \(suffix)"

        var overflow: NSAttributedString? = attrString

        while overflow != nil {
            renderer.beginPage()
            PageLayout.drawFooter(
                context: renderer.context,
                pageSize: pageSize,
                title: fullTitle,
                fontName: fontName,
                otFeatures: otFeatures.isEmpty ? nil : otFeatures,
                tracking: tracking,
                pageNumber: renderer.pageCount,
                showPageNumber: true,
                lineHeight: footerLineHeight
            )

            if context.showBaselines, let remaining = overflow {
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

            for col in colRects {
                guard let remaining = overflow else { break }
                overflow = TextRenderer.drawText(remaining, in: col, context: renderer.context)
            }

            renderer.endPage()
        }
    }
}
