import CoreText
import Foundation

struct FontLoader {

    static func register(url: URL) -> Bool {
        var error: Unmanaged<CFError>?
        let success = CTFontManagerRegisterFontsForURL(url as CFURL, .process, &error)
        return success
    }

    static func unregister(url: URL) {
        CTFontManagerUnregisterFontsForURL(url as CFURL, .process, nil)
    }

    static func makeFont(
        path: String,
        size: CGFloat,
        features: [String: Bool]?,
        variations: [String: Double]?,
        hangingPunctuation: Bool = false
    ) -> CTFont? {
        let url = URL(fileURLWithPath: path) as CFURL
        guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url) as? [CTFontDescriptor],
              let baseDesc = descriptors.first else {
            return nil
        }

        let baseFont = CTFontCreateWithFontDescriptor(baseDesc, size, nil)

        if features == nil && variations == nil && !hangingPunctuation {
            return baseFont
        }

        var attrs: [String: Any] = [:]

        if let features = features, !features.isEmpty {
            var featureSettings: [[String: Any]] = features.map { tag, enabled in
                [kCTFontOpenTypeFeatureTag as String: tag,
                 kCTFontOpenTypeFeatureValue as String: enabled]
            }
            if hangingPunctuation {
                // AAT feature type 22 (kTextSpacingType), selector 1 (kOpticalBoundsSelector)
                featureSettings.append([
                    kCTFontFeatureTypeIdentifierKey as String: 22,
                    kCTFontFeatureSelectorIdentifierKey as String: 1,
                ])
            }
            attrs[kCTFontFeatureSettingsAttribute as String] = featureSettings
        } else if hangingPunctuation {
            let featureSettings: [[String: Any]] = [[
                kCTFontFeatureTypeIdentifierKey as String: 22,
                kCTFontFeatureSelectorIdentifierKey as String: 1,
            ]]
            attrs[kCTFontFeatureSettingsAttribute as String] = featureSettings
        }

        if let variations = variations, !variations.isEmpty {
            let variationDict: [Int: Double] = Dictionary(
                uniqueKeysWithValues: variations.map { (axisTagToID($0.key), $0.value) }
            )
            attrs[kCTFontVariationAttribute as String] = variationDict
        }

        if attrs.isEmpty {
            return baseFont
        }

        let currentDesc = CTFontCopyFontDescriptor(baseFont)
        let newDesc = CTFontDescriptorCreateCopyWithAttributes(currentDesc, attrs as CFDictionary)
        return CTFontCreateWithFontDescriptor(newDesc, size, nil)
    }

    static func fontContains(_ font: CTFont, characters: String) -> Bool {
        let utf16 = Array(characters.utf16)
        var glyphs = [CGGlyph](repeating: 0, count: utf16.count)
        return CTFontGetGlyphsForCharacters(font, utf16, &glyphs, utf16.count)
    }

    static func drawGlyphsByName(
        _ glyphNames: [String],
        font: CTFont,
        in rect: CGRect,
        context: CGContext,
        tracking: CGFloat = 0
    ) {
        var glyphs: [CGGlyph] = []
        for name in glyphNames {
            let glyph = CTFontGetGlyphWithName(font, name as CFString)
            if glyph != 0 { glyphs.append(glyph) }
        }
        if glyphs.isEmpty { return }

        var advances = [CGSize](repeating: .zero, count: glyphs.count)
        CTFontGetAdvancesForGlyphs(font, .horizontal, glyphs, &advances, glyphs.count)

        let ascent = CTFontGetAscent(font)
        var x = rect.minX
        let y = rect.minY + (rect.height - ascent) / 2 + ascent * 0.1

        context.saveGState()
        context.textMatrix = .identity
        context.setFillColor(CGColor(gray: 0, alpha: 1))

        for (i, glyph) in glyphs.enumerated() {
            if x > rect.maxX { break }
            var g = glyph
            var pos = CGPoint(x: x, y: y)
            CTFontDrawGlyphs(font, &g, &pos, 1, context)
            x += advances[i].width + tracking
        }

        context.restoreGState()
    }

    static func drawGlyphsByID(
        _ glyphIDs: [UInt16],
        font: CTFont,
        in rect: CGRect,
        context: CGContext,
        tracking: CGFloat = 0
    ) {
        let glyphs: [CGGlyph] = glyphIDs.map { CGGlyph($0) }
        if glyphs.isEmpty { return }

        var advances = [CGSize](repeating: .zero, count: glyphs.count)
        CTFontGetAdvancesForGlyphs(font, .horizontal, glyphs, &advances, glyphs.count)

        let ascent = CTFontGetAscent(font)
        let descent = CTFontGetDescent(font)
        var x = rect.minX
        let y = rect.minY + (rect.height - ascent - descent) / 2 + descent

        context.saveGState()
        context.textMatrix = .identity
        context.setFillColor(CGColor(gray: 0, alpha: 1))

        for (i, glyph) in glyphs.enumerated() {
            if x > rect.maxX { break }
            var g = glyph
            var pos = CGPoint(x: x, y: y)
            CTFontDrawGlyphs(font, &g, &pos, 1, context)
            x += advances[i].width + tracking
        }

        context.restoreGState()
    }

    static func measureGlyphsByID(
        _ glyphIDs: [UInt16],
        font: CTFont,
        tracking: CGFloat = 0
    ) -> CGFloat {
        let glyphs: [CGGlyph] = glyphIDs.map { CGGlyph($0) }
        if glyphs.isEmpty { return 0 }
        var advances = [CGSize](repeating: .zero, count: glyphs.count)
        CTFontGetAdvancesForGlyphs(font, .horizontal, glyphs, &advances, glyphs.count)
        return advances.reduce(CGFloat(0)) { $0 + $1.width } + tracking * CGFloat(max(0, glyphs.count - 1))
    }

    static func glyphName(for glyphID: UInt16, font: CTFont) -> String? {
        if let cgFont = CTFontCopyGraphicsFont(font, nil) as CGFont? {
            if let name = cgFont.name(for: CGGlyph(glyphID)) {
                return name as String
            }
        }
        return nil
    }

    static func fontSupportsOpbd(path: String) -> Bool {
        let url = URL(fileURLWithPath: path) as CFURL
        guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url) as? [CTFontDescriptor],
              let desc = descriptors.first else { return false }
        let font = CTFontCreateWithFontDescriptor(desc, 12, nil)
        guard let features = CTFontCopyFeatures(font) as? [[String: Any]] else { return false }
        return features.contains { dict in
            (dict[kCTFontFeatureTypeIdentifierKey as String] as? Int) == 22
        }
    }

    private static func axisTagToID(_ tag: String) -> Int {
        let bytes = Array(tag.utf8)
        guard bytes.count >= 4 else { return 0 }
        return Int(bytes[0]) << 24 | Int(bytes[1]) << 16 | Int(bytes[2]) << 8 | Int(bytes[3])
    }
}
