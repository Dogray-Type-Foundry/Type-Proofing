# Font Manager - Core font management functionality

import os
import drawBot as db
from font_utils import (
    get_ttfont,
    normalize_font_path,
    is_valid_font_file,
    get_font_family_name,
    filteredCharset,
)
from character_analysis import check_arabic_support
from variable_font_utils import (
    get_all_font_axes,
    parse_axis_values_string,
    format_axis_values,
    parse_axis_value,
)


class FontManager:
    """Manages font information and processing."""

    def __init__(self, settings=None):
        self.settings = settings
        self.fonts = tuple()
        self.font_info = {}
        self.axis_values_by_font = {}

        # Load fonts from settings if available
        if self.settings:
            saved_fonts = self.settings.get_fonts()
            if saved_fonts:
                self.fonts = tuple(saved_fonts)
                self.update_font_info()
                # Load axis values from settings
                for font_path in self.fonts:
                    axis_values = self.settings.get_font_axis_values(font_path)
                    if axis_values:
                        self.axis_values_by_font[font_path] = axis_values

    def add_fonts(self, paths):
        """Add new fonts to the collection."""
        valid_paths = [
            normalize_font_path(p)
            for p in paths
            if is_valid_font_file(normalize_font_path(p))
        ]

        # Only add fonts not already in the list
        new_fonts = [p for p in valid_paths if p not in self.fonts]
        if not new_fonts:
            return False

        self.fonts = tuple(list(self.fonts) + new_fonts)
        self.update_font_info()

        # Save to settings
        if self.settings:
            self.settings.set_fonts(list(self.fonts))

        return True

    def remove_fonts_by_indices(self, indices):
        """Remove fonts by their indices."""
        if not indices:
            return
        fonts_list = list(self.fonts)
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(fonts_list):
                removed = fonts_list.pop(index)
                if removed in self.axis_values_by_font:
                    del self.axis_values_by_font[removed]
        self.fonts = tuple(fonts_list)
        self.update_font_info()

        # Save to settings
        if self.settings:
            self.settings.set_fonts(list(self.fonts))
            # Also clean up axis values in settings
            saved_axis_values = self.settings.data.get("fonts", {}).get(
                "axis_values", {}
            )
            for font_path in list(saved_axis_values.keys()):
                if font_path not in self.fonts:
                    # Use the proper method to remove axis values
                    self.settings.set_font_axis_values(font_path, {})

    def update_font_info(self):
        """Update font information for all loaded fonts."""
        self.font_info = {}
        self.axis_values_by_font = {}

        for font_path in self.fonts:
            try:
                font_info = {
                    "features": db.listOpenTypeFeatures(font_path),
                    "name": os.path.basename(font_path),
                }

                # Process variable font axes
                variableDict = db.listFontVariations(font_path)
                axes_dict = {}

                if variableDict:
                    for axis, data in variableDict.items():
                        # Get unique values in order: min, default, max
                        values = []
                        for key in ("minValue", "defaultValue", "maxValue"):
                            v = data.get(key)
                            if v is not None and v not in values:
                                # Convert to int if it's a whole number
                                values.append(
                                    int(v)
                                    if isinstance(v, (int, float)) and v == int(v)
                                    else v
                                )
                        axes_dict[axis] = values

                font_info["axes"] = axes_dict
                self.axis_values_by_font[font_path] = axes_dict
                self.font_info[font_path] = font_info

            except Exception as e:
                print(f"Error processing font {font_path}: {e}")
                self.font_info[font_path] = {
                    "axes": {},
                    "name": os.path.basename(font_path),
                }
                self.axis_values_by_font[font_path] = {}

    def get_table_data(self):
        """Get formatted data for the file table display."""
        table_data = []
        for font_path in self.fonts:
            info = self.font_info.get(font_path, {})
            row = {"name": info.get("name", os.path.basename(font_path))}
            # Format axes dict as string for display
            axes_str = "; ".join(
                f"{k}: {format_axis_values(v)}"
                for k, v in self.axis_values_by_font.get(font_path, {}).items()
            )
            row["axes"] = axes_str
            row["_path"] = font_path
            table_data.append(row)
        return table_data

    def update_axis_values_from_table(self, table_data):
        """Update axis values from table data."""
        for row in table_data:
            font_path = row.get("_path")
            if not font_path:
                continue

            axes_str = row.get("axes", "")
            axes_dict = {}

            for part in axes_str.split(";"):
                part = part.strip()
                if not part or ":" not in part:
                    continue

                axis, values_str = part.split(":", 1)
                values = parse_axis_values_string(values_str)
                if values:  # Only add if we have valid values
                    axes_dict[axis.strip()] = values

            self.axis_values_by_font[font_path] = axes_dict

            # Save to settings
            if self.settings:
                self.settings.set_font_axis_values(font_path, axes_dict)

    def update_axis_values_from_individual_axes_table(self, table_data, all_axes):
        """Update axis values from table data with individual axis columns."""
        for row in table_data:
            font_path = row.get("_path")
            if not font_path:
                continue

            axes_dict = {}
            for axis in all_axes:
                values_str = row.get(axis, "")
                if values_str.strip():
                    values = parse_axis_values_string(values_str)
                    if values:  # Only add if we have valid values
                        axes_dict[axis] = values

            self.axis_values_by_font[font_path] = axes_dict

            # Save to settings
            if self.settings:
                self.settings.set_font_axis_values(font_path, axes_dict)

    def get_family_name(self):
        """Get family name from the first font."""
        return get_font_family_name(self.fonts[0]) if self.fonts else ""

    def get_axis_values_for_font(self, font_path):
        """Get axis values for a specific font."""
        return self.axis_values_by_font.get(font_path, {})

    def has_arabic_support(self):
        """Check if any loaded font supports Arabic characters."""
        if not self.fonts:
            return False

        for font_path in self.fonts:
            try:
                charset = filteredCharset(font_path)
                if check_arabic_support(charset):
                    return True
            except Exception as e:
                print(f"Error checking Arabic support in {font_path}: {e}")
                continue

        return False

    def load_fonts(self, font_paths):
        """Load fonts from a list of paths."""
        if not font_paths:
            return False

        valid_paths = [path for path in font_paths if is_valid_font_file(path)]

        if not valid_paths:
            return False

        self.fonts = tuple(valid_paths)
        self.update_font_info()

        # Save to settings
        if self.settings:
            self.settings.set_fonts(list(self.fonts))

        return True

    def get_all_axes(self):
        """Get all unique axes across all loaded fonts in their original font order."""
        return get_all_font_axes(self.fonts)

    def get_table_data_with_individual_axes(self):
        """Get formatted data for the file table display with individual axis columns."""
        all_axes = self.get_all_axes()
        table_data = []

        for font_path in self.fonts:
            info = self.font_info.get(font_path, {})
            row = {"name": info.get("name", os.path.basename(font_path))}

            # Add each axis as a separate column
            axes_dict = self.axis_values_by_font.get(font_path, {})
            for axis in all_axes:
                if axis in axes_dict:
                    # Format axis values as comma-separated string
                    axis_values = axes_dict[axis]
                    row[axis] = format_axis_values(axis_values)
                else:
                    row[axis] = ""  # Empty for fonts that don't have this axis

            row["_path"] = font_path
            table_data.append(row)

        return table_data, all_axes
