# KTC - Klipper Tool Changer code
# Toollock and general Tool support
#
# Copyright (C) 2024  Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

import dataclasses
from . import ktc as ktc, ktc_persisting, ktc_log, ktc_tool


class KtcToolchanger:
    """Class initialized for each toolchanger.
    At least one toolchanger will be initialized for each printer.
    A "default_toolchanger" will be initialized if no toolchanger
    is specified in the config."""

    # Initialize general static class variables.
    printer = None
    reactor = None
    gcode = None
    ktc = None
    log = None
    ktc_persistent = None

    def __init__(self, config):
        """_summary_

        Args:
            config (Klipper configuration): required for initialization.

        Returns:
            _type_: _description_
        """
        # Initialize general class variables if not already initialized.
        if KtcToolchanger.printer is None:
            self.printer = config.get_printer()
            self.reactor = self.printer.get_reactor()
            self.gcode = self.printer.lookup_object("gcode")
            self.ktc: ktc.Ktc = self.printer.load_object(config, "ktc")
            self.log: ktc_log.Ktc_Log = self.printer.load_object(
                config, "ktc_log"
            )  # Load the log object.
            self.ktc_persistent: ktc_persisting.KtcPersisting = (
                self.printer.load_object(config, "ktc_persisting")
            )  # Load the ktc_persisting object.

        # Initialize object variables.
        self.name: str = config.get_name().split(" ", 1)[1]
        self.params = ktc.get_params_dict_from_config(config)
        self.status = STATUS.UNINITIALIZED
        self.tools: dict[str, ktc_tool.KtcTool] = {}  # All tools on this toolchanger.
        self.init_mode = INIT_MODE.MANUAL
        self.active_tool = (
            ktc.TOOL_UNKNOWN  # The currently active tool. Default is unknown.
        )

        ######
        # TODO: Check if implemented and if needs to move to ktc or ktc_tool.
        self.saved_fan_speed = (
            0  # Saved partcooling fan speed when deselecting a tool with a fan.
        )

        self.restore_axis_on_toolchange = ""  # string of axis to restore: XYZ
        self.tool_map = {}
        self.last_endstop_query = {}
        self.changes_made_by_set_all_tool_heaters_off = {}
        self.saved_position = None
        ######


        # G-Code macros
        gcode_macro = self.printer.load_object(config, "gcode_macro")
        self.engage_gcode_template = gcode_macro.load_template(
            config, "engage_gcode", ""
        )
        self.disengage_gcode_template = gcode_macro.load_template(
            config, "disengage_gcode", ""
        )
        self.init_gcode_template = gcode_macro.load_template(
            config, "tool_init_gcode", ""
        )

        # Add itself to the list of toolchangers if not already added.
        if self.ktc.toolchangers.get(self.name) is None:
            self.ktc.toolchangers[self.name] = self
        else:
            raise Exception(
                "KtcToolchanger: Toolchanger %s already registered." % self.name
            )

        # Register handlers for events.
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

    def handle_ready(self):
        if self.init_mode == INIT_MODE.ON_START:
            self.initialize()

    def initialize(self):
        """Initialize the tool lock."""
        if self.status > STATUS.UNINITIALIZED:
            self.log.always(
                "ktc_toolchanger.initialize(): Toolchanger %s already initialized." % self.name
            )
            return None
        
        # Get the active tool from the persistent variables.
        active_tool_name = self.ktc_persistent.content.get(
            "tool_current", ktc.TOOL_NONE.name
        )

        # Run the init gcode template.
        context = self.init_gcode_template.create_template_context()
        context['myself'] = self.get_status()
        context['ktc'] = self.ktc.get_status()
        self.pickup_gcode_template.run_gcode_from_command(context)


        if active_tool_name == ktc.TOOL_NONE.name:
            self.active_tool = ktc.TOOL_NONE
        elif active_tool_name == ktc.TOOL_UNKNOWN.name:
            self.active_tool = ktc.TOOL_UNKNOWN
        else:
            self.active_tool = self.printer.load_object(
                self.printer.config, "ktc_tool " + active_tool_name
            )

        self.ktc.active_tool = self.active_tool

        self.log.trace("KTC initialized with active tool: %s." % self.active_tool.name)

        if self.active_tool == ktc.TOOL_NONE:
            self.disengage()
        else:
            self.engage(True)
            self.log.always(
            )

        self.ktc.active_tool = self.active_tool

    def engage(self, ignore_engaged=False) -> bool:
        if self.engage_gcode_template is None:
            self.log.always(
                "ktc_toolchanger.engage(): No tool lock gcode template"
                + " defined for ktc_toolchanger %s." % self.name
            )
            return None

        self.log.trace("ktc_toolchanger.engage() running. ")
        if not ignore_engaged and int(self.ktc.active_tool) != ktc.TOOL_NONE_N:
            self.log.always(
                "ktc_toolchanger %s is already locked with tool %s."
                % (self.name, self.ktc.active_tool.name)
            )
        else:
            self.engage_gcode_template.run_gcode_from_command()
            self.ktc.active_tool = ktc.TOOL_UNKNOWN
            self.log.trace("Tool Locked")
            self.log.changer_stats[self.name].engages += 1

    def disengage(self) -> bool:
        """Disengage the lock on the tool so it can be removed.
        Return: True if successful, False if not."""
        
        try:
            if self.status < STATUS.READY:
                raise Exception(
                    "Toolchanger %s not ready." % self.name
                )
                
            if self.disengage_gcode_template is None:
                self.log.debug(
                    "ktc_toolchanger.disengage(): No tool unlock gcode template"
                    + " defined for ktc_toolchanger %s." % self.name
                )
                return true

            # Run the disengage gcode template.
            # TODO: Add context. Myself, ktc, etc.
            self.disengage_gcode_template.run_gcode_from_command()

            # TODO: Check if this is apropiate.
            self.ktc.active_tool = ktc.TOOL_NONE
            
            # Add disengage to statistics.
            self.log.trace("Adding disengage to statistics: %s" % (self.log.changer_stats[self.name].disengages))
            self.log.changer_stats[self.name].disengages += 1
            self.log.trace("Added disengage to statistics: %s" % (self.log.changer_stats[self.name].disengages))
            
            return True
        except Exception as e:
            self.log.always("ktc_toolchanger.disengage(): failed for ktc_toolchanger %s with error: %s" % (self.name, e))
            return False

    def get_status(self, eventtime=None):
        status = {
            # "global_offset": self.global_offset,
            "name": self.name,
            "active_tool": self.active_tool.name,
            "active_tool_n": self.active_tool.number,
            # "saved_fan_speed": self.saved_fan_speed,
            # "purge_on_toolchange": self.purge_on_toolchange,
            # "restore_axis_on_toolchange": self.restore_axis_on_toolchange,
            # "saved_position": self.saved_position,
            # "last_endstop_query": self.last_endstop_query
        }
        return status


# @dataclasses.dataclass
class STATUS:
    """Constants for the status of the toolchanger."""
    ERROR = -3
    UNINITIALIZED = -2
    INITIALIZING = -1
    INITIALIZED = 0
    READY = 1
    CHANGING = 2
    ENGAGING = 3
    ENGAGED = 4
    def get_name(self, status):
        return next((key for key, value in dataclasses.asdict(self) if value == status), None)
    
class INIT_MODE:
    """Constants for the initialization mode of the toolchanger."""
    MANUAL = "manual"
    ON_START = "on_start"
    ON_FIRST_USE = "on_first_use"

def load_config_prefix(config):
    return KtcToolchanger(config)
