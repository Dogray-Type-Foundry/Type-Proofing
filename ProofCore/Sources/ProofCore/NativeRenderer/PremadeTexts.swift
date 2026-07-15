import Foundation

public struct PremadeTexts {

    // MARK: - Resource Loading

    /// Loads an editable sample text from `Resources/SampleTexts/<name>.txt`.
    /// Keeping these as plain-text resources makes them easy to edit or extend
    /// without touching Swift source.
    private static func loadText(_ name: String) -> String {
        guard let url = Bundle.module.url(forResource: name, withExtension: "txt"),
              let text = try? String(contentsOf: url, encoding: .utf8) else {
            assertionFailure("Missing sample text resource: \(name).txt")
            return ""
        }
        return text
    }

    // MARK: - Accented Dictionary

    private static let _accentedDict: [String: [String]] = {
        guard let url = Bundle.module.url(forResource: "accented_dictionary", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let dict = try? JSONDecoder().decode([String: [String]].self, from: data) else {
            return [:]
        }
        return dict
    }()

    static func accentedWords(for character: Character) -> [String] {
        _accentedDict[String(character).lowercased()] ?? []
    }

    // MARK: - Script Texts

    static let arabicVocalization = loadText("arabicVocalization")
    static let arabicLatinMixed = loadText("arabicLatinMixed")
    static let arabicFarsiUrduNumbers = loadText("arabicFarsiUrduNumbers")

    // MARK: - Sample Texts

    static let bigRandomNumbers = loadText("bigRandomNumbers")
    public static let additionalSmallText = loadText("additionalSmallText")
    static let bigMixedText = loadText("bigMixedText")
    static let bigLowerText = loadText("bigLowerText")
    static let bigUpperText = loadText("bigUpperText")
    static let smallMixedText = loadText("smallMixedText")
    static let smallLowerText = loadText("smallLowerText")
    static let smallUpperText = loadText("smallUpperText")

    // MARK: - Inject Text Resolution

    static func resolveInjectText(forKey key: String) -> String? {
        switch key {
        case "arabicVocalization": return arabicVocalization
        case "arabicLatinMixed": return arabicLatinMixed
        case "arabicFarsiUrduNumbers": return arabicFarsiUrduNumbers
        case "misc_small_injects": return bigRandomNumbers + "\n" + additionalSmallText
        default: return nil
        }
    }
}
