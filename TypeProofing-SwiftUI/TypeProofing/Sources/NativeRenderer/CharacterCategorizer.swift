import Foundation

struct CharacterCategorizer {

    static let upperTemplate = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    static let lowerTemplate = "abcdefghijklmnopqrstuvwxyz"

    static func categorize(charset: String) -> CharacterCategories {
        var uniLu = "", uniLl = "", uniLo = ""
        var uniNd = "", uniNo = ""
        var uniPo = "", uniPc = "", uniPd = ""
        var uniPs = "", uniPe = "", uniPi = "", uniPf = ""
        var uniSm = "", uniSc = "", uniSo = ""
        var uniLuBase = "", uniLlBase = ""
        var accented = ""
        var ar = "", fa = ""
        var arabTyped = "", arfaDualJoin = "", arfaRightJoin = ""

        let arTemplate = Set("ءاأإآٱبتثجچحخدذرزسشصضطظعغفڤقكلمنهةوؤىيﻻ")
        let faTemplate = Set("اآبپتثجچحخدذرزژسشصضطظعغفقکگلمنهویﻻ")
        let dualJoinSet = Set("بپتثجچحخسصضطظعغفڤقكکگلمنهہھيئی")
        let rightJoinSet = Set("اأإآٱدذرزژوﻻ")

        for char in charset {
            let scalar = char.unicodeScalars.first!
            let category = scalar.properties.generalCategory

            switch category {
            case .uppercaseLetter:
                uniLu.append(char)
                if isAccented(char) { accented.append(char) } else { uniLuBase.append(char) }
            case .lowercaseLetter:
                uniLl.append(char)
                if isAccented(char) { accented.append(char) } else { uniLlBase.append(char) }
            case .otherLetter: uniLo.append(char)
            case .decimalNumber: uniNd.append(char)
            case .otherNumber: uniNo.append(char)
            case .otherPunctuation: uniPo.append(char)
            case .connectorPunctuation: uniPc.append(char)
            case .dashPunctuation: uniPd.append(char)
            case .openPunctuation: uniPs.append(char)
            case .closePunctuation: uniPe.append(char)
            case .initialPunctuation: uniPi.append(char)
            case .finalPunctuation: uniPf.append(char)
            case .mathSymbol: uniSm.append(char)
            case .currencySymbol: uniSc.append(char)
            case .otherSymbol: uniSo.append(char)
            default: break
            }

            if arTemplate.contains(char) { ar.append(char) }
            if faTemplate.contains(char) { fa.append(char) }

            if isArabicScript(scalar) {
                arabTyped.append(char)
            }
            if dualJoinSet.contains(char) { arfaDualJoin.append(char) }
            if rightJoinSet.contains(char) { arfaRightJoin.append(char) }
        }

        let upperSet = Set(upperTemplate)
        let lowerSet = Set(lowerTemplate)
        let accentedSet = Set(accented)
        var accentedPlus = accented
        for char in uniLu + uniLl {
            if !accentedSet.contains(char) && !upperSet.contains(char) && !lowerSet.contains(char) {
                accentedPlus.append(char)
            }
        }

        return CharacterCategories(
            uniLu: uniLu, uniLl: uniLl, uniLo: uniLo,
            uniLuBase: uniLuBase, uniLlBase: uniLlBase,
            uniNd: uniNd, uniNo: uniNo,
            uniPo: uniPo, uniPc: uniPc, uniPd: uniPd,
            uniPs: uniPs, uniPe: uniPe,
            uniPi: uniPi, uniPf: uniPf,
            uniSm: uniSm, uniSc: uniSc, uniSo: uniSo,
            uppercaseOnly: uniLl.isEmpty,
            lowercaseOnly: uniLu.isEmpty,
            accentedPlus: accentedPlus,
            ar: ar, fa: fa,
            arabTyped: arabTyped,
            arfaDualJoin: arfaDualJoin,
            arfaRightJoin: arfaRightJoin
        )
    }

    private static func isArabicScript(_ scalar: Unicode.Scalar) -> Bool {
        let v = scalar.value
        return (0x0600...0x06FF).contains(v) ||   // Arabic
               (0x0750...0x077F).contains(v) ||   // Arabic Supplement
               (0x08A0...0x08FF).contains(v) ||   // Arabic Extended-A
               (0xFB50...0xFDFF).contains(v) ||   // Arabic Presentation Forms-A
               (0xFE70...0xFEFF).contains(v)      // Arabic Presentation Forms-B
    }

    private static func isAccented(_ char: Character) -> Bool {
        let scalars = char.unicodeScalars
        if scalars.count > 1 { return true }
        guard let scalar = scalars.first else { return false }
        let decomposed = String(scalar).decomposedStringWithCanonicalMapping.unicodeScalars
        return decomposed.count > 1
    }

    struct ProofCategories {
        let uppercaseBase: String
        let lowercaseBase: String
        let numbersSymbols: String
        let punctuation: String
        let accented: String
    }

    static func proofCategories(from cat: CharacterCategories) -> ProofCategories {
        let uppercaseBaseSorted = String(cat.uniLuBase.sorted())
        let lowercaseBaseSorted = String(cat.uniLlBase.sorted())

        let num = [cat.uniNd, cat.uniSm, cat.uniSc, cat.uniNo]
            .filter { !$0.isEmpty }
            .joined(separator: "\n")

        let punct = cat.uniPo + cat.uniPc + cat.uniPd + cat.uniPs + cat.uniPe + cat.uniPi + cat.uniPf

        return ProofCategories(
            uppercaseBase: uppercaseBaseSorted,
            lowercaseBase: lowercaseBaseSorted,
            numbersSymbols: num,
            punctuation: punct,
            accented: cat.accentedPlus
        )
    }

    static func generateSpacingString(characterSet: String) -> String {
        var lines: [String] = []
        for char in characterSet {
            if char == "\n" || char == " " { continue }

            let cat = char.unicodeScalars.first!.properties.generalCategory
            let control1: Character
            let control2: Character
            if cat == .lowercaseLetter {
                control1 = "n"; control2 = "o"
            } else if cat == .decimalNumber {
                control1 = "0"; control2 = "1"
            } else {
                control1 = "H"; control2 = "O"
            }

            lines.append("\(control1)\(control1)\(control1)\(char)\(control1)\(control2)\(control1)\(char)\(control2)\(char)\(control2)\(control2)\(control2)")
        }
        return lines.isEmpty ? "" : lines.joined(separator: "\n") + "\n"
    }
}
