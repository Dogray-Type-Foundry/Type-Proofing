import CoreGraphics
import CoreText
import Foundation

struct AutoSizing {

    static func fitToPage(
        text: String,
        fontPath: String,
        pageFormat: String,
        tracking: CGFloat = 0,
        alignment: CTTextAlignment = .center,
        otFeatures: [String: Bool]? = nil,
        variations: [String: Double]? = nil,
        minSize: CGFloat = 4,
        maxSize: CGFloat = 200
    ) -> CGFloat {
        let contentRect = PageLayout.contentRect(pageFormat: pageFormat)
        let contentW = contentRect.width
        let contentH = contentRect.height

        func fits(_ size: CGFloat) -> Bool {
            guard let font = FontLoader.makeFont(
                path: fontPath,
                size: size,
                features: otFeatures,
                variations: variations
            ) else { return false }

            let effectiveTracking = tracking == 0 ? size / 1.5 : tracking
            let attrString = TextRenderer.makeAttributedString(
                text: text,
                font: font,
                fontSize: size,
                alignment: alignment,
                tracking: effectiveTracking,
                lineHeight: nil,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: false
            )
            let measured = TextRenderer.measureText(attrString, width: contentW)
            return measured.height <= contentH
        }

        var lo = minSize
        var hi = maxSize
        for _ in 0..<30 {
            let mid = (lo + hi) / 2
            if fits(mid) {
                lo = mid
            } else {
                hi = mid
            }
            if hi - lo < 0.5 { break }
        }
        return floor(lo)
    }

    static func fitToLine(
        text: String,
        fontPath: String,
        pageFormat: String,
        tracking: CGFloat = 0,
        otFeatures: [String: Bool]? = nil,
        variations: [String: Double]? = nil,
        minSize: CGFloat = 4,
        maxSize: CGFloat = 200
    ) -> CGFloat {
        let contentRect = PageLayout.contentRect(pageFormat: pageFormat)
        let contentW = contentRect.width

        func fits(_ size: CGFloat) -> Bool {
            guard let font = FontLoader.makeFont(
                path: fontPath,
                size: size,
                features: otFeatures,
                variations: variations
            ) else { return false }

            let attrString = TextRenderer.makeAttributedString(
                text: text,
                font: font,
                fontSize: size,
                alignment: .left,
                tracking: tracking,
                lineHeight: nil,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: false
            )
            let measured = TextRenderer.measureText(attrString, width: .greatestFiniteMagnitude)
            return measured.width <= contentW
        }

        var lo = minSize
        var hi = maxSize
        for _ in 0..<30 {
            let mid = (lo + hi) / 2
            if fits(mid) {
                lo = mid
            } else {
                hi = mid
            }
            if hi - lo < 0.5 { break }
        }
        return floor(lo)
    }
}
