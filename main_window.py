# Main Window - Application window and controller

import sys
import io
import os
import traceback
import datetime
from itertools import product
import vanilla
import AppKit
from PyObjCTools import AppHelper

from core_config import (
    WINDOW_TITLE,
    SETTINGS_PATH,
    SCRIPT_DIR,
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
)
from proof_config import (
    get_proof_default_font_size,
    proof_supports_formatting,
)
from font_manager import FontManager
from variable_font_utils import (
    product_dict,
    variableFont,
    pairStaticStyles,
)
from font_utils import filteredCharset
from stepper_cell import (
    StepperList2Cell,
    get_stepper_config_for_setting,
    register_row_setting,
    clear_row_settings,
)
from character_analysis import categorize
from proof_generation import (
    charsetProof,
    spacingProof,
)
from proof_handlers import (
    ProofContext,
    get_proof_handler,
    create_unique_proof_key,
    clear_handler_cache,
)
from settings_manager import Settings, ProofSettingsManager, AppSettingsManager
from files_tab import FilesTab
from controls_tab import ControlsTab
from pdf_manager import PDFManager
from proof_config import (
    get_proof_settings_mapping,
    get_proof_by_storage_key,
    get_proof_by_settings_key,
)
from PyObjCTools.AppHelper import callAfter
from vanilla.dialogs import askYesNo, getFile, message
from core_config import PAGE_FORMAT_OPTIONS
import drawBot as db


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
    """Redirect stdout/stderr to a text box."""

    def __init__(self, textBox):
        self.textBox = textBox

    def write(self, text):
        """Write text to the text box."""
        if hasattr(self.textBox, "set"):
            current_text = self.textBox.get()
            new_text = current_text + text
            self.textBox.set(new_text)

    def flush(self):
        """Flush method for compatibility."""
        pass


class ProofSettingsKeyGenerator:
    """Centralized generator for all proof settings keys."""

    @staticmethod
    def font_size_key(proof_key):
        """Generate font size key."""
        return f"{proof_key}_fontSize"

    @staticmethod
    def columns_key(proof_key):
        """Generate columns key."""
        return f"{proof_key}_cols"

    @staticmethod
    def paragraphs_key(proof_key):
        """Generate paragraphs key."""
        return f"{proof_key}_para"

    @staticmethod
    def tracking_key(proof_key):
        """Generate tracking key."""
        return f"{proof_key}_tracking"

    @staticmethod
    def alignment_key(proof_key):
        """Generate alignment key."""
        return f"{proof_key}_align"

    @staticmethod
    def otf_prefix(proof_key):
        """Generate OpenType feature prefix."""
        return f"otf_{proof_key}_"

    @staticmethod
    def otf_feature_key(proof_key, feature_tag):
        """Generate OpenType feature key."""
        return f"otf_{proof_key}_{feature_tag}"


class ProofWindow:
    """Main application window and controller."""

    # Class constants
    ALIGNMENT_OPTIONS = ["left", "center", "right"]

    # Proof name to key mapping - centralized constant
    PROOF_NAME_TO_KEY = {
        "Filtered Character Set": "filtered_character_set",
        "Spacing Proof": "spacing_proof",
        "Basic Paragraph Large": "basic_paragraph_large",
        "Diacritic Words Large": "diacritic_words_large",
        "Basic Paragraph Small": "basic_paragraph_small",
        "Paired Styles Paragraph Small": "paired_styles_paragraph_small",
        "Generative Text Small": "generative_text_small",
        "Diacritic Words Small": "diacritic_words_small",
        "Misc Paragraph Small": "misc_paragraph_small",
        "Ar Character Set": "ar_character_set",
        "Ar Paragraph Large": "ar_paragraph_large",
        "Fa Paragraph Large": "fa_paragraph_large",
        "Ar Paragraph Small": "ar_paragraph_small",
        "Fa Paragraph Small": "fa_paragraph_small",
        "Ar Vocalization Paragraph Small": "ar_vocalization_paragraph_small",
        "Ar-Lat Mixed Paragraph Small": "ar_lat_mixed_paragraph_small",
        "Ar Numbers Small": "ar_numbers_small",
    }

    def __init__(self):
        # Close any existing windows with the same title
        close_existing_windows(WINDOW_TITLE)

        # Initialize settings and font manager
        self.settings = Settings(SETTINGS_PATH)
        self.font_manager = FontManager(self.settings)

        # Initialize settings managers
        self.proof_settings_manager = ProofSettingsManager(
            self.settings, self.font_manager
        )
        self.app_settings_manager = AppSettingsManager(self.settings)

        # Initialize PDF manager
        self.pdf_manager = PDFManager(self.settings)

        # Initialize proof-specific settings storage (deprecated - use proof_settings_manager)
        # Get proof types with settings keys from registry
        settings_mapping = get_proof_settings_mapping()
        self.proof_types_with_otf = [
            (key, name) for name, key in settings_mapping.items()
        ]
        self.default_on_features = DEFAULT_ON_FEATURES
        self.proof_settings = self.proof_settings_manager.proof_settings
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
        self.controlsTab.integrate_preview_view(self.pdf_manager.get_preview_view())

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
        return self.proof_settings_manager.get_proof_font_size(proof_identifier)

    def _get_font_features(self):
        """Get OpenType features from the first loaded font."""
        if self.font_manager.fonts:
            try:
                return db.listOpenTypeFeatures(self.font_manager.fonts[0])
            except Exception:
                return []
        return []

    def _build_feature_settings(self, proof_key, feature_tags):
        """Build feature settings list for a given proof and feature tags."""
        feature_items = []
        for tag in feature_tags:
            # Skip hidden features
            if tag in HIDDEN_FEATURES:
                continue

            feature_key = ProofSettingsKeyGenerator.otf_feature_key(proof_key, tag)

            # Special handling for Spacing_Proof kern feature
            if proof_key == "spacing_proof" and tag == "kern":
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
        return feature_items

    def save_all_settings(self):
        """Save all current settings to the settings file."""

        def _save_operation():
            # Save proof options
            proof_options_items = self.controlsTab.group.proofOptionsList.get()
            for item in proof_options_items:
                proof_name = item[
                    "Option"
                ]  # Use the actual proof name (including numbers)
                base_option = item.get(
                    "_original_option", proof_name
                )  # Get original option name
                enabled = item["Enabled"]

                if base_option == "Show Baselines/Grid":
                    self.settings.set_proof_option("showBaselines", enabled)
                else:
                    # For unique proof names, use a sanitized version as the key
                    unique_key = create_unique_proof_key(proof_name)
                    self.settings.set_proof_option(unique_key, enabled)

            # Save proof-specific settings
            self.settings.set_proof_settings(self.proof_settings)

            # Save the settings file
            self.settings.save()

        self._safe_execute("save_all_settings", _save_operation)

    def resetSettingsCallback(self, sender):
        """Handle the Reset Settings button click."""

        def _reset_operation():
            # Show confirmation dialog
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
                    "show_baselines",
                    "filtered_character_set",
                    "spacing_proof",
                    "basic_paragraph_large",
                    "diacritic_words_large",
                    "basic_paragraph_small",
                    "paired_styles_paragraph_small",
                    "generative_text_small",
                    "diacritic_words_small",
                    "misc_paragraph_small",
                    "ar_character_set",
                    "ar_paragraph_large",
                    "fa_paragraph_large",
                    "ar_paragraph_small",
                    "fa_paragraph_small",
                    "ar_vocalization_paragraph_small",
                    "ar_lat_mixed_paragraph_small",
                    "ar_numbers_small",
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

        self._safe_execute("resetSettingsCallback", _reset_operation)

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

        def _cleanup_operation():
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

        # Use silent error handling for cleanup
        try:
            _cleanup_operation()
        except:
            pass  # Don't let any error prevent exit

        # Force exit the Python process
        import os

        os._exit(0)

    def generateCallback(self, sender):
        """Handle the Generate Proof button click."""

        def _generate_operation():
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

                # Get mapping from proof_config
                display_name_to_settings_key = get_proof_settings_mapping()

                # Process settings for both old-style and new unique proof identifiers
                for item in proof_options_items:
                    if not item["Enabled"]:
                        continue

                    proof_name = item["Option"]

                    # Always use the unique identifier for settings keys to ensure consistency
                    # This handles both original proofs and numbered duplicates uniformly
                    unique_key = create_unique_proof_key(proof_name)

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
                        settings_key = "basic_paragraph_small"

                    # Use centralized key generation
                    cols_key = ProofSettingsKeyGenerator.columns_key(unique_key)
                    para_key = ProofSettingsKeyGenerator.paragraphs_key(unique_key)
                    otf_prefix = ProofSettingsKeyGenerator.otf_prefix(unique_key)

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

        self._safe_execute("generateCallback", _generate_operation)

    def initialize_proof_settings(self):
        """Initialize proof-specific settings storage using the settings manager."""
        # Clear handler cache when settings change
        clear_handler_cache()

        # Delegate to the proof settings manager
        self.proof_settings_manager.initialize_proof_settings()

        # Update our reference to the proof settings
        self.proof_settings = self.proof_settings_manager.proof_settings

        # Refresh proof options list to show/hide Arabic proofs based on loaded fonts
        if hasattr(self, "controlsTab") and self.controlsTab:
            self.controlsTab.refresh_proof_options_list()

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
                    "cellClass": StepperList2Cell,
                },
            ],
            editCallback=self.numericSettingsEditCallback,
        )

        # Align control (standalone)
        popover.alignLabel = vanilla.TextBox((10, 245, 100, 20), "Alignment:")
        popover.alignPopUp = vanilla.PopUpButton(
            (120, 245, 100, 20),
            self.ALIGNMENT_OPTIONS,
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
        font_size_key = ProofSettingsKeyGenerator.font_size_key(proof_key)
        # Set default font size based on proof type using registry
        default_font_size = get_proof_default_font_size(proof_key)

        font_size_value = self.proof_settings.get(font_size_key, default_font_size)
        numeric_items.append(
            {"Setting": "Font Size", "Value": font_size_value, "_key": font_size_key}
        )

        # Columns setting with appropriate defaults (skip for certain proofs)
        if proof_key not in ["filtered_character_set", "ar_character_set"]:
            cols_key = ProofSettingsKeyGenerator.columns_key(proof_key)

            # Get proof info from registry
            proof_info = get_proof_by_storage_key(proof_key)
            if proof_info:
                default_cols = proof_info["default_cols"]
            else:
                default_cols = 2  # Fallback

            cols_value = self.proof_settings.get(cols_key, default_cols)
            numeric_items.append(
                {"Setting": "Columns", "Value": cols_value, "_key": cols_key}
            )

        # Paragraphs setting (only for proofs that have paragraphs)
        # Get proof info from registry
        proof_info = get_proof_by_settings_key(proof_key)
        if proof_info and proof_info["has_paragraphs"]:
            para_key = ProofSettingsKeyGenerator.paragraphs_key(proof_key)
            para_value = self.proof_settings.get(para_key, 5)
            numeric_items.append(
                {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
            )

        # Add tracking for supported proof types
        if proof_supports_formatting(proof_key):
            tracking_key = ProofSettingsKeyGenerator.tracking_key(proof_key)
            tracking_value = self.proof_settings.get(tracking_key, 0)
            numeric_items.append(
                {"Setting": "Tracking", "Value": tracking_value, "_key": tracking_key}
            )

        popover.numericList.set(numeric_items)

        # Populate the row setting registry for stepper auto-configuration
        clear_row_settings()
        for row_index, item in enumerate(numeric_items):
            if "Setting" in item:
                register_row_setting(row_index, item["Setting"])

        # Configure steppers for the numeric settings
        self.configureSteppersForNumericList(popover.numericList, numeric_items)

        # Update features settings using helper method
        feature_tags = self._get_font_features()
        feature_items = self._build_feature_settings(proof_key, feature_tags)
        popover.featuresList.set(feature_items)

        # Update alignment control for supported proof types
        if proof_supports_formatting(proof_key):
            # Update align control
            align_key = ProofSettingsKeyGenerator.alignment_key(proof_key)
            align_value = self.proof_settings.get(align_key, "left")
            if align_value in self.ALIGNMENT_OPTIONS:
                popover.alignPopUp.set(self.ALIGNMENT_OPTIONS.index(align_value))
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
        if 0 <= selected_idx < len(self.ALIGNMENT_OPTIONS):
            align_value = self.ALIGNMENT_OPTIONS[selected_idx]
            align_key = ProofSettingsKeyGenerator.alignment_key(self.current_proof_key)
            self.proof_settings[align_key] = align_value

    def stepperChangeCallback(self, setting_key, value):
        """Handle stepper value changes."""
        is_valid, converted_value, error_msg = self._validate_setting_value(
            setting_key, value
        )
        if not is_valid:
            print(f"Invalid value for setting: {error_msg}")
            return
        self.proof_settings[setting_key] = converted_value

    def configureSteppersForNumericList(self, numeric_list, items):
        """Configure stepper cells in the numeric list with appropriate min/max/increment values."""

        # Use a delayed call to allow the table to be fully rendered first
        def configure_delayed():
            # Get the NSTableView from the List2 object
            table_view = numeric_list.getNSTableView()

            # Access the data source to get cell wrappers
            data_source = table_view.dataSource()

            # Configure steppers for each row
            for row_index, item in enumerate(items):
                if "Setting" in item:
                    setting_name = item["Setting"]
                    stepper_config = get_stepper_config_for_setting(setting_name)

                    # Get the NSView for the "Value" column (column index 1)
                    try:
                        ns_cell_view = table_view.viewAtColumn_row_(
                            1, row_index, makeIfNecessary=True
                        )
                    except AttributeError:
                        # Try alternative method names
                        try:
                            ns_cell_view = table_view.makeViewWithIdentifier_owner_(
                                "Value", data_source
                            )
                        except:
                            continue

                    # Try multiple approaches to get the vanilla wrapper
                    vanilla_wrapper = None

                    # Approach 1: Get from data source cell wrappers
                    if ns_cell_view and hasattr(data_source, "_cellWrappers"):
                        vanilla_wrapper = data_source._cellWrappers.get(ns_cell_view)

                    # Approach 2: Check if the NSView has a vanillaWrapper method
                    if (
                        not vanilla_wrapper
                        and ns_cell_view
                        and hasattr(ns_cell_view, "vanillaWrapper")
                    ):
                        try:
                            vanilla_wrapper = ns_cell_view.vanillaWrapper()
                        except:
                            pass

                    # Approach 3: Check if NSView is actually the vanilla wrapper
                    if not vanilla_wrapper and hasattr(
                        ns_cell_view, "setStepperConfiguration_"
                    ):
                        vanilla_wrapper = ns_cell_view

                    if vanilla_wrapper and hasattr(
                        vanilla_wrapper, "setStepperConfiguration_"
                    ):
                        vanilla_wrapper.setStepperConfiguration_(stepper_config)

                        # Set the callback for this specific cell
                        if "_key" in item:
                            vanilla_wrapper.setChangeCallback_withKey_(
                                self.stepperChangeCallback, item["_key"]
                            )

        # Use performSelector to delay the configuration
        callAfter(configure_delayed)

        # Try immediate configuration as well
        configure_delayed()

    def numericSettingsEditCallback(self, sender):
        """Handle edits to numeric settings in popover."""
        items = sender.get()
        for item in items:
            if "_key" in item:
                key = item["_key"]
                value = item["Value"]
                is_valid, converted_value, error_msg = self._validate_setting_value(
                    key, item["Value"]
                )
                if not is_valid:
                    print(f"Invalid value for {item['Setting']}: {error_msg}")
                    continue
                self.proof_settings[key] = converted_value

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
        # Initialize PDF generation
        if not self.pdf_manager.begin_pdf_generation():
            print("Error: Failed to initialize PDF generation")
            return None

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
            if not (
                hasattr(controls, "group")
                and hasattr(controls.group, "proofOptionsList")
            ):
                print("Error: Could not access proof options list")
                return None

            proof_options_items = controls.group.proofOptionsList.get()

            # Pre-create context once for efficiency
            proof_context = ProofContext(
                full_character_set=fullCharacterSet,
                axes_product=axesProduct,
                ind_font=indFont,
                paired_static_styles=pairedStaticStyles,
                otfeatures_by_proof=otfeatures_by_proof,
                cols_by_proof=cols_by_proof,
                paras_by_proof=paras_by_proof,
                cat=cat,
                proof_name=None,  # Will be updated per proof
            )

            # Generate each enabled proof using the optimized handler system
            for item in proof_options_items:
                if not item["Enabled"]:
                    continue

                proof_name = item["Option"]
                base_proof_type = item.get("_original_option", proof_name)

                # Update context for this specific proof
                proof_context.proof_name = proof_name

                # Get handler and generate proof
                handler = get_proof_handler(
                    base_proof_type,
                    proof_name,
                    self.proof_settings,
                    self.get_proof_font_size,
                )

                if handler:
                    try:
                        handler.generate_proof(proof_context)
                    except Exception as e:
                        print(f"Error generating proof '{proof_name}': {e}")
                        traceback.print_exc()
                        continue  # Continue with next proof
                else:
                    print(
                        f"Warning: No handler found for proof type '{base_proof_type}'"
                    )

        # Finalize PDF generation and save
        pdf_path = self.pdf_manager.end_pdf_generation(self.font_manager, now)
        print(datetime.datetime.now() - now)
        return pdf_path

    def addSettingsFileCallback(self, sender):
        """Handle the Add Settings File button click."""
        try:
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
                    message(
                        "Settings Loaded",
                        f"Settings have been loaded from:\n{settings_file_path}\n\n"
                        "Changes will now be saved to this file instead of the auto-save file.",
                        informativeText="You can use 'Reset Settings' to clear this file and return to auto-save mode.",
                    )
                else:
                    message(
                        "Error Loading Settings",
                        f"Failed to load settings from:\n{settings_file_path}\n\n"
                        "Please check that the file contains valid JSON and try again.",
                    )

        except Exception as e:
            print(f"Error loading settings file: {e}")
            traceback.print_exc()
            message("Error", f"An error occurred while loading the settings file:\n{e}")

    def refresh_controls_tab(self):
        """Refresh the controls tab with current settings values."""
        try:
            # Use the dynamic proof options list
            self.controlsTab.refresh_proof_options_list()

            # Update page format selection
            if hasattr(self.controlsTab.group, "pageFormatPopUp"):
                current_format = self.settings.get_page_format()
                if current_format in PAGE_FORMAT_OPTIONS:
                    self.controlsTab.group.pageFormatPopUp.set(
                        PAGE_FORMAT_OPTIONS.index(current_format)
                    )

        except Exception as e:
            print(f"Error refreshing controls tab: {e}")
            traceback.print_exc()

    def display_pdf(self, pdf_path):
        """Display a PDF in the preview."""
        return self.pdf_manager.display_pdf(pdf_path)

    def initialize_settings_for_proof(self, unique_proof_name, base_proof_type):
        """Initialize settings for a newly added proof instance."""
        # Delegate to the proof settings manager
        self.proof_settings_manager.initialize_settings_for_proof(
            unique_proof_name, base_proof_type
        )

        # Update our reference to the proof settings
        self.proof_settings = self.proof_settings_manager.proof_settings

    def update_proof_settings_popover_for_instance(
        self, unique_proof_key, base_proof_type
    ):
        """Update the proof settings popover for a specific proof instance."""
        try:
            # Use centralized mapping
            base_proof_key = self.PROOF_NAME_TO_KEY.get(base_proof_type)
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
            font_size_key = ProofSettingsKeyGenerator.font_size_key(unique_proof_key)
            # Set default font size using registry
            default_font_size = get_proof_default_font_size(base_proof_key)

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
                "filtered_character_set",
                "ar_character_set",
            ]:
                cols_key = ProofSettingsKeyGenerator.columns_key(unique_proof_key)

                # Get proof info from registry
                proof_info = get_proof_by_storage_key(base_proof_key)
                if proof_info:
                    default_cols = proof_info["default_cols"]
                else:
                    default_cols = 2  # Fallback

                cols_value = self.proof_settings.get(cols_key, default_cols)
                numeric_items.append(
                    {"Setting": "Columns", "Value": cols_value, "_key": cols_key}
                )

            # Paragraphs setting (only for proofs that have paragraphs)
            # Get proof info from registry
            proof_info = get_proof_by_settings_key(base_proof_key)
            if proof_info and proof_info["has_paragraphs"]:
                para_key = ProofSettingsKeyGenerator.paragraphs_key(unique_proof_key)
                para_value = self.proof_settings.get(para_key, 5)
                numeric_items.append(
                    {"Setting": "Paragraphs", "Value": para_value, "_key": para_key}
                )

            # Add tracking for supported proof types
            if proof_supports_formatting(base_proof_key):
                tracking_key = ProofSettingsKeyGenerator.tracking_key(unique_proof_key)
                tracking_value = self.proof_settings.get(tracking_key, 0)
                numeric_items.append(
                    {
                        "Setting": "Tracking",
                        "Value": tracking_value,
                        "_key": tracking_key,
                    }
                )

            popover.numericList.set(numeric_items)

            # Populate the row setting registry for stepper auto-configuration
            clear_row_settings()
            for row_index, item in enumerate(numeric_items):
                if "Setting" in item:
                    register_row_setting(row_index, item["Setting"])

            # Configure steppers for the numeric settings
            self.configureSteppersForNumericList(popover.numericList, numeric_items)

            # Update OpenType features for this specific instance using helper method
            feature_tags = self._get_font_features()
            feature_items = self._build_feature_settings(unique_proof_key, feature_tags)
            popover.featuresList.set(feature_items)

            # Update alignment control for supported proof types
            if proof_supports_formatting(base_proof_key):
                # Update align control
                align_key = ProofSettingsKeyGenerator.alignment_key(unique_proof_key)
                align_value = self.proof_settings.get(align_key, "left")
                if align_value in self.ALIGNMENT_OPTIONS:
                    popover.alignPopUp.set(self.ALIGNMENT_OPTIONS.index(align_value))
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
            traceback.print_exc()

    def _validate_setting_value(self, key, value):
        # Validate and convert setting values based on key type
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

    def _safe_execute(self, operation_name, func, *args, **kwargs):
        # Safely execute an operation with standardized error handling
        try:
            func(*args, **kwargs)
            return True
        except Exception as e:
            print(f"Error in {operation_name}: {e}")
            traceback.print_exc()
            return False
