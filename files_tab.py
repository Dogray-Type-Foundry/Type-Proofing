# Files Tab - Font management and PDF output location UI

import os
import traceback
import urllib.parse
import vanilla
from utils import normalize_path, validate_font_path, log_error
from ui_utils import refresh_path_control, create_font_drop_data, format_table_data


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

    # ============ Helper Methods ============

    def _refresh_after_font_changes(self):
        """Refresh UI components after font changes."""
        self.update_table()
        self.parent_window.initialize_proof_settings()

    def _sync_table_with_backend(self):
        """Sync font manager backend with table UI state."""
        table_data = self.group.tableView.get()
        font_paths = [row["_path"] for row in table_data if "_path" in row]
        # Find indices of fonts to remove
        indices_to_remove = []
        for i, font_path in enumerate(self.font_manager.fonts):
            if font_path not in font_paths:
                indices_to_remove.append(i)
        self.font_manager.remove_fonts_by_indices(indices_to_remove)

    def create_ui(self):
        """Create the Files tab UI components."""
        self.group = vanilla.Group((0, 0, -0, -0))

        # Initialize with basic column descriptions - will be updated dynamically
        self.base_column_descriptions = [
            {"identifier": "name", "title": "Font", "width": 200},
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

        # Get table data with individual axis columns from font manager
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
                "width": 180,
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

        desired_axes_order = self.font_manager.get_all_axes()
        current_columns = self.group.tableView.getColumnIdentifiers()
        base_column_ids = [desc["identifier"] for desc in self.base_column_descriptions]
        existing_axis_columns = [
            col for col in current_columns if col not in base_column_ids
        ]

        if existing_axis_columns and existing_axis_columns != desired_axes_order:
            # Build new column order: base + axes in first font's order
            new_column_order = base_column_ids + [
                axis for axis in desired_axes_order if axis in existing_axis_columns
            ]
            # Add remaining axis columns not in the first font
            new_column_order.extend(
                [axis for axis in existing_axis_columns if axis not in new_column_order]
            )

            if new_column_order != current_columns:
                current_data = self.group.tableView.get()

                # Remove and re-add axis columns in new order
                for axis in existing_axis_columns:
                    self.group.tableView.removeColumn(axis)

                for axis in new_column_order:
                    if axis not in base_column_ids:
                        self.group.tableView.appendColumn(
                            {
                                "identifier": axis,
                                "title": axis,
                                "width": 180,
                                "editable": True,
                            }
                        )

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
        try:
            # Normalize and validate paths using utility functions
            validated_paths = []
            for path in paths:
                normalized_path = normalize_path(path)
                if validate_font_path(normalized_path):
                    validated_paths.append(normalized_path)
                else:
                    print(f"Skipping invalid font file: {path}")

            if validated_paths and self.font_manager.add_fonts(validated_paths):
                self._refresh_after_font_changes()
                # Update PDF location UI to populate PathControl with first font's folder
                self.update_pdf_location_ui()
            else:
                print("No new valid font paths found")
        except Exception as e:
            log_error(f"Error adding fonts: {e}", traceback.format_exc())

    def removeFontsCallback(self, sender):
        """Handle the Remove Selected button click."""
        self.group.tableView.removeSelection()
        self._sync_table_with_backend()
        self._refresh_after_font_changes()

    def axisEditCallback(self, sender):
        """Handle axis editing in the table."""
        table_data = sender.get()
        if hasattr(self, "current_axes"):
            self.font_manager.update_axis_values_from_table(
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

            # Remove items to move in reverse order to maintain indices
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
                # Update axis values
                if hasattr(self, "current_axes"):
                    self.font_manager.update_axis_values_from_table(
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
            return

        # Use utility function for refreshing path control
        refresh_path_control(path_control, url)

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
