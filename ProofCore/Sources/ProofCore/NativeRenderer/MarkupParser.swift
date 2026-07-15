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

    // MARK: - Escapes

    /// Characters that `\` escapes. Escapes are resolved inline while
    /// scanning — the previous implementation smuggled them through
    /// U+E000–E006 sentinels and mapped every sentinel back to punctuation at
    /// the end, which corrupted Private Use Area characters (perfectly
    /// legitimate input when proofing fonts).
    private static let escapableChars: Set<Character> = ["\\", "*", "#", "[", "]", "{", "}"]

    /// Resolves `\X` sequences in text used verbatim (headings). Backslashes
    /// before non-escapable characters stay as-is.
    private static func unescape(_ text: String) -> String {
        let chars = Array(text)
        var result = ""
        result.reserveCapacity(chars.count)
        var i = 0
        while i < chars.count {
            if chars[i] == "\\", i + 1 < chars.count, escapableChars.contains(chars[i + 1]) {
                result.append(chars[i + 1])
                i += 2
            } else {
                result.append(chars[i])
                i += 1
            }
        }
        return result
    }

    // MARK: - Tokenizer

    static func tokenize(_ rawText: String) -> [Token] {
        let lines = rawText.components(separatedBy: "\n")
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
                tokens.append(Token(kind: .heading2, text: unescape(String(line.dropFirst(3)))))
            } else if line.hasPrefix("# ") {
                tokens.append(Token(kind: .heading1, text: unescape(String(line.dropFirst(2)))))
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
        let chars = Array(line)
        var i = 0
        var plain = ""

        func flushPlain() {
            if !plain.isEmpty {
                tokens.append(Token(kind: .plain, text: plain))
                plain = ""
            }
        }

        while i < chars.count {
            let ch = chars[i]

            if ch == "\\", i + 1 < chars.count, escapableChars.contains(chars[i + 1]) {
                plain.append(chars[i + 1])
                i += 2
                continue
            }

            if ch == "*" {
                var run = 0
                while i + run < chars.count && chars[i + run] == "*" { run += 1 }
                // Longest marker first, mirroring the old regex alternation
                // (***…*** | **…** | *…*).
                var matched = false
                for stars in stride(from: min(run, 3), through: 1, by: -1) {
                    if let (content, next) = scanEmphasis(chars, from: i + stars, closingRun: stars) {
                        flushPlain()
                        let kind: TokenKind = stars == 3 ? .boldItalic : (stars == 2 ? .bold : .italic)
                        tokens.append(Token(kind: kind, text: content))
                        i = next
                        matched = true
                        break
                    }
                }
                if !matched {
                    plain.append(String(repeating: "*", count: run))
                    i += run
                }
                continue
            }

            if ch == "[", let span = scanAttrSpan(chars, from: i) {
                flushPlain()
                tokens.append(Token(kind: .attrSpan, text: span.text, attrs: parseAttrs(span.attrs)))
                i = span.next
                continue
            }

            plain.append(ch)
            i += 1
        }

        flushPlain()
    }

    /// Scans for a `closingRun`-star delimiter starting at `from`, resolving
    /// escapes inline. Returns the (non-empty) content and the index just past
    /// the closing stars, or nil if the marker never closes on this line.
    private static func scanEmphasis(_ chars: [Character], from: Int, closingRun: Int) -> (content: String, next: Int)? {
        var content = ""
        var i = from
        while i < chars.count {
            if chars[i] == "\\", i + 1 < chars.count, escapableChars.contains(chars[i + 1]) {
                content.append(chars[i + 1])
                i += 2
                continue
            }
            if chars[i] == "*", !content.isEmpty {
                var run = 0
                while i + run < chars.count && chars[i + run] == "*" { run += 1 }
                if run >= closingRun {
                    return (content, i + closingRun)
                }
            }
            content.append(chars[i])
            i += 1
        }
        return nil
    }

    /// Scans a `[text]{attrs}` span starting at the `[` at `from`. Both
    /// segments resolve escapes inline and must be non-empty.
    private static func scanAttrSpan(_ chars: [Character], from: Int) -> (text: String, attrs: String, next: Int)? {
        var text = ""
        var i = from + 1
        while i < chars.count, chars[i] != "]" {
            if chars[i] == "\\", i + 1 < chars.count, escapableChars.contains(chars[i + 1]) {
                text.append(chars[i + 1])
                i += 2
            } else {
                text.append(chars[i])
                i += 1
            }
        }
        guard !text.isEmpty, i < chars.count, i + 1 < chars.count, chars[i + 1] == "{" else { return nil }

        var attrs = ""
        var j = i + 2
        while j < chars.count, chars[j] != "}" {
            if chars[j] == "\\", j + 1 < chars.count, escapableChars.contains(chars[j + 1]) {
                attrs.append(chars[j + 1])
                j += 2
            } else {
                attrs.append(chars[j])
                j += 1
            }
        }
        guard !attrs.isEmpty, j < chars.count else { return nil }
        return (text, attrs, j + 1)
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
