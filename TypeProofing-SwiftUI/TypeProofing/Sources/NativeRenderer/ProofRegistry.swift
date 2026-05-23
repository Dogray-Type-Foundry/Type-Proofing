import Foundation

struct TextProofConfig {
	let characterSetKey: String
	let defaultParagraphs: Int
	let forceWordsiv: Bool
	let mixedStyles: Bool
	let accents: Int
	let language: String?
	let hoeflerStyle: Bool
	let injectTextKey: String?

	init(
		characterSetKey: String = "base_letters",
		defaultParagraphs: Int = 5,
		forceWordsiv: Bool = false,
		mixedStyles: Bool = false,
		accents: Int = 0,
		language: String? = nil,
		hoeflerStyle: Bool = false,
		injectTextKey: String? = nil
	) {
		self.characterSetKey = characterSetKey
		self.defaultParagraphs = defaultParagraphs
		self.forceWordsiv = forceWordsiv
		self.mixedStyles = mixedStyles
		self.accents = accents
		self.language = language
		self.hoeflerStyle = hoeflerStyle
		self.injectTextKey = injectTextKey
	}
}

struct ProofRegistryInfo {
	let key: String
	let displayName: String
	let isArabic: Bool
	let hasSettings: Bool
	let defaultCols: Int
	let hasParagraphs: Bool
	let defaultSize: Int
	let hasCustomText: Bool
	let hasCategories: Bool
	let multiStyle: Bool
	let defaultEnabled: Bool
	let textConfig: TextProofConfig?
}

struct ProofRegistry {

	static let defaultProofOrder: [String] = [
		"filtered_character_set",
		"spacing_proof",
		"basic_paragraph_large",
		"diacritic_words_large",
		"basic_paragraph_small",
		"paired_styles_paragraph_small",
		"generative_text_small",
		"diacritic_words_small",
		"misc_paragraph_small",
		"custom_text",
		"multi_style_comparison",
		"substitution_overview",
		"ar_character_set",
		"ar_paragraph_large",
		"fa_paragraph_large",
		"ar_paragraph_small",
		"fa_paragraph_small",
		"ar_vocalization_paragraph_small",
		"ar_lat_mixed_paragraph_small",
		"ar_numbers_small",
		"ar_generative_paragraph_small",
		"fa_generative_paragraph_small",
	]

	static let entries: [String: ProofRegistryInfo] = {
		var map: [String: ProofRegistryInfo] = [:]

		func add(
			_ key: String, _ name: String, arabic: Bool = false, cols: Int = 2,
			paras: Bool = false, size: Int = 10, customText: Bool = false,
			categories: Bool = false, multiStyle: Bool = false,
			enabled: Bool = true, text: TextProofConfig? = nil
		) {
			map[key] = ProofRegistryInfo(
				key: key, displayName: name, isArabic: arabic,
				hasSettings: true, defaultCols: cols, hasParagraphs: paras,
				defaultSize: size, hasCustomText: customText, hasCategories: categories,
				multiStyle: multiStyle, defaultEnabled: enabled, textConfig: text
			)
		}

		add("filtered_character_set", "Character Overview", cols: 1, size: 78, categories: true)
		add("spacing_proof", "Spacing Test", cols: 2, size: 14, categories: true)
		add(
			"basic_paragraph_large", "Structured Text (Heading)", cols: 1, size: 28,
			text: TextProofConfig(
				characterSetKey: "base_letters", defaultParagraphs: 2, hoeflerStyle: true))
		add(
			"diacritic_words_large", "Accented Words (Heading)", cols: 1, size: 28,
			text: TextProofConfig(
				characterSetKey: "accented_plus", defaultParagraphs: 3, accents: 3))
		add(
			"basic_paragraph_small", "Structured Text (Text)", cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "base_letters", defaultParagraphs: 5, hoeflerStyle: true))
		add(
			"paired_styles_paragraph_small", "Style Pairing", cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "base_letters", defaultParagraphs: 5, forceWordsiv: true,
				mixedStyles: true))
		add(
			"generative_text_small", "Auto-Generated Text", cols: 2, paras: true, size: 9,
			text: TextProofConfig(
				characterSetKey: "base_letters", defaultParagraphs: 5, forceWordsiv: true))
		add(
			"diacritic_words_small", "Accented Words (Text)", cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "accented_plus", defaultParagraphs: 5, accents: 3))
		add(
			"misc_paragraph_small", "Practical Figures & Punctuation", cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "base_letters", defaultParagraphs: 5,
				injectTextKey: "misc_small_injects"))
		add("custom_text", "Custom Text", cols: 1, size: 16, customText: true)
		add(
			"multi_style_comparison", "Style Comparison", cols: 1, size: 24,
			customText: true, categories: true, multiStyle: true)
		add("substitution_overview", "Substitution Overview", cols: 5, size: 28, enabled: false)

		// Arabic/Farsi proofs
		add("ar_character_set", "Ar Character Overview", arabic: true, cols: 1, size: 64)
		add(
			"ar_paragraph_large", "Ar Structured Text (Heading)", arabic: true, cols: 1, size: 28,
			text: TextProofConfig(characterSetKey: "arabic", defaultParagraphs: 2, language: "ar"))
		add(
			"fa_paragraph_large", "Fa Structured Text (Heading)", arabic: true, cols: 1, size: 28,
			text: TextProofConfig(characterSetKey: "farsi", defaultParagraphs: 2, language: "fa"))
		add(
			"ar_paragraph_small", "Ar Structured Text (Text)", arabic: true, cols: 1, size: 9,
			text: TextProofConfig(characterSetKey: "arabic", defaultParagraphs: 5, language: "ar"))
		add(
			"fa_paragraph_small", "Fa Structured Text (Text)", arabic: true, cols: 1, size: 9,
			text: TextProofConfig(characterSetKey: "farsi", defaultParagraphs: 5, language: "fa"))
		add(
			"ar_vocalization_paragraph_small", "Ar Vowel Marks", arabic: true, cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "arabic", defaultParagraphs: 5, language: "ar",
				injectTextKey: "arabicVocalization"))
		add(
			"ar_lat_mixed_paragraph_small", "Ar-Latin Mixed", arabic: true, cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "arabic", defaultParagraphs: 5, language: "ar",
				injectTextKey: "arabicLatinMixed"))
		add(
			"ar_numbers_small", "Ar Numerals", arabic: true, cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "arabic", defaultParagraphs: 5, language: "ar",
				injectTextKey: "arabicFarsiUrduNumbers"))
		add(
			"ar_generative_paragraph_small", "Ar All Combinations", arabic: true, cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "arabic", defaultParagraphs: 5, language: "ar", hoeflerStyle: true)
		)
		add(
			"fa_generative_paragraph_small", "Fa All Combinations", arabic: true, cols: 2, size: 9,
			text: TextProofConfig(
				characterSetKey: "farsi", defaultParagraphs: 5, language: "fa", hoeflerStyle: true))

		return map
	}()

	static func entry(forKey key: String) -> ProofRegistryInfo? {
		entries[key]
	}

	static func entry(forDisplayName name: String) -> ProofRegistryInfo? {
		entries.values.first { $0.displayName == name }
	}

	static func defaultProofOrder(includeArabic: Bool = true) -> [String] {
		if includeArabic { return defaultProofOrder }
		return defaultProofOrder.filter { !(entries[$0]?.isArabic ?? false) }
	}
}
