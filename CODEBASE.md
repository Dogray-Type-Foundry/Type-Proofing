# CODEBASE.md — Type Proofing Technical Reference

> This document is aimed at LLM agents and developers working on the codebase. It covers architecture, data flow, the proof system, settings, rendering pipelines, and the specific steps required to add or modify proofs.

---

## 1. What This App Does

Type Proofing is a macOS SwiftUI app that generates multi-page PDF proofing documents for fonts. A type designer loads one or more font files (`.otf`, `.ttf`), selects which proof types to generate, tweaks per-proof settings (font size, columns, OpenType features, etc.), and hits "Generate." The app produces a PDF with pages covering character sets, spacing tests, paragraph proofs, diacritic words, Arabic contextual forms, and more.

The app supports:
- Static and variable fonts (with full axis control)
- Latin and Arabic/Farsi/Urdu scripts
- Live PDF preview (per-proof fragment generation + composition)
- Premade and generative text (via WordSiv, a Rust text generator)
- A rich markup language for custom text proofs
- Multi-style comparison (all named instances or custom axis positions side-by-side)
- OpenType feature toggling per proof
- GSUB substitution overview rendering
- Settings persistence and import/export

---

## 2. High-Level Architecture

Three language layers coexist:

```
┌─────────────────────────────────────────────────┐
│  Swift / SwiftUI (macOS app)                    │
│  - UI, state management, PDF preview            │
│  - Native PDF rendering (CoreText/CoreGraphics) │
│  - Calls Rust via C FFI for font analysis       │
├─────────────────────────────────────────────────┤
│  Rust (native/ directory)                       │
│  - Font analysis: charset, axes, OT features    │
│  - GSUB substitution extraction                 │
│  - WordSiv text generation (separate crate)     │
│  - Compiled as universal2 static lib            │
├─────────────────────────────────────────────────┤
│  Python (python/ directory) — LEGACY            │
│  - Original proof engine using DrawBot          │
│  - No longer called at runtime                  │
│  - Source of truth for some proof logic patterns │
└─────────────────────────────────────────────────┘
```

**The active pipeline is Swift + Rust.** Python is legacy code kept as reference. `ProofEngine.swift` is the only file that historically bridged to Python (via PythonKit), but the current renderer is fully native.

---

## 3. Source Layout

```
TypeProofing-SwiftUI/
├── project.yml                    # XcodeGen project definition (DO NOT edit .xcodeproj directly)
├── NativeLib/
│   ├── libtpnative.a             # Compiled Rust static library (universal2, gitignored)
│   └── include/tpnative.h        # Auto-generated C header (cbindgen)
├── Scripts/
│   ├── build_release.sh           # Signed DMG creation
│   ├── bundle_python_packages.sh  # Legacy: bundle Python deps
│   └── copy_python_sources.sh     # Legacy: copy Python to bundle
├── TypeProofing/
│   ├── Sources/
│   │   ├── TypeProofingApp.swift         # @main, creates ProofEngine + AppState, injects into environment
│   │   ├── AppState.swift                # Central state (928 lines), split into 6 sub-objects
│   │   ├── ProofEngine.swift             # Rust FFI wrapper, proof generation orchestration (706 lines)
│   │   ├── ContentView.swift             # Main 4-panel layout (601 lines)
│   │   ├── SidebarView.swift             # Left panel: fonts, proofs, output, generate (351 lines)
│   │   ├── SettingsPanelView.swift        # Right panel: per-proof settings inspector (1265 lines)
│   │   ├── PDFViewerView.swift           # PDF display + thumbnails + grid/compare views (903 lines)
│   │   ├── PreviewCoordinator.swift       # Async preview generation pipeline (497 lines)
│   │   ├── AppFont.swift                 # Custom app font (SetsGroteskVF)
│   │   ├── FontsSection.swift            # Font list UI + drag/drop
│   │   ├── FontAxesView.swift            # Variable font axis sliders
│   │   ├── FontStyleSelectionViews.swift  # Default font picker, multi-style font list
│   │   ├── FontSortBar.swift             # Font sorting controls
│   │   ├── FontSortCriterion.swift        # Sort criteria enum
│   │   ├── SidebarListRow.swift          # Reusable sidebar row component
│   │   ├── HoverComponents.swift         # Hover state UI helpers
│   │   └── NativeRenderer/               # PDF generation engine (see §5)
│   │       ├── NativeProofOrchestrator.swift   # Main generation coordinator
│   │       ├── ProofRegistry.swift             # All 22 proof type definitions
│   │       ├── ProofHandler.swift              # Protocol + shared rendering logic
│   │       ├── PDFRenderer.swift               # CGContext PDF wrapper
│   │       ├── TextRenderer.swift              # CoreText text rendering
│   │       ├── PageLayout.swift                # Page dimensions, columns, footer
│   │       ├── FontLoader.swift                # CTFont loading with features/variations
│   │       ├── StandardTextProofHandler.swift   # Text paragraph proofs
│   │       ├── CategoryBasedProofHandler.swift  # Character set + spacing proofs
│   │       ├── ArabicProofHandler.swift         # Arabic contextual forms
│   │       ├── CustomTextProofHandler.swift     # User-provided text proofs
│   │       ├── SubstitutionOverviewHandler.swift # GSUB feature display
│   │       ├── MultiStyleComparisonHandler.swift # Side-by-side style comparison
│   │       ├── MarkupParser.swift              # Markup tokenizer
│   │       ├── MarkupRenderer.swift            # Markup → attributed string
│   │       ├── TextGeneration.swift            # Text content generation logic
│   │       ├── PremadeTexts.swift              # Static text samples + accented dictionary
│   │       ├── WordSivBridge.swift             # FFI wrapper for WordSiv text generator
│   │       ├── StylePairing.swift              # Upright/italic, regular/bold detection
│   │       ├── CharacterCategorizer.swift       # Unicode category classification
│   │       ├── BaselineGrid.swift              # Debug grid overlay
│   │       └── AutoSizing.swift                # Binary search font sizing
│   └── Resources/
│       ├── accented_dictionary.json            # Character → accented word examples
│       └── Assets.xcassets                     # App icons, colors
│
├── TypeProofingTests/             # Unit tests
└── TypeProofingUITests/           # UI tests

native/
├── Cargo.toml                     # Workspace: tp-fonts + tp-bridge
├── build_rust.sh                  # Build universal2 + generate header
├── include/tpnative.h             # Generated C header
├── tp-fonts/src/
│   ├── lib.rs                     # Module declarations
│   ├── font_info.rs               # Font metadata (family, weight, axes, features)
│   ├── charset.rs                 # Filtered charset (outlines only, cmap + AGL fallback)
│   ├── axes.rs                    # Variable font axis values + Cartesian product
│   ├── substitutions.rs           # GSUB lookup extraction (single, ligature, contextual)
│   └── agl.rs                     # Adobe Glyph List name→Unicode mapping
└── tp-bridge/src/
    └── lib.rs                     # C FFI exports (tp_load_font, tp_get_charset, wsv_*, etc.)

python/                            # LEGACY — not called at runtime
├── engine.py                      # Headless proof generation entry point
├── proof.py                       # Proof handler classes (2974 lines)
├── config.py                      # Proof registry, page formats, constants
├── fonts.py                       # Font analysis utilities
├── settings.py                    # Settings persistence
├── sample_texts.py                # Premade Latin text samples
├── script_texts.py                # Arabic/Farsi text samples
├── accented_dictionary.py         # Character → accented word mapping
├── text_generators.py             # Text generation helpers
├── markup_parser.py               # Markup parsing
├── opentype_substitutions.py      # GSUB extraction
├── generation_config.py           # Typed generation config
├── diagnostics.py                 # Diagnostic event collection
├── pdf_manager.py                 # PDF output management
└── worker.py                      # Background worker process
```

---

## 4. State Architecture

The app uses a hierarchical `@MainActor ObservableObject` pattern. `AppState` is the root, with 6 published sub-objects:

```swift
@main struct TypeProofingApp: App {
    @StateObject private var engine = ProofEngine()
    @StateObject private var appState = AppState()
    // All 6 sub-objects injected as individual @EnvironmentObject
}
```

### 4.1 State Objects

| Object | Purpose | Key Properties |
|--------|---------|----------------|
| **FontState** | Loaded fonts, axes, styles | `fontPaths`, `loadedFonts: [FontInfo]`, `axisValuesByFont`, `disabledFontPaths`, `fontStyles: [FontStyleEntry]`, `styleSourceMode` (.namedInstances / .customPositions) |
| **ProofState** | Proof instances, selection | `proofOptions: [ProofOption]`, `selectedProof: UUID?`, `proofSettingsByProof: [name: ProofSettings]`, `registryByKey` |
| **PreviewState** | Preview/final PDF paths | `previewPDFPath`, `previewSections: [ProofSection]`, `finalPDFPath`, `currentConfigFingerprint`, `finalGeneratedConfigFingerprint` |
| **PageState** | Page format, view mode | `pageFormat` ("A4Landscape", etc.), `showBaselines`, `viewMode` (.page/.grid/.compare) |
| **UIState** | Panel visibility, widths | `showSidebar`, `showInspector`, `showThumbnailStrip`, panel widths, section expansion state |
| **OutputState** | PDF output directory | `useCustomLocation`, `customLocation` |

### 4.2 ProofOption (Per-Instance)

Each proof in the sidebar is a `ProofOption` instance:

```swift
struct ProofOption: Identifiable, Codable {
    let id: UUID          // Unique per instance
    var name: String      // Display name, e.g. "Spacing Test 2"
    var baseType: String  // Registry key, e.g. "spacing_proof"
    var enabled: Bool
    var order: Int        // Position in sidebar list
}
```

Multiple instances of the same proof type can coexist with different settings. The `name` field is the settings key — each instance has its own `ProofSettings` in `proofSettingsByProof`.

### 4.3 ProofSettings (Per-Instance)

```swift
struct ProofSettings: Codable {
    var fontSize: Double            // 4–200 pt
    var tracking: Double            // Letter spacing in points
    var lineHeight: Double          // Em multiplier (default 1.2)
    var columns: Int                // 1–6
    var paragraphs: Int             // 1–20
    var alignment: String           // "left" / "center" / "right" / "justified"
    var customText: String          // For custom_text / multi_style_comparison
    var markupEnabled: Bool         // Parse markup in custom text
    var generateOnce: Bool          // Render once (not per font)
    var categories: CategorySettings // uppercase/lowercase/numbersSymbols/punctuation/accented toggles
    var otFeatures: [OTFeature]     // Per-proof OpenType feature toggles
    var substitutionFeatures: [SubstitutionFeature]  // GSUB feature toggles
    var autoSize: Bool              // Binary-search fit to page
    var showFallback: Bool          // Show missing glyphs in multi-style
    var columnGap: Double           // Column gutter in points
    var direction: String           // "ltr" / "rtl" / "auto"
    var paragraphIndent: Double
    var paragraphSpace: Double
    var hyphenation: Bool
    var hangingPunctuation: Bool
    var enabledStyleIndices: [String: Bool]  // Multi-style: which styles are visible
    var defaultFontPath: String     // For generateOnce mode
    var defaultFontAxisDict: [String: Double]?
}
```

### 4.4 Settings Persistence

- **Auto-save**: `~/.type-proofing-swiftui-prefs.json`, debounced 3 seconds
- **Settings key derivation**: `pythonProofKey(for:)` lowercases and replaces spaces/dashes/slashes with underscores
- **Flattening**: `buildFlatProofSettings()` converts nested `ProofSettings` into flat keys like `"spacing_proof_fontSize"`, `"otf_spacing_proof_kern"` — this format is consumed by the renderer
- **Fingerprint**: SHA256 of sorted JSON config, used to detect changes and skip redundant regeneration

### 4.5 OT Feature Defaults

Two key constant sets control feature behavior:

```swift
let DEFAULT_ON_FEATURES: Set<String> = [
    "ccmp", "kern", "calt", "rlig", "liga", "mark", "mkmk",
    "clig", "dist", "rclt", "rvrn", "curs", "locl"
]

let HIDDEN_FEATURES: Set<String> = [
    "init", "medi", "med2", "fina", "fin2", "fin3", "isol",
    "curs", "aalt", "rand"
]
```

Hidden features are never shown in the UI. Default-on features are enabled when a proof is first created. The spacing proof force-disables `kern`.

---

## 5. Native Renderer Pipeline

### 5.1 Orchestration Flow

```
NativeProofOrchestrator.generate(config)
  │
  ├─ For each font path:
  │    ├─ Read font file into Data
  │    ├─ tp_get_charset() → filtered character string
  │    ├─ CharacterCategorizer.categorize() → CharacterCategories
  │    ├─ FontLoader.register(url:) → register in process scope
  │    │
  │    ├─ For each axis combination (Cartesian product):
  │    │    │
  │    │    ├─ For each enabled ProofOption:
  │    │    │    ├─ makeHandler(baseType) → ProofHandler
  │    │    │    ├─ Build ProofContext (charset, categories, features, settings)
  │    │    │    └─ handler.generateProof(context, renderer)
  │    │    │         ├─ Resolve params (fontSize, cols, tracking, etc.)
  │    │    │         ├─ Generate/load text content
  │    │    │         ├─ FontLoader.makeFont(path, size, features, variations)
  │    │    │         ├─ TextRenderer.makeAttributedString(...)
  │    │    │         └─ drawContent(...) → multi-page column rendering
  │    │    │              ├─ PDFRenderer.beginPage()
  │    │    │              ├─ PageLayout.drawFooter(...)
  │    │    │              ├─ BaselineGrid (if showBaselines)
  │    │    │              ├─ TextRenderer.drawText() per column
  │    │    │              └─ PDFRenderer.endPage()
  │    │    │
  │    │    └─ Track ProofSection (page ranges per proof)
  │    │
  │    └─ FontLoader.unregister(url:)
  │
  └─ PDFRenderer.close() → finalized PDF
```

### 5.2 ProofHandler Protocol

```swift
protocol ProofHandler {
    var proofName: String { get }
    var proofKey: String { get }
    func generateProof(context: ProofContext, renderer: PDFRenderer)
}
```

The protocol extension provides shared utilities:
- `resolveParams(from:)` → `ProofParams` — extracts all settings from the flat dict
- `drawContent(...)` — multi-column paginated text rendering with footer, baselines, overflow
- `makeSettingsKey(...)` — constructs keys like `"basic_paragraph_large_fontSize"`
- `axisLabel(from:)` — formats axis values for footer display

### 5.3 Handler Dispatch (makeHandler)

```swift
switch baseType {
case "filtered_character_set":     → FilteredCharacterSetHandler
case "spacing_proof":              → SpacingProofHandler
case "ar_character_set":           → ArCharacterSetHandler
case "custom_text":                → CustomTextProofHandler
case "substitution_overview":      → SubstitutionOverviewHandler
case "multi_style_comparison":     → MultiStyleComparisonHandler
default (all text proofs):         → StandardTextProofHandler
}
```

### 5.4 Handler Details

**StandardTextProofHandler** — Handles 14 of the 22 proof types (all the text-based paragraph proofs). Uses `TextProofConfig` from the registry entry to determine:
- Which character set to use (`base_letters`, `accented_plus`, `arabic`, `farsi`)
- Whether to use premade text, generative text (WordSiv), or Hoefler-style contextual text
- Whether to render mixed styles (alternating bold/italic via `StylePairing`)
- Whether to inject premade text blocks (e.g., vocalization, numbers)

**FilteredCharacterSetHandler** — Renders characters grouped by category (uppercase, lowercase, numbers, punctuation, accented). Supports auto-sizing via binary search to fit all characters on one page.

**SpacingProofHandler** — Renders each character flanked by control characters (e.g., `HHHnHOnOOO`). Force-disables `kern` and `liga`.

**ArCharacterSetHandler** — Renders Arabic characters showing contextual forms (isolated, initial, medial, final). Detects dual-join vs. right-join characters.

**CustomTextProofHandler** — Renders user-provided text. Supports the markup language (bold, italic, headings, attributes, page/column breaks). Has `generateOnce` mode that renders with a single specified font across all fonts.

**SubstitutionOverviewHandler** — Reads the font's GSUB table (via Rust FFI), displays input→output glyph substitutions with glyph name annotations. 5-column layout.

**MultiStyleComparisonHandler** — Renders the same text in every enabled font style (named instances or custom axis positions), one line per style. Supports category-based text groups + custom text.

---

## 6. The Proof Registry — Complete Reference

The registry at `ProofRegistry.swift` defines all 22 proof types. This is **the single source of truth** for what proofs exist.

### 6.1 Latin Proofs

| Key | Display Name | Default Size | Default Cols | Notable |
|-----|-------------|-------------|-------------|---------|
| `filtered_character_set` | Character Overview | 78pt | 1 | hasCategories, autoSize option |
| `spacing_proof` | Spacing Test | 14pt | 2 | hasCategories, force-disables kern |
| `basic_paragraph_large` | Structured Text - Heading | 28pt | 1 | hoeflerStyle text |
| `diacritic_words_large` | Accented Words - Heading | 28pt | 1 | accents: 3 |
| `basic_paragraph_small` | Structured Text - Text | 9pt | 2 | hoeflerStyle text |
| `paired_styles_paragraph_small` | Style Pairing | 9pt | 2 | mixedStyles, forceWordsiv |
| `generative_text_small` | Auto-Generated Text | 9pt | 2 | forceWordsiv, hasParagraphs |
| `diacritic_words_small` | Accented Words - Text | 9pt | 2 | accents: 3 |
| `misc_paragraph_small` | Practical Figures & Punctuation | 9pt | 2 | injectTextKey: "misc_small_injects" |
| `custom_text` | Custom Text | 16pt | 1 | hasCustomText, markup support |
| `multi_style_comparison` | Style Comparison | 24pt | 1 | hasCustomText, hasCategories, multiStyle |
| `substitution_overview` | Substitution Overview | 28pt | 5 | defaultEnabled: false (opt-in) |

### 6.2 Arabic Proofs (isArabic: true)

| Key | Display Name | Default Size | Default Cols | Notable |
|-----|-------------|-------------|-------------|---------|
| `ar_character_set` | Ar Character Overview | 64pt | 1 | Contextual forms display |
| `ar_paragraph_large` | Ar Structured Text - Heading | 28pt | 1 | language: "ar" |
| `fa_paragraph_large` | Fa Structured Text - Heading | 28pt | 1 | language: "fa" |
| `ar_paragraph_small` | Ar Structured Text - Text | 9pt | 1 | language: "ar" |
| `fa_paragraph_small` | Fa Structured Text - Text | 9pt | 1 | language: "fa" |
| `ar_vocalization_paragraph_small` | Ar Vowel Marks | 9pt | 2 | injectTextKey: "arabicVocalization" |
| `ar_lat_mixed_paragraph_small` | Ar-Latin Mixed | 9pt | 2 | injectTextKey: "arabicLatinMixed" |
| `ar_numbers_small` | Ar Numerals | 9pt | 2 | injectTextKey: "arabicFarsiUrduNumbers" |
| `ar_generative_paragraph_small` | Ar All Combinations | 9pt | 2 | hoeflerStyle, language: "ar" |
| `fa_generative_paragraph_small` | Fa All Combinations | 9pt | 2 | hoeflerStyle, language: "fa" |

### 6.3 TextProofConfig Fields

Each standard text proof has a `TextProofConfig`:

```swift
struct TextProofConfig {
    let characterSetKey: String     // "base_letters", "accented_plus", "arabic", "farsi"
    let defaultParagraphs: Int
    let forceWordsiv: Bool          // Force WordSiv generation (skip premade text)
    let mixedStyles: Bool           // Alternate regular/italic or regular/bold
    let accents: Int                // Number of accented word examples per character
    let language: String?           // "en", "ar", "fa" — affects text generation
    let hoeflerStyle: Bool          // Context-aware word pairing (round/flat neighbors)
    let injectTextKey: String?      // Key to PremadeTexts for injected content
}
```

---

## 7. How to Add a New Proof Type

Adding a new proof requires changes in exactly 3 places (plus optionally a 4th for custom handlers):

### Step 1: Register in ProofRegistry.swift

Add a new `ProofRegistryInfo` entry to the `entries` array:

```swift
ProofRegistryInfo(
    key: "my_new_proof",
    displayName: "My New Proof",
    isArabic: false,
    hasSettings: true,
    defaultCols: 2,
    hasParagraphs: true,
    defaultSize: 12,
    hasCustomText: false,
    hasCategories: false,
    multiStyle: false,
    defaultEnabled: false,
    textConfig: TextProofConfig(
        characterSetKey: "base_letters",
        defaultParagraphs: 5,
        forceWordsiv: false,
        mixedStyles: false,
        accents: 0,
        language: nil,
        hoeflerStyle: false,
        injectTextKey: nil
    )
)
```

Also add the key to `defaultProofOrder`.

### Step 2: Add Handler Dispatch (if custom handler needed)

If the new proof follows the standard text pattern, `StandardTextProofHandler` handles it automatically based on the `TextProofConfig`. No code change needed.

If it needs custom rendering, create a new handler class and add a case to `NativeProofOrchestrator.makeHandler()`:

```swift
case "my_new_proof": return MyNewProofHandler(proofName: proofName, proofKey: proofKey)
```

### Step 3: Create Handler Class (if custom)

Implement `ProofHandler`:

```swift
final class MyNewProofHandler: ProofHandler {
    let proofName: String
    let proofKey: String

    init(proofName: String, proofKey: String) {
        self.proofName = proofName
        self.proofKey = proofKey
    }

    func generateProof(context: ProofContext, renderer: PDFRenderer) {
        let params = resolveParams(from: context)
        // ... custom rendering logic ...
        // Use drawContent() for standard column rendering
        // Or call renderer/TextRenderer directly for custom layouts
    }
}
```

### Step 4: Settings UI (automatic)

`SettingsPanelView` automatically renders controls based on the registry entry's flags:
- `hasSettings` → shows the settings panel
- `hasParagraphs` → shows paragraph count control
- `hasCustomText` → shows text editor + markup toggle
- `hasCategories` → shows category checkboxes
- `multiStyle` → shows style source picker + font style list
- `supportsCols` (derived) → shows columns/gap controls
- `supportsFormatting` (derived) → shows alignment, direction, hyphenation, etc.

No UI code changes needed unless the proof needs truly novel controls.

---

## 8. Rust Native Library (native/)

### 8.1 Architecture

Two crates in a Cargo workspace:
- **`tp-fonts`** — Pure Rust font analysis library, no FFI
- **`tp-bridge`** — C FFI exports that wrap tp-fonts + WordSiv

Dependencies: `read-fonts` 0.39, `skrifa` 0.42 (Google Fonts Rust libraries), `wordsiv` (private crate from Dogray Type Foundry).

### 8.2 FFI Functions (tpnative.h)

```c
// Font analysis
TPFontInfo *tp_load_font(const uint8_t *data, uintptr_t len);
void tp_free_font_info(TPFontInfo *ptr);
char *tp_get_charset(const uint8_t *data, uintptr_t len);
char *tp_get_axes_json(const uint8_t *data, uintptr_t len);
char *tp_get_named_instances_json(const uint8_t *data, uintptr_t len);
char *tp_get_substitutions_json(const uint8_t *data, uintptr_t len);

// Text generation (WordSiv)
WordSiv *wsv_create(uint64_t seed);
void wsv_free(WordSiv *ptr);
char *wsv_text(WordSiv *ptr, const char *glyphs, uint32_t n_paras, ...);
char *wsv_words(WordSiv *ptr, const char *glyphs, const char *case_str, ...);
char *wsv_top_word(WordSiv *ptr, const char *glyphs, ...);
void wsv_seed(WordSiv *ptr, uint64_t seed);
```

**Memory convention**: All `char *` returns are heap-allocated by Rust. Caller must free via `wsv_free_string()` or `tp_free_font_info()`. NULL return means error.

### 8.3 TPFontInfo Struct

```c
typedef struct TPFontInfo {
    char *family_name;
    char *subfamily_name;
    uint16_t weight;      // OS/2 usWeightClass
    uint16_t width;       // OS/2 usWidthClass
    uint16_t fs_selection; // Bit flags (bit 0 = italic, bit 5 = bold, bit 6 = regular)
    bool is_variable;
    double slant;         // -12.0 for italic, 0.0 for upright
    double optical_size;  // Default opsz value or 0.0
    char *axes_json;      // JSON: [{"tag":"wght","min":100,"default":400,"max":900}]
    char *features_json;  // JSON: ["kern","calt","ss01"]
} TPFontInfo;
```

### 8.4 Charset Detection (charset.rs)

1. Parse font as `FontRef` via skrifa
2. Iterate cmap best subtable by codepoint
3. For each mapping, verify the glyph has actual outlines (not just a cmap entry):
   - Check `glyf` table: `numberOfContours != 0`
   - Check `CFF`/`CFF2`: outline provider
4. Fallback: if cmap is empty, use Adobe Glyph List (agl.rs) for name→Unicode mapping
5. Return sorted string of renderable characters

### 8.5 GSUB Substitution Extraction (substitutions.rs)

Extracts GSUB feature substitutions for the SubstitutionOverview proof:
- Handles lookup types: Single (1:1), Ligature (N:1), ChainContextual (conditional)
- Skips positional features: init, medi, fina, isol, curs, aalt, rand
- Builds context strings for contextual substitutions
- Returns JSON array of features with entries (input/output glyph IDs, names, context)

### 8.6 Build Process

```bash
bash native/build_rust.sh
# 1. cargo build --release --target aarch64-apple-darwin -p tp-bridge
# 2. cargo build --release --target x86_64-apple-darwin -p tp-bridge
# 3. lipo -create → lib/libtpnative.a (universal2)
# 4. cbindgen → include/tpnative.h
```

The Xcode project has a pre-build script that auto-builds if `libtpnative.a` is missing.

---

## 9. Preview System

### 9.1 PreviewCoordinator

The live preview is not a single-shot generation. It decomposes proofs into **fragments** (one PDF per proof) and composes them into a single preview PDF.

```
State change detected
  → Debounce (2s for global changes, 2s per proof)
  → invalidateAll() or invalidateProof(id)
  → Queue PreviewJobs by cost (.fast or .wordsiv)
  → pumpQueues() — run up to N fast jobs in parallel, 1 wordsiv at a time
  → Each job: engine.generatePreviewFragment(config)
  → On completion: requestCompose() (debounced 75ms)
  → composePreview() — merge fragment PDFs into one
  → Update state.preview.previewPDFPath
```

Key design choices:
- **Two queues**: `.fast` proofs (character set, spacing) run in parallel; `.wordsiv` proofs (text generation) are serialized to avoid WordSiv contention
- **Fingerprinting**: Each fragment has a SHA256 fingerprint. If settings haven't changed, the existing fragment is reused
- **Priority**: The currently-selected proof gets priority in the queue
- **Pause/resume**: Final generation pauses the preview coordinator to avoid contention

### 9.2 PDF Viewer

`PDFViewerView.swift` provides three view modes:
- **Page view**: Standard scrollable PDFView with zoom (10–500%)
- **Grid view**: Lazy grid of all pages with section headers
- **Compare view**: Side-by-side PDFs with synced scroll/zoom (for before/after comparison)

The thumbnail strip shows page thumbnails with proof section headers. Thumbnails are cached (up to 500) and eagerly rendered.

Viewport anchor preservation: when the PDF is reloaded (after a preview update), the viewer restores the previous scroll position and zoom level.

---

## 10. Text Generation System

### 10.1 Text Sources

Text for proofs comes from multiple sources, selected by the handler:

1. **Premade texts** (PremadeTexts.swift): Static pangrams, paragraph samples, Arabic vocalization text, numbers
2. **Accented dictionary** (accented_dictionary.json): Maps base characters to words containing accented variants
3. **WordSiv** (Rust crate via FFI): Generates pseudo-random text constrained to a font's character set
4. **Hoefler-style generation** (TextGeneration.swift): Context-aware word pairing — each character is shown in words with specific neighboring character shapes (round, flat, diagonal)
5. **Custom text** (user-provided): Plain or markup text entered in the settings panel

### 10.2 Markup Language

Custom text supports a markup syntax:

| Syntax | Effect |
|--------|--------|
| `**text**` | Bold |
| `*text*` | Italic |
| `***text***` | Bold italic |
| `# text` | Heading 1 |
| `## text` | Heading 2 |
| `[text]{attr:value}` | Attribute span |
| `#pagebreak()` | Insert page break |
| `#colbreak()` | Insert column break |
| `\\`, `\*`, `\#` | Escape characters |

Attribute span supports: `wght`, `opsz`, `wdth`, `ital`, `slnt` (axis values), `size` (multiplier), `color` (hex), `tracking`, `style` (font style name), `feat` (OT features, prefix `-` to disable).

### 10.3 Style Pairing

For mixed-style proofs (`paired_styles_paragraph_small`), the system detects style pairs:
1. Static upright + italic (same weight)
2. Static regular + bold
3. Variable font with `ital` axis
4. Variable font with `wght` axis (≥600 threshold)

Text is rendered alternating between styles every 1–4 words (deterministic via seeded XorShift64 RNG).

---

## 11. Page Layout & Rendering

### 11.1 Page Formats

| Format | Width × Height (points) |
|--------|------------------------|
| A3Landscape | 1190 × 842 |
| A4Landscape | 842 × 595 |
| A5Landscape | 595 × 420 |
| LetterLandscape | 792 × 612 |
| LegalLandscape | 1008 × 612 |

Margins: 50pt vertical, 40pt horizontal. Default column gutter: 20pt.

### 11.2 Footer

Each page has a footer with:
- Left: `date time | font_name | proof_name - axis_label`
- Right: page number
- Second line (7pt): `OT Fea: ON: smcp, OFF: kern | Tracking: 5 | Line Height: 1.5` (non-default features only)

### 11.3 CoreText Rendering

`TextRenderer.swift` uses two rendering paths:
- **CTFramesetter** (default): Standard CoreText layout
- **NSLayoutManager** (when hyphenation is enabled): Uses TextKit for hyphenation support

For strings >2000 characters, enables unbounded layout to prevent CoreText truncation.

---

## 12. Unicode & Character Categorization

`CharacterCategorizer` classifies a font's character set into Unicode categories:

| Category | Unicode Properties |
|----------|-------------------|
| `uniLu` | Uppercase letters |
| `uniLl` | Lowercase letters |
| `uniLo` | Other letters |
| `uniNd` | Decimal numbers |
| `uniNo` | Other numbers |
| `uniPo`, `uniPc`, `uniPd`, `uniPs`, `uniPe`, `uniPi`, `uniPf` | Punctuation (various) |
| `uniSm`, `uniSc`, `uniSo` | Symbols (math, currency, other) |
| `accented` | Letters with combining marks |
| `accentedPlus` | accented + non-Latin letters |

Arabic-specific:
- `ar`: Core Arabic character set (13 main characters)
- `fa`: Farsi additions
- `arabTyped`: All characters in Arabic Unicode ranges (0x0600–0x06FF, 0x0750–0x077F, 0x08A0–0x08FF, 0xFB50–0xFDFF, 0xFE70–0xFEFF)
- `arfaDualJoin`: Characters that connect on both sides
- `arfaRightJoin`: Characters that connect on right side only

---

## 13. Build & Project Configuration

### 13.1 XcodeGen

The Xcode project is generated from `TypeProofing-SwiftUI/project.yml`:
- **Never edit `.xcodeproj` directly** — run `xcodegen generate`
- Deployment target: macOS 26.0
- Swift 5.9
- SPM dependency: CompactSlider 2.1+
- Links `libtpnative.a` via `LIBRARY_SEARCH_PATHS` + `OTHER_LDFLAGS`
- Swift module map for C header: `SWIFT_INCLUDE_PATHS` → `NativeLib/include/`
- Pre-build script auto-builds Rust if `.a` is missing

### 13.2 Bundle Identifier

`com.dograytype.typeproofing`, version 2.0.0, category: Graphics & Design.

---

## 14. Settings File Schema

Settings persist to `~/.type-proofing-swiftui-prefs.json`. The full schema is documented in `README_SETTINGS.md`. Key sections:

```json
{
    "version": "1.0",
    "fonts": {
        "paths": ["/path/to/font.otf"],
        "axis_values": { "/path/to/font.otf": { "wght": 400 } }
    },
    "proof_options": {
        "filtered_character_set": true,
        "spacing_proof": true
    },
    "proof_settings": {
        "BigParagraphProof_cols": 1,
        "SmallParagraphProof_cols": 2,
        "otf_BigParagraphProof_kern": true
    },
    "page_format": "A4Landscape",
    "pdf_output": {
        "use_custom_location": false,
        "custom_location": ""
    }
}
```

Users can duplicate this file, rename it, and load it via "Import Settings" to switch between project configurations.

---

## 15. Non-Obvious Patterns & Gotchas

### Proof Instance vs. Proof Type
A proof *type* is a registry entry (e.g., `"spacing_proof"`). A proof *instance* is a `ProofOption` with a unique UUID, name, and settings. Users can add multiple instances of the same type with different settings. The `baseType` field links an instance to its registry entry.

### Settings Key Derivation
Settings keys are derived from the proof *instance name*, not the type key. `pythonProofKey(for:)` lowercases and replaces non-alphanumeric characters with underscores. For named instances like "Spacing Test 2", the key becomes `"spacing_test_2"`. OT features are prefixed: `"otf_spacing_test_2_kern"`.

### Axis Cartesian Product
For variable fonts, the app generates a Cartesian product of all axis values. If a font has `wght: [100, 400, 900]` and `opsz: [8, 32]`, that's 6 combinations, each generating its own proof pages.

### Preview Fragment Composition
The preview PDF is a composition of individual fragment PDFs, one per proof. Fragments are generated independently and cached by fingerprint. Composition merges them in proof order with section markers for thumbnail navigation.

### Arabic Contextual Form Detection
Arabic proof rendering distinguishes dual-join characters (connect both sides: ب, ت, ث, etc.) from right-join characters (connect right only: ا, د, ر, etc.). This affects how the contextual form display is generated.

### WordSiv Charset-Constrained Generation
WordSiv generates text using only glyphs available in the loaded font. It takes a character set string and produces words from English, Arabic, or Farsi vocabularies. Seed 987654 ensures deterministic output.

### Auto-Sizing Binary Search
For character set proofs, the auto-size feature uses binary search (range 4–200pt) to find the largest font size that fits all characters on one page.

### Hanging Punctuation
Implemented via Apple Advanced Typography (AAT) feature type 22, selector 1. Only available if the font supports `opbd` (optical bounds). `FontLoader.fontSupportsOpbd()` checks for this.

### Substitution Overview
The GSUB substitution data comes from Rust (`tp_get_substitutions_json`), not from CoreText. The handler displays input glyphs → output glyphs with feature-on rendering, plus glyph name annotations.

### Multi-Style "Generate Once"
The `CustomTextProofHandler` with `generateOnce: true` renders the custom text exactly once using a specified default font, rather than once per loaded font. A static set tracks which instances have already generated to prevent duplicates.

---

## 16. Testing

```bash
# Python unit tests (mocked, no external deps)
python3 -m pytest tests/ -v

# Python integration tests (real fonts + DrawBot)
python3 -m pytest tests_integration/ -v

# Swift unit + UI tests
xcodebuild -project TypeProofing-SwiftUI/TypeProofing.xcodeproj -scheme TypeProofing test
```

Swift test files cover: markup parsing, category-based proofs, native library FFI, renderer output, proof key generation, standard text handler, diagnostics.
