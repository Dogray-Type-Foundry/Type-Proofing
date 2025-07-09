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

### Proof Options List

The left side shows available proof types. Each can be enabled/disabled individually:

#### Basic Proof Types
- **Show Baselines/Grid**: Displays text box and baseline grids
- **Character Set Proof**: Shows all available characters in the font
- **Spacing Proof**: Shows each character in a pattern that helps evaluate spacing
- **Big Paragraph Proof**: Paragraphs of text in large font size
- **Big Diacritics Proof**: Diacritics proof in large font size
- **Small Paragraph Proof**: Paragraphs of text in small font size
- **Small Paired Styles Proof**: Show regular/italic or regular/bold parings to evaluate how those styles work together in small font size
- **Small Wordsiv Proof**: Generates pseudo-random text in small font size
- **Small Diacritics Proof**: Diacritics proof in small font size
- **Small Mixed Text Proof**: Preset text to test numbers, punctuation and symbols in paragraphs of text set in small font size

#### Arabic/Persian Proof Types
*These options appear automatically when Arabic-supporting fonts are loaded:*

- **Arabic Contextual Forms**: Tests Arabic character contextual variations
- **Big Arabic Text Proof**: Large Arabic text blocks
- **Big Farsi Text Proof**: Large Persian/Farsi text blocks  
- **Small Arabic Text Proof**: Small Arabic text testing
- **Small Farsi Text Proof**: Small Persian text testing
- **Arabic Vocalization Proof**: Tests Arabic diacritical marks
- **Arabic-Latin Mixed Proof**: Mixed Arabic and Latin script testing
- **Arabic Numbers Proof**: Arabic numerals and numbering systems

### Proof Settings

Many proof types have configurable settings accessible via a settings button:

#### Common Settings
- **Font Size**: Adjustable size for the specific proof type
- **OpenType Features**: Enable/disable specific OpenType features
- **Text Content**: Custom text input for some proof types
- **Layout Options**: Spacing, alignment, and formatting controls

### Action Buttons

#### Generate Proof
- **Main Action**: Creates PDF with all enabled proof types
- **Processing**: Shows progress and completion status
- **Output**: Saves PDF to the location specified in Files tab

#### Settings Management
- **Add Settings File**: Load a previously saved settings configuration
- **Remove Settings File**: Clear loaded settings and return to defaults

#### PDF Preview
- **Preview Window**: Shows real-time preview of the generated PDF
- **Navigation**: Use preview controls to browse through pages
- **Zoom**: Adjust preview size for detailed inspection

## Advanced Features

### Settings Files
Settings files allow you to save and reuse specific configurations:

1. **Creating Settings**: Configure your preferred proof options and settings
2. **Saving**: Settings are automatically saved when you close the app
3. **Loading Custom Settings**: Use "Add Settings File" to load specific configurations
4. **Sharing**: Settings files can be shared between users or projects

### Batch Processing
Process multiple fonts efficiently:
1. Add all fonts to the Files tab
2. Configure desired proof types in Controls tab
3. Click "Generate Proof" to process all fonts
4. Each font generates a separate PDF with consistent settings

### Variable Font Workflows
For variable fonts:
1. Load the variable font file
2. Adjust axis values in the Files tab table
3. Generate proofs with your specific axis settings
4. Test multiple variations by adjusting axes and regenerating

## Output and File Management

### PDF Structure
Generated PDFs include:
- **Header Information**: Font name, generation date, and proof type
- **Page Numbers**: Sequential page numbering
- **Organized Sections**: Each proof type on dedicated pages
- **Footer Details**: Font family, date, and page information

### File Naming
PDFs are automatically named with:
- Font family name
- Generation timestamp
- Descriptive suffix based on proof types included

### Quality Settings
All PDFs are generated at print quality with:
- High-resolution output suitable for printing
- Embedded fonts for accurate display
- Optimized file sizes for sharing

## Troubleshooting

### Common Issues

#### iCloud Drive Paths
- **Issue**: Path picker appears empty for iCloud Drive
- **Solution**: Check the backup text field - the path is correctly selected
- **Result**: PDFs will save properly despite display issue

#### Arabic Proofs Not Showing
- **Issue**: Arabic proof options don't appear
- **Solution**: Ensure at least one loaded font supports Arabic script
- **Detection**: App automatically detects script support

#### Missing Characters
- **Issue**: Some characters don't appear in proofs
- **Solution**: Check if the font actually contains those characters
- **Alternative**: App will use fallback font for missing characters

## Tips for Best Results

### Font Testing Strategy
1. **Start Simple**: Begin with basic character set and spacing proofs
2. **Add Complexity**: Gradually enable more proof types as needed
3. **Script-Specific**: Use appropriate script proofs for your font's target languages
4. **Comparative**: Test multiple weights/styles together for consistency

### Professional Workflows
1. **Systematic Testing**: Develop consistent proof configurations for projects
2. **Version Control**: Keep proof PDFs with font development versions
3. **Client Review**: Use generated PDFs for client presentations and approvals
4. **Quality Assurance**: Regular proofing catches design issues early

### Optimization
1. **Batch Processing**: Process related fonts together for efficiency
2. **Settings Reuse**: Save settings files for repeated use
3. **Selective Proofing**: Enable only relevant proof types for faster generation
4. **Organization**: Maintain clear folder structures for fonts and proofs

---

*This application is designed to streamline professional font proofing workflows. For additional support or feature requests, refer to the application documentation or contact the development team.*
