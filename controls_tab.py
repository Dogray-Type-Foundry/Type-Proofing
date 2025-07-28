# Controls Tab - Proof options and settings UI

import traceback
import vanilla
import AppKit
from AppKit import NSBezelStyleRegularSquare, NSTextAlignmentCenter
from proof_handlers import create_unique_proof_key


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
        from proof_config import (
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
        from proof_config import get_proof_display_names

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
            self.group = vanilla.Group((0, 0, -0, -0))

            # Create a split layout: Controls on left, Preview on right
            # Controls area (left side)
            controls_x = 10
            y = 10

            # Preview area (right side)
            self.group.previewBox = vanilla.Box((350, 10, -10, -10))

            # Define which proofs have settings (all proofs now have font size setting)
            proofs_with_settings = {
                "Filtered Character Set",
                "Spacing Proof",
                "Basic Paragraph Large",
                "Diacritic Words Large",
                "Basic Paragraph Small",
                "Paired Styles Paragraph Small",
                "Generative Text Small",
                "Diacritic Words Small",
                "Misc Paragraph Small",
                "Ar Character Set",
                "Ar Paragraph Large",
                "Fa Paragraph Large",
                "Ar Paragraph Small",
                "Fa Paragraph Small",
                "Ar Vocalization Paragraph Small",
                "Ar-Lat Mixed Paragraph Small",
                "Ar Numbers Small",
            }

            # Generate dynamic proof options list
            proof_options_items = self.get_proof_options_list()

            # Track popover states for proofs with settings
            for item in proof_options_items:
                proof_name = item["Option"]
                base_option = item.get("_original_option", proof_name)
                if base_option in proofs_with_settings:
                    self.popover_states[proof_name] = False  # Track popover visibility

            # Drag settings for internal reordering only
            dragSettings = dict(makeDragDataCallback=self.makeProofDragDataCallback)

            # Drop settings for internal reordering only (no external file drops)
            dropSettings = dict(
                pasteboardTypes=["dev.drawbot.proof.proofOptionIndexes"],
                dropCandidateCallback=self.dropProofCandidateCallback,
                performDropCallback=self.performProofDropCallback,
            )

            # Page format selection
            # Import PAGE_FORMAT_OPTIONS from core_config
            from core_config import PAGE_FORMAT_OPTIONS

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
            traceback.print_exc()
            raise

    def proofOptionsEditCallback(self, sender):
        """Handle edits to proof options."""
        items = sender.get()
        edited_index = sender.getEditedIndex()

        from proof_config import get_proof_display_names

        proofs_with_settings = set(get_proof_display_names(include_arabic=True))

        if edited_index is not None and edited_index < len(items):
            item = items[edited_index]
            proof_name = item["Option"]
            base_option = item.get("_original_option", proof_name)
            enabled = item["Enabled"]

            # If this proof has settings and was just enabled, show the popover
            if (
                base_option in proofs_with_settings
                and enabled
                and not self.popover_states.get(proof_name, False)
            ):
                self.hide_all_popovers_except(proof_name)
                self.show_popover_for_option(proof_name, edited_index)
                self.popover_states[proof_name] = True
            elif (
                base_option in proofs_with_settings
                and not enabled
                and self.popover_states.get(proof_name, False)
            ):
                # If the proof was disabled, hide its popover
                self.hide_popover_for_option(proof_name)
                self.popover_states[proof_name] = False

        # Handle regular proof option edits (save settings)
        for item in items:
            proof_name = item["Option"]  # Use the actual proof name
            base_option = item.get("_original_option", proof_name)  # Get base type
            enabled = item["Enabled"]

            # Get the correct proof key from the registry
            from proof_config import get_proof_settings_mapping

            proof_settings_mapping = get_proof_settings_mapping()

            # For base proof types, use the registry key directly
            if proof_name in proof_settings_mapping:
                proof_key = proof_settings_mapping[proof_name]
            else:
                # For numbered variants, use a sanitized version as the key
                proof_key = create_unique_proof_key(proof_name)

            self.settings.set_proof_option(proof_key, enabled)

    def pageFormatCallback(self, sender):
        """Handle page format selection changes."""
        try:
            from core_config import PAGE_FORMAT_OPTIONS

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
        for option in self.popover_states:
            if option != except_option and self.popover_states[option]:
                self.hide_popover_for_option(option)
                self.popover_states[option] = False

    def show_popover_for_option(self, option, row_index):
        """Show popover for the specified option."""
        # Import the helper function from proof_config
        from proof_config import get_proof_popover_mapping

        # Get proof name to key mapping from registry
        proof_name_to_key = get_proof_popover_mapping()

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
            traceback.print_exc()

    def create_add_proof_popover(self):
        """Create the add proof popover."""
        self.add_proof_popover = vanilla.Popover((300, 100))
        popover = self.add_proof_popover

        # Title
        popover.titleLabel = vanilla.TextBox(
            (10, 10, -10, 20), "Select Proof Type to Add:"
        )

        # Import helper functions from proof_config
        from proof_config import (
            get_base_proof_display_names,
            get_arabic_proof_display_names,
        )

        # Get available proof types from registry
        proof_type_options = get_base_proof_display_names()

        # Add Arabic proof types if fonts support Arabic
        if self.parent_window.font_manager.has_arabic_support():
            proof_type_options.extend(get_arabic_proof_display_names())

        popover.proofTypePopup = vanilla.PopUpButton(
            (10, 35, -10, 20),
            proof_type_options,
        )

        # Add button
        popover.addButton = vanilla.Button(
            (10, 65, 120, 20),
            "Add",
            callback=self.addSelectedProofCallback,
        )

        # Cancel button
        popover.cancelButton = vanilla.Button(
            (-130, 65, 120, 20),
            "Cancel",
            callback=self.cancelAddProofCallback,
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
