# Main Window - Application window and controller

import sys
import io
import os
import traceback
import datetime
import vanilla
import AppKit
import drawBot as db
from PyObjCTools import AppHelper
from PyObjCTools.AppHelper import callAfter
from vanilla.dialogs import askYesNo, getFile, message

from config import (
    WINDOW_TITLE,
    SETTINGS_PATH,
    SCRIPT_DIR,
    DEFAULT_ON_FEATURES,
    HIDDEN_FEATURES,
    PAGE_FORMAT_OPTIONS,
    PAGE_DIMENSIONS,
    WINDOW_SIZE,
    WINDOW_MIN_SIZE,
    SPLIT_MAIN_SIZE,
    SPLIT_DEBUG_SIZE,
)
from config import (
    proof_supports_formatting,
    get_proof_settings_mapping,
    get_proof_by_storage_key,
    get_proof_by_settings_key,
    proof_has_custom_text,
    proof_has_categories,
    proof_is_multi_style,
)
from fonts import FontManager
from fonts import product_dict, variableFont, pairStaticStyles
from fonts import filteredCharset
from settings import validate_setting_value, safe_execute
from ui import (
    StepperList2Cell,
    get_stepper_config_for_setting,
    register_row_setting,
    clear_row_settings,
)
from fonts import categorize
from proof import charsetProof, spacingProof
from proof import (
    ProofContext,
    get_proof_handler,
    clear_handler_cache,
    MultiStyleComparisonProofHandler,
)
from pdf_manager import PDFManager
from settings import (
    Settings,
    ProofSettingsManager,
    get_app_settings,
    make_settings_key,
    create_unique_proof_key,
)
from ui import FilesTab
from ui import ControlsTab


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


class ProofWindow:
    """Main application window and controller."""

    # Class constants
    ALIGNMENT_OPTIONS = ["left", "center", "right"]

    # ============ UI Helper Methods ============

    def _safe_callback(self, callback_name, operation_func):
        """Wrapper for safe callback execution with consistent error handling."""
        safe_execute(callback_name, operation_func)

    def _refresh_ui_components(self):
        """Refresh all UI components after settings changes."""
        self.controlsTab.refresh_proof_options_list()
        self.refresh_controls_tab()

    def _handle_settings_confirmation(self, message_text, action_func):
        """Handle confirmation dialogs for settings operations."""
        response = askYesNo("Confirm Action", message_text)
        if response:
            action_func()
            self._refresh_ui_components()

    def _validate_and_update_settings(
        self, items, key_field="_key", value_field="Value"
    ):
        """Validate and update settings from list items."""
        for item in items:
            if key_field in item:
                key = item[key_field]
                value = item[value_field]
                is_valid, converted_value, error_msg = validate_setting_value(
                    key, value
                )
                if not is_valid:
                    print(f"Invalid value for {item.get('Setting', key)}: {error_msg}")
                    continue
                self.proof_settings[key] = converted_value

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
        # No longer need app_settings_manager - use self.settings directly

        # Initialize PDF manager
        self.pdf_manager = PDFManager(self.settings)

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
            WINDOW_SIZE, WINDOW_TITLE, minSize=WINDOW_MIN_SIZE, closable=True
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
                dict(view=self.mainContent, identifier="main", size=SPLIT_MAIN_SIZE),
                dict(
                    view=self.debugTextEditor, identifier="debug", size=SPLIT_DEBUG_SIZE
                ),
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

    def _setup_category_controls(self, popover, proof_key, show=True):
        """Setup character category controls for popover."""
        controls = [
            (popover.categoryLabel, None),
            (popover.categoryUppercase, "uppercase_base"),
            (popover.categoryLowercase, "lowercase_base"),
            (popover.categoryNumbersSymbols, "numbers_symbols"),
            (popover.categoryPunctuation, "punctuation"),
            (popover.categoryAccented, "accented"),
        ]

        for control, category_key in controls:
            control.show(show)
            if show and category_key:
                setting_key = make_settings_key(proof_key, "cat", category_key)
                # Use the defaults from settings manager
                value = self.proof_settings_manager.proof_settings.get(
                    setting_key,
                    self.proof_settings_manager._CATEGORY_DEFAULTS.get(
                        category_key, True
                    ),
                )
                control.set(value)

    def _build_feature_settings(self, proof_key, feature_tags):
        """Build feature settings list for a given proof and feature tags."""
        return self.proof_settings_manager.get_opentype_features_for_proof(proof_key)

    def save_all_settings(self):
        """Save all current settings to the settings file."""

        def _save_operation():
            proof_options_items = self.controlsTab.group.proofOptionsList.get()
            self.proof_settings_manager.save_all_settings(proof_options_items)

        self._safe_callback("save_all_settings", _save_operation)

    def resetSettingsCallback(self, sender):
        """Handle the Reset Settings button click."""

        def _reset_action():
            # Reset settings to defaults (this also clears user_settings_file)
            self.settings.reset_to_defaults()

            # Override proof options to all be False (unchecked)
            # Use the centralized mapping to get all proof keys
            from config import get_proof_settings_mapping

            proof_option_keys = ["show_baselines"] + list(
                get_proof_settings_mapping().values()
            )
            for option_key in proof_option_keys:
                self.settings.set_proof_option(option_key, False)

            # Clear font manager
            self.font_manager.fonts = tuple()
            self.font_manager.font_info = {}
            self.font_manager.axis_values_by_font = {}

            # Reset table columns to base columns only
            self.filesTab.reset_table_columns()
            self.filesTab.update_table()
            self.filesTab.update_pdf_location_ui()
            self.initialize_proof_settings()
            print("Settings reset to defaults.")

        # Build confirmation message
        message_text = (
            "This will reset all settings to defaults and clear all loaded fonts."
        )
        if self.settings.user_settings_file:
            message_text += f"\n\nThis will also stop using the custom settings file:\n{self.settings.user_settings_file}"
        message_text += "\n\nAre you sure?"

        self._handle_settings_confirmation(message_text, _reset_action)

    def closeWindowCallback(self, sender):
        """Handle the Close Window button click."""
        self._perform_cleanup_and_exit()

    def windowCloseCallback(self, sender):
        """Handle the window close button (X) being pressed."""
        self._perform_cleanup_and_exit()

    def windowShouldCloseCallback(self, sender):
        """Handle the window should close event to ensure proper cleanup."""
        return True

    def _perform_cleanup_and_exit(self):
        """Perform cleanup and exit the application."""
        # Prevent multiple calls to this method
        if hasattr(self, "_exiting"):
            return
        self._exiting = True

        def _cleanup_operation():
            # Silent cleanup operations that should not fail the exit process
            cleanup_tasks = [
                lambda: self.settings.save() if hasattr(self, "settings") else None,
                lambda: (
                    setattr(sys, "stdout", self._original_stdout)
                    if hasattr(self, "_original_stdout")
                    else None
                ),
                lambda: (
                    setattr(sys, "stderr", self._original_stderr)
                    if hasattr(self, "_original_stderr")
                    else None
                ),
                lambda: AppHelper.stopEventLoop(),
            ]

            for task in cleanup_tasks:
                try:
                    task()
                except:
                    pass

        # Use silent error handling for cleanup
        try:
            _cleanup_operation()
        except:
            pass

        # Force exit the Python process
        os._exit(0)

    def generateCallback(self, sender):
        """Handle the Generate Proof button click."""

        def _generate_operation():
            # Save all current settings before generating
            self.save_all_settings()

            # Setup stdout/stderr redirection
            buffer = io.StringIO()
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = buffer

            try:
                setup_result = self._setup_proof_generation(self.controlsTab.group)
                if setup_result[0] is None:  # Check if setup failed
                    return

                fonts, userAxesValues, proof_options, proof_options_items = setup_result
                otfeatures_by_proof, cols_by_proof, paras_by_proof = (
                    self._build_proof_settings(proof_options_items)
                )

                # Generate and display proof
                output_path = self.run_proof(
                    userAxesValues,
                    proof_options,
                    otfeatures_by_proof,
                    cols_by_proof=cols_by_proof,
                    paras_by_proof=paras_by_proof,
                )
                if self.display_pdf(output_path):
                    self.tabSwitcher.set(
                        1
                    )  # Switch to Controls tab (which now has preview)
                    self.switchTab(self.tabSwitcher)

            except Exception as e:
                print(f"Error in proof generation: {e}")
                traceback.print_exc()
            finally:
                # Restore stdout/stderr and update debug output
                sys.stdout, sys.stderr = old_stdout, old_stderr
                self.debugTextEditor.set(buffer.getvalue())

        self._safe_callback("generateCallback", _generate_operation)

    def _setup_proof_generation(self, controls):
        """Setup variables for proof generation."""
        if not self.font_manager.fonts:
            print("No fonts loaded. Please add fonts first.")
            return None, None, None, None

        proof_options_items = controls.proofOptionsList.get()
        proof_options = {}

        # Read showBaselines from the standalone checkbox
        self.showBaselines = controls.showBaselinesCheckbox.get()
        db.showBaselines = self.showBaselines

        for item in proof_options_items:
            proof_options[item["Option"]] = bool(item["Enabled"])

        return self.font_manager.fonts, {}, proof_options, proof_options_items

    def _build_proof_settings(self, proof_options_items):
        """Build proof settings dictionaries using the settings manager."""
        return self.proof_settings_manager.build_proof_data_for_generation(
            proof_options_items
        )

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
        self.proof_settings_popover = vanilla.Popover((400, 1000))
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
        popover.numericLabel = vanilla.TextBox((10, 20, -10, 20), "Page Settings:")
        popover.numericList = vanilla.List2(
            (10, 40, -10, 140),
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
        popover.alignLabel = vanilla.TextBox((10, 190, 100, 20), "Alignment:")
        popover.alignPopUp = vanilla.PopUpButton(
            (120, 190, 100, 20),
            self.ALIGNMENT_OPTIONS,
            callback=self.alignPopUpCallback,
        )

        # Character Category controls (for Filtered Character Set, Spacing Proof, Multi-Style Comparison)
        popover.categoryLabel = vanilla.TextBox(
            (10, 220, -10, 20), "Character Categories:"
        )

        # Character category checkboxes
        popover.categoryUppercase = vanilla.CheckBox(
            (20, 240, -10, 20),
            "Uppercase Base",
            callback=self.characterCategoryCallback,
        )
        popover.categoryLowercase = vanilla.CheckBox(
            (20, 260, -10, 20),
            "Lowercase Base",
            callback=self.characterCategoryCallback,
        )
        popover.categoryNumbersSymbols = vanilla.CheckBox(
            (20, 280, -10, 20),
            "Numbers & Symbols",
            callback=self.characterCategoryCallback,
        )
        popover.categoryPunctuation = vanilla.CheckBox(
            (20, 300, -10, 20), "Punctuation", callback=self.characterCategoryCallback
        )
        popover.categoryAccented = vanilla.CheckBox(
            (20, 320, -10, 20),
            "Accented Characters",
            callback=self.characterCategoryCallback,
        )

        # Hide character category controls by default
        popover.categoryLabel.show(False)
        popover.categoryUppercase.show(False)
        popover.categoryLowercase.show(False)
        popover.categoryNumbersSymbols.show(False)
        popover.categoryPunctuation.show(False)
        popover.categoryAccented.show(False)

        # Custom text input (for Custom Text and Multi-Style Comparison proofs)
        popover.customTextLabel = vanilla.TextBox((10, 350, -10, 20), "Custom Text:")
        popover.customTextEditor = vanilla.TextEditor(
            (10, 370, -10, 160), "", callback=self.customTextEditCallback
        )
        popover.markupToggle = vanilla.CheckBox(
            (200, 350, -10, 20),
            "Enable Markup",
            callback=self.markupToggleCallback,
        )
        popover.generateOnceToggle = vanilla.CheckBox(
            (10, 540, -10, 20),
            "Generate Once",
            callback=self.generateOnceToggleCallback,
        )
        popover.defaultFontLabel = vanilla.TextBox((10, 565, 100, 20), "Default Font:")
        popover.defaultFontPopup = vanilla.PopUpButton(
            (110, 565, -10, 20),
            [],
            callback=self.defaultFontPopupCallback,
        )
        popover.customTextLabel.show(False)
        popover.customTextEditor.show(False)
        popover.markupToggle.show(False)
        popover.generateOnceToggle.show(False)
        popover.defaultFontLabel.show(False)
        popover.defaultFontPopup.show(False)

        # Styles selector (for Multi-Style Comparison)
        popover.stylesLabel = vanilla.TextBox((10, 600, -10, 20), "Styles to Compare:")
        popover.stylesList = vanilla.List2(
            (10, 620, -10, 200),
            [],
            columnDescriptions=[
                {
                    "identifier": "Style",
                    "title": "Style",
                    "key": "Style",
                    "width": 250,
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
            editCallback=self.stylesEditCallback,
        )
        popover.stylesLabel.show(False)
        popover.stylesList.show(False)

        # OpenType features list
        popover.featuresLabel = vanilla.TextBox(
            (10, 830, -10, 20), "OpenType Features:"
        )
        popover.featuresList = vanilla.List2(
            (10, 850, -10, -10),
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
        self.current_proof_key = proof_key
        self.current_base_proof_type = proof_label
        popover = self.proof_settings_popover

        # Get numeric settings from settings manager
        numeric_items = self.proof_settings_manager.get_popover_settings_for_proof(
            proof_key
        )
        popover.numericList.set(numeric_items)

        # Populate the row setting registry for stepper auto-configuration
        clear_row_settings()
        for row_index, item in enumerate(numeric_items):
            if "Setting" in item:
                register_row_setting(row_index, item["Setting"])

        # Configure steppers for the numeric settings
        self.configureSteppersForNumericList(popover.numericList, numeric_items)

        # Update features settings using settings manager
        feature_items = self.proof_settings_manager.get_opentype_features_for_proof(
            proof_key
        )
        popover.featuresList.set(feature_items)

        # Update alignment control for supported proof types
        if proof_supports_formatting(proof_key):
            align_value = self.proof_settings_manager.get_alignment_value_for_proof(
                proof_key
            )
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

        # Update character category controls
        if proof_has_categories(proof_key):
            self._setup_category_controls(popover, proof_key, show=True)
        else:
            self._setup_category_controls(popover, proof_key, show=False)

        # Update custom text editor
        if proof_has_custom_text(proof_key):
            text_key = make_settings_key(proof_key, "customText")
            existing_text = self.proof_settings.get(text_key, "")
            popover.customTextEditor.set(existing_text)
            popover.customTextLabel.show(True)
            popover.customTextEditor.show(True)
            if not proof_is_multi_style(proof_key):
                markup_key = make_settings_key(proof_key, "markupEnabled")
                popover.markupToggle.set(self.proof_settings.get(markup_key, False))
                popover.markupToggle.show(True)
                # Generate Once toggle and font selector
                once_key = make_settings_key(proof_key, "generateOnce")
                generate_once = self.proof_settings.get(once_key, False)
                popover.generateOnceToggle.set(generate_once)
                popover.generateOnceToggle.show(True)
                self._update_default_font_popup(popover, proof_key, generate_once)
            else:
                popover.markupToggle.show(False)
                popover.generateOnceToggle.show(False)
                popover.defaultFontLabel.show(False)
                popover.defaultFontPopup.show(False)
        else:
            popover.customTextLabel.show(False)
            popover.customTextEditor.show(False)
            popover.markupToggle.show(False)
            popover.generateOnceToggle.show(False)
            popover.defaultFontLabel.show(False)
            popover.defaultFontPopup.show(False)
        if proof_is_multi_style(proof_key):
            self._populate_styles_list(popover, proof_key)
            popover.stylesLabel.show(True)
            popover.stylesList.show(True)
        else:
            popover.stylesLabel.show(False)
            popover.stylesList.show(False)

    def characterCategoryCallback(self, sender):
        """Handle character category checkbox changes."""
        if not hasattr(self, "current_proof_key") or not hasattr(
            self, "current_base_proof_type"
        ):
            return

        # Only handle this for proofs that have categories
        if self.current_base_proof_type not in [
            "Filtered Character Set",
            "Spacing Proof",
            "Multi-Style Comparison",
        ]:
            return

        popover = self.proof_settings_popover

        # Map checkbox controls to category keys
        category_mapping = {
            popover.categoryUppercase: "uppercase_base",
            popover.categoryLowercase: "lowercase_base",
            popover.categoryNumbersSymbols: "numbers_symbols",
            popover.categoryPunctuation: "punctuation",
            popover.categoryAccented: "accented",
        }

        category_key = category_mapping.get(sender)
        if category_key:
            setting_key = make_settings_key(self.current_proof_key, "cat", category_key)
            self.proof_settings[setting_key] = sender.get()

    def customTextEditCallback(self, sender):
        """Handle custom text editor changes."""
        if not hasattr(self, "current_proof_key"):
            return
        text_key = make_settings_key(self.current_proof_key, "customText")
        self.proof_settings[text_key] = sender.get()

    def markupToggleCallback(self, sender):
        """Handle markup toggle changes."""
        if not hasattr(self, "current_proof_key"):
            return
        markup_key = make_settings_key(self.current_proof_key, "markupEnabled")
        self.proof_settings[markup_key] = sender.get()

    def generateOnceToggleCallback(self, sender):
        """Handle Generate Once toggle changes."""
        if not hasattr(self, "current_proof_key"):
            return
        once_key = make_settings_key(self.current_proof_key, "generateOnce")
        self.proof_settings[once_key] = sender.get()
        popover = self.proof_settings_popover
        self._update_default_font_popup(popover, self.current_proof_key, sender.get())

    def defaultFontPopupCallback(self, sender):
        """Handle default font selection for Generate Once."""
        if not hasattr(self, "current_proof_key"):
            return
        menu_idx = sender.get()
        if not hasattr(self, "_default_font_styles"):
            return
        # Map through the menu index mapping (skipping disabled header items)
        menu_map = getattr(self, "_default_font_menu_map", None)
        if menu_map and 0 <= menu_idx < len(menu_map):
            si = menu_map[menu_idx]
            if si is None:
                return  # header item, ignore
            style = self._default_font_styles[si]
            path_key = make_settings_key(self.current_proof_key, "defaultFontPath")
            axis_key = make_settings_key(self.current_proof_key, "defaultFontAxisDict")
            self.proof_settings[path_key] = style["font_path"]
            self.proof_settings[axis_key] = style["axis_dict"]

    def _update_default_font_popup(self, popover, proof_key, generate_once):
        """Show/hide and populate the default font popup based on Generate Once.

        For variable fonts, lists all named instances from the fvar table.
        For static fonts, lists one entry per file.
        Groups entries by family with non-selectable header items.
        """
        if generate_once and self.font_manager.fonts:
            from proof import get_font_display_name
            from fonts import get_ttfont

            # Build flat styles list with family info
            styles = []
            for font_path in self.font_manager.fonts:
                tt = get_ttfont(font_path)
                if tt and "fvar" in tt:
                    name_table = tt["name"]
                    family_name = (
                        name_table.getBestFamilyName()
                        or get_font_display_name(font_path)
                    )
                    for inst in tt["fvar"].instances:
                        coords = dict(inst.coordinates)
                        inst_name = name_table.getName(
                            inst.subfamilyNameID, 3, 1, 0x0409
                        )
                        style_name = (
                            str(inst_name)
                            if inst_name
                            else ", ".join(f"{k}:{v}" for k, v in coords.items())
                        )
                        styles.append(
                            {
                                "label": f"{family_name} — {style_name}",
                                "style_name": style_name,
                                "font_path": font_path,
                                "axis_dict": coords,
                                "family_name": family_name,
                            }
                        )
                else:
                    if tt:
                        family_name = tt[
                            "name"
                        ].getBestFamilyName() or get_font_display_name(font_path)
                        style_name = tt[
                            "name"
                        ].getBestSubFamilyName() or get_font_display_name(font_path)
                    else:
                        family_name = get_font_display_name(font_path)
                        style_name = get_font_display_name(font_path)
                    styles.append(
                        {
                            "label": f"{family_name} — {style_name}",
                            "style_name": style_name,
                            "font_path": font_path,
                            "axis_dict": None,
                            "family_name": family_name,
                        }
                    )

            self._default_font_styles = styles

            # Group by family preserving order
            from collections import OrderedDict

            families = OrderedDict()
            for i, style in enumerate(styles):
                fam = style["family_name"]
                if fam not in families:
                    families[fam] = []
                families[fam].append(i)

            # Build NSMenu with family headers + indented members
            ns_popup = popover.defaultFontPopup.getNSPopUpButton()
            ns_popup.removeAllItems()
            menu = ns_popup.menu()
            style_idx_for_menu_idx = []  # maps menu item index → styles index

            for fam, member_indices in families.items():
                if len(families) > 1:
                    # Add family header as disabled item
                    header = (
                        AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                            fam, None, ""
                        )
                    )
                    header.setEnabled_(False)
                    attrs = {
                        AppKit.NSFontAttributeName: AppKit.NSFont.boldSystemFontOfSize_(
                            11
                        )
                    }
                    header.setAttributedTitle_(
                        AppKit.NSAttributedString.alloc().initWithString_attributes_(
                            fam, attrs
                        )
                    )
                    menu.addItem_(header)
                    style_idx_for_menu_idx.append(None)  # not selectable

                for si in member_indices:
                    title = (
                        f"  {styles[si]['style_name']}"
                        if len(families) > 1
                        else styles[si]["label"]
                    )
                    item = (
                        AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                            title, None, ""
                        )
                    )
                    item.setEnabled_(True)
                    menu.addItem_(item)
                    style_idx_for_menu_idx.append(si)

            self._default_font_menu_map = style_idx_for_menu_idx

            # Restore saved selection
            path_key = make_settings_key(proof_key, "defaultFontPath")
            axis_key = make_settings_key(proof_key, "defaultFontAxisDict")
            saved_path = self.proof_settings.get(path_key, "")
            saved_axis = self.proof_settings.get(axis_key, None)
            matched_menu_idx = None
            for menu_idx, si in enumerate(style_idx_for_menu_idx):
                if si is not None:
                    s = styles[si]
                    if s["font_path"] == saved_path and s["axis_dict"] == saved_axis:
                        matched_menu_idx = menu_idx
                        break
            # Fallback to first selectable item
            if matched_menu_idx is None:
                for menu_idx, si in enumerate(style_idx_for_menu_idx):
                    if si is not None:
                        matched_menu_idx = menu_idx
                        break
            if matched_menu_idx is not None:
                ns_popup.selectItemAtIndex_(matched_menu_idx)
                chosen = styles[style_idx_for_menu_idx[matched_menu_idx]]
                self.proof_settings[path_key] = chosen["font_path"]
                self.proof_settings[axis_key] = chosen["axis_dict"]

            popover.defaultFontLabel.show(True)
            popover.defaultFontPopup.show(True)
        else:
            popover.defaultFontLabel.show(False)
            popover.defaultFontPopup.show(False)

    def _build_available_styles(self):
        """Build list of available font styles from all loaded fonts.

        Each entry includes 'label', 'font_path', 'axis_dict', 'family_name',
        and 'style_name' for grouping purposes.
        For variable fonts, lists all named instances from the fvar table.
        """
        from fonts import get_ttfont
        from proof import get_font_display_name

        styles = []
        for font_path in self.font_manager.fonts:
            tt = get_ttfont(font_path)
            if tt and "fvar" in tt:
                name_table = tt["name"]
                family_name = name_table.getBestFamilyName() or get_font_display_name(
                    font_path
                )
                for inst in tt["fvar"].instances:
                    coords = dict(inst.coordinates)
                    inst_name = name_table.getName(inst.subfamilyNameID, 3, 1, 0x0409)
                    style_name = (
                        str(inst_name)
                        if inst_name
                        else ", ".join(f"{k}:{v}" for k, v in coords.items())
                    )
                    styles.append(
                        {
                            "label": f"{family_name} — {style_name}",
                            "font_path": font_path,
                            "axis_dict": coords,
                            "family_name": family_name,
                            "style_name": style_name,
                        }
                    )
            else:
                # Static font — use fontTools family name if available
                if tt:
                    family_name = tt[
                        "name"
                    ].getBestFamilyName() or get_font_display_name(font_path)
                    style_name = tt[
                        "name"
                    ].getBestSubFamilyName() or get_font_display_name(font_path)
                else:
                    family_name = get_font_display_name(font_path)
                    style_name = get_font_display_name(font_path)
                styles.append(
                    {
                        "label": f"{family_name} — {style_name}",
                        "font_path": font_path,
                        "axis_dict": None,
                        "family_name": family_name,
                        "style_name": style_name,
                    }
                )
        return styles

    def _populate_styles_list(self, popover, proof_key):
        """Populate the styles list for a multi-style comparison proof.

        Groups styles by family name with a toggle-all header row per family.
        """
        available_styles = self._build_available_styles()

        # Group by family_name preserving order
        from collections import OrderedDict

        families = OrderedDict()
        for i, style in enumerate(available_styles):
            fam = style["family_name"]
            if fam not in families:
                families[fam] = []
            families[fam].append((i, style))

        style_items = []
        for fam, members in families.items():
            # Check current enabled state of all members
            all_enabled = True
            for i, style in members:
                setting_key = make_settings_key(proof_key, "style", str(i))
                if not self.proof_settings.get(setting_key, True):
                    all_enabled = False
                    break

            # Family header row
            member_indices = [i for i, _ in members]
            style_items.append(
                {
                    "Style": f"▸ {fam}",
                    "Enabled": all_enabled,
                    "_index": None,
                    "_family_indices": member_indices,
                }
            )

            # Member rows (indented)
            for i, style in members:
                setting_key = make_settings_key(proof_key, "style", str(i))
                enabled = self.proof_settings.get(setting_key, True)
                style_items.append(
                    {
                        "Style": f"    {style['style_name']}",
                        "Enabled": enabled,
                        "_index": i,
                    }
                )

        popover.stylesList.set(style_items)

    def stylesEditCallback(self, sender):
        """Handle style checkbox changes in the styles list.

        Family header rows toggle all their children.
        """
        if not hasattr(self, "current_proof_key"):
            return
        items = list(sender.get())
        changed = False
        for row_idx, item in enumerate(items):
            family_indices = item.get("_family_indices")
            if family_indices is not None:
                # Family header — propagate to children
                header_enabled = bool(item.get("Enabled", True))
                for child_row in range(row_idx + 1, len(items)):
                    child = items[child_row]
                    if child.get("_family_indices") is not None:
                        break  # next family header
                    child_idx = child.get("_index")
                    if child_idx is not None:
                        items[child_row] = dict(child, Enabled=header_enabled)
                        setting_key = make_settings_key(
                            self.current_proof_key, "style", str(child_idx)
                        )
                        self.proof_settings[setting_key] = header_enabled
                        changed = True
            else:
                idx = item.get("_index")
                if idx is not None:
                    setting_key = make_settings_key(
                        self.current_proof_key, "style", str(idx)
                    )
                    self.proof_settings[setting_key] = bool(item.get("Enabled", True))

        # Update family header checkboxes to reflect children state
        for row_idx, item in enumerate(items):
            family_indices = item.get("_family_indices")
            if family_indices is not None:
                all_on = True
                for child_row in range(row_idx + 1, len(items)):
                    child = items[child_row]
                    if child.get("_family_indices") is not None:
                        break
                    if not child.get("Enabled", True):
                        all_on = False
                        break
                items[row_idx] = dict(item, Enabled=all_on)

        if changed:
            sender.set(items)

    def alignPopUpCallback(self, sender):
        """Handle alignment selection changes."""
        if not hasattr(self, "current_proof_key"):
            return

        selected_idx = sender.get()
        if 0 <= selected_idx < len(self.ALIGNMENT_OPTIONS):
            align_value = self.ALIGNMENT_OPTIONS[selected_idx]
            align_key = make_settings_key(self.current_proof_key, "align")
            self.proof_settings[align_key] = align_value

    def stepperChangeCallback(self, setting_key, value):
        """Handle stepper value changes."""
        is_valid, converted_value, error_msg = validate_setting_value(
            setting_key, value
        )
        if not is_valid:
            print(f"Invalid value for setting: {error_msg}")
            return
        self.proof_settings[setting_key] = converted_value

    def configureSteppersForNumericList(self, numeric_list, items):
        """Configure stepper cells in the numeric list with appropriate min/max/increment values."""

        def configure_delayed():
            table_view = numeric_list.getNSTableView()
            data_source = table_view.dataSource()

            for row_index, item in enumerate(items):
                if "Setting" not in item:
                    continue

                setting_name = item["Setting"]
                stepper_config = get_stepper_config_for_setting(setting_name)

                # Get the NSView for the "Value" column (column index 1)
                try:
                    ns_cell_view = table_view.viewAtColumn_row_(
                        1, row_index, makeIfNecessary=True
                    )
                except AttributeError:
                    try:
                        ns_cell_view = table_view.makeViewWithIdentifier_owner_(
                            "Value", data_source
                        )
                    except:
                        continue

                # Find the vanilla wrapper through multiple approaches
                vanilla_wrapper = None
                if ns_cell_view and hasattr(data_source, "_cellWrappers"):
                    vanilla_wrapper = data_source._cellWrappers.get(ns_cell_view)

                if (
                    not vanilla_wrapper
                    and ns_cell_view
                    and hasattr(ns_cell_view, "vanillaWrapper")
                ):
                    try:
                        vanilla_wrapper = ns_cell_view.vanillaWrapper()
                    except:
                        pass

                if not vanilla_wrapper and hasattr(
                    ns_cell_view, "setStepperConfiguration_"
                ):
                    vanilla_wrapper = ns_cell_view

                if vanilla_wrapper and hasattr(
                    vanilla_wrapper, "setStepperConfiguration_"
                ):
                    vanilla_wrapper.setStepperConfiguration_(stepper_config)
                    if "_key" in item:
                        vanilla_wrapper.setChangeCallback_withKey_(
                            self.stepperChangeCallback, item["_key"]
                        )

        callAfter(configure_delayed)

    def numericSettingsEditCallback(self, sender):
        """Handle edits to numeric settings in popover."""
        self._validate_and_update_settings(sender.get(), value_field="Value")

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

        # Reset multi-style dedup so it generates once per PDF run
        MultiStyleComparisonProofHandler.reset_generated()

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
                all_fonts=list(self.font_manager.fonts),
                font_manager=self.font_manager,
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
                    self.proof_settings_manager.get_proof_font_size,
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
            result = getFile(
                title="Select Settings File",
                messageText="Choose a JSON settings file to load:",
                fileTypes=["json"],
                allowsMultipleSelection=False,
            )

            if result and len(result) > 0:
                settings_file_path = result[0]

                if self.settings.load_from_file(settings_file_path):
                    # Clear and reload font manager
                    self.font_manager.fonts = tuple()
                    self.font_manager.font_info = {}
                    self.font_manager.axis_values_by_font = {}

                    # Load fonts from the new settings
                    font_paths = self.settings.get_fonts()
                    if font_paths:
                        self.font_manager.load_fonts(font_paths)
                        for font_path in font_paths:
                            axis_values = self.settings.get_font_axis_values(font_path)
                            if axis_values:
                                self.font_manager.axis_values_by_font[font_path] = (
                                    axis_values
                                )

                    # Refresh UI
                    self.filesTab.update_table()
                    self.refresh_controls_tab()
                    self.initialize_proof_settings()

                    print(f"Settings loaded from: {settings_file_path}")
                    message(
                        "Settings Loaded",
                        f"Settings have been loaded from:\n{settings_file_path}\n\n"
                        "Changes will now be saved to this file instead of the auto-save file.\n\n"
                        "You can use 'Reset Settings' to clear all settings from the GUI and return to auto-save mode. This will not delete the custom settings file.",
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
            self.controlsTab.refresh_proof_options_list()
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
            from config import resolve_base_proof_key

            _, base_proof_key = resolve_base_proof_key(base_proof_type)
            if not base_proof_key:
                return

            popover = self.proof_settings_popover

            # Hide the proof type popup since we're editing a specific instance
            if hasattr(popover, "proofTypeLabel"):
                popover.proofTypeLabel.show(False)
            if hasattr(popover, "proofTypePopup"):
                popover.proofTypePopup.show(False)

            # Update numeric settings for this specific instance using settings manager
            numeric_items = (
                self.proof_settings_manager.get_popover_settings_for_proof_instance(
                    unique_proof_key, base_proof_key
                )
            )
            popover.numericList.set(numeric_items)

            # Populate the row setting registry for stepper auto-configuration
            clear_row_settings()
            for row_index, item in enumerate(numeric_items):
                if "Setting" in item:
                    register_row_setting(row_index, item["Setting"])

            # Configure steppers for the numeric settings
            self.configureSteppersForNumericList(popover.numericList, numeric_items)

            # Update OpenType features for this specific instance using settings manager
            feature_items = self.proof_settings_manager.get_opentype_features_for_proof(
                unique_proof_key
            )
            popover.featuresList.set(feature_items)

            # Update alignment control for supported proof types
            if proof_supports_formatting(base_proof_key):
                align_value = self.proof_settings_manager.get_alignment_value_for_proof(
                    unique_proof_key
                )
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

            # Update character category controls
            if proof_has_categories(base_proof_key):
                self._setup_category_controls(popover, unique_proof_key, show=True)
            else:
                self._setup_category_controls(popover, unique_proof_key, show=False)

            # Update custom text editor
            if proof_has_custom_text(base_proof_key):
                text_key = make_settings_key(unique_proof_key, "customText")
                existing_text = self.proof_settings.get(text_key, "")
                popover.customTextEditor.set(existing_text)
                popover.customTextLabel.show(True)
                popover.customTextEditor.show(True)
                if not proof_is_multi_style(base_proof_key):
                    markup_key = make_settings_key(unique_proof_key, "markupEnabled")
                    popover.markupToggle.set(self.proof_settings.get(markup_key, False))
                    popover.markupToggle.show(True)
                    # Generate Once toggle and font selector
                    once_key = make_settings_key(unique_proof_key, "generateOnce")
                    generate_once = self.proof_settings.get(once_key, False)
                    popover.generateOnceToggle.set(generate_once)
                    popover.generateOnceToggle.show(True)
                    self._update_default_font_popup(
                        popover, unique_proof_key, generate_once
                    )
                else:
                    popover.markupToggle.show(False)
                    popover.generateOnceToggle.show(False)
                    popover.defaultFontLabel.show(False)
                    popover.defaultFontPopup.show(False)
            else:
                popover.customTextLabel.show(False)
                popover.customTextEditor.show(False)
                popover.markupToggle.show(False)
                popover.generateOnceToggle.show(False)
                popover.defaultFontLabel.show(False)
                popover.defaultFontPopup.show(False)

            # Update styles selector for Multi-Style Comparison
            if proof_is_multi_style(base_proof_key):
                self._populate_styles_list(popover, unique_proof_key)
                popover.stylesLabel.show(True)
                popover.stylesList.show(True)
            else:
                popover.stylesLabel.show(False)
                popover.stylesList.show(False)

        except Exception as e:
            print(f"Error updating proof settings popover: {e}")
            traceback.print_exc()

        return False
