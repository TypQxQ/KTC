# KTC - Klipper Tool Changer code
# Toollock and general Tool support
#
# Copyright (C) 2024  Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

import dataclasses
from . import ktc, ktc_persisting, ktc_log, ktc_tool

class KtcToolchanger:
    """Class initialized for each toolchanger.
    At least one toolchanger will be initialized for each printer.
    A "default_toolchanger" will be initialized if no toolchanger
    is specified in the config."""

    def __init__(self, config):
        """Initialize the toolchanger object."""
        self.config = config                    # For later use. Used in ktc_tool objects too.
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.log: ktc_log.KtcLog = self.printer.load_object(
            config, "ktc_log"
        )  # Load the log object.
        self.ktc: ktc.Ktc = self.printer.load_object(config, "ktc")
        self.ktc_persistent: ktc_persisting.KtcPersisting = (
            self.printer.load_object(config, "ktc_persisting")
        )  # Load the ktc_persisting object.

        # Initialize object variables.
        self.name: str = config.get_name().split(" ", 1)[1]
        self.params = ktc.get_params_dict_from_config(config)
        self.state = STATE.UNINITIALIZED
        self.tools: dict[str, ktc_tool.KtcTool] = {}  # All tools on this toolchanger.
        self.parent_tool: ktc_tool.KtcTool = None  # The parent tool of this toolchanger.
        
        # Get initialization mode and check if valid.
        init_mode = config.get("init_mode", INIT_MODE.MANUAL)
        self.init_mode = INIT_MODE.get_value_from_configuration(init_mode)
        if self.init_mode is None:
            raise config.error(
                "Invalid init_mode %s for ktc_toolchanger %s. Valid values are: %s"
            % (init_mode, self.name, INIT_MODE.list_valid_values()))
            
        # Get the initialization order and check if valid.
        init_order = config.get("init_order", INIT_ORDER.INDEPENDENT)
        self.init_order = INIT_ORDER.get_value_from_configuration(init_order)
        if self.init_order is None:
            raise config.error(
                "Invalid init_order %s for ktc_toolchanger %s. Valid values are: %s"
            % (init_order, self.name, INIT_ORDER.list_valid_values()))
        
        self.active_tool = (
            ktc.TOOL_UNKNOWN  # The currently active tool. Default is unknown.
        )

        # G-Code macros
        gcode_macro = self.printer.load_object(config, "gcode_macro")
        self.engage_gcode_template = gcode_macro.load_template(
            config, "engage_gcode", ""
        )
        self.disengage_gcode_template = gcode_macro.load_template(
            config, "disengage_gcode", ""
        )
        # Load the init gcode template from the config.
        # If it is not defined, set it to None and it will be ignored.
        # If it is defined, load it as a gcode template in itself
        # by using it as default value for the init_gcode_template parameter.
        self.init_gcode_template = config.get("init_gcode", None)
        if  isinstance(self.init_gcode_template, str):
            self.init_gcode_template = gcode_macro.load_template(
                config, "none", self.init_gcode_template
            )
            
        # Get the parent tool if defined. This is set to the object 
        # after connect, after all objects are initialized.
        self.parent_tool = config.get("parent_tool", None)

        # Add itself to the list of toolchangers if not already added.
        # This can potentially happen if the toolchanger is named "default_toolchanger".
        # Other cases are possible and should be handled here.
        if self.ktc.toolchangers.get(self.name) is None:
            self.ktc.toolchangers[self.name] = self
        else:
            raise config.error(
                "ktc_toolchanger %s already registered." % self.name
            )

        ###### Inherited parameters from ktc.
        # If set to "X", "Y", "Z" or a combination of them, then the tool will require the axis to be homed before it can be selected. Defaults to "".
        self.requires_axis_homed: str = config.get("requires_axis_homed", self.ktc.requires_axis_homed)
        
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
        # self.last_endstop_query = {}
        # self.changes_made_by_set_all_tool_heaters_off = {}
        # self.saved_position = None
        ######

    def handle_connect(self):
        if self.parent_tool is not None:
            self.parent_tool = self.printer.lookup_object(self.parent_tool, None)
            raise self.config.error(
                "parent_tool %s not found for ktc_toolchanger %s."
                % (self.parent_tool, self.name)
            )

    def handle_ready(self):
        if self.init_mode == INIT_MODE.ON_START:
            self.initialize()

    def _handle_home_rails_begin(self, homing_state, rails):
        if self.init_mode == INIT_MODE.HOMING_START:
            self.initialize()
            
    def _handle_home_rails_end(self, homing_state, rails):
        if self.init_mode == INIT_MODE.HOMING_END:
            self.initialize()

    @property
    def persistent_state(self) -> dict:
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
        if self.init_order != INIT_ORDER.INDEPENDENT and self.parent_tool is not None:
            raise Exception(
                "Toolchanger %s has no parent tool defined but init_order is set to AFTER_PARENT." % self.name
            )

        # Check if the parent tool is initialized if the init_order is set to
        # be after the parent tool is selected or initialized.
        if (self.init_order == INIT_ORDER.AFTER_PARENT_SELECTED or
            self.init_order == INIT_ORDER.AFTER_PARENT_INITIALIZATION):
            # If the parent tool is not initialized, initialize it.
            if self.parent_tool.toolchanger.state < STATE.INITIALIZED:
                self.parent_tool.toolchanger.initialize()

        # Check if the parent tool is ready if the init_order is set to
        # be after the parent tool is selected.                
        if self.init_order == INIT_ORDER.AFTER_PARENT_SELECTED:
            # Parent toolchanger should be initialized now if possible.
            if self.parent_tool.toolchanger.state < STATE.READY:
                raise Exception(
                    "Toolchanger %s has parent tool %s that resides on toolchanger %s " 
                    % (self.name, self.parent_tool.name, self.parent_tool.toolchanger.name) +
                    "that is not ready but init_order for this toolchanger is set to AFTER_PARENT_SELECTED."
                )
                
            if (self.parent_tool.toolchanger.state < STATE.ENGAGED and
                self.parent_tool.toolchanger.active_tool != self.parent_tool):
                self.parent_tool.select()

        # If not, set the state to INITIALIZING 
        
        # Get the active tool from the persistent variables.
        active_tool_name = str.lower(self.persistent_state.get(
            "active_tool", ktc.TOOL_UNKNOWN.name
        ))

        # Set the active tool to the tool with the name from the persistent variables.
        # If not found in the tools that are loaded for this changer, set it to TOOL_UNKNOWN.
        self.active_tool = self.tools.get(active_tool_name, None)
        if self.active_tool is None:
            self.active_tool = ktc.TOOL_UNKNOWN
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
            context['STATE'] = STATE
            context['INIT_MODE'] = INIT_MODE
            self.init_gcode_template.run_gcode_from_command(context)
        else:
            self.state = STATE.INITIALIZED
            
        self.log.trace("ktc_toolchanger[%s].initialize(): Complete." % self.name)
        self.log.trace("ktc_toolchanger[%s].active_tool: %s." % (self.name, self.active_tool.name))
        self.log.trace("ktc_toolchanger[%s].state: %s." % (self.name, STATE.value_to_key_string(self.state)))
        
        if self.ktc.default_toolchanger == self:
            self.ktc.active_tool = self.active_tool
            self.log.trace("ktc.active_tool set to: %s." % self.ktc.active_tool.name)
           
        
    
        # if self.active_tool == ktc.TOOL_NONE:
        #     self.disengage()
        # else:
        #     self.engage(True)
        #     self.log.always(
        #     )

        # self.ktc.active_tool = self.active_tool

    def engage(self, ignore_engaged=False) -> bool:
        try:
            if self.state < STATE.INITIALIZING:
                raise Exception(
                    "Status is: %s." % STATE.value_to_key_string(self.state)
                )

            if self.engage_gcode_template is None:
                raise Exception(
                    "No tool lock gcode template defined."
                )

            if not ignore_engaged and self.state == STATE.ENGAGED:
                self.log.always(
                    "ktc_toolchanger %s is already engaged with tool %s."
                    % (self.name, self.ktc.active_tool.name)
                    + " IGNORE_ENGAGED is not set. No action taken."
                )
                return True

            self.state = STATE.ENGAGING
            context = self.init_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            context['STATE'] = STATE
            context['INIT_MODE'] = INIT_MODE
            self.log.trace("ktc_toolchanger.engage() running. ")
            self.engage_gcode_template.run_gcode_from_command(context)
            self.log.trace("Tool engaged successfully.")

            self.log.changer_stats[self.name].engages += 1
            self.state = STATE.ENGAGED
            return True
        except Exception as e:
            self.log.always("ktc_toolchanger.disengage(): failed for ktc_toolchanger %s with error: %s" % (self.name, e))
            self.state = STATE.ERROR
            return False

    def disengage(self) -> bool:
        """Disengage the lock on the tool so it can be removed.
        Return: True if successful, False if not."""
        
        try:
            if self.state < STATE.INITIALIZING:
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
            self.state = STATE.DISENGAGING
            context = self.init_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            context['STATE'] = STATE
            context['INIT_MODE'] = INIT_MODE
            self.log.trace("ktc_toolchanger.disengage() running. ")
            self.disengage_gcode_template.run_gcode_from_command(context)
            self.log.trace("Tool disengaged successfully.")

            # Add disengage to statistics.
            self.log.changer_stats[self.name].disengages += 1
            
            self.state = STATE.READY
            return True
        except Exception as e:
            self.log.always("ktc_toolchanger.disengage(): failed for ktc_toolchanger %s with error: %s" % (self.name, e))
            self.state = STATE.ERROR
            return False

    def get_status(self, eventtime=None):
        status = {
            # "global_offset": self.global_offset,
            "name": self.name,
            "active_tool": self.active_tool.name,
            # "active_tool_n": self.active_tool.number,
            "state": self.state,
            "init_mode": self.init_mode,
            "tools": list(self.tools.keys()),
            # "saved_fan_speed": self.saved_fan_speed,
            # "purge_on_toolchange": self.purge_on_toolchange,
            # "restore_axis_on_toolchange": self.restore_axis_on_toolchange,
            # "saved_position": self.saved_position,
            # "last_endstop_query": self.last_endstop_query
            **self.params,
        }
        return status

@dataclasses.dataclass
class STATE:
    """Constants for the status of the toolchanger.
    Using dataclasses to allow for easy traversal of the values."""
    ERROR: int = -3
    UNINITIALIZED: int = -2
    INITIALIZING: int = -1
    INITIALIZED: int = 0
    READY: int = 1
    CHANGING: int = 2
    ENGAGING: int = 3
    DISENGAGING: int = 4
    ENGAGED: int = 5
    # Return the attr name of the status from the value.
    @staticmethod
    def value_to_key_string(status):
        r = [field.name for field in dataclasses.fields(STATE) if field.default == int(status)]
        if len(r) == 0:
            return None
        else:
            return r[0]
    def list_valid_values(self):
        return _list_valid_values_of_dataclass(self)
    @staticmethod
    def get_value_from_configuration(configured_value):
        return _get_value_from_configuration_for_dataclass(STATE, configured_value)
    
@dataclasses.dataclass
class INIT_MODE:
    """Constants for the initialization mode of the toolchanger."""
    MANUAL: str = "manual"
    ON_START: str = "on_start"
    ON_FIRST_USE: str = "on_first_use"
    HOMING_START: str = "homing_start"
    HOMING_END: str = "homing_end"
    @staticmethod
    def list_valid_values():
        return _list_valid_values_of_dataclass(INIT_MODE)
    @staticmethod
    def get_value_from_configuration(configured_value):
        return _get_value_from_configuration_for_dataclass(INIT_MODE, configured_value)

@dataclasses.dataclass
class INIT_ORDER:
    """Constants for the initialization order of the toolchanger."""
    INDEPENDENT : str = "independent"
    # BEFORE_PARENT_SELECTED : str = "before_parent_selected"
    AFTER_PARENT_SELECTED : str = "after_parent_selected"
    # BEFORE_PARENT_INITIALIZATION : str = "before_parent_initialization"
    AFTER_PARENT_INITIALIZATION : str = "after_parent_initialization"
    @staticmethod
    def list_valid_values():
        return _list_valid_values_of_dataclass(INIT_ORDER)
    @staticmethod
    def get_value_from_configuration(configured_value):
        return _get_value_from_configuration_for_dataclass(INIT_ORDER, configured_value)

@dataclasses.dataclass
class __KTCToolchanger_Parameters:
    q=1
    @staticmethod
    def list_valid_values():
        """Return a list of valid values for the parameters."""
        return True
        

def _get_value_from_configuration_for_dataclass(c: dataclasses.dataclass, configured_value: str):
    r = [field.default for field in dataclasses.fields(c) if str.lower(field.name) == str.lower(configured_value)]
    if len(r) == 0:
        return None
    else:
        return r[0]
    # return next((field.value for field in dataclasses.fields(c) if str.lower(field.name) == str.lower(configured_value)), None)

def _list_valid_values_of_dataclass(c):
    return [field.name for field in dataclasses.fields(c)]

# def _get_attr_key_name_from_value(c, status):
#     return next((key for key, value in dataclasses.asdict(c) if value == status), None)

def load_config_prefix(config):
    """Load the toolchanger object with the given config.
    This is called by Klipper to initialize the toolchanger object."""
    return KtcToolchanger(config)
