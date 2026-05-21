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
                    variations: config.variations
                )
                appendRun(to: currentString, text: token.text, config: headingConfig)

            case .bold:
                let boldVariations = resolveBoldVariations(config: config)
                appendRun(to: currentString, text: token.text, config: config, variationOverride: boldVariations)

            case .italic:
                let italicVariations = resolveItalicVariations(config: config)
                appendRun(to: currentString, text: token.text, config: config, variationOverride: italicVariations)

            case .boldItalic:
                var merged = resolveBoldVariations(config: config)
                for (k, v) in resolveItalicVariations(config: config) {
                    merged[k] = v
                }
                appendRun(to: currentString, text: token.text, config: config, variationOverride: merged)

            case .attrSpan:
                let overrides = buildAttrOverrides(attrs: token.attrs, config: config)
                appendRun(to: currentString, text: token.text, config: config,
                          fontSizeOverride: overrides.fontSize,
                          variationOverride: overrides.variations,
                          colorOverride: overrides.color,
                          trackingOverride: overrides.tracking)

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
        fontSizeOverride: CGFloat? = nil,
        variationOverride: [String: Double]? = nil,
        colorOverride: CGColor? = nil,
        trackingOverride: CGFloat? = nil
    ) {
        let fontSize = fontSizeOverride ?? config.fontSize
        let variations = variationOverride ?? config.variations
        let color = colorOverride ?? CGColor(gray: 0, alpha: 1)
        let tracking = trackingOverride ?? config.tracking

        guard let font = FontLoader.makeFont(
            path: config.fontPath,
            size: fontSize,
            features: config.otFeatures,
            variations: variations
        ) else { return }

        let kernDisabled = config.otFeatures?["kern"] == false
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

    private static func resolveBoldVariations(config: RenderConfig) -> [String: Double] {
        var v = config.variations ?? [:]
        if hasAxis(fontPath: config.fontPath, tag: "wght") {
            v["wght"] = 700
        }
        return v
    }

    private static func resolveItalicVariations(config: RenderConfig) -> [String: Double] {
        var v = config.variations ?? [:]
        if hasAxis(fontPath: config.fontPath, tag: "ital") {
            v["ital"] = 1
        } else if hasAxis(fontPath: config.fontPath, tag: "slnt") {
            v["slnt"] = -12
        }
        return v
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

    struct AttrOverrides {
        var fontSize: CGFloat?
        var variations: [String: Double]?
        var color: CGColor?
        var tracking: CGFloat?
    }

    private static func buildAttrOverrides(attrs: [String: String], config: RenderConfig) -> AttrOverrides {
        var result = AttrOverrides()
        var variations = config.variations ?? [:]
        var hasVariations = false

        for (key, value) in attrs {
            switch key {
            case "wght", "opsz", "wdth":
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
