import AppKit
import CoreGraphics
import CoreText
import Foundation

struct TextRenderer {

    static func makeAttributedString(
        text: String,
        font: CTFont,
        fontSize: CGFloat,
        alignment: CTTextAlignment,
        tracking: CGFloat,
        lineHeight: CGFloat?,
        foregroundColor: CGColor,
        kernDisabled: Bool = false
    ) -> NSMutableAttributedString {
        let paragraphStyle = NSMutableParagraphStyle()
        paragraphStyle.setParagraphStyle(.default)
        paragraphStyle.alignment = alignment.nsTextAlignment
        paragraphStyle.hyphenationFactor = 0
        if let lh = lineHeight {
            paragraphStyle.minimumLineHeight = lh
            paragraphStyle.maximumLineHeight = lh
        }

        var attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .paragraphStyle: paragraphStyle,
            .foregroundColor: foregroundColor,
        ]

        if tracking != 0 {
            attrs[NSAttributedString.Key(kCTTrackingAttributeName as String)] = tracking
        }

        if kernDisabled {
            attrs[.kern] = NSNumber(value: 0)
        }

        return NSMutableAttributedString(string: text, attributes: attrs)
    }

    static func appendText(
        to attrString: NSMutableAttributedString,
        text: String,
        font: CTFont,
        fontSize: CGFloat,
        alignment: CTTextAlignment,
        tracking: CGFloat,
        lineHeight: CGFloat?,
        foregroundColor: CGColor,
        kernDisabled: Bool = false
    ) {
        let additional = makeAttributedString(
            text: text,
            font: font,
            fontSize: fontSize,
            alignment: alignment,
            tracking: tracking,
            lineHeight: lineHeight,
            foregroundColor: foregroundColor,
            kernDisabled: kernDisabled
        )
        attrString.append(additional)
    }

    @discardableResult
    static func drawText(
        _ attrString: NSAttributedString,
        in rect: CGRect,
        context: CGContext
    ) -> NSAttributedString? {
        let framesetter = makeFramesetter(for: attrString)

        let path = CGMutablePath()
        path.addRect(rect)

        let frame = CTFramesetterCreateFrame(framesetter, CFRange(location: 0, length: 0), path, nil)
        CTFrameDraw(frame, context)

        let visibleRange = CTFrameGetVisibleStringRange(frame)
        let drawnLength = visibleRange.location + visibleRange.length
        if drawnLength < attrString.length {
            return attrString.attributedSubstring(
                from: NSRange(location: drawnLength, length: attrString.length - drawnLength)
            )
        }
        return nil
    }

    static func measureText(_ attrString: NSAttributedString, width: CGFloat?) -> CGSize {
        if let w = width {
            let framesetter = makeFramesetter(for: attrString)
            let constraint = CGSize(width: w, height: CGFloat.greatestFiniteMagnitude)
            let size = CTFramesetterSuggestFrameSizeWithConstraints(
                framesetter, CFRange(location: 0, length: 0), nil, constraint, nil
            )
            return size
        } else {
            let line = CTLineCreateWithAttributedString(attrString)
            var ascent: CGFloat = 0
            var descent: CGFloat = 0
            var leading: CGFloat = 0
            let width = CTLineGetTypographicBounds(line, &ascent, &descent, &leading)
            return CGSize(width: width, height: ascent + descent + leading)
        }
    }

    private static func makeFramesetter(for attrString: NSAttributedString) -> CTFramesetter {
        if attrString.length > 2000 {
            let typesetter = CTTypesetterCreateWithAttributedStringAndOptions(
                attrString,
                [kCTTypesetterOptionAllowUnboundedLayout: true] as CFDictionary
            )!
            return CTFramesetterCreateWithTypesetter(typesetter)
        } else {
            return CTFramesetterCreateWithAttributedString(attrString)
        }
    }
}

extension CTTextAlignment {
    var nsTextAlignment: NSTextAlignment {
        switch self {
        case .left: return .left
        case .right: return .right
        case .center: return .center
        case .justified: return .justified
        case .natural: return .natural
        @unknown default: return .left
        }
    }
}
