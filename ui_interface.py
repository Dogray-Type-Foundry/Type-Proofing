# User Interface Components and Main Application

import datetime
import io
import os
import sys
import traceback

# Third-party imports
import AppKit
from AppKit import NSBezelStyleRegularSquare
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
        self.current_axes = []  # Track current axes for editing
        self.create_ui()
        # Update PDF location UI to reflect current settings
        self.update_pdf_location_ui()
        # Update table with any fonts loaded from settings
        self.update_table()

    def create_ui(self):
        """Create the Files tab UI components."""
        self.group = vanilla.Group((0, 0, -0, -0))

        # Initialize with basic column descriptions - will be updated dynamically
        self.base_column_descriptions = [
            {"identifier": "name", "title": "Font", "width": 300},
        ]

        # Start with basic columns
        columnDescriptions = self.base_column_descriptions.copy()

        # Drag settings for internal reordering
        dragSettings = dict(makeDragDataCallback=self.makeDragDataCallback)

        # Drop settings for both file drops and internal reordering
        dropSettings = dict(
            pasteboardTypes=["fileURL", "dev.drawbot.proof.fontListIndexes"],
            dropCandidateCallback=self.dropCandidateCallback,
            performDropCallback=self.performDropCallback,
        )

        self.group.tableView = vanilla.List2(
            (0, 0, -0, -120),
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
            (10, -40, 155, 20), "Add Fonts", callback=self.addFontsCallback
        )
        self.group.removeButton = vanilla.Button(
            (175, -40, 155, 20), "Remove Selected", callback=self.removeFontsCallback
        )

        # PDF Output Location section in a Box to the right of Remove Selected button
        self.group.pdfOutputBox = vanilla.Box((10, -105, -10, 52))

        self.group.pdfOutputBox.defaultLocationRadio = vanilla.RadioButton(
            (10, 0, 200, 18),
            "Save to first font's folder",
            callback=self.pdfLocationRadioCallback,
            value=True,
            sizeStyle="small",
        )

        self.group.pdfOutputBox.customLocationRadio = vanilla.RadioButton(
            (10, 20, 150, 18),
            "Save to custom location:",
            callback=self.pdfLocationRadioCallback,
            sizeStyle="small",
        )

        # Browse button to select custom folder location
        self.group.pdfOutputBox.browseButton = vanilla.Button(
            (170, 19, 80, 22),
            "Browse...",
            callback=self.browsePdfLocationCallback,
            sizeStyle="small",
        )

        self.group.pdfOutputBox.pathControl = vanilla.PathControl(
            (260, 19, -10, 22),
            "",  # initial url/path (empty string for no initial path)
            callback=self.pdfPathControlCallback,
        )

        # Add a backup text field to show path when PathControl fails (especially for iCloud Drive)
        self.group.pdfOutputBox.pathBackupText = vanilla.TextBox(
            (260, 45, -10, 17),
            "",
            sizeStyle="small",
        )

    def get_first_font_folder(self):
        """Get the folder path of the first font in the list."""
        if self.font_manager.fonts:
            first_font_path = self.font_manager.fonts[0]
            return os.path.dirname(first_font_path)
        return ""

    def update_table(self):
        """Update the table with current font data."""
        if not self.font_manager.fonts:
            # If no fonts, show empty table with basic columns
            self.group.tableView.set([])
            self.current_axes = []
            return

        # Get table data with individual axis columns
        table_data, all_axes = self.font_manager.get_table_data_with_individual_axes()

        # Check if we need to update the table columns
        if not hasattr(self, "current_axes") or self.current_axes != all_axes:
            # Need to update the table with new columns
            self.update_table_columns(all_axes)

        # Reorder columns to match first font's axis order
        self.reorder_columns_by_first_font()

        # Update table data
        self.group.tableView.set(table_data)

        # Store current axes for later use
        self.current_axes = all_axes

    def update_table_columns(self, all_axes):
        """Update the table columns dynamically using insertColumn instead of recreating."""
        # Get current column identifiers
        current_columns = self.group.tableView.getColumnIdentifiers()

        # Base columns that should always exist
        base_column_ids = [desc["identifier"] for desc in self.base_column_descriptions]

        # Calculate which columns need to be added
        new_axes = [axis for axis in all_axes if axis not in current_columns]

        # Add new axis columns
        for axis in new_axes:
            column_desc = {
                "identifier": axis,
                "title": axis,
                "width": 100,
                "editable": True,
            }
            # Insert at the end (after all existing columns)
            self.group.tableView.appendColumn(column_desc)

        # Note: We could also remove columns that are no longer needed, but for
        # simplicity and to avoid potential issues, we'll keep all existing columns.
        # This means once an axis column is added, it stays even if no fonts use it.
        # This is acceptable behavior and avoids complexity.

    def reorder_columns_by_first_font(self):
        """Reorder axis columns to match the first font's axis order."""
        if not self.font_manager.fonts:
            return

        # Get the desired axis order from the first font
        desired_axes_order = self.font_manager.get_all_axes()

        # Get current column identifiers
        current_columns = self.group.tableView.getColumnIdentifiers()

        # Base columns that should always be first
        base_column_ids = [desc["identifier"] for desc in self.base_column_descriptions]

        # Find which axis columns currently exist
        existing_axis_columns = [
            col for col in current_columns if col not in base_column_ids
        ]

        # Only reorder if we have axis columns and they're not already in the right order
        if existing_axis_columns and existing_axis_columns != desired_axes_order:
            # Build the new column order: base columns + axes in first font's order
            new_column_order = base_column_ids[:]

            # Add axes in the order they appear in the first font
            for axis in desired_axes_order:
                if axis in existing_axis_columns:
                    new_column_order.append(axis)

            # Add any remaining axis columns that aren't in the first font
            for axis in existing_axis_columns:
                if axis not in new_column_order:
                    new_column_order.append(axis)

            # Apply the new column order if it's different from current
            if new_column_order != current_columns:
                # Store current table data
                current_data = self.group.tableView.get()

                # Remove all axis columns
                for axis in existing_axis_columns:
                    self.group.tableView.removeColumn(axis)

                # Re-add axis columns in the new order
                for axis in new_column_order:
                    if axis not in base_column_ids:  # Skip base columns
                        column_desc = {
                            "identifier": axis,
                            "title": axis,
                            "width": 100,
                            "editable": True,
                        }
                        self.group.tableView.appendColumn(column_desc)

                # Restore table data
                self.group.tableView.set(current_data)

    def reset_table_columns(self):
        """Reset the table to only show base columns, removing all axis columns."""
        # Get current column identifiers
        current_columns = self.group.tableView.getColumnIdentifiers()

        # Base columns that should always exist
        base_column_ids = [desc["identifier"] for desc in self.base_column_descriptions]

        # Remove all axis columns (any column that's not in base_column_ids)
        for column_id in current_columns:
            if column_id not in base_column_ids:
                self.group.tableView.removeColumn(column_id)

        # Reset current_axes to empty list
        self.current_axes = []

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
            # Update PDF location UI to populate PathControl with first font's folder
            self.update_pdf_location_ui()
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
        if hasattr(self, "current_axes"):
            self.font_manager.update_axis_values_from_individual_axes_table(
                table_data, self.current_axes
            )
        else:
            # Fallback to old method if current_axes not available
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
                # Update axis values using the appropriate method
                if hasattr(self, "current_axes"):
                    self.font_manager.update_axis_values_from_individual_axes_table(
                        table_data, self.current_axes
                    )
                else:
                    self.font_manager.update_axis_values_from_table(table_data)
                # Reorder columns to match new first font's axis order
                self.reorder_columns_by_first_font()
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

    def pdfLocationRadioCallback(self, sender):
        """Handle PDF location radio button changes."""
        # Update the settings based on which radio button is selected
        use_custom = self.group.pdfOutputBox.customLocationRadio.get()

        # Update settings - ensure pdf_output key exists
        settings = self.parent_window.settings
        if "pdf_output" not in settings.data:
            settings.data["pdf_output"] = {
                "use_custom_location": False,
                "custom_location": "",
            }
        settings.data["pdf_output"]["use_custom_location"] = use_custom
        settings.save()

        # Update UI state
        self.update_pdf_location_ui()

    def _set_path_control_with_refresh(self, path_control, url):
        """
        Set PathControl URL with enhanced compatibility for py2app bundles.
        This addresses iCloud Drive path display issues in app bundles.
        """
        if not url:
            path_control.set("")
            # Clear backup text as well
            if hasattr(self.group.pdfOutputBox, "pathBackupText"):
                self.group.pdfOutputBox.pathBackupText.set("")
            return

        import os
        import urllib.parse

        # Convert file URL to path for processing
        if url.startswith("file://"):
            path = urllib.parse.unquote(url[7:])
        else:
            path = url

        # Try to resolve iCloud Drive paths to their actual locations
        original_path = path
        try:
            if "Mobile Documents" in path or "iCloud" in path:
                # For iCloud Drive paths, try to resolve the real path
                resolved_path = os.path.realpath(path)
                if os.path.exists(resolved_path):
                    path = resolved_path
        except Exception as e:
            print(f"Path resolution failed: {e}")

        # Ensure proper URL encoding for app bundles
        try:
            # Re-encode the path properly
            encoded_path = urllib.parse.quote(path, safe="/:")
            final_url = f"file://{encoded_path}"

            # Try multiple approaches to set the PathControl
            # Approach 1: Direct set
            path_control.set(final_url)

            # Approach 2: Force refresh if direct set doesn't work
            if not path_control.get():  # If PathControl is still empty
                path_control.set("")  # Clear
                path_control.set(final_url)  # Reset

            # Approach 3: Try with unencoded URL as fallback
            if not path_control.get():
                simple_url = f"file://{path}"
                path_control.set(simple_url)

            # Set backup text field with user-friendly path
            if hasattr(self.group.pdfOutputBox, "pathBackupText"):
                # Show a user-friendly version of the path
                display_path = original_path
                if "Mobile Documents/com~apple~CloudDocs" in display_path:
                    # Make iCloud Drive paths more readable
                    user_home = os.path.expanduser("~")
                    icloud_base = (
                        f"{user_home}/Library/Mobile Documents/com~apple~CloudDocs"
                    )
                    if display_path.startswith(icloud_base):
                        relative_path = display_path[len(icloud_base) :].lstrip("/")
                        display_path = (
                            f"iCloud Drive/{relative_path}"
                            if relative_path
                            else "iCloud Drive"
                        )

                # self.group.pdfOutputBox.pathBackupText.set(f"Selected: {display_path}")

        except Exception as e:
            print(f"PathControl setting failed: {e}")
            # Last resort - try the original URL
            path_control.set(url)

            # Still set backup text
            if hasattr(self.group.pdfOutputBox, "pathBackupText"):
                self.group.pdfOutputBox.pathBackupText.set(f"Selected: {original_path}")

    def pdfPathControlCallback(self, sender):
        """Handle PathControl changes for PDF output location."""
        url = sender.get()
        if url:
            # Use helper method to set PathControl with refresh for app bundle compatibility
            self._set_path_control_with_refresh(sender, url)

            # Update settings
            settings = self.parent_window.settings
            if "pdf_output" not in settings.data:
                settings.data["pdf_output"] = {
                    "use_custom_location": False,
                    "custom_location": "",
                }

            settings.data["pdf_output"]["custom_location"] = url
            settings.data["pdf_output"]["use_custom_location"] = True
            settings.save()

            # Update UI - select custom location radio button
            self.group.pdfOutputBox.customLocationRadio.set(True)
            self.group.pdfOutputBox.defaultLocationRadio.set(False)

    def browsePdfLocationCallback(self, sender):
        """Handle the browse button click for PDF output location."""
        try:
            from vanilla.dialogs import getFolder

            # Get current path as starting point
            current_path = self.group.pdfOutputBox.pathControl.get()
            if not current_path or not os.path.exists(current_path):
                # Fall back to first font's folder if available
                current_path = self.get_first_font_folder()

            result = getFolder(messageText="Choose a folder for PDF output:")

            if result:
                # Handle the Objective-C array properly
                selected_path = None
                if hasattr(result, "__iter__") and hasattr(result, "__len__"):
                    # It's an iterable with length, try to get the first item
                    if len(result) > 0:
                        selected_path = result[0]
                        # If it's still an array-like object, convert to string
                        if hasattr(selected_path, "__iter__") and not isinstance(
                            selected_path, str
                        ):
                            selected_path = str(selected_path).strip('()"')
                        else:
                            selected_path = str(selected_path)
                else:
                    selected_path = str(result)

                # Clean up the path string - remove any remaining array formatting
                selected_path = selected_path.strip('()"').strip()
                if selected_path.startswith('"') and selected_path.endswith('"'):
                    selected_path = selected_path[1:-1]

                # Convert to proper file URL for PathControl
                if not selected_path.startswith("file://"):
                    file_url = f"file://{selected_path}"
                    print(f"PDF will be saved at: {file_url}")
                else:
                    file_url = selected_path
                    print(f"PDF will be saved at: {file_url}")

                # Update the PathControl to display the selected path
                self._set_path_control_with_refresh(
                    self.group.pdfOutputBox.pathControl, file_url
                )

                # Update settings
                settings = self.parent_window.settings
                if "pdf_output" not in settings.data:
                    settings.data["pdf_output"] = {
                        "use_custom_location": False,
                        "custom_location": "",
                    }

                settings.data["pdf_output"]["custom_location"] = selected_path
                settings.data["pdf_output"]["use_custom_location"] = True
                settings.save()

                # Update UI to reflect the change
                self.group.pdfOutputBox.customLocationRadio.set(True)
                self.group.pdfOutputBox.defaultLocationRadio.set(False)

        except Exception as e:
            print(f"Error browsing for PDF location: {e}")
            import traceback

            traceback.print_exc()

    def update_pdf_location_ui(self):
        """Update the PDF location UI to reflect current settings."""
        settings = self.parent_window.settings

        # Ensure pdf_output key exists with defaults
        if "pdf_output" not in settings.data:
            settings.data["pdf_output"] = {
                "use_custom_location": False,
                "custom_location": "",
            }

        use_custom = settings.data["pdf_output"].get("use_custom_location", False)
        custom_location = settings.data["pdf_output"].get("custom_location", "")

        # Update radio buttons
        self.group.pdfOutputBox.defaultLocationRadio.set(not use_custom)
        self.group.pdfOutputBox.customLocationRadio.set(use_custom)

        # Update path control - populate with first font's folder if no custom location is set
        if custom_location:
            # Ensure we use a proper file URL for PathControl
            if not custom_location.startswith("file://"):
                file_url = f"file://{custom_location}"
            else:
                file_url = custom_location
            self._set_path_control_with_refresh(
                self.group.pdfOutputBox.pathControl, file_url
            )
        else:
            # Auto-populate with first font's folder to make PathControl visible and functional
            first_font_folder = self.get_first_font_folder()
            if first_font_folder:
                file_url = f"file://{first_font_folder}"
                self._set_path_control_with_refresh(
                    self.group.pdfOutputBox.pathControl, file_url
                )
            else:
                self._set_path_control_with_refresh(
                    self.group.pdfOutputBox.pathControl, ""
                )

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
        self.popover_states = {}  # Track which popovers are shown for each row
        self.create_ui()

    def get_proof_options_list(self):
        """Generate dynamic proof options list based on font capabilities."""
        # Base proof options (always shown)
        base_options = [
            ("Character Set Proof", "CharacterSetProof"),
            ("Spacing Proof", "SpacingProof"),
            ("Big Paragraph Proof", "BigParagraphProof"),
            ("Big Diacritics Proof", "BigDiacriticsProof"),
            ("Small Paragraph Proof", "SmallParagraphProof"),
            ("Small Paired Styles Proof", "SmallPairedStylesProof"),
            ("Small Wordsiv Proof", "SmallWordsivProof"),
            ("Small Diacritics Proof", "SmallDiacriticsProof"),
            ("Small Mixed Text Proof", "SmallMixedTextProof"),
        ]

        # Arabic/Persian proof options (shown only if fonts support Arabic)
        arabic_options = [
            ("Arabic Contextual Forms", "ArabicContextualFormsProof"),
            ("Big Arabic Text Proof", "BigArabicTextProof"),
            ("Big Farsi Text Proof", "BigFarsiTextProof"),
            ("Small Arabic Text Proof", "SmallArabicTextProof"),
            ("Small Farsi Text Proof", "SmallFarsiTextProof"),
            ("Arabic Vocalization Proof", "ArabicVocalizationProof"),
            ("Arabic-Latin Mixed Proof", "ArabicLatinMixedProof"),
            ("Arabic Numbers Proof", "ArabicNumbersProof"),
        ]

        # Check if any loaded font supports Arabic
        show_arabic_proofs = self.parent_window.font_manager.has_arabic_support()

        # Build the complete options list
        all_options = base_options[:]
        if show_arabic_proofs:
            all_options.extend(arabic_options)

        # Create a mapping from display names to options
        options_dict = dict(all_options)

        # Get the saved proof order from settings
        saved_order = self.settings.get_proof_order()

        # Build ordered list based on saved order, filtering out unavailable options
        ordered_options = []
        available_display_names = set(options_dict.keys())

        # First, add items in the saved order
        for display_name in saved_order:
            if display_name in available_display_names:
                settings_key = options_dict[display_name]
                ordered_options.append((display_name, settings_key))
                available_display_names.remove(display_name)

        # Then add any new options that weren't in the saved order
        for display_name, settings_key in all_options:
            if display_name in available_display_names:
                ordered_options.append((display_name, settings_key))

        # Convert to UI format
        proof_options_items = []
        for display_name, settings_key in ordered_options:
            enabled = self.settings.get_proof_option(settings_key)
            item = {
                "Option": display_name,
                "Enabled": enabled,
                "_original_option": display_name,
            }
            proof_options_items.append(item)

        return proof_options_items

    def refresh_proof_options_list(self):
        """Refresh the proof options list when fonts change."""
        try:
            # Generate new proof options list
            proof_options_items = self.get_proof_options_list()

            # Update the list
            self.group.proofOptionsList.set(proof_options_items)

            # Update the standalone checkbox
            if hasattr(self.group, "showBaselinesCheckbox"):
                self.group.showBaselinesCheckbox.set(
                    self.settings.get_proof_option("showBaselines")
                )
        except Exception as e:
            print(f"Error refreshing proof options list: {e}")

    def integrate_preview_view(self, pdfView):
        """Integrate the PDF view into the controls tab."""
        if hasattr(self.group, "previewBox"):
            self.group.previewBox._nsObject.setContentView_(pdfView)

    def create_ui(self):
        """Create the Controls tab UI components."""
        try:
            self.group = vanilla.Group((0, 0, -0, -0))

            # Create a split layout: Controls on left, Preview on right
            # Controls area (left side)
            controls_x = 10
            y = 10

            # Preview area (right side)
            self.group.previewBox = vanilla.Box((350, 10, -10, -10))

            # Define which proofs have settings (all proofs now have font size setting)
            proofs_with_settings = {
                "Character Set Proof",
                "Spacing Proof",
                "Big Paragraph Proof",
                "Big Diacritics Proof",
                "Small Paragraph Proof",
                "Small Paired Styles Proof",
                "Small Wordsiv Proof",
                "Small Diacritics Proof",
                "Small Mixed Text Proof",
                "Arabic Contextual Forms",
                "Big Arabic Text Proof",
                "Big Farsi Text Proof",
                "Small Arabic Text Proof",
                "Small Farsi Text Proof",
                "Arabic Vocalization Proof",
                "Arabic-Latin Mixed Proof",
                "Arabic Numbers Proof",
            }

            # Generate dynamic proof options list
            proof_options_items = self.get_proof_options_list()

            # Track popover states for proofs with settings
            for item in proof_options_items:
                proof_name = item["Option"]
                base_option = item.get("_original_option", proof_name)
                if base_option in proofs_with_settings:
                    self.popover_states[proof_name] = False  # Track popover visibility

            # Drag settings for internal reordering only
            dragSettings = dict(makeDragDataCallback=self.makeProofDragDataCallback)

            # Drop settings for internal reordering only (no external file drops)
            dropSettings = dict(
                pasteboardTypes=["dev.drawbot.proof.proofOptionIndexes"],
                dropCandidateCallback=self.dropProofCandidateCallback,
                performDropCallback=self.performProofDropCallback,
            )

            self.group.proofOptionsList = vanilla.List2(
                (controls_x, y, 320, 420),  # Adjusted width for left side
                proof_options_items,
                columnDescriptions=[
                    {
                        "identifier": "Option",
                        "title": "Option",
                        "key": "Option",
                        "width": 240,  # Adjusted width
                        "editable": False,
                    },
                    {
                        "identifier": "Enabled",
                        "title": "Enabled",
                        "key": "Enabled",
                        "width": 16,
                        "editable": True,
                        "cellClass": vanilla.CheckBoxList2Cell,
                    },
                ],
                showColumnTitles=False,
                allowsSelection=True,
                allowsMultipleSelection=True,
                allowsEmptySelection=True,
                allowsSorting=False,  # Disable sorting to allow reordering
                allowColumnReordering=False,
                alternatingRowColors=True,
                enableDelete=True,
                drawFocusRing=True,
                dragSettings=dragSettings,
                dropSettings=dropSettings,
                autohidesScrollers=True,
                editCallback=self.proofOptionsEditCallback,
            )
            y += 460  # Adjust button position

            # Standalone "Show Baselines/Grid" checkbox
            self.group.showBaselinesCheckbox = vanilla.CheckBox(
                (controls_x + 4, -96, 100, 20),
                "Show Grid",
                value=self.settings.get_proof_option("showBaselines"),
                callback=self.showBaselinesCallback,
            )

            self.group.addProofButton = vanilla.Button(
                (controls_x + 165, -96, 155, 20),
                title="Add Proof",
                callback=self.addProofCallback,
            )

            self.group.generateButton = vanilla.GradientButton(
                (controls_x, -70, 155, 55),
                title="Generate Proof",
                callback=self.parent_window.generateCallback,
            )
            self.group.generateButton._nsObject.setBezelStyle_(
                NSBezelStyleRegularSquare
            )
            self.group.generateButton._nsObject.setKeyEquivalent_("\r")

            # Second row: Add Settings File and Reset Settings
            self.group.addSettingsButton = vanilla.Button(
                (controls_x + 165, -68, 155, 20),
                "Add Settings File",
                callback=self.parent_window.addSettingsFileCallback,
            )

            self.group.resetButton = vanilla.Button(
                (controls_x + 165, -40, 155, 20),
                "Reset Settings",
                callback=self.parent_window.resetSettingsCallback,
            )

        except Exception as e:
            print(f"Error creating Controls tab UI: {e}")
            import traceback

            traceback.print_exc()
            raise

    def update_table(self):
        """Update the table with current font data."""
        table_data = self.font_manager.get_table_data()
        self.group.tableView.set(table_data)

    def proofOptionsEditCallback(self, sender):
        """Handle edits to proof options."""
        items = sender.get()

        # Check if this is a checkbox edit
        edited_index = sender.getEditedIndex()

        # Define which proofs have settings (same as in create_ui)
        proofs_with_settings = {
            "Character Set Proof",
            "Spacing Proof",
            "Big Paragraph Proof",
            "Big Diacritics Proof",
            "Small Paragraph Proof",
            "Small Paired Styles Proof",
            "Small Wordsiv Proof",
            "Small Diacritics Proof",
            "Small Mixed Text Proof",
            "Arabic Contextual Forms",
            "Big Arabic Text Proof",
            "Big Farsi Text Proof",
            "Small Arabic Text Proof",
            "Small Farsi Text Proof",
            "Arabic Vocalization Proof",
            "Arabic-Latin Mixed Proof",
            "Arabic Numbers Proof",
        }

        if edited_index is not None and edited_index < len(items):
            item = items[edited_index]
            proof_name = item["Option"]  # Use the actual proof name
            base_option = item.get("_original_option", proof_name)  # Get base type
            enabled = item["Enabled"]

            # If this proof has settings and was just enabled, show the popover
            if (
                base_option in proofs_with_settings
                and enabled
                and not self.popover_states.get(proof_name, False)
            ):
                # Hide any other open popovers first
                self.hide_all_popovers_except(proof_name)

                # Show the popover for this option
                self.show_popover_for_option(proof_name, edited_index)
                self.popover_states[proof_name] = True
            elif (
                base_option in proofs_with_settings
                and not enabled
                and self.popover_states.get(proof_name, False)
            ):
                # If the proof was disabled, hide its popover
                self.hide_popover_for_option(proof_name)
                self.popover_states[proof_name] = False

        # Handle regular proof option edits (save settings)
        for item in items:
            proof_name = item["Option"]  # Use the actual proof name
            base_option = item.get("_original_option", proof_name)  # Get base type
            enabled = item["Enabled"]

            # For unique proof names, use a sanitized version as the key
            unique_key = proof_name.replace(" ", "_").replace("/", "_")
            self.settings.set_proof_option(unique_key, enabled)

    def showBaselinesCallback(self, sender):
        """Handle the Show Baselines/Grid standalone checkbox."""
        enabled = sender.get()
        self.settings.set_proof_option("showBaselines", enabled)

    def makeProofDragDataCallback(self, index):
        """Create drag data for internal proof options reordering."""
        proof_items = self.group.proofOptionsList.get()
        if 0 <= index < len(proof_items):
            item = proof_items[index]
            typesAndValues = {
                "dev.drawbot.proof.proofOptionIndexes": index,
                "dev.drawbot.proof.proofOptionData": item,
            }
            return typesAndValues
        return {}

    def dropProofCandidateCallback(self, info):
        """Handle drop candidate validation for proof options reordering."""
        source = info["source"]

        # Only allow internal reordering (no external drops)
        if source == self.group.proofOptionsList:
            return "move"

        return None  # Reject external drops

    def performProofDropCallback(self, info):
        """Handle proof options internal reordering."""
        sender = info["sender"]
        source = info["source"]
        index = info["index"]
        items = info["items"]

        # Internal reordering only
        if source == self.group.proofOptionsList:
            indexes = sender.getDropItemValues(
                items, "dev.drawbot.proof.proofOptionIndexes"
            )
            if not indexes:
                return False

            # Get current list data
            proof_items = list(self.group.proofOptionsList.get())

            # Remove items to move (in reverse order to maintain indices)
            moved_items = []
            for idx in sorted(indexes, reverse=True):
                if 0 <= idx < len(proof_items):
                    moved_items.insert(0, proof_items.pop(idx))

            # Insert items at new position
            if index is not None:
                proof_items[index:index] = moved_items
            else:
                proof_items.extend(moved_items)

            # Update the list
            self.group.proofOptionsList.set(proof_items)

            # Save the new order to settings
            new_order = [item["Option"] for item in proof_items]
            self.settings.set_proof_order(new_order)
            self.settings.save()

            return True

        return False

    def hide_all_popovers_except(self, except_option):
        """Hide all open popovers except the specified one."""
        for option in self.popover_states:
            if option != except_option and self.popover_states[option]:
                self.hide_popover_for_option(option)
                self.popover_states[option] = False

    def show_popover_for_option(self, option, row_index):
        """Show popover for the specified option."""
        # Map proof names to keys for proof types that have settings
        proof_name_to_key = {
            "Character Set Proof": "CharacterSetProof",
            "Spacing Proof": "SpacingProof",
            "Big Paragraph Proof": "BigParagraphProof",
            "Big Diacritics Proof": "BigDiacriticsProof",
            "Small Paragraph Proof": "SmallParagraphProof",
            "Small Paired Styles Proof": "SmallPairedStylesProof",
            "Small Wordsiv Proof": "SmallWordsivProof",
            "Small Diacritics Proof": "SmallDiacriticsProof",
            "Small Mixed Text Proof": "SmallMixedTextProof",
            "Arabic Contextual Forms": "ArabicContextualFormsProof",
            "Big Arabic Text Proof": "BigArabicTextProof",
            "Big Farsi Text Proof": "BigFarsiTextProof",
            "Small Arabic Text Proof": "SmallArabicTextProof",
            "Small Farsi Text Proof": "SmallFarsiTextProof",
            "Arabic Vocalization Proof": "ArabicVocalizationProof",
            "Arabic-Latin Mixed Proof": "ArabicLatinMixedProof",
            "Arabic Numbers Proof": "ArabicNumbersProof",
        }

        # Check if this is a base proof type or a numbered variant
        base_proof_type = option
        for base_name in proof_name_to_key.keys():
            if option.startswith(base_name):
                base_proof_type = base_name
                break

        if base_proof_type in proof_name_to_key:
            # Use the unique option name as the proof key for settings
            unique_proof_key = option.replace(" ", "_").replace("/", "_")
            self.parent_window.current_proof_key = unique_proof_key
            self.parent_window.current_base_proof_type = base_proof_type

            # Get the relative rect for the selected row
            relativeRect = self.group.proofOptionsList.getNSTableView().rectOfRow_(
                row_index
            )

            # Create and show popover
            if not hasattr(self.parent_window, "proof_settings_popover"):
                self.parent_window.create_proof_settings_popover()

            # Update popover with settings for this specific proof instance
            self.parent_window.update_proof_settings_popover_for_instance(
                unique_proof_key, base_proof_type
            )

            # Open popover positioned relative to the selected row
            self.parent_window.proof_settings_popover.open(
                parentView=self.group.proofOptionsList.getNSTableView(),
                preferredEdge="right",
                relativeRect=relativeRect,
            )

    def hide_popover_for_option(self, option):
        """Hide popover for the specified option."""
        if hasattr(self.parent_window, "proof_settings_popover"):
            self.parent_window.proof_settings_popover.close()

    def addProofCallback(self, sender):
        """Handle the Add Proof button click."""
        try:
            # Create and show the add proof popover if it doesn't exist
            if not hasattr(self, "add_proof_popover"):
                self.create_add_proof_popover()

            # Position the popover to the right of the Add Proof button
            button_frame = sender.getNSButton().frame()
            self.add_proof_popover.open(
                parentView=sender.getNSButton().superview(),
                preferredEdge="right",
                relativeRect=button_frame,
            )
        except Exception as e:
            print(f"Error showing add proof popover: {e}")
            import traceback

            traceback.print_exc()

    def create_add_proof_popover(self):
        """Create the add proof popover."""
        self.add_proof_popover = vanilla.Popover((300, 100))
        popover = self.add_proof_popover

        # Title
        popover.titleLabel = vanilla.TextBox(
            (10, 10, -10, 20), "Select Proof Type to Add:"
        )

        # Proof type selector - get available proof types
        proof_type_options = [
            "Character Set Proof",
            "Spacing Proof",
            "Big Paragraph Proof",
            "Big Diacritics Proof",
            "Small Paragraph Proof",
            "Small Paired Styles Proof",
            "Small Wordsiv Proof",
            "Small Diacritics Proof",
            "Small Mixed Text Proof",
        ]

        # Add Arabic proof types if fonts support Arabic
        if self.parent_window.font_manager.has_arabic_support():
            proof_type_options.extend(
                [
                    "Arabic Contextual Forms",
                    "Big Arabic Text Proof",
                    "Big Farsi Text Proof",
                    "Small Arabic Text Proof",
                    "Small Farsi Text Proof",
                    "Arabic Vocalization Proof",
                    "Arabic-Latin Mixed Proof",
                    "Arabic Numbers Proof",
                ]
            )

        popover.proofTypePopup = vanilla.PopUpButton(
            (10, 35, -10, 20),
            proof_type_options,
        )

        # Add button
        popover.addButton = vanilla.Button(
            (10, 65, 120, 20),
            "Add",
            callback=self.addSelectedProofCallback,
        )

        # Cancel button
        popover.cancelButton = vanilla.Button(
            (-130, 65, 120, 20),
            "Cancel",
            callback=self.cancelAddProofCallback,
        )

    def addSelectedProofCallback(self, sender):
        """Handle adding the selected proof type."""
        try:
            # Get the selected proof type
            selected_idx = self.add_proof_popover.proofTypePopup.get()
            proof_type_options = self.add_proof_popover.proofTypePopup.getItems()

            if selected_idx < 0 or selected_idx >= len(proof_type_options):
                return

            selected_proof_type = proof_type_options[selected_idx]

            # Get current proof list
            current_proofs = list(self.group.proofOptionsList.get())

            # Check if this proof type already exists and generate unique name if needed
            unique_proof_name = self.generate_unique_proof_name(
                selected_proof_type, current_proofs
            )

            # Create new proof item
            new_proof_item = {
                "Option": unique_proof_name,
                "Enabled": False,  # Start disabled by default
                "_original_option": selected_proof_type,  # Keep track of the base type
            }

            # Add to the list
            current_proofs.append(new_proof_item)
            self.group.proofOptionsList.set(current_proofs)

            # Initialize settings for the new proof if it's a proof type with settings
            self.parent_window.initialize_settings_for_proof(
                unique_proof_name, selected_proof_type
            )

            # Update the proof order in settings
            new_order = [item["Option"] for item in current_proofs]
            self.settings.set_proof_order(new_order)
            self.settings.save()

            # Close the popover
            self.add_proof_popover.close()

            print(f"Added proof: {unique_proof_name}")

        except Exception as e:
            print(f"Error adding proof: {e}")
            import traceback

            traceback.print_exc()

    def cancelAddProofCallback(self, sender):
        """Handle canceling the add proof action."""
        self.add_proof_popover.close()

    def generate_unique_proof_name(self, base_proof_type, current_proofs):
        """Generate a unique proof name by adding a number suffix if needed."""
        existing_names = [item["Option"] for item in current_proofs]

        # If the base name doesn't exist, use it as-is
        if base_proof_type not in existing_names:
            return base_proof_type

        # Find the next available number
        counter = 2
        while True:
            candidate_name = f"{base_proof_type} {counter}"
            if candidate_name not in existing_names:
                return candidate_name
            counter += 1


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
            ("CharacterSetProof", "Character Set Proof"),
            ("SpacingProof", "Spacing Proof"),
            ("BigParagraphProof", "Big Paragraph Proof"),
            ("BigDiacriticsProof", "Big Diacritics Proof"),
            ("SmallParagraphProof", "Small Paragraph Proof"),
            ("SmallPairedStylesProof", "Small Paired Styles Proof"),
            ("SmallWordsivProof", "Small Wordsiv Proof"),
            ("SmallDiacriticsProof", "Small Diacritics Proof"),
            ("SmallMixedTextProof", "Small Mixed Text Proof"),
            ("ArabicContextualFormsProof", "Arabic Contextual Forms"),
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
            (1000, 700), WINDOW_TITLE, minSize=(1000, 700), closable=True
        )

        # Set the window close callback to handle the window close button
        self.w.bind("close", self.windowCloseCallback)
        self.w.bind("should close", self.windowShouldCloseCallback)

        # SegmentedButton for tab switching
        self.tabSwitcher = vanilla.SegmentedButton(
            (10, 10, 322, 24),
            segmentDescriptions=[
                dict(title="Files"),
                dict(title="Controls"),
            ],
            callback=self.switchTab,
        )

        # Create tab instances
        self.filesTab = FilesTab(self, self.font_manager)
        self.controlsTab = ControlsTab(self, self.settings)

        # Create preview components that will be integrated into Controls tab
        self.preview_components = self.create_preview_components()

        # Refresh proof options list after tabs are created
        if hasattr(self, "controlsTab") and self.controlsTab:
            self.controlsTab.refresh_proof_options_list()

        # --- Main Content Group (holds the two tab groups) ---
        self.mainContent = vanilla.Group((0, 44, -0, -0))
        self.mainContent.filesGroup = self.filesTab.group
        self.mainContent.controlsGroup = self.controlsTab.group
        self.filesTab.group.show(True)
        self.controlsTab.group.show(False)

        # Integrate preview into controls tab
        self.controlsTab.integrate_preview_view(self.preview_components["pdfView"])

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

    def get_proof_font_size(self, proof_identifier):
        """Get font size for a specific proof from its settings."""
        # Map display names to their corresponding settings keys
        display_name_to_settings_key = {
            "Character Set Proof": "CharacterSetProof",
            "Spacing Proof": "SpacingProof",
            "Big Paragraph Proof": "BigParagraphProof",
            "Big Diacritics Proof": "BigDiacriticsProof",
            "Small Paragraph Proof": "SmallParagraphProof",
            "Small Paired Styles Proof": "SmallPairedStylesProof",
            "Small Wordsiv Proof": "SmallWordsivProof",
            "Small Diacritics Proof": "SmallDiacriticsProof",
            "Small Mixed Text Proof": "SmallMixedTextProof",
            "Arabic Contextual Forms": "ArabicContextualFormsProof",
            "Big Arabic Text Proof": "BigArabicTextProof",
            "Big Farsi Text Proof": "BigFarsiTextProof",
            "Small Arabic Text Proof": "SmallArabicTextProof",
            "Small Farsi Text Proof": "SmallFarsiTextProof",
            "Arabic Vocalization Proof": "ArabicVocalizationProof",
            "Arabic-Latin Mixed Proof": "ArabicLatinMixedProof",
            "Arabic Numbers Proof": "ArabicNumbersProof",
        }

        # Determine if this is a direct match or a numbered variant
        proof_key = None
        if proof_identifier in display_name_to_settings_key:
            # Direct match - use original settings key
            proof_key = display_name_to_settings_key[proof_identifier]
            font_size_key = f"{proof_key}_fontSize"
        else:
            # This might be a numbered variant like "Character Set Proof 2"
            # Find the base proof type by checking if the identifier starts with any known proof type
            for display_name, settings_key in display_name_to_settings_key.items():
                if proof_identifier.startswith(display_name):
                    proof_key = settings_key
                    # For numbered variants, we use the unique identifier as the key
                    unique_key = proof_identifier.replace(" ", "_").replace("/", "_")
                    font_size_key = f"{unique_key}_fontSize"
                    break

            # Fallback if no match found
            if not proof_key:
                proof_key = "SmallParagraphProof"
                unique_key = proof_identifier.replace(" ", "_").replace("/", "_")
                font_size_key = f"{unique_key}_fontSize"

        # Set default font size based on proof type
        if proof_key in [
            "BigParagraphProof",
            "BigDiacriticsProof",
            "BigArabicTextProof",
            "BigFarsiTextProof",
        ]:
            default_font_size = largeTextFontSize
        elif proof_key in ["CharacterSetProof", "ArabicContextualFormsProof"]:
            default_font_size = charsetFontSize
        elif proof_key == "SpacingProof":
            default_font_size = spacingFontSize
        else:
            # Small proofs and other proofs
            default_font_size = smallTextFontSize

        return self.proof_settings.get(font_size_key, default_font_size)

    def save_all_settings(self):
        """Save all current settings to the settings file."""
        try:
            # Save proof options
            proof_options_items = self.controlsTab.group.proofOptionsList.get()
            for item in proof_options_items:
                proof_name = item[
                    "Option"
                ]  # Use the actual proof name (including numbers)
                base_option = item.get(
                    "_original_option", proof_name
                )  # Get original option name
                enabled = bool(item["Enabled"])

                if base_option == "Show Baselines/Grid":
                    self.settings.set_proof_option("showBaselines", enabled)
                else:
                    # For unique proof names, use a sanitized version as the key
                    unique_key = proof_name.replace(" ", "_").replace("/", "_")
                    self.settings.set_proof_option(unique_key, enabled)

            # Save proof-specific settings
            self.settings.set_proof_settings(self.proof_settings)

            # Save the settings file
            self.settings.save()

        except Exception as e:
            print(f"Error saving settings: {e}")
            import traceback

            traceback.print_exc()

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

                # Reset table columns to base columns only
                self.filesTab.reset_table_columns()

                # Refresh UI
                self.filesTab.update_table()

                # Update PDF location UI to reflect reset settings
                self.filesTab.update_pdf_location_ui()

                # Refresh controls tab with default values
                self.refresh_controls_tab()

                self.initialize_proof_settings()

                print("Settings reset to defaults.")

        except Exception as e:
            print(f"Error resetting settings: {e}")
            traceback.print_exc()

    def closeWindowCallback(self, sender):
        """Handle the Close Window button click."""
        self._perform_cleanup_and_exit()

    def windowCloseCallback(self, sender):
        """Handle the window close button (X) being pressed."""
        self._perform_cleanup_and_exit()

    def windowShouldCloseCallback(self, sender):
        """Handle the window should close event to ensure proper cleanup."""
        # Just allow the close, cleanup will be handled by windowCloseCallback
        return True

    def _perform_cleanup_and_exit(self):
        """Perform cleanup and exit the application."""
        # Prevent multiple calls to this method
        if hasattr(self, "_exiting"):
            return
        self._exiting = True

        try:
            # Try to save settings quickly without full validation
            if hasattr(self, "settings"):
                try:
                    self.settings.save()
                except:
                    pass  # Don't fail if settings can't be saved

            # Restore stdout and stderr
            try:
                if hasattr(self, "_original_stdout"):
                    sys.stdout = self._original_stdout
                if hasattr(self, "_original_stderr"):
                    sys.stderr = self._original_stderr
            except:
                pass

            # Stop the event loop
            try:
                AppHelper.stopEventLoop()
            except:
                pass

        except:
            pass  # Don't let any error prevent exit

        # Force exit the Python process
        import os

        os._exit(0)

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

                # Read proof options from list
                proof_options_items = controls.proofOptionsList.get()
                proof_options = {}

                # Read showBaselines from the standalone checkbox
                self.showBaselines = controls.showBaselinesCheckbox.get()
                db.showBaselines = self.showBaselines

                for item in proof_options_items:
                    option = item.get(
                        "_original_option", item["Option"]
                    )  # Get original option name
                    enabled = bool(item["Enabled"])

                    # For all proofs, use the actual option name as the key
                    # This handles both original proofs and numbered duplicates
                    proof_options[item["Option"]] = enabled

                # Build otfeatures dict from proof_settings
                otfeatures_by_proof = {}
                cols_by_proof = {}
                paras_by_proof = {}

                # Map display names to their corresponding settings keys
                display_name_to_settings_key = {
                    "Character Set Proof": "CharacterSetProof",
                    "Spacing Proof": "SpacingProof",
                    "Big Paragraph Proof": "BigParagraphProof",
                    "Big Diacritics Proof": "BigDiacriticsProof",
                    "Small Paragraph Proof": "SmallParagraphProof",
                    "Small Paired Styles Proof": "SmallPairedStylesProof",
                    "Small Wordsiv Proof": "SmallWordsivProof",
                    "Small Diacritics Proof": "SmallDiacriticsProof",
                    "Small Mixed Text Proof": "SmallMixedTextProof",
                    "Arabic Contextual Forms": "ArabicContextualFormsProof",
                    "Big Arabic Text Proof": "BigArabicTextProof",
                    "Big Farsi Text Proof": "BigFarsiTextProof",
                    "Small Arabic Text Proof": "SmallArabicTextProof",
                    "Small Farsi Text Proof": "SmallFarsiTextProof",
                    "Arabic Vocalization Proof": "ArabicVocalizationProof",
                    "Arabic-Latin Mixed Proof": "ArabicLatinMixedProof",
                    "Arabic Numbers Proof": "ArabicNumbersProof",
                }

                # Process settings for both old-style and new unique proof identifiers
                for item in proof_options_items:
                    if not item["Enabled"]:
                        continue

                    proof_name = item["Option"]

                    # Always use the unique identifier for settings keys to ensure consistency
                    # This handles both original proofs and numbered duplicates uniformly
                    unique_key = proof_name.replace(" ", "_").replace("/", "_")

                    # Determine the base proof type for validation
                    settings_key = None
                    for (
                        display_name,
                        base_settings_key,
                    ) in display_name_to_settings_key.items():
                        if proof_name.startswith(display_name):
                            settings_key = base_settings_key
                            break

                    # Fallback if no base type found
                    if not settings_key:
                        settings_key = "SmallParagraphProof"

                    # Always use unique identifier for all settings keys
                    cols_key = f"{unique_key}_cols"
                    para_key = f"{unique_key}_para"
                    otf_prefix = f"otf_{unique_key}_"

                    # Get columns setting
                    if cols_key in self.proof_settings:
                        cols_by_proof[proof_name] = self.proof_settings[cols_key]

                    # Get paragraphs setting (only for Wordsiv proofs)
                    if "Wordsiv" in proof_name:
                        if para_key in self.proof_settings:
                            paras_by_proof[proof_name] = self.proof_settings[para_key]

                    # Get OpenType features
                    otf_dict = {}
                    otf_search_prefix = f"otf_{unique_key if proof_name not in display_name_to_settings_key else settings_key}_"
                    for key, value in self.proof_settings.items():
                        if key.startswith(otf_prefix):
                            feature = key.replace(otf_prefix, "")
                            otf_dict[feature] = bool(value)
                    otfeatures_by_proof[proof_name] = otf_dict

                # Generate proof
                output_path = self.run_proof(
                    userAxesValues,
                    proof_options,
                    otfeatures_by_proof,
                    cols_by_proof=cols_by_proof,
                    paras_by_proof=paras_by_proof,
                )

                # Display the generated PDF
                if self.display_pdf(output_path):
                    self.tabSwitcher.set(
                        1
                    )  # Switch to Controls tab (which now has preview)
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
            # Character Set and Arabic Contextual Forms don't use columns
            if proof_key not in ["CharacterSetProof", "ArabicContextualFormsProof"]:
                # Big proofs, Big Diacritics, and Big Arabic/Farsi proofs use 1 column
                if proof_key in [
                    "BigParagraphProof",
                    "BigDiacriticsProof",
                    "BigArabicTextProof",
                    "BigFarsiTextProof",
                ]:
                    default_cols = 1
                else:
                    default_cols = 2

                if cols_key not in self.proof_settings:
                    self.proof_settings[cols_key] = default_cols

            # Font size settings for all proofs
            font_size_key = f"{proof_key}_fontSize"
            # Set default font size based on proof type
            if proof_key in [
                "BigParagraphProof",
                "BigDiacriticsProof",
                "BigArabicTextProof",
                "BigFarsiTextProof",
            ]:
                default_font_size = largeTextFontSize
            elif proof_key in ["CharacterSetProof", "ArabicContextualFormsProof"]:
                default_font_size = charsetFontSize
            elif proof_key == "SpacingProof":
                default_font_size = spacingFontSize
            else:
                # Small proofs and other proofs
                default_font_size = smallTextFontSize

            if font_size_key not in self.proof_settings:
                self.proof_settings[font_size_key] = default_font_size

            # Paragraph settings (only for SmallWordsivProof)
            if proof_key == "SmallWordsivProof":
                para_key = f"{proof_key}_para"
                if para_key not in self.proof_settings:
                    self.proof_settings[para_key] = 5

            # Text formatting settings for supported proof types
            supported_formatting_proofs = {
                "BigParagraphProof",
                "BigDiacriticsProof",
                "SmallParagraphProof",
                "SmallPairedStylesProof",
                "SmallWordsivProof",
                "SmallDiacriticsProof",
                "SmallMixedTextProof",
                "BigArabicTextProof",
                "BigFarsiTextProof",
                "SmallArabicTextProof",
                "SmallFarsiTextProof",
                "ArabicVocalizationProof",
                "ArabicLatinMixedProof",
                "ArabicNumbersProof",
            }

            if proof_key in supported_formatting_proofs:
                # Tracking setting (default 0)
                tracking_key = f"{proof_key}_tracking"
                if tracking_key not in self.proof_settings:
                    self.proof_settings[tracking_key] = 0

                # Align setting (default "left")
                align_key = f"{proof_key}_align"
                if align_key not in self.proof_settings:
                    self.proof_settings[align_key] = "left"

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

        # Refresh proof options list to show/hide Arabic proofs based on loaded fonts
        if hasattr(self, "controlsTab") and self.controlsTab:
            self.controlsTab.refresh_proof_options_list()

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
            "Character Set Proof": "CharacterSetProof",
            "Spacing Proof": "SpacingProof",
            "Big Paragraph Proof": "BigParagraphProof",
            "Big Diacritics Proof": "BigDiacriticsProof",
            "Small Paragraph Proof": "SmallParagraphProof",
            "Small Paired Styles Proof": "SmallPairedStylesProof",
            "Small Wordsiv Proof": "SmallWordsivProof",
            "Small Diacritics Proof": "SmallDiacriticsProof",
            "Small Mixed Text Proof": "SmallMixedTextProof",
            "Arabic Contextual Forms": "ArabicContextualFormsProof",
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
        self.proof_settings_popover = vanilla.Popover((400, 520))
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

        # Numeric settings list (now includes tracking)
        popover.numericLabel = vanilla.TextBox((10, 70, -10, 20), "Settings:")
        popover.numericList = vanilla.List2(
            (10, 95, -10, 140),
            [],
            columnDescriptions=[
                {
                    "identifier": "Setting",
                    "title": "Setting",
                    "key": "Setting",
                    "width": 150,
                    "editable": False,
                },
                {
                    "identifier": "Value",
                    "title": "Value",
                    "key": "Value",
                    "width": 100,
                    "editable": True,
                },
            ],
            editCallback=self.numericSettingsEditCallback,
        )

        # Align control (standalone)
        popover.alignLabel = vanilla.TextBox((10, 245, 100, 20), "Alignment:")
        popover.alignPopUp = vanilla.PopUpButton(
            (120, 245, 100, 20),
            ["left", "center", "right"],
            callback=self.alignPopUpCallback,
        )

        # OpenType features list
        popover.featuresLabel = vanilla.TextBox(
            (10, 275, -10, 20), "OpenType Features:"
        )
        popover.featuresList = vanilla.List2(
            (10, 300, -10, -10),
            [],
            columnDescriptions=[
                {
                    "identifier": "Feature",
                    "title": "Feature",
                    "key": "Feature",
                    "width": 150,
                    "editable": False,
                },
                {
                    "identifier": "Enabled",
                    "title": "Enabled",
                    "key": "Enabled",
                    "width": 80,
                    "editable": True,
                    "cellClass": vanilla.CheckBoxList2Cell,
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

        # Font size setting for all proofs (always first)
        font_size_key = f"{proof_key}_fontSize"
        # Set default font size based on proof type
        if proof_key in [
            "BigParagraphProof",
            "BigDiacriticsProof",
            "BigArabicTextProof",
            "BigFarsiTextProof",
        ]:
            default_font_size = largeTextFontSize
        elif proof_key in ["CharacterSetProof", "ArabicContextualFormsProof"]:
            default_font_size = charsetFontSize
        elif proof_key == "SpacingProof":
            default_font_size = spacingFontSize
        else:
            # Small proofs and other proofs
            default_font_size = smallTextFontSize

        font_size_value = self.proof_settings.get(font_size_key, default_font_size)
        numeric_items.append(
            {"Setting": "Font Size", "Value": font_size_value, "_key": font_size_key}
        )

        # Columns setting with appropriate defaults (skip for certain proofs)
        if proof_key not in ["CharacterSetProof", "ArabicContextualFormsProof"]:
            cols_key = f"{proof_key}_cols"
            # Big proofs, Big Arabic/Farsi proofs, and Big Diacritics default to 1 column

            if proof_key in [
                "BigParagraphProof",
                "BigDiacriticsProof",
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
        if proof_key == "SmallWordsivProof":
            para_key = f"{proof_key}_para"
            para_value = self.proof_settings.get(para_key, 5)
            numeric_items.append(
                {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
            )

        # Add tracking for supported proof types
        supported_formatting_proofs = {
            "BigParagraphProof",
            "BigDiacriticsProof",
            "SmallParagraphProof",
            "SmallPairedStylesProof",
            "SmallWordsivProof",
            "SmallDiacriticsProof",
            "SmallMixedTextProof",
            "BigArabicTextProof",
            "BigFarsiTextProof",
            "SmallArabicTextProof",
            "SmallFarsiTextProof",
            "ArabicVocalizationProof",
            "ArabicLatinMixedProof",
            "ArabicNumbersProof",
        }

        if proof_key in supported_formatting_proofs:
            tracking_key = f"{proof_key}_tracking"
            tracking_value = self.proof_settings.get(tracking_key, 0)
            numeric_items.append(
                {"Setting": "Tracking", "Value": tracking_value, "_key": tracking_key}
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

            # Special handling for SpacingProof kern feature
            if proof_key == "SpacingProof" and tag == "kern":
                feature_value = False
                self.proof_settings[feature_key] = False
                feature_items.append(
                    {
                        "Feature": f"{tag} (always off)",
                        "Enabled": feature_value,
                        "_key": feature_key,
                        "_readonly": True,
                    }
                )
            else:
                default_value = tag in self.default_on_features
                feature_value = self.proof_settings.get(feature_key, default_value)
                feature_items.append(
                    {"Feature": tag, "Enabled": feature_value, "_key": feature_key}
                )

        popover.featuresList.set(feature_items)

        # Update alignment control for supported proof types
        if proof_key in supported_formatting_proofs:
            # Update align control
            align_key = f"{proof_key}_align"
            align_value = self.proof_settings.get(align_key, "left")
            align_options = ["left", "center", "right"]
            if align_value in align_options:
                popover.alignPopUp.set(align_options.index(align_value))
            else:
                popover.alignPopUp.set(0)  # Default to "left"

            # Show alignment control
            popover.alignLabel.show(True)
            popover.alignPopUp.show(True)
        else:
            # Hide alignment control for unsupported proof types
            popover.alignLabel.show(False)
            popover.alignPopUp.show(False)

    def alignPopUpCallback(self, sender):
        """Handle alignment selection changes."""
        if not hasattr(self, "current_proof_key"):
            return

        selected_idx = sender.get()
        align_options = ["left", "center", "right"]
        if 0 <= selected_idx < len(align_options):
            align_value = align_options[selected_idx]
            align_key = f"{self.current_proof_key}_align"
            self.proof_settings[align_key] = align_value

    def numericSettingsEditCallback(self, sender):
        """Handle edits to numeric settings in popover."""
        items = sender.get()
        for item in items:
            if "_key" in item:
                key = item["_key"]
                value = item["Value"]
                try:
                    # Handle tracking values (can be float) vs other settings (must be positive int)
                    if "_tracking" in key:
                        value = float(value)
                        self.proof_settings[key] = value
                    else:
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

                # Prevent editing kern feature for SpacingProof
                if item.get("_readonly", False):
                    # Reset to disabled if someone tries to change it
                    if enabled:
                        item["Enabled"] = False
                        sender.set(items)
                    continue

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

            # Dynamic proof generation based on UI list order
            # Get the current proof options from the UI in their display order
            controls = self.controlsTab
            if hasattr(controls, "group") and hasattr(
                controls.group, "proofOptionsList"
            ):
                proof_options_items = controls.group.proofOptionsList.get()

                for item in proof_options_items:
                    proof_name = item[
                        "Option"
                    ]  # Use the actual proof name (may include numbers)
                    base_proof_type = item.get(
                        "_original_option", proof_name
                    )  # Get the base type
                    enabled = bool(item["Enabled"])

                    if not enabled:
                        continue  # Skip disabled proofs

                    # Generate each enabled proof using the unique proof name as identifier
                    if base_proof_type == "Character Set Proof":
                        charset_font_size = self.get_proof_font_size(proof_name)
                        charsetProof(
                            fullCharacterSet,
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            otfeatures_by_proof.get(proof_name, {}),
                            charset_font_size,
                        )
                    elif base_proof_type == "Spacing Proof":
                        spacing_font_size = self.get_proof_font_size(proof_name)
                        spacing_columns = cols_by_proof.get(proof_name, 2)
                        spacingProof(
                            fullCharacterSet,
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            otfeatures_by_proof.get(proof_name, {}),
                            spacing_font_size,
                            spacing_columns,
                        )
                    elif base_proof_type == "Big Paragraph Proof":
                        big_paragraph_font_size = self.get_proof_font_size(proof_name)
                        big_paragraph_columns = cols_by_proof.get(proof_name, 1)

                        # Get text formatting settings
                        unique_proof_key = proof_name.replace(" ", "_").replace(
                            "/", "_"
                        )
                        tracking_value = self.proof_settings.get(
                            f"{unique_proof_key}_tracking", 0
                        )
                        align_value = self.proof_settings.get(
                            f"{unique_proof_key}_align", "left"
                        )

                        textProof(
                            cat["uniLu"] + cat["uniLl"],
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            big_paragraph_columns,
                            2,
                            False,
                            big_paragraph_font_size,
                            f"Big size proof - {proof_name}",
                            False,  # mixedStyles=False
                            False,  # forceWordsiv
                            None,  # injectText
                            otfeatures_by_proof.get(proof_name, {}),
                            0,
                            cat,
                            fullCharacterSet,
                            None,  # lang
                            tracking_value,
                            align_value,
                        )
                    elif base_proof_type == "Big Diacritics Proof":
                        big_diacritics_font_size = self.get_proof_font_size(proof_name)

                        # Get text formatting settings
                        unique_proof_key = proof_name.replace(" ", "_").replace(
                            "/", "_"
                        )
                        tracking_value = self.proof_settings.get(
                            f"{unique_proof_key}_tracking", 0
                        )
                        align_value = self.proof_settings.get(
                            f"{unique_proof_key}_align", "left"
                        )

                        textProof(
                            cat["accented_plus"],
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            cols_by_proof.get(proof_name, 1),
                            3,
                            False,
                            big_diacritics_font_size,
                            f"Big size accented proof - {proof_name}",
                            False,  # mixedStyles=False
                            False,  # forceWordsiv
                            None,  # injectText
                            otfeatures_by_proof.get(proof_name, {}),
                            3,
                            cat,
                            fullCharacterSet,
                            None,  # lang
                            tracking_value,
                            align_value,
                        )
                    elif base_proof_type == "Small Paragraph Proof":
                        small_paragraph_font_size = self.get_proof_font_size(proof_name)

                        # Get text formatting settings
                        unique_proof_key = proof_name.replace(" ", "_").replace(
                            "/", "_"
                        )
                        tracking_value = self.proof_settings.get(
                            f"{unique_proof_key}_tracking", 0
                        )
                        align_value = self.proof_settings.get(
                            f"{unique_proof_key}_align", "left"
                        )

                        textProof(
                            cat["uniLu"] + cat["uniLl"],
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            cols_by_proof.get(proof_name, 2),
                            5,
                            False,
                            small_paragraph_font_size,
                            f"Small size proof - {proof_name}",
                            False,  # mixedStyles=False
                            False,  # forceWordsiv
                            None,  # injectText
                            otfeatures_by_proof.get(proof_name, {}),
                            0,
                            cat,
                            fullCharacterSet,
                            None,  # lang
                            tracking_value,
                            align_value,
                        )
                    elif base_proof_type == "Small Paired Styles Proof":
                        small_paired_styles_font_size = self.get_proof_font_size(
                            proof_name
                        )

                        # Get text formatting settings
                        unique_proof_key = proof_name.replace(" ", "_").replace(
                            "/", "_"
                        )
                        tracking_value = self.proof_settings.get(
                            f"{unique_proof_key}_tracking", 0
                        )
                        align_value = self.proof_settings.get(
                            f"{unique_proof_key}_align", "left"
                        )

                        textProof(
                            cat["uniLu"] + cat["uniLl"],
                            axesProduct,
                            indFont,
                            pairedStaticStyles,
                            cols_by_proof.get(proof_name, 2),
                            5,
                            False,
                            small_paired_styles_font_size,
                            f"Small size paired styles proof - {proof_name}",
                            True,  # mixedStyles=True for SmallPairedStylesProof
                            True,  # forceWordsiv
                            None,  # injectText
                            otfeatures_by_proof.get(proof_name, {}),
                            0,
                            cat,
                            fullCharacterSet,
                            None,  # lang
                            tracking_value,
                            align_value,
                        )
                    elif base_proof_type == "Small Wordsiv Proof":
                        small_wordsiv_font_size = self.get_proof_font_size(proof_name)

                        # Get text formatting settings
                        unique_proof_key = proof_name.replace(" ", "_").replace(
                            "/", "_"
                        )
                        tracking_value = self.proof_settings.get(
                            f"{unique_proof_key}_tracking", 0
                        )
                        align_value = self.proof_settings.get(
                            f"{unique_proof_key}_align", "left"
                        )

                        textProof(
                            cat["uniLu"] + cat["uniLl"],
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            cols_by_proof.get(proof_name, 2),
                            paras_by_proof.get(proof_name, 5),
                            False,
                            small_wordsiv_font_size,
                            f"Small size proof mixed - {proof_name}",
                            False,  # mixedStyles=False
                            True,  # forceWordsiv
                            None,  # injectText
                            otfeatures_by_proof.get(proof_name, {}),
                            0,
                            cat,
                            fullCharacterSet,
                            None,  # lang
                            tracking_value,
                            align_value,
                        )
                    elif base_proof_type == "Small Diacritics Proof":
                        small_diacritics_font_size = self.get_proof_font_size(
                            proof_name
                        )

                        # Get text formatting settings
                        unique_proof_key = proof_name.replace(" ", "_").replace(
                            "/", "_"
                        )
                        tracking_value = self.proof_settings.get(
                            f"{unique_proof_key}_tracking", 0
                        )
                        align_value = self.proof_settings.get(
                            f"{unique_proof_key}_align", "left"
                        )

                        textProof(
                            cat["accented_plus"],
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            cols_by_proof.get(proof_name, 2),
                            4,
                            False,
                            small_diacritics_font_size,
                            f"Small size accented proof - {proof_name}",
                            False,  # mixedStyles=False
                            False,  # forceWordsiv
                            None,  # injectText
                            otfeatures_by_proof.get(proof_name, {}),
                            4,
                            cat,
                            fullCharacterSet,
                            None,  # lang
                            tracking_value,
                            align_value,
                        )
                    elif base_proof_type == "Small Mixed Text Proof":
                        small_mixed_text_font_size = self.get_proof_font_size(
                            proof_name
                        )

                        # Get text formatting settings
                        unique_proof_key = proof_name.replace(" ", "_").replace(
                            "/", "_"
                        )
                        tracking_value = self.proof_settings.get(
                            f"{unique_proof_key}_tracking", 0
                        )
                        align_value = self.proof_settings.get(
                            f"{unique_proof_key}_align", "left"
                        )

                        textProof(
                            cat["uniLu"] + cat["uniLl"],
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            cols_by_proof.get(proof_name, 2),
                            5,
                            False,
                            small_mixed_text_font_size,
                            f"Small size misc proof - {proof_name}",
                            False,  # mixedStyles=False
                            False,  # forceWordsiv
                            (  # injectText
                                pte.bigRandomNumbers if pte else "",
                                pte.additionalSmallText if pte else "",
                            ),
                            otfeatures_by_proof.get(proof_name, {}),
                            0,
                            cat,
                            fullCharacterSet,
                            None,  # lang
                            tracking_value,
                            align_value,
                        )
                    elif base_proof_type == "Arabic Contextual Forms":
                        arabic_contextual_forms_font_size = self.get_proof_font_size(
                            "ArabicContextualFormsProof"
                        )
                        arabicContextualFormsProof(
                            cat,
                            axesProduct,
                            indFont,
                            None,  # pairedStaticStyles
                            otfeatures_by_proof.get("ArabicContextualFormsProof", {}),
                            arabic_contextual_forms_font_size,
                        )
                    elif base_proof_type == "Big Arabic Text Proof":
                        big_arabic_font_size = self.get_proof_font_size(proof_name)
                        arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                        if arabic_chars:
                            # Get text formatting settings
                            unique_proof_key = proof_name.replace(" ", "_").replace(
                                "/", "_"
                            )
                            tracking_value = self.proof_settings.get(
                                f"{unique_proof_key}_tracking", 0
                            )
                            align_value = self.proof_settings.get(
                                f"{unique_proof_key}_align", "left"
                            )

                            textProof(
                                arabic_chars,
                                axesProduct,
                                indFont,
                                None,  # pairedStaticStyles
                                cols_by_proof.get(proof_name, 1),
                                2,  # Fixed paragraph count for big text
                                False,
                                big_arabic_font_size,
                                f"Big Arabic text proof - {proof_name}",
                                False,  # mixedStyles=False
                                False,  # forceWordsiv
                                None,  # injectText
                                otfeatures_by_proof.get(proof_name, {}),
                                0,
                                cat,
                                fullCharacterSet,
                                "ar",
                                tracking_value,
                                align_value,
                            )
                    elif base_proof_type == "Big Farsi Text Proof":
                        big_farsi_font_size = self.get_proof_font_size(proof_name)
                        farsi_chars = cat.get("fa", "") or cat.get("arab", "")
                        if farsi_chars:
                            # Get text formatting settings
                            unique_proof_key = proof_name.replace(" ", "_").replace(
                                "/", "_"
                            )
                            tracking_value = self.proof_settings.get(
                                f"{unique_proof_key}_tracking", 0
                            )
                            align_value = self.proof_settings.get(
                                f"{unique_proof_key}_align", "left"
                            )

                            textProof(
                                farsi_chars,
                                axesProduct,
                                indFont,
                                None,  # pairedStaticStyles
                                cols_by_proof.get(proof_name, 1),
                                2,  # Fixed paragraph count for big text
                                False,
                                big_farsi_font_size,
                                f"Big Farsi text proof - {proof_name}",
                                False,  # mixedStyles=False
                                False,  # forceWordsiv
                                None,  # injectText
                                otfeatures_by_proof.get(proof_name, {}),
                                0,
                                cat,
                                fullCharacterSet,
                                "fa",
                                tracking_value,
                                align_value,
                            )
                    elif base_proof_type == "Small Arabic Text Proof":
                        small_arabic_font_size = self.get_proof_font_size(proof_name)
                        arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                        if arabic_chars:
                            # Get text formatting settings
                            unique_proof_key = proof_name.replace(" ", "_").replace(
                                "/", "_"
                            )
                            tracking_value = self.proof_settings.get(
                                f"{unique_proof_key}_tracking", 0
                            )
                            align_value = self.proof_settings.get(
                                f"{unique_proof_key}_align", "left"
                            )

                            textProof(
                                arabic_chars,
                                axesProduct,
                                indFont,
                                None,  # pairedStaticStyles
                                cols_by_proof.get(proof_name, 2),
                                5,  # Standard paragraph count for small text
                                False,
                                small_arabic_font_size,
                                f"Small Arabic text proof - {proof_name}",
                                False,  # mixedStyles=False
                                False,  # forceWordsiv
                                None,  # injectText
                                otfeatures_by_proof.get(proof_name, {}),
                                0,
                                cat,
                                fullCharacterSet,
                                "ar",
                                tracking_value,
                                align_value,
                            )
                    elif base_proof_type == "Small Farsi Text Proof":
                        small_farsi_font_size = self.get_proof_font_size(proof_name)
                        farsi_chars = cat.get("fa", "") or cat.get("arab", "")
                        if farsi_chars:
                            # Get text formatting settings
                            unique_proof_key = proof_name.replace(" ", "_").replace(
                                "/", "_"
                            )
                            tracking_value = self.proof_settings.get(
                                f"{unique_proof_key}_tracking", 0
                            )
                            align_value = self.proof_settings.get(
                                f"{unique_proof_key}_align", "left"
                            )

                            textProof(
                                farsi_chars,
                                axesProduct,
                                indFont,
                                None,  # pairedStaticStyles
                                cols_by_proof.get(proof_name, 2),
                                5,  # Standard paragraph count for small text
                                False,
                                small_farsi_font_size,
                                f"Small Farsi text proof - {proof_name}",
                                False,  # mixedStyles=False
                                False,  # forceWordsiv
                                None,  # injectText
                                otfeatures_by_proof.get(proof_name, {}),
                                0,
                                cat,
                                fullCharacterSet,
                                "fa",
                                tracking_value,
                                align_value,
                            )
                    elif base_proof_type == "Arabic Vocalization Proof":
                        arabic_vocab_font_size = self.get_proof_font_size(proof_name)
                        arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                        if arabic_chars:
                            # Get text formatting settings
                            unique_proof_key = proof_name.replace(" ", "_").replace(
                                "/", "_"
                            )
                            tracking_value = self.proof_settings.get(
                                f"{unique_proof_key}_tracking", 0
                            )
                            align_value = self.proof_settings.get(
                                f"{unique_proof_key}_align", "left"
                            )

                            textProof(
                                arabic_chars,
                                axesProduct,
                                indFont,
                                None,  # pairedStaticStyles
                                cols_by_proof.get(proof_name, 2),
                                3,  # Specific paragraph count for vocalization
                                False,
                                arabic_vocab_font_size,
                                f"Arabic vocalization proof - {proof_name}",
                                False,  # mixedStyles=False
                                False,  # forceWordsiv
                                (arabicVocalization,),  # injectText
                                otfeatures_by_proof.get(proof_name, {}),
                                0,
                                cat,
                                fullCharacterSet,
                                "ar",
                                tracking_value,
                                align_value,
                            )
                    elif base_proof_type == "Arabic-Latin Mixed Proof":
                        arabic_latin_font_size = self.get_proof_font_size(proof_name)
                        arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                        if arabic_chars:
                            # Get text formatting settings
                            unique_proof_key = proof_name.replace(" ", "_").replace(
                                "/", "_"
                            )
                            tracking_value = self.proof_settings.get(
                                f"{unique_proof_key}_tracking", 0
                            )
                            align_value = self.proof_settings.get(
                                f"{unique_proof_key}_align", "left"
                            )

                            textProof(
                                arabic_chars,
                                axesProduct,
                                indFont,
                                None,  # pairedStaticStyles
                                cols_by_proof.get(proof_name, 2),
                                3,  # Specific paragraph count for mixed text
                                False,
                                arabic_latin_font_size,
                                f"Arabic-Latin mixed proof - {proof_name}",
                                False,  # mixedStyles=False
                                False,  # forceWordsiv
                                (arabicLatinMixed,),  # injectText
                                otfeatures_by_proof.get(proof_name, {}),
                                0,
                                cat,
                                fullCharacterSet,
                                "ar",
                                tracking_value,
                                align_value,
                            )
                    elif base_proof_type == "Arabic Numbers Proof":
                        arabic_numbers_font_size = self.get_proof_font_size(proof_name)
                        arabic_chars = cat.get("ar", "") or cat.get("arab", "")
                        if arabic_chars:
                            # Get text formatting settings
                            unique_proof_key = proof_name.replace(" ", "_").replace(
                                "/", "_"
                            )
                            tracking_value = self.proof_settings.get(
                                f"{unique_proof_key}_tracking", 0
                            )
                            align_value = self.proof_settings.get(
                                f"{unique_proof_key}_align", "left"
                            )

                            textProof(
                                arabic_chars,
                                axesProduct,
                                indFont,
                                None,  # pairedStaticStyles
                                cols_by_proof.get(proof_name, 2),
                                3,  # Specific paragraph count for numbers
                                False,
                                arabic_numbers_font_size,
                                f"Arabic numbers proof - {proof_name}",
                                False,  # mixedStyles=False
                                False,  # forceWordsiv
                                (arabicFarsiUrduNumbers,),  # injectText
                                otfeatures_by_proof.get(proof_name, {}),
                                0,
                                cat,
                                fullCharacterSet,
                                "ar",
                                tracking_value,
                                align_value,
                            )
            else:
                # Fallback to old hardcoded order if UI list is not available
                print(
                    "Warning: Could not access proof options list, using fallback order"
                )

                # Generate proofs in default order using proof_options dict
                if proof_options.get("CharacterSetProof"):
                    charset_font_size = self.get_proof_font_size("CharacterSetProof")
                    charsetProof(
                        fullCharacterSet,
                        axesProduct,
                        indFont,
                        None,  # pairedStaticStyles
                        otfeatures_by_proof.get("CharacterSetProof", {}),
                        charset_font_size,
                    )

                if proof_options.get("SpacingProof"):
                    spacing_font_size = self.get_proof_font_size("SpacingProof")
                    spacing_columns = cols_by_proof.get("SpacingProof", 2)
                    spacingProof(
                        fullCharacterSet,
                        axesProduct,
                        indFont,
                        None,  # pairedStaticStyles
                        otfeatures_by_proof.get("SpacingProof", {}),
                        spacing_font_size,
                        spacing_columns,
                    )

                # Add other proofs in the same pattern if needed...
                # (This is a simplified fallback - the main path uses the UI order)

        db.endDrawing()
        # Save the proof doc
        try:
            if self.font_manager.fonts:
                first_font_path = self.font_manager.fonts[0]
                family_name = os.path.splitext(os.path.basename(first_font_path))[
                    0
                ].split("-")[0]

                # Check if user wants to use custom PDF output location
                # Ensure pdf_output key exists with defaults
                if "pdf_output" not in self.settings.data:
                    self.settings.data["pdf_output"] = {
                        "use_custom_location": False,
                        "custom_location": "",
                    }

                use_custom = self.settings.data["pdf_output"].get(
                    "use_custom_location", False
                )
                custom_location = self.settings.data["pdf_output"].get(
                    "custom_location", ""
                )

                if use_custom and custom_location and os.path.exists(custom_location):
                    # Use custom location
                    pdf_directory = custom_location
                else:
                    # Use default: first font's directory
                    pdf_directory = os.path.dirname(first_font_path)
            else:
                # Fallback to script directory if no fonts loaded
                pdf_directory = SCRIPT_DIR
                family_name = "proof"

            proofPath = os.path.join(
                pdf_directory, f"{nowformat}_{family_name}-proof.pdf"
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
            # Use the dynamic proof options list
            self.controlsTab.refresh_proof_options_list()

        except Exception as e:
            print(f"Error refreshing controls tab: {e}")
            import traceback

            traceback.print_exc()

    def create_preview_components(self):
        """Create preview components that will be integrated into Controls tab."""
        components = {}

        # Create PDFView for preview
        pdfView = PDFKit.PDFView.alloc().initWithFrame_(((0, 0), (100, 100)))
        pdfView.setAutoresizingMask_(1 << 1 | 1 << 4)
        pdfView.setAutoScales_(True)
        pdfView.setDisplaysPageBreaks_(True)
        pdfView.setDisplayMode_(1)
        pdfView.setDisplayBox_(0)

        components["pdfView"] = pdfView
        return components

    def display_pdf(self, pdf_path):
        """Display a PDF in the preview."""
        if pdf_path and os.path.exists(pdf_path):
            pdfDoc = PDFKit.PDFDocument.alloc().initWithURL_(
                AppKit.NSURL.fileURLWithPath_(pdf_path)
            )
            self.preview_components["pdfView"].setDocument_(pdfDoc)
            return True
        return False

    def initialize_settings_for_proof(self, unique_proof_name, base_proof_type):
        """Initialize settings for a newly added proof instance."""
        try:
            # Map proof display names to internal keys
            proof_name_to_key = {
                "Show Baselines/Grid": "showBaselines",
                "Character Set Proof": "CharacterSetProof",
                "Spacing Proof": "SpacingProof",
                "Big Paragraph Proof": "BigParagraphProof",
                "Big Diacritics Proof": "BigDiacriticsProof",
                "Small Paragraph Proof": "SmallParagraphProof",
                "Small Paired Styles Proof": "SmallPairedStylesProof",
                "Small Wordsiv Proof": "SmallWordsivProof",
                "Small Diacritics Proof": "SmallDiacriticsProof",
                "Small Mixed Text Proof": "SmallMixedTextProof",
                "Arabic Contextual Forms": "ArabicContextualFormsProof",
                "Big Arabic Text Proof": "BigArabicTextProof",
                "Big Farsi Text Proof": "BigFarsiTextProof",
                "Small Arabic Text Proof": "SmallArabicTextProof",
                "Small Farsi Text Proof": "SmallFarsiTextProof",
                "Arabic Vocalization Proof": "ArabicVocalizationProof",
                "Arabic-Latin Mixed Proof": "ArabicLatinMixedProof",
                "Arabic Numbers Proof": "ArabicNumbersProof",
            }

            # Skip if this is just "Show Baselines/Grid" - it doesn't need special settings
            if base_proof_type == "Show Baselines/Grid":
                return

            base_proof_key = proof_name_to_key.get(base_proof_type)
            if not base_proof_key:
                return

            # Create a unique identifier for this proof instance by sanitizing the unique name
            unique_key = unique_proof_name.replace(" ", "_").replace("/", "_")

            # Initialize settings with defaults based on the base proof type
            # Font size setting
            font_size_key = f"{unique_key}_fontSize"
            if base_proof_key in [
                "BigParagraphProof",
                "BigDiacriticsProof",
                "BigArabicTextProof",
                "BigFarsiTextProof",
            ]:
                default_font_size = largeTextFontSize
            elif base_proof_key in ["CharacterSetProof", "ArabicContextualFormsProof"]:
                default_font_size = charsetFontSize
            elif base_proof_key == "SpacingProof":
                default_font_size = spacingFontSize
            else:
                default_font_size = smallTextFontSize

            self.proof_settings[font_size_key] = default_font_size

            # Columns setting (if applicable)
            if base_proof_key not in [
                "CharacterSetProof",
                "ArabicContextualFormsProof",
            ]:
                cols_key = f"{unique_key}_cols"
                if base_proof_key in [
                    "BigParagraphProof",
                    "BigDiacriticsProof",
                    "BigArabicTextProof",
                    "BigFarsiTextProof",
                ]:
                    default_cols = 1
                else:
                    default_cols = 2
                self.proof_settings[cols_key] = default_cols

            # Paragraphs setting (only for SmallWordsivProof)
            if base_proof_key == "SmallWordsivProof":
                para_key = f"{unique_key}_para"
                self.proof_settings[para_key] = 5

            # Text formatting settings for supported proof types
            supported_formatting_proofs = {
                "BigParagraphProof",
                "BigDiacriticsProof",
                "SmallParagraphProof",
                "SmallPairedStylesProof",
                "SmallWordsivProof",
                "SmallDiacriticsProof",
                "SmallMixedTextProof",
                "BigArabicTextProof",
                "BigFarsiTextProof",
                "SmallArabicTextProof",
                "SmallFarsiTextProof",
                "ArabicVocalizationProof",
                "ArabicLatinMixedProof",
                "ArabicNumbersProof",
            }

            if base_proof_key in supported_formatting_proofs:
                # Tracking setting (default 0)
                tracking_key = f"{unique_key}_tracking"
                self.proof_settings[tracking_key] = 0

                # Align setting (default "left")
                align_key = f"{unique_key}_align"
                self.proof_settings[align_key] = "left"

            # OpenType features
            if self.font_manager.fonts:
                try:
                    feature_tags = db.listOpenTypeFeatures(self.font_manager.fonts[0])
                except Exception:
                    feature_tags = []

                for tag in feature_tags:
                    feature_key = f"otf_{unique_key}_{tag}"
                    default_value = tag in self.default_on_features
                    self.proof_settings[feature_key] = default_value

        except Exception as e:
            print(f"Error initializing settings for proof {unique_proof_name}: {e}")
            import traceback

            traceback.print_exc()

    def update_proof_settings_popover_for_instance(
        self, unique_proof_key, base_proof_type
    ):
        """Update the proof settings popover for a specific proof instance."""
        try:
            # Map base proof types to internal keys
            proof_name_to_key = {
                "Character Set Proof": "CharacterSetProof",
                "Spacing Proof": "SpacingProof",
                "Big Paragraph Proof": "BigParagraphProof",
                "Big Diacritics Proof": "BigDiacriticsProof",
                "Small Paragraph Proof": "SmallParagraphProof",
                "Small Paired Styles Proof": "SmallPairedStylesProof",
                "Small Wordsiv Proof": "SmallWordsivProof",
                "Small Diacritics Proof": "SmallDiacriticsProof",
                "Small Mixed Text Proof": "SmallMixedTextProof",
                "Arabic Contextual Forms": "ArabicContextualFormsProof",
                "Big Arabic Text Proof": "BigArabicTextProof",
                "Big Farsi Text Proof": "BigFarsiTextProof",
                "Small Arabic Text Proof": "SmallArabicTextProof",
                "Small Farsi Text Proof": "SmallFarsiTextProof",
                "Arabic Vocalization Proof": "ArabicVocalizationProof",
                "Arabic-Latin Mixed Proof": "ArabicLatinMixedProof",
                "Arabic Numbers Proof": "ArabicNumbersProof",
            }

            base_proof_key = proof_name_to_key.get(base_proof_type)
            if not base_proof_key:
                return

            popover = self.proof_settings_popover

            # Hide the proof type popup since we're editing a specific instance
            if hasattr(popover, "proofTypeLabel"):
                popover.proofTypeLabel.show(False)
            if hasattr(popover, "proofTypePopup"):
                popover.proofTypePopup.show(False)

            # Update numeric settings for this specific instance
            numeric_items = []

            # Font size setting
            font_size_key = f"{unique_proof_key}_fontSize"
            if base_proof_key in [
                "BigParagraphProof",
                "BigDiacriticsProof",
                "BigArabicTextProof",
                "BigFarsiTextProof",
            ]:
                default_font_size = largeTextFontSize
            elif base_proof_key in ["CharacterSetProof", "ArabicContextualFormsProof"]:
                default_font_size = charsetFontSize
            elif base_proof_key == "SpacingProof":
                default_font_size = spacingFontSize
            else:
                default_font_size = smallTextFontSize

            font_size_value = self.proof_settings.get(font_size_key, default_font_size)
            numeric_items.append(
                {
                    "Setting": "Font Size",
                    "Value": font_size_value,
                    "_key": font_size_key,
                }
            )

            # Columns setting (if applicable)
            if base_proof_key not in [
                "CharacterSetProof",
                "ArabicContextualFormsProof",
            ]:
                cols_key = f"{unique_proof_key}_cols"
                if base_proof_key in [
                    "BigParagraphProof",
                    "BigDiacriticsProof",
                    "BigArabicTextProof",
                    "BigFarsiTextProof",
                ]:
                    default_cols = 1
                else:
                    default_cols = 2
                cols_value = self.proof_settings.get(cols_key, default_cols)
                numeric_items.append(
                    {"Setting": "Columns", "Value": cols_value, "_key": cols_key}
                )

            # Paragraphs setting (only for SmallWordsivProof)
            if base_proof_key == "SmallWordsivProof":
                para_key = f"{unique_proof_key}_para"
                para_value = self.proof_settings.get(para_key, 5)
                numeric_items.append(
                    {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
                )

            # Add tracking for supported proof types
            supported_formatting_proofs = {
                "BigParagraphProof",
                "BigDiacriticsProof",
                "SmallParagraphProof",
                "SmallPairedStylesProof",
                "SmallWordsivProof",
                "SmallDiacriticsProof",
                "SmallMixedTextProof",
                "BigArabicTextProof",
                "BigFarsiTextProof",
                "SmallArabicTextProof",
                "SmallFarsiTextProof",
                "ArabicVocalizationProof",
                "ArabicLatinMixedProof",
                "ArabicNumbersProof",
            }

            if base_proof_key in supported_formatting_proofs:
                tracking_key = f"{unique_proof_key}_tracking"
                tracking_value = self.proof_settings.get(tracking_key, 0)
                numeric_items.append(
                    {"Setting": "Tracking", "Value": tracking_value, "_key": tracking_key}
                )

            popover.numericList.set(numeric_items)

            # Update OpenType features for this specific instance
            if self.font_manager.fonts:
                try:
                    feature_tags = db.listOpenTypeFeatures(self.font_manager.fonts[0])
                except Exception:
                    feature_tags = []
            else:
                feature_tags = []

            feature_items = []
            for tag in feature_tags:
                feature_key = f"otf_{unique_proof_key}_{tag}"

                # Special handling for SpacingProof kern feature
                if base_proof_key == "SpacingProof" and tag == "kern":
                    feature_value = False
                    self.proof_settings[feature_key] = False
                    feature_items.append(
                        {
                            "Feature": f"{tag} (always off)",
                            "Enabled": feature_value,
                            "_key": feature_key,
                            "_readonly": True,
                        }
                    )
                else:
                    default_value = tag in self.default_on_features
                    feature_value = self.proof_settings.get(feature_key, default_value)
                    feature_items.append(
                        {"Feature": tag, "Enabled": feature_value, "_key": feature_key}
                    )

            popover.featuresList.set(feature_items)

            # Update alignment control for supported proof types
            if base_proof_key in supported_formatting_proofs:
                # Update align control
                align_key = f"{unique_proof_key}_align"
                align_value = self.proof_settings.get(align_key, "left")
                align_options = ["left", "center", "right"]
                if align_value in align_options:
                    popover.alignPopUp.set(align_options.index(align_value))
                else:
                    popover.alignPopUp.set(0)  # Default to "left"

                # Show alignment control
                popover.alignLabel.show(True)
                popover.alignPopUp.show(True)
            else:
                # Hide alignment control for unsupported proof types
                popover.alignLabel.show(False)
                popover.alignPopUp.show(False)

        except Exception as e:
            print(f"Error updating proof settings popover: {e}")
            import traceback

            traceback.print_exc()
