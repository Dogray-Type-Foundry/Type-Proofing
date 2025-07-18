# Type Proofing Application - User Guide

## Overview

Type Proofing is a macOS application that generates comprehensive proofing documents for fonts. It automatically populates the pages with the required content, even if the font doesn't have a very complete character set.

## What the App Does

- **Font Analysis**: Automatically analyzes font capabilities, character sets, and OpenType features
- **Multiple Proof Types**: Generates various proof styles including character sets, spacing tests, paragraph proofs, and script-specific proofs
- **Variable Font Support**: Handles both static and variable fonts with axis control
- **Multi-Script Support**: Specialized proofs for Arabic, Persian, and Urdu
- **PDF Output**: Generates PDF documents with customizable settings
- **Batch Processing**: Processes multiple fonts simultaneously
- **Settings Management**: Save and load custom configurations

## Getting Started

### Installation
1. Download the Type Proofing DMG file
2. Run the DMG file
3. Move the TypeProofing.app bundle to your Applications folder
4. Launch the application

  **NOTE:** The built app is a universal2 bundle which means it should support computers with Intel and Apple Silicon processors

### First Launch
When you first open the app, you'll see a two-tab interface:
- **Files Tab**: For managing fonts, variable axes if available and output location
- **Controls Tab**: For selecting proofs, configuring individual proof settings and generating PDFs

## Files Tab - Detailed Guide

### Font Management

#### Adding Fonts
1. **Add Fonts Button**: Click to open a file browser and select font files
   - Supports: `.otf`, `.ttf` files
   - Supports static and variable fonts

2. **Font List Table**: Displays loaded fonts with the following information:
   - **Font Name**: The family and style name
   - **Variable Font Axes** (if applicable): Shows interactive controls for Weight, Width, Optical Size, etc.
   - Can select multiple fonts at once
   - Drag and drop fonts directly onto the font list
   - Reorder the font list, which influences the order of the fonts in the proofing document

#### Managing Fonts
- **Remove Selected**: Select fonts in the list and click to remove them
- **Reordering**: Drag fonts up and down in the list to change processing order
- **Font Details**: The table automatically detects and displays variable font axes

#### Variable Font Controls
- For variable fonts, the table displays the axis order based on the order of the axes in the first font of the list
- Each axis has values populated automatically when loading a font
- It will provide min, max and default (if different from min or max) for each axis
- You can adjust the numerical values for each axis, adding or removing values, separated by a comma
- The axis values set for each axis will influence what instances of the VF are used for proofing
- **Make sure to not go beyong what the font supports**

### PDF Output Settings

#### Location Options
1. **Save to first font's folder** (Default)
   - PDFs are saved in the same directory as the first font in your list
   - Convenient for keeping proofs together with font files

2. **Save to custom location**
   - Click "Browse..." to select a specific folder
   - Useful for organizing proofs in a dedicated location

## Controls Tab - Detailed Guide

### General settings

There's a number of settings that affect all proofs generated:
- **Page size**: There's a page size selector that provides a list of common printer page sizes in landscape only.
- **Show Grid**: This checkbox enables drawing of the baseline grid and text boxes which allows you to see the internal structure of your pages.

### Action Buttons
- **Add Settings File**: Load a previously saved settings configuration
- **Reset Settings**: Clear loaded settings and return to defaults
- **Generate Proof**: Creates PDF with all enabled proof types
- **Add Proof**: Allows you to create another copy of a proof, which can have completely different settings from the default one. This can be useful to see a given proof with certain Opentype features on and off
- **Remove Proof**: Remove the selected proofs from the list

### Proof Options List

The left side shows available proof types. Proof in the list can be reordered, which will affect the order of the proof in the generated PDF. Each can be enabled/disabled individually:

#### Basic Proof Types
- **Show Baselines/Grid**: Displays text box and baseline grids
- **Filtered Character Set**: Shows all available characters in the font
- **Spacing Proof**: Shows each character in a pattern that helps evaluate spacing
- **Basic Paragraph Large**: Paragraphs of text in large font size
- **Diacritic Words Large**: Diacritics proof in large font size
- **Basic Paragraph Small**: Paragraphs of text in small font size
- **Paired Styles Paragraph Small**: Show regular/italic or regular/bold parings to evaluate how those styles work together in small font size
- **Generative Text Small**: Generates pseudo-random text in small font size
- **Diacritic Words Small**: Diacritics proof in small font size
- **Misc Paragraph Small**: Preset text to test numbers, punctuation and symbols in paragraphs of text set in small font size

#### Arabic/Persian Proof Types
*These options appear automatically when Arabic-supporting fonts are loaded:*

- **ARA Character Set**: Shows arabic positional forms in big font size
- **Ar Paragraph Large**: Paragraphs of Arabic language text in large font size
- **Fa Paragraph Large**: Paragraphs of Persian language text in large font size
- **Ar Paragraph Small**: Paragraphs of Arabic language text in small font size
- **Fa Paragraph Small**: Paragraphs of Persian language text in small font size
- **Ar Vocalization Paragraph Small**: Shows Arabic vocalization marks in small font size
- **Ar-Lat Mixed Paragraph Small**: Shows Arabic and Latin script mixed in text
- **Ar Numbers Small**: Numbers in different contexts

### Proof Settings

Many proof types have configurable settings accessible when that proof's checkbox is first ticked on:

### Settings
- **Font Size**: Adjustable size for the specific proof type
- **Columns**: Change the number of text columns on the page
- **Tracking**: Allows you to add positive or negative tracking to your proof. Value is in points, not percentage
- **Alignment**: Allows you to change the text alingment of a proof. Options are: left, center and right
- **OpenType Features**: Enable/disable specific OpenType features. This list is populated automatically based on the Opentype features available in the first font on the Files list.
- **Paragraphs**: Select the number of paragraphs to be generated in the Wordsiv proof

### PDF Preview
- **Preview Window**: Shows real-time preview of the generated PDF. You can scroll though the pages and zoom in. You can resize the app's window to enlarge the Preview space.

## Advanced Features

### Settings Files
Settings files allow you to save and reuse specific configurations:

- **Auto-save**: Settings are automatically saved when you close the app. Settings are saved to `~/.type-proofing-prefs.json` (`~/` is the current user's Home folder)
- **Auto-load**: When you open the app again, settings are automatically loaded from `~/.type-proofing-prefs.json`. If there are no settings in the file, default settings will be loaded. Note that every single setting in the app can be saved to the settings file, including fonts, export location and all the Controls page settings
- **Creating Settings**: If you have settings that are useful for a given project, duplicate `~/.type-proofing-prefs.json`, rename it and save it elsewhere. You can load that settings file later so you don't have to set everything manually again, which is useful when working on different projects
- **Loading Custom Settings**: Use "Add Settings File" to load specific settings files

## Output and File Management

### PDF Structure
Generated PDFs include:
- **Footer Information**: Date, Font name, proof type and style used in that page
- **Page Numbers**: Sequential page numbering

### File Naming
PDFs are automatically named with:
- Timestamp including date and time
- Font family name

## Troubleshooting

### Common Issues

#### Arabic Proofs Not Showing
- **Issue**: Arabic proof options don't appear
- **Solution**: Ensure at least one loaded font supports Arabic script
- **Explanation**: App automatically detects script support

#### Missing Characters
- **Issue**: Some characters don't appear in proofs
- **Solution**: Check if the font actually contains those characters
- **Explanation**: App will use emtpy fallback font for missing characters. This can affect line height on lines where the empty fallback font is used
