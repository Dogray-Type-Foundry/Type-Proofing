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
        kernDisabled: Bool = false,
        paragraphIndent: CGFloat? = nil,
        paragraphSpace: CGFloat? = nil,
        hyphenation: Bool = false,
        language: String? = nil
    ) -> NSMutableAttributedString {
        let paragraphStyle = NSMutableParagraphStyle()
        paragraphStyle.setParagraphStyle(.default)
        paragraphStyle.alignment = alignment.nsTextAlignment
        paragraphStyle.hyphenationFactor = hyphenation ? 0.9 : 0
        if let lh = lineHeight {
            paragraphStyle.minimumLineHeight = lh
            paragraphStyle.maximumLineHeight = lh
        }
        if let indent = paragraphIndent, indent > 0 {
            paragraphStyle.firstLineHeadIndent = indent * fontSize
        }
        if let space = paragraphSpace, space > 0 {
            paragraphStyle.paragraphSpacing = space * fontSize
        }

        var attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .paragraphStyle: paragraphStyle,
            .foregroundColor: foregroundColor,
        ]

        if let lang = language {
            attrs[NSAttributedString.Key(kCTLanguageAttributeName as String)] = lang
        }

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
        kernDisabled: Bool = false,
        paragraphIndent: CGFloat? = nil,
        paragraphSpace: CGFloat? = nil,
        hyphenation: Bool = false,
        language: String? = nil
    ) {
        let additional = makeAttributedString(
            text: text,
            font: font,
            fontSize: fontSize,
            alignment: alignment,
            tracking: tracking,
            lineHeight: lineHeight,
            foregroundColor: foregroundColor,
            kernDisabled: kernDisabled,
            paragraphIndent: paragraphIndent,
            paragraphSpace: paragraphSpace,
            hyphenation: hyphenation,
            language: language
        )
        attrString.append(additional)
    }

    @discardableResult
    static func drawText(
        _ attrString: NSAttributedString,
        in rect: CGRect,
        context: CGContext
    ) -> NSAttributedString? {
        let hasHyphenation: Bool = {
            guard attrString.length > 0 else { return false }
            let paraStyle = attrString.attribute(.paragraphStyle, at: 0, effectiveRange: nil) as? NSParagraphStyle
            return (paraStyle?.hyphenationFactor ?? 0) > 0
        }()

        if hasHyphenation {
            return drawTextWithLayoutManager(attrString, in: rect, context: context)
        }
        return drawTextWithFramesetter(attrString, in: rect, context: context)
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

    static func baselineOrigins(for attrString: NSAttributedString, in rect: CGRect) -> [CGFloat] {
        let framesetter = makeFramesetter(for: attrString)
        let path = CGMutablePath()
        path.addRect(rect)
        let frame = CTFramesetterCreateFrame(framesetter, CFRange(location: 0, length: 0), path, nil)
        let lines = CTFrameGetLines(frame)
        let count = CFArrayGetCount(lines)
        guard count > 0 else { return [] }
        var origins = [CGPoint](repeating: .zero, count: count)
        CTFrameGetLineOrigins(frame, CFRange(location: 0, length: count), &origins)
        return origins.map { rect.origin.y + $0.y }
    }

    // MARK: - Private

    private static func drawTextWithFramesetter(
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

    private static func drawTextWithLayoutManager(
        _ attrString: NSAttributedString,
        in rect: CGRect,
        context: CGContext
    ) -> NSAttributedString? {
        let mutable = NSMutableAttributedString(attributedString: attrString)
        let fullRange = NSRange(location: 0, length: mutable.length)
        if let cgColor = mutable.attribute(.foregroundColor, at: 0, effectiveRange: nil) {
            mutable.addAttribute(.foregroundColor, value: NSColor(cgColor: cgColor as! CGColor) ?? NSColor.black, range: fullRange)
        }
        let textStorage = NSTextStorage(attributedString: mutable)
        let layoutManager = NSLayoutManager()
        layoutManager.usesDefaultHyphenation = true
        let textContainer = NSTextContainer(size: rect.size)
        textContainer.lineFragmentPadding = 0
        layoutManager.addTextContainer(textContainer)
        textStorage.addLayoutManager(layoutManager)
        layoutManager.ensureLayout(for: textContainer)

        let glyphRange = layoutManager.glyphRange(for: textContainer)

        let nsContext = NSGraphicsContext(cgContext: context, flipped: true)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = nsContext

        let savedTextMatrix = context.textMatrix
        context.saveGState()
        context.translateBy(x: rect.origin.x, y: rect.origin.y + rect.height)
        context.scaleBy(x: 1, y: -1)

        layoutManager.drawBackground(forGlyphRange: glyphRange, at: .zero)
        layoutManager.drawGlyphs(forGlyphRange: glyphRange, at: .zero)

        context.restoreGState()
        context.textMatrix = savedTextMatrix
        NSGraphicsContext.restoreGraphicsState()

        let charRange = layoutManager.characterRange(forGlyphRange: glyphRange, actualGlyphRange: nil)
        let drawnLength = charRange.location + charRange.length
        if drawnLength < attrString.length {
            return attrString.attributedSubstring(
                from: NSRange(location: drawnLength, length: attrString.length - drawnLength)
            )
        }
        return nil
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
