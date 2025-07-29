# UI Utilities - Interface helpers, drawing utilities, and data formatting for UI components

import os
from datetime import datetime
from urllib.parse import unquote
import vanilla
import AppKit
import objc
import drawBot as db
from Foundation import NSURL
import core_config
from utils import log_error, format_timestamp, normalize_path


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

from core_config import PAGE_DIMENSIONS


def setup_page_format(page_format):
    """Set up page format for drawBot based on format string"""
    try:
        import drawBot as db

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

        # Try to set the size, but catch the error if drawing has already started
        try:
            db.size(width, height)
        except Exception as size_error:
            # If size() fails because drawing has started, just log it but don't fail
            if "drawing has begun" in str(size_error):
                log_error(
                    f"Cannot set page size after drawing has started, using current dimensions"
                )
            else:
                # Re-raise other errors
                raise size_error

        # Always update the global pageDimensions variable for compatibility
        import core_config

        core_config.pageDimensions = (width, height)
        return True

    except Exception as e:
        log_error(f"Failed to setup page format: {e}")
        return False


def add_footer_info(font_name, proof_type, page_number, page_width, page_height):
    """Add footer information to drawBot canvas"""
    try:
        import drawBot as db

        # Footer settings
        footer_height = 30
        footer_margin = 20
        font_size = 10

        # Set footer font
        db.font("Arial", font_size)
        db.fill(0.5)  # Gray color

        # Generate footer text
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        left_text = f"{timestamp} | {font_name} | {proof_type} | Page {page_number}"
        right_text = f"Page {page_number} of {core_config.totalPages}"

        # Position footer at bottom
        y_position = footer_margin

        # Draw footer text
        db.text(left_text, (footer_margin, footer_margin))
        db.text(
            right_text,
            (page_width - db.textSize(right_text)[0] - footer_margin, footer_margin),
        )

    except Exception as e:
        log_error(f"Failed to add footer info: {e}", "add_footer_info")


def calculate_text_bounds(text, font_size, font_name="Arial"):
    """Calculate text bounds for layout purposes"""
    try:
        import drawBot as db

        db.font(font_name, font_size)
        width, height = db.textSize(text)
        return {"width": width, "height": height}

    except Exception as e:
        log_error(f"Failed to calculate text bounds: {e}")
        return {"width": 0, "height": 0}


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
# Font-specific UI Utilities
# =============================================================================
