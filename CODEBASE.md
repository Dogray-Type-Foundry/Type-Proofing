# Type Proofing — Codebase Reference

> This document is designed to give an LLM (or a new contributor) all the information needed to understand, navigate, and modify the codebase.

## Architecture Overview

The application is a macOS font proofing tool built with Python. It uses **drawBot** for PDF rendering, **Vanilla** for the UI, **fontTools** for font analysis, and **wordsiv** for text generation.

### Data Flow

```
User interaction (UI)
  → ControlsTab / FilesTab (ui.py)
    → ProofWindow controller (app.py)
      → ProofSettingsManager (settings.py) for config
      → FontManager (fonts.py) for font data
      → run_proof() loops over fonts
        → get_proof_handler() factory (proof.py)
          → handler.generate_proof(ProofContext)
            → drawBot API (pages, formatted strings, PDF output)
      → PDFManager (pdf_manager.py) finalises and saves PDF
```

### Module Map

| File | Role |
|---|---|
| `TypeProofing.py` | Entry point — launches `ProofWindow` |
| `config.py` | Constants, `PROOF_REGISTRY`, helper functions |
| `app.py` | `ProofWindow` class — main controller, popover, proof generation loop |
| `ui.py` | `FilesTab`, `ControlsTab`, `StepperList2Cell`, `TextGenerator` |
| `proof.py` | `ProofContext`, handler classes, drawing functions, text generators |
| `fonts.py` | `FontManager`, character categorisation, variable font utilities |
| `settings.py` | `Settings`, `ProofSettingsManager`, key construction, validation |
| `pdf_manager.py` | `PDFManager` — begin/end PDF, save, preview |
| `sample_texts.py` | Pre-made paragraph texts (big/small, upper/lower/mixed) |
| `script_texts.py` | Arabic, Persian, Urdu sample texts |
| `accented_dictionary.py` | Word lists for accented-character proofs |

---

## config.py — Configuration & Proof Registry

### Core Constants

| Constant | Value / Purpose |
|---|---|
| `SCRIPT_DIR` | Application root (respects py2app frozen state) |
| `SETTINGS_PATH` | `~/.type-proofing-prefs.json` |
| `APP_VERSION` | e.g. `"1.6.3"` |
| `FALLBACK_FONT` | `AdobeBlank.otf` path |
| `MARGIN_VERTICAL` / `MARGIN_HORIZONTAL` | 50 / 40 points |
| `PAGE_FORMAT_OPTIONS` | List of 7 format strings (A3Landscape, A4Landscape, …) |
| `PAGE_DIMENSIONS` | `{format: (width, height)}` |
| `DEFAULT_PAGE_FORMAT` | `"A4Landscape"` |
| `WINDOW_SIZE` | `(1000, 700)` |
| `POPOVER_PROOF_SETTINGS_SIZE` | `(400, 780)` |
| `DEFAULT_CHARSET_TRACKING` | 24 |
| `DEFAULT_ON_FEATURES` | Set of 11 OT features enabled by default |
| `HIDDEN_FEATURES` | 10 features hidden from the UI |

### PROOF_REGISTRY

Central dict defining every proof type. Structure:

```python
PROOF_REGISTRY = {
    "proof_key": {
        "display_name": "Human Name",
        "is_arabic": False,
        "has_settings": True,
        "default_cols": 2,
        "has_paragraphs": False,
        "default_size": 16,
        # Optional fields:
        "text": { ... },           # Config for StandardTextProofHandler
        "has_custom_text": True,    # Shows custom text editor in popover
        "has_categories": True,     # Shows character category checkboxes
        "multi_style": True,        # Multi-style comparison mode
    },
    ...
}
```

**All proof keys (in display order):**
`filtered_character_set`, `spacing_proof`, `basic_paragraph_large`, `diacritic_words_large`, `basic_paragraph_small`, `paired_styles_paragraph_small`, `generative_text_small`, `diacritic_words_small`, `misc_paragraph_small`, `custom_text`, `multi_style_comparison`, `ar_character_set`, `ar_paragraph_large`, `fa_paragraph_large`, `ar_paragraph_small`, `fa_paragraph_small`, `ar_vocalization_paragraph_small`, `ar_lat_mixed_paragraph_small`, `ar_numbers_small`

### Key Helper Functions

```python
get_proof_display_names(include_arabic=True) -> list[str]
get_proof_settings_mapping() -> {display_name: proof_key}
get_proof_default_font_size(proof_key) -> int
get_proof_default_columns() -> {proof_key_cols: default}
get_proof_paragraph_settings() -> {proof_key_para: 3}
get_text_proof_config(proof_key) -> dict | None
resolve_character_set_by_key(cat, key) -> str
proof_supports_formatting(proof_key) -> bool
proof_has_custom_text(proof_key) -> bool
proof_has_categories(proof_key) -> bool
proof_is_multi_style(proof_key) -> bool
get_default_alignment_for_proof(proof_key) -> str
resolve_base_proof_key(proof_name) -> (display_name, base_key)
get_otf_prefix(proof_key) -> str
```

---

## settings.py — Settings Management

### Key Construction

```python
make_settings_key(base_key, setting_type, category=None) -> str
# e.g. make_settings_key("filtered_character_set", "fontSize") -> "filtered_character_set_fontSize"
# e.g. make_settings_key("filtered_character_set", "cat", "uppercase_base") -> "filtered_character_set_cat_uppercase_base"

make_feature_key(base_key, feature_tag) -> str
# e.g. "otf_filtered_character_set_kern"

create_unique_proof_key(proof_name) -> str
# "Basic Paragraph Large 2" -> "basic_paragraph_large_2"
```

### Settings Class

Handles JSON persistence at `~/.type-proofing-prefs.json`.

**Default structure:**
```python
{
    "version": APP_VERSION,
    "fonts": {"paths": [], "axis_values": {}},
    "proof_options": {"show_baselines": False, ...one key per proof...},
    "proof_settings": {},           # All per-proof setting values
    "proof_order": [...],           # Display name order
    "pdf_output": {"use_custom_location": False, "custom_location": ""},
    "page_format": DEFAULT_PAGE_FORMAT,
    "user_settings_file": None      # Optional pointer to external settings file
}
```

**Key methods:** `load()`, `save()`, `get(key, default)`, `set(key, value)`, `reset_to_defaults()`, `export_to_file(path)`, `load_from_file(path)`, `get_proof_settings()`, `set_proof_settings(dict)`, `get_proof_order()`, `set_proof_order(list)`, `get_font_axis_values(font_path)`, `set_font_axis_values(font_path, dict)`.

### ProofSettingsManager

Manages per-proof settings (font size, columns, paragraphs, tracking, alignment, OT features, categories, custom text).

**Important constants:**
```python
_CATEGORY_DEFAULTS = {
    "uppercase_base": True, "lowercase_base": True,
    "numbers_symbols": True, "punctuation": True, "accented": False,
}
_COLUMN_EXCLUDED_PROOFS = {
    "filtered_character_set", "spacing_proof", "ar_character_set", "multi_style_comparison"
}
```

**Key methods:**
- `initialize_proof_settings()` — populates defaults from registry
- `get_popover_settings_for_proof(proof_key)` → `[{Setting, Value, _key}, ...]`
- `get_opentype_features_for_proof(proof_key)` → `[{Feature, Enabled, _key}, ...]`
- `build_proof_data_for_generation(items)` → `(otfeatures_dict, cols_dict, paras_dict)`
- `save_all_settings(proof_options_items)` — persist to disk
- `initialize_settings_for_proof(unique_name, base_type)` — set up a new custom instance

### Validation

```python
validate_setting_value(key, value) -> (is_valid: bool, converted_value, error_msg: str)
```

---

## fonts.py — Font Management

### FontManager Class

```python
FontManager(settings=None)
```

**Properties:** `fonts` (tuple of paths), `font_info` (dict per font), `axis_values_by_font`.

**Key methods:**
- `add_fonts(paths)`, `remove_fonts_by_indices(indices)`
- `get_table_data()` / `get_table_data_with_individual_axes()` — for UI tables
- `update_axis_values_from_table(table_data, all_axes)` — sync from UI
- `has_arabic_support()` — check if any font supports Arabic
- `get_axis_values_for_font(font_path)` — stored per-font axis values
- `get_family_name()` — first font's family name

### Character Analysis

```python
filteredCharset(input_font) -> str       # Characters with outlines
categorize(charset) -> dict              # Unicode categories, script detection
get_charset_proof_categories(cat) -> dict # {uppercase_base, lowercase_base, numbers_symbols, punctuation, accented}
check_arabic_support(charset) -> bool
```

### Variable Font Utilities

```python
product_dict(**kwargs) -> Generator      # All axis value combinations
variableFont(input_font) -> (axes_product, axes_dict)
pairStaticStyles(fonts) -> (upright_italic_pairs, regular_bold_pairs)
get_all_font_axes(fonts) -> list[str]
```

---

## proof.py — Proof Handlers & Drawing

### ProofContext

Dataclass passed to every handler:

```python
@dataclass
class ProofContext:
    full_character_set: str
    axes_product: object
    ind_font: str
    paired_static_styles: object
    otfeatures_by_proof: dict    # {proof_name: {feature_tag: bool}}
    cols_by_proof: dict          # {proof_name: int}
    paras_by_proof: dict         # {proof_name: int}
    cat: dict                    # From categorize()
    proof_name: str | None
    all_fonts: list | None = None
    font_manager: object | None = None
```

### Handler Hierarchy

```
BaseProofHandler (ABC)
├── StandardTextProofHandler     — most text proofs (config-driven)
├── CategoryBasedProofHandler    — base for proofs with category checkboxes
│   ├── FilteredCharacterSetHandler
│   ├── SpacingProofHandler
│   └── MultiStyleComparisonProofHandler
├── ArCharacterSetHandler        — Arabic contextual forms
└── CustomTextProofHandler       — user-entered text
```

### BaseProofHandler

```python
class BaseProofHandler(ABC):
    def __init__(self, proof_name, proof_settings, get_proof_font_size_func)

    # Setting accessors (unique_proof_key derived from proof_name)
    get_font_size() -> int
    get_tracking_value() -> float
    get_align_value() -> str
    get_section_name(font_size) -> str
    get_common_proof_params(context, default_columns, default_paragraphs) -> dict

    @abstractmethod
    def generate_proof(self, context) -> None

    def generate_text_proof(self, context, character_set, ...) -> None
```

### Handler Registry & Factory

```python
PROOF_HANDLER_REGISTRY = {
    "Filtered Character Set": FilteredCharacterSetHandler,
    "Spacing Proof": SpacingProofHandler,
    "Ar Character Set": ArCharacterSetHandler,
    "Custom Text": CustomTextProofHandler,
    "Multi-Style Comparison": MultiStyleComparisonProofHandler,
    # All other proofs → StandardTextProofHandler (default)
}

get_proof_handler(proof_type, proof_name, proof_settings, get_font_size_func) -> BaseProofHandler | None
clear_handler_cache() -> None
```

### Core Drawing Functions

```python
drawContent(textToDraw, pageTitle, columnNumber, currentFont, direction, otFeatures, tracking) -> None
drawFooter(title, indFont, otFeatures, tracking, pageNumber) -> None
stringMaker(textInput, fontSizeInput, indFont, axesProduct, ...) -> db.FormattedString

# Specialised drawing:
charsetProof(characterSet, axesProduct, indFont, ...) -> None
spacingProof(characterSet, axesProduct, indFont, ...) -> None
textProof(characterSet, axesProduct, indFont, ...) -> None
```

### Text Generation

```python
generateTextProofString(characterSet, para, casing, bigProof, ...) -> str
generateSpacingString(characterSet) -> str
generateArabicContextualFormsProof(cat) -> str
```

`_render_proof_content()` is a shared helper that wraps `stringMaker` + `drawContent` for the common case.

---

## app.py — ProofWindow Controller

### ProofWindow Class

Main application controller. Created by `TypeProofing.py`.

**Key attributes:**
- `settings: Settings`
- `font_manager: FontManager`
- `proof_settings_manager: ProofSettingsManager`
- `pdf_manager: PDFManager`
- `proof_settings: dict` — reference to `proof_settings_manager.proof_settings`
- `current_proof_key: str` — key of the proof currently shown in the popover
- `current_base_proof_type: str` — display name of the base proof type
- `w: vanilla.Window`

### Popover System

`create_proof_settings_popover()` builds a `vanilla.Popover` with:
- Proof type dropdown (visible in general mode, hidden in instance mode)
- Numeric settings list (font size, columns, paragraphs, tracking) with steppers
- Alignment popup
- Character category checkboxes (shown for proofs with `has_categories`)
- Custom text editor (shown for proofs with `has_custom_text`)
- OpenType features list

`update_proof_settings_popover_for_instance(unique_key, base_type)` configures the popover for a specific proof instance (hides the dropdown, loads instance-specific settings).

**Callbacks:** `proofTypeSelectionCallback`, `characterCategoryCallback`, `customTextEditCallback`, `alignPopUpCallback`, `stepperChangeCallback`, `featuresEditCallback`.

### Proof Generation Loop

`run_proof()` is the core generation method:

1. Calls `MultiStyleComparisonProofHandler.reset_generated()` (dedup reset)
2. Loops over each font in `font_manager.fonts`:
   - Gets character set via `filteredCharset()`
   - Gets categories via `categorize()`
   - Gets axis product for variable fonts
   - Creates `ProofContext` with `all_fonts` and `font_manager`
   - For each enabled proof:
     - Gets handler via `get_proof_handler()`
     - Calls `handler.generate_proof(context)`
3. `PDFManager.end_pdf_generation()` saves the PDF

---

## ui.py — UI Components

### FilesTab

Font list table (drag/drop reordering, per-axis columns for variable fonts), Add/Remove buttons, PDF output location controls.

### ControlsTab

- Page format popup + Show Grid checkbox
- Proof Options List (draggable, checkboxes, gear icons for settings)
- Add/Remove Proof buttons
- Generate Proof button
- PDF Preview area

**Popover management:** `show_popover_for_option()` sets `parent_window.current_proof_key` and `current_base_proof_type`, then calls `update_proof_settings_popover_for_instance()`.

**Custom proof instances:** Users can "Add Proof" to create duplicates of any proof type with independent settings. Names like "Basic Paragraph Large 2". Keys derived via `create_unique_proof_key()`.

### StepperList2Cell

Custom `vanilla.Group` subclass used in `List2` for numeric settings with a text field + NSStepper.

---

## pdf_manager.py — PDF Output

### PDFManager

```python
PDFManager(settings)
```

**Key methods:**
- `begin_pdf_generation()` — initialise drawBot for new PDF
- `end_pdf_generation(font_manager, now)` — finalise, save to disk, return path
- `create_preview_components()` — create PDFView for in-app preview
- `setup_page_format()` — apply page dimensions from settings

---

## Extension Points

### Adding a New Proof Type

1. **config.py**: Add entry to `PROOF_REGISTRY` with all required fields. Add key to `proof_order` list in `get_proof_display_names()`.
2. **proof.py**: Create handler class extending `BaseProofHandler` (or `CategoryBasedProofHandler`). Register in `PROOF_HANDLER_REGISTRY`.
3. **settings.py**: If the proof has special settings (categories, custom text, etc.), update `_apply_settings_for_key()` to initialise defaults.
4. **app.py**: Update popover show/hide logic if the proof uses custom UI elements (categories, custom text editor). Update `run_proof()` if the proof needs special setup (e.g. deduplication).

### Settings Key Patterns

All per-proof settings use `make_settings_key(proof_key, setting_type, category?)`:
- Font size: `{proof_key}_fontSize`
- Columns: `{proof_key}_cols`
- Paragraphs: `{proof_key}_para`
- Tracking: `{proof_key}_tracking`
- Alignment: `{proof_key}_align`
- Category: `{proof_key}_cat_{category_name}`
- Custom text: `{proof_key}_customText`
- OT feature: `otf_{proof_key}_{feature_tag}`
