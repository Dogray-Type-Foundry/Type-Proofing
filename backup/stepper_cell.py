# Custom Stepper Cell for vanilla.List2 - Adds steppers to numeric cells

import AppKit
import vanilla
import objc


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
