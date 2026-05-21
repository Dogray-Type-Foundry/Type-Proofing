import CoreGraphics
import CoreText
import Foundation

enum TextDirection {
    case ltr, rtl
}

struct PageLayout {
    static let marginVertical: CGFloat = 50
    static let marginHorizontal: CGFloat = 40
    static let defaultGutter: CGFloat = 20
    static let footerFontSize: CGFloat = 9
    static let footerFeaturesFontSize: CGFloat = 7

    static let pageFormatOrder: [String] = [
        "A4Landscape", "A4Portrait",
        "LetterLandscape", "LetterPortrait",
        "A3Landscape", "A3Portrait",
        "A5Landscape", "A5Portrait",
        "LegalLandscape", "LegalPortrait",
        "iPhoneLandscape", "iPhonePortrait",
    ]

    static let pageDimensions: [String: CGSize] = [
        "A4Landscape": CGSize(width: 842, height: 595),
        "A4Portrait": CGSize(width: 595, height: 842),
        "LetterLandscape": CGSize(width: 792, height: 612),
        "LetterPortrait": CGSize(width: 612, height: 792),
        "A3Landscape": CGSize(width: 1190, height: 842),
        "A3Portrait": CGSize(width: 842, height: 1190),
        "A5Landscape": CGSize(width: 595, height: 420),
        "A5Portrait": CGSize(width: 420, height: 595),
        "LegalLandscape": CGSize(width: 1008, height: 612),
        "LegalPortrait": CGSize(width: 612, height: 1008),
        "iPhoneLandscape": CGSize(width: 844, height: 390),
        "iPhonePortrait": CGSize(width: 390, height: 844),
    ]

    static func contentRect(pageFormat: String) -> CGRect {
        let size = pageDimensions[pageFormat] ?? pageDimensions["A4Landscape"]!
        return CGRect(
            x: marginHorizontal,
            y: marginVertical,
            width: size.width - marginHorizontal * 2,
            height: size.height - marginVertical * 2
        )
    }

    static func columnRects(
        contentRect: CGRect,
        columns: Int,
        gutter: CGFloat = defaultGutter,
        direction: TextDirection = .ltr
    ) -> [CGRect] {
        let count = max(1, columns)
        if count == 1 {
            return [contentRect]
        }
        let colWidth = (contentRect.width - CGFloat(count - 1) * gutter) / CGFloat(count)
        return (0..<count).map { i in
            let visualIndex = direction == .rtl ? count - 1 - i : i
            let x = contentRect.minX + CGFloat(visualIndex) * (colWidth + gutter)
            return CGRect(x: x, y: contentRect.minY, width: colWidth, height: contentRect.height)
        }
    }

    static func drawFooter(
        context: CGContext,
        pageSize: CGSize,
        title: String,
        fontName: String,
        otFeatures: [String: Bool]?,
        tracking: CGFloat,
        pageNumber: Int,
        showPageNumber: Bool,
        lineHeight: CGFloat? = nil
    ) {
        let width = pageSize.width - marginHorizontal * 2
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let dateStr = formatter.string(from: Date())
        formatter.dateFormat = "HH:mm"
        let timeStr = formatter.string(from: Date())

        let footerText = "\(dateStr) \(timeStr) | \(fontName) | \(title)"
        let footerFont = CTFontCreateWithName("Courier" as CFString, footerFontSize, nil)
        let black = CGColor(gray: 0, alpha: 1)

        let footerRect = CGRect(
            x: marginHorizontal,
            y: marginVertical - 20,
            width: width,
            height: footerFontSize + 4
        )
        let footerAttr = TextRenderer.makeAttributedString(
            text: footerText,
            font: footerFont,
            fontSize: footerFontSize,
            alignment: .left,
            tracking: 0,
            lineHeight: nil,
            foregroundColor: black
        )
        TextRenderer.drawText(footerAttr, in: footerRect, context: context)

        if showPageNumber {
            let folioAttr = TextRenderer.makeAttributedString(
                text: "\(pageNumber)",
                font: footerFont,
                fontSize: footerFontSize,
                alignment: .right,
                tracking: 0,
                lineHeight: nil,
                foregroundColor: black
            )
            TextRenderer.drawText(folioAttr, in: footerRect, context: context)
        }

        var secondLineText = ""
        if let features = otFeatures, !features.isEmpty {
            let raw = buildFeaturesText(features, tracking: 0)
            if !raw.isEmpty {
                secondLineText = "OT Fea: " + raw
            }
        }
        if tracking != 0 {
            let trackingStr = "Tracking: \(Int(tracking))"
            if secondLineText.isEmpty {
                secondLineText = trackingStr
            } else {
                secondLineText += " | " + trackingStr
            }
        }
        if let lh = lineHeight, lh > 0 {
            let lhStr = "Line Height: \(String(format: "%.1f", lh))"
            if secondLineText.isEmpty {
                secondLineText = lhStr
            } else {
                secondLineText += " | " + lhStr
            }
        }
        if !secondLineText.isEmpty {
            let featFont = CTFontCreateWithName("Courier" as CFString, footerFeaturesFontSize, nil)
            let featRect = CGRect(
                x: marginHorizontal,
                y: marginVertical - 30,
                width: width,
                height: footerFeaturesFontSize + 4
            )
            let featAttr = TextRenderer.makeAttributedString(
                text: secondLineText,
                font: featFont,
                fontSize: footerFeaturesFontSize,
                alignment: .left,
                tracking: 0,
                lineHeight: nil,
                foregroundColor: black
            )
            TextRenderer.drawText(featAttr, in: featRect, context: context)
        }
    }

    private static let defaultOnFeatures: Set<String> = [
        "ccmp", "locl", "mark", "mkmk", "kern", "liga", "clig", "rclt", "rlig",
    ]

    private static func buildFeaturesText(_ features: [String: Bool], tracking: CGFloat) -> String {
        var parts: [String] = []

        let enabledNonDefault = features.filter { $0.value && !defaultOnFeatures.contains($0.key) }
            .keys.sorted()
        if !enabledNonDefault.isEmpty {
            parts.append("ON: \(enabledNonDefault.joined(separator: ", "))")
        }

        let disabledDefault = features.filter { !$0.value && defaultOnFeatures.contains($0.key) }
            .keys.sorted()
        if !disabledDefault.isEmpty {
            parts.append("OFF: \(disabledDefault.joined(separator: ", "))")
        }

        return parts.joined(separator: " - ")
    }
}
