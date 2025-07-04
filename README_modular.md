# Font Proofing Application - Modular Structure

This document explains how the original `type_proofing.py` file has been reorganized into a modular structure for better maintainability and organization.

## Installation & Requirements

### Dependencies

The application requires Python 3.8+ and several specialized libraries for font processing and macOS integration.

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**Or use the setup script:**

```bash
chmod +x setup.sh
./setup.sh
```

### Key Dependencies

- **DrawBot**: Core drawing and PDF generation (`git+https://github.com/typemytype/drawbot`)
- **DrawBotGrid**: Grid extension for DrawBot (`git+https://github.com/mathieureguer/drawbotgrid`)
- **FontTools** (4.58.5+): Font file processing and analysis
- **WordSiv**: Word list generation for proofing (`git+https://github.com/tallpauley/wordsiv`)
- **PyObjC** (11.1+): macOS system integration
- **Vanilla/Cocoa-Vanilla** (0.8.0+): macOS UI framework

**Note**: DrawBot, DrawBotGrid, and WordSiv are installed from Git repositories as they are not available on PyPI.

**Note**: This application is designed specifically for macOS and requires the macOS system frameworks.

## File Structure

The application has been split into 4 main modules plus a main entry point:

### 1. `config.py` - Configuration & Constants
**Purpose**: Centralized configuration management
**Contains**:
- Page layout constants (margins, dimensions)
- Font size defaults
- OpenType feature defaults
- File paths and settings
- `FsSelection` class for font selection bits
- `Settings` class for persistent settings management

### 2. `font_analysis.py` - Font & Character Analysis
**Purpose**: Font processing and character set analysis
**Contains**:
- Font caching (`get_ttfont`, `_ttfont_cache`)
- Character set filtering (`filteredCharset`)
- Unicode categorization (`categorize`, `findAccented`)
- Variable font analysis (`variableFont`)
- Font pairing logic (`pairStaticStyles`)
- `FontManager` class for font collection management

### 3. `proof_generation.py` - Proof Generation Functions  
**Purpose**: PDF generation and text processing
**Contains**:
- Drawing functions (`drawFooter`, `drawContent`)
- Text formatting (`stringMaker`, mixed style handling)
- Text generation (`generateTextProofString`, WordSiv integration)
- Proof generation functions (`charsetProof`, `spacingProof`, `textProof`)
- Spacing string generation

### 4. `ui_interface.py` - User Interface Components
**Purpose**: GUI components and user interaction
**Contains**:
- Main application window (`ProofWindow`)
- Tab management (`FilesTab`, `ControlsTab`, `PreviewTab`)
- Event handlers and callbacks
- Drag & drop functionality
- Settings popover management
- PDF preview functionality

### 5. `Type Proofing.py` - Main Entry Point
**Purpose**: Application startup and coordination
**Contains**:
- Main entry point
- Error handling for missing dependencies
- Application initialization

## Benefits of This Structure

### 1. **Separation of Concerns**
- Configuration is isolated from business logic
- UI code is separate from font processing
- Proof generation logic is self-contained
- Font analysis functions are grouped together

### 2. **Improved Maintainability** 
- Easier to locate and modify specific functionality
- Reduced risk of breaking unrelated features
- Clear dependencies between modules

### 3. **Better Testing**
- Individual modules can be tested in isolation
- Font analysis functions can be unit tested
- Proof generation can be tested without UI

### 4. **Enhanced Readability**
- Each file has a clear, focused purpose
- Related functions are grouped together
- Less scrolling through large files

### 5. **Easier Development**
- Multiple developers can work on different modules
- UI changes don't affect font processing logic
- Configuration changes are centralized

## Migration Notes

### Import Changes
The original file imported everything at the top. The new structure uses targeted imports:
- `from config import Settings, DEFAULT_ON_FEATURES, ...`
- `from font_analysis import FontManager, filteredCharset, ...`
- `from proof_generation import charsetProof, spacingProof, ...`

### Shared State
Global variables from the original file are now:
- Constants moved to `config.py`
- Font cache moved to `font_analysis.py`
- UI state managed in respective UI classes

### Dependencies
Each module imports only what it needs:
- `config.py`: Standard library + JSON
- `font_analysis.py`: FontTools, DrawBot, config
- `proof_generation.py`: DrawBot, WordSiv, font analysis functions
- `ui_interface.py`: All GUI libraries, other modules

## Running the Application

To run the modularized application:

```bash
python "Type Proofing.py"
```

## Future Enhancements

This modular structure enables several potential improvements:

1. **Plugin Architecture**: Proof generation functions could be made pluggable
2. **Configuration UI**: Settings could have a dedicated configuration interface
3. **Export Formats**: New export formats could be added to proof generation
4. **Font Format Support**: New font formats could be added to font analysis
5. **Testing Suite**: Comprehensive tests could be added for each module
