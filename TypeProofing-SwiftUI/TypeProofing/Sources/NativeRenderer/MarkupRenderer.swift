import CoreGraphics
import CoreText
import Foundation

struct MarkupRenderer {

    struct RenderConfig {
        let fontPath: String
        let fontSize: CGFloat
        let alignment: CTTextAlignment
        let tracking: CGFloat
        let lineHeight: CGFloat?
        let otFeatures: [String: Bool]?
        let variations: [String: Double]?
        let allFontPaths: [String]
    }

    struct PageSegments {
        let pages: [[NSAttributedString]]
    }

    static func buildPages(
        tokens: [MarkupParser.Token],
        config: RenderConfig
    ) -> PageSegments {
        var pages: [[NSAttributedString]] = []
        var currentPage: [NSAttributedString] = []
        var currentString = NSMutableAttributedString()
        var skipNextNewline = false

        for token in tokens {
            if token.kind == .pageBreak {
                currentPage.append(currentString)
                pages.append(currentPage)
                currentPage = []
                currentString = NSMutableAttributedString()
                skipNextNewline = true
                continue
            }

            if token.kind == .columnBreak {
                currentPage.append(currentString)
                currentString = NSMutableAttributedString()
                skipNextNewline = true
                continue
            }

            if skipNextNewline && token.kind == .plain && token.text == "\n" {
                skipNextNewline = false
                continue
            }
            skipNextNewline = false

            switch token.kind {
            case .plain:
                appendRun(to: currentString, text: token.text, config: config)

            case .heading1, .heading2:
                let multiplier: CGFloat = token.kind == .heading1 ? 2.5 : 1.8
                let headingSize = min(config.fontSize * multiplier, 90)
                var headingConfig = config
                headingConfig = RenderConfig(
                    fontPath: config.fontPath,
                    fontSize: headingSize,
                    alignment: config.alignment,
                    tracking: config.tracking,
                    lineHeight: config.lineHeight.map { $0 / config.fontSize * headingSize },
                    otFeatures: config.otFeatures,
                    variations: config.variations,
                    allFontPaths: config.allFontPaths
                )
                appendRun(to: currentString, text: token.text, config: headingConfig)

            case .bold:
                let resolved = resolveBold(config: config)
                appendRun(to: currentString, text: token.text, config: config,
                          fontPathOverride: resolved.fontPath,
                          variationOverride: resolved.variations)

            case .italic:
                let resolved = resolveItalic(config: config)
                appendRun(to: currentString, text: token.text, config: config,
                          fontPathOverride: resolved.fontPath,
                          variationOverride: resolved.variations)

            case .boldItalic:
                let resolved = resolveBoldItalic(config: config)
                appendRun(to: currentString, text: token.text, config: config,
                          fontPathOverride: resolved.fontPath,
                          variationOverride: resolved.variations)

            case .attrSpan:
                let overrides = buildAttrOverrides(attrs: token.attrs, config: config)
                appendRun(to: currentString, text: token.text, config: config,
                          fontPathOverride: overrides.fontPath,
                          fontSizeOverride: overrides.fontSize,
                          variationOverride: overrides.variations,
                          colorOverride: overrides.color,
                          trackingOverride: overrides.tracking,
                          otFeaturesOverride: overrides.otFeatures)

            case .pageBreak, .columnBreak:
                break
            }
        }

        currentPage.append(currentString)
        pages.append(currentPage)
        return PageSegments(pages: pages)
    }

    private static func appendRun(
        to attrString: NSMutableAttributedString,
        text: String,
        config: RenderConfig,
        fontPathOverride: String? = nil,
        fontSizeOverride: CGFloat? = nil,
        variationOverride: [String: Double]? = nil,
        colorOverride: CGColor? = nil,
        trackingOverride: CGFloat? = nil,
        otFeaturesOverride: [String: Bool]? = nil
    ) {
        let fontPath = fontPathOverride ?? config.fontPath
        let fontSize = fontSizeOverride ?? config.fontSize
        let variations = variationOverride ?? config.variations
        let color = colorOverride ?? CGColor(gray: 0, alpha: 1)
        let tracking = trackingOverride ?? config.tracking
        let features = otFeaturesOverride ?? config.otFeatures

        guard let font = FontLoader.makeFont(
            path: fontPath,
            size: fontSize,
            features: features,
            variations: variations
        ) else { return }

        let kernDisabled = features?["kern"] == false
        TextRenderer.appendText(
            to: attrString,
            text: text,
            font: font,
            fontSize: fontSize,
            alignment: config.alignment,
            tracking: tracking,
            lineHeight: config.lineHeight,
            foregroundColor: color,
            kernDisabled: kernDisabled
        )
    }

    // MARK: - Style Resolution

    private struct StyleResolution {
        var fontPath: String?
        var variations: [String: Double]?
    }

    private static func resolveBold(config: RenderConfig) -> StyleResolution {
        if hasAxis(fontPath: config.fontPath, tag: "wght") {
            var v = config.variations ?? [:]
            v["wght"] = 700
            return StyleResolution(variations: v)
        }
        if let path = findFontByStyle(keywords: ["Bold"], excluding: ["Italic", "Oblique"], config: config) {
            return StyleResolution(fontPath: path)
        }
        return StyleResolution()
    }

    private static func resolveItalic(config: RenderConfig) -> StyleResolution {
        if hasAxis(fontPath: config.fontPath, tag: "ital") {
            var v = config.variations ?? [:]
            v["ital"] = 1
            return StyleResolution(variations: v)
        }
        if hasAxis(fontPath: config.fontPath, tag: "slnt") {
            var v = config.variations ?? [:]
            v["slnt"] = -12
            return StyleResolution(variations: v)
        }
        if let path = findFontByStyle(keywords: ["Italic", "Oblique"], excluding: ["Bold", "Black", "Heavy"], config: config) {
            return StyleResolution(fontPath: path)
        }
        return StyleResolution()
    }

    private static func resolveBoldItalic(config: RenderConfig) -> StyleResolution {
        let hasWght = hasAxis(fontPath: config.fontPath, tag: "wght")
        let hasItal = hasAxis(fontPath: config.fontPath, tag: "ital")
        let hasSlnt = hasAxis(fontPath: config.fontPath, tag: "slnt")

        if hasWght && (hasItal || hasSlnt) {
            var v = config.variations ?? [:]
            v["wght"] = 700
            if hasItal { v["ital"] = 1 } else { v["slnt"] = -12 }
            return StyleResolution(variations: v)
        }
        if let path = findFontByStyle(keywords: ["Bold", "Italic"], excluding: [], config: config) {
            return StyleResolution(fontPath: path)
        }
        let bold = resolveBold(config: config)
        return bold
    }

    private static func findFontByStyle(keywords: [String], excluding: [String], config: RenderConfig) -> String? {
        let baseFamilyName = fontFamilyName(path: config.fontPath)
        guard !baseFamilyName.isEmpty else { return nil }

        for path in config.allFontPaths where path != config.fontPath {
            let family = fontFamilyName(path: path)
            guard family == baseFamilyName else { continue }
            let style = fontStyleName(path: path).lowercased()
            let matchesAll = keywords.allSatisfy { style.contains($0.lowercased()) }
            let matchesExcluded = excluding.contains { style.contains($0.lowercased()) }
            if matchesAll && !matchesExcluded { return path }
        }
        return nil
    }

    private static func findFontByStyleName(_ styleName: String, config: RenderConfig) -> String? {
        let target = styleName.lowercased()
        let baseFamilyName = fontFamilyName(path: config.fontPath)

        for path in config.allFontPaths {
            let style = fontStyleName(path: path).lowercased()
            if style == target {
                if baseFamilyName.isEmpty || fontFamilyName(path: path) == baseFamilyName {
                    return path
                }
            }
        }
        for path in config.allFontPaths {
            let style = fontStyleName(path: path).lowercased()
            if style.contains(target) || target.contains(style) {
                if baseFamilyName.isEmpty || fontFamilyName(path: path) == baseFamilyName {
                    return path
                }
            }
        }
        return nil
    }

    private static func fontFamilyName(path: String) -> String {
        guard let font = FontLoader.makeFont(path: path, size: 12, features: nil, variations: nil) else { return "" }
        return CTFontCopyFamilyName(font) as String
    }

    private static func fontStyleName(path: String) -> String {
        let url = URL(fileURLWithPath: path) as CFURL
        guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url) as? [CTFontDescriptor],
              let desc = descriptors.first else { return "" }
        return CTFontDescriptorCopyAttribute(desc, kCTFontStyleNameAttribute) as? String ?? ""
    }

    private static func hasAxis(fontPath: String, tag: String) -> Bool {
        guard let font = FontLoader.makeFont(path: fontPath, size: 12, features: nil, variations: nil) else {
            return false
        }
        let axes = CTFontCopyVariationAxes(font) as? [[String: Any]] ?? []
        let targetID = axisTagToID(tag)
        return axes.contains { ($0[kCTFontVariationAxisIdentifierKey as String] as? Int) == targetID }
    }

    private static func axisTagToID(_ tag: String) -> Int {
        let bytes = Array(tag.utf8)
        guard bytes.count == 4 else { return 0 }
        return Int(bytes[0]) << 24 | Int(bytes[1]) << 16 | Int(bytes[2]) << 8 | Int(bytes[3])
    }

    // MARK: - Attribute Span Overrides

    struct AttrOverrides {
        var fontPath: String?
        var fontSize: CGFloat?
        var variations: [String: Double]?
        var color: CGColor?
        var tracking: CGFloat?
        var otFeatures: [String: Bool]?
    }

    private static func buildAttrOverrides(attrs: [String: String], config: RenderConfig) -> AttrOverrides {
        var result = AttrOverrides()
        var variations = config.variations ?? [:]
        var hasVariations = false

        for (key, value) in attrs {
            switch key {
            case "wght", "opsz", "wdth", "ital", "slnt":
                if let v = Double(value) {
                    variations[key] = v
                    hasVariations = true
                }
            case "size":
                result.fontSize = CGFloat(Double(value) ?? Double(config.fontSize))
            case "color":
                if let rgb = MarkupParser.parseHexColor(value) {
                    result.color = CGColor(red: rgb.0, green: rgb.1, blue: rgb.2, alpha: 1)
                }
            case "tracking":
                result.tracking = CGFloat(Double(value) ?? Double(config.tracking))
            case "style":
                if let path = findFontByStyleName(value, config: config) {
                    result.fontPath = path
                }
            case "feat":
                var features = config.otFeatures ?? [:]
                for tag in value.components(separatedBy: ",").map({ $0.trimmingCharacters(in: .whitespaces) }) {
                    if tag.hasPrefix("-") {
                        features[String(tag.dropFirst())] = false
                    } else {
                        features[tag] = true
                    }
                }
                result.otFeatures = features
            default:
                break
            }
        }

        if hasVariations {
            result.variations = variations
        }

        return result
    }
}
