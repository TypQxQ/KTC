# KTC - Klipper Tool Changer code
# Toollock and general Tool support
#
# Copyright (C) 2024  Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

from enum import unique
import typing
from .ktc_base import *

# from . import ktc

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from .klippy import configfile
    # from .klippy import klippy, gcode
    from .klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_persisting, ktc_tool

class KtcToolchanger(KtcBaseChangerClass, KtcConstantsClass):
    """Class initialized for each toolchanger.
    At least one toolchanger will be initialized for each printer.
    A "default_toolchanger" will be initialized if no toolchanger
    is specified in the config."""

    def __init__(self, config: 'configfile.ConfigWrapper'):
        # Most of the function is inherited from the base class.
        super().__init__(config)

        # When is the toolchanger initialized in relation to printer start and homing.
        self.init_mode = self.InitModeType.get_value_from_configuration(
            config, "init_mode", self.InitModeType.MANUAL)        # type: ignore

        # And in relation to the parent tool.
        self.init_order = self.InitOrderType.get_value_from_configuration(
            config, "init_order", self.InitOrderType.INDEPENDENT)

        self.selected_tool = self.TOOL_UNKNOWN  # The currently active tool. Default is unknown.

        # Load the parent tool if it is defined.
        self.parent_tool = None
        parent_tool_name = config.get("parent_tool", None)  # type: ignore
        if parent_tool_name is not None:
            self.parent_tool = typing.cast('ktc_tool.KtcTool', self.printer.load_object(
                config, "ktc_tool " + parent_tool_name))  # type: ignore
            if self.parent_tool is None:
                raise config.error(
                    "parent_tool %s not found for ktc_toolchanger %s."
                    % (parent_tool_name, self.name)
                )

    def configure_inherited_params(self):
        super().configure_inherited_params()
        # Ref. to the ktc_persisting object. Loaded by ktc_log.
        self.ktc_persistent: 'ktc_persisting.KtcPersisting' = ( # type: ignore
            self.printer.lookup_object("ktc_persisting")
        )

        self.gcode_macro = typing.cast('klippy_gcode_macro.PrinterGCodeMacro',
                                  self.printer.lookup_object("gcode_macro"))    # type: ignore

        self.state = self.StateType.CONFIGURED

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
                "Toolchanger %s has no parent tool " % self.name
                + "defined but init_order is set to AFTER_PARENT."
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
            if (self.parent_tool is not None and 
                self.parent_tool.toolchanger.state < self.StateType.READY):
                raise Exception(
                    "Toolchanger %s has parent tool %s that resides on toolchanger %s " 
                    % (self.name, self.parent_tool.name, self.parent_tool.toolchanger.name) +
                    "that is not ready but init_order for this toolchanger"
                    + "is set to AFTER_PARENT_SELECTED."
                )

            if (self.parent_tool is not None and
                self.parent_tool.toolchanger.state < self.StateType.ENGAGED and
                self.parent_tool.toolchanger.selected_tool != self.parent_tool):
                self.parent_tool.select()

        # Get the active tool from the persistent variables.
        active_tool_name = str.lower(self.persistent_state.get(
            "active_tool", self.TOOL_UNKNOWN.name
        ))

        # Set the active tool to the tool with the name from the persistent variables.
        # If not found in the tools that are loaded for this changer, set it to TOOL_UNKNOWN.
        self.selected_tool = self.tools.get(active_tool_name, None)
        if self.selected_tool is None:
            self.selected_tool = self.TOOL_UNKNOWN
            self.log.always(
                "ktc_toolchanger.initialize(): Active tool "
                + "%s not found for ktc_toolchanger %s. Using tool %s."
                % (active_tool_name, self.name, self.selected_tool.name)
            )

        self.log.trace("ktc_toolchanger[%s].initialize(): Loaded persisted active tool: %s." 
                       % (self.name, self.selected_tool.name))

        # Run the init gcode template if it is defined.
        if self._init_gcode != "":
            init_gcode_template = self.gcode_macro.load_template(   # type: ignore
            self.config, "", self._init_gcode)
            context = init_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self._ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            init_gcode_template.run_gcode_from_command(context)
        else:
            self.state = self.StateType.INITIALIZED
            
        self.log.trace("ktc_toolchanger[%s].initialize(): Complete." % self.name)
        self.log.trace("ktc_toolchanger[%s].selected_tool: %s." % (self.name, self.selected_tool.name))
        self.log.trace("ktc_toolchanger[%s].state: %s." % (self.name, self.state))
        
        if self._ktc.default_toolchanger == self:
            self._ktc.selected_tool = self.selected_tool
            self.log.trace("ktc.active_tool set to: %s." % self._ktc.active_tool.name)
           
        
    
        # if self.selected_tool == self.TOOL_NONE:
        #     self.disengage()
        # else:
        #     self.engage(True)
        #     self.log.always(
        #     )

        # self._ktc.active_tool = self.selected_tool

    def engage(self, ignore_engaged=False) -> bool:
        try:
            if self.state < self.StateType.INITIALIZING:
                raise Exception(
                    "Status is: %s. Can't engage %s." % (self.state, self.name)
                )

            if self.engage_gcode_template is None:
                raise Exception(
                    "No tool lock gcode template defined."
                )

            if not ignore_engaged and self.state == self.StateType.ENGAGED:
                self.log.always(
                    "ktc_toolchanger %s is already engaged with tool %s."
                    % (self.name, self._ktc.active_tool.name)
                    + " IGNORE_ENGAGED is not set. No action taken."
                )
                return True

            self.state = self.StateType.ENGAGING
            context = self.engage_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self._ktc.get_status()
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
                
            if self._disengage_gcode == "":
                self.state = self.StateType.READY
                return True

            disengage_gcode_template = self.gcode_macro.load_template(
                self.config, "", self._disengage_gcode)
            # Run the disengage gcode template.
            self.log.trace("ktc_toolchanger.disengage(): Setting state to DISENGAGING.")
            self.state = self.StateType.DISENGAGING.value
            self.log.trace("ktc_toolchanger.disengage(): Getting context for disengage_gcode_template.")
            context = disengage_gcode_template.create_template_context()
            self.log.trace("ktc_toolchanger.disengage(): Setting myself in context.")
            context['myself'] = self.get_status()
            self.log.trace("ktc_toolchanger.disengage(): Setting ktc in context.")
            context['ktc'] = self._ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            self.log.trace("ktc_toolchanger.disengage() running. ")
            disengage_gcode_template.run_gcode_from_command(context)
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
            "selected_tool": self.selected_tool.name,
            "selected_tool_n": self.selected_tool.number,
            "state": self.state,
            "init_mode": self.init_mode,
            "tool_names": list(self.tools),
            # "saved_fan_speed": self.saved_fan_speed,
            # "purge_on_toolchange": self.purge_on_toolchange,
            # "restore_axis_on_toolchange": self.restore_axis_on_toolchange,
            # "saved_position": self.saved_position,
            **self.params,
        }
        return status

    @unique
    class InitModeType(str, KtcConfigurableEnum):
        """Constants for the initialization mode of the toolchanger.
        Inherits from str so it can be JSON serializable."""
        MANUAL = "manual"
        ON_START = "on_start"
        ON_FIRST_USE = "on_first_use"
        # Can be manual and call KTC_TOOLCHANGER_INITIALIZE from gcode homing macro.
            # HOMING_START = "homing_start"
            # HOMING_END = "homing_end"

    @unique
    class InitOrderType(str, KtcConfigurableEnum):
        """Constants for the initialization order of the toolchanger."""
        INDEPENDENT  = "independent"
        AFTER_PARENT_SELECTED = "after_parent_selected"
        AFTER_PARENT_INITIALIZATION = "after_parent_initialization"
        # BEFORE_PARENT_SELECTED  = "before_parent_selected"
        # BEFORE_PARENT_INITIALIZATION = "before_parent_initialization"

def load_config_prefix(config):
    """Load the toolchanger object with the given config.
    This is called by Klipper to initialize the toolchanger object."""
    return KtcToolchanger(config)
