# Type Proofing — Complete Codebase Reference

> A macOS application for type designers to generate font proofing PDF documents. Built as a SwiftUI app with an embedded Python engine that uses DrawBot for PDF rendering.

## Table of Contents

- [What the App Does](#what-the-app-does)
- [Architecture Overview](#architecture-overview)
- [Directory Structure](#directory-structure)
- [Build System](#build-system)
- [SwiftUI Layer (GUI)](#swiftui-layer-gui)
- [Python Layer (Engine)](#python-layer-engine)
- [Data Flow: From Button Click to PDF](#data-flow-from-button-click-to-pdf)
- [The Proof Registry](#the-proof-registry)
- [Proof Handler System](#proof-handler-system)
- [Settings System](#settings-system)
- [Font Management](#font-management)
- [Text Generation](#text-generation)
- [Markup Parser](#markup-parser)
- [PDF Management](#pdf-management)
- [Module Dependency Graph](#module-dependency-graph)
- [Key Constants and Defaults](#key-constants-and-defaults)
- [Conventions and Patterns](#conventions-and-patterns)

---

## What the App Does

Type Proofing generates PDF documents that type designers use to visually evaluate their fonts. The user loads one or more font files, selects which proof types to generate (character sets, spacing tests, paragraph proofs, etc.), tweaks per-proof settings (font size, columns, tracking, OpenType features), and clicks **Generate**. The app produces a multi-page PDF with all selected proofs for all loaded fonts.

**Key capabilities:**
- Analyzes font character sets, OpenType features, and variable font axes automatically
- Supports 24 proof types covering Latin, Arabic, Persian, and mixed scripts
- Handles both static and variable fonts — variable fonts generate proof pages for each axis combination
- Pairs regular/italic and regular/bold styles for mixed-style proofs
- Supports custom text input with a lightweight markup syntax for inline styling
- Multi-style comparison proofs showing one line per font style on the same page
- Auto-sizing mode that binary-searches for the largest font size that fits content on a page

---

## Architecture Overview

The app is split into two layers:

```
┌─────────────────────────────────────────────────┐
│             SwiftUI Layer (GUI)                  │
│  TypeProofingApp → ContentView → Views           │
│  AppState (observable state + persistence)        │
│  ProofEngine (only PythonKit importer)            │
│              ↕  PythonKit bridge                  │
├─────────────────────────────────────────────────┤
│           Python Layer (Engine)                   │
│  engine.py  (headless entry point)                │
│  proof.py   (proof generation + handlers)         │
│  fonts.py   (font analysis + management)          │
│  config.py  (registry, constants, page formats)   │
│  settings.py (persistence + utilities)            │
│  markup_parser.py (custom text styling)           │
│  pdf_manager.py (PDF save + preview)              │
│  text_generators.py (text data access)            │
│  DrawBot  (PDF rendering engine)                  │
└─────────────────────────────────────────────────┘
```

**The boundary is strict:** `ProofEngine.swift` is the *only* Swift file that imports PythonKit. All Python calls go through it. SwiftUI views never touch Python directly.

**Python runs on @MainActor** because PythonKit requires the GIL to be held on a single thread. The Swift side yields to the run loop before calling into Python so the UI can show a spinner.

---

## Directory Structure

```
Type-Proofing/
├── python/                          # Python engine modules
│   ├── config.py                    # Central registry, constants, page formats
│   ├── engine.py                    # Headless entry point (called from Swift)
│   ├── fonts.py                     # Font loading, charset analysis, VF support
│   ├── proof.py                     # Proof generation handlers + drawing functions
│   ├── settings.py                  # Settings persistence + utility functions
│   ├── markup_parser.py             # Markdown-like styling for custom text
│   ├── pdf_manager.py               # PDF creation, preview, export
│   ├── text_generators.py           # Text data wrapper class
│   ├── sample_texts.py              # Pre-made Latin text samples
│   ├── script_texts.py              # Arabic/Persian/Urdu text samples
│   ├── accented_dictionary.py       # Accented character word dictionaries
│   └── eng_wiki.tsv                 # Word frequency data for Hoefler proofs
│
├── TypeProofing-SwiftUI/            # SwiftUI application
│   ├── project.yml                  # xcodegen project specification
│   ├── TypeProofing/
│   │   ├── Sources/                 # All Swift source files
│   │   │   ├── TypeProofingApp.swift
│   │   │   ├── PythonSetup.swift
│   │   │   ├── ProofEngine.swift
│   │   │   ├── AppState.swift
│   │   │   ├── ContentView.swift
│   │   │   ├── SidebarView.swift
│   │   │   ├── FontsSection.swift
│   │   │   ├── FontSortBar.swift
│   │   │   ├── FontSortCriterion.swift
│   │   │   ├── FontAxesView.swift
│   │   │   ├── SidebarListRow.swift
│   │   │   ├── FontStyleSelectionViews.swift
│   │   │   ├── SettingsPanelView.swift
│   │   │   ├── PDFViewerView.swift
│   │   │   └── HoverComponents.swift
│   │   └── TypeProofing.entitlements
│   ├── Scripts/
│   │   ├── bundle_python_packages.sh  # One-time: pip install vendored packages
│   │   ├── copy_python_sources.sh     # Build phase: copies .py + packages into bundle
│   │   └── build_release.sh           # Release build + code signing
│   ├── python-packages/               # Vendored Python packages (pip installed)
│   └── TypeProofing.xcodeproj/        # Generated by xcodegen
│
├── tests/                           # Unit tests
├── tests_integration/               # Integration tests
├── wheels/                          # Vendored Python wheels (wordsiv)
├── icon/                            # App icon assets
├── README.md                        # User guide
├── README_SETTINGS.md               # Settings file reference
├── MARKUP_PLAN.md                   # Markup syntax specification
└── requirements.txt                 # Python dependencies
```

---

## Build System

The Xcode project is generated from `project.yml` using **xcodegen**.

### Key build details:
- **Deployment target:** macOS 13.0+
- **Swift version:** 5.9
- **Python:** System Python 3.13 (`/Library/Frameworks/Python.framework`) embedded in bundle
- **SPM dependencies:**
  - **PythonKit** — Swift-to-Python bridge
  - **CompactSlider** — Multi-handle slider used for VF axis controls

### Build scripts:
1. **`bundle_python_packages.sh`** — Run once after cloning. Installs drawBot, drawBotGrid, wordsiv, fontTools, Pillow, booleanOperations, and minimal PyObjC bridges into `python-packages/`.
2. **`copy_python_sources.sh`** — Xcode build phase. Copies all `.py` files, `AdobeBlank.otf`, `eng_wiki.tsv`, and the vendored packages into the app bundle at `Resources/python-lib`.
3. **`build_release.sh`** — Release build via `xcodebuild`. Fixes `Python.framework` install names from absolute to `@rpath`, then code-signs everything inside-out.

### Regenerating the project:
```bash
cd TypeProofing-SwiftUI && xcodegen generate
```

---

## SwiftUI Layer (GUI)

### Entry Point

`TypeProofingApp.swift` — Creates the main window with two `@StateObject`s injected as environment objects:
- **`ProofEngine`** — The Python bridge
- **`AppState`** — All application state

Menu commands: Import Settings, Reset Settings, Reset Fonts.

### Window Layout

`ContentView.swift` — Three-column `HSplitView`:

```
┌──────────┬──────────────────────┬──────────┐
│ Sidebar  │    PDF Viewer        │ Settings │
│ (220w)   │  Thumbnails + PDF    │ Panel    │
│          │  (160w + rest)       │ (280w)   │
└──────────┴──────────────────────┴──────────┘
```

### Sidebar (`SidebarView.swift`)

**Top controls:** Generate button (disabled if no enabled fonts, shows spinner during generation), page format picker, baseline grid toggle.

**Two tabs:**

**Fonts tab** (`FontsSection.swift`):
- Multi-criteria sort bar with draggable chips (`FontSortBar.swift`, `FontSortCriterion.swift`)
- Font list with enable toggle, rename, delete, drag-reorder
- Variable font axes shown inline per font (`FontAxesView.swift`) — multi-handle CompactSlider with named-instance snap markers, editable value labels, add/remove handle buttons
- "Add Fonts" button + drag-drop support

**Proofs tab:**
- Reorderable list of proof options with enable toggle, rename, delete
- Arabic proofs auto-hidden when no fonts support Arabic
- "Add Proof" button → popover listing available proof types

### Settings Panel (`SettingsPanelView.swift`)

Right sidebar, dynamically shows/hides sections based on selected proof type's registry flags:

| Section | Shown when |
|---------|-----------|
| Font Size (4–200) | Always |
| Auto-size toggle | Charset or multi-style proofs |
| Line Height (0.5–5.0 em) | Proof supports line height |
| Columns (1–6) | Proof supports columns |
| Tracking (-20–100 pt) | Proof supports formatting |
| Paragraphs (1–20) | Proof has paragraphs |
| Alignment (L/C/R/J) | Proof supports formatting |
| Character categories (5 checkboxes) | Proof has categories |
| Custom text editor + markup toggle | Proof has custom text |
| Default font picker | Custom text "Generate Once" mode |
| Multi-style font list | Multi-style proofs |
| OpenType features (2-col grid) | Always (populated from first font) |

Custom text editor uses `NSViewRepresentable` wrapping `NSTextView` with smart quotes/dashes disabled.

### PDF Viewer (`PDFViewerView.swift`)

Two-pane NSSplitView:
- **Thumbnail sidebar** — Page thumbnails with section headers (e.g. "Filtered Character Set", "Basic Paragraph Large"). Clicking a thumbnail scrolls the main viewer.
- **Main viewer** — PDFKit `PDFView` in single-page-continuous mode with auto-scaling.

### Font Style Selection (`FontStyleSelectionViews.swift`)

Two specialized components:
- **DefaultFontPicker** — Hierarchical family→style picker for Custom Text "Generate Once" mode
- **MultiStyleFontList** — Family-grouped toggles for selecting which styles appear in multi-style comparison proofs

### Shared Components
- **`SidebarListRow.swift`** — Reusable row with drag handle, toggle, name (double-click rename), badge, delete
- **`HoverComponents.swift`** — `HoverButton`, `HoverIconButton`, `HoverValueLabel` with hover color changes

### ProofEngine (`ProofEngine.swift`)

The **sole Python bridge**. `@MainActor ObservableObject`.

**Bootstrap:** Calls `PythonSetup.initialize()` which sets `PYTHON_LIBRARY`, `PYTHONHOME`, adds bundled packages to `sys.path`. Then imports `engine`, `config`, `fonts` modules.

**Published state:** `isReady`, `isGenerating`, `lastPDFPath`, `errorMessage`.

**Bridge methods:**

| Swift method | Python call | Returns |
|---|---|---|
| `generateProof(config:)` | `engine.generate_proof(dict)` | PDF path + section list |
| `getFontMetadata(paths:)` | `engine.get_font_metadata(paths)` | `[FontInfo]` |
| `getAvailableOTFeatures(path:)` | `engine.get_available_ot_features(path)` | `[String]` |
| `getProofRegistry()` | `engine.get_proof_registry()` | `[ProofRegistryEntry]` |
| `getPageFormats()` | `engine.get_page_formats()` | `[String]` |
| `getFontStyles(paths:)` | `engine.get_font_styles(paths)` | `[FontStyleEntry]` |

### AppState (`AppState.swift`)

Central `@MainActor ObservableObject` (~40 published properties):

**Font state:** `fontPaths`, `loadedFonts` (`[FontInfo]`), `axisValuesByFont`, `disabledFontPaths`, `fontSortCriteria`, `fontStyles`.

**Proof state:** `proofOptions` (`[ProofOption]`), `selectedProof`, `proofSettingsByProof` (`[String: ProofSettings]`).

**Page/output:** `pageFormat`, `showBaselines`, `outputDirectory`, `currentPDFPath`, `proofSections`.

**Persistence:** Auto-saves to `~/.type-proofing-swiftui-prefs.json` with a 3-second debounce timer. Loads on startup, encodes via `Codable` `PersistedState`.

**Key method: `buildProofConfig()`** — Serializes all state into a flat `ProofConfig` struct that gets converted to a Python dict for `engine.generate_proof()`.

### Swift Data Models

```swift
struct FontInfo       // id, name, isVariable, axes, supportsArabic, familyName, weight, width, slant, opticalSize
struct FontAxis       // id(tag), name, min, max, default, current, instanceValues
struct ProofOption    // id, name, baseType, enabled, order
struct ProofSettings  // fontSize, tracking, lineHeight, columns, paragraphs, alignment, customText, markupEnabled,
                      // generateOnce, categories, otFeatures, defaultFontPath, enabledStyleIndices, autoSize
struct ProofRegistryEntry  // key, displayName, isArabic, hasSettings, defaultColumns, hasParagraphs, defaultFontSize,
                           // hasCustomText, hasCategories, isMultiStyle + computed: supportsFormatting, supportsCols, etc.
struct FontStyleEntry // index, fontPath, familyName, styleName, isVariable, coordinates
```

---

## Python Layer (Engine)

### engine.py — Headless Entry Point

The main function called from Swift. No UI imports, no Vanilla/AppKit dependencies (except DrawBot and pdf_manager).

**`generate_proof(config: dict) → dict`**

Receives a flat config dict from Swift, runs the full proof generation pipeline, returns `{"pdf_path": str, "sections": [...]}`.

Steps:
1. Extract font paths, axis values, proof options, proof settings, page format from config
2. Create `Settings`, `FontManager`, `ProofSettingsManager` instances
3. Begin DrawBot PDF document
4. For each enabled proof option:
   - Get the proof handler via `get_proof_handler()`
   - For each font: build `ProofContext`, call `handler.generate_proof(context)`
5. End DrawBot document, save PDF
6. Return path + section metadata

**Font sorting:** `_extract_sort_properties()` creates composite sort keys from OS/2 table values (weight class, width class, fsSelection) with name-based keyword tiebreakers. Supports weight (17 keywords), width (16 keywords), slant, and optical size extraction.

**Other exports:** `get_font_metadata()`, `get_available_ot_features()`, `get_proof_registry()`, `get_page_formats()`, `get_font_styles()`, `get_default_proof_order()`.

### config.py — Central Configuration

**No internal dependencies.** The foundation module everything else imports.

**Core contents:**

- **App constants:** `APP_VERSION` (1.7.0), `SETTINGS_PATH`, `FALLBACK_FONT` (AdobeBlank.otf), `WORDSIV_SEED`
- **Page formats:** `PAGE_FORMAT_OPTIONS` (12 formats: A4, Letter, A3, A5, Legal, iPhone sizes), `PAGE_DIMENSIONS` dict
- **Layout constants:** `MARGIN_VERTICAL` (50pt), `MARGIN_HORIZONTAL` (40pt), footer font settings
- **OpenType feature sets:** `DEFAULT_ON_FEATURES` (15 features), `HIDDEN_FEATURES` (10 features hidden from UI)
- **Arabic/Farsi templates:** Character templates, positional forms (`init`, `medi`, `fina`), join types
- **`PROOF_REGISTRY`** — The central data structure. See [The Proof Registry](#the-proof-registry).

**Key helper functions:**
- `get_proof_display_names(include_arabic)` — Ordered list of visible proof names
- `resolve_base_proof_key(proof_name)` — Map user-visible name to (display_name, key)
- `proof_has_custom_text()`, `proof_has_categories()`, `proof_is_multi_style()`, `proof_supports_formatting()` — Registry queries
- `setup_page_format(page_format)` — Configures DrawBot page dimensions
- `filter_visible_features(feature_tags)` — Strips hidden OT features for UI display
- `resolve_character_set_by_key(cat, key)` — Maps a `character_set_key` to the actual character string from the categorized charset

### fonts.py — Font Analysis

**Depends on:** config, settings, fontTools, drawBot

**`FontManager` class:**
- `add_fonts(paths)`, `remove_fonts_by_indices(indices)`, `load_fonts(font_paths)`
- `update_font_info()` — Refreshes font info, merges user axis values
- `get_table_data()`, `get_all_axes()` — For UI display
- `has_arabic_support()` — Checks if any loaded font has Arabic characters
- `get_axis_values_for_font(font_path)` — Returns axis values dict

**Font analysis functions:**
- `filteredCharset(font)` — Gets charset excluding glyphs without outlines. Prefers cmap-based collection, falls back to AGL name mapping
- `get_font_info(font_path)` — Returns dict with OT features, VF axes, named instances
- `variableFont(font)` — Returns axes info + cartesian product of all axis value combinations
- `pairStaticStyles(fonts)` — Matches regular/italic and regular/bold pairs by weight using OS/2 table
- `categorize(charset)` — Groups characters by Unicode category (uppercase_base, lowercase_base, numbers_symbols, punctuation, accented, arabic_base, arabic_marks, farsi_extra)
- `get_charset_proof_categories(cat)` — Organizes categorized chars into proof-ready groups
- `check_arabic_support(charset)` — Detects Arabic support by checking for Arabic template characters

**Caching:** `_ttfont_cache` stores `TTFont` instances by path; `clear_font_cache()` to reset.

### proof.py — Proof Generation

**Depends on:** config, fonts, settings, text_generators, markup_parser, drawBot, wordsiv, drawBotGrid

This is the largest and most complex module. Contains drawing functions, text generation, and the handler class hierarchy.

**Core drawing functions:**
- `drawContent(textToDraw, pageTitle, columnNumber, ...)` — Renders text to DrawBot with column layout
- `drawPageSegments(page_segments, ...)` — Renders markup output supporting multi-page, multi-column layout
- `drawFooter(title, indFont, otFeatures, tracking, pageNumber)` — Date/time, font name, features, page number
- `stringMaker(textInput, fontSize, indFont, ...)` — Creates `FormattedString` with optional mixed styles
- `_render_proof_content(...)` — Unified helper that iterates over VF axis combinations, renders content, draws pages

**Text generation functions:**
- `generateTextProofString(characterSet, para, casing, ...)` — Main text generator dispatcher. Routes to wordsiv, Hoefler-style, uppercase-only, lowercase-only, or Arabic generators
- `_generate_hoefler_style_text(...)` — Creates proofs showing contextual words per letter (loads from eng_wiki.tsv)
- `_generate_arabic_farsi_text(...)` — Creates Arabic/Farsi text with positional forms
- `generateSpacingString(characterSet)` — Creates HHxHH patterns for evaluating letter spacing

**Auto-sizing:**
- `_calc_auto_size_for_page(text, font_path, ...)` — Binary search for largest font size that fits content within page margins
- `_calc_auto_size_for_line(text, font_path, ...)` — Binary search for largest font size fitting a single line

### settings.py — Settings & Utilities

**Depends on:** config

**Utility functions (used everywhere):**
- `normalize_path(path)` — Handles NSURL, file:// URLs, regular paths
- `safe_json_load/save()` — Atomic JSON persistence (temp file + fsync + rename)
- `log_error(error, context)` — Timestamped error logging
- `safe_execute(name, func, ...)` — Try/except wrapper
- `validate_setting_value(key, value)` — Type-based validation and coercion
- `make_settings_key(base_key, setting_type, category?)` — Constructs consistent keys like `"proof_key_fontSize"`, `"proof_key_cat_uppercase"`
- `make_feature_key(base_key, feature_tag)` — Constructs keys like `"otf_proof_key_kern"`

**`Settings` class:**
- Loads from `~/.type-proofing-prefs.json` (or auto-save path)
- Nested dict access using dot notation: `settings.get("fonts.paths")`
- Merge strategy: user data overrides defaults, missing keys filled from defaults
- Font validation on load (checks files still exist)
- Import/export to arbitrary files

**`ProofSettingsManager` class:**
- Manages per-proof-type settings (font size, columns, paragraphs, tracking, alignment, OT features, categories)
- `initialize_proof_settings()` — Sets defaults for all proof types based on registry
- `build_proof_data_for_generation(proof_options_items)` — Builds dicts keyed by proof type containing columns, paragraphs, and OT features for the generation pipeline
- `get_popover_settings_for_proof(proof_key)` — Returns current settings for UI display
- `update_feature_setting(key, enabled, readonly)` — Updates individual OT feature toggle

### markup_parser.py — Custom Text Styling

**Depends on:** config, fonts, drawBot

Lightweight markdown-like parser for the Custom Text proof type.

**Supported syntax:**
```
# Heading 1              → 2.5× base font size
## Heading 2             → 1.8× base font size
**bold**                 → Resolves VF wght:700 or static bold variant
*italic*                 → Resolves VF ital:1/slnt or static italic variant
***bold italic***        → Both combined
[text]{wght:700, size:24, color:#FF0000, feat:smcp, style:"Bold"}
#pagebreak()             → Force new page
#colbreak()              → Force new column
```

**Processing pipeline:**
1. `_escape(text)` — Replaces `\*`, `\#`, `\[`, etc. with Unicode private-use chars
2. `_tokenize(raw_text)` — Splits into `Token` objects (heading, bold, italic, bold_italic, attr_span, plain, page_break, column_break)
3. `_build_formatted_string(tokens, ...)` — Converts tokens to DrawBot `FormattedString` list (one per page)
4. `_restore(text)` — Restores escaped characters in final output

**Font resolution:** `_resolve_bold_font()`, `_resolve_italic_font()`, `_resolve_bold_italic_font()` — Try VF axis manipulation first (wght:700, ital:1, slnt:-12), fall back to file-name matching for static fonts.

### pdf_manager.py — PDF Operations

**Depends on:** settings, config, proof, AppKit, Quartz.PDFKit

`PDFManager` class handles:
- PDF preview via `PDFView` + `PDFThumbnailView` (AppKit hierarchy)
- `begin_pdf_generation()` / `end_pdf_generation()` — DrawBot document lifecycle
- `save_pdf_document(font_manager, now)` — Save to output directory with timestamped filename
- `display_pdf(pdf_path)` — Load into preview
- `export_pdf_pages(output_dir, page_range, pdf_path)` — Extract individual pages

### text_generators.py — Text Data Wrapper

Provides a `TextGenerator` class that wraps access to `sample_texts`, `script_texts`, and `accented_dictionary`. Methods: `get_text_sample()`, `get_script_text()`, `generate_accented_text()`. A global `text_generator` singleton is available module-wide.

---

## Data Flow: From Button Click to PDF

```
User clicks "Generate"
        │
        ▼
SidebarView.generateProof()
        │
        ▼
AppState.buildProofConfig()
  ├─ Collect enabledFontPaths + axisValuesByFont
  ├─ Serialize proofOptions (name, baseType, enabled)
  ├─ Flatten proofSettingsByProof → flat dict keys:
  │     "{proofType}_fontSize", "{proofType}_cols",
  │     "otf_{proofType}_{tag}", "{proofType}_cat_{category}", ...
  ├─ Page format, baselines flag, output directory
  └─ Return ProofConfig
        │
        ▼
ProofEngine.generateProof(config:)
  ├─ config.toPythonDict()  →  Python dict
  └─ engine.generate_proof(pyDict)
        │
        ▼
engine.py: generate_proof(config)
  ├─ Create Settings, FontManager, ProofSettingsManager
  ├─ Sort fonts by composite key (weight, width, slant, opsz)
  ├─ FontManager.update_font_info()
  ├─ ProofSettingsManager.initialize_proof_settings()
  ├─ ProofSettingsManager.build_proof_data_for_generation()
  ├─ setup_page_format()
  ├─ db.newDrawing()
  │
  ├─ For each enabled proof option:
  │   ├─ get_proof_handler(proof_type, proof_name, proof_settings, ...)
  │   │     → Creates/caches handler from PROOF_HANDLER_REGISTRY
  │   │
  │   ├─ For each font in sorted fonts:
  │   │   ├─ Get charset → filteredCharset(font)
  │   │   ├─ Get axes product → variableFont(font)
  │   │   ├─ Categorize chars → categorize(charset)
  │   │   ├─ Pair styles if needed → pairStaticStyles(fonts)
  │   │   ├─ Build ProofContext dataclass
  │   │   └─ handler.generate_proof(context)
  │   │         │
  │   │         ▼
  │   │     (Handler-specific logic — see Proof Handler System)
  │   │         │
  │   │         ▼
  │   │     drawContent() or drawPageSegments()
  │   │         ├─ stringMaker() → FormattedString
  │   │         ├─ drawBot column layout
  │   │         └─ drawFooter()
  │   │
  │   └─ Record section metadata (name + first page index)
  │
  ├─ db.saveImage(pdf_path)
  ├─ db.endDrawing()
  └─ Return {"pdf_path": ..., "sections": [...]}
        │
        ▼
Back in Swift:
  ├─ AppState.currentPDFPath = path
  ├─ AppState.proofSections = sections
  └─ PDFViewerView loads PDF, builds thumbnail sidebar with section headers
```

---

## The Proof Registry

`PROOF_REGISTRY` in `config.py` is the **single source of truth** for all proof types. Every proof type is defined here with its capabilities and defaults.

```python
PROOF_REGISTRY = {
    "filtered_character_set": {
        "display_name": "Filtered Character Set",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 1,
        "default_size": 48,
        "has_categories": True,
        "text": {
            "character_set_key": "uppercase_base",
            ...
        }
    },
    "basic_paragraph_large": {
        "display_name": "Basic Paragraph Large",
        "default_cols": 1,
        "default_size": 24,
        "has_paragraphs": True,
        "text": {
            "default_paragraphs": 5,
            ...
        }
    },
    # ... 24 total proof types
}
```

**Registry flags control both Python behavior and Swift UI:**

| Flag | Python effect | Swift UI effect |
|------|--------------|----------------|
| `has_settings` | Handler reads per-proof settings | Settings panel shown |
| `has_categories` | Categories filter charset | Category checkboxes shown |
| `has_paragraphs` | Paragraph count used | Paragraph stepper shown |
| `has_custom_text` | Custom text editor input | Custom text section shown |
| `multi_style` | Multi-style comparison logic | Font style list shown |
| `is_arabic` | Arabic text generators used | Proof hidden if no Arabic fonts |
| `default_cols/size` | Fallback defaults | Initial control values |

**Proof types (24 total):**

| Key | Type | Description |
|-----|------|-------------|
| `filtered_character_set` | Category-based | Full charset organized by Unicode category |
| `spacing_proof` | Category-based | HHxHH patterns for evaluating spacing |
| `basic_paragraph_large` | Text | Large paragraphs (wordsiv or sample text) |
| `basic_paragraph_small` | Text | Small paragraphs |
| `diacritic_words_large` | Text | Words with diacritics, large |
| `diacritic_words_small` | Text | Words with diacritics, small |
| `paired_styles_paragraph_small` | Text | Alternating regular/italic or regular/bold |
| `generative_text_small` | Text | Pseudo-random wordsiv text |
| `misc_paragraph_small` | Text | Numbers, punctuation, symbols in paragraphs |
| `custom_text` | Custom | User-entered text with optional markup |
| `multi_style_comparison` | Multi-style | One line per font style, same text |
| `ar_character_set` | Arabic | Arabic contextual forms (init/medi/fina/isol) |
| `ar_paragraph_large` | Arabic text | Arabic paragraphs, large |
| `ar_paragraph_small` | Arabic text | Arabic paragraphs, small |
| `fa_paragraph_large` | Arabic text | Persian paragraphs, large |
| `fa_paragraph_small` | Arabic text | Persian paragraphs, small |
| `ar_vocalization_paragraph_small` | Arabic text | Arabic with vocalization marks |
| `ar_lat_mixed_paragraph_small` | Arabic text | Arabic-Latin mixed text |
| `ar_numbers_small` | Arabic text | Number proofs |

---

## Proof Handler System

Proof generation uses an abstract handler hierarchy with a registry-based factory.

```
BaseProofHandler (ABC)
  ├─ StandardTextProofHandler        ← Most text-based proofs (default)
  ├─ CustomTextProofHandler          ← Custom Text proof
  ├─ ArCharacterSetHandler           ← Arabic character set
  └─ CategoryBasedProofHandler
        ├─ FilteredCharacterSetHandler  ← Filtered Character Set
        ├─ SpacingProofHandler          ← Spacing Proof
        └─ MultiStyleComparisonProofHandler ← Multi-Style Comparison
```

### BaseProofHandler

Caches common settings on construction: `font_size`, `tracking`, `align`, `line_height`, `columns`, `paragraphs`, `otfeatures`. Provides template method `generate_text_proof()` that calls `textProof()` with standard parameters.

### StandardTextProofHandler

Handles the majority of proofs (basic paragraph, diacritics, paired styles, generative text, misc, Arabic/Farsi text proofs). Reads proof-specific config from the registry (`text.default_paragraphs`, `text.hoefler_style`, `text.casing`, etc.) and delegates to `textProof()`.

### CategoryBasedProofHandler

Base for proofs that iterate over character categories (uppercase, lowercase, numbers/symbols, punctuation, accented). Reads category enable flags from settings, filters charset accordingly.

### CustomTextProofHandler

Supports plain text or markup mode. Has a `generate_once` flag — when enabled, generates the custom text proof only for a single font (the user-selected default font), not for every loaded font. Uses `markup_parser._build_formatted_string()` when markup is enabled.

### MultiStyleComparisonProofHandler

Generates one line per loaded font style for selected categories. Uses class-level `_generated_instances` set for deduplication within a single PDF generation run — ensures each instance combination is only rendered once even when called for multiple fonts.

### Factory

```python
PROOF_HANDLER_REGISTRY = {
    "Filtered Character Set": FilteredCharacterSetHandler,
    "Spacing Proof": SpacingProofHandler,
    "ARA Character Set": ArCharacterSetHandler,
    "Custom Text": CustomTextProofHandler,
    "Multi-Style Comparison": MultiStyleComparisonProofHandler,
}
# All other proof display names → StandardTextProofHandler

get_proof_handler(proof_type, proof_name, proof_settings, get_proof_font_size_func)
# → Returns cached handler instance
```

---

## Settings System

### Two Settings Files

| File | Purpose | Format |
|------|---------|--------|
| `~/.type-proofing-swiftui-prefs.json` | SwiftUI app auto-save | JSON (`PersistedState`) |
| `~/.type-proofing-prefs.json` | Python-side settings (legacy + engine use) | JSON (flat structure) |

### Settings Key Convention

Settings keys follow a consistent pattern:

```
{proof_key}_fontSize          → Font size for proof
{proof_key}_cols              → Column count
{proof_key}_para              → Paragraph count
{proof_key}_tracking          → Tracking value
{proof_key}_align             → Alignment string
{proof_key}_lineHeight        → Line height ratio
{proof_key}_cat_{category}    → Category enable flag
{proof_key}_customText        → Custom text content
{proof_key}_markupEnabled     → Markup mode flag
{proof_key}_generateOnce      → Generate-once flag
otf_{proof_key}_{feature}     → OT feature toggle
```

Built by `make_settings_key(base_key, setting_type, category?)` and `make_feature_key(base_key, feature_tag)`.

### Settings Flow (Swift → Python)

1. Swift `AppState.proofSettingsByProof` stores typed `ProofSettings` structs per proof
2. `buildFlatProofSettings()` flattens these into a `[String: PythonObject]` dict using the key convention above
3. Python `engine.generate_proof()` passes the flat dict to `ProofSettingsManager`
4. `ProofSettingsManager` reads keys using `make_settings_key()` / `make_feature_key()` and populates handler settings

### Atomic Persistence

`safe_json_save()` writes to a temp file, calls `fsync`, then atomically renames — preventing corruption on crash.

---

## Font Management

### Loading and Analysis

1. User drops font files or clicks "Add Fonts"
2. Swift calls `engine.get_font_metadata(paths)` → Python `fonts.get_font_info()` for each file
3. Returns: family name, OT features, VF axes (min/max/default/named instances), Arabic support flag
4. Swift populates `FontInfo` models, displays in sidebar with axis controls

### Variable Font Handling

- `variableFont(font)` returns axes info + cartesian product of all axis value combinations
- User adjusts axis values via multi-handle sliders (each handle = one instance to generate)
- The product of all axis values determines how many pages are generated per proof type
- Example: 3 weight values × 2 width values = 6 instance combinations per proof

### Character Set Analysis

`filteredCharset()` builds the font's effective character set:
1. Reads cmap tables, prefers format 4/12 for complete Unicode coverage
2. Filters out glyphs without outlines (checks glyf/CFF tables)
3. Falls back to AGL (Adobe Glyph List) name-to-Unicode mapping if cmap is sparse

`categorize()` then groups characters:
- `uppercase_base`, `lowercase_base` — Latin letters without diacritics
- `numbers_symbols` — digits + currency + math symbols
- `punctuation` — all punctuation categories
- `accented` — characters with combining marks (detected via Unicode decomposition)
- `arabic_base`, `arabic_marks`, `farsi_extra` — script-specific groups

### Font Pairing

`pairStaticStyles(fonts)` matches fonts for alternating-style proofs:
- Uses OS/2 `fsSelection` bits to identify Regular, Bold, Italic
- Groups by weight class, pairs upright with italic at same weight
- Returns paired font lists for `_handle_mixed_styles()`

### Font Sorting (engine.py)

`_extract_sort_properties()` creates composite sort keys:
- Primary: OS/2 `usWeightClass` → ordinal (100→1, 200→2, ..., 950→10)
- Secondary: OS/2 `usWidthClass` → ordinal (1→1, ..., 9→9)
- Fallback: Name-based keyword matching against 17 weight keywords, 16 width keywords
- Additional: Slant (from `fsSelection` italic bit or slnt axis), optical size
- Sort key: `(family_name, weight_composite, width_composite, slant, optical_size)`

---

## Text Generation

### Sources

| Source | Used for |
|--------|----------|
| **wordsiv** (WordSiv library) | Primary text generator — produces pseudo-random words from vocabulary, seeded for reproducibility |
| **sample_texts.py** | Pre-made paragraphs (mixed case, lowercase, uppercase, numbers, punctuation) |
| **script_texts.py** | Arabic vocalization, Arabic-Latin mixed, Arabic/Farsi/Urdu numbers |
| **accented_dictionary.py** | Words containing specific accented characters |
| **eng_wiki.tsv** | Word frequency data for Hoefler-style proofs |

### Text Generation Strategy

`generateTextProofString()` dispatches based on font capabilities:
1. **Font has upper + lowercase** → WordSiv mixed-case text, or sample text fallback
2. **Font is uppercase-only** → Uppercase sample text + accented uppercase words
3. **Font is lowercase-only** → Lowercase sample text + accented lowercase words
4. **Arabic/Farsi font** → Script-specific text with positional forms

**Hoefler-style proofs:** For each letter in the charset, finds real English words from `eng_wiki.tsv` that contain that letter in various positions (initial, medial, final), grouped by letter shape (round-left, flat-left, round-right, flat-right). This creates contextually rich proofs showing how each letter behaves next to different letter shapes.

**WordSiv text:** Uses seeded randomization (`WORDSIV_SEED = 987654`) for reproducible output. Generates words that only use characters present in the font's charset, with recent-word tracking to avoid repetition.

---

## Markup Parser

The markup parser (`markup_parser.py`) enables rich text formatting in Custom Text proofs. It converts a markdown-like syntax into DrawBot `FormattedString` objects.

### Processing Pipeline

```
Raw text → _escape() → _tokenize() → _build_formatted_string() → _restore()
                                              │
                                    [FormattedString per page]
```

### Token Types

| Token | Syntax | Effect |
|-------|--------|--------|
| `heading1` | `# Title` | min(base_size × 2.5, 90) |
| `heading2` | `## Title` | min(base_size × 1.8, 90) |
| `bold` | `**text**` | Resolves weight:700 or static bold |
| `italic` | `*text*` | Resolves ital:1/slnt or static italic |
| `bold_italic` | `***text***` | Both combined |
| `attr_span` | `[text]{attrs}` | Inline attribute overrides |
| `page_break` | `#pagebreak()` | New page |
| `column_break` | `#colbreak()` | New column |

### Attribute Syntax

```
[text]{wght:700, size:24, color:#FF0000, feat:"smcp,onum", tracking:10, style:"Bold Italic"}
```

- `wght`, `wdth`, `opsz`, `ital`, `slnt` → Variable font axis overrides
- `style` → Resolves font by subfamily name from loaded fonts
- `feat` → OpenType feature overrides
- `size` → Font size override
- `color` → Fill color (hex)
- `tracking` → Tracking override

### Font Resolution

Bold/italic resolution tries three strategies:
1. **Variable font axis:** Set wght:700, ital:1, or slnt:-12
2. **Named instances:** Find matching instance in the same font
3. **Static font matching:** Search loaded fonts for matching subfamily name

---

## PDF Management

`pdf_manager.py` handles the AppKit-level PDF operations:

- **Preview:** `PDFView` (auto-scaling, continuous scroll) + `PDFThumbnailView` (sidebar minimap)
- **Save:** Timestamped filename (`YYYY-MM-DD_HHMM_{family_name}.pdf`), output to font directory or custom location
- **Document lifecycle:** `begin_pdf_generation()` → proof handlers draw pages → `end_pdf_generation()`

The PDF viewer in Swift (`PDFViewerView.swift`) reimplements the preview using PDFKit directly, with custom section headers in the thumbnail sidebar.

---

## Module Dependency Graph

```
config.py                    ← No internal dependencies
    │
    ├──→ fonts.py            ← Depends on config, settings
    ├──→ settings.py         ← Depends on config
    ├──→ markup_parser.py    ← Depends on config, fonts
    │
    └──→ proof.py            ← Depends on config, fonts, settings,
         │                      markup_parser, text_generators,
         │                      wordsiv, drawBotGrid
         │
         └──→ engine.py      ← Depends on config, fonts, settings, proof
              │
              └──→ pdf_manager.py  ← Depends on settings, config, proof
```

External dependencies: `drawBot`, `fontTools`, `wordsiv`, `drawBotGrid`, `AppKit`, `Quartz.PDFKit`, `PythonKit`.

---

## Key Constants and Defaults

| Constant | Value | Location |
|----------|-------|----------|
| `APP_VERSION` | 1.7.0 | config.py |
| `FALLBACK_FONT` | AdobeBlank.otf | config.py |
| `WORDSIV_SEED` | 987654 | config.py |
| `DUAL_STYLE_SEED` | 1029384756 | config.py |
| `MARGIN_VERTICAL` | 50 pt | config.py |
| `MARGIN_HORIZONTAL` | 40 pt | config.py |
| `DEFAULT_PAGE_FORMAT` | A4Landscape | config.py |
| `DEFAULT_CHARSET_TRACKING` | 24 | config.py |
| Settings auto-save path | `~/.type-proofing-prefs.json` | config.py |
| SwiftUI settings path | `~/.type-proofing-swiftui-prefs.json` | AppState.swift |
| Bundle ID | `com.dograytype.typeproofing` | project.yml |
| Deployment target | macOS 13.0+ | project.yml |
| Python version | 3.13 | PythonSetup.swift |

---

## Conventions and Patterns

### Naming
- **Python files:** snake_case (`proof_config.py`)
- **Python classes:** PascalCase (`ProofSettingsManager`)
- **Python functions:** snake_case, private prefixed with `_` (`_extract_sort_properties`)
- **Swift files:** PascalCase (`ProofEngine.swift`)
- **Settings keys:** `{proof_key}_{settingType}` or `otf_{proof_key}_{tag}`

### Design Patterns
- **Registry pattern:** `PROOF_REGISTRY` (config), `PROOF_HANDLER_REGISTRY` (proof) — centralized definitions queried by all layers
- **Factory with caching:** `get_proof_handler()` creates and caches handler instances
- **Abstract base class + template method:** `BaseProofHandler.generate_text_proof()` provides the template, subclasses override `generate_proof()`
- **Context object:** `ProofContext` dataclass carries all per-font data to handlers
- **Atomic file writes:** temp + fsync + rename for settings persistence
- **Bridge pattern:** `ProofEngine` is the sole Swift↔Python interface
- **Environment objects:** `ProofEngine` and `AppState` injected via SwiftUI environment
- **Debounced persistence:** 3-second timer in AppState for auto-save

### Error Handling
- Python: `log_error(error, context)` for logging, `safe_execute(name, func)` for wrapped calls
- Swift: `ProofEngine.errorMessage` published for UI display
- Font loading: graceful degradation — invalid fonts skipped with warning
- Missing characters: `AdobeBlank.otf` used as fallback (renders empty space, preserving layout)

### Threading
- All PythonKit calls run on `@MainActor` (required for GIL safety)
- `Task.yield()` before Python calls to let SwiftUI redraw (show spinner)
- No background Python threads — would cause SIGSEGV in `_PyObject_Malloc`
