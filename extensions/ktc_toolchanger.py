# KTC - Klipper Tool Changer code
# Toollock and general Tool support
#
# Copyright (C) 2024  Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

from enum import Enum, IntEnum, unique
import typing

from . import ktc

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from .klippy import configfile
    # from .klippy import klippy, gcode
    from .klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_log, ktc_persisting#, ktc_tool

class KtcToolchanger(ktc.KtcBaseChangerClass, ktc.KtcConstantsClass):
    """Class initialized for each toolchanger.
    At least one toolchanger will be initialized for each printer.
    A "default_toolchanger" will be initialized if no toolchanger
    is specified in the config."""

    def __init__(self, config: 'configfile.ConfigWrapper'):
        super().__init__(config)

        self.ktc = None  # type: ignore # This is set in configure_inherited_params.
        gcode_macro = typing.cast('klippy_gcode_macro.PrinterGCodeMacro',
                                  self.printer.lookup_object("gcode_macro"))   # type: ignore

        # Initialize object variables.
        self._state = self.StateType.UNINITIALIZED

        # Get initialization mode and check if valid.
        init_mode = config.get("init_mode", self.InitModeType.MANUAL.name)           # type: ignore
        try:
            self.init_mode = self.InitModeType[init_mode]
        except KeyError as e:
            raise config.error(
                "Invalid init_mode %s for ktc_toolchanger %s. Valid values are: %s"
            % (init_mode, self.name, self.InitModeType.list_valid_values())) from e

        # Get the initialization order and check if valid.
        init_order = config.get("init_order", self.InitOrderType.INDEPENDENT.name)   # type: ignore
        try:
            self.init_order = self.InitOrderType[init_order]
        except KeyError as e:
            raise config.error(
                "Invalid init_order %s for ktc_toolchanger %s. Valid values are: %s"
            % (init_order, self.name, self.InitOrderType.list_valid_values())) from e

        self.active_tool = self.TOOL_UNKNOWN  # The currently active tool. Default is unknown.

        self.engage_gcode_template = gcode_macro.load_template(
            config, "engage_gcode", "")
        self.disengage_gcode_template = gcode_macro.load_template(
            config, "disengage_gcode", "")
        # Load the init gcode template from the config.
        # If it is not defined, set it to None and it will be ignored.
        # If it is defined, load it as a gcode template in itself
        # by using it as default value for the init_gcode_template parameter.
        self.init_gcode = config.get("init_gcode", "")  # type: ignore
        self.init_gcode_template = gcode_macro.load_template(   # type: ignore
            config, "", self.init_gcode)

        # Get the parent tool if defined. This is set to the object
        # after connect, after all objects are initialized.
        self.parent_tool = config.get("parent_tool", None)

    def configure_inherited_params(self):
        super().configure_inherited_params()
        self.ktc = typing.cast(ktc.Ktc, self.printer.lookup_object("ktc"))

        self.log = typing.cast('ktc_log.KtcLog', self.printer.load_object(
            self.config, "ktc_log"))  # Load the log object.

        self.ktc_persistent: 'ktc_persisting.KtcPersisting' = ( # type: ignore
            self.printer.lookup_object("ktc_persisting")
        )  # Load the ktc_persisting object.

        if self.parent_tool is not None:
            self.parent_tool = self.printer.lookup_object(self.parent_tool, None)
            raise self.config.error(
                "parent_tool %s not found for ktc_toolchanger %s."
                % (self.parent_tool, self.name)
            )

        ###### Inherited parameters from ktc.
        # If set to "X", "Y", "Z" or a combination of them, then the tool will require the axis to be homed before it can be selected. Defaults to "".
        self.requires_axis_homed = config.get("requires_axis_homed", self.ktc.requires_axis_homed)
        
        # Tool Selection and Deselection G-Code macros
        # This is overridden by the tool if it has a tool_select_gcode or tool_deselect_gcode defined.
        self.tool_select_gcode = self.config.get("tool_select_gcode", self.ktc.tool_select_gcode)
        self.tool_deselect_gcode = self.config.get("tool_deselect_gcode", self.ktc.tool_deselect_gcode)

        ###### Register event handlers.
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        self.printer.register_event_handler("klippy:connect", self.handle_connect)
        self.printer.register_event_handler("homing:home_rails_begin", self._handle_home_rails_begin)
        self.printer.register_event_handler("homing:home_rails_end", self._handle_home_rails_end)

        ######
        # TODO: Move to ktc.
        # self.saved_fan_speed = (
            # 0  # Saved partcooling fan speed when deselecting a tool with a fan.
        # )

        # self.restore_axis_on_toolchange = ""  # string of axis to restore: XYZ
        # self.tool_map = {}
        # self.changes_made_by_set_all_tool_heaters_off = {}
        # self.saved_position = None
        ######

    @property
    def state(self):
        return self._state
    @state.setter
    def state(self, value):
        self._state = self.StateType[str(value)]
    
    def handle_ready(self):
        return
        # if self.init_mode == self.InitModeType.ON_START:
        #     self.initialize()

    def _handle_home_rails_begin(self, homing_state, rails):
        if self.init_mode == self.InitModeType.HOMING_START:
            self.initialize()
            
    def _handle_home_rails_end(self, homing_state, rails):
        if self.init_mode == self.InitModeType.HOMING_END:
            self.initialize()

    @property
    def persistent_state(self) -> dict:
        '''Return the persistent state from file.
        This is not to be used before the printer is in ready state
        Is initialized inside handle_connect.'''
        return self.ktc_persistent.content.get(
                "State", {}
            ).get("ktc_toolchanger_" + self.name.lower(), {})
        
    @persistent_state.setter
    def persistent_state(self, value: dict):
        self.ktc_persistent.content["State"]["ktc_toolchanger_" + self.name.lower()] = value
        self.ktc_persistent.ready_to_save = True


    def initialize(self):
        """Initialize the tool lock."""
        # Check if the toolchanger has a parent tool if the init_order is set to
        # something else than independent.
        if self.init_order != self.InitOrderType.INDEPENDENT and self.parent_tool is not None:
            raise Exception(
                "Toolchanger %s has no parent tool defined but init_order is set to AFTER_PARENT." % self.name
            )

        # Check if the parent tool is initialized if the init_order is set to
        # be after the parent tool is selected or initialized.
        if (self.init_order == self.InitOrderType.AFTER_PARENT_SELECTED or
            self.init_order == self.InitOrderType.AFTER_PARENT_INITIALIZATION):
            # If the parent tool is not initialized, initialize it.
            if self.parent_tool.toolchanger.state < self.StateType.INITIALIZED:
                self.parent_tool.toolchanger.initialize()

        # Check if the parent tool is ready if the init_order is set to
        # be after the parent tool is selected.                
        if self.init_order == self.InitOrderType.AFTER_PARENT_SELECTED:
            # Parent toolchanger should be initialized now if possible.
            if self.parent_tool.toolchanger.state < self.StateType.READY:
                raise Exception(
                    "Toolchanger %s has parent tool %s that resides on toolchanger %s " 
                    % (self.name, self.parent_tool.name, self.parent_tool.toolchanger.name) +
                    "that is not ready but init_order for this toolchanger is set to AFTER_PARENT_SELECTED."
                )
                
            if (self.parent_tool.toolchanger.state < self.StateType.ENGAGED and
                self.parent_tool.toolchanger.active_tool != self.parent_tool):
                self.parent_tool.select()

        # Get the active tool from the persistent variables.
        active_tool_name = str.lower(self.persistent_state.get(
            "active_tool", self.TOOL_UNKNOWN.name
        ))

        # Set the active tool to the tool with the name from the persistent variables.
        # If not found in the tools that are loaded for this changer, set it to TOOL_UNKNOWN.
        self.active_tool = self.tools.get(active_tool_name, None)
        if self.active_tool is None:
            self.active_tool = self.TOOL_UNKNOWN
            self.log.always(
                "ktc_toolchanger.initialize(): Active tool %s not found for ktc_toolchanger %s. Using tool %s."
                % (active_tool_name, self.name, self.active_tool.name)
            )
        
        self.log.trace("ktc_toolchanger[%s].initialize(): Loaded persisted active tool: %s." 
                       % (self.name, self.active_tool.name))

        # Run the init gcode template if it is defined.
        if self.init_gcode_template is not None:

            context = self.init_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            self.init_gcode_template.run_gcode_from_command(context)
        else:
            self.state = self.StateType.INITIALIZED
            
        self.log.trace("ktc_toolchanger[%s].initialize(): Complete." % self.name)
        self.log.trace("ktc_toolchanger[%s].active_tool: %s." % (self.name, self.active_tool.name))
        self.log.trace("ktc_toolchanger[%s].state: %s." % (self.name, self.state))
        
        if self.ktc.default_toolchanger == self:
            self.ktc.active_tool = self.active_tool
            self.log.trace("ktc.active_tool set to: %s." % self.ktc.active_tool.name)
           
        
    
        # if self.active_tool == self.TOOL_NONE:
        #     self.disengage()
        # else:
        #     self.engage(True)
        #     self.log.always(
        #     )

        # self.ktc.active_tool = self.active_tool

    def engage(self, ignore_engaged=False) -> bool:
        try:
            if self.state < self.StateType.INITIALIZING:
                raise Exception(
                    "Status is: %s." % self.StateType.value_to_key_string(self.state)
                )

            if self.engage_gcode_template is None:
                raise Exception(
                    "No tool lock gcode template defined."
                )

            if not ignore_engaged and self.state == self.StateType.ENGAGED:
                self.log.always(
                    "ktc_toolchanger %s is already engaged with tool %s."
                    % (self.name, self.ktc.active_tool.name)
                    + " IGNORE_ENGAGED is not set. No action taken."
                )
                return True

            self.state = self.StateType.ENGAGING
            context = self.init_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            self.log.trace("ktc_toolchanger.engage() running. ")
            self.engage_gcode_template.run_gcode_from_command(context)
            self.log.trace("Tool engaged successfully.")

            self.log.changer_stats[self.name].engages += 1
            self.state = self.StateType.ENGAGED
            return True
        except Exception as e:
            self.log.always("ktc_toolchanger.disengage(): failed for ktc_toolchanger %s with error: %s" % (self.name, e))
            self.state = self.StateType.ERROR
            return False

    def disengage(self) -> bool:
        """Disengage the lock on the tool so it can be removed.
        Return: True if successful, False if not."""
        
        try:
            if self.state < self.StateType.INITIALIZING:
                raise Exception(
                    "Toolchanger %s not ready." % self.name
                )
                
            if self.disengage_gcode_template is None:
                self.log.debug(
                    "ktc_toolchanger.disengage(): No tool unlock gcode template"
                    + " defined for ktc_toolchanger %s." % self.name
                )
                return True

            # Run the disengage gcode template.
            self.log.trace("ktc_toolchanger.disengage(): Setting state to DISENGAGING.")
            self.state = self.StateType.DISENGAGING.value
            self.log.trace("ktc_toolchanger.disengage(): Getting context for disengage_gcode_template.")
            context = self.init_gcode_template.create_template_context()
            self.log.trace("ktc_toolchanger.disengage(): Setting myself in context.")
            context['myself'] = self.get_status()
            self.log.trace("ktc_toolchanger.disengage(): Setting ktc in context.")
            context['ktc'] = self.ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            self.log.trace("ktc_toolchanger.disengage() running. ")
            self.disengage_gcode_template.run_gcode_from_command(context)
            self.log.trace("Tool disengaged successfully.")

            # Add disengage to statistics.
            self.log.changer_stats[self.name].disengages += 1
            self.log.trace("ktc_toolchanger.disengage(): Setting state to READY.")
            self.state = self.StateType.READY
            return True
        except Exception as e:
            self.log.always("ktc_toolchanger.disengage(): failed for ktc_toolchanger %s with error: %s" % (self.name, e))
            self.state = self.StateType.ERROR
            return False

    def get_status(self, eventtime=None):   # pylint: disable=unused-argument
        status = {
            # "global_offset": self.global_offset,
            "name": self.name,
            "active_tool": self.active_tool.name,
            "active_tool_n": self.active_tool.number,
            "state": self.state,
            "init_mode": self.init_mode,
            "tools": list(self.tools.keys()),
            # "saved_fan_speed": self.saved_fan_speed,
            # "purge_on_toolchange": self.purge_on_toolchange,
            # "restore_axis_on_toolchange": self.restore_axis_on_toolchange,
            # "saved_position": self.saved_position,
            **self.params,
        }
        return status

    @unique
    class StateType(IntEnum):
        """Constants for the status of the toolchanger.
        Using dataclasses to allow for easy traversal of the values."""
        ERROR= -3
        UNINITIALIZED = -2
        INITIALIZING = -1
        INITIALIZED = 0
        READY = 1
        CHANGING = 2
        ENGAGING = 3
        DISENGAGING = 4
        ENGAGED = 5

        @classmethod
        # This might be unnecessary.
        def value_to_key_string(cls, status):
            try:
                return cls(status).name
            except Exception:
                return None

        @classmethod
        def list_valid_values(cls):
            return [name for name, _ in cls.__members__]

        @classmethod
        def get_value_from_configuration(cls, configured_value):
            return cls[str(configured_value).upper()]

        def __str__(self):
            return f'{self.name}'

    @unique
    class InitModeType(str, Enum):
        """Constants for the initialization mode of the toolchanger.
        Inherits from str so it can be JSON serializable.
        Not using """
        MANUAL = "manual"
        ON_START = "on_start"
        ON_FIRST_USE = "on_first_use"
        HOMING_START = "homing_start"
        HOMING_END = "homing_end"

        @classmethod
        def list_valid_values(cls):
            return [name for name, _ in cls.__members__]

        @classmethod
        def get_value_from_configuration(cls, configured_value):
            return cls[str(configured_value).upper()]
            # return cls(str(configured_value).lower())

    @unique
    class InitOrderType(str, Enum):
        """Constants for the initialization order of the toolchanger."""
        INDEPENDENT  = "independent"
        AFTER_PARENT_SELECTED = "after_parent_selected"
        AFTER_PARENT_INITIALIZATION = "after_parent_initialization"
        # BEFORE_PARENT_SELECTED  = "before_parent_selected"
        # BEFORE_PARENT_INITIALIZATION = "before_parent_initialization"

        @classmethod
        def list_valid_values(cls):
            return [name for name, _ in cls.__members__]

        @classmethod
        def get_value_from_configuration(cls, configured_value):
            return cls[str(configured_value).upper()]

def load_config_prefix(config):
    """Load the toolchanger object with the given config.
    This is called by Klipper to initialize the toolchanger object."""
    return KtcToolchanger(config)
