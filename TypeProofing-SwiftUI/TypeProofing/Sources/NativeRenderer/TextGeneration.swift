import Foundation
import TPNative

struct TextGeneration {

    static let wordsivSeed: UInt64 = 987654

    private static let upperTemplate = Set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    private static let lowerTemplate = Set("abcdefghijklmnopqrstuvwxyz")

    static func generateTextProofString(
        characterSet: String,
        paragraphs: Int = 2,
        forceWordsiv: Bool = false,
        cat: CharacterCategories,
        fullCharacterSet: String,
        language: String? = nil,
        hoeflerStyle: Bool = false
    ) -> String {
        if characterSet.isEmpty { return "" }

        if let lang = language, (lang == "ar" || lang == "fa") {
            if hoeflerStyle {
                return generateHoeflerStyleArabicText(
                    characterSet: characterSet,
                    paragraphs: paragraphs,
                    language: lang,
                    fullCharacterSet: fullCharacterSet
                )
            }
            return generateArabicText(
                characterSet: characterSet,
                paragraphs: paragraphs,
                language: lang,
                fullCharacterSet: fullCharacterSet
            )
        }

        let upperSet = Set(cat.uniLu)
        let lowerSet = Set(cat.uniLl)

        if cat.uppercaseOnly
            && upperTemplate.isSubset(of: upperSet)
            && !forceWordsiv {
            return PremadeTexts.smallUpperText
        }

        if cat.lowercaseOnly
            && lowerTemplate.isSubset(of: lowerSet)
            && !forceWordsiv {
            return PremadeTexts.smallLowerText
        }

        if upperTemplate.isSubset(of: upperSet)
            && lowerTemplate.isSubset(of: lowerSet)
            && !forceWordsiv {
            return PremadeTexts.smallMixedText + " " + PremadeTexts.smallUpperText
        }

        if forceWordsiv || hoeflerStyle {
            return generateWordsivText(
                cat: cat,
                paragraphs: paragraphs,
                fullCharacterSet: fullCharacterSet,
                characterSet: characterSet,
                hoeflerStyle: hoeflerStyle
            )
        }

        if !cat.uppercaseOnly && !cat.lowercaseOnly {
            return generateWordsivText(
                cat: cat,
                paragraphs: paragraphs,
                fullCharacterSet: fullCharacterSet,
                characterSet: characterSet,
                hoeflerStyle: hoeflerStyle
            )
        }

        return generateWordsivText(
            cat: cat,
            paragraphs: paragraphs,
            fullCharacterSet: fullCharacterSet,
            characterSet: characterSet,
            hoeflerStyle: false
        )
    }

    private static func generateWordsivText(
        cat: CharacterCategories,
        paragraphs: Int,
        fullCharacterSet: String,
        characterSet: String,
        hoeflerStyle: Bool
    ) -> String {
        let wsv = WordSivBridge(seed: wordsivSeed)
        let vocab = "en"

        let glyphs = fullCharacterSet.isEmpty ? characterSet : fullCharacterSet
        let allGlyphs = cat.uniLu + cat.uniLl + cat.uniNd + cat.uniPo + cat.uniPc + cat.uniPd + cat.uniPi + cat.uniPf + "()"

        if hoeflerStyle {
            return generateHoeflerStyleText(wsv: wsv, cat: cat, glyphs: glyphs, allGlyphs: allGlyphs, paragraphs: paragraphs, vocab: vocab)
        }

        var caplc: [String] = []
        let lcBase = cat.uniLlBase.isEmpty ? cat.uniLl : cat.uniLlBase
        let ucBase = cat.uniLuBase.isEmpty ? cat.uniLu : cat.uniLuBase

        for u in ucBase {
            let capAndLower = String(u) + lcBase
            wsv.reseed(wordsivSeed)
            let capitalisedWords = wsv.words(glyphs: capAndLower, caseStr: "cap", count: 2, minWL: 5, maxWL: 14, vocab: vocab)
            if !capitalisedWords.isEmpty {
                caplc.append(capitalisedWords + " ")
            }
            let lcWords = wsv.words(glyphs: capAndLower, caseStr: "lc_force", contains: String(u).lowercased(), count: 4, minWL: 5, maxWL: 14, vocab: vocab)
            if !lcWords.isEmpty {
                caplc.append(lcWords + " ")
            }
        }

        let caplcStr = caplc.joined()
        let wsvText = wsv.text(glyphs: allGlyphs, paragraphs: paragraphs, numbers: 0.1, rndPunc: 0.1, vocab: vocab)

        return caplcStr + "\n\n" + wsvText + "\n\n" + wsvText.uppercased()
    }

    private static func generateHoeflerStyleText(
        wsv: WordSivBridge,
        cat: CharacterCategories,
        glyphs: String,
        allGlyphs: String,
        paragraphs: Int,
        vocab: String
    ) -> String {
        let ucBase = cat.uniLuBase.isEmpty ? cat.uniLu : cat.uniLuBase
        if ucBase.isEmpty { return wsv.text(glyphs: allGlyphs, paragraphs: paragraphs, vocab: vocab) }

        var lines: [String] = []

        for ucChar in ucBase {
            let lcChar = String(ucChar).lowercased()
            let capWord = wsv.topWord(glyphs: glyphs, caseStr: "cap", regexp: "\(ucChar).*", idx: 0, minWL: 5, vocab: vocab)
            let lcWords = wsv.words(glyphs: glyphs, caseStr: "lc", contains: lcChar, count: 4, minWL: 5, maxWL: 14, vocab: vocab)

            var line = ""
            if !capWord.isEmpty { line += capWord + " " }
            if !lcWords.isEmpty { line += lcWords }
            if !line.isEmpty { lines.append(line) }
        }

        let structured = lines.joined(separator: " ")
        let flowing = wsv.text(glyphs: allGlyphs, paragraphs: paragraphs, numbers: 0.1, rndPunc: 0.1, vocab: vocab)
        return structured + "\n\n" + flowing
    }

    private static func generateHoeflerStyleArabicText(
        characterSet: String,
        paragraphs: Int,
        language: String,
        fullCharacterSet: String
    ) -> String {
        let wsv = WordSivBridge(seed: wordsivSeed)
        let vocab = language
        let glyphs = fullCharacterSet.isEmpty ? characterSet : fullCharacterSet
        let charSet = Set(characterSet)

        var initClasses: [String] = []
        var mediClasses: [String] = []
        var finaClasses: [String] = []
        var isoClasses: [String] = []

        for (_, suffix, glyphNames) in arabicShapeGroups {
            var chars = ""
            for glyph in glyphNames {
                if let uc = arabicGlyphToUnicode[glyph], charSet.contains(uc) {
                    chars.append(uc)
                }
            }
            if chars.isEmpty { continue }

            switch suffix {
            case "init": initClasses.append(chars)
            case "medi": mediClasses.append(chars)
            case "fina": finaClasses.append(chars)
            case "":     isoClasses.append(chars)
            default: break
            }
        }

        var allWords: [String] = []
        var seen = Set<String>()

        func tryWord(regexp: String, minWL: Int = 3) {
            let w = wsv.topWord(glyphs: glyphs, regexp: regexp, idx: 0, minWL: minWL, vocab: vocab)
            if !w.isEmpty && !seen.contains(w) {
                allWords.append(w)
                seen.insert(w)
            }
        }

        for ic in initClasses {
            for mc in mediClasses {
                tryWord(regexp: "[\(ic)][\(mc)].*")
            }
        }

        for m1 in mediClasses {
            for m2 in mediClasses {
                tryWord(regexp: ".+[\(m1)][\(m2)].+", minWL: 4)
            }
        }

        for mc in mediClasses {
            for fc in finaClasses {
                tryWord(regexp: ".*[\(mc)][\(fc)]")
            }
        }

        for oc in isoClasses {
            for ic in initClasses {
                tryWord(regexp: "[\(oc)][\(ic)].*")
            }
        }

        for fc in finaClasses {
            for oc in isoClasses {
                tryWord(regexp: ".*[\(fc)][\(oc)]")
            }
        }

        if allWords.isEmpty {
            return characterSet.map { String($0) }.joined(separator: " ")
        }
        return allWords.joined(separator: " ")
    }

    private static let posForms = ["init", "medi", "fina"]

    private static func generateArabicText(
        characterSet: String,
        paragraphs: Int,
        language: String,
        fullCharacterSet: String
    ) -> String {
        let wsv = WordSivBridge(seed: wordsivSeed)
        let vocab = language
        let glyphs = fullCharacterSet.isEmpty ? characterSet : fullCharacterSet
        let bigProof = paragraphs <= 2
        let numberOfWords = bigProof ? 4 : 6

        var arabWords = ""
        for char in characterSet {
            let g = String(char)
            arabWords += g + ". "

            for p in posForms {
                var words = ""
                switch p {
                case "init":
                    words = wsv.words(glyphs: glyphs, count: numberOfWords, minWL: 5, maxWL: 14, vocab: vocab, startsWith: g)
                case "medi":
                    words = wsv.words(glyphs: glyphs, count: numberOfWords, minWL: 5, maxWL: 14, vocab: vocab, inner: g)
                case "fina":
                    words = wsv.words(glyphs: glyphs, count: numberOfWords, minWL: 5, maxWL: 14, vocab: vocab, endsWith: g)
                default:
                    words = wsv.words(glyphs: glyphs, contains: g, count: numberOfWords, minWL: 5, maxWL: 14, vocab: vocab)
                }
                if !words.isEmpty {
                    arabWords += words + " "
                }
            }
            arabWords += "\n"
        }

        return arabWords
    }

    // MARK: - Arabic shape data

    private static let arabicGlyphToUnicode: [String: Character] = [
        "hamza-ar":               "\u{0621}",
        "alef-ar":                "\u{0627}",
        "alefHamzaabove":         "\u{0623}",
        "alefHamzabelow-ar":      "\u{0625}",
        "alefMadda-ar":           "\u{0622}",
        "alefWasla-ar":           "\u{0671}",
        "behDotless-ar":          "\u{066E}",
        "beh-ar":                 "\u{0628}",
        "peh-ar":                 "\u{067E}",
        "teh-ar":                 "\u{062A}",
        "theh-ar":                "\u{062B}",
        "tteh-ar":                "\u{0679}",
        "alefMaksura-ar":         "\u{0649}",
        "noon-ar":                "\u{0646}",
        "noonghunna-ar":          "\u{06BA}",
        "yeh-ar":                 "\u{064A}",
        "yehHamzaabove-ar":       "\u{0626}",
        "yehFarsi-ar":            "\u{06CC}",
        "jeem-ar":                "\u{062C}",
        "tcheh-ar":               "\u{0686}",
        "hah-ar":                 "\u{062D}",
        "khah-ar":                "\u{062E}",
        "dal-ar":                 "\u{062F}",
        "thal-ar":                "\u{0630}",
        "ddal-ar":                "\u{0688}",
        "reh-ar":                 "\u{0631}",
        "zain-ar":                "\u{0632}",
        "rreh-ar":                "\u{0691}",
        "jeh-ar":                 "\u{0698}",
        "seen-ar":                "\u{0633}",
        "sheen-ar":               "\u{0634}",
        "sad-ar":                 "\u{0635}",
        "dad-ar":                 "\u{0636}",
        "tah-ar":                 "\u{0637}",
        "zah-ar":                 "\u{0638}",
        "ain-ar":                 "\u{0639}",
        "ghain-ar":               "\u{063A}",
        "fehDotless-ar":          "\u{06A1}",
        "feh-ar":                 "\u{0641}",
        "veh-ar":                 "\u{06A4}",
        "qaf-ar":                 "\u{0642}",
        "qafDotless-ar":          "\u{066F}",
        "kaf-ar":                 "\u{0643}",
        "keheh-ar":               "\u{06A9}",
        "gaf-ar":                 "\u{06AF}",
        "lam-ar":                 "\u{0644}",
        "meem-ar":                "\u{0645}",
        "heh-ar":                 "\u{0647}",
        "tehMarbuta-ar":          "\u{0629}",
        "hehDoachashmee-ar":      "\u{06BE}",
        "hehgoal-ar":             "\u{06C1}",
        "hehgoalHamzaabove-ar":   "\u{06C2}",
        "tehMarbutagoal-ar":      "\u{06C3}",
        "waw-ar":                 "\u{0648}",
        "wawHamzaabove-ar":       "\u{0624}",
        "yehbarree-ar":           "\u{06D2}",
        "yehbarreeHamzaabove-ar": "\u{06D3}",
    ]

    private static let arabicShapeGroups: [(String, String, [String])] = [
        ("hamza-ar",          "fina", ["hamza-ar"]),
        ("hamza-ar",          "",     ["hamza-ar"]),
        ("alef-ar",           "fina", ["alef-ar", "alefHamzaabove", "alefHamzabelow-ar", "alefMadda-ar", "alefWasla-ar"]),
        ("alef-ar",           "",     ["alef-ar", "alefHamzaabove", "alefHamzabelow-ar", "alefMadda-ar", "alefWasla-ar"]),
        ("behDotless-ar",     "fina", ["behDotless-ar", "beh-ar", "peh-ar", "teh-ar", "theh-ar", "tteh-ar"]),
        ("behDotless-ar",     "medi", ["behDotless-ar", "beh-ar", "peh-ar", "alefMaksura-ar", "teh-ar", "theh-ar", "tteh-ar", "noon-ar", "noonghunna-ar", "yeh-ar", "yehHamzaabove-ar", "yehFarsi-ar"]),
        ("behDotless-ar",     "init", ["behDotless-ar", "beh-ar", "peh-ar", "alefMaksura-ar", "teh-ar", "theh-ar", "tteh-ar", "noon-ar", "noonghunna-ar", "hehgoal-ar", "yeh-ar", "yehHamzaabove-ar", "yehFarsi-ar"]),
        ("hah-ar",            "fina", ["jeem-ar", "tcheh-ar", "hah-ar", "khah-ar"]),
        ("hah-ar",            "medi", ["jeem-ar", "tcheh-ar", "hah-ar", "khah-ar"]),
        ("hah-ar",            "init", ["jeem-ar", "tcheh-ar", "hah-ar", "khah-ar"]),
        ("dal-ar",            "fina", ["dal-ar", "thal-ar", "ddal-ar"]),
        ("dal-ar",            "",     ["dal-ar", "thal-ar", "ddal-ar"]),
        ("reh-ar",            "fina", ["reh-ar", "zain-ar", "rreh-ar", "jeh-ar"]),
        ("reh-ar",            "",     ["reh-ar", "zain-ar", "rreh-ar", "jeh-ar"]),
        ("seen-ar",           "fina", ["seen-ar", "sheen-ar"]),
        ("seen-ar",           "medi", ["seen-ar", "sheen-ar"]),
        ("seen-ar",           "init", ["seen-ar", "sheen-ar"]),
        ("sad-ar",            "fina", ["sad-ar", "dad-ar"]),
        ("sad-ar",            "medi", ["sad-ar", "dad-ar"]),
        ("sad-ar",            "init", ["sad-ar", "dad-ar"]),
        ("tah-ar",            "fina", ["tah-ar", "zah-ar"]),
        ("tah-ar",            "medi", ["tah-ar", "zah-ar"]),
        ("tah-ar",            "init", ["tah-ar", "zah-ar"]),
        ("ain-ar",            "fina", ["ain-ar", "ghain-ar"]),
        ("ain-ar",            "medi", ["ain-ar", "ghain-ar"]),
        ("ain-ar",            "init", ["ain-ar", "ghain-ar"]),
        ("fehDotless-ar",     "fina", ["fehDotless-ar", "feh-ar", "veh-ar"]),
        ("fehDotless-ar",     "medi", ["fehDotless-ar", "feh-ar", "veh-ar", "qaf-ar"]),
        ("fehDotless-ar",     "init", ["fehDotless-ar", "feh-ar", "veh-ar", "qaf-ar"]),
        ("qafDotless-ar",     "fina", ["qafDotless-ar", "qaf-ar"]),
        ("kaf-ar",            "fina", ["kaf-ar"]),
        ("kaf-ar",            "medi", ["kaf-ar", "keheh-ar", "gaf-ar"]),
        ("kaf-ar",            "init", ["kaf-ar", "keheh-ar", "gaf-ar"]),
        ("keheh-ar",          "fina", ["keheh-ar", "gaf-ar"]),
        ("lam-ar",            "fina", ["lam-ar"]),
        ("lam-ar",            "medi", ["lam-ar"]),
        ("lam-ar",            "init", ["lam-ar"]),
        ("meem-ar",           "fina", ["meem-ar"]),
        ("meem-ar",           "medi", ["meem-ar"]),
        ("meem-ar",           "init", ["meem-ar"]),
        ("noonghunna-ar",     "fina", ["noonghunna-ar", "noon-ar"]),
        ("heh-ar",            "fina", ["heh-ar", "tehMarbuta-ar"]),
        ("heh-ar",            "medi", ["heh-ar", "hehDoachashmee-ar"]),
        ("heh-ar",            "init", ["heh-ar", "hehDoachashmee-ar"]),
        ("hehgoal-ar",        "fina", ["hehgoal-ar", "hehgoalHamzaabove-ar", "tehMarbutagoal-ar"]),
        ("hehgoal-ar",        "medi", ["hehgoal-ar"]),
        ("hehDoachashmee-ar", "fina", ["hehDoachashmee-ar"]),
        ("waw-ar",            "fina", ["waw-ar", "wawHamzaabove-ar"]),
        ("waw-ar",            "",     ["waw-ar", "wawHamzaabove-ar"]),
        ("alefMaksura-ar",    "fina", ["alefMaksura-ar", "yeh-ar", "yehHamzaabove-ar", "yehFarsi-ar"]),
        ("alefMaksura-ar",    "",     ["alefMaksura-ar", "yeh-ar", "yehHamzaabove-ar", "yehFarsi-ar"]),
        ("yehbarree-ar",      "fina", ["yehbarree-ar", "yehbarreeHamzaabove-ar"]),
    ]
}
