# UI Utilities - Interface helpers, drawing utilities, and data formatting for UI components

import os
import random
import traceback
from datetime import datetime
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


def show_error_dialog(message, title="Error"):
    """Show error dialog to user (macOS)"""
    try:
        import vanilla

        # Create a simple error dialog
        dialog = vanilla.Window((400, 150), title)
        dialog.textBox = vanilla.TextBox(
            (20, 20, -20, -60), message, sizeStyle="regular"
        )
        dialog.okButton = vanilla.Button(
            (150, -40, 100, 20), "OK", callback=lambda sender: dialog.close()
        )

        dialog.open()
        return True

    except Exception as e:
        log_error(f"Failed to show error dialog: {e}")
        # Fallback to console
        print(f"{title}: {message}")
        return False


def get_table_column_width(table, column_index, default_width=100):
    """Get table column width safely"""
    try:
        if hasattr(table, "getNSTableView"):
            ns_table = table.getNSTableView()
            if hasattr(ns_table, "tableColumns"):
                columns = ns_table.tableColumns()
                if 0 <= column_index < len(columns):
                    return columns[column_index].width()
        return default_width
    except Exception:
        return default_width


def set_table_column_width(table, column_index, width):
    """Set table column width safely"""
    try:
        if hasattr(table, "getNSTableView"):
            ns_table = table.getNSTableView()
            if hasattr(ns_table, "tableColumns"):
                columns = ns_table.tableColumns()
                if 0 <= column_index < len(columns):
                    columns[column_index].setWidth_(width)
                    return True
        return False
    except Exception as e:
        log_error(f"Failed to set table column width: {e}")
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

        # If page_format is already a tuple/list of dimensions, use it directly
        if isinstance(page_format, (list, tuple)) and len(page_format) >= 2:
            width, height = page_format[0], page_format[1]
            db.size(width, height)

            # Update the global pageDimensions variable for compatibility
            import config

            config.pageDimensions = (width, height)
            return True

        # If page_format is a string, look it up in the mapping
        if isinstance(page_format, str) and page_format in PAGE_DIMENSIONS:
            width, height = PAGE_DIMENSIONS[page_format]
            db.size(width, height)

            # Update the global pageDimensions variable for compatibility
            import config

            config.pageDimensions = (width, height)
            return True

        log_error(f"Invalid page format: {page_format}")
        return False

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
        footer_text = f"{timestamp} | {font_name} | {proof_type} | Page {page_number}"

        # Position footer at bottom
        y_position = footer_margin

        # Draw footer text
        db.textBox(
            footer_text,
            (footer_margin, y_position, page_width - 2 * footer_margin, footer_height),
            align="center",
        )

        return True

    except Exception as e:
        log_error(f"Failed to add footer info: {e}")
        return False


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


def center_text_on_page(text, page_width, page_height, font_size=12, font_name="Arial"):
    """Calculate centered text position"""
    try:
        bounds = calculate_text_bounds(text, font_size, font_name)

        x = (page_width - bounds["width"]) / 2
        y = (page_height - bounds["height"]) / 2

        return {"x": x, "y": y, "width": bounds["width"], "height": bounds["height"]}

    except Exception as e:
        log_error(f"Failed to center text: {e}")
        return {"x": 0, "y": 0, "width": 0, "height": 0}


def draw_text_with_background(
    text, x, y, width, height, bg_color=None, text_color=None
):
    """Draw text with optional background"""
    try:
        import drawBot as db

        # Draw background if specified
        if bg_color:
            db.fill(*bg_color)
            db.rect(x, y, width, height)

        # Draw text
        if text_color:
            db.fill(*text_color)
        else:
            db.fill(0)  # Black text by default

        db.textBox(text, (x, y, width, height))
        return True

    except Exception as e:
        log_error(f"Failed to draw text with background: {e}")
        return False


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


def generate_font_preview_text(font_path, sample_text="The quick brown fox"):
    """Generate preview text for a font"""
    try:
        from utils import safe_font_load

        ttfont = safe_font_load(font_path)
        if not ttfont:
            return sample_text

        # Get character set from font
        cmap = ttfont.getBestCmap()
        available_chars = set(cmap.keys()) if cmap else set()

        # Filter sample text to only include available characters
        filtered_chars = []
        for char in sample_text:
            if ord(char) in available_chars:
                filtered_chars.append(char)
            elif char.isspace():
                filtered_chars.append(char)  # Keep spaces

        preview = "".join(filtered_chars)
        return preview if preview.strip() else sample_text

    except Exception as e:
        log_error(f"Failed to generate font preview: {e}")
        return sample_text


def get_font_display_name(font_path):
    """Get display name for font in UI"""
    try:
        from utils import safe_font_load

        ttfont = safe_font_load(font_path)
        if ttfont and "name" in ttfont:
            name_table = ttfont["name"]

            # Try to get family name (ID 1) and style name (ID 2)
            family_name = None
            style_name = None

            for record in name_table.names:
                if record.nameID == 1:  # Family name
                    family_name = str(record)
                elif record.nameID == 2:  # Style name
                    style_name = str(record)

            if family_name:
                if style_name and style_name.lower() not in ["regular", "normal"]:
                    return f"{family_name} {style_name}"
                return family_name

        # Fallback to filename
        return os.path.splitext(os.path.basename(font_path))[0]

    except Exception as e:
        log_error(f"Failed to get font display name: {e}")
        return os.path.splitext(os.path.basename(font_path))[0]


# =============================================================================
# Color Utilities
# =============================================================================


def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    try:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    except Exception:
        return (0, 0, 0)  # Black fallback


def rgb_to_hex(rgb_tuple):
    """Convert RGB tuple to hex color"""
    try:
        r, g, b = rgb_tuple
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    except Exception:
        return "#000000"  # Black fallback


def get_contrast_text_color(bg_color):
    """Get appropriate text color (black/white) for background"""
    try:
        if isinstance(bg_color, str):
            bg_color = hex_to_rgb(bg_color)

        # Calculate relative luminance
        r, g, b = bg_color
        luminance = 0.299 * r + 0.587 * g + 0.114 * b

        # Return white text for dark backgrounds, black for light
        return (1, 1, 1) if luminance < 0.5 else (0, 0, 0)

    except Exception:
        return (0, 0, 0)  # Black fallback
