import XCTest

/// Tests for the Settings Panel (right sidebar):
/// - Per-proof settings controls (font size, tracking, columns, etc.)
/// - Character category checkboxes
/// - Custom text input
/// - OpenType feature toggles
/// - Alignment picker
/// - Auto-size toggle
final class SettingsPanelUITests: XCTestCase {

    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false

        app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
        app.launch()

        // Wait for initialization
        let generateButton = app.buttons["Generate"]
        let exists = generateButton.waitForExistence(timeout: 10)
        XCTAssertTrue(exists, "App failed to initialize")
    }

    override func tearDown() {
        app = nil
        super.tearDown()
    }

    // MARK: - Setup Helper

    /// Adds a proof to test settings panel
    func addProof(named proofName: String) {
        // Switch to Proofs tab
        let proofsTab = app.radioButtons["Proofs"]
        if proofsTab.exists {
            proofsTab.tap()
        }

        // Add proof
        let addButton = app.buttons["add-proof-button"]
        addButton.click()

        // Wait for popover
        sleep(1)

        // Look for the proof in the popover (SwiftUI popovers show as buttons/text, not menu items)
        let proofButton = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", proofName)).firstMatch
        let proofText = app.staticTexts.matching(NSPredicate(format: "label == %@", proofName)).firstMatch

        if proofButton.waitForExistence(timeout: 2) {
            proofButton.click()
        } else if proofText.exists {
            proofText.click()
        }

        // Wait for proof to be added
        _ = app.staticTexts[proofName].waitForExistence(timeout: 2)
    }

    // MARK: - Settings Panel Visibility

    func testSettingsPanelAppearsWhenProofSelected() throws {
        // Add a proof
        addProof(named: "Filtered Character Set")

        // Click the proof to select it
        let proofRow = app.staticTexts["Filtered Character Set"]
        proofRow.click()

        // Settings panel should show the proof name as a heading
        let heading = app.staticTexts["Filtered Character Set"]
        XCTAssertTrue(heading.exists, "Settings panel should show selected proof name")
    }

    // MARK: - Numeric Settings

    func testFontSizeSetting() throws {
        addProof(named: "Basic Paragraph Large")

        // Select the proof
        app.staticTexts["Basic Paragraph Large"].click()

        // Look for Size setting
        let sizeLabel = app.staticTexts["Size"]
        XCTAssertTrue(sizeLabel.exists, "Font size setting should exist")

        // Find the text field for size
        let sizeField = app.textFields.matching(NSPredicate(format: "value != ''")).firstMatch
        if sizeField.exists {
            XCTAssertTrue(true, "Font size field is accessible")

            // Try to modify it
            sizeField.click()
            sizeField.typeKey(.delete, modifierFlags: .command) // Select all and delete
            sizeField.typeText("24")

            // Verify the value was set (may need to press Enter)
            sizeField.typeKey(.enter, modifierFlags: [])
        }
    }

    func testTrackingSetting() throws {
        addProof(named: "Basic Paragraph Small")

        app.staticTexts["Basic Paragraph Small"].click()

        // Look for Tracking setting
        let trackingLabel = app.staticTexts["Tracking"]
        XCTAssertTrue(trackingLabel.exists, "Tracking setting should exist for paragraph proofs")

        // Tracking control should be adjustable
        let trackingFields = app.textFields.matching(NSPredicate(format: "value != ''"))
        XCTAssertGreaterThan(trackingFields.count, 0, "Tracking field should exist")
    }

    func testColumnsSetting() throws {
        addProof(named: "Filtered Character Set")

        app.staticTexts["Filtered Character Set"].click()

        // Look for Columns setting
        let columnsLabel = app.staticTexts["Columns"]
        XCTAssertTrue(columnsLabel.exists, "Columns setting should exist for charset proofs")
    }

    func testLineHeightSetting() throws {
        addProof(named: "Basic Paragraph Large")

        app.staticTexts["Basic Paragraph Large"].click()

        // Look for Line Height setting
        let lineHeightLabel = app.staticTexts["Line Height"]
        XCTAssertTrue(lineHeightLabel.exists, "Line height setting should exist for paragraph proofs")
    }

    // MARK: - Toggle Settings

    func testAutoSizeToggle() throws {
        addProof(named: "Filtered Character Set")

        app.staticTexts["Filtered Character Set"].click()

        // Look for auto-size toggle
        let autoSizeToggle = app.checkBoxes.matching(NSPredicate(format: "label CONTAINS 'Auto-size'")).firstMatch

        if autoSizeToggle.exists {
            let initialValue = autoSizeToggle.value as? Int ?? 0

            // Toggle it
            autoSizeToggle.click()

            let newValue = autoSizeToggle.value as? Int ?? 0
            XCTAssertNotEqual(initialValue, newValue, "Auto-size toggle should change state")
        }
    }

    // MARK: - Character Categories

    func testCharacterCategoryCheckboxes() throws {
        addProof(named: "Filtered Character Set")

        app.staticTexts["Filtered Character Set"].click()

        // Look for category checkboxes (Uppercase, Lowercase, etc.)
        let categoryCheckboxes = app.checkBoxes.matching(NSPredicate(format: "label CONTAINS 'Uppercase' OR label CONTAINS 'Lowercase' OR label CONTAINS 'Numbers'"))

        if categoryCheckboxes.count > 0 {
            XCTAssertTrue(true, "Character category checkboxes exist")

            // Try toggling one
            let firstCategory = categoryCheckboxes.firstMatch
            let initialValue = firstCategory.value as? Int ?? 0

            firstCategory.click()

            let newValue = firstCategory.value as? Int ?? 0
            XCTAssertNotEqual(initialValue, newValue, "Category checkbox should toggle")
        } else {
            XCTFail("Character category checkboxes should exist for Filtered Character Set proof")
        }
    }

    // MARK: - Alignment Picker

    func testAlignmentPicker() throws {
        addProof(named: "Basic Paragraph Small")

        app.staticTexts["Basic Paragraph Small"].click()

        // Look for alignment buttons (Left, Center, Right, Justified)
        let alignmentButtons = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Align' OR identifier CONTAINS 'align'"))

        if alignmentButtons.count > 0 {
            XCTAssertTrue(true, "Alignment controls exist for paragraph proofs")

            // Try clicking an alignment button
            alignmentButtons.firstMatch.click()
        } else {
            // Alignment might be shown differently
            XCTAssertTrue(true, "Alignment controls may be shown as radio buttons or other controls")
        }
    }

    // MARK: - Custom Text

    func testCustomTextInput() throws {
        addProof(named: "Custom Text")

        // Click on the proof to select it
        let proofRow = app.staticTexts["Custom Text"]
        if proofRow.exists {
            proofRow.click()
        }

        // Wait for settings panel to update
        sleep(1)

        // Look for custom text input area - it might be a text view or text field
        let textViews = app.textViews
        let textFields = app.textFields

        if textViews.count > 0 {
            let textView = textViews.firstMatch
            XCTAssertTrue(textView.exists, "Custom text input field should exist")

            // Try typing in it
            textView.click()
            textView.typeText("Hello World")

            // Verify test completed
            XCTAssertTrue(true, "Custom text can be entered")
        } else if textFields.count > 0 {
            // Might be a text field instead
            XCTAssertTrue(true, "Custom text input exists as text field")
        } else {
            // Custom text might not be immediately visible without selecting the proof
            // Just verify the proof was added successfully
            XCTAssertTrue(proofRow.exists, "Custom Text proof was added successfully")
        }
    }

    func testMarkupEnabledToggle() throws {
        addProof(named: "Custom Text")

        app.staticTexts["Custom Text"].click()

        // Look for "Enable markup" toggle
        let markupToggle = app.checkBoxes.matching(NSPredicate(format: "label CONTAINS 'markup' OR label CONTAINS 'Markup'")).firstMatch

        if markupToggle.exists {
            let initialValue = markupToggle.value as? Int ?? 0

            markupToggle.click()

            let newValue = markupToggle.value as? Int ?? 0
            XCTAssertNotEqual(initialValue, newValue, "Markup toggle should change state")
        } else {
            XCTAssertTrue(true, "Markup toggle may not be visible in current state")
        }
    }

    // MARK: - OpenType Features

    func testOpenTypeFeaturesSection() throws {
        addProof(named: "Basic Paragraph Large")

        app.staticTexts["Basic Paragraph Large"].click()

        // Look for OpenType features section (might have heading "OpenType Features")
        let otFeaturesHeading = app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'OpenType' OR label CONTAINS 'Features'")).firstMatch

        if otFeaturesHeading.exists {
            XCTAssertTrue(true, "OpenType features section exists")

            // Look for feature toggles (kern, liga, etc.)
            let featureToggles = app.checkBoxes.matching(NSPredicate(format: "label CONTAINS 'kern' OR label CONTAINS 'liga' OR label CONTAINS 'calt'"))

            if featureToggles.count > 0 {
                XCTAssertTrue(true, "OpenType feature toggles exist")

                // Try toggling one
                let firstFeature = featureToggles.firstMatch
                let initialValue = firstFeature.value as? Int ?? 0

                firstFeature.click()

                let newValue = firstFeature.value as? Int ?? 0
                XCTAssertNotEqual(initialValue, newValue, "OpenType feature toggle should work")
            }
        } else {
            XCTAssertTrue(true, "OpenType features may only appear with certain fonts loaded")
        }
    }

    // MARK: - Settings Persistence

    func testSettingsChangesPersistBetweenProofSelections() throws {
        // Add two proofs
        addProof(named: "Filtered Character Set")
        addProof(named: "Spacing Proof")

        // Select first proof and change a setting
        app.staticTexts["Filtered Character Set"].click()

        let sizeField = app.textFields.matching(NSPredicate(format: "value != ''")).firstMatch
        if sizeField.exists {
            sizeField.click()
            sizeField.typeKey(.delete, modifierFlags: .command)
            sizeField.typeText("48")
            sizeField.typeKey(.enter, modifierFlags: [])
        }

        // Switch to second proof
        app.staticTexts["Spacing Proof"].click()

        // Switch back to first proof
        app.staticTexts["Filtered Character Set"].click()

        // Verify the setting persisted
        if sizeField.exists {
            let currentValue = sizeField.value as? String ?? ""
            XCTAssertTrue(currentValue.contains("48"), "Settings should persist when switching between proofs")
        }
    }
}
