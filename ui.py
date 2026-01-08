# UI - User interface utilities, custom controls, and text generation
# Consolidated from ui_utils.py, stepper_cell.py, and text_generators.py

import os
import random
from datetime import datetime
from urllib.parse import unquote
import vanilla
import AppKit
import objc
import drawBot as db
from Foundation import NSURL
import config
from settings import log_error, format_timestamp, normalize_path


# =============================================================================
# UI Helper Functions
# =============================================================================


def refresh_path_control(path_control, url):
    """Refresh PathControl with proper URL handling for app bundle compatibility"""
    try:
        if not url:
            path_control.set("")
            return

        # Handle different URL formats
        if isinstance(url, str) and not url.startswith("file://"):
            url = f"file://{normalize_path(url)}"

        path_control.set(url)

        # Force refresh for app bundle compatibility
        if hasattr(path_control, "getNSPathControl"):
            ns_control = path_control.getNSPathControl()
            if hasattr(ns_control, "setNeedsDisplay_"):
                ns_control.setNeedsDisplay_(True)

    except Exception as e:
        log_error(f"PathControl refresh failed: {e}", "refresh_path_control")
        try:
            path_control.set(url)
        except Exception:
            path_control.set("")


def create_font_drop_data(font_info, index=None):
    """Create drag data dictionary for font reordering"""
    try:
        if not font_info:
            return {}

        data = {
            "dev.drawbot.proof.fontData": font_info,
        }

        if index is not None:
            data["dev.drawbot.proof.fontListIndexes"] = index

        return data

    except Exception as e:
        log_error(f"Failed to create font drop data: {e}")
        return {}


def update_table_selection(table, new_data):
    """Update table data and preserve selection if possible"""
    try:
        if not hasattr(table, "get") or not hasattr(table, "set"):
            return False

        # Get current selection
        current_selection = getattr(table, "getSelection", lambda: [])()

        # Update table data
        table.set(new_data)

        # Restore selection if still valid
        if current_selection and len(current_selection) > 0:
            max_index = len(new_data) - 1
            valid_selection = [i for i in current_selection if 0 <= i <= max_index]
            if valid_selection and hasattr(table, "setSelection"):
                table.setSelection(valid_selection)

        return True

    except Exception as e:
        log_error(f"Failed to update table selection: {e}")
        return False


# =============================================================================
# DrawBot and PDF Utilities
# =============================================================================

from config import PAGE_DIMENSIONS


def setup_page_format(page_format):
    """Set up page format for drawBot based on format string"""
    try:
        # Get dimensions first
        width, height = None, None

        # If page_format is already a tuple/list of dimensions, use it directly
        if isinstance(page_format, (list, tuple)) and len(page_format) >= 2:
            width, height = page_format[0], page_format[1]
        # If page_format is a string, look it up in the mapping
        elif isinstance(page_format, str) and page_format in PAGE_DIMENSIONS:
            width, height = PAGE_DIMENSIONS[page_format]
        else:
            log_error(f"Invalid page format: {page_format}")
            return False

        # Do not call db.size() here to avoid creating an implicit page.
        # The proof generation flow explicitly calls db.newPage(pageDimensions)
        # for each page, so we only update the shared dimensions.
        # Always update the global pageDimensions variable for compatibility
        import config

        config.pageDimensions = (width, height)
        return True

    except Exception as e:
        log_error(f"Failed to setup page format: {e}")
        return False


# =============================================================================
# Data Processing for UI
# =============================================================================


def normalize_folder_result(result):
    """Normalize folder selection result from getFolder dialog."""
    if not result:
        return None

    # Handle the Objective-C array properly
    selected_path = None
    if hasattr(result, "__iter__") and hasattr(result, "__len__"):
        if len(result) > 0:
            selected_path = result[0]
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
    return selected_path


def set_path_control_with_refresh(path_control, url):
    """
    Set PathControl URL with enhanced compatibility for py2app bundles.
    This addresses iCloud Drive path display issues in app bundles.
    """
    if not url:
        path_control.set("")
        return

    # Use utility function for refreshing path control
    refresh_path_control(path_control, url)


def reorder_table_items(table_data, indexes, target_index):
    """Reorder table items based on drag and drop operation."""
    if not indexes or not table_data:
        return table_data

    # Convert to list if needed
    table_data = list(table_data)

    # Remove items from original positions (in reverse order to maintain indexes)
    moved_items = []
    for index in sorted(indexes, reverse=True):
        if 0 <= index < len(table_data):
            moved_items.insert(0, table_data.pop(index))

    # Insert items at target position
    for i, item in enumerate(moved_items):
        insert_index = target_index + i
        if insert_index > len(table_data):
            table_data.append(item)
        else:
            table_data.insert(insert_index, item)

    return table_data


def update_pdf_settings_helper(settings, custom_location=None, use_custom=None):
    """Helper to update PDF output settings consistently."""
    if "pdf_output" not in settings.data:
        settings.data["pdf_output"] = {
            "use_custom_location": False,
            "custom_location": "",
        }

    if custom_location is not None:
        settings.data["pdf_output"]["custom_location"] = custom_location
    if use_custom is not None:
        settings.data["pdf_output"]["use_custom_location"] = use_custom
    settings.save()


def create_table_drag_settings():
    """Create standard drag settings for font tables."""
    return dict(makeDragDataCallback=lambda index: create_font_drop_data(None, index))


def create_table_drop_settings():
    """Create standard drop settings for font tables."""
    return dict(
        pasteboardTypes=["fileURL", "dev.drawbot.proof.fontListIndexes"],
        dropCandidateCallback=lambda info: "move" if info.get("source") else "copy",
    )


def format_table_data(data_list, display_name_mapping=None, value_formatter=None):
    """
    Format data for PopUpButton display and value mapping.
    Returns (display_items, value_map) where value_map[display_name] = actual_value
    """
    if not data_list:
        return [], {}

    display_items = []
    value_map = {}

    for item in data_list:
        display_name = (
            display_name_mapping.get(item, item) if display_name_mapping else item
        )
        actual_value = value_formatter(item) if value_formatter else item

        display_items.append(display_name)
        value_map[display_name] = actual_value

    return display_items, value_map


def merge_font_data(font_list, axis_data):
    """Merge font list with axis data for table display"""
    try:
        if not font_list:
            return []

        merged_data = []

        for i, font_path in enumerate(font_list):
            font_info = {
                "path": font_path,
                "name": os.path.basename(font_path),
                "_path": font_path,  # Internal reference
            }

            # Add axis data if available
            if axis_data and i < len(axis_data):
                font_info.update(axis_data[i])

            merged_data.append(font_info)

        return merged_data

    except Exception as e:
        log_error(f"Failed to merge font data: {e}")
        return []


def extract_axis_values_from_table(table_data):
    """Extract axis values from table data"""
    try:
        axis_values = {}

        for row in table_data:
            if not isinstance(row, dict):
                continue

            font_path = row.get("_path") or row.get("path")
            if not font_path:
                continue

            # Extract axis values (skip non-axis keys)
            font_axes = {}
            skip_keys = {"path", "name", "_path"}

            for key, value in row.items():
                if key not in skip_keys:
                    font_axes[key] = value

            if font_axes:
                axis_values[font_path] = font_axes

        return axis_values

    except Exception as e:
        log_error(f"Failed to extract axis values: {e}")
        return {}


def format_axis_value_display(value):
    """Format axis value for display in UI"""
    try:
        if isinstance(value, (list, tuple)):
            # Format list of values
            formatted_values = []
            for v in value:
                if isinstance(v, float):
                    formatted_values.append(f"{v:.1f}")
                else:
                    formatted_values.append(str(v))
            return ", ".join(formatted_values)

        elif isinstance(value, float):
            return f"{value:.1f}"
        else:
            return str(value)

    except Exception:
        return str(value)


def parse_axis_value_input(input_string):
    """Parse user input for axis values (comma-separated numbers)"""
    try:
        if not input_string or not input_string.strip():
            return []

        # Split by comma and parse each value
        values = []
        for part in input_string.split(","):
            part = part.strip()
            if part:
                try:
                    # Try to parse as float
                    value = float(part)
                    values.append(value)
                except ValueError:
                    log_error(f"Invalid numeric value: {part}")

        return values

    except Exception as e:
        log_error(f"Failed to parse axis input: {e}")
        return []


# =============================================================================
# Custom Stepper Cell for vanilla.List2 - Adds steppers to numeric cells
# =============================================================================


class StepperTarget(AppKit.NSObject):
    """Target object for NSStepper actions."""

    def initWithCallback_(self, callback):
        """Initialize with a Python callback."""
        self = objc.super(StepperTarget, self).init()
        if self is None:
            return None
        self.callback = callback
        return self

    def stepperAction_(self, sender):
        """Handle stepper action and call Python callback."""
        if self.callback:
            self.callback(sender)


class StepperList2Cell(vanilla.Group):
    """
    A cell that displays a text field with a stepper control for numeric values.

    This follows the exact pattern used by other vanilla.List2 cell classes
    like EditTextList2Cell, CheckBoxList2Cell, etc.

    .. note::
       This class should only be used in the *columnDescriptions*
       *cellClass* argument during the construction of a List.
       This is never constructed directly.
    """

    def __init__(self, editable=True, callback=None, **kwargs):
        super().__init__("auto")

        # Store the external callback - this matches vanilla.List2 cell pattern
        self._externalCallback = callback

        # Create text field for value input
        self.textField = vanilla.EditText(
            "auto", callback=self._internalCallback, continuous=False
        )

        # Configuration storage
        self._stepperConfig = {"min_value": 0, "max_value": 100, "increment": 1}
        self._settingKey = None
        self._changeCallback = None

        # Try to get stepper config from kwargs (if passed during cell creation)
        if "stepperConfig" in kwargs:
            self._stepperConfig = kwargs["stepperConfig"]

        # Create the actual NSStepper with a wrapper target
        self._stepperTarget = StepperTarget.alloc().initWithCallback_(
            self._stepperChangedInternal
        )
        self._nsStepper = AppKit.NSStepper.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, 19, 22)
        )
        self._nsStepper.setTarget_(self._stepperTarget)
        self._nsStepper.setAction_("stepperAction:")

        # Apply initial configuration
        self._nsStepper.setMinValue_(self._stepperConfig.get("min_value", 0))
        self._nsStepper.setMaxValue_(self._stepperConfig.get("max_value", 100))
        self._nsStepper.setIncrement_(self._stepperConfig.get("increment", 1))
        self._nsStepper.setValueWraps_(False)  # Don't wrap around at limits

        # Layout - text field takes most space minus stepper width
        rules = [
            "H:|[textField]-25-|",  # Leave 25pt on right for stepper (19pt + margins)
            "V:|[textField]|",
        ]
        self.addAutoPosSizeRules(rules)

        # Add the stepper after layout rules are set
        self._nsObject.addSubview_(self._nsStepper)

        # Position stepper with a more reliable approach
        def _positionStepper():
            container_frame = self._nsObject.frame()
            if container_frame.size.width > 25:  # Only position if we have enough space
                # Position stepper 2pt from right edge, centered vertically
                stepper_x = container_frame.size.width - 21
                stepper_y = max(0, (container_frame.size.height - 22) / 2)
                self._nsStepper.setFrame_(
                    AppKit.NSMakeRect(stepper_x, stepper_y, 19, 22)
                )

        # Store positioning function
        self._positionStepper = _positionStepper

        # Position immediately and also after next run loop
        _positionStepper()
        from PyObjCTools.AppHelper import callAfter

        callAfter(_positionStepper)

    def _stepperChangedInternal(self, sender):
        """Internal stepper callback - called by StepperTarget."""
        value = sender.doubleValue()
        increment = self._stepperConfig.get("increment", 1)

        # Handle floating-point precision issues
        if increment < 1:
            decimal_places = (
                len(str(increment).split(".")[-1]) if "." in str(increment) else 0
            )
            value = round(value, decimal_places)
            if abs(value) < increment / 2:
                value = 0.0

        # Format based on increment type
        formatted_value = str(int(value)) if increment >= 1 else f"{value:g}"
        self.textField.set(formatted_value)

        # Call callbacks
        if self._externalCallback is not None:
            self._externalCallback(self)
        if self._changeCallback and self._settingKey:
            self._changeCallback(self._settingKey, formatted_value)

    def _internalCallback(self, sender):
        """Handle text field changes."""
        value_str = sender.get()

        try:
            numeric_value = float(value_str)
            self._nsStepper.setDoubleValue_(numeric_value)
        except (ValueError, TypeError):
            # Don't return - still call callbacks for validation/feedback
            pass

        # Call external callback if present (vanilla.List2 pattern)
        if self._externalCallback is not None:
            self._externalCallback(self)

        # Call specific change callback if present (our custom callback)
        if self._changeCallback and self._settingKey:
            self._changeCallback(self._settingKey, value_str)

    def set(self, value):
        """Set the value of the stepper cell."""
        if value is not None:
            try:
                # Set text field
                self.textField.set(str(value))

                # Set stepper
                numeric_value = float(value)
                self._nsStepper.setDoubleValue_(numeric_value)

                # Auto-configure stepper based on the row position if we have _representedColumnRow
                if hasattr(self, "_representedColumnRow"):
                    identifier, row = self._representedColumnRow

                    # Check the global registry for this row
                    if row in _ROW_SETTING_REGISTRY:
                        setting_name = _ROW_SETTING_REGISTRY[row]
                        stepper_config = get_stepper_config_for_setting(setting_name)
                        self.setStepperConfiguration_(stepper_config)

            except (ValueError, TypeError) as e:
                self.textField.set(str(value))

    def get(self):
        """Get the value of the stepper cell."""
        return self.textField.get()

    def setStepperConfiguration_(self, config):
        """Configure the stepper with min/max/increment values."""
        if config:
            self._stepperConfig = config
            self._nsStepper.setMinValue_(config.get("min_value", 0))
            self._nsStepper.setMaxValue_(config.get("max_value", 100))
            self._nsStepper.setIncrement_(config.get("increment", 1))
            self._nsStepper.setValueWraps_(False)  # Ensure no wrapping

    def setSettingName_(self, setting_name):
        """Set the setting name and auto-configure stepper."""
        self._settingName = setting_name
        stepper_config = get_stepper_config_for_setting(setting_name)
        self.setStepperConfiguration_(stepper_config)

    def setChangeCallback_withKey_(self, callback, setting_key):
        """Set the callback function and setting key."""
        self._changeCallback = callback
        self._settingKey = setting_key

    def resizeSubviewsWithOldSize_(self, oldSize):
        """Handle resizing to reposition stepper."""
        # Call super first
        try:
            super().resizeSubviewsWithOldSize_(oldSize)
        except AttributeError:
            pass  # Method may not exist in all versions

        # Reposition stepper
        if hasattr(self, "_positionStepper"):
            self._positionStepper()

    def setFrame_(self, frame):
        """Override setFrame to reposition stepper when frame changes."""
        # Call super first
        try:
            super().setFrame_(frame)
        except AttributeError:
            # Fallback to NSView method
            self._nsObject.setFrame_(frame)

        # Reposition stepper after frame change
        if hasattr(self, "_positionStepper"):
            from PyObjCTools.AppHelper import callAfter

            callAfter(self._positionStepper)


# Configuration for different numeric settings
STEPPER_CONFIGURATIONS = {
    "Font Size": {"min_value": 4, "max_value": 100, "increment": 1},
    "Columns": {"min_value": 1, "max_value": 5, "increment": 1},
    "Paragraphs": {"min_value": 1, "max_value": 20, "increment": 1},
    "Tracking": {"min_value": -10, "max_value": 10, "increment": 0.1},
}

# Global registry to map row indices to setting names
# This will be populated by the main window when the list is set up
_ROW_SETTING_REGISTRY = {}


def register_row_setting(row_index, setting_name):
    """Register a setting name for a specific row index."""
    _ROW_SETTING_REGISTRY[row_index] = setting_name


def clear_row_settings():
    """Clear the row settings registry."""
    global _ROW_SETTING_REGISTRY
    _ROW_SETTING_REGISTRY = {}


def get_stepper_config_for_setting(setting_name):
    """Get stepper configuration for a specific setting."""
    return STEPPER_CONFIGURATIONS.get(
        setting_name, {"min_value": 0, "max_value": 100, "increment": 1}
    )


# =============================================================================
# Text Generators - Functions for dynamic text generation and manipulation
# =============================================================================

from sample_texts import *
from script_texts import *
from accented_dictionary import accentedDict


class TextGenerator:
    """Handles dynamic text generation for proof documents"""

    def __init__(self):
        self.sample_texts = {
            "bigMixed": bigMixedText,
            "bigLower": bigLowerText,
            "bigUpper": bigUpperText,
            "smallMixed": smallMixedText,
            "smallLower": smallLowerText,
            "smallUpper": smallUpperText,
            "additional": additionalSmallText,
        }

        self.script_texts = {
            "arabic_vocalization": arabicVocalization,
            "arabic_latin_mixed": arabicLatinMixed,
            "arabic_farsi_urdu_numbers": arabicFarsiUrduNumbers,
        }

    def get_text_sample(self, text_type, case="mixed"):
        """Get a specific text sample by type and case"""
        if text_type == "big":
            if case == "mixed":
                return self.sample_texts["bigMixed"]
            elif case == "lower":
                return self.sample_texts["bigLower"]
            elif case == "upper":
                return self.sample_texts["bigUpper"]
        elif text_type == "small":
            if case == "mixed":
                return self.sample_texts["smallMixed"]
            elif case == "lower":
                return self.sample_texts["smallLower"]
            elif case == "upper":
                return self.sample_texts["smallUpper"]
        elif text_type == "additional":
            return self.sample_texts["additional"]
        elif text_type == "numbers":
            return bigRandomNumbers

        return ""

    def get_script_text(self, script_type):
        """Get script-specific text samples"""
        return self.script_texts.get(script_type, "")

    def generate_accented_text(self, character_list=None, word_count=50):
        """Generate text using accented characters"""
        if character_list is None:
            character_list = list(accentedDict.keys())

        words = []
        for char in character_list[:10]:  # Limit to first 10 characters
            if char in accentedDict:
                words.extend(accentedDict[char][:5])  # Take first 5 words per character

        random.shuffle(words)
        return " ".join(words[:word_count])

    def generate_random_numbers(self, count=100):
        """Generate random number sequences"""
        numbers = []
        for _ in range(count):
            # Mix of different number formats
            if random.choice([True, False]):
                numbers.append(str(random.randint(0, 9999)))
            else:
                numbers.append(f"{random.randint(0, 99)}.{random.randint(0, 99)}")
        return " ".join(numbers)

    def mix_texts(self, *text_types):
        """Mix multiple text types together"""
        combined = []
        for text_type in text_types:
            text = self.get_text_sample(text_type)
            if text:
                combined.append(text[:500])  # Take first 500 chars of each
        return "\n\n".join(combined)

    def get_character_set_sample(self, start_char, end_char, repeat=3):
        """Generate character set samples for testing"""
        chars = []
        for i in range(ord(start_char), ord(end_char) + 1):
            chars.append(chr(i) * repeat)
        return " ".join(chars)


# Global instance for easy access
text_generator = TextGenerator()


# =============================================================================
# Files Tab - Font management and PDF output location UI
# =============================================================================


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

    def _reorder_table_items(self, table_data, indexes, insert_index):
        """Reorder table items based on provided indexes."""
        return reorder_table_items(table_data, indexes, insert_index)

    def _update_backend_from_table(self, table_data):
        """Update font manager backend based on table data."""
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

    def _update_pdf_settings(self, custom_location=None, use_custom=None):
        """Helper to update PDF output settings consistently."""
        update_pdf_settings_helper(
            self.parent_window.settings, custom_location, use_custom
        )

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
        return (
            os.path.dirname(self.font_manager.fonts[0])
            if self.font_manager.fonts
            else ""
        )

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
            import traceback

            traceback.print_exc()

    def add_fonts(self, paths):
        """Add fonts to the font manager."""
        try:
            from settings import validate_font_path

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
            log_error(f"Error adding fonts: {e}", "add_fonts")

    def removeFontsCallback(self, sender):
        """Handle the Remove Selected button click."""
        try:
            # Try primary API
            try:
                selection = self.group.tableView.getSelection()
            except AttributeError:
                # Fallback to NSTableView selection indices
                table_view = self.group.tableView.getNSTableView()
                selection_indexes = table_view.selectedRowIndexes()
                selection = []
                index = selection_indexes.firstIndex()
                while index != AppKit.NSNotFound:
                    selection.append(index)
                    index = selection_indexes.indexGreaterThanIndex_(index)

            if not selection:
                return

            # Remove from backend using the same logic as deleteCallback
            self.font_manager.remove_fonts_by_indices(selection)

            # Refresh UI components and proof settings
            self.update_table()
            self.parent_window.initialize_proof_settings()

            # If no fonts remain, reset columns to base; also update PDF location UI
            if not self.font_manager.fonts:
                self.reset_table_columns()
            self.update_pdf_location_ui()
        except Exception as e:
            print(f"Error removing selected fonts: {e}")

    def axisEditCallback(self, sender):
        """Handle axis editing in the table."""
        table_data = sender.get()
        axes = getattr(self, "current_axes", None)
        self.font_manager.update_axis_values_from_table(table_data, axes)

    def makeDragDataCallback(self, index):
        """Create drag data for internal reordering."""
        table_data = self.group.tableView.get()
        if not (0 <= index < len(table_data)):
            return {}
        return create_font_drop_data(table_data[index], index)

    def dropCandidateCallback(self, info):
        """Handle drop candidate validation for both file drops and reordering."""
        return "move" if info["source"] == self.group.tableView else "copy"

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

            # Get current table data and reorder
            table_data = list(self.group.tableView.get())
            table_data = self._reorder_table_items(table_data, indexes, index)

            # Update table and backend
            self.group.tableView.set(table_data)
            self._update_backend_from_table(table_data)
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
        use_custom = self.group.pdfOutputBox.customLocationRadio.get()
        self._update_pdf_settings(use_custom=use_custom)
        self.update_pdf_location_ui()

    def _set_path_control_with_refresh(self, path_control, url):
        """Set PathControl URL with enhanced compatibility for py2app bundles."""
        set_path_control_with_refresh(path_control, url)

    def pdfPathControlCallback(self, sender):
        """Handle PathControl changes for PDF output location."""
        url = sender.get()
        if url:
            # Use helper method to set PathControl with refresh for app bundle compatibility
            self._set_path_control_with_refresh(sender, url)
            self._update_pdf_settings(custom_location=url, use_custom=True)

            # Update UI - select custom location radio button
            self.group.pdfOutputBox.customLocationRadio.set(True)
            self.group.pdfOutputBox.defaultLocationRadio.set(False)

    def browsePdfLocationCallback(self, sender):
        """Handle the browse button click for PDF output location."""
        try:
            from vanilla.dialogs import getFolder

            result = getFolder(messageText="Choose a folder for PDF output:")

            selected_path = normalize_folder_result(result)
            if selected_path:
                # Convert to proper file URL for PathControl
                file_url = (
                    f"file://{selected_path}"
                    if not selected_path.startswith("file://")
                    else selected_path
                )
                print(f"PDF will be saved at: {file_url}")

                # Update the PathControl and settings
                self._set_path_control_with_refresh(
                    self.group.pdfOutputBox.pathControl, file_url
                )
                self._update_pdf_settings(
                    custom_location=selected_path, use_custom=True
                )

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


# =============================================================================
# Controls Tab - Proof options and settings UI
# =============================================================================

from settings import create_unique_proof_key


class ControlsTab:
    """Handles the Controls tab UI and functionality."""

    def __init__(self, parent_window, settings):
        self.parent_window = parent_window
        self.settings = settings
        self.popover_states = {}  # Track which popovers are shown for each row
        self.create_ui()

    # ============ Helper Methods ============

    def _get_proof_mapping_data(self):
        """Get proof options mapping data from registry."""
        from config import (
            get_base_proof_display_names,
            get_arabic_proof_display_names,
            get_proof_settings_mapping,
        )

        mapping = get_proof_settings_mapping()
        base_options = [
            (name, key)
            for name, key in mapping.items()
            if name in get_base_proof_display_names()
        ]
        arabic_options = [
            (name, key)
            for name, key in mapping.items()
            if name in get_arabic_proof_display_names()
        ]
        return base_options, arabic_options

    def _get_proof_key_for_option(self, proof_name):
        """Get the correct proof key for a given proof option name."""
        from config import get_proof_settings_mapping

        proof_settings_mapping = get_proof_settings_mapping()

        # For base proof types, use the registry key directly
        if proof_name in proof_settings_mapping:
            return proof_settings_mapping[proof_name]
        else:
            # For numbered variants, use a sanitized version as the key
            return create_unique_proof_key(proof_name)

    def _has_settings(self, proof_name):
        """Check if a proof type has settings (all proofs have at least font size)."""
        from config import get_proof_display_names

        base_option = proof_name
        # Extract base type for numbered variants
        for base_name in get_proof_display_names(include_arabic=True):
            if proof_name.startswith(base_name):
                base_option = base_name
                break
        return base_option in get_proof_display_names(include_arabic=True)

    def _manage_popover_state(self, proof_name, action):
        """Centralized popover state management."""
        if action == "show":
            self.popover_states[proof_name] = True
        elif action == "hide":
            self.popover_states[proof_name] = False
        elif action == "toggle":
            self.popover_states[proof_name] = not self.popover_states.get(
                proof_name, False
            )
        elif action == "get":
            return self.popover_states.get(proof_name, False)
        return self.popover_states.get(proof_name, False)

    def get_proof_options_list(self):
        """Generate dynamic proof options list based on font capabilities and saved custom instances."""
        # Get base and Arabic proof options from registry
        base_options, arabic_options = self._get_proof_mapping_data()

        # Check if any loaded font supports Arabic
        show_arabic_proofs = self.parent_window.font_manager.has_arabic_support()

        # Build the base options list
        all_options = base_options[:]
        if show_arabic_proofs:
            all_options.extend(arabic_options)

        # Get the saved proof order to check for custom instances
        saved_order = self.settings.get_proof_order()
        base_proof_names = set(name for name, key in all_options)

        # Add custom instances from saved order that aren't in base options
        custom_instances = []
        custom_instance_names = set()
        for display_name in saved_order:
            if (
                display_name not in base_proof_names
                and display_name != "Show Baselines/Grid"
            ):
                # This is a custom instance - extract the base proof type
                base_type = self._extract_base_proof_type(display_name)
                if base_type and base_type in base_proof_names:
                    # Create a unique key for this custom instance
                    unique_key = create_unique_proof_key(display_name)
                    custom_instances.append((display_name, unique_key))
                    custom_instance_names.add(display_name)

        # Add custom instances to the options
        all_options.extend(custom_instances)

        # Create a mapping from display names to options
        options_dict = dict(all_options)

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
            # For custom instances, determine the enabled state correctly
            if display_name in custom_instance_names:
                # Custom instance - use the unique key format for storage
                unique_key = create_unique_proof_key(display_name)
                enabled = self.settings.get_proof_option(unique_key)

                # For custom instances, set the original option to the base type
                base_type = self._extract_base_proof_type(display_name)
                item = {
                    "Option": display_name,
                    "Enabled": enabled,
                    "_original_option": base_type or display_name,
                }
            else:
                # Base proof type - use the registry key
                enabled = self.settings.get_proof_option(settings_key)
                item = {
                    "Option": display_name,
                    "Enabled": enabled,
                    "_original_option": display_name,
                }

            proof_options_items.append(item)

        return proof_options_items

    def _extract_base_proof_type(self, custom_display_name):
        """Extract base proof type from a custom display name like 'Diacritic Words Small 2'."""
        # Import helper functions
        from config import get_proof_display_names

        base_display_names = get_proof_display_names(include_arabic=True)

        # Try to find the base proof type by checking if the custom name starts with a base name
        for base_name in base_display_names:
            if (
                custom_display_name.startswith(base_name)
                and custom_display_name != base_name
            ):
                # Check if the remainder is just a number/space pattern
                remainder = custom_display_name[len(base_name) :].strip()
                if remainder and (remainder.isdigit() or remainder.startswith(" ")):
                    return base_name

        return None

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
                    self.settings.get_proof_option("show_baselines")
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
            from AppKit import NSBezelStyleRegularSquare, NSTextAlignmentCenter

            self.group = vanilla.Group((0, 0, -0, -0))

            # Create a split layout: Controls on left, Preview on right
            # Controls area (left side)
            controls_x = 10
            y = 10

            # Preview area (right side)
            self.group.previewBox = vanilla.Box((350, 10, -10, -10))

            # Generate dynamic proof options list
            proof_options_items = self.get_proof_options_list()

            # Initialize popover states for all proofs (lazy initialization in helper method)
            self.popover_states = {}

            # Drag and drop settings for internal reordering only
            dragSettings = dict(makeDragDataCallback=self.makeProofDragDataCallback)
            dropSettings = dict(
                pasteboardTypes=["dev.drawbot.proof.proofOptionIndexes"],
                dropCandidateCallback=self.dropProofCandidateCallback,
                performDropCallback=self.performProofDropCallback,
            )

            # Page format selection
            # Import PAGE_FORMAT_OPTIONS from core_config
            from config import PAGE_FORMAT_OPTIONS

            self.group.pageFormatPopUp = vanilla.PopUpButton(
                (controls_x + 2, y, 153, 20),
                PAGE_FORMAT_OPTIONS,
                callback=self.pageFormatCallback,
            )
            self.group.pageFormatPopUp._nsObject.setAlignment_(NSTextAlignmentCenter)

            # Set current value
            current_format = self.settings.get_page_format()
            if current_format in PAGE_FORMAT_OPTIONS:
                self.group.pageFormatPopUp.set(
                    PAGE_FORMAT_OPTIONS.index(current_format)
                )
            else:
                self.group.pageFormatPopUp.set(PAGE_FORMAT_OPTIONS.index("A4Landscape"))

            self.group.showBaselinesCheckbox = vanilla.CheckBox(
                (controls_x + 165, y, 100, 20),
                "Show Grid",
                value=self.settings.get_proof_option("show_baselines"),
                callback=self.showBaselinesCallback,
            )

            self.group.addSettingsButton = vanilla.Button(
                (controls_x, y + 26, 155, 20),
                "Add Settings File",
                callback=self.parent_window.addSettingsFileCallback,
            )

            self.group.resetButton = vanilla.Button(
                (controls_x + 165, y + 26, 155, 20),
                "Reset Settings",
                callback=self.parent_window.resetSettingsCallback,
            )

            self.group.proofOptionsList = vanilla.List2(
                (controls_x, y + 59, 320, 401),  # Adjusted width for left side
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

            y += 30  # Space for the page format control

            self.group.addProofButton = vanilla.Button(
                (controls_x + 165, -68, 155, 20),
                title="Add Proof",
                callback=self.addProofCallback,
            )

            self.group.removeProofButton = vanilla.Button(
                (controls_x + 165, -40, 155, 20),
                title="Remove Proof",
                callback=self.removeProofCallback,
            )

            self.group.generateButton = vanilla.GradientButton(
                (controls_x, -70, 155, 55),
                title="Generate Proof",
                callback=self.parent_window.generateCallback,
            )
            self.group.generateButton._nsObject.setBezelStyle_(
                NSBezelStyleRegularSquare
            )
            self.group.generateButton._nsObject.setKeyEquivalent_("\\r")

        except Exception as e:
            print(f"Error creating Controls tab UI: {e}")
            import traceback

            traceback.print_exc()
            raise

    def proofOptionsEditCallback(self, sender):
        """Handle edits to proof options."""
        items = sender.get()
        edited_index = sender.getEditedIndex()

        if edited_index is not None and edited_index < len(items):
            item = items[edited_index]
            proof_name = item["Option"]
            base_option = item.get("_original_option", proof_name)
            enabled = item["Enabled"]

            # If this proof has settings and was just enabled, show the popover
            if (
                self._has_settings(base_option)
                and enabled
                and not self._manage_popover_state(proof_name, "get")
            ):
                self.hide_all_popovers_except(proof_name)
                self.show_popover_for_option(proof_name, edited_index)
                self._manage_popover_state(proof_name, "show")
            elif (
                self._has_settings(base_option)
                and not enabled
                and self._manage_popover_state(proof_name, "get")
            ):
                self.hide_popover_for_option(proof_name)
                self._manage_popover_state(proof_name, "hide")

        # Handle regular proof option edits (save settings)
        for item in items:
            proof_name = item["Option"]  # Use the actual proof name
            enabled = item["Enabled"]
            proof_key = self._get_proof_key_for_option(proof_name)
            self.settings.set_proof_option(proof_key, enabled)

    def pageFormatCallback(self, sender):
        """Handle page format selection changes."""
        try:
            from config import PAGE_FORMAT_OPTIONS

            selected_index = sender.get()
            if 0 <= selected_index < len(PAGE_FORMAT_OPTIONS):
                selected_format = PAGE_FORMAT_OPTIONS[selected_index]
                self.settings.set_page_format(selected_format)
                print(f"Page format changed to: {selected_format}")
        except Exception as e:
            print(f"Error changing page format: {e}")

    def showBaselinesCallback(self, sender):
        """Handle the Show Baselines/Grid standalone checkbox."""
        enabled = sender.get()
        self.settings.set_proof_option("show_baselines", enabled)

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

            # Save the new order to settings (excluding Show Baselines/Grid)
            new_order = [
                item["Option"]
                for item in proof_items
                if item["Option"] != "Show Baselines/Grid"
            ]
            self.settings.set_proof_order(new_order)
            self.settings.save()

            return True

        return False

    def hide_all_popovers_except(self, except_option):
        """Hide all open popovers except the specified one."""
        for option in list(self.popover_states.keys()):
            if option != except_option and self._manage_popover_state(option, "get"):
                self.hide_popover_for_option(option)
                self._manage_popover_state(option, "hide")

    def show_popover_for_option(self, option, row_index):
        """Show popover for the specified option."""
        # Import the helper function from proof_config
        from config import get_proof_settings_mapping

        # Get proof name to key mapping from registry
        proof_name_to_key = get_proof_settings_mapping()

        # Check if this is a base proof type or a numbered variant
        base_proof_type = option
        for base_name in proof_name_to_key.keys():
            if option.startswith(base_name):
                base_proof_type = base_name
                break

        if base_proof_type in proof_name_to_key:
            # Use the unique option name as the proof key for settings
            unique_proof_key = create_unique_proof_key(option)
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

        # Get available proof types using existing helper
        base_options, arabic_options = self._get_proof_mapping_data()
        proof_type_options = [name for name, key in base_options]

        # Add Arabic proof types if fonts support Arabic
        if self.parent_window.font_manager.has_arabic_support():
            proof_type_options.extend([name for name, key in arabic_options])

        popover.proofTypePopup = vanilla.PopUpButton(
            (10, 35, -10, 20), proof_type_options
        )

        # Buttons
        popover.addButton = vanilla.Button(
            (10, 65, 120, 20), "Add", callback=self.addSelectedProofCallback
        )
        popover.cancelButton = vanilla.Button(
            (-130, 65, 120, 20), "Cancel", callback=self.cancelAddProofCallback
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

            # Update the proof order in settings (excluding Show Baselines/Grid)
            new_order = [
                item["Option"]
                for item in current_proofs
                if item["Option"] != "Show Baselines/Grid"
            ]
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

    def removeProofCallback(self, sender):
        """Handle the Remove Proof button click."""
        try:
            # Get the current selection from the proof options list
            # Note: We need to get selection before removing to track what was removed
            current_proofs = list(self.group.proofOptionsList.get())

            # Get selection using the List2 object's selection
            # Try to get the selection - List2 objects may use different method names
            try:
                selection = self.group.proofOptionsList.getSelection()
            except AttributeError:
                # Fallback - get selection using NSTableView if getSelection doesn't exist
                table_view = self.group.proofOptionsList.getNSTableView()
                selection_indexes = table_view.selectedRowIndexes()
                selection = []
                index = selection_indexes.firstIndex()
                while index != AppKit.NSNotFound:
                    selection.append(index)
                    index = selection_indexes.indexGreaterThanIndex_(index)

            if not selection:
                print("No proof selected for removal")
                return

            # Track what we're removing for logging
            removed_proofs = []
            for index in selection:
                if 0 <= index < len(current_proofs):
                    removed_proofs.append(current_proofs[index]["Option"])

            # Remove selected items (in reverse order to maintain indices)
            for index in sorted(selection, reverse=True):
                if 0 <= index < len(current_proofs):
                    current_proofs.pop(index)

            # Update the list
            self.group.proofOptionsList.set(current_proofs)

            # Update the proof order in settings (excluding Show Baselines/Grid)
            new_order = [
                item["Option"]
                for item in current_proofs
                if item["Option"] != "Show Baselines/Grid"
            ]
            self.settings.set_proof_order(new_order)
            self.settings.save()

            # Log what was removed
            for proof_name in removed_proofs:
                print(f"Removed proof: {proof_name}")

        except Exception as e:
            print(f"Error removing proof: {e}")
            import traceback

            traceback.print_exc()

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
