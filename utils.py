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


def normalize_path(path):
    """Normalize path from various input types (URL, string, etc.)"""
    if not path:
        return ""

    # Handle URL format
    if isinstance(path, str) and path.startswith("file://"):
        parsed = urlparse(path)
        path = unquote(parsed.path)

    return os.path.abspath(os.path.expanduser(path))


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


# =============================================================================
# Error Handling and Logging
# =============================================================================


def log_error(error, context=""):
    """Log error with context information"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    context_str = f" [{context}]" if context else ""
    print(f"[{timestamp}] ERROR{context_str}: {error}")


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


def handle_ui_callback_error(callback_func):
    """Decorator to handle UI callback errors gracefully"""

    def wrapper(*args, **kwargs):
        try:
            return callback_func(*args, **kwargs)
        except Exception as e:
            error_msg = f"UI callback error in {callback_func.__name__}: {e}"
            log_error(error_msg, "UI Callback")
            # In a UI context, you might want to show a user-friendly dialog
            return None

    return wrapper


def format_exception_info(exc_info=None):
    """Format exception information for logging"""
    try:
        if exc_info is None:
            exc_info = traceback.format_exc()

        return f"Exception details:\n{exc_info}"
    except Exception:
        return "Unable to format exception information"


# =============================================================================
# Data Processing Utilities
# =============================================================================


def deep_merge_dicts(dict1, dict2):
    """Deep merge two dictionaries"""
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def safe_get_nested_value(data, key_path, default=None):
    """Safely get nested dictionary value using dot notation"""
    try:
        keys = key_path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current
    except Exception:
        return default


def safe_set_nested_value(data, key_path, value):
    """Safely set nested dictionary value using dot notation"""
    try:
        keys = key_path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value
        return True
    except Exception as e:
        log_error(f"Failed to set nested value {key_path}: {e}")
        return False


# =============================================================================
# System Integration Utilities
# =============================================================================


def open_in_external_app(file_path):
    """Open file in external application (macOS)"""
    try:
        import subprocess

        normalized_path = normalize_path(file_path)

        if not os.path.exists(normalized_path):
            log_error(f"Cannot open non-existent file: {file_path}")
            return False

        subprocess.run(["open", normalized_path], check=True)
        return True

    except Exception as e:
        log_error(f"Failed to open file externally: {e}")
        return False


def get_user_documents_folder():
    """Get user's Documents folder"""
    try:
        home = os.path.expanduser("~")
        documents = os.path.join(home, "Documents")
        return documents if os.path.exists(documents) else home
    except Exception:
        return os.path.expanduser("~")


def is_dark_mode_enabled():
    """Check if macOS is in dark mode"""
    try:
        import subprocess

        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == "Dark"
    except Exception:
        return False  # Default to light mode if unable to detect
