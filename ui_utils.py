# UI Utilities - Interface helpers, drawing utilities, and data formatting for UI components
from datetime import datetime
from utils import log_error, format_timestamp, normalize_path
import vanilla
import AppKit
import objc
import os
from urllib.parse import unquote
from Foundation import NSURL
import core_config
import drawBot as db


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
        if isinstance(url, str):
            if not url.startswith("file://"):
                url = f"file://{normalize_path(url)}"

        # Set the path control
        path_control.set(url)

        # Force refresh for app bundle compatibility
        if hasattr(path_control, "getNSPathControl"):
            ns_control = path_control.getNSPathControl()
            if hasattr(ns_control, "setNeedsDisplay_"):
                ns_control.setNeedsDisplay_(True)

    except Exception as e:
        log_error(f"PathControl refresh failed: {e}", "refresh_path_control")
        # Fallback: try setting the original URL
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

# Page format dimensions mapping (in points)
PAGE_DIMENSIONS = {
    "A3Landscape": (1190, 842),  # A3 landscape: 420mm x 297mm
    "A4Landscape": (842, 595),  # A4 landscape: 297mm x 210mm
    "A4SmallLandscape": (756, 531),  # A4 small landscape: 267mm x 187mm
    "A5Landscape": (595, 420),  # A5 landscape: 210mm x 148mm
    "LegalLandscape": (1008, 612),  # Legal landscape: 14" x 8.5"
    "LetterLandscape": (792, 612),  # Letter landscape: 11" x 8.5"
    "LetterSmallLandscape": (720, 540),  # Letter small landscape: 10" x 7.5"
}


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


def format_table_data(raw_data):
    """Format raw data for table display"""
    try:
        if not raw_data:
            return []

        if isinstance(raw_data, list):
            return raw_data

        if isinstance(raw_data, dict):
            # Convert dict to list of dicts
            return [{"key": k, "value": v} for k, v in raw_data.items()]

        # Convert other types to string representation
        return [{"value": str(raw_data)}]

    except Exception as e:
        log_error(f"Failed to format table data: {e}")
        return []


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
