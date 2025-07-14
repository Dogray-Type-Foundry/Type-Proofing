# Complete reference for all settings that can be stored in settings files

SETTINGS FILE STRUCTURE:
```
{
    "version": "1.0",
    "user_settings_file": "/path/to/user/settings.json",  // Only in auto-save file
    "fonts": {
        "paths": ["/path/to/font1.otf", "/path/to/font2.ttf"],
        "axis_values": {
            "/path/to/font1.otf": {
                "wght": 400,
                "wdth": 100,
                "slnt": 0
            }
        }
    },
    "proof_options": {
        "show_baselines": true,                    // Show baseline/grid overlays
        "filtered_character_set": true,               // Generate Filtered Character Set
        "spacing_proof": true,                     // Generate spacing proof
        "basic_paragraph_large": true,               // Generate large paragraph proof
        "diacritic_words_large": false,             // Generate large diacritics proof
        "basic_paragraph_small": true,             // Generate Basic Paragraph Small
        "paired_styles_paragraph_small": false,        // Generate Paired Styles Paragraph Small
        "generative_text_small": false,              // Generate Generative Text Small
        "diacritic_words_small": false,           // Generate Diacritic Words Small
        "misc_paragraph_small": false,           // Generate Misc Paragraph Small
        "ar_character_set": false,    // Generate ARA Character Set
        "ar_paragraph_large": false,            // Generate large Arabic text proof
        "fa_paragraph_large": false,             // Generate large Farsi text proof
        "ar_paragraph_small": false,          // Generate Ar Paragraph Small
        "fa_paragraph_small": false,           // Generate Fa Paragraph Small
        "ar_vocalization_paragraph_small": false,        // Generate Ar Vocalization Paragraph Small
        "ar_lat_mixed_paragraph_small": false,         // Generate Ar-Lat Mixed Paragraph Small
        "ar_numbers_small": false              // Generate Ar Numbers Small
    },
    "proof_settings": {
        // Column settings for each proof type
        "BigParagraphProof_cols": 1,
        "BigDiacriticsProof_cols": 1,
        "SmallParagraphProof_cols": 2,
        "SmallPairedStylesProof_cols": 2,
        "SmallWordsivProof_cols": 2,
        "SmallDiacriticsProof_cols": 2,
        "SmallMixedTextProof_cols": 2,
        "ArabicContextualFormsProof_cols": 2,
        "BigArabicTextProof_cols": 1,
        "BigFarsiTextProof_cols": 1,
        "SmallArabicTextProof_cols": 2,
        "SmallFarsiTextProof_cols": 2,
        "ArabicVocalizationProof_cols": 2,
        "ArabicLatinMixedProof_cols": 2,
        "ArabicNumbersProof_cols": 2,
        
        // Paragraph settings (currently only for SmallWordsivProof)
        "SmallWordsivProof_para": 3,
        
        // OpenType feature settings per proof type
        // Format: "otf_{ProofType}_{feature_tag}": boolean
        "otf_BigParagraphProof_kern": true,
        "otf_BigParagraphProof_liga": true,
        "otf_BigParagraphProof_calt": true,
        "otf_SmallParagraphProof_kern": true,
        "otf_SmallParagraphProof_liga": false,
        // ... (many more combinations possible)
    },
    "pdf_output": {
        "use_custom_location": false,              // Whether to use custom PDF output location  
        "custom_location": ""                      // Custom directory for PDF output (empty = use font folder)
    },
    "page_format": "A4Landscape"                   // Page format for generated proofs
}
}
```

## PAGE FORMAT OPTIONS:
Available page format values for the "page_format" setting:
- A3Landscape: A3 paper in landscape orientation
- A4Landscape: A4 paper in landscape orientation (default)
- A4SmallLandscape: A4 small paper in landscape orientation
- A5Landscape: A5 paper in landscape orientation
- LegalLandscape: Legal paper in landscape orientation
- LetterLandscape: Letter paper in landscape orientation
- LetterSmallLandscape: Letter small paper in landscape orientation

The page format setting controls the paper size and orientation for generated proof PDFs.
This setting is saved automatically when changed through the GUI.

OPENTYPE FEATURE TAGS REFERENCE:
Common OpenType features that can be enabled/disabled per proof type:

Typography Features:
- kern: Kerning
- liga: Standard ligatures
- clig: Contextual ligatures
- dlig: Discretionary ligatures
- rlig: Required ligatures
- calt: Contextual alternates
- salt: Stylistic alternates
- hist: Historical forms
- titl: Titling forms
- swsh: Swash forms

Case Features:
- smcp: Small capitals
- c2sc: Capitals to small capitals
- pcap: Petite capitals
- c2pc: Capitals to petite capitals
- unic: Unicase
- cpsp: Capital spacing

Number Features:
- lnum: Lining figures
- onum: Oldstyle figures
- pnum: Proportional figures
- tnum: Tabular figures
- frac: Fractions
- afrc: Alternative fractions
- ordn: Ordinals
- sups: Superscript
- subs: Subscript
- sinf: Scientific inferiors

Position Features:
- sups: Superscript
- subs: Subscript
- ordn: Ordinals
- dnom: Denominators
- numr: Numerators

Language Features:
- locl: Localized forms
- ccmp: Glyph composition/decomposition
- mark: Mark positioning
- mkmk: Mark-to-mark positioning
- curs: Cursive positioning

Arabic/Complex Script Features:
- init: Initial forms
- medi: Medial forms
- fina: Final forms
- isol: Isolated forms
- rlig: Required ligatures
- calt: Contextual alternates
- rclt: Required contextual alternates
- curs: Cursive positioning
- kern: Kerning
- mark: Mark positioning
- mkmk: Mark-to-mark positioning

Stylistic Features:
- ss01-ss20: Stylistic sets 1-20
- cv01-cv99: Character variants 1-99
- aalt: Access all alternates

Technical Features:
- ccmp: Glyph composition/decomposition (always recommended)
- rvrn: Required variation alternates (for variable fonts)
- rclt: Required contextual alternates
- curs: Cursive positioning
- dist: Distances
- abvf: Above-base forms
- blwf: Below-base forms
- half: Half forms
- pres: Pre-base substitutions
- abvs: Above-base substitutions
- blws: Below-base substitutions
- psts: Post-base substitutions
- haln: Halant forms
- rphf: Reph forms
- pref: Pre-base forms
- rkrf: Rakar forms
- abvm: Above-base mark positioning
- blwm: Below-base mark positioning

USAGE NOTES:
1. The auto-save file (~/.type-proofing-prefs.json) only stores non-default values
2. User settings files can contain complete settings structures
3. When a user settings file is loaded, only its path is stored in the auto-save file
4. Font axis values are stored per font path
5. OpenType features are stored per proof type for maximum flexibility
6. Column and paragraph settings allow customization of proof layout
7. All boolean settings default to their defined values in proof_options
8. Font sizes are defined per proof type in the PROOF_REGISTRY and can be customized per proof instance

EXAMPLE USER SETTINGS FILE:
{
    "version": "1.0",
    "fonts": {
        "paths": ["/Users/designer/fonts/MyFont-Regular.otf"],
        "axis_values": {
            "/Users/designer/fonts/MyFont-Regular.otf": {
                "wght": 500,
                "wdth": 95
            }
        }
    },
    "proof_options": {
        "filtered_character_set": true,
        "spacing_proof": true,
        "basic_paragraph_large": true,
        "basic_paragraph_small": true,
        "ar_character_set": true
    },
    "proof_settings": {
        "BigParagraphProof_cols": 1,
        "SmallParagraphProof_cols": 2,
        "otf_BigParagraphProof_kern": true,
        "otf_BigParagraphProof_liga": true,
        "otf_BigParagraphProof_calt": true,
        "otf_SmallParagraphProof_kern": true,
        "otf_SmallParagraphProof_liga": false,
        "otf_ArabicContextualFormsProof_calt": true,
        "otf_ArabicContextualFormsProof_rlig": true
    },
    "pdf_output": {
        "use_custom_location": false,              // Whether to use custom PDF output location
        "custom_location": ""                      // Custom directory for PDF output
    },
    "page_format": "A4Landscape"                   // Page format for generated proofs
}
}
"""