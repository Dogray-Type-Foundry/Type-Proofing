import CoreGraphics
import CoreText
import Foundation
import TPNative

struct StylePairing {

    private static let dualStyleSeed: UInt64 = 12345

    enum Pairing {
        case staticUprightItalic(upright: String, italic: String)
        case staticRegularBold(regular: String, bold: String)
        case variableItal(upright: Double, italic: Double)
        case variableWght(regular: Double, bold: Double)
    }

    struct FontMeta {
        let path: String
        let familyName: String
        let subfamilyName: String
        let weight: Int
        let isItalic: Bool
        let isVariable: Bool
        let hasItalAxis: Bool
        let hasWghtAxis: Bool
    }

    private static var metaCache: [String: FontMeta] = [:]

    static func resetCache() {
        metaCache.removeAll()
    }

    static func loadFontMeta(path: String) -> FontMeta? {
        if let cached = metaCache[path] { return cached }
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return nil }
        return data.withUnsafeBytes { buffer -> FontMeta? in
            guard let ptr = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return nil }
            guard let infoPtr = tp_load_font(ptr, UInt(buffer.count)) else { return nil }
            defer { tp_free_font_info(infoPtr) }
            let info = infoPtr.pointee

            let familyName = info.family_name != nil ? String(cString: info.family_name) : ""
            let subfamilyName = info.subfamily_name != nil ? String(cString: info.subfamily_name) : "Regular"
            let isItalic = (info.fs_selection & 1) != 0
            let isVariable = info.is_variable

            var hasItal = false
            var hasWght = false
            if let axesJSON = info.axes_json != nil ? String(cString: info.axes_json) : nil,
               let axesData = axesJSON.data(using: .utf8),
               let axes = try? JSONSerialization.jsonObject(with: axesData) as? [[String: Any]] {
                for axis in axes {
                    if let tag = axis["tag"] as? String {
                        if tag == "ital" { hasItal = true }
                        if tag == "wght" { hasWght = true }
                    }
                }
            }

            let meta = FontMeta(
                path: path, familyName: familyName, subfamilyName: subfamilyName,
                weight: Int(info.weight), isItalic: isItalic, isVariable: isVariable,
                hasItalAxis: hasItal, hasWghtAxis: hasWght
            )
            metaCache[path] = meta
            return meta
        }
    }

    static func detectPairing(
        fontPath: String,
        axisValues: [String: Double]?,
        allFontPaths: [String]
    ) -> Pairing? {
        guard let currentMeta = loadFontMeta(path: fontPath) else { return nil }

        let allMeta = allFontPaths.compactMap { loadFontMeta(path: $0) }

        // 1) Static Regular/Bold pairing: generated from Regular subfamily
        if currentMeta.subfamilyName == "Regular" && !currentMeta.isVariable {
            if let boldMatch = allMeta.first(where: {
                $0.familyName == currentMeta.familyName
                && $0.subfamilyName == "Bold"
                && !$0.isVariable
            }) {
                return .staticRegularBold(regular: currentMeta.path, bold: boldMatch.path)
            }
        }

        // 2) Static Upright/Italic pairing
        // For non-Regular weights: generated from the upright
        // For Regular weight (400): generated from the Italic so Regular can produce R/B above
        if !currentMeta.isVariable {
            if currentMeta.weight == 400 && currentMeta.isItalic {
                if let uprightMatch = allMeta.first(where: {
                    $0.familyName == currentMeta.familyName
                    && $0.weight == currentMeta.weight
                    && !$0.isItalic
                    && !$0.isVariable
                }) {
                    return .staticUprightItalic(upright: uprightMatch.path, italic: currentMeta.path)
                }
            } else if !currentMeta.isItalic {
                if let italicMatch = allMeta.first(where: {
                    $0.familyName == currentMeta.familyName
                    && $0.weight == currentMeta.weight
                    && $0.isItalic
                    && !$0.isVariable
                }) {
                    return .staticUprightItalic(upright: currentMeta.path, italic: italicMatch.path)
                }
            }
        }

        // 3) Variable font ital axis
        if currentMeta.hasItalAxis {
            let italVal = axisValues?["ital"] ?? 0
            if italVal != 0 {
                return .variableItal(upright: 0, italic: 1)
            }
        }

        // 4) Variable font wght axis (when at bold weight)
        if currentMeta.hasWghtAxis {
            let wghtVal = axisValues?["wght"] ?? 400
            if wghtVal >= 600 {
                return .variableWght(regular: 400, bold: wghtVal)
            }
        }

        return nil
    }

    static func shouldSkipFont(
        fontPath: String,
        allFontPaths: [String]
    ) -> Bool {
        guard let meta = loadFontMeta(path: fontPath) else { return false }
        if meta.isVariable { return false }

        let allMeta = allFontPaths.compactMap { loadFontMeta(path: $0) }

        // Skip Bold if Regular exists in same family (R/B generated from Regular)
        if meta.subfamilyName == "Bold" {
            if allMeta.contains(where: {
                $0.familyName == meta.familyName && $0.subfamilyName == "Regular" && !$0.isVariable
            }) {
                return true
            }
        }

        // Skip non-Regular-weight italic if matching upright exists (U/I generated from upright)
        if meta.isItalic && meta.weight != 400 {
            if allMeta.contains(where: {
                $0.familyName == meta.familyName && $0.weight == meta.weight && !$0.isItalic && !$0.isVariable
            }) {
                return true
            }
        }

        // Skip non-italic Regular weight upright if it has an italic pair
        // (U/I at weight 400 is generated from the Italic, while Regular produces R/B)
        // But only skip if Regular actually found no R/B pair (detectPairing returns nil means
        // it couldn't find Bold, so it would try U/I from upright — don't skip then)
        // Actually: Regular upright produces R/B or nothing. Italic 400 produces U/I.
        // Non-400 upright produces U/I. Non-400 italic is skipped.
        // So: no additional skip needed here — detectPairing handles the logic.

        return false
    }

    static func buildMixedStyleAttributedString(
        text: String,
        fontPath: String,
        fontSize: CGFloat,
        alignment: CTTextAlignment,
        tracking: CGFloat,
        lineHeight: CGFloat?,
        baseVariations: [String: Double]?,
        pairing: Pairing,
        otFeatures: [String: Bool]?
    ) -> NSMutableAttributedString {
        var rng = SeededRNG(seed: dualStyleSeed)
        let words = text.split(separator: " ", omittingEmptySubsequences: false)
        let result = NSMutableAttributedString()
        let kernDisabled = otFeatures?["kern"] == false

        var useAlternate = false
        var nextSwitch = Int.random(in: 1...4, using: &rng)
        var wordCount = 0

        for word in words {
            let wordStr = String(word) + " "

            let font: CTFont?
            switch pairing {
            case .staticUprightItalic(let upright, let italic):
                let path = useAlternate ? italic : upright
                font = FontLoader.makeFont(path: path, size: fontSize, features: otFeatures, variations: nil)

            case .staticRegularBold(let regular, let bold):
                let path = useAlternate ? bold : regular
                font = FontLoader.makeFont(path: path, size: fontSize, features: otFeatures, variations: nil)

            case .variableItal(let uprightVal, let italicVal):
                var v = baseVariations ?? [:]
                v["ital"] = useAlternate ? italicVal : uprightVal
                font = FontLoader.makeFont(path: fontPath, size: fontSize, features: otFeatures, variations: v)

            case .variableWght(let regularVal, let boldVal):
                var v = baseVariations ?? [:]
                v["wght"] = useAlternate ? boldVal : regularVal
                font = FontLoader.makeFont(path: fontPath, size: fontSize, features: otFeatures, variations: v)
            }

            guard let resolvedFont = font else { continue }

            TextRenderer.appendText(
                to: result,
                text: wordStr,
                font: resolvedFont,
                fontSize: fontSize,
                alignment: alignment,
                tracking: tracking,
                lineHeight: lineHeight,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: kernDisabled
            )

            wordCount += 1
            if wordCount >= nextSwitch {
                useAlternate.toggle()
                wordCount = 0
                nextSwitch = Int.random(in: 1...4, using: &rng)
            }
        }

        return result
    }
}

private struct SeededRNG: RandomNumberGenerator {
    var state: UInt64

    init(seed: UInt64) {
        state = seed
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}
