import Foundation
import TPNative

final class WordSivBridge {
    private var handle: OpaquePointer?

    init(seed: UInt64 = 987654) {
        handle = wsv_create(seed)
    }

    deinit {
        if let h = handle { wsv_free(h) }
    }

    func reseed(_ seed: UInt64) {
        guard let h = handle else { return }
        wsv_seed(h, seed)
    }

    func text(glyphs: String, paragraphs: Int = 2, numbers: Double = 0, rndPunc: Double = 0, paraSep: String = " ", vocab: String? = nil) -> String {
        guard let h = handle else { return "" }
        guard let result = wsv_text(h, glyphs, UInt32(paragraphs), numbers, rndPunc, paraSep, vocab) else { return "" }
        let str = String(cString: result)
        wsv_free_string(result)
        return str
    }

    func words(glyphs: String, caseStr: String = "", contains: String = "", count: Int = 10, minWL: Int = 1, maxWL: Int = 30, vocab: String? = nil, startsWith: String? = nil, endsWith: String? = nil, inner: String? = nil) -> String {
        guard let h = handle else { return "" }
        let caseArg = caseStr.isEmpty ? nil : caseStr
        let containsArg = contains.isEmpty ? nil : contains
        guard let result = wsv_words(h, glyphs, caseArg, containsArg, UInt32(count), UInt32(minWL), UInt32(maxWL), vocab, startsWith, endsWith, inner) else { return "" }
        let str = String(cString: result)
        wsv_free_string(result)
        return str
    }

    func topWord(glyphs: String, caseStr: String = "", regexp: String = "", idx: Int = 0, minWL: Int = 1, vocab: String? = nil) -> String {
        guard let h = handle else { return "" }
        let caseArg = caseStr.isEmpty ? nil : caseStr
        let regexpArg = regexp.isEmpty ? nil : regexp
        guard let result = wsv_top_word(h, glyphs, caseArg, regexpArg, UInt32(idx), UInt32(minWL), vocab) else { return "" }
        let str = String(cString: result)
        wsv_free_string(result)
        return str
    }
}
