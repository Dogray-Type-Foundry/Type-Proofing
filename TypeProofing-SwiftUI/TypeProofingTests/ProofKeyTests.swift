import XCTest
@testable import TypeProofing

/// Tests that `pythonProofKey(for:)` produces the same keys Python's
/// `create_unique_proof_key()` would, ensuring the Swift–Python bridge
/// agrees on settings-key prefixes for every proof instance.
final class ProofKeyTests: XCTestCase {

    // MARK: - 1. Parity with PROOF_REGISTRY keys

    /// Every display name in PROOF_REGISTRY, when passed through
    /// `pythonProofKey(for:)`, must produce the same string as its
    /// registry key. This is the fundamental contract between Swift
    /// and Python.
    func testAllRegistryDisplayNamesMatchBaseType() {
        // (displayName from Python's PROOF_REGISTRY, registry key / baseType)
        let entries: [(displayName: String, registryKey: String)] = [
            ("Filtered Character Set",           "filtered_character_set"),
            ("Spacing Proof",                    "spacing_proof"),
            ("Basic Paragraph Large",            "basic_paragraph_large"),
            ("Diacritic Words Large",            "diacritic_words_large"),
            ("Basic Paragraph Small",            "basic_paragraph_small"),
            ("Paired Styles Paragraph Small",    "paired_styles_paragraph_small"),
            ("Generative Text Small",            "generative_text_small"),
            ("Diacritic Words Small",            "diacritic_words_small"),
            ("Misc Paragraph Small",             "misc_paragraph_small"),
            ("Ar Character Set",                 "ar_character_set"),
            ("Ar Paragraph Large",               "ar_paragraph_large"),
            ("Fa Paragraph Large",               "fa_paragraph_large"),
            ("Ar Paragraph Small",               "ar_paragraph_small"),
            ("Fa Paragraph Small",               "fa_paragraph_small"),
            ("Ar Vocalization Paragraph Small",  "ar_vocalization_paragraph_small"),
            ("Ar-Lat Mixed Paragraph Small",     "ar_lat_mixed_paragraph_small"),
            ("Ar Numbers Small",                 "ar_numbers_small"),
            ("Custom Text",                      "custom_text"),
            ("Multi-Style Comparison",           "multi_style_comparison"),
        ]

        for (displayName, registryKey) in entries {
            XCTAssertEqual(
                pythonProofKey(for: displayName), registryKey,
                "Key mismatch for display name '\(displayName)'"
            )
        }
    }

    // MARK: - 2. Duplicate proof names produce unique keys

    func testDuplicateProofNamesProduceUniqueKeys() {
        let key1 = pythonProofKey(for: "Filtered Character Set")
        let key2 = pythonProofKey(for: "Filtered Character Set 2")
        let key3 = pythonProofKey(for: "Filtered Character Set 3")

        XCTAssertNotEqual(key1, key2)
        XCTAssertNotEqual(key2, key3)
        XCTAssertNotEqual(key1, key3)

        XCTAssertEqual(key1, "filtered_character_set")
        XCTAssertEqual(key2, "filtered_character_set_2")
        XCTAssertEqual(key3, "filtered_character_set_3")
    }

    func testDuplicateParagraphProofKeys() {
        let key1 = pythonProofKey(for: "Basic Paragraph Large")
        let key2 = pythonProofKey(for: "Basic Paragraph Large 2")

        XCTAssertEqual(key1, "basic_paragraph_large")
        XCTAssertEqual(key2, "basic_paragraph_large_2")
        XCTAssertNotEqual(key1, key2)
    }

    func testDuplicateCustomTextKeys() {
        let key1 = pythonProofKey(for: "Custom Text")
        let key2 = pythonProofKey(for: "Custom Text 2")

        XCTAssertEqual(key1, "custom_text")
        XCTAssertEqual(key2, "custom_text_2")
    }

    // MARK: - 3. Special character handling

    func testDashesConvertedToUnderscores() {
        // "Ar-Lat Mixed Paragraph Small" and "Multi-Style Comparison" both have dashes
        XCTAssertEqual(
            pythonProofKey(for: "Ar-Lat Mixed Paragraph Small"),
            "ar_lat_mixed_paragraph_small"
        )
        XCTAssertEqual(
            pythonProofKey(for: "Multi-Style Comparison"),
            "multi_style_comparison"
        )
    }

    func testSlashesConvertedToUnderscores() {
        // Edge case: slashes in proof names (not currently used, but the
        // Python function handles them)
        XCTAssertEqual(
            pythonProofKey(for: "Some/Custom Proof"),
            "some_custom_proof"
        )
    }

    func testCaseInsensitive() {
        XCTAssertEqual(
            pythonProofKey(for: "FILTERED CHARACTER SET"),
            "filtered_character_set"
        )
        XCTAssertEqual(
            pythonProofKey(for: "filtered character set"),
            "filtered_character_set"
        )
    }

    // MARK: - 4. Settings key construction patterns

    /// Verify that the key prefix, combined with standard suffixes,
    /// matches the Python convention for all setting types.
    func testSettingsKeySuffixPatterns() {
        let prefix = pythonProofKey(for: "Basic Paragraph Large")

        XCTAssertEqual("\(prefix)_fontSize", "basic_paragraph_large_fontSize")
        XCTAssertEqual("\(prefix)_cols", "basic_paragraph_large_cols")
        XCTAssertEqual("\(prefix)_tracking", "basic_paragraph_large_tracking")
        XCTAssertEqual("\(prefix)_align", "basic_paragraph_large_align")
        XCTAssertEqual("\(prefix)_para", "basic_paragraph_large_para")
        XCTAssertEqual("\(prefix)_lineHeight", "basic_paragraph_large_lineHeight")
        XCTAssertEqual("otf_\(prefix)_kern", "otf_basic_paragraph_large_kern")
    }

    func testDuplicateSettingsKeySuffixPatterns() {
        let prefix = pythonProofKey(for: "Basic Paragraph Large 2")

        XCTAssertEqual("\(prefix)_fontSize", "basic_paragraph_large_2_fontSize")
        XCTAssertEqual("otf_\(prefix)_kern", "otf_basic_paragraph_large_2_kern")
    }

    func testCategoryKeyPatterns() {
        let prefix = pythonProofKey(for: "Filtered Character Set")

        XCTAssertEqual("\(prefix)_cat_uppercase_base", "filtered_character_set_cat_uppercase_base")
        XCTAssertEqual("\(prefix)_cat_lowercase_base", "filtered_character_set_cat_lowercase_base")
        XCTAssertEqual("\(prefix)_cat_accented", "filtered_character_set_cat_accented")
    }

    func testDuplicateCategoryKeyPatterns() {
        let prefix = pythonProofKey(for: "Filtered Character Set 2")

        XCTAssertEqual(
            "\(prefix)_cat_uppercase_base",
            "filtered_character_set_2_cat_uppercase_base"
        )
    }

    func testBaseProofSettingsUseRegistryKey() {
        let entry = ProofRegistryEntry(
            key: "filtered_character_set",
            displayName: "Character Overview",
            isArabic: false,
            hasSettings: true,
            defaultColumns: 1,
            hasParagraphs: false,
            defaultFontSize: 78,
            hasCustomText: false,
            hasCategories: true,
            isMultiStyle: false,
            defaultEnabled: true,
            displayOrder: 0
        )
        let baseOption = ProofOption(
            name: "Character Overview",
            baseType: "filtered_character_set",
            enabled: true,
            order: 0
        )
        let duplicateOption = ProofOption(
            name: "Character Overview 2",
            baseType: "filtered_character_set",
            enabled: true,
            order: 1
        )

        XCTAssertEqual(pythonSettingsKey(for: baseOption, entry: entry), "filtered_character_set")
        XCTAssertEqual(pythonSettingsKey(for: duplicateOption, entry: entry), "character_overview_2")
    }
}
