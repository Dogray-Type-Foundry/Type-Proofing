import Foundation

struct MarkupParser {

    enum TokenKind: String {
        case heading1, heading2
        case bold, italic, boldItalic
        case attrSpan
        case plain
        case pageBreak, columnBreak
    }

    struct Token {
        let kind: TokenKind
        var text: String = ""
        var attrs: [String: String] = [:]
    }

    // MARK: - Escape / Restore

    private static let escapePairs: [(String, String)] = [
        ("\\\\", "\u{E000}"),
        ("\\*", "\u{E001}"),
        ("\\#", "\u{E002}"),
        ("\\[", "\u{E003}"),
        ("\\]", "\u{E004}"),
        ("\\{", "\u{E005}"),
        ("\\}", "\u{E006}"),
    ]

    private static let restoreMap: [Character: Character] = [
        "\u{E000}": "\\",
        "\u{E001}": "*",
        "\u{E002}": "#",
        "\u{E003}": "[",
        "\u{E004}": "]",
        "\u{E005}": "{",
        "\u{E006}": "}",
    ]

    private static func escape(_ text: String) -> String {
        var result = text
        for (old, new) in escapePairs {
            result = result.replacingOccurrences(of: old, with: new)
        }
        return result
    }

    private static func restore(_ text: String) -> String {
        var result = ""
        result.reserveCapacity(text.count)
        for ch in text {
            if let replacement = restoreMap[ch] {
                result.append(replacement)
            } else {
                result.append(ch)
            }
        }
        return result
    }

    // MARK: - Tokenizer

    private static let inlinePattern = try! NSRegularExpression(
        pattern: #"\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|\[([^\]]+)\]\{([^}]+)\}"#
    )

    static func tokenize(_ rawText: String) -> [Token] {
        let escaped = escape(rawText)
        let lines = escaped.components(separatedBy: "\n")
        var tokens: [Token] = []

        for (i, line) in lines.enumerated() {
            let stripped = line.trimmingCharacters(in: .whitespaces)

            if stripped.isEmpty {
                // blank line
            } else if stripped == "#pagebreak()" {
                tokens.append(Token(kind: .pageBreak))
            } else if stripped == "#colbreak()" {
                tokens.append(Token(kind: .columnBreak))
            } else if line.hasPrefix("## ") {
                tokens.append(Token(kind: .heading2, text: restore(String(line.dropFirst(3)))))
            } else if line.hasPrefix("# ") {
                tokens.append(Token(kind: .heading1, text: restore(String(line.dropFirst(2)))))
            } else {
                tokenizeInline(line, into: &tokens)
            }

            if i < lines.count - 1 {
                tokens.append(Token(kind: .plain, text: "\n"))
            }
        }

        return tokens
    }

    private static func tokenizeInline(_ line: String, into tokens: inout [Token]) {
        let nsLine = line as NSString
        let range = NSRange(location: 0, length: nsLine.length)
        let matches = inlinePattern.matches(in: line, range: range)

        var lastEnd = 0
        for match in matches {
            if match.range.location > lastEnd {
                let plainRange = NSRange(location: lastEnd, length: match.range.location - lastEnd)
                tokens.append(Token(kind: .plain, text: restore(nsLine.substring(with: plainRange))))
            }

            if match.range(at: 1).location != NSNotFound {
                tokens.append(Token(kind: .boldItalic, text: restore(nsLine.substring(with: match.range(at: 1)))))
            } else if match.range(at: 2).location != NSNotFound {
                tokens.append(Token(kind: .bold, text: restore(nsLine.substring(with: match.range(at: 2)))))
            } else if match.range(at: 3).location != NSNotFound {
                tokens.append(Token(kind: .italic, text: restore(nsLine.substring(with: match.range(at: 3)))))
            } else if match.range(at: 4).location != NSNotFound {
                let text = restore(nsLine.substring(with: match.range(at: 4)))
                let attrStr = nsLine.substring(with: match.range(at: 5))
                let attrs = parseAttrs(restore(attrStr))
                tokens.append(Token(kind: .attrSpan, text: text, attrs: attrs))
            }

            lastEnd = match.range.location + match.range.length
        }

        if lastEnd < nsLine.length {
            let remaining = NSRange(location: lastEnd, length: nsLine.length - lastEnd)
            tokens.append(Token(kind: .plain, text: restore(nsLine.substring(with: remaining))))
        }
    }

    // MARK: - Attribute Parsing

    static func parseAttrs(_ attrString: String) -> [String: String] {
        var parts: [String] = []
        var current = ""
        var inQuotes = false

        for ch in attrString {
            if ch == "\"" {
                inQuotes.toggle()
                current.append(ch)
            } else if ch == "," && !inQuotes {
                parts.append(current.trimmingCharacters(in: .whitespaces))
                current = ""
            } else {
                current.append(ch)
            }
        }
        if !current.isEmpty {
            parts.append(current.trimmingCharacters(in: .whitespaces))
        }

        var result: [String: String] = [:]
        for part in parts {
            guard let colonIdx = part.firstIndex(of: ":") else { continue }
            let key = part[part.startIndex..<colonIdx].trimmingCharacters(in: .whitespaces)
            let value = part[part.index(after: colonIdx)...].trimmingCharacters(in: .whitespaces).trimmingCharacters(in: CharacterSet(charactersIn: "\"'"))
            result[key] = value
        }
        return result
    }

    // MARK: - Color Parsing

    static func parseHexColor(_ hex: String) -> (CGFloat, CGFloat, CGFloat)? {
        var hexStr = hex.trimmingCharacters(in: .whitespaces)
        if hexStr.hasPrefix("#") { hexStr = String(hexStr.dropFirst()) }
        if hexStr.count == 3 {
            hexStr = String(hexStr.flatMap { [$0, $0] })
        }
        guard hexStr.count == 6,
              let value = UInt32(hexStr, radix: 16) else { return nil }
        let r = CGFloat((value >> 16) & 0xFF) / 255
        let g = CGFloat((value >> 8) & 0xFF) / 255
        let b = CGFloat(value & 0xFF) / 255
        return (r, g, b)
    }
}
