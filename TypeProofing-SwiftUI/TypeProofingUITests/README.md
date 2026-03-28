# TypeProofing UI Tests

This directory contains XCUITests for the Type Proofing macOS app. These tests verify that GUI controls work correctly by simulating actual user interactions.

## Test Files

- **AppIntegrationUITests.swift** - App launch, Python initialization, tab switching, window state, menu bar
- **SidebarProofsUITests.swift** - Proofs tab: adding/removing/reordering proofs, enabling/disabling via checkboxes
- **SidebarFontsUITests.swift** - Fonts tab: adding/removing fonts, font sorting, variable font axes
- **SettingsPanelUITests.swift** - Settings panel: font size, tracking, columns, character categories, OpenType features
- **PageFormatUITests.swift** - Page format picker, grid toggle, Generate button, PDF viewer

## Running the Tests

### From Xcode

1. Open `TypeProofing.xcodeproj` in Xcode
2. Select the TypeProofing scheme
3. Press `Cmd+U` to run all tests (both unit and UI tests)
4. Or: Press `Cmd+6` to open the Test navigator, then click the play button next to specific tests

### From Command Line

Run all tests (unit + UI):
```bash
xcodebuild -project TypeProofing.xcodeproj -scheme TypeProofing -test
```

Run only UI tests:
```bash
xcodebuild -project TypeProofing.xcodeproj -scheme TypeProofing -only-testing:TypeProofingUITests -test
```

Run a specific test file:
```bash
xcodebuild -project TypeProofing.xcodeproj -scheme TypeProofing -only-testing:TypeProofingUITests/SidebarProofsUITests -test
```

Run a specific test case:
```bash
xcodebuild -project TypeProofing.xcodeproj -scheme TypeProofing -only-testing:TypeProofingUITests/SidebarProofsUITests/testAddProofViaMenu -test
```

## Test Limitations

### Current Limitations

1. **No Font Files in Tests** - Tests assume the app starts without fonts loaded. To test font-specific functionality, you'll need to manually load test fonts or extend the tests to load fonts programmatically.

2. **Drag-and-Drop** - macOS drag-and-drop simulation in XCUITest can be unreliable. Tests verify the UI elements exist but may not fully simulate drag operations.

3. **File Pickers** - Native macOS file pickers (Open/Save dialogs) are difficult to automate in UI tests. Tests verify buttons exist but don't click them.

4. **PDF Generation** - Tests don't verify actual PDF content. They only verify the UI controls work correctly. Use Python integration tests for PDF validation.

5. **Settings Persistence** - Testing persistence across app launches requires more complex test setup. Current tests verify in-session state management.

### What These Tests Verify

- ✅ All GUI controls exist and are accessible
- ✅ Buttons, checkboxes, toggles, and pickers respond to clicks
- ✅ State changes are reflected in the UI
- ✅ Tab switching works correctly
- ✅ App launches and initializes Python successfully
- ✅ Generate button is properly enabled/disabled based on state
- ✅ Settings panel updates when proof selection changes
- ✅ Proofs and fonts can be added/removed via UI

### What These Tests DON'T Verify

- ❌ Actual PDF generation (use Python integration tests)
- ❌ Font file parsing (use Python unit tests)
- ❌ Settings persistence to disk across launches
- ❌ Complex drag-and-drop reordering
- ❌ File picker interactions

## Test Setup

Tests use the launch argument `--uitesting` to identify when running in test mode. You can add conditional behavior in the app:

```swift
if CommandLine.arguments.contains("--uitesting") {
    // Skip certain initializations
    // Use mock data
    // Disable animations
}
```

## Debugging Tests

### View Test Output in Xcode

1. Run tests with `Cmd+U`
2. Open Report navigator (`Cmd+9`)
3. Click on the test run to see results
4. Expand failed tests to see failure messages and screenshots

### Record UI Tests

Xcode can record your interactions and generate test code:

1. Open a test file
2. Place cursor inside a test method
3. Click the red record button at the bottom of the editor
4. Perform actions in the app
5. Xcode generates XCUITest code

### Slow Down Tests

Add delays for debugging:

```swift
sleep(2) // Wait 2 seconds
```

### View Element Hierarchy

When a test fails, Xcode captures screenshots and element trees. You can inspect these to find the correct identifiers.

## Accessibility Identifiers

To make tests more reliable, add accessibility identifiers to SwiftUI views:

```swift
Button("Add Proof") { }
    .accessibilityIdentifier("add-proof-button")
```

Then in tests:

```swift
app.buttons["add-proof-button"].click()
```

## Best Practices

1. **Keep tests independent** - Each test should work regardless of test order
2. **Clean up state** - Reset app state in `setUp()` or `tearDown()`
3. **Use waits** - UI elements may take time to appear: `waitForExistence(timeout:)`
4. **Verify existence first** - Check `exists` before interacting with elements
5. **Use descriptive test names** - Name should clearly state what's being tested
6. **Test one thing per test** - Keep tests focused and atomic
7. **Handle flakiness** - UI tests can be flaky; add appropriate waits and retries

## Maintenance

When you add new UI features:

1. Add corresponding UI tests to verify the controls work
2. Update this README if you add new test files
3. Run the full test suite before committing changes
4. Fix any broken tests before merging

When UI changes:

1. Update tests to reflect new element identifiers or hierarchies
2. Add accessibility identifiers to make tests more robust
3. Re-run tests to verify they still pass

## Continuous Integration

These tests can be run in CI/CD pipelines:

```bash
# In CI script
xcodebuild -project TypeProofing.xcodeproj \\
  -scheme TypeProofing \\
  -destination 'platform=macOS' \\
  -test
```

Note: UI tests require a GUI environment. In headless CI, you may need to use a virtual display or skip UI tests.
