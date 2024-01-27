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

    def __init__(self, config, name: str = None):
        """_summary_

        Args:
            config (Klipper configuration): required for initialization.
            name (str, optional): Name to use when called to add . Defaults to None.

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
        self.name = name
        self.params = {}
        self.status = KtcToolchangerStatus.uninitialized
        self.init_printer_to_last_tool = True
        self.tool_lock_gcode_template = None
        self.tool_unlock_gcode_template = None

        self.saved_fan_speed = (
            0  # Saved partcooling fan speed when deselecting a tool with a fan.
        )
        self.active_tool = (
            ktc.TOOL_UNKNOWN  # The currently active tool. Default is unknown.
        )
        self.tools: dict[str, ktc_tool.KtcTool] = {}  # List of all tools.
        self.saved_position = None
        self.restore_axis_on_toolchange = ""  # string of axis to restore: XYZ
        self.tool_map = {}
        self.last_endstop_query = {}
        self.changes_made_by_set_all_tool_heaters_off = {}


        self.log.trace("Toolchanger %s has configuration section: %s" % (self.name, config.get_name()))

        # When initialized from another component it has no own config section.
        # if not config.get_name().startswith("ktc_toolchanger"):
        #     return None

        self.name: str = config.get_name().split(" ", 1)[1]

        # Add itself to the list of toolchangers if not already added.
        if self.ktc.toolchangers.get(self.name) is None:
            self.ktc.toolchangers[self.name] = self
        else:
            self.log.always(
                "KtcToolchanger: Toolchanger %s already registered." % self.name
            )

        self.params = ktc.get_params_dict_from_config(config)

        self.log.trace("KtcToolchanger: Loading config for %s." % self.name)
        
        self.init_printer_to_last_tool = config.getboolean(
            "init_printer_to_last_tool", True
        )

        # G-Code macros
        gcode_macro = self.printer.load_object(config, "gcode_macro")
        self.tool_lock_gcode_template = gcode_macro.load_template(
            config, "tool_lock_gcode", ""
        )
        self.tool_unlock_gcode_template = gcode_macro.load_template(
            config, "tool_unlock_gcode", ""
        )

        # Register handlers for events.
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        

    def handle_ready(self):
        self.initialize_tool_lock()

    def initialize_tool_lock(self):
        if not self.init_printer_to_last_tool:
            return None

        active_tool_name = self.ktc_persistent.vars.get(
            "tool_current", ktc.TOOL_NONE.name
        )
        if active_tool_name == ktc.TOOL_NONE.name:
            self.active_tool = ktc.TOOL_NONE
        elif active_tool_name == ktc.TOOL_UNKNOWN.name:
            self.active_tool = ktc.TOOL_UNKNOWN
        else:
            self.active_tool = self.printer.load_object(
                self.printer.config, "ktc_tool " + active_tool_name
            )

        self.ktc.active_tool = self.active_tool

        self.log.trace("KTC initialized with active tool: %s." % self.active_tool)

        # TODO: Change this to use name instead of number.
        if self.active_tool == ktc.TOOL_NONE:
            self.disengage()
            self.log.always("KTC initialized with unlocked ToolLock")
        else:
            self.engage(True)
            self.log.always(
                "KTC initialized with KTC Tool %s." % self.ktc.active_tool.name
            )

        self.ktc.active_tool = self.active_tool

    # cmd_KTC_TOOLCHANGER_ENGAGE_help = "Lock the ToolLock."
    # def cmd_KTC_TOOLCHANGER_ENGAGE(self, gcmd = None):
    #     self.engage()

    def engage(self, ignore_locked=False):
        if self.tool_lock_gcode_template is None:
            self.log.always(
                "ktc_toolchanger.engage(): No tool lock gcode template" +
                " defined for ktc_toolchanger %s." % self.name
            )
            return None

        self.log.trace("ktc_toolchanger.engage() running. ")
        if not ignore_locked and int(self.ktc.active_tool) != ktc.TOOL_NONE_N:
            self.log.always(
                "ktc_toolchanger %s is already locked with tool %s."
                % (self.name, self.ktc.active_tool.name)
            )
        else:
            self.tool_lock_gcode_template.run_gcode_from_command()
            self.ktc.active_tool = ktc.TOOL_UNKNOWN
            self.log.trace("Tool Locked")
            self.log.total_stats.toollocks += 1

    # cmd_KTC_TOOLCHANGER_DISENGAGE_help = "Unlock the ToolLock."
    # def cmd_KTC_TOOLCHANGER_DISENGAGE(self, gcmd = None):
    #     self.disengage()

    def disengage(self):
        if self.tool_unlock_gcode_template is None:
            self.log.always(
                "ktc_toolchanger.disengage(): No tool unlock gcode template" +
                " defined for ktc_toolchanger %s." % self.name
            )
            return None

        self.log.trace("KTC_TOOLCHANGER_DISENGAGE running.")
        self.tool_unlock_gcode_template.run_gcode_from_command()
        self.ktc.active_tool = ktc.TOOL_NONE
        self.log.trace("ToolLock Unlocked.")
        self.log.total_stats.toolunlocks += 1


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
class KtcToolchangerStatus:
    uninitialized = -1
    initialized = 0
    ready = 1
    engaged = 2
    

def load_config_prefix(config):
    return KtcToolchanger(config)
