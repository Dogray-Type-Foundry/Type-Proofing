import CoreGraphics
import CoreText
import Foundation
import TPNative

/// One style participating in a user-defined pairing. Referenced by font path
/// plus axis coordinates (not style index) so it survives font list reordering.
public struct PairingStyleRef: Codable, Equatable, Identifiable {
    public var id: UUID = UUID()
    public var fontPath: String = ""
    public var coordinates: [String: Double]? = nil
    public var weight: Double = 50
    public var label: String = ""

    public init(
        id: UUID = UUID(),
        fontPath: String = "",
        coordinates: [String: Double]? = nil,
        weight: Double = 50,
        label: String = ""
    ) {
        self.id = id
        self.fontPath = fontPath
        self.coordinates = coordinates
        self.weight = weight
        self.label = label
    }
}

/// A user-defined mix of 2–4 styles for the Style Pairing proof's manual mode.
public struct ManualPairing: Codable, Equatable, Identifiable {
    public var id: UUID = UUID()
    public var styles: [PairingStyleRef] = []

    public init() {}
}

struct StylePairing {

    private static let dualStyleSeed: UInt64 = 12345

    enum Pairing {
        case staticUprightItalic(upright: String, italic: String)
        case staticRegularBold(regular: String, bold: String)
        case variableItal(upright: Double, italic: Double)
        case variableSlnt(upright: Double, italic: Double)
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
        let hasSlntAxis: Bool
        /// The slanted end of the slnt axis (usually the negative extreme).
        let slntItalicValue: Double
    }

    // Accessed from concurrent preview fragment generations — guard every
    // read/write with the lock. Keyed on path + mtime + size (via
    // FontLoader.fontCacheKey) so re-exporting a font over an existing path
    // produces a new key and auto-misses, never serving stale metadata.
    private static var metaCache: [String: FontMeta] = [:]
    private static let metaCacheLock = NSLock()

    static func loadFontMeta(path: String) -> FontMeta? {
        let key = FontLoader.fontCacheKey(for: path)
        metaCacheLock.lock()
        let cached = metaCache[key]
        metaCacheLock.unlock()
        if let cached = cached { return cached }
        return FontLoader.withFontBytes(path: path, fallback: nil) { ptr, len -> FontMeta? in
            guard let infoPtr = tp_load_font(ptr, len) else { return nil }
            defer { tp_free_font_info(infoPtr) }
            let info = infoPtr.pointee

            let familyName = info.family_name != nil ? String(cString: info.family_name) : ""
            let subfamilyName = info.subfamily_name != nil ? String(cString: info.subfamily_name) : "Regular"
            let isItalic = (info.fs_selection & 1) != 0
            let isVariable = info.is_variable

            var hasItal = false
            var hasWght = false
            var hasSlnt = false
            var slntItalicValue: Double = 0
            if let axesJSON = info.axes_json != nil ? String(cString: info.axes_json) : nil,
               let axesData = axesJSON.data(using: .utf8),
               let axes = try? JSONSerialization.jsonObject(with: axesData) as? [[String: Any]] {
                for axis in axes {
                    if let tag = axis["tag"] as? String {
                        if tag == "ital" { hasItal = true }
                        if tag == "wght" { hasWght = true }
                        if tag == "slnt" {
                            hasSlnt = true
                            let minVal = axis["min"] as? Double ?? 0
                            let maxVal = axis["max"] as? Double ?? 0
                            slntItalicValue = minVal < 0 ? minVal : maxVal
                        }
                    }
                }
            }

            let meta = FontMeta(
                path: path, familyName: familyName, subfamilyName: subfamilyName,
                weight: Int(info.weight), isItalic: isItalic, isVariable: isVariable,
                hasItalAxis: hasItal, hasWghtAxis: hasWght,
                hasSlntAxis: hasSlnt, slntItalicValue: slntItalicValue
            )
            metaCacheLock.lock()
            metaCache[key] = meta
            metaCacheLock.unlock()
            return meta
        }
    }

    /// Family key for pairing comparisons. Some families bake style words into
    /// the family name ("IvyMazarin Regular", "Chronicle Bold"), which made
    /// cross-style matches fail; strip trailing RIBBI words before comparing.
    static func familyKey(_ name: String) -> String {
        var words = name.split(separator: " ")
        while let last = words.last, last == "Regular" || last == "Italic" || last == "Bold" {
            words.removeLast()
        }
        return words.isEmpty ? name : words.joined(separator: " ")
    }

    private static func sameFamily(_ a: FontMeta, _ b: FontMeta) -> Bool {
        familyKey(a.familyName) == familyKey(b.familyName)
    }

    static func detectPairing(
        fontPath: String,
        axisValues: [String: Double]?,
        allFontPaths: [String],
        allAxisValues: [String: [Double]]? = nil
    ) -> Pairing? {
        guard let currentMeta = loadFontMeta(path: fontPath) else { return nil }

        let allMeta = allFontPaths.compactMap { loadFontMeta(path: $0) }

        // 1) Static Regular/Bold pairing: generated from the Regular. The bold
        // partner matches by subfamily name or by weight 700 — style-linked
        // families often name their Bold's subfamily "Regular" too.
        if currentMeta.subfamilyName == "Regular" && currentMeta.weight == 400
            && !currentMeta.isItalic && !currentMeta.isVariable {
            if let boldMatch = allMeta.first(where: {
                sameFamily($0, currentMeta)
                && ($0.subfamilyName == "Bold" || $0.weight == 700)
                && !$0.isItalic
                && $0.path != currentMeta.path
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
                    sameFamily($0, currentMeta)
                    && $0.weight == currentMeta.weight
                    && !$0.isItalic
                    && !$0.isVariable
                }) {
                    return .staticUprightItalic(upright: uprightMatch.path, italic: currentMeta.path)
                }
            } else if !currentMeta.isItalic && currentMeta.weight != 400 {
                // Weight 400 is excluded: its U/I pairing is generated from
                // the Italic (branch above) — without the exclusion a
                // Regular+Italic family rendered the identical pairing twice.
                if let italicMatch = allMeta.first(where: {
                    sameFamily($0, currentMeta)
                    && $0.weight == currentMeta.weight
                    && $0.isItalic
                    && !$0.isVariable
                }) {
                    return .staticUprightItalic(upright: currentMeta.path, italic: italicMatch.path)
                }
            }
        }

        // 3) Variable font at an explicitly italic/slanted position: pair the
        // upright with this position (generated from the italic side).
        if currentMeta.hasItalAxis {
            let italVal = axisValues?["ital"] ?? 0
            if italVal != 0 {
                return .variableItal(upright: 0, italic: italVal)
            }
        }
        if currentMeta.hasSlntAxis {
            let slntVal = axisValues?["slnt"] ?? 0
            if slntVal != 0 {
                return .variableSlnt(upright: 0, italic: slntVal)
            }
        }

        // 4) Variable font wght axis at a Bold-like position (600–800): pair
        // only with a regular-ish weight the user actually selected — never
        // fabricate one. Heavier weights (Black etc.) get no regular pairing.
        if currentMeta.hasWghtAxis {
            let wghtVal = axisValues?["wght"] ?? 400
            if wghtVal >= 600 && wghtVal <= 800 {
                let selectedWghts = allAxisValues?["wght"] ?? []
                let regularish = selectedWghts
                    .filter { $0 >= 300 && $0 <= 500 }
                    .min(by: { abs($0 - 400) < abs($1 - 400) })
                if let regular = regularish {
                    return .variableWght(regular: regular, bold: wghtVal)
                }
            }
        }

        // 5) Variable font upright with an italic/slant axis: pair with the
        // italic end — unless the user selected an italic position, in which
        // case that combination generates the pairing (case 3).
        if currentMeta.hasItalAxis {
            let selectedItals = allAxisValues?["ital"] ?? []
            if !selectedItals.contains(where: { $0 != 0 }) {
                return .variableItal(upright: 0, italic: 1)
            }
        }
        if currentMeta.hasSlntAxis, currentMeta.slntItalicValue != 0 {
            let selectedSlnts = allAxisValues?["slnt"] ?? []
            if !selectedSlnts.contains(where: { $0 != 0 }) {
                return .variableSlnt(upright: 0, italic: currentMeta.slntItalicValue)
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
        // — unless Bold has a same-weight italic partner: then Bold still
        // generates the Bold/Bold Italic pairing (RIBBI needs R/I, R/B, B/BI).
        if meta.subfamilyName == "Bold" {
            let hasRegular = allMeta.contains {
                sameFamily($0, meta) && $0.subfamilyName == "Regular" && $0.weight == 400
                    && !$0.isItalic && !$0.isVariable
            }
            let hasItalicPartner = allMeta.contains {
                sameFamily($0, meta) && $0.weight == meta.weight && $0.isItalic && !$0.isVariable
            }
            if hasRegular && !hasItalicPartner {
                return true
            }
        }

        // Skip non-Regular-weight italic if matching upright exists (U/I generated from upright)
        if meta.isItalic && meta.weight != 400 {
            if allMeta.contains(where: {
                sameFamily($0, meta) && $0.weight == meta.weight && !$0.isItalic && !$0.isVariable
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

        // A pairing only ever uses two fonts (primary + alternate). Resolve them
        // once here instead of re-creating a CTFont per word — makeFont re-parses
        // the font file from disk, so per-word creation made every page O(words)
        // disk reads when only two fonts are needed.
        func styleFont(alternate: Bool) -> CTFont? {
            switch pairing {
            case .staticUprightItalic(let upright, let italic):
                return FontLoader.makeFont(path: alternate ? italic : upright, size: fontSize, features: otFeatures, variations: nil)
            case .staticRegularBold(let regular, let bold):
                return FontLoader.makeFont(path: alternate ? bold : regular, size: fontSize, features: otFeatures, variations: nil)
            case .variableItal(let uprightVal, let italicVal):
                var v = baseVariations ?? [:]
                v["ital"] = alternate ? italicVal : uprightVal
                return FontLoader.makeFont(path: fontPath, size: fontSize, features: otFeatures, variations: v)
            case .variableSlnt(let uprightVal, let italicVal):
                var v = baseVariations ?? [:]
                v["slnt"] = alternate ? italicVal : uprightVal
                return FontLoader.makeFont(path: fontPath, size: fontSize, features: otFeatures, variations: v)
            case .variableWght(let regularVal, let boldVal):
                var v = baseVariations ?? [:]
                v["wght"] = alternate ? boldVal : regularVal
                return FontLoader.makeFont(path: fontPath, size: fontSize, features: otFeatures, variations: v)
            }
        }
        let primaryFont = styleFont(alternate: false)
        let alternateFont = styleFont(alternate: true)

        var useAlternate = false
        var nextSwitch = Int.random(in: 1...4, using: &rng)
        var wordCount = 0

        for word in words {
            let wordStr = String(word) + " "

            // Fall back to the other style if one font failed to load, so text
            // is never silently dropped.
            guard let resolvedFont = (useAlternate ? alternateFont : primaryFont) ?? primaryFont ?? alternateFont else { continue }

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

    /// Human-readable summary of a detected pairing for the page footer.
    static func describe(pairing: Pairing) -> String {
        func fmt(_ v: Double) -> String {
            v == v.rounded() ? String(Int(v)) : String(format: "%.1f", v)
        }
        // Style-linked families can name a 700-weight font "Regular"; append
        // the weight so footers like "Regular + Regular" stay readable.
        func styleLabel(_ path: String, fallback: String) -> String {
            guard let meta = loadFontMeta(path: path) else { return fallback }
            if (meta.subfamilyName == "Regular" || meta.subfamilyName == "Italic") && meta.weight != 400 {
                return "\(meta.subfamilyName) \(meta.weight)"
            }
            return meta.subfamilyName
        }
        switch pairing {
        case .staticUprightItalic(let upright, let italic):
            return "\(styleLabel(upright, fallback: "Upright")) + \(styleLabel(italic, fallback: "Italic"))"
        case .staticRegularBold(let regular, let bold):
            return "\(styleLabel(regular, fallback: "Regular")) + \(styleLabel(bold, fallback: "Bold"))"
        case .variableItal(let upright, let italic):
            return "ital \(fmt(upright)) + ital \(fmt(italic))"
        case .variableSlnt(let upright, let italic):
            return "slnt \(fmt(upright)) + slnt \(fmt(italic))"
        case .variableWght(let regular, let bold):
            return "wght \(fmt(regular)) + wght \(fmt(bold))"
        }
    }

    static func decodeManualPairings(json: String) -> [ManualPairing] {
        guard !json.isEmpty, let data = json.data(using: .utf8) else { return [] }
        return (try? JSONDecoder().decode([ManualPairing].self, from: data)) ?? []
    }

    static func buildWeightedMixedAttributedString(
        text: String,
        styles: [(font: CTFont, weight: Double)],
        fontSize: CGFloat,
        alignment: CTTextAlignment,
        tracking: CGFloat,
        lineHeight: CGFloat?,
        otFeatures: [String: Bool]?
    ) -> NSMutableAttributedString {
        var rng = SeededRNG(seed: dualStyleSeed)
        let words = text.split(separator: " ", omittingEmptySubsequences: false)
        let result = NSMutableAttributedString()
        let kernDisabled = otFeatures?["kern"] == false

        // All-zero weights would make every style unreachable — treat as equal.
        let weights = styles.map(\.weight).reduce(0, +) > 0
            ? styles.map(\.weight)
            : Array(repeating: 1.0, count: styles.count)

        var currentIndex = pickWeightedIndex(weights: weights, using: &rng)
        var nextSwitch = Int.random(in: 1...4, using: &rng)
        var wordCount = 0

        for word in words {
            let wordStr = String(word) + " "

            TextRenderer.appendText(
                to: result,
                text: wordStr,
                font: styles[currentIndex].font,
                fontSize: fontSize,
                alignment: alignment,
                tracking: tracking,
                lineHeight: lineHeight,
                foregroundColor: CGColor(gray: 0, alpha: 1),
                kernDisabled: kernDisabled
            )

            wordCount += 1
            if wordCount >= nextSwitch {
                currentIndex = pickWeightedIndex(weights: weights, using: &rng)
                wordCount = 0
                nextSwitch = Int.random(in: 1...4, using: &rng)
            }
        }

        return result
    }

    private static func pickWeightedIndex(weights: [Double], using rng: inout SeededRNG) -> Int {
        let total = weights.reduce(0, +)
        var remaining = Double.random(in: 0..<total, using: &rng)
        for (i, weight) in weights.enumerated() {
            remaining -= weight
            if remaining < 0 { return i }
        }
        return weights.count - 1
    }
}

struct SeededRNG: RandomNumberGenerator {
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
