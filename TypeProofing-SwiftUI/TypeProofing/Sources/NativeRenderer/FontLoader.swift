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
        guard let baseDesc = baseDescriptor(path: path) else {
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
        guard let desc = baseDescriptor(path: path) else { return false }
        let font = CTFontCreateWithFontDescriptor(desc, 12, nil)
        guard let features = CTFontCopyFeatures(font) as? [[String: Any]] else { return false }
        return features.contains { dict in
            (dict[kCTFontFeatureTypeIdentifierKey as String] as? Int) == 22
        }
    }

    static func axisTagToID(_ tag: String) -> Int {
        let bytes = Array(tag.utf8)
        guard bytes.count >= 4 else { return 0 }
        return Int(bytes[0]) << 24 | Int(bytes[1]) << 16 | Int(bytes[2]) << 8 | Int(bytes[3])
    }

    static func axisIDToTag(_ id: Int) -> String {
        let bytes: [UInt8] = [
            UInt8((id >> 24) & 0xFF),
            UInt8((id >> 16) & 0xFF),
            UInt8((id >> 8) & 0xFF),
            UInt8(id & 0xFF),
        ]
        return String(bytes.map { Character(UnicodeScalar($0)) })
    }

    // MARK: - Cached font descriptors

    private static let baseDescriptorCache = NSCache<NSString, CTFontDescriptor>()

    /// The first font descriptor of the file at `path`, cached with the same
    /// mtime/size-invalidated key as `fontData`. Creating a descriptor via
    /// CTFontManagerCreateFontDescriptorsFromURL reads and parses the file from
    /// disk, and makeFont sits in hot loops (auto-sizing bisection, per-token
    /// markup styling, per-entry substitution rows), so this cache is what keeps
    /// those loops off the disk.
    static func baseDescriptor(path: String) -> CTFontDescriptor? {
        let key = fontCacheKey(for: path) as NSString
        if let cached = baseDescriptorCache.object(forKey: key) {
            return cached
        }
        let url = URL(fileURLWithPath: path) as CFURL
        guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url) as? [CTFontDescriptor],
              let desc = descriptors.first else {
            return nil
        }
        baseDescriptorCache.setObject(desc, forKey: key)
        return desc
    }

    // MARK: - Cached font bytes

    private static let fontDataCache = NSCache<NSString, NSData>()

    /// Reads the font file at `path`, caching the bytes keyed by path + modification
    /// date + size so repeated metadata queries for the same unchanged file read disk
    /// only once. A changed file (different mtime/size) produces a new key, so stale
    /// bytes are never served.
    static func fontData(path: String) -> Data? {
        let key = fontCacheKey(for: path) as NSString
        if let cached = fontDataCache.object(forKey: key) {
            return cached as Data
        }
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return nil }
        fontDataCache.setObject(data as NSData, forKey: key)
        return data
    }

    static func fontCacheKey(for path: String) -> String {
        let attrs = try? FileManager.default.attributesOfItem(atPath: path)
        let mtime = (attrs?[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0
        let size = (attrs?[.size] as? Int) ?? 0
        return "\(path)|\(mtime)|\(size)"
    }

    /// Centralizes the `Data.withUnsafeBytes { ... }` pointer dance used to pass font
    /// bytes to the Rust FFI. Exposes the bytes as a (pointer, length) pair to `body`,
    /// returning `fallback` when the file can't be read.
    static func withFontBytes<T>(path: String, fallback: T, _ body: (UnsafePointer<UInt8>, UInt) -> T) -> T {
        guard let data = fontData(path: path) else { return fallback }
        return data.withUnsafeBytes { buffer -> T in
            guard let base = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return fallback }
            return body(base, UInt(buffer.count))
        }
    }
}
