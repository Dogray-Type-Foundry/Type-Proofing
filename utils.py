# Core Utilities - File operations, validation, string processing, and error handling

import os
import json
import datetime
import traceback
import re
from urllib.parse import urlparse, unquote


# =============================================================================
# File and Path Utilities
# =============================================================================


def normalize_path(path, font_specific=False):
    """Normalize path from various input types (URL, string, AppKit.NSURL, etc.)"""
    if not path:
        return ""

    # Handle AppKit.NSURL objects for font-specific paths
    if font_specific:
        try:
            import AppKit

            if isinstance(path, AppKit.NSURL):
                return path.path()
        except ImportError:
            pass

    # Handle URL format
    if isinstance(path, str):
        if path.startswith("file://"):
            if font_specific:
                return path.replace("file://", "")
            else:
                parsed = urlparse(path)
                path = unquote(parsed.path)

    if font_specific:
        return str(path)
    else:
        return os.path.abspath(os.path.expanduser(str(path)))


def ensure_directory_exists(directory):
    """Create directory if it doesn't exist"""
    try:
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        log_error(f"Failed to create directory {directory}: {e}")
        return False


def get_file_extension(path):
    """Get file extension in lowercase"""
    if not path:
        return ""
    return os.path.splitext(path)[1].lower()


def is_valid_font_extension(path):
    """Check if path has a valid font file extension"""
    valid_extensions = {".otf", ".ttf", ".woff", ".woff2"}
    return get_file_extension(path) in valid_extensions


def make_safe_filename(name, extension=""):
    """Create a safe filename by removing/replacing invalid characters"""
    if not name:
        return "unnamed"

    # Replace invalid filename characters
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
    safe_name = safe_name.strip(". ")

    # Limit length
    if len(safe_name) > 200:
        safe_name = safe_name[:200]

    # Add extension if provided and not already present
    if extension and not safe_name.endswith(extension):
        safe_name += extension

    return safe_name or "unnamed"


def resolve_icloud_path(path):
    """Resolve iCloud Drive paths to user-friendly display format"""
    if not path:
        return path

    user_home = os.path.expanduser("~")
    icloud_base = f"{user_home}/Library/Mobile Documents/com~apple~CloudDocs"

    if path.startswith(icloud_base):
        relative_path = path[len(icloud_base) :].lstrip("/")
        return f"iCloud Drive/{relative_path}" if relative_path else "iCloud Drive"

    return path


def get_file_size_formatted(path):
    """Get formatted file size string"""
    try:
        if not path or not os.path.exists(path):
            return "Unknown"

        size_bytes = os.path.getsize(path)
        return format_file_size(size_bytes)
    except Exception:
        return "Unknown"


def format_file_size(bytes_size):
    """Format bytes into human readable string"""
    if bytes_size == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    size = bytes_size
    i = 0

    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


# =============================================================================
# JSON File Operations
# =============================================================================


def safe_json_load(file_path, default=None):
    """Safely load JSON file with error handling"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_error(f"Failed to load JSON from {file_path}: {e}")

    return default if default is not None else {}


def safe_json_save(data, file_path):
    """Safely save data to JSON file"""
    try:
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory:
            ensure_directory_exists(directory)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        log_error(f"Failed to save JSON to {file_path}: {e}")
        return False


# =============================================================================
# String Processing Utilities
# =============================================================================


def clean_font_name(name):
    """Clean font name for display"""
    if not name:
        return "Unnamed Font"

    # Remove common font suffixes and clean up
    cleaned = name.replace("Regular", "").replace("Normal", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned or "Unnamed Font"


def format_timestamp(datetime_obj=None):
    """Format datetime object to readable string"""
    if datetime_obj is None:
        datetime_obj = datetime.datetime.now()

    return datetime_obj.strftime("%Y-%m-%d_%H%M")


def sanitize_filename(filename):
    """Sanitize filename for cross-platform compatibility"""
    if not filename:
        return "unnamed"

    # Remove path components
    filename = os.path.basename(filename)

    # Replace problematic characters
    sanitized = re.sub(r"[^\w\-_\.]", "_", filename)

    # Remove multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)

    # Remove leading/trailing underscores and dots
    sanitized = sanitized.strip("_.")

    return sanitized or "unnamed"


def truncate_text(text, max_length=100, suffix="..."):
    """Truncate text to specified length"""
    if not text or len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


# =============================================================================
# Validation Utilities
# =============================================================================


def validate_font_path(path):
    """Validate that path points to a valid font file"""
    try:
        if not path:
            return False, "No path provided"

        normalized = normalize_path(path)

        if not os.path.exists(normalized):
            return False, f"File does not exist: {path}"

        if not os.path.isfile(normalized):
            return False, f"Path is not a file: {path}"

        if not is_valid_font_extension(normalized):
            return False, f"Invalid font file extension: {get_file_extension(path)}"

        return True, "Valid font file"

    except Exception as e:
        return False, f"Validation error: {e}"


def validate_axis_values(axis_dict):
    """Validate variable font axis values"""
    if not isinstance(axis_dict, dict):
        return False, "Axis values must be a dictionary"

    for axis_name, values in axis_dict.items():
        if not isinstance(axis_name, str):
            return False, f"Axis name must be string, got {type(axis_name)}"

        if isinstance(values, (int, float)):
            continue  # Single value is OK

        if isinstance(values, (list, tuple)):
            for value in values:
                if not isinstance(value, (int, float)):
                    return (
                        False,
                        f"Axis values must be numeric, got {type(value)} in {axis_name}",
                    )
        else:
            return (
                False,
                f"Axis values must be number or list, got {type(values)} for {axis_name}",
            )

    return True, "Valid axis values"


def validate_pdf_output_path(path):
    """Validate PDF output path"""
    try:
        if not path:
            return False, "No path provided"

        normalized = normalize_path(path)
        directory = os.path.dirname(normalized)

        if not os.path.exists(directory):
            return False, f"Directory does not exist: {directory}"

        if not os.access(directory, os.W_OK):
            return False, f"Directory is not writable: {directory}"

        return True, "Valid PDF output path"

    except Exception as e:
        return False, f"Path validation error: {e}"


def is_valid_numeric_input(value):
    """Check if value can be converted to a number"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_setting_value(key, value):
    """Validate and convert setting values based on key type.

    Args:
        key: Setting key (used to determine validation rules)
        value: Value to validate and convert

    Returns:
        tuple: (is_valid, converted_value, error_message)
    """
    try:
        if "_tracking" in key:
            # Tracking values can be float (including negative)
            converted_value = float(value)
            return True, converted_value, None
        else:
            # Other settings must be positive integers
            converted_value = int(float(value))
            if converted_value <= 0:
                return False, None, "must be > 0"
            return True, converted_value, None
    except (ValueError, TypeError):
        return False, None, f"invalid value: {value}"


# =============================================================================
# Error Handling and Logging
# =============================================================================


def log_error(error, context=""):
    """Log error with context information"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    context_str = f" [{context}]" if context else ""
    print(f"[{timestamp}] ERROR{context_str}: {error}")


def safe_execute(operation_name, func, *args, **kwargs):
    """Safely execute an operation with standardized error handling.

    Args:
        operation_name: Name of the operation for error reporting
        func: Function to execute
        *args, **kwargs: Arguments to pass to the function

    Returns:
        bool: True if operation succeeded, False if it failed
    """
    try:
        func(*args, **kwargs)
        return True
    except Exception as e:
        print(f"Error in {operation_name}: {e}")
        traceback.print_exc()
        return False


def safe_font_load(font_path):
    """Safely attempt to load a font file"""
    try:
        from fontTools.ttLib import TTFont

        normalized_path = normalize_path(font_path)

        valid, message = validate_font_path(normalized_path)
        if not valid:
            log_error(f"Font validation failed: {message}", "safe_font_load")
            return None

        return TTFont(normalized_path)

    except Exception as e:
        log_error(f"Failed to load font {font_path}: {e}", "safe_font_load")
        return None


# =============================================================================
# System Integration Utilities
# =============================================================================
