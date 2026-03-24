# Type Proofing — SwiftUI + PythonKit Migration Plan

## Summary

Port the GUI from Python (Vanilla/PyObjC) to Swift/SwiftUI in Xcode. Keep the Python engine (DrawBot, wordsiv, fontTools, drawBotGrid) running inside the app via PythonKit. The result is a native macOS app with a SwiftUI frontend calling Python functions directly — no subprocess, no CLI bridge.

### What Gets Deleted

- `app.py` (~1,600 lines) — replaced by Swift controllers
- `ui.py` (~1,850 lines) — replaced by SwiftUI views
- `TypeProofing.py` (~50 lines) — replaced by Swift `@main`
- PDF preview code in `pdf_manager.py` (~150 lines of NSView/PDFKit) — native PDFKit in Swift instead

### What Stays (Unchanged Python)

- `proof.py` (~1,950 lines) — all proof handlers, DrawBot rendering, text generation
- `fonts.py` (~850 lines) — FontManager, `filteredCharset()`, `categorize()`, variable font utilities
- `config.py` (~500 lines) — PROOF_REGISTRY, constants, helper functions
- `settings.py` (~1,200 lines) — Settings class, ProofSettingsManager, validation
- `pdf_manager.py` (~180 lines, simplified) — `begin_pdf_generation()`, `end_pdf_generation()`, `setup_page_format()` (remove preview code)
- `sample_texts.py`, `script_texts.py`, `accented_dictionary.py` — pure data
- `markup_parser.py` (~550 lines) — DrawBot-based markup formatting

### What Gets Created (New Swift)

- Xcode project with SwiftUI app target
- `ProofEngine.swift` — thin bridge to Python via PythonKit
- SwiftUI views: sidebar, PDF viewer, settings panel, font management
- Build infrastructure: Python.framework embedding, package bundling, code signing

---

## Architecture

```
TypeProofing.app/
  Contents/
    MacOS/
      TypeProofing                    ← Swift binary
    Frameworks/
      Python.framework/               ← Embedded Python 3.13 runtime
    Resources/
      python-lib/                     ← Python modules + dependencies
        proof.py
        fonts.py
        config.py
        settings.py
        pdf_manager.py                ← Simplified (no NSView code)
        markup_parser.py
        sample_texts.py
        script_texts.py
        accented_dictionary.py
        engine.py                     ← NEW: headless entry point
        AdobeBlank.otf
        eng_wiki.tsv
        drawBot/                      ← DrawBot package
        drawBotGrid/                  ← drawBotGrid package
        wordsiv/                      ← wordsiv + Rust .so extension
        fontTools/                    ← fontTools package
        (other dependencies)
```

### Data Flow

```
User interaction (SwiftUI)
  → ProofEngine.swift (PythonKit bridge)
    → Python: engine.generate_proof(config_dict)
      → proof.py handlers → DrawBot → PDF file on disk
    ← Returns: PDF file path (String)
  → PDFKit displays the PDF
```

---

## The PythonKit Bridge

PythonKit (https://github.com/pvieito/PythonKit) loads Python at runtime via `dlopen` and provides transparent Swift↔Python type bridging. Strings, ints, floats, bools, dicts, and lists convert automatically.

### How It Works

```swift
import PythonKit

// One-time setup: point Python at our bundled packages
let sys = Python.import("sys")
sys.path.insert(0, bundledPythonLibPath)

// Import Python modules — these are your existing, unchanged .py files
let engine = Python.import("engine")
let config = Python.import("config")
let fonts  = Python.import("fonts")

// Call Python functions directly from Swift
let charset: String = String(fonts.filteredCharset("/path/to/font.otf"))!
let categories: PythonObject = fonts.categorize(charset)

// Generate a proof — returns a file path
let pdfPath: String = String(engine.generate_proof(settingsDict))!
```

### Type Bridging Rules

| Swift Type | Python Type | Conversion |
|---|---|---|
| `String` | `str` | Automatic both ways |
| `Int`, `Double` | `int`, `float` | Automatic both ways |
| `Bool` | `bool` | Automatic both ways |
| `[String]` | `list` | Automatic both ways |
| `[String: Any]` | `dict` | Use `PythonObject` on Swift side |
| `nil` | `None` | Use `Python.None` |

### Critical: Hardened Runtime

PythonKit loads `Python.framework` via `dlopen`. With Hardened Runtime (required for notarization), you must add this entitlement:

```xml
<key>com.apple.security.cs.disable-library-validation</key>
<true/>
```

This is the same pattern the current app uses (the build script already signs with `--options runtime`). The entitlement allows loading the bundled (but differently-signed) Python framework.

---

## Phase 1: Create `engine.py` — Headless Python Entry Point

**Goal:** Extract `run_proof()` from `app.py` into a standalone module that can be called from Swift without any UI imports.

**Success criteria:** `python3 -c "from engine import generate_proof; print('OK')"` works without importing Vanilla, AppKit, or any UI code.

### What to Build

Create `engine.py` — a single file that wraps the proof generation pipeline. This replaces what `app.py.run_proof()` does, but without any UI dependencies.

```python
"""
engine.py — Headless proof generation entry point.

Called from Swift via PythonKit. No UI imports.
"""

import datetime
import drawBot as db
from config import (
    PROOF_REGISTRY,
    DEFAULT_ON_FEATURES,
    get_proof_settings_mapping,
    resolve_base_proof_key,
)
from fonts import (
    FontManager,
    filteredCharset,
    categorize,
    variableFont,
    pairStaticStyles,
    product_dict,
)
from settings import Settings, ProofSettingsManager
from proof import (
    ProofContext,
    get_proof_handler,
    clear_handler_cache,
    MultiStyleComparisonProofHandler,
)
from pdf_manager import PDFManager


def generate_proof(config: dict) -> str:
    """
    Generate a proof PDF from a configuration dictionary.

    Args:
        config: dict with keys:
            - "font_paths": list[str] — absolute paths to font files
            - "axis_values": dict[str, dict[str, list]] — per-font axis values
            - "proof_options": list[dict] — ordered list of
                {"name": str, "enabled": bool, "base_type": str}
            - "proof_settings": dict — the full proof_settings dict
            - "page_format": str — e.g. "A4Landscape"
            - "output_dir": str — directory to write the PDF
            - "show_baselines": bool

    Returns:
        str — absolute path to the generated PDF, or empty string on failure.
    """
    # ... implementation per run_proof() logic below
```

### Implementation Details

The function must replicate the exact logic of `app.py:run_proof()` (lines 1374–1490). Here is what it does, step by step:

1. **Create Settings and FontManager from the config dict** — don't load from disk; populate from the dict Swift passes in.
2. **Call `pdf_manager.begin_pdf_generation()`**
3. **Get paired static styles:** `pairStaticStyles(font_manager.fonts)`
4. **Get OT feature tags from first font:** `db.listOpenTypeFeatures(fonts[0])`
5. **Build default OT features dict:** `{tag: tag in DEFAULT_ON_FEATURES for tag in feature_tags}`
6. **Reset multi-style dedup:** `MultiStyleComparisonProofHandler.reset_generated()`
7. **Loop over enabled proofs** (in the order from `config["proof_options"]`):
   - Get handler via `get_proof_handler(base_type, name, proof_settings, get_font_size_func)`
   - **Loop over each font:**
     - `filteredCharset(font_path)` → character set
     - `categorize(charset)` → categories dict
     - `db.listFontVariations(font_path)` → variable font check
     - Build `axesProduct` from per-font axis values or `variableFont()`
     - Create `ProofContext` dataclass
     - Call `handler.generate_proof(context)`
8. **Call `pdf_manager.end_pdf_generation()`** → returns PDF path
9. **Return the path as a string**

### Simplify `pdf_manager.py`

Remove these methods (they are UI code that Swift replaces):
- `create_preview_components()` — builds NSView/PDFView/ThumbnailView
- `_layout_preview_container()` — positions NSViews
- `toggle_thumbnails()` — shows/hides thumbnail sidebar
- `get_preview_view()` — returns NSView container

Keep these methods (they are DrawBot/PDF logic):
- `begin_pdf_generation()` — calls `db.newDrawing()`
- `end_pdf_generation(font_manager, now)` — calls `db.saveImage()`, returns path
- `setup_page_format()` — sets page dimensions from settings

The remaining `PDFManager` should have no AppKit/PDFKit/NSView imports.

### Also Needed: Font Query Functions

Swift needs font metadata (family name, style, axes) for the UI without going through the full proof pipeline. Expose these in `engine.py`:

```python
def get_font_info(font_paths: list) -> list:
    """Return metadata for each font. Called when user drops fonts."""

def get_font_axes(font_path: str) -> dict:
    """Return axis names and ranges for a variable font."""

def get_charset_categories(font_path: str) -> dict:
    """Return character categories for a font."""

def get_available_ot_features(font_path: str) -> list:
    """Return list of OpenType feature tags available in the font."""
```

These are thin wrappers around existing `fonts.py` and DrawBot functions.

### Verification

```bash
python3 -c "from engine import generate_proof; print('import OK')"
# Should print "import OK" with no errors, no GUI windows
```

---

## Phase 2: Xcode Project Setup with PythonKit and Embedded Python

**Goal:** A bare Xcode project that starts, initializes PythonKit, imports `engine.py`, and prints a success message to the console.

**Success criteria:** Running the app from Xcode prints "Python engine loaded" in the debug console.

### Step-by-Step

#### 2.1 Create the Xcode Project

- File → New → Project → macOS → App
- Product Name: `TypeProofing`
- Interface: SwiftUI
- Language: Swift
- Bundle Identifier: `com.dograytype.typeproofing`
- Deployment Target: macOS 13.0

#### 2.2 Add PythonKit as a Swift Package Dependency

- File → Add Package Dependencies
- URL: `https://github.com/pvieito/PythonKit.git`
- Branch: `master`
- Add `PythonKit` to the TypeProofing target

#### 2.3 Embed Python.framework

Download a standalone Python 3.13 framework build. Options:
- **python.org installer** — installs to `/Library/Frameworks/Python.framework` (this is what the current build uses)
- **python-build-standalone** (https://github.com/indygreg/python-build-standalone) — relocatable framework builds designed for embedding

Use the python.org framework (consistent with current setup):

1. Copy `Python.framework` (the 3.13 version) into the Xcode project
2. In Target → Build Phases → Embed Frameworks: drag `Python.framework`, set "Embed & Sign"
3. In Target → Build Settings → Framework Search Paths: add the path to the framework
4. In Target → Build Settings → Runpath Search Paths: add `@executable_path/../Frameworks`

#### 2.4 Bundle Python Packages

Create a build phase script ("Run Script") that copies the Python modules into the app bundle:

```bash
# Copy Python libraries into app bundle
PYTHON_LIB_DIR="${BUILT_PRODUCTS_DIR}/${CONTENTS_FOLDER_PATH}/Resources/python-lib"
mkdir -p "${PYTHON_LIB_DIR}"

# Copy your Python source files
SOURCE_DIR="${SRCROOT}/python-engine"
cp "${SOURCE_DIR}/engine.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/proof.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/fonts.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/config.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/settings.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/pdf_manager.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/markup_parser.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/sample_texts.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/script_texts.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/accented_dictionary.py" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/AdobeBlank.otf" "${PYTHON_LIB_DIR}/"
cp "${SOURCE_DIR}/eng_wiki.tsv" "${PYTHON_LIB_DIR}/"

# Copy Python packages (from a pre-built site-packages)
PACKAGES_DIR="${SRCROOT}/python-packages"
cp -R "${PACKAGES_DIR}/drawBot" "${PYTHON_LIB_DIR}/"
cp -R "${PACKAGES_DIR}/drawBotGrid" "${PYTHON_LIB_DIR}/"
cp -R "${PACKAGES_DIR}/wordsiv" "${PYTHON_LIB_DIR}/"
cp -R "${PACKAGES_DIR}/fontTools" "${PYTHON_LIB_DIR}/"
# ... other transitive dependencies
```

The `python-packages/` directory should contain pre-installed packages. Create it once:

```bash
pip3 install --target=python-packages \
    git+https://github.com/typemytype/drawbot \
    git+https://github.com/jmsole/drawbotgrid \
    ./wheels/wordsiv-0.3.1-cp39-abi3-macosx_10_12_x86_64.macosx_11_0_arm64.macosx_10_12_universal2.whl \
    "fonttools>=4.58.5"
```

#### 2.5 Python Initialization in Swift

Create `PythonSetup.swift`:

```swift
import Foundation
import PythonKit

enum PythonSetup {
    static func initialize() {
        // Point PythonKit at our bundled framework
        let frameworkPath = Bundle.main.privateFrameworksPath! + "/Python.framework/Versions/3.13/lib/libpython3.13.dylib"
        setenv("PYTHON_LIBRARY", frameworkPath, 1)

        // Set PYTHONPATH to our bundled packages
        let resourcePath = Bundle.main.resourcePath!
        let pythonLibPath = resourcePath + "/python-lib"
        let sys = Python.import("sys")
        sys.path.insert(0, pythonLibPath)

        // Also set PYTHONHOME so Python finds its standard library
        let pythonHome = Bundle.main.privateFrameworksPath! + "/Python.framework/Versions/3.13"
        setenv("PYTHONHOME", pythonHome, 1)
    }
}
```

#### 2.6 Entitlements

Create `TypeProofing.entitlements`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
    <key>com.apple.security.files.downloads.read-write</key>
    <true/>
    <key>com.apple.security.files.documents.read-write</key>
    <true/>
</dict>
</plist>
```

#### 2.7 Verification

```swift
// In App init or ContentView.onAppear:
PythonSetup.initialize()
let engine = Python.import("engine")
print("Python engine loaded: \(engine)")
```

The Xcode console should print the module object. If it fails, check:
1. `PYTHON_LIBRARY` points to the correct dylib
2. `PYTHONHOME` is set before any Python import
3. `sys.path` includes the `python-lib` directory
4. All `.so` files in the bundle are code-signed

---

## Phase 3: Swift ProofEngine Bridge

**Goal:** A Swift class that wraps all Python calls needed by the UI. This is the **only** Swift file that imports PythonKit. Every SwiftUI view talks to `ProofEngine`, never directly to Python.

**Success criteria:** `ProofEngine.generateProof(...)` produces a PDF at the returned path.

### ProofEngine.swift

```swift
import Foundation
import PythonKit

@MainActor
final class ProofEngine: ObservableObject {
    private let engineModule: PythonObject
    private let configModule: PythonObject
    private let fontsModule: PythonObject
    private let settingsModule: PythonObject

    // Published state for SwiftUI binding
    @Published var isGenerating = false
    @Published var lastPDFPath: String?
    @Published var errorMessage: String?

    init() {
        PythonSetup.initialize()
        self.engineModule = Python.import("engine")
        self.configModule = Python.import("config")
        self.fontsModule = Python.import("fonts")
        self.settingsModule = Python.import("settings")
    }

    // MARK: - Proof Generation

    func generateProof(config: ProofConfig) async -> String? {
        isGenerating = true
        defer { isGenerating = false }

        return await Task.detached(priority: .userInitiated) {
            let pyConfig = config.toPythonDict()
            let result = self.engineModule.generate_proof(pyConfig)
            return String(result)
        }.value
    }

    // MARK: - Font Queries

    func analyzeFont(path: String) -> FontInfo? {
        let result = engineModule.get_font_info([path])
        guard result != Python.None, let list = Array<PythonObject>(result) else {
            return nil
        }
        return FontInfo(from: list[0])
    }

    func getFontAxes(path: String) -> [FontAxis] {
        let result = engineModule.get_font_axes(path)
        // Convert Python dict to Swift [FontAxis]
    }

    func getAvailableOTFeatures(path: String) -> [String] {
        let result = engineModule.get_available_ot_features(path)
        return Array<String>(result) ?? []
    }

    // MARK: - Config Queries

    func getProofRegistry() -> [ProofRegistryEntry] {
        let registry = configModule.PROOF_REGISTRY
        // Convert to Swift structs
    }

    func getPageFormats() -> [String] {
        let formats = configModule.PAGE_FORMAT_OPTIONS
        return Array<String>(formats) ?? []
    }

    func getDefaultProofOrder() -> [String] {
        let names = configModule.get_proof_display_names(include_arabic: true)
        return Array<String>(names) ?? []
    }
}
```

### Swift Data Models

These are pure Swift structs that mirror the Python data. They don't depend on PythonKit — only `ProofEngine` does the conversion.

```swift
struct FontInfo: Identifiable {
    let id: String          // file path
    let familyName: String
    let styleName: String
    let isVariable: Bool
    let axes: [FontAxis]
    let supportsArabic: Bool
}

struct FontAxis: Identifiable {
    let id: String          // tag, e.g. "wght"
    let name: String        // "Weight"
    let minValue: Double
    let maxValue: Double
    let defaultValue: Double
    var currentValue: Double
}

struct ProofOption: Identifiable {
    let id = UUID()
    var name: String
    var baseType: String    // original proof type key
    var enabled: Bool
    var order: Int
}

struct ProofConfig {
    var fontPaths: [String]
    var axisValues: [String: [String: [Double]]]
    var proofOptions: [ProofOption]
    var proofSettings: [String: Any]
    var pageFormat: String
    var outputDir: String
    var showBaselines: Bool

    func toPythonDict() -> PythonObject {
        // Convert all fields to a Python dict
        // PythonKit handles String, Int, Double, Bool, Array, Dict automatically
    }
}

struct ProofRegistryEntry {
    let key: String
    let displayName: String
    let isArabic: Bool
    let hasSettings: Bool
    let defaultColumns: Int
    let hasParagraphs: Bool
    let defaultFontSize: Int
    let hasCustomText: Bool
    let hasCategories: Bool
    let isMultiStyle: Bool
}
```

### Settings in Swift vs Python

There are two options for settings persistence:

**Option A — Keep Python settings (simpler migration):** Let `Settings` class in Python handle JSON I/O. Swift calls `engine.load_settings()` and `engine.save_settings(dict)`. The proof_settings dict passes through as a `PythonObject`.

**Option B — Swift-native settings (cleaner long-term):** Port `Settings` and `ProofSettingsManager` to Swift using `Codable` + JSON. The Swift side owns persistence; the Python side receives settings as a dict argument to `generate_proof()`.

**Recommendation: Option A for initial migration, Option B later.** The `proof_settings` dict has complex, dynamic keys generated by `make_settings_key()`. Keeping Python in charge avoids reimplementing that logic. The Swift side just mirrors the dict as `[String: Any]` and passes it through.

---

## Phase 4: SwiftUI Views — Main Window, Sidebar, PDF Viewer

**Goal:** The main app window with three-column layout matching the reference screenshot: sections sidebar (left), PDF viewer (center), settings panel (right). The "Generate" button produces a PDF and displays it.

**Success criteria:** User can load fonts, enable proofs, press Generate, and see the resulting PDF in the viewer.

### Window Layout

The reference screenshot shows a `NavigationSplitView` with:
- **Left sidebar:** scrollable list of section names (proof types / languages)
- **Center:** PDF page view with zoom controls and page navigation
- **Right detail panel:** settings for the selected section (fonts, design, OT features)

```swift
@main
struct TypeProofingApp: App {
    @StateObject private var engine = ProofEngine()
    @StateObject private var appState = AppState()

    var body: some Scene {
        Window("Type Proofing", id: "main") {
            ContentView()
                .environmentObject(engine)
                .environmentObject(appState)
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState

    var body: some View {
        NavigationSplitView {
            SidebarView()
        } detail: {
            HSplitView {
                PDFViewerView()
                SettingsPanelView()
                    .frame(width: 280)
            }
        }
        .toolbar { ToolbarView() }
    }
}
```

### SidebarView

Lists proof options in their user-defined order. Each item has a checkbox (enabled/disabled) and a name. Drag-to-reorder is supported via `.onMove`.

```swift
struct SidebarView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        List(selection: $state.selectedProof) {
            ForEach($state.proofOptions) { $option in
                HStack {
                    Toggle("", isOn: $option.enabled)
                        .toggleStyle(.checkbox)
                    Text(option.name)
                }
                .tag(option.id)
            }
            .onMove { state.moveProofOptions(from: $0, to: $1) }
        }
        .listStyle(.sidebar)
    }
}
```

### PDFViewerView

Wraps `PDFKit.PDFView` via `NSViewRepresentable`. Shows the generated PDF with thumbnails sidebar.

```swift
import PDFKit

struct PDFViewerView: NSViewRepresentable {
    @EnvironmentObject var state: AppState

    func makeNSView(context: Context) -> PDFView {
        let pdfView = PDFView()
        pdfView.autoScales = true
        pdfView.displaysPageBreaks = true
        return pdfView
    }

    func updateNSView(_ pdfView: PDFView, context: Context) {
        if let path = state.currentPDFPath,
           let url = URL(fileURLWithPath: path) as URL?,
           let document = PDFDocument(url: url) {
            pdfView.document = document
        }
    }
}
```

For the thumbnail sidebar shown in the reference screenshot, use a `PDFThumbnailView` alongside the `PDFView`, connected via `thumbnailView.pdfView = pdfView`. Wrap both in an `NSViewRepresentable` horizontal container, or use separate representables in an `HSplitView`.

### SettingsPanelView

The right panel from the reference screenshot. Shows contextual settings for the selected proof. This maps to the current app's "popover" system, but as a persistent panel instead.

```swift
struct SettingsPanelView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var engine: ProofEngine

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Section header (proof name)
                Text(selectedProofName)
                    .font(.headline)

                // Font size, tracking, columns, paragraphs
                NumericSettingsSection()

                // Alignment
                AlignmentPicker()

                // Character categories (if applicable)
                if proofHasCategories {
                    CategoryCheckboxes()
                }

                // Custom text (if applicable)
                if proofHasCustomText {
                    CustomTextEditor()
                }

                // OpenType features
                OTFeaturesSection()
            }
            .padding()
        }
    }
}
```

### Toolbar

```swift
struct ToolbarView: ToolbarContent {
    @EnvironmentObject var engine: ProofEngine
    @EnvironmentObject var state: AppState

    var body: some ToolbarContent {
        ToolbarItem(placement: .primaryAction) {
            Button("Generate Proof") {
                Task { await generateProof() }
            }
            .disabled(engine.isGenerating || state.fontPaths.isEmpty)
        }

        ToolbarItem {
            Picker("Page Format", selection: $state.pageFormat) {
                ForEach(state.pageFormats, id: \.self) { Text($0) }
            }
        }

        ToolbarItem {
            Toggle("Show Grid", isOn: $state.showBaselines)
        }
    }
}
```

### Generate Proof Flow

```swift
func generateProof() async {
    let config = ProofConfig(
        fontPaths: state.fontPaths,
        axisValues: state.axisValuesByFont,
        proofOptions: state.proofOptions,
        proofSettings: state.proofSettings,
        pageFormat: state.pageFormat,
        outputDir: state.outputDirectory,
        showBaselines: state.showBaselines
    )
    if let path = await engine.generateProof(config: config) {
        state.currentPDFPath = path
    }
}
```

### Font Management

The reference screenshot shows a "Fonts" section in the right panel. Fonts are added via a button that opens an `NSOpenPanel` (wrapped in SwiftUI via `fileImporter` modifier or a custom sheet). Variable font axes appear as sliders.

```swift
struct FontsSection: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading) {
            Text("Fonts").font(.headline)

            if state.loadedFonts.isEmpty {
                Text("No fonts to proof yet.")
                    .foregroundColor(.secondary)
            }

            ForEach(state.loadedFonts) { font in
                FontRow(font: font)
            }

            Button("+ Fonts") {
                state.showFontPicker = true
            }
        }
        .fileImporter(
            isPresented: $state.showFontPicker,
            allowedContentTypes: [.font],
            allowsMultipleSelection: true
        ) { result in
            // Add fonts to state, query engine for metadata
        }
    }
}
```

---

## Phase 5: SwiftUI Views — Settings Detail, Variable Font Axes, OT Features

**Goal:** Full feature parity with the current app's settings popover, proof reordering, custom proof instances, and per-font axis editing.

**Success criteria:** Every setting that can be changed in the current Vanilla/PyObjC app can also be changed in the SwiftUI app.

### Mapping: Current UI → SwiftUI Equivalent

| Current (Vanilla/PyObjC) | SwiftUI Equivalent |
|---|---|
| `vanilla.Window` | `WindowGroup` / `Window` |
| `vanilla.Group` + tab switching | `NavigationSplitView` |
| `vanilla.List2` (font table) | `Table` or `List` with columns |
| `vanilla.List2` (proof options) | `List` with `ForEach` + `.onMove` |
| `vanilla.Popover` (proof settings) | Persistent `SettingsPanelView` in right column |
| `vanilla.PopUpButton` | `Picker` with `.menu` style |
| `vanilla.CheckBox` | `Toggle(.checkbox)` |
| `vanilla.Button` | `Button` |
| `vanilla.EditText` / `vanilla.TextEditor` | `TextField` / `TextEditor` |
| `vanilla.PathControl` | `fileImporter` / `fileExporter` modifiers |
| `StepperList2Cell` (custom NSStepper) | `Stepper` or `TextField` with `.onChange` |
| `NSStepper` + `NSTextField` combo | `Stepper(value:in:step:)` with `TextField` |
| PDFKit.PDFView + PDFThumbnailView (embedded NSViews) | `NSViewRepresentable` wrappers |
| Drag/drop font files | `.onDrop(of:)` modifier |
| Edit menu (Cmd+C/V/X/A) | Automatic in SwiftUI (no manual setup needed) |

### Numeric Settings with Steppers

The current app uses a custom `StepperList2Cell` class. In SwiftUI this is straightforward:

```swift
struct NumericSetting: View {
    let label: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double

    var body: some View {
        HStack {
            Text(label)
            Spacer()
            TextField("", value: $value, format: .number)
                .frame(width: 60)
                .textFieldStyle(.roundedBorder)
            Stepper("", value: $value, in: range, step: step)
                .labelsHidden()
        }
    }
}
```

### OpenType Features List

```swift
struct OTFeaturesSection: View {
    @Binding var features: [OTFeature]

    var body: some View {
        VStack(alignment: .leading) {
            Text("OpenType Features").font(.subheadline)

            if features.isEmpty {
                Text("No OpenType features available")
                    .foregroundColor(.secondary)
            } else {
                ForEach($features) { $feature in
                    Toggle(feature.tag, isOn: $feature.enabled)
                        .toggleStyle(.checkbox)
                }
            }
        }
    }
}
```

### Character Categories

For proofs that have `has_categories: true` (Filtered Character Set, Spacing Proof, Multi-Style Comparison):

```swift
struct CategoryCheckboxes: View {
    @Binding var categories: CategorySettings

    var body: some View {
        VStack(alignment: .leading) {
            Toggle("Uppercase", isOn: $categories.uppercaseBase)
            Toggle("Lowercase", isOn: $categories.lowercaseBase)
            Toggle("Numbers & Symbols", isOn: $categories.numbersSymbols)
            Toggle("Punctuation", isOn: $categories.punctuation)
            Toggle("Accented", isOn: $categories.accented)
        }
    }
}
```

### Custom Proof Instances

Users can "Add Proof" to create duplicates (e.g., "Basic Paragraph Large 2"). In SwiftUI:

```swift
Button("Add Proof") {
    // Show picker for base proof type
    state.showAddProofSheet = true
}
.sheet(isPresented: $state.showAddProofSheet) {
    AddProofSheet(onAdd: { baseType in
        let newName = state.generateUniqueName(for: baseType)
        let newOption = ProofOption(
            name: newName,
            baseType: baseType,
            enabled: true,
            order: state.proofOptions.count
        )
        state.proofOptions.append(newOption)
        // Initialize settings for the new instance via engine
        engine.initializeSettingsForProof(uniqueName: newName, baseType: baseType)
    })
}
```

### Variable Font Axes

Per-font axis values are shown as sliders in the font management section:

```swift
struct FontAxesView: View {
    let font: FontInfo
    @Binding var axisValues: [String: Double]

    var body: some View {
        ForEach(font.axes) { axis in
            VStack(alignment: .leading) {
                HStack {
                    Text(axis.name)
                    Spacer()
                    Text(String(format: "%.0f", axisValues[axis.id] ?? axis.defaultValue))
                }
                Slider(
                    value: Binding(
                        get: { axisValues[axis.id] ?? axis.defaultValue },
                        set: { axisValues[axis.id] = $0 }
                    ),
                    in: axis.minValue...axis.maxValue
                )
            }
        }
    }
}
```

### AppState

Central `ObservableObject` that holds all UI state:

```swift
@MainActor
final class AppState: ObservableObject {
    // Fonts
    @Published var fontPaths: [String] = []
    @Published var loadedFonts: [FontInfo] = []
    @Published var axisValuesByFont: [String: [String: Double]] = [:]

    // Proofs
    @Published var proofOptions: [ProofOption] = []
    @Published var selectedProof: ProofOption.ID?
    @Published var proofSettings: [String: Any] = [:]  // Passed through to Python

    // Page
    @Published var pageFormat: String = "A4Landscape"
    @Published var pageFormats: [String] = []
    @Published var showBaselines: Bool = false

    // Output
    @Published var outputDirectory: String = ""
    @Published var currentPDFPath: String?

    // UI state
    @Published var showFontPicker = false
    @Published var showAddProofSheet = false
    @Published var isGenerating = false
}
```

---

## Phase 6: Build, Code Signing, DMG Distribution

**Goal:** Produce a signed, notarizable `.app` bundle with embedded Python.framework and all packages, packaged as a DMG.

**Success criteria:** The DMG installs and runs on a clean macOS 13+ machine that has never had Python installed.

### Code Signing

All dynamic libraries and frameworks in the bundle must be signed with the same identity. This is the same requirement as the current py2app build.

**Code signing order matters.** Sign from the inside out:

1. Sign all `.so` and `.dylib` files in `python-lib/` (wordsiv's Rust extension, PIL dylibs, etc.)
2. Sign `Python.framework/Versions/3.13/Python`
3. Sign DrawBot's embedded tools (`ffmpeg`, `potrace`, `gifsicle`, `mkbitmap`)
4. Sign the main executable (`TypeProofing`)
5. Sign the `.app` bundle with entitlements

This mirrors the existing `build_app.sh` signing sequence.

### Build Script

Create a `build.sh` that runs after Xcode's archive:

```bash
#!/bin/bash
set -e

APP="TypeProofing.app"
CODESIGN_ID="Developer ID Application: Your Name (TEAMID)"

# Sign Python packages' native extensions
find "dist/${APP}/Contents/Resources/python-lib" \
    -name '*.so' -or -name '*.dylib' |
    while read libfile; do
        codesign --force --sign "${CODESIGN_ID}" \
            --options runtime --timestamp "${libfile}"
    done

# Sign Python framework
codesign --force --sign "${CODESIGN_ID}" \
    --options runtime --timestamp \
    "dist/${APP}/Contents/Frameworks/Python.framework/Versions/3.13/Python"

# Sign DrawBot tools
for tool in ffmpeg potrace gifsicle mkbitmap; do
    TOOL_PATH="dist/${APP}/Contents/Resources/python-lib/drawBot/context/tools/${tool}"
    if [ -f "${TOOL_PATH}" ]; then
        codesign --force --sign "${CODESIGN_ID}" \
            --options runtime --timestamp "${TOOL_PATH}"
    fi
done

# Sign the app bundle with entitlements
codesign --force --sign "${CODESIGN_ID}" \
    --options runtime --timestamp \
    --entitlements TypeProofing.entitlements \
    "dist/${APP}"

# Verify
codesign --verify --deep --strict "dist/${APP}"
spctl --assess --type exec "dist/${APP}"
```

### DMG Creation

Same approach as current distribution:

```bash
# Create DMG
hdiutil create -volname "Type Proofing" \
    -srcfolder "dist/TypeProofing.app" \
    -ov -format UDZO \
    "dist/TypeProofing.dmg"

# Sign the DMG
codesign --force --sign "${CODESIGN_ID}" --timestamp "dist/TypeProofing.dmg"
```

### Notarization (Optional but Recommended)

```bash
xcrun notarytool submit "dist/TypeProofing.dmg" \
    --apple-id "your@email.com" \
    --team-id "TEAMID" \
    --password "@keychain:notarize-password" \
    --wait

xcrun stapler staple "dist/TypeProofing.dmg"
```

### Dependency Checklist

These packages must be bundled in `python-lib/`. The full list from the current `setup.py` and `requirements.txt`:

| Package | Type | Notes |
|---|---|---|
| `drawBot` | Pure Python + compiled tools | Contains `ffmpeg`, `potrace`, `gifsicle`, `mkbitmap` binaries that need signing |
| `drawBotGrid` | Pure Python | From `jmsole/drawbotgrid` |
| `wordsiv` | Python + Rust `.so` | Universal2 wheel in `wheels/` directory. The `.so` must be signed |
| `fontTools` | Pure Python (mostly) | May have optional C extensions |
| `PIL/Pillow` | Python + compiled `.dylibs` | DrawBot dependency. `.dylibs` need signing |
| `booleanOperations` | Python + C extension | DrawBot dependency |
| `jaraco.text` | Pure Python | |
| `more_itertools` | Pure Python | |
| `packaging` | Pure Python | |
| `platformdirs` | Pure Python | |

**Do NOT bundle:** `vanilla`, `pyobjc`, `AppKit`, `Foundation`, `Quartz`, `CoreText`, `CoreFoundation` — these were only needed for the Python GUI. DrawBot uses `CoreGraphics` via its own PyObjC bridge which IS still needed.

**Important**: DrawBot internally imports PyObjC modules (`AppKit`, `CoreText`, etc.) for its PDF rendering. These PyObjC bridges must still be bundled. What you remove is `cocoa-vanilla` (the Vanilla GUI framework) and any direct use of these from your own code.

### Testing the Bundle

On a clean macOS machine (or a VM with no Python installed):

1. Mount the DMG
2. Drag `TypeProofing.app` to Applications
3. Open it — should launch without "Python not found" errors
4. Load a font, enable a proof, generate — should produce a PDF

---

## Migration Sequence Summary

| Phase | Builds On | Output | Estimated Scope |
|---|---|---|---|
| **1: engine.py** | Existing Python codebase | Headless Python module, no UI imports | ~200 lines new Python |
| **2: Xcode project** | Phase 1 | Bare app that loads Python engine | Xcode config + ~50 lines Swift |
| **3: ProofEngine bridge** | Phase 2 | Swift class wrapping all Python calls | ~300 lines Swift |
| **4: Main SwiftUI views** | Phase 3 | Sidebar + PDF viewer + Generate button | ~800 lines Swift |
| **5: Settings + full parity** | Phase 4 | All settings, axes, OT features, custom proofs | ~1,500 lines Swift |
| **6: Build + distribution** | Phase 5 | Signed .app in DMG | Build scripts + signing |

### Key Risks and Mitigations

**Risk: DrawBot imports PyObjC/AppKit internally.**
DrawBot uses `AppKit`, `CoreText`, `Quartz`, `CoreGraphics` for rendering. These are macOS system frameworks, but DrawBot accesses them via PyObjC bridges. The PyObjC packages must be bundled. This is the same as the current app — py2app already handles this. Verify by checking that `import drawBot` works in the bundled Python.

**Risk: PythonKit + DrawBot thread safety.**
DrawBot is not thread-safe. All DrawBot calls must happen on the same thread. Use `Task.detached` for the generation call, but ensure only one generation runs at a time. The `@Published var isGenerating` flag prevents concurrent generation.

**Risk: wordsiv Rust extension loading.**
The `.so` file must match the Python version (cp39-abi3 means Python 3.9+ ABI). Ensure it's codesigned and in the `PYTHONPATH`. The current `wheels/` directory already has the universal2 build.

**Risk: Python.framework size.**
A full Python.framework is ~80MB. Use `python-build-standalone` for a stripped-down version if size matters. The current py2app build produces a ~150MB app bundle, so this is comparable.
