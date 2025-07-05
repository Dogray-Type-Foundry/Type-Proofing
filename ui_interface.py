# User Interface Components and Main Application

import datetime
import io
import os
import sys
import traceback

# Third-party imports
import AppKit
import drawBot as db
import objc
import Quartz.PDFKit as PDFKit
import vanilla
from Foundation import NSObject
from PyObjCTools import AppHelper

# Local imports
from config import (
    SETTINGS_PATH,
    WINDOW_TITLE,
    DEFAULT_ON_FEATURES,
    SCRIPT_DIR,
    Settings,
    charsetFontSize,
    spacingFontSize,
    largeTextFontSize,
    smallTextFontSize,
    arabicVocalization,
    arabicLatinMixed,
    arabicFarsiUrduNumbers,
)
from font_analysis import (
    FontManager,
    filteredCharset,
    categorize,
    pairStaticStyles,
    variableFont,
    product_dict,
)
from proof_generation import (
    charsetProof,
    spacingProof,
    textProof,
    arabicContextualFormsProof,
)

# Import proof texts
try:
    from importlib import reload
    import prooftexts

    reload(prooftexts)
    import prooftexts as pte
except ImportError:
    print("Warning: prooftexts module not found.")
    pte = None


def close_existing_windows(window_title):
    """Close any existing windows with the same title."""
    try:
        app = AppKit.NSApp()
        if app is not None and hasattr(app, "windows"):
            for window in app.windows():
                if window.title() == window_title:
                    window.close()
    except (ImportError, AttributeError):
        pass


class TextBoxOutput:
    """Redirect output to a text box widget."""

    def __init__(self, textBox):
        self.textBox = textBox
        self.buffer = textBox.get() or ""

    def write(self, message):
        if message:
            # Remove placeholder if present
            if self.buffer.strip() == "Debug output will appear here.":
                self.buffer = ""
            self.buffer += message
            self.textBox.set(self.buffer)

    def flush(self):
        pass


class FontListDelegate(NSObject):
    """Delegate for handling font list drag and drop operations."""

    def init(self):
        """Initialize and return self."""
        self = objc.super(FontListDelegate, self).init()
        if self is None:
            return None
        self.callback = None
        return self

    def initWithCallback_(self, callback):
        """Initialize with a callback function."""
        self = self.init()
        if self is None:
            return None
        self.callback = callback
        return self

    def tableView_validateDrop_proposedRow_proposedDropOperation_(
        self, tableView, info, row, operation
    ):
        """Validate the drop operation."""
        pboard = info.draggingPasteboard()

        # Check for file URLs
        if pboard.types().containsObject_("public.file-url"):
            info.setDropOperation_(AppKit.NSTableViewDropAbove)
            return AppKit.NSDragOperationCopy

        # Check for filenames
        if pboard.types().containsObject_("NSFilenamesPboardType"):
            info.setDropOperation_(AppKit.NSTableViewDropAbove)
            return AppKit.NSDragOperationCopy

        print("No valid drag types found")
        return AppKit.NSDragOperationNone

    def tableView_acceptDrop_row_dropOperation_(self, tableView, info, row, operation):
        """Handle the drop operation."""
        pboard = info.draggingPasteboard()
        paths = []

        # Try to get filenames first as they're more reliable
        if pboard.types().containsObject_("NSFilenamesPboardType"):
            filenames = pboard.propertyListForType_("NSFilenamesPboardType")
            if isinstance(filenames, str):
                filenames = [filenames]
            paths.extend(filenames)

        # Then try URLs if we didn't get filenames
        elif pboard.types().containsObject_("public.file-url"):
            urls = pboard.propertyListForType_("public.file-url")
            if isinstance(urls, str):
                urls = [urls]
            for url in urls:
                if isinstance(url, AppKit.NSURL):
                    paths.append(url.path())
                else:
                    paths.append(AppKit.NSURL.URLWithString_(url).path())

        if paths:
            self.callback(paths)
            return True

        return False

    def numberOfRowsInTableView_(self, tableView):
        """Required data source method: return 0 since we're using vanilla.List."""
        return 0

    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        """Required data source method: return None since we're using vanilla.List."""
        return None


class FilesTab:
    """Handles the Files tab UI and functionality."""

    def __init__(self, parent_window, font_manager):
        self.parent_window = parent_window
        self.font_manager = font_manager
        self.create_ui()
        # Update table with any fonts loaded from settings
        self.update_table()

    def create_ui(self):
        """Create the Files tab UI components."""
        self.group = vanilla.Group((0, 0, -0, -0))

        # Table view for fonts
        columnDescriptions = [
            {"identifier": "name", "title": "Font", "width": 300},
            {"identifier": "axes", "title": "Axes", "width": 300, "editable": True},
        ]

        # Drag settings for internal reordering
        dragSettings = dict(makeDragDataCallback=self.makeDragDataCallback)

        # Drop settings for both file drops and internal reordering
        dropSettings = dict(
            pasteboardTypes=["fileURL", "dev.drawbot.proof.fontListIndexes"],
            dropCandidateCallback=self.dropCandidateCallback,
            performDropCallback=self.performDropCallback,
        )

        self.group.tableView = vanilla.List2(
            (0, 0, -0, -70),
            items=[],
            columnDescriptions=columnDescriptions,
            allowsSelection=True,
            allowsMultipleSelection=True,
            allowsEmptySelection=True,
            allowsSorting=False,  # Disable sorting to allow reordering
            allowColumnReordering=False,
            alternatingRowColors=True,
            showColumnTitles=True,
            drawFocusRing=True,
            dragSettings=dragSettings,
            dropSettings=dropSettings,
            editCallback=self.axisEditCallback,
            enableDelete=True,
            deleteCallback=self.deleteFontCallback,
        )

        self.group.addButton = vanilla.Button(
            (10, -60, 140, 20), "Add Fonts", callback=self.addFontsCallback
        )
        self.group.removeButton = vanilla.Button(
            (160, -60, 140, 20), "Remove Selected", callback=self.removeFontsCallback
        )

    def update_table(self):
        """Update the table with current font data."""
        table_data = self.font_manager.get_table_data()
        self.group.tableView.set(table_data)

    def addFontsCallback(self, sender):
        """Handle the Add Fonts button click."""
        try:
            from vanilla.dialogs import getFile

            result = getFile(
                messageText="Select font file(s)",
                fileTypes=["otf", "ttf"],
                allowsMultipleSelection=True,
            )
            if result:
                self.add_fonts(result)
            else:
                print("No files selected")
        except Exception as e:
            print(f"Error in file dialog: {e}")
            traceback.print_exc()

    def add_fonts(self, paths):
        """Add fonts to the font manager."""
        if self.font_manager.add_fonts(paths):
            self.update_table()
            self.parent_window.initialize_proof_settings()
        else:
            print("No new valid font paths found")

    def removeFontsCallback(self, sender):
        """Handle the Remove Selected button click."""
        self.group.tableView.removeSelection()
        # Sync backend with UI
        table_data = self.group.tableView.get()
        font_paths = [row["_path"] for row in table_data if "_path" in row]
        # Find indices of fonts to remove
        indices_to_remove = []
        for i, font_path in enumerate(self.font_manager.fonts):
            if font_path not in font_paths:
                indices_to_remove.append(i)
        self.font_manager.remove_fonts_by_indices(indices_to_remove)
        self.update_table()
        self.parent_window.initialize_proof_settings()

    def axisEditCallback(self, sender):
        """Handle axis editing in the table."""
        table_data = sender.get()
        self.font_manager.update_axis_values_from_table(table_data)

    def makeDragDataCallback(self, index):
        """Create drag data for internal reordering."""
        table_data = self.group.tableView.get()
        if 0 <= index < len(table_data):
            row = table_data[index]
            typesAndValues = {
                "dev.drawbot.proof.fontListIndexes": index,
                "dev.drawbot.proof.fontData": row,
            }
            return typesAndValues
        return {}

    def dropCandidateCallback(self, info):
        """Handle drop candidate validation for both file drops and reordering."""
        source = info["source"]

        # Internal reordering
        if source == self.group.tableView:
            return "move"

        # File drops from external sources
        return "copy"

    def performDropCallback(self, info):
        """Handle both file drops and internal reordering."""
        sender = info["sender"]
        source = info["source"]
        index = info["index"]
        items = info["items"]

        # Internal reordering
        if source == self.group.tableView:
            indexes = sender.getDropItemValues(
                items, "dev.drawbot.proof.fontListIndexes"
            )
            if not indexes:
                return False

            # Get current table data
            table_data = list(self.group.tableView.get())

            # Remove items to move (in reverse order to maintain indices)
            moved_items = []
            for idx in sorted(indexes, reverse=True):
                if 0 <= idx < len(table_data):
                    moved_items.insert(0, table_data.pop(idx))

            # Insert items at new position
            if index is not None:
                table_data[index:index] = moved_items
            else:
                table_data.extend(moved_items)

            # Update the table
            self.group.tableView.set(table_data)

            # Update backend font order
            new_font_paths = [row["_path"] for row in table_data if "_path" in row]
            if new_font_paths:
                self.font_manager.fonts = tuple(new_font_paths)
                self.font_manager.update_axis_values_from_table(table_data)
                self.parent_window.initialize_proof_settings()

            return True

        # File drops from external sources
        else:
            try:
                file_items = sender.getDropItemValues(items, "fileURL")
                if file_items:
                    paths = [
                        item.path()
                        for item in file_items
                        if item.path().lower().endswith((".otf", ".ttf"))
                    ]
                    if paths:
                        self.add_fonts(paths)
                        return True
            except Exception as e:
                print(f"Error processing file drop: {e}")
                # Try fallback approach
                try:
                    file_items = sender.getDropItemValues(items)
                    if file_items:
                        paths = [
                            item.path()
                            for item in file_items
                            if hasattr(item, "path")
                            and item.path().lower().endswith((".otf", ".ttf"))
                        ]
                        if paths:
                            self.add_fonts(paths)
                            return True
                except Exception as e2:
                    print(f"Error in fallback file drop: {e2}")

        return False

    def deleteFontCallback(self, sender):
        """Handle font deletion from the table."""
        selection = sender.getSelection()
        if not selection:
            return
        self.font_manager.remove_fonts_by_indices(selection)
        self.update_table()
        self.parent_window.initialize_proof_settings()


class ControlsTab:
    """Handles the Controls tab UI and functionality."""

    def __init__(self, parent_window, settings):
        self.parent_window = parent_window
        self.settings = settings
        self.create_ui()

    def create_ui(self):
        """Create the Controls tab UI components."""
        self.group = vanilla.Group((0, 0, -0, -0))
        y = 10

        # Font Size List
        self.group.fontSizeLabel = vanilla.TextBox((10, y, 150, 20), "Font Sizes:")
        y += 25

        font_size_items = [
            {
                "Setting": "Charset Font Size",
                "Value": self.settings.get_font_size("charset"),
            },
            {
                "Setting": "Spacing Font Size",
                "Value": self.settings.get_font_size("spacing"),
            },
            {
                "Setting": "Large Text Font Size",
                "Value": self.settings.get_font_size("large"),
            },
            {
                "Setting": "Small Text Font Size",
                "Value": self.settings.get_font_size("small"),
            },
        ]

        self.group.fontSizeList = vanilla.List(
            (10, y, 400, 100),
            font_size_items,
            columnDescriptions=[
                {"title": "Setting", "key": "Setting", "width": 150, "editable": False},
                {"title": "Value", "key": "Value", "width": 100, "editable": True},
            ],
            editCallback=self.fontSizeEditCallback,
        )
        y += 110

        # Proof Options List
        self.group.proofOptionsLabel = vanilla.TextBox(
            (10, y, 150, 20), "Proof Options:"
        )
        y += 25

        # Define which proofs have settings (for indicator)
        proofs_with_settings = {
            "Big Paragraph Proof",
            "Small Paragraph Proof",
            "Small Paired Styles Proof",
            "Small Wordsiv Proof",
            "Small Mixed Text Proof",
            "Big Arabic Text Proof",
            "Big Farsi Text Proof",
            "Small Arabic Text Proof",
            "Small Farsi Text Proof",
            "Arabic Vocalization Proof",
            "Arabic-Latin Mixed Proof",
            "Arabic Numbers Proof",
        }

        proof_options_items = []
        for option, enabled in [
            ("Show Baselines/Grid", self.settings.get_proof_option("showBaselines")),
            (
                "Character Set Proof",
                self.settings.get_proof_option("CharacterSetProof"),
            ),
            ("Spacing Proof", self.settings.get_proof_option("SpacingProof")),
            (
                "Big Paragraph Proof",
                self.settings.get_proof_option("BigParagraphProof"),
            ),
            (
                "Big Diacritics Proof",
                self.settings.get_proof_option("BigDiacriticsProof"),
            ),
            (
                "Small Paragraph Proof",
                self.settings.get_proof_option("SmallParagraphProof"),
            ),
            (
                "Small Paired Styles Proof",
                self.settings.get_proof_option("SmallPairedStylesProof"),
            ),
            (
                "Small Wordsiv Proof",
                self.settings.get_proof_option("SmallWordsivProof"),
            ),
            (
                "Small Diacritics Proof",
                self.settings.get_proof_option("SmallDiacriticsProof"),
            ),
            (
                "Small Mixed Text Proof",
                self.settings.get_proof_option("SmallMixedTextProof"),
            ),
            (
                "Arabic Contextual Forms",
                self.settings.get_proof_option("ArabicContextualFormsProof"),
            ),
            (
                "Big Arabic Text Proof",
                self.settings.get_proof_option("BigArabicTextProof"),
            ),
            (
                "Big Farsi Text Proof",
                self.settings.get_proof_option("BigFarsiTextProof"),
            ),
            (
                "Small Arabic Text Proof",
                self.settings.get_proof_option("SmallArabicTextProof"),
            ),
            (
                "Small Farsi Text Proof",
                self.settings.get_proof_option("SmallFarsiTextProof"),
            ),
            (
                "Arabic Vocalization Proof",
                self.settings.get_proof_option("ArabicVocalizationProof"),
            ),
            (
                "Arabic-Latin Mixed Proof",
                self.settings.get_proof_option("ArabicLatinMixedProof"),
            ),
            (
                "Arabic Numbers Proof",
                self.settings.get_proof_option("ArabicNumbersProof"),
            ),
        ]:
            item = {"Option": option, "Enabled": enabled}
            # Add indicator text for proofs with settings
            if option in proofs_with_settings:
                item["Settings"] = "⚙"  # Gear symbol as text
            else:
                item["Settings"] = ""
            proof_options_items.append(item)

        self.group.proofOptionsList = vanilla.List(
            (10, y, 400, 340),
            proof_options_items,
            columnDescriptions=[
                {"title": "Option", "key": "Option", "width": 200, "editable": False},
                {
                    "title": "Enabled",
                    "key": "Enabled",
                    "width": 80,
                    "cell": vanilla.CheckBoxListCell(),
                },
                {
                    "title": "Settings",
                    "key": "Settings",
                    "width": 50,
                    "editable": False,
                },
            ],
            editCallback=self.proofOptionsEditCallback,
            selectionCallback=self.proofSelectionCallback,
        )
        y += 230

        # Buttons arranged in a 2x2 grid at the bottom
        # First row: Generate Proof and Add Settings File
        self.group.generateButton = vanilla.Button(
            (10, -110, 140, 30),
            "Generate Proof",
            callback=self.parent_window.generateCallback,
        )
        self.group.addSettingsButton = vanilla.Button(
            (160, -110, 140, 30),
            "Add Settings File",
            callback=self.parent_window.addSettingsFileCallback,
        )

        # Second row: Close Window and Reset Settings
        self.group.closeButton = vanilla.Button(
            (10, -70, 140, 30),
            "Close Window",
            callback=self.parent_window.closeWindowCallback,
        )
        self.group.resetButton = vanilla.Button(
            (160, -70, 140, 30),
            "Reset Settings",
            callback=self.parent_window.resetSettingsCallback,
        )

    def update_table(self):
        """Update the table with current font data."""
        table_data = self.font_manager.get_table_data()
        self.group.tableView.set(table_data)

    def fontSizeEditCallback(self, sender):
        """Handle edits to font sizes."""
        items = sender.get()
        for item in items:
            setting = item["Setting"]
            value = item["Value"]
            try:
                value = int(value)
                if value <= 0:
                    print(f"Invalid font size for {setting}: must be > 0")
                    continue

                if setting == "Charset Font Size":
                    self.settings.set_font_size("charset", value)
                elif setting == "Spacing Font Size":
                    self.settings.set_font_size("spacing", value)
                elif setting == "Large Text Font Size":
                    self.settings.set_font_size("large", value)
                elif setting == "Small Text Font Size":
                    self.settings.set_font_size("small", value)

            except (ValueError, TypeError):
                print(f"Invalid font size for {setting}: {value}")

    def proofOptionsEditCallback(self, sender):
        """Handle edits to proof options."""
        items = sender.get()
        for item in items:
            option = item["Option"]
            enabled = item["Enabled"]

            if option == "Show Baselines/Grid":
                self.settings.set_proof_option("showBaselines", enabled)
            elif option.endswith(" Proof"):
                # Convert display name back to key
                key = option.replace(" ", "").replace("Proof", "Proof")
                self.settings.set_proof_option(key, enabled)

    def proofSelectionCallback(self, sender):
        """Handle proof selection to show popover with settings."""
        self.parent_window.proofSelectionCallback(sender)


class PreviewTab:
    """Handles the Preview tab UI and functionality."""

    def __init__(self, parent_window):
        self.parent_window = parent_window
        self.create_ui()

    def create_ui(self):
        """Create the Preview tab UI components."""
        self.group = vanilla.Group((0, 0, -0, -0))
        self.group.pdfBox = vanilla.Box((10, 10, -10, -10))

        self.pdfView = PDFKit.PDFView.alloc().initWithFrame_(((0, 0), (100, 100)))
        self.pdfView.setAutoresizingMask_(1 << 1 | 1 << 4)
        self.pdfView.setAutoScales_(True)
        self.pdfView.setDisplaysPageBreaks_(True)
        self.pdfView.setDisplayMode_(1)
        self.pdfView.setDisplayBox_(0)
        self.group.pdfBox._nsObject.setContentView_(self.pdfView)

    def display_pdf(self, pdf_path):
        """Display a PDF in the preview."""
        if pdf_path and os.path.exists(pdf_path):
            pdfDoc = PDFKit.PDFDocument.alloc().initWithURL_(
                AppKit.NSURL.fileURLWithPath_(pdf_path)
            )
            self.pdfView.setDocument_(pdfDoc)
            return True
        return False


class ProofWindow(object):
    """Main application window and controller."""

    def __init__(self):
        # Close any existing windows with the same title
        close_existing_windows(WINDOW_TITLE)

        # Initialize settings and font manager
        self.settings = Settings(SETTINGS_PATH)
        self.font_manager = FontManager(self.settings)

        # Initialize proof-specific settings storage
        self.proof_types_with_otf = [
            ("BigParagraphProof", "Big Paragraph Proof"),
            ("SmallParagraphProof", "Small Paragraph Proof"),
            ("SmallPairedStylesProof", "Small Paired Styles Proof"),
            ("SmallWordsivProof", "Small Wordsiv Proof"),
            ("SmallMixedTextProof", "Small Mixed Text Proof"),
            ("BigArabicTextProof", "Big Arabic Text Proof"),
            ("BigFarsiTextProof", "Big Farsi Text Proof"),
            ("SmallArabicTextProof", "Small Arabic Text Proof"),
            ("SmallFarsiTextProof", "Small Farsi Text Proof"),
            ("ArabicVocalizationProof", "Arabic Vocalization Proof"),
            ("ArabicLatinMixedProof", "Arabic-Latin Mixed Proof"),
            ("ArabicNumbersProof", "Arabic Numbers Proof"),
        ]
        self.default_on_features = DEFAULT_ON_FEATURES
        self.proof_settings = {}
        self.initialize_proof_settings()

        # Create main window
        self.w = vanilla.Window(
            (1000, 800), WINDOW_TITLE, minSize=(1000, 800), closable=False
        )

        # SegmentedButton for tab switching
        self.tabSwitcher = vanilla.SegmentedButton(
            (10, 10, 400, 24),
            segmentDescriptions=[
                dict(title="Files"),
                dict(title="Controls"),
                dict(title="Preview"),
            ],
            callback=self.switchTab,
        )

        # Create tab instances
        self.filesTab = FilesTab(self, self.font_manager)
        self.controlsTab = ControlsTab(self, self.settings)
        self.previewTab = PreviewTab(self)

        # --- Main Content Group (holds the three tab groups) ---
        self.mainContent = vanilla.Group((0, 44, -0, -0))
        self.mainContent.filesGroup = self.filesTab.group
        self.mainContent.controlsGroup = self.controlsTab.group
        self.mainContent.previewGroup = self.previewTab.group
        self.filesTab.group.show(True)
        self.controlsTab.group.show(False)
        self.previewTab.group.show(False)

        # --- Debug Text Editor ---
        self.debugTextEditor = vanilla.TextEditor(
            (0, 0, -0, -0), "Debug output will appear here.", readOnly=True
        )

        # --- SplitView: main content (top), debug (bottom) ---
        self.w.splitView = vanilla.SplitView(
            (0, 0, -0, -0),
            [
                dict(view=self.mainContent, identifier="main", size=600),
                dict(view=self.debugTextEditor, identifier="debug", size=100),
            ],
            isVertical=False,
        )
        self.w.tabSwitcher = self.tabSwitcher

        # Show only the selected group
        self.switchTab(self.tabSwitcher)

        # Redirect stdout and stderr to the debugTextEditor
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = TextBoxOutput(self.debugTextEditor)
        sys.stderr = TextBoxOutput(self.debugTextEditor)

        self.w.open()
        # Ensure Files tab is selected by default on startup
        self.tabSwitcher.set(0)
        self.switchTab(self.tabSwitcher)

    def switchTab(self, sender):
        """Switch between tabs."""
        idx = sender.get()
        self.filesTab.group.show(idx == 0)
        self.controlsTab.group.show(idx == 1)
        self.previewTab.group.show(idx == 2)

    def save_all_settings(self):
        """Save all current settings to the settings file."""
        try:
            # Save font sizes
            font_size_items = self.controlsTab.group.fontSizeList.get()
            for item in font_size_items:
                setting = item["Setting"]
                value = item["Value"]
                try:
                    value = int(value)
                    if setting == "Charset Font Size":
                        self.settings.set_font_size("charset", value)
                    elif setting == "Spacing Font Size":
                        self.settings.set_font_size("spacing", value)
                    elif setting == "Large Text Font Size":
                        self.settings.set_font_size("large", value)
                    elif setting == "Small Text Font Size":
                        self.settings.set_font_size("small", value)
                except (ValueError, TypeError):
                    pass  # Skip invalid values

            # Save proof options
            proof_options_items = self.controlsTab.group.proofOptionsList.get()
            for item in proof_options_items:
                option = item["Option"]
                enabled = bool(item["Enabled"])

                if option == "Show Baselines/Grid":
                    self.settings.set_proof_option("showBaselines", enabled)
                elif option.endswith(" Proof"):
                    # Convert display name back to key
                    key = option.replace(" ", "").replace("Proof", "Proof")
                    self.settings.set_proof_option(key, enabled)

            # Save proof-specific settings
            self.settings.set_proof_settings(self.proof_settings)

            # Save the settings file
            self.settings.save()

        except Exception as e:
            print(f"Error saving settings: {e}")

    def resetSettingsCallback(self, sender):
        """Handle the Reset Settings button click."""
        try:
            # Show confirmation dialog
            from vanilla.dialogs import askYesNo

            message_text = (
                "This will reset all settings to defaults and clear all loaded fonts."
            )
            if self.settings.user_settings_file:
                message_text += f"\n\nThis will also stop using the custom settings file:\n{self.settings.user_settings_file}"
            message_text += "\n\nAre you sure?"

            result = askYesNo("Reset All Settings", message_text)

            if result == 1:  # User clicked Yes
                # Reset settings to defaults (this also clears user_settings_file)
                self.settings.reset_to_defaults()

                # Override proof options to all be False (unchecked)
                proof_option_keys = [
                    "showBaselines",
                    "CharacterSetProof",
                    "SpacingProof",
                    "BigParagraphProof",
                    "BigDiacriticsProof",
                    "SmallParagraphProof",
                    "SmallPairedStylesProof",
                    "SmallWordsivProof",
                    "SmallDiacriticsProof",
                    "SmallMixedTextProof",
                    "ArabicContextualFormsProof",
                    "BigArabicTextProof",
                    "BigFarsiTextProof",
                    "SmallArabicTextProof",
                    "SmallFarsiTextProof",
                    "ArabicVocalizationProof",
                    "ArabicLatinMixedProof",
                    "ArabicNumbersProof",
                ]

                for option_key in proof_option_keys:
                    self.settings.set_proof_option(option_key, False)

                # Clear font manager
                self.font_manager.fonts = tuple()
                self.font_manager.font_info = {}
                self.font_manager.axis_values_by_font = {}

                # Refresh UI
                self.filesTab.update_table()

                # Refresh controls tab with default values
                self.refresh_controls_tab()

                self.initialize_proof_settings()

                print("Settings reset to defaults.")

        except Exception as e:
            print(f"Error resetting settings: {e}")
            traceback.print_exc()

    def closeWindowCallback(self, sender):
        """Handle the Close Window button click."""
        # Restore stdout and stderr
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self.w.close()
        AppHelper.stopEventLoop()

    def generateCallback(self, sender):
        """Handle the Generate Proof button click."""
        try:
            # Save all current settings before generating
            self.save_all_settings()

            # Setup stdout/stderr redirection
            buffer = io.StringIO()
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = buffer
            sys.stderr = buffer

            try:
                # Initialize variables
                global charsetFontSize, spacingFontSize, largeTextFontSize, smallTextFontSize
                controls = self.controlsTab.group  # "Controls" group

                if not self.font_manager.fonts:
                    print("No fonts loaded. Please add fonts first.")
                    return

                # Use the currently loaded fonts
                fonts = self.font_manager.fonts
                familyName = os.path.splitext(os.path.basename(fonts[0]))[0].split("-")[
                    0
                ]

                # Read axis values - now handled through Files tab per-font settings
                userAxesValues = {}

                # Read font sizes from list
                font_size_items = controls.fontSizeList.get()
                for item in font_size_items:
                    setting = item["Setting"]
                    value = item["Value"]
                    try:
                        value = int(value)
                        if setting == "Charset Font Size":
                            charsetFontSize = value
                        elif setting == "Spacing Font Size":
                            spacingFontSize = value
                        elif setting == "Large Text Font Size":
                            largeTextFontSize = value
                        elif setting == "Small Text Font Size":
                            smallTextFontSize = value
                    except (ValueError, TypeError):
                        print(f"Error reading font size for {setting}: {value}")

                # Read proof options from list
                proof_options_items = controls.proofOptionsList.get()
                proof_options = {}
                self.showBaselines = False

                for item in proof_options_items:
                    option = item["Option"]
                    enabled = bool(item["Enabled"])

                    if option == "Show Baselines/Grid":
                        self.showBaselines = enabled
                        db.showBaselines = self.showBaselines
                    elif option == "Character Set Proof":
                        proof_options["CharacterSetProof"] = enabled
                    elif option == "Spacing Proof":
                        proof_options["SpacingProof"] = enabled
                    elif option == "Big Paragraph Proof":
                        proof_options["BigParagraphProof"] = enabled
                    elif option == "Big Diacritics Proof":
                        proof_options["BigDiacriticsProof"] = enabled
                    elif option == "Small Paragraph Proof":
                        proof_options["SmallParagraphProof"] = enabled
                    elif option == "Small Paired Styles Proof":
                        proof_options["SmallPairedStylesProof"] = enabled
                    elif option == "Small Wordsiv Proof":
                        proof_options["SmallWordsivProof"] = enabled
                    elif option == "Small Diacritics Proof":
                        proof_options["SmallDiacriticsProof"] = enabled
                    elif option == "Small Mixed Text Proof":
                        proof_options["SmallMixedTextProof"] = enabled
                    elif option == "Arabic Contextual Forms":
                        proof_options["ArabicContextualFormsProof"] = enabled
                    elif option == "Big Arabic Text Proof":
                        proof_options["BigArabicTextProof"] = enabled
                    elif option == "Big Farsi Text Proof":
                        proof_options["BigFarsiTextProof"] = enabled
                    elif option == "Small Arabic Text Proof":
                        proof_options["SmallArabicTextProof"] = enabled
                    elif option == "Small Farsi Text Proof":
                        proof_options["SmallFarsiTextProof"] = enabled
                    elif option == "Arabic Vocalization Proof":
                        proof_options["ArabicVocalizationProof"] = enabled
                    elif option == "Arabic-Latin Mixed Proof":
                        proof_options["ArabicLatinMixedProof"] = enabled
                    elif option == "Arabic Numbers Proof":
                        proof_options["ArabicNumbersProof"] = enabled

                # Build otfeatures dict from proof_settings
                otfeatures_by_proof = {}
                cols_by_proof = {}
                paras_by_proof = {}

                for proof_key, _ in self.proof_types_with_otf:
                    # Get columns setting
                    cols_key = f"{proof_key}_cols"
                    if cols_key in self.proof_settings:
                        cols_by_proof[proof_key] = self.proof_settings[cols_key]

                    # Get paragraphs setting (only for SmallWordsivProof)
                    if proof_key in ["SmallWordsivProof"]:
                        para_key = f"{proof_key}_para"
                        if para_key in self.proof_settings:
                            paras_by_proof[proof_key] = self.proof_settings[para_key]

                    # Get OpenType features
                    otf_dict = {}
                    for key, value in self.proof_settings.items():
                        if key.startswith(f"otf_{proof_key}_"):
                            feature = key.replace(f"otf_{proof_key}_", "")
                            otf_dict[feature] = bool(value)
                    otfeatures_by_proof[proof_key] = otf_dict

                # Generate proof
                output_path = self.run_proof(
                    userAxesValues,
                    proof_options,
                    otfeatures_by_proof,
                    cols_by_proof=cols_by_proof,
                    paras_by_proof=paras_by_proof,
                )

                # Display the generated PDF
                if self.previewTab.display_pdf(output_path):
                    self.tabSwitcher.set(2)  # Switch to Preview tab
                    self.switchTab(self.tabSwitcher)

            except Exception as e:
                print(f"Error in proof generation: {e}")
                traceback.print_exc()

            # Restore stdout/stderr and update debug output
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.debugTextEditor.set(buffer.getvalue())

        except Exception as e:
            print(f"Error in generate callback: {e}")
            traceback.print_exc()

    def initialize_proof_settings(self):
        """Initialize proof-specific settings storage."""
        # Load existing proof settings from the settings file
        saved_proof_settings = self.settings.get_proof_settings()
        self.proof_settings = (
            saved_proof_settings.copy() if saved_proof_settings else {}
        )

        # Initialize default values for all proof types
        for proof_key, _ in self.proof_types_with_otf:
            # Column settings - set proper defaults for each proof type
            cols_key = f"{proof_key}_cols"
            # Big proofs use 1 column, small/mixed use 2 columns
            if proof_key in [
                "BigParagraphProof",
                "BigArabicTextProof",
                "BigFarsiTextProof",
            ]:
                default_cols = 1
            else:
                default_cols = 2

            if cols_key not in self.proof_settings:
                self.proof_settings[cols_key] = default_cols

            # Paragraph settings (only for SmallWordsivProof)
            if proof_key == "SmallWordsivProof":
                para_key = f"{proof_key}_para"
                if para_key not in self.proof_settings:
                    self.proof_settings[para_key] = 5

            # OpenType features
            if self.font_manager.fonts:
                try:
                    feature_tags = db.listOpenTypeFeatures(self.font_manager.fonts[0])
                except Exception:
                    feature_tags = []

                for tag in feature_tags:
                    feature_key = f"otf_{proof_key}_{tag}"
                    if feature_key not in self.proof_settings:
                        default_value = tag in self.default_on_features
                        self.proof_settings[feature_key] = default_value

    def proofSelectionCallback(self, sender):
        """Handle proof selection to show popover with settings."""
        selection = sender.getSelection()
        if not selection:
            return

        # Get the selected proof item
        items = sender.get()
        if not items or len(selection) == 0:
            return

        selected_idx = selection[0]
        if selected_idx >= len(items):
            return

        selected_item = items[selected_idx]
        proof_name = selected_item.get("Option", "")

        # Map proof names to keys for proof types that have settings
        proof_name_to_key = {
            "Big Paragraph Proof": "BigParagraphProof",
            "Small Paragraph Proof": "SmallParagraphProof",
            "Small Paired Styles Proof": "SmallPairedStylesProof",
            "Small Wordsiv Proof": "SmallWordsivProof",
            "Small Mixed Text Proof": "SmallMixedTextProof",
            "Big Arabic Text Proof": "BigArabicTextProof",
            "Big Farsi Text Proof": "BigFarsiTextProof",
            "Small Arabic Text Proof": "SmallArabicTextProof",
            "Small Farsi Text Proof": "SmallFarsiTextProof",
            "Arabic Vocalization Proof": "ArabicVocalizationProof",
            "Arabic-Latin Mixed Proof": "ArabicLatinMixedProof",
            "Arabic Numbers Proof": "ArabicNumbersProof",
        }

        # Only show popover for proofs that have settings
        if proof_name in proof_name_to_key:
            proof_key = proof_name_to_key[proof_name]
            self.current_proof_key = proof_key

            # Get the relative rect for the selected row
            relativeRect = sender.getNSTableView().rectOfRow_(selected_idx)

            # Create and show popover
            if not hasattr(self, "proof_settings_popover"):
                self.create_proof_settings_popover()

            # Set the proof type based on current selection
            proof_keys = [key for key, _ in self.proof_types_with_otf]
            if self.current_proof_key in proof_keys:
                idx = proof_keys.index(self.current_proof_key)
                self.proof_settings_popover.proofTypePopup.set(idx)
                self.proofTypeSelectionCallback(
                    self.proof_settings_popover.proofTypePopup
                )

            # Open popover positioned relative to the selected row
            self.proof_settings_popover.open(
                parentView=sender.getNSTableView(),
                preferredEdge="right",
                relativeRect=relativeRect,
            )

    def create_proof_settings_popover(self):
        """Create the proof settings popover."""
        self.proof_settings_popover = vanilla.Popover((400, 460))
        popover = self.proof_settings_popover

        # Proof type selector
        popover.proofTypeLabel = vanilla.TextBox(
            (10, 10, -10, 20), "Select Proof Type:"
        )
        proof_type_names = [label for _, label in self.proof_types_with_otf]
        popover.proofTypePopup = vanilla.PopUpButton(
            (10, 35, -10, 20),
            proof_type_names,
            callback=self.proofTypeSelectionCallback,
        )

        # Numeric settings list
        popover.numericLabel = vanilla.TextBox((10, 70, -10, 20), "Numeric Settings:")
        popover.numericList = vanilla.List(
            (10, 95, -10, 120),
            [],
            columnDescriptions=[
                {"title": "Setting", "key": "Setting", "width": 150},
                {"title": "Value", "key": "Value", "width": 100, "editable": True},
            ],
            editCallback=self.numericSettingsEditCallback,
        )

        # OpenType features list
        popover.featuresLabel = vanilla.TextBox(
            (10, 225, -10, 20), "OpenType Features:"
        )
        popover.featuresList = vanilla.List(
            (10, 250, -10, -10),
            [],
            columnDescriptions=[
                {"title": "Feature", "key": "Feature", "width": 150},
                {
                    "title": "Enabled",
                    "key": "Enabled",
                    "width": 80,
                    "cell": vanilla.CheckBoxListCell(),
                },
            ],
            editCallback=self.featuresEditCallback,
        )

        # Initialize with first proof type
        if self.proof_types_with_otf:
            popover.proofTypePopup.set(0)
            self.proofTypeSelectionCallback(popover.proofTypePopup)

    def proofTypeSelectionCallback(self, sender):
        """Handle proof type selection in popover."""
        if not hasattr(self, "proof_settings_popover"):
            return

        idx = sender.get()
        if idx < 0 or idx >= len(self.proof_types_with_otf):
            return

        proof_key, proof_label = self.proof_types_with_otf[idx]
        popover = self.proof_settings_popover

        # Update numeric settings
        numeric_items = []

        # Columns setting with appropriate defaults
        cols_key = f"{proof_key}_cols"
        # Big proofs and Big Arabic/Farsi proofs default to 1 column
        if proof_key in [
            "BigParagraphProof",
            "BigArabicTextProof",
            "BigFarsiTextProof",
        ]:
            default_cols = 1
        else:
            # All other proofs default to 2 columns
            default_cols = 2
        cols_value = self.proof_settings.get(cols_key, default_cols)
        numeric_items.append(
            {"Setting": "Columns", "Value": cols_value, "_key": cols_key}
        )

        # Paragraphs setting (only for SmallWordsivProof)
        if proof_key in ["SmallWordsivProof"]:
            para_key = f"{proof_key}_para"
            para_value = self.proof_settings.get(para_key, 5)
            numeric_items.append(
                {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
            )

        popover.numericList.set(numeric_items)

        # Update features settings
        if self.font_manager.fonts:
            try:
                feature_tags = db.listOpenTypeFeatures(self.font_manager.fonts[0])
            except Exception:
                feature_tags = []
        else:
            feature_tags = []

        feature_items = []
        for tag in feature_tags:
            feature_key = f"otf_{proof_key}_{tag}"
            default_value = tag in self.default_on_features
            feature_value = self.proof_settings.get(feature_key, default_value)
            feature_items.append(
                {"Feature": tag, "Enabled": feature_value, "_key": feature_key}
            )

        popover.featuresList.set(feature_items)

    def numericSettingsEditCallback(self, sender):
        """Handle edits to numeric settings in popover."""
        items = sender.get()
        for item in items:
            if "_key" in item:
                key = item["_key"]
                value = item["Value"]
                try:
                    value = int(value)
                    if value <= 0:
                        print(f"Invalid value for {item['Setting']}: must be > 0")
                        continue
                    self.proof_settings[key] = value
                except (ValueError, TypeError):
                    print(f"Invalid value for {item['Setting']}: {value}")

    def featuresEditCallback(self, sender):
        """Handle edits to OpenType features in popover."""
        items = sender.get()
        for item in items:
            if "_key" in item:
                key = item["_key"]
                enabled = item["Enabled"]
                self.proof_settings[key] = bool(enabled)

    def run_proof(
        self,
        userAxesValues,
        proof_options,
        otfeatures_by_proof=None,
        now=None,
        nowformat=None,
        cols_by_proof=None,
        paras_by_proof=None,
    ):
        """Run the proof generation process."""
        db.newDrawing()
        pairedStaticStyles = pairStaticStyles(self.font_manager.fonts)
        if otfeatures_by_proof is None:
            otfeatures_by_proof = {}
        if cols_by_proof is None:
            cols_by_proof = {}
        if paras_by_proof is None:
            paras_by_proof = {}
        feature_tags = (
            db.listOpenTypeFeatures(self.font_manager.fonts[0])
            if self.font_manager.fonts
            else []
        )
        # Create default OpenType features dict
        default_otfeatures = {tag: tag in DEFAULT_ON_FEATURES for tag in feature_tags}
        spacing_otfeatures = dict(default_otfeatures)
        spacing_otfeatures["kern"] = False

        # Initialize now and nowformat if not provided
        if now is None:
            now = datetime.datetime.now()
        if nowformat is None:
            nowformat = now.strftime("%Y-%m-%d_%H%M")

        for indFont in self.font_manager.fonts:
            fullCharacterSet = filteredCharset(indFont)
            cat = categorize(fullCharacterSet)
            variableDict = db.listFontVariations(indFont)

            # Prefer per-font axes from Files tab if present
            axes_dict = self.font_manager.get_axis_values_for_font(indFont)
            if axes_dict:
                axesProduct = list(product_dict(**axes_dict))
            elif userAxesValues:
                axesProduct = list(product_dict(**userAxesValues))
            elif not bool(variableDict):
                axesProduct = ""
            else:
                axesProduct = variableFont(indFont)[0]

            # Explicit, in-order proof generation (matches checkbox/UI order)
            if proof_options.get("CharacterSetProof"):
                charsetProof(
                    fullCharacterSet,
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    otfeatures_by_proof.get("CharacterSetProof", {}),
                )
            if proof_options.get("SpacingProof"):
                spacingProof(
                    fullCharacterSet,
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    otfeatures_by_proof.get("SpacingProof", {}),
                )
            if proof_options.get("BigParagraphProof"):
                textProof(
                    cat["uniLu"] + cat["uniLl"],
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    cols_by_proof.get("BigParagraphProof", 1),
                    2,
                    False,
                    largeTextFontSize,
                    "Big size proof",
                    False,
                    False,
                    False,
                    None,
                    otfeatures_by_proof.get("BigParagraphProof", {}),
                    0,
                    cat,
                    fullCharacterSet,
                )
            if proof_options.get("BigDiacriticsProof"):
                textProof(
                    cat["accented"],
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    1,
                    3,
                    False,
                    largeTextFontSize,
                    "Big size accented proof",
                    False,
                    False,
                    False,
                    None,
                    otfeatures_by_proof.get("BigDiacriticsProof", {}),
                    3,
                    cat,
                    fullCharacterSet,
                )
            if proof_options.get("SmallParagraphProof"):
                textProof(
                    cat["uniLu"] + cat["uniLl"],
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    cols_by_proof.get("SmallParagraphProof", 2),
                    5,
                    False,
                    smallTextFontSize,
                    "Small size proof",
                    False,
                    False,
                    False,
                    None,
                    otfeatures_by_proof.get("SmallParagraphProof", {}),
                    0,
                    cat,
                    fullCharacterSet,
                )
            if proof_options.get("SmallPairedStylesProof"):
                textProof(
                    cat["uniLu"] + cat["uniLl"],
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    cols_by_proof.get("SmallPairedStylesProof", 2),
                    5,
                    False,
                    smallTextFontSize,
                    "Small size rg & bd proof",
                    False,
                    True,
                    True,
                    None,
                    otfeatures_by_proof.get("SmallPairedStylesProof", {}),
                    0,
                    cat,
                    fullCharacterSet,
                )
            if proof_options.get("SmallWordsivProof"):
                textProof(
                    cat["uniLu"] + cat["uniLl"],
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    cols_by_proof.get("SmallWordsivProof", 2),
                    paras_by_proof.get("SmallWordsivProof", 5),
                    False,
                    smallTextFontSize,
                    "Small size proof mixed",
                    False,
                    False,
                    True,
                    None,
                    otfeatures_by_proof.get("SmallWordsivProof", {}),
                    0,
                    cat,
                    fullCharacterSet,
                )
            if proof_options.get("SmallDiacriticsProof"):
                textProof(
                    cat["accented"],
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    2,
                    4,
                    False,
                    smallTextFontSize,
                    "Small size accented proof",
                    False,
                    False,
                    False,
                    None,
                    otfeatures_by_proof.get("SmallDiacriticsProof", {}),
                    4,
                    cat,
                    fullCharacterSet,
                )
            if proof_options.get("SmallMixedTextProof"):
                textProof(
                    cat["uniLu"] + cat["uniLl"],
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    cols_by_proof.get("SmallMixedTextProof", 2),
                    5,
                    False,
                    smallTextFontSize,
                    "Small size misc proof",
                    False,
                    False,
                    False,
                    (
                        pte.bigRandomNumbers if pte else "",
                        pte.additionalSmallText if pte else "",
                    ),
                    otfeatures_by_proof.get("SmallMixedTextProof", {}),
                    0,
                    cat,
                    fullCharacterSet,
                )

            # Arabic Contextual Forms Proof (no settings needed)
            if proof_options.get("ArabicContextualFormsProof"):
                arabicContextualFormsProof(
                    cat,
                    axesProduct,
                    indFont,
                    pairedStaticStyles,
                    otfeatures_by_proof.get("ArabicContextualFormsProof", {}),
                )

            # Big Arabic Text Proof
            if proof_options.get("BigArabicTextProof"):
                arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                if arabic_chars:
                    textProof(
                        arabic_chars,
                        axesProduct,
                        indFont,
                        pairedStaticStyles,
                        cols_by_proof.get("BigArabicTextProof", 1),
                        2,  # Fixed paragraph count for big text
                        False,
                        largeTextFontSize,
                        "Big Arabic text proof",
                        False,
                        False,
                        False,
                        None,
                        otfeatures_by_proof.get("BigArabicTextProof", {}),
                        0,
                        cat,
                        fullCharacterSet,
                        "ar",
                    )

            # Big Farsi Text Proof
            if proof_options.get("BigFarsiTextProof"):
                farsi_chars = cat.get("fa", "") or cat.get("arab", "")
                if farsi_chars:
                    textProof(
                        farsi_chars,
                        axesProduct,
                        indFont,
                        pairedStaticStyles,
                        cols_by_proof.get("BigFarsiTextProof", 1),
                        2,  # Fixed paragraph count for big text
                        False,
                        largeTextFontSize,
                        "Big Farsi text proof",
                        False,
                        False,
                        False,
                        None,
                        otfeatures_by_proof.get("BigFarsiTextProof", {}),
                        0,
                        cat,
                        fullCharacterSet,
                        "fa",
                    )

            # Small Arabic Text Proof
            if proof_options.get("SmallArabicTextProof"):
                arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                if arabic_chars:
                    textProof(
                        arabic_chars,
                        axesProduct,
                        indFont,
                        pairedStaticStyles,
                        cols_by_proof.get("SmallArabicTextProof", 2),
                        5,  # Fixed paragraph count for small text
                        False,
                        smallTextFontSize,
                        "Small Arabic text proof",
                        False,
                        False,
                        False,
                        None,
                        otfeatures_by_proof.get("SmallArabicTextProof", {}),
                        0,
                        cat,
                        fullCharacterSet,
                        "ar",
                    )

            # Small Farsi Text Proof
            if proof_options.get("SmallFarsiTextProof"):
                farsi_chars = cat.get("fa", "") or cat.get("arab", "")
                if farsi_chars:
                    textProof(
                        farsi_chars,
                        axesProduct,
                        indFont,
                        pairedStaticStyles,
                        cols_by_proof.get("SmallFarsiTextProof", 2),
                        5,  # Fixed paragraph count for small text
                        False,
                        smallTextFontSize,
                        "Small Farsi text proof",
                        False,
                        False,
                        False,
                        None,
                        otfeatures_by_proof.get("SmallFarsiTextProof", {}),
                        0,
                        cat,
                        fullCharacterSet,
                        "fa",
                    )

            # Arabic Vocalization Proof
            if proof_options.get("ArabicVocalizationProof"):
                arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                if arabic_chars:
                    textProof(
                        arabic_chars,
                        axesProduct,
                        indFont,
                        pairedStaticStyles,
                        cols_by_proof.get("ArabicVocalizationProof", 2),
                        5,
                        False,
                        smallTextFontSize,
                        "Arabic vocalization proof",
                        False,
                        False,
                        False,
                        (arabicVocalization,),
                        otfeatures_by_proof.get("ArabicVocalizationProof", {}),
                        0,
                        cat,
                        fullCharacterSet,
                        "ar",
                    )

            # Arabic-Latin Mixed Proof
            if proof_options.get("ArabicLatinMixedProof"):
                arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                if arabic_chars:
                    textProof(
                        arabic_chars,
                        axesProduct,
                        indFont,
                        pairedStaticStyles,
                        cols_by_proof.get("ArabicLatinMixedProof", 2),
                        5,
                        False,
                        smallTextFontSize,
                        "Arabic-Latin mixed proof",
                        False,
                        False,
                        False,
                        (arabicLatinMixed,),
                        otfeatures_by_proof.get("ArabicLatinMixedProof", {}),
                        0,
                        cat,
                        fullCharacterSet,
                        "ar",
                    )

            # Arabic Numbers Proof
            if proof_options.get("ArabicNumbersProof"):
                arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                if arabic_chars:
                    textProof(
                        arabic_chars,
                        axesProduct,
                        indFont,
                        pairedStaticStyles,
                        cols_by_proof.get("ArabicNumbersProof", 2),
                        5,
                        False,
                        smallTextFontSize,
                        "Arabic numbers proof",
                        False,
                        False,
                        False,
                        (arabicFarsiUrduNumbers,),
                        otfeatures_by_proof.get("ArabicNumbersProof", {}),
                        0,
                        cat,
                        fullCharacterSet,
                        "ar",
                    )

        db.endDrawing()
        # Save the proof doc
        try:
            if self.font_manager.fonts:
                first_font_path = self.font_manager.fonts[0]
                # Get the directory of the first font
                font_directory = os.path.dirname(first_font_path)
                family_name = os.path.splitext(os.path.basename(first_font_path))[
                    0
                ].split("-")[0]
            else:
                # Fallback to script directory if no fonts loaded
                font_directory = SCRIPT_DIR
                family_name = "proof"
            proofPath = os.path.join(
                font_directory, f"{nowformat}_{family_name}-proof.pdf"
            )
            db.saveImage(proofPath)
            print(f"Proof PDF was saved: {proofPath}")
        except Exception as e:
            print(f"Error saving proof: {e}")
            print("Use UI to select which proofs to generate")
        print(datetime.datetime.now() - now)
        return proofPath

    def addSettingsFileCallback(self, sender):
        """Handle the Add Settings File button click."""
        try:
            from vanilla.dialogs import getFile

            # Show file dialog to select settings file
            result = getFile(
                title="Select Settings File",
                messageText="Choose a JSON settings file to load:",
                fileTypes=["json"],
                allowsMultipleSelection=False,
            )

            if result and len(result) > 0:
                settings_file_path = result[0]

                # Try to load the settings file
                if self.settings.load_user_settings_file(settings_file_path):
                    # Clear font manager and reload fonts
                    self.font_manager.fonts = tuple()
                    self.font_manager.font_info = {}
                    self.font_manager.axis_values_by_font = {}

                    # Load fonts from the new settings
                    font_paths = self.settings.get_fonts()
                    if font_paths:
                        self.font_manager.load_fonts(font_paths)

                        # Load axis values
                        for font_path in font_paths:
                            axis_values = self.settings.get_font_axis_values(font_path)
                            if axis_values:
                                self.font_manager.axis_values_by_font[font_path] = (
                                    axis_values
                                )

                    # Refresh UI
                    self.filesTab.update_table()

                    # Refresh controls tab with new values
                    self.refresh_controls_tab()

                    self.initialize_proof_settings()

                    print(f"Settings loaded from: {settings_file_path}")

                    # Show information dialog
                    from vanilla.dialogs import message

                    message(
                        "Settings Loaded",
                        f"Settings have been loaded from:\n{settings_file_path}\n\n"
                        "Changes will now be saved to this file instead of the auto-save file.",
                        informativeText="You can use 'Reset Settings' to clear this file and return to auto-save mode.",
                    )
                else:
                    from vanilla.dialogs import message

                    message(
                        "Error Loading Settings",
                        f"Failed to load settings from:\n{settings_file_path}\n\n"
                        "Please check that the file contains valid JSON and try again.",
                    )

        except Exception as e:
            print(f"Error loading settings file: {e}")
            traceback.print_exc()
            from vanilla.dialogs import message

            message("Error", f"An error occurred while loading the settings file:\n{e}")

    def refresh_controls_tab(self):
        """Refresh the controls tab with current settings values."""
        try:
            # Update font size list
            font_size_items = [
                {
                    "Setting": "Charset Font Size",
                    "Value": self.settings.get_font_size("charset"),
                },
                {
                    "Setting": "Spacing Font Size",
                    "Value": self.settings.get_font_size("spacing"),
                },
                {
                    "Setting": "Large Text Font Size",
                    "Value": self.settings.get_font_size("large"),
                },
                {
                    "Setting": "Small Text Font Size",
                    "Value": self.settings.get_font_size("small"),
                },
            ]
            self.controlsTab.group.fontSizeList.set(font_size_items)

            # Update proof options list
            proofs_with_settings = {
                "Big Paragraph Proof",
                "Small Paragraph Proof",
                "Small Paired Styles Proof",
                "Small Wordsiv Proof",
                "Small Mixed Text Proof",
                "Big Arabic Text Proof",
                "Big Farsi Text Proof",
                "Small Arabic Text Proof",
                "Small Farsi Text Proof",
                "Arabic Vocalization Proof",
                "Arabic-Latin Mixed Proof",
                "Arabic Numbers Proof",
            }

            proof_options_items = []
            for option, enabled in [
                (
                    "Show Baselines/Grid",
                    self.settings.get_proof_option("showBaselines"),
                ),
                (
                    "Character Set Proof",
                    self.settings.get_proof_option("CharacterSetProof"),
                ),
                ("Spacing Proof", self.settings.get_proof_option("SpacingProof")),
                (
                    "Big Paragraph Proof",
                    self.settings.get_proof_option("BigParagraphProof"),
                ),
                (
                    "Big Diacritics Proof",
                    self.settings.get_proof_option("BigDiacriticsProof"),
                ),
                (
                    "Small Paragraph Proof",
                    self.settings.get_proof_option("SmallParagraphProof"),
                ),
                (
                    "Small Paired Styles Proof",
                    self.settings.get_proof_option("SmallPairedStylesProof"),
                ),
                (
                    "Small Wordsiv Proof",
                    self.settings.get_proof_option("SmallWordsivProof"),
                ),
                (
                    "Small Diacritics Proof",
                    self.settings.get_proof_option("SmallDiacriticsProof"),
                ),
                (
                    "Small Mixed Text Proof",
                    self.settings.get_proof_option("SmallMixedTextProof"),
                ),
                (
                    "Arabic Contextual Forms",
                    self.settings.get_proof_option("ArabicContextualFormsProof"),
                ),
                (
                    "Big Arabic Text Proof",
                    self.settings.get_proof_option("BigArabicTextProof"),
                ),
                (
                    "Big Farsi Text Proof",
                    self.settings.get_proof_option("BigFarsiTextProof"),
                ),
                (
                    "Small Arabic Text Proof",
                    self.settings.get_proof_option("SmallArabicTextProof"),
                ),
                (
                    "Small Farsi Text Proof",
                    self.settings.get_proof_option("SmallFarsiTextProof"),
                ),
                (
                    "Arabic Vocalization Proof",
                    self.settings.get_proof_option("ArabicVocalizationProof"),
                ),
                (
                    "Arabic-Latin Mixed Proof",
                    self.settings.get_proof_option("ArabicLatinMixedProof"),
                ),
                (
                    "Arabic Numbers Proof",
                    self.settings.get_proof_option("ArabicNumbersProof"),
                ),
            ]:
                item = {"Option": option, "Enabled": enabled}
                # Add indicator text for proofs with settings
                if option in proofs_with_settings:
                    item["Settings"] = "⚙"  # Gear symbol as text
                else:
                    item["Settings"] = ""
                proof_options_items.append(item)

            self.controlsTab.group.proofOptionsList.set(proof_options_items)

        except Exception as e:
            print(f"Error refreshing controls tab: {e}")
            import traceback

            traceback.print_exc()
