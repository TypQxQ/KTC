# KTC - Klipper Tool Changer code (v.2)
# Toollock and general Tool support
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
from __future__ import annotations
import typing

# from .ktc_base import * # pylint: disable=relative-beyond-top-level, wildcard-import
from .ktc_base import (
    KtcConstantsClass,
    KtcBaseClass,
    KtcBaseToolClass,
)
from .ktc_heater import HeaterStateType

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy.extras import (
        heaters as klippy_heaters,
        gcode_move as klippy_gcode_move,
    )
    from . import ktc_log, ktc_persisting, ktc_toolchanger, ktc_tool, ktc_heater

# Constants for the restore_axis_on_toolchange variable.
XYZ_TO_INDEX: dict[str, int] = {"x": 0, "X": 0, "y": 1, "Y": 1, "z": 2, "Z": 2}
INDEX_TO_XYZ: dict[int, str] = {0: "X", 1: "Y", 2: "Z"}
DEFAULT_WAIT_FOR_TEMPERATURE_TOLERANCE = 1  # Default tolerance in degC.
# Don't wait for temperatures below this because they might be ambient.
LOWEST_ALLOWED_TEMPERATURE_TO_WAIT_FOR = 40
_OFFSET_HELP = (
    "\n[X: X position] or [X_ADJUST: X adjust]\n"
    + "[Y: Y position] or [Y_ADJUST: Y adjust]\n"
    + "[Z: Z position] or [Z_ADJUST: Z adjust]\n"
)

_TOOL_HELP = "\n [TOOL: Tool name] or [T: Tool number]"


class Ktc(KtcBaseClass, KtcConstantsClass):

    def __init__(self, config: "configfile.ConfigWrapper"):
        super().__init__(config)

        self.propagate_state = config.getboolean("propagate_state", True)  # type: ignore

        ############################
        # Load the persistent variables object
        self._ktc_persistent = typing.cast(
            "ktc_persisting.KtcPersisting",
            self.printer.load_object(config, "ktc_persisting"),
        )

        self.saved_fan_speed = (
            0  # Saved partcooling fan speed when deselecting a tool with a fan.
        )

        self.all_tools: dict[str, "ktc_tool.KtcTool"] = {}
        self.all_tools_by_number: dict[int, "ktc_tool.KtcTool"] = {}
        self._registered_toolnumbers: list[int] = []
        self.all_toolchangers: dict[str, "ktc_toolchanger.KtcToolchanger"] = {}
        self._tools_having_tc: typing.Dict[
            "ktc_tool.KtcTool", "ktc_toolchanger.KtcToolchanger"
        ] = {}
        self.all_heaters: dict[str, "ktc_heater.KtcHeater"] = {}

        self.__active_tool = self.TOOL_UNKNOWN  # The currently active tool.

        # Gets the name here and connects to a toolchanger object later
        # when all objects are loaded.
        self.default_toolchanger_name: str = config.get("default_toolchanger", "")  # type: ignore
        self.default_toolchanger: "ktc_toolchanger.KtcToolchanger" = None  # type: ignore

        self._heaters_paused = {}
        self._saved_position = [None, None, None]

        self.global_offset = [0, 0, 0]  # Global offset for all tools.
        self.global_offset = config.get("global_offset", "0,0,0")  # type: ignore
        if isinstance(self.global_offset, str):
            offset_list = self.global_offset.split(",")
            if len(offset_list) == 3 and all(
                x.replace(".", "").isdigit() for x in offset_list
            ):
                self.global_offset = [float(x) for x in offset_list]
            else:
                raise ValueError(
                    "global_offset is not a string containing 3 float numbers separated by ,"
                )
        else:
            raise TypeError("global_offset is not a string")

        # Register events
        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        # self.printer.register_event_handler("klippy:disconnect", self.handle_disconnect)

    def _handle_connect(self):
        """This method is called when all objects are loaded, initialized and configured."""
        # Reference the log object here to avoid circular imports.
        self.log = typing.cast(  # pylint: disable=attribute-defined-outside-init
            "ktc_log.KtcLog", self.printer.lookup_object("ktc_log")
        )

        ############################
        # Configure default toolchanger and tools
        self._config_default_toolchanger()
        self._config_tools()

        ############################
        # Configure inherited parameters
        self.configure_inherited_params()
        self._recursive_configure_inherited_attributes(self.default_toolchanger)

        # Control that all tools and toolchangers are configured.
        if self.state < self.StateType.CONFIGURED:
            raise ValueError("KTC did not configure properly.")
        for tc in self.all_toolchangers.values():
            if tc.state < tc.StateType.CONFIGURED:
                raise ValueError("Toolchanger %s did not configure properly." % tc.name)
        for tool in self.all_tools.values():
            if tool.state < tool.StateType.CONFIGURED:
                raise ValueError("Tool %s did not configure properly." % tool.name)

        # Register commands
        handlers = [
            "KTC_DROPOFF",
            "KTC_TEMPERATURE_WAIT_WITH_TOLERANCE",
            "KTC_SET_AND_SAVE_PARTFAN_SPEED",
            "KTC_GLOBAL_OFFSET_SAVE",
            "KTC_SET_TOOL_TEMPERATURE",
            "KTC_TOOL_OFFSET_SAVE",
            "KTC_TOOL_OFFSET_APPLY",  # Maybe remove?
            "KTC_SET_STATE",
            "KTC_TOOL_SET_STATE",
            "KTC_TOOLCHANGER_SET_STATE",
            "KTC_TOOLCHANGER_SET_SELECTED_TOOL",
            "KTC_SET_ACTIVE_TOOL",
            "KTC_TOOLCHANGER_ENGAGE",
            "KTC_TOOLCHANGER_DISENGAGE",
            "KTC_HEATERS_PAUSE",
            "KTC_HEATERS_RESUME",
            "KTC_TOOLCHANGER_INITIALIZE",
            "KTC_TOOLS_DISPLAY",
            "KTC_TOOL_MAP_NR",
            "KTC_DEBUG_HEATERS",
            "KTC_DEBUG_TOOLS",
        ]
        for cmd in handlers:
            func = getattr(self, "cmd_" + cmd)
            desc = getattr(self, "cmd_" + cmd + "_help", None)
            self.gcode.register_command(cmd, func, False, desc)

    def _handle_ready(self):
        """This method is called when the printer is ready to print."""
        # Initialize all toolchangers that have init_mode == ON_START.
        self._recursive_initialize_toolchangers(
            self.default_toolchanger,
            self.default_toolchanger.__class__.InitModeType.ON_START,
        )
        self._register_tool_gcode_commands()

    def _config_default_toolchanger(self):
        """Set the default toolchanger and validate it."""
        # If a default toolchanger name is specified, validate it and set it as default.
        if not self.default_toolchanger_name.strip() == "":
            self.default_toolchanger = typing.cast(
                "ktc_toolchanger.KtcToolchanger",
                self.printer.lookup_object(
                    "ktc_toolchanger " + self.default_toolchanger_name, None
                ),  # type: ignore
            )
            # Handle different errors if the default toolchanger is not found.
            if self.default_toolchanger is None:
                if len(self.all_toolchangers) == 0:
                    raise self.config.error(
                        "No toolchangers found. Can't set default toolchanger to %s."
                        % self.default_toolchanger_name
                    )
                else:
                    raise self.config.error(
                        (
                            "default_toolchanger %s in section [ktc] is not a valid"
                            % self.default_toolchanger_name
                        )
                        + (
                            " toolchanger. Toolchangers found: %s."
                            % str(self.all_toolchangers.keys())
                        )
                    )
        # If no default toolchanger specified and no toolchangers, create a default toolchanger.
        elif len(self.all_toolchangers) == 0:
            self.log.trace("No toolchangers defined. Creating default toolchanger.")
            # The toolchanger init will add itself to the list of toolchangers.
            _ = self.printer.load_object(
                self.config, "ktc_toolchanger default_toolchanger"
            )

        # If only one toolchanger and no default toolchanger is specified, set it as default.
        elif len(self.all_toolchangers) == 1 and self.default_toolchanger is None:
            self.log.trace("Only one toolchanger defined. Setting it as default.")
            self.default_toolchanger = list(self.all_toolchangers.values())[0]

            # Check if the now default toolchanger has a parent tool. If so raise error.
            if self.default_toolchanger.parent_tool is not None:
                raise self.config.error(
                    "Only toolchanger %s can't have a parent tool."
                    % self.default_toolchanger.name
                )
        elif len(self.all_toolchangers) > 1 and self.default_toolchanger is None:
            raise self.config.error(
                "More than one toolchanger defined but no default toolchanger set."
                + "Please set default_toolchanger in the [ktc] section of your printer.cfg file."
            )
        else:
            raise self.config.error(
                "Unknow logic error. Can't set default toolchanger to %s."
                % self.default_toolchanger_name
            )

        if self.default_toolchanger.parent_tool is not None:
            raise self.config.error(
                "The default toolchanger %s can't have a parent tool."
                % self.default_toolchanger.name
            )

        # Add all toolchangers to the list of all toolchangers.
        tc: "ktc_toolchanger.KtcToolchanger"
        for tc in dict(self.printer.lookup_objects("ktc_toolchanger")).values():
            self.all_toolchangers[tc.name] = tc
            # Check so all toolchangers besides the default toolchanger have a parent tool.
            if self.default_toolchanger != tc and tc.parent_tool is None:
                raise self.config.error(
                    "Toolchanger %s has no parent_tool while it is not the default toolchanger."
                    % tc.name
                )

    def _config_tools(self):
        """
        Add all tools to the list of all tools and validate them.
        - All objects are loaded and initialized at this point.
        - All inherited parameters are configured at this point.
        - All toolchangers are configured at this point.
        """
        tool: "ktc_tool.KtcTool"
        # For each tool that is defined in the config file:
        for tool in dict(self.printer.lookup_objects("ktc_tool")).values():
            if tool.toolchanger is None:
                tool.toolchanger = self.default_toolchanger
            tool.toolchanger.tools[tool.name] = tool
            self.all_tools[tool.name] = tool

            if tool.number is not None:
                if tool.number not in self.all_tools_by_number:
                    self.all_tools_by_number[tool.number] = tool
                else:
                    raise self.config.error(
                        "Tool number %d is already used by tool %s."
                        % (tool.number, self.all_tools_by_number[tool.number].name)
                    )

        for tc in self.all_toolchangers.values():
            self._tools_having_tc[tc.parent_tool] = tc
            for tool in (self.TOOL_NONE, self.TOOL_UNKNOWN):
                self.all_tools[tool.name] = tool

        for tool in (self.TOOL_NONE, self.TOOL_UNKNOWN):
            self.all_tools[tool.name] = tool

    def _register_tool_gcode_commands(self):
        """Register Gcode commands for all tools having a number."""
        new_toolnumbers: list[int] = []
        for tool in self.all_tools.values():
            if tool.number is not None and tool.number > self.TOOL_NONE_N:
                new_toolnumbers.append(tool.number)
                if tool.number not in self._registered_toolnumbers:
                    self._registered_toolnumbers.append(tool.number)
                self.gcode.register_command(
                    "KTC_T" + str(tool.number),
                    tool.select,
                    False,
                    "Select tool " + tool.name + " with number " + str(tool.number),
                )
        # Get all toolnumbers from self._registered_toolnumbers that are not in new_toolnumbers.
        for toolnumber in (
            x for x in self._registered_toolnumbers if x not in new_toolnumbers
        ):
            self.gcode.register_command("KTC_T" + str(toolnumber), None)

    def _recursive_configure_inherited_attributes(
        self, tc: "ktc_toolchanger.KtcToolchanger"
    ):
        """Recursively configure inherited parameters for all toolchangers and tools."""
        tc.configure_inherited_params()
        for tool in (
            tool for tool in tc.tools.values() if tool.toolchanger is not None
        ):
            tool.configure_inherited_params()
            # If this tool is a parent for a toolchanger
            if tool in self._tools_having_tc:
                # Run this method for the toolchanger that has this tool as a parent.
                self._recursive_configure_inherited_attributes(
                    self._tools_having_tc[tool]
                )

    def _recursive_initialize_toolchangers(
        self,
        tc: "ktc_toolchanger.KtcToolchanger",
        init_mode: "ktc_toolchanger.KtcToolchanger.InitModeType",
    ):
        """Initialize all toolchangers that have init_mode == ON_START
        and have a parent tool that has been initialized."""
        if tc.init_mode == init_mode:
            tc.initialize()

        # Check if any toolchangers exist on next level and run this method for them.
        for tool in (
            tool for tool in tc.tools.values() if tool in self._tools_having_tc
        ):
            self._recursive_initialize_toolchangers(
                self._tools_having_tc[tool], init_mode
            )

    def configure_inherited_params(self):
        super().configure_inherited_params()
        self.state = self.StateType.CONFIGURED

    @property
    def active_tool(self) -> KtcBaseToolClass:
        return self.__active_tool

    @active_tool.setter
    def active_tool(self, value: typing.Union[str, KtcBaseToolClass]):
        if isinstance(value, KtcBaseClass):
            tool = value
        elif isinstance(value, str):
            tool = self.all_tools.get(value, None)
            if tool is None:
                raise ValueError("active_tool: tool name not found: %s." % str(value))

        elif isinstance(value, int):  # If value is an int for backwayds compatibility.
            tool = self.all_tools_by_number.get(value, None)
            if tool is None:
                raise ValueError("active_tool: tool number not found: %s." % str(value))
        else:
            raise TypeError(
                "active_tool must be a KtcTool, a string representing the tool name"
                + " or an int representing the current tool number."
            )

        self.__active_tool = tool

        # Set the active tool in the toolchanger if not TOOL_NONE or TOOL_UNKNOWN.
        if self.__active_tool.toolchanger is not None:
            if self.__active_tool.toolchanger.selected_tool != tool:
                self.__active_tool.toolchanger.selected_tool = tool  # type: ignore # subclassing

        self.log.trace("ktc.active_tool set to: " + tool.name)

        self._ktc_persistent.save_variable(
            "current_tool", str("'" + tool.name + "'"), section="State", force_save=True
        )

    @property
    def active_tool_n(self) -> int:
        return self.__active_tool.number

    @KtcBaseClass.state.setter
    def state(self, value):
        self._state = value

        if value == self.StateType.ENGAGING or value == self.StateType.DISENGAGING:
            self.selected_tool = self.TOOL_UNKNOWN
        elif value == self.StateType.READY:
            self.selected_tool = self.TOOL_NONE
        elif value == self.StateType.ERROR:
            self.log.always("KTC Toolchanger %s is now in error state." % self.name)
            self.selected_tool = self.TOOL_UNKNOWN

    cmd_KTC_TOOLCHANGER_SET_STATE_help = (
        "Set the state of the toolchanger."
        + " [TOOLCHANGER: Default_ToolChanger]"
        + " [STATE: STATE.ERROR]"
    )

    def cmd_KTC_TOOLCHANGER_SET_STATE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        try:
            self.get_toolchanger_from_gcmd(gcmd).state = gcmd.get("STATE", None)
        except Exception as e:
            raise gcmd.error("Error setting toolchanger state: %s" % str(e)) from e

    cmd_KTC_TOOL_SET_STATE_help = (
        "Set the state of the toolchanger.\n"
        + " [TOOL: Tool_name] or [T: Tool_number]\n"
        + " [STATE: STATE.ERROR]"
    )

    cmd_KTC_TOOLCHANGER_SET_SELECTED_TOOL_help = (
        "Set the selected tool in the toolchanger.\n"
        + "[TOOLCHANGER: Default_ToolChanger]\n"
        + "[TOOL: Tool_name] or [T: Tool_number]"
    )

    def cmd_KTC_TOOLCHANGER_SET_SELECTED_TOOL(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        tool = self.get_tool_from_gcmd(gcmd)
        toolchanger = self.get_toolchanger_from_gcmd(gcmd)
        if tool not in self.INVALID_TOOLS and tool.name not in toolchanger.tools:
            raise self.printer.command_error(
                "Tool %s not found in toolchanger %s." % (tool.name, toolchanger.name)
            )
        toolchanger.selected_tool = tool

    cmd_KTC_TOOLCHANGER_INITIALIZE_help = (
        "Initialize the toolchanger before use." + "[TOOLCHANGER: Default_ToolChanger]"
    )

    def cmd_KTC_TOOLCHANGER_INITIALIZE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        self.get_toolchanger_from_gcmd(gcmd).initialize()

    cmd_KTC_TOOLCHANGER_ENGAGE_help = (
        "Engage the toolchanger, lock in place.\n"
        + "[TOOLCHANGER: Default_ToolChanger]\n"
        + "[DISREGARD_ENGAGED: False]"
    )

    def cmd_KTC_TOOLCHANGER_ENGAGE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        try:
            de = self.parse_bool(gcmd.get("DISREGARD_ENGAGED", "False"))
            self.get_toolchanger_from_gcmd(gcmd).engage(disregard_engaged=de)
        except Exception as e:
            raise self.printer.command_error(
                "Error engaging toolchanger: %s" % str(e)
            ) from e

    cmd_KTC_TOOLCHANGER_DISENGAGE_help = (
        "Disengage the toolchanger, unlock"
        + " from place.\n [TOOLCHANGER: Default_ToolChanger]"
    )

    def cmd_KTC_TOOLCHANGER_DISENGAGE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        try:
            self.get_toolchanger_from_gcmd(gcmd).disengage()
        except Exception as e:
            raise self.printer.command_error(
                "Error disengaging toolchanger: %s" % str(e)
            ) from e

    def cmd_KTC_TOOL_SET_STATE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        tool = self.get_tool_from_gcmd(gcmd)
        value = gcmd.get("STATE", None)
        if value is None:
            raise self.printer.command_error(
                "KTC_TOOL_SET_STATE: No STATE specified for tool: %s." % str(tool.name)
            )
        elif value not in self.StateType.__members__:
            raise self.printer.command_error(
                f"KTC_TOOL_SET_STATE: Invalid STATE: {value}."
                + f" Valid states are: {self.StateType.__members__}"
            )
        tool: "ktc_tool.KtcTool" = self.printer.lookup_object(
            "ktc_tool " + str(tool.name)
        )
        tool.state = value

    cmd_KTC_SET_STATE_help = "Set the state of the KTC.\n STATE= Defaut is ERROR."

    def cmd_KTC_SET_STATE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        value = gcmd.get("STATE", self.StateType.ERROR)
        if value not in self.StateType.__members__:
            raise self.printer.command_error(
                f"KTC_SET_STATE: Invalid STATE: {value}."
                + f" Valid states are: {self.StateType.__members__}"
            )
        self._state = value

    cmd_KTC_SET_ACTIVE_TOOL_help = (
        "Set the active tool.\n" + "[TOOL: Tool_name] or [T: Tool_number]"
    )

    def cmd_KTC_SET_ACTIVE_TOOL(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        self.active_tool = self.get_tool_from_gcmd(gcmd)

    cmd_KTC_DROPOFF_help = "Deselect all tools"

    def cmd_KTC_DROPOFF(
        self, gcmd=None
    ):  # pylint: disable=invalid-name, unused-argument
        if self.active_tool == self.TOOL_UNKNOWN:
            raise self.printer.command_error(
                "Unknown tool is active and can't be deselected."
            )

        for tc in self.all_toolchangers.values():
            if (
                tc.selected_tool == self.TOOL_UNKNOWN
                and tc.state == self.StateType.SELECTED
            ):
                raise self.printer.command_error(
                    f"Toolchanger {tc.name} has unknown tool selected "
                    + "and can't be deselected."
                )

        if self.active_tool != self.TOOL_NONE:
            self.active_tool.deselect()

        try:
            # Traverse all tools and deselect them from the deepest towards the top.
            def deselect(tool: "ktc_tool.KtcTool"):
                if (
                    tool not in self.INVALID_TOOLS
                    and tool.state == self.StateType.SELECTED
                ):
                    tool.deselect()

            self.traverse_tools_from_deepest(deselect)
        except Exception as e:
            raise Exception("Failed to deselect all tools: %s" % str(e)) from e

    cmd_KTC_SET_AND_SAVE_PARTFAN_SPEED_help = (
        "Save the fan speed to be recovered at ToolChange."
    )

    def cmd_KTC_SET_AND_SAVE_PARTFAN_SPEED(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        try:
            tool = self.get_tool_from_gcmd(gcmd)
            fanspeed = typing.cast(float, gcmd.get_float("S", 1.0, 0.0, 255.0))
            self.set_and_save_fan_speed(tool, fanspeed)
        except Exception as e:
            raise gcmd.error(f"KTC_SET_AND_SAVE_PARTFAN_SPEED: Error: {str(e)}") from e

    def set_and_save_fan_speed(self, tool: ktc_tool.KtcTool, fanspeed: float):
        if fanspeed > 1:
            fanspeed = fanspeed / 255.0

        self.saved_fan_speed = fanspeed
        for fan in tool.fans:
            self.gcode.run_script_from_command(
                f"SET_FAN_SPEED FAN={fan[0]} SPEED={fanspeed * float(fan[1])}"
            )
        return

    cmd_KTC_TEMPERATURE_WAIT_WITH_TOLERANCE_help = (
        "Waits for current tool temperature, or a specified.\n"
        + "TOOL= Tool name or T= Tool number or HEATER= Coma separated list of heater names.\n"
        + "TOLERANCE= Tolerance in degC. Defaults to 1*C."
    )

    def cmd_KTC_TEMPERATURE_WAIT_WITH_TOLERANCE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        """Waits for current tool temperature, or a specified tool or heater's temperature.
        This command can be used without any additional parameters.
        Without parameters it waits for bed and current heaters.
        Only one of either P or H may be used.

        TOOL= Tool name.
        T= Tool number.
        HEATER= Coma separated list of heater names.
        TOLERANCE=nnn Tolerance in degC. Defaults to 1*C.
        Wait will wait until heater is between set temperature +/- tolerance."""
        heater_names = []
        tolerance = gcmd.get_int(
            "TOLERANCE", DEFAULT_WAIT_FOR_TEMPERATURE_TOLERANCE, minval=0, maxval=50
        )
        var_heater = typing.cast(str, gcmd.get("HEATER", None))
        var_tool_name = typing.cast(str, gcmd.get("TOOL", None))
        var_tool_id = gcmd.get_int("T", None, minval=0)

        if var_heater is not None and (
            var_tool_name is not None or var_tool_id is not None
        ):
            raise gcmd.error(
                "Can't use both TOOL and HEATER parameter at the same time."
            )

        available_heaters = typing.cast(
            "klippy_heaters.PrinterHeaters", self.printer.lookup_objects("heaters")
        ).available_heaters

        # If neither tool or heaters are given, also wait for bed.
        if var_tool_name is None and var_tool_id is None and var_heater is None:
            if "heater_bed" in available_heaters:
                heater_names.append("heater_bed")

        # If heater names are specified
        if var_heater is not None:
            var_heater = var_heater.replace(" ", "").split(",")
            lcase_heater_names_dict = {
                heater.lower(): heater for heater in available_heaters
            }
            for name in var_heater:
                if name.lower() not in lcase_heater_names_dict:
                    raise gcmd.error(
                        "Heater name %s is not a valid heater name." % name
                    )
                heater_names.append(lcase_heater_names_dict[name.lower()])
        # If tool name is specified or neither tool or heater is specified.
        else:
            # Get the tool if valid or active tool.
            tool = self.get_tool_from_gcmd(gcmd)
            heater_names.append(
                [tool_heater.name for tool_heater in tool.extruder.heaters]
            )

        for name in heater_names:
            self._temperature_wait_with_tolerance(name, tolerance)

    def _temperature_wait_with_tolerance(
        self, heater_name, tolerance
    ):  # pylint: disable=invalid-name
        curtime = self.printer.get_reactor().monotonic()
        target_temp = int(
            self.printer.lookup_object(heater_name).get_status(curtime)["target"]
        )

        if target_temp > LOWEST_ALLOWED_TEMPERATURE_TO_WAIT_FOR:
            self.log.always(
                f"Waiting for heater {heater_name} to reach {target_temp}"
                + f" with a tolerance of {tolerance}."
            )
            self.gcode.run_script_from_command(
                "TEMPERATURE_WAIT SENSOR="
                + heater_name
                + " MINIMUM="
                + str(target_temp - tolerance)
                + " MAXIMUM="
                + str(target_temp + tolerance)
            )
            self.log.always("Wait for heater " + heater_name + " complete.")

    cmd_KTC_SET_TOOL_TEMPERATURE_help = (
        "Waits for all temperatures, or a specified (TOOL) tool or"
        + "(HEATER) heater's temperature within (TOLERANCE) tolerance."
    )

    def cmd_KTC_SET_TOOL_TEMPERATURE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        """
        Set tool temperature.
        TOOL= Tool number, optional. If this parameter is not provided, the current tool is used.
        STDB_TMP= Standby temperature(s), optional
        ACTV_TMP= Active temperature(s), optional
        CHNG_STATE = Change Heater State, optional:
            0/OFF = off
            1/STANDBY = standby temperature(s)
            2/ACTIVE = active temperature(s).
        STDB_TIMEOUT = Time in seconds to wait between changing heater
            state to standby and setting heater target temperature to standby
            temperature when standby temperature is lower than tool temperature.
            Use for example 0 to change immediately to standby temperature.
        SHTDWN_TIMEOUT = Time in seconds to wait from docking tool to shutting
        off the heater, optional.
            Use for example 86400 to wait 24h if you want to disable shutdown timer.
        """
        try:
            tool = self.get_tool_from_gcmd(gcmd)

            stdb_tmp = gcmd.get_int("STDB_TMP", None, minval=0)
            actv_tmp = gcmd.get_int("ACTV_TMP", None, minval=0)
            chng_state = typing.cast(str, gcmd.get("CHNG_STATE", None))
            stdb_timeout = gcmd.get_float("STDB_TIMEOUT", None, minval=0)
            shtdwn_timeout = gcmd.get_float("SHTDWN_TIMEOUT", None, minval=0)

            self.log.trace(
                f"cmd_KTC_SET_TOOL_TEMPERATURE: T{tool.name}: stdb_tmp:{stdb_tmp}, "
                + f"actv_tmp:{actv_tmp}, chng_state:{chng_state}, "
                + f"stdb_timeout:{stdb_timeout}, shtdwn_timeout:{shtdwn_timeout}."
            )

            if len(self.all_tools[tool.name].extruder.heaters) < 1:
                self.log.always(f"T{tool.name} has no heaters! Nothing to do.")
                return

            set_heater_cmd = {}

            if stdb_tmp is not None:
                set_heater_cmd["heater_standby_temp"] = int(stdb_tmp)
            if actv_tmp is not None:
                set_heater_cmd["heater_active_temp"] = int(actv_tmp)
            if stdb_timeout is not None:
                set_heater_cmd["heater_active_to_standby_delay"] = stdb_timeout
            if shtdwn_timeout is not None:
                set_heater_cmd["heater_standby_to_powerdown_delay"] = shtdwn_timeout
            if chng_state is not None:
                set_heater_cmd["heater_state"] = HeaterStateType.parse_heater_state(
                    chng_state
                )

            if len(set_heater_cmd) > 0:
                tool.set_heaters(**set_heater_cmd)
            else:
                # Print out the current temperature settings.
                ext = tool.extruder
                msg = (
                    f"{tool.name} is {ext.state}:\n"
                    + f"Active temperature: {ext.active_temp}\n"
                    + f"Standby temperature: {ext.standby_temp}\n"
                    + f"Active to Standby timer: {ext.active_to_standby_delay} seconds\n"
                    + f"Standby to Off timer: {ext.standby_to_powerdown_delay} seconds\n"
                )

                if ext.state == HeaterStateType.STANDBY:
                    first_heater_object = self.all_heaters[ext.heaters[0].name]
                    to_standby_timer = (
                        first_heater_object.timer_heater_active_to_standby_delay
                    )
                    to_standby_timer_wake = to_standby_timer.get_status()["next_wake"]
                    if to_standby_timer_wake:
                        msg += (
                            "\n Will go to standby temperature in "
                            + f"{to_standby_timer_wake} seconds."
                        )

                    to_powerdown_timer = (
                        first_heater_object.timer_heater_standby_to_powerdown_delay
                    )
                    to_powerdown_timer_wake = to_powerdown_timer.get_status()[
                        "next_wake"
                    ]
                    if to_powerdown_timer_wake:
                        msg += (
                            "\n Will power down in "
                            + f"{to_powerdown_timer_wake} seconds."
                        )
                gcmd.respond_info(msg)
        except ValueError as e:
            raise gcmd.error(
                "KTC_SET_TOOL_TEMPERATURE: Error: %s" % str(e)
            ) from e.with_traceback(e.__traceback__)

    cmd_KTC_HEATERS_PAUSE_help = (
        "Turns off all heaters and saves changes made to be resumed by "
        + "KTC_HEATERS_RESUME."
    )

    def cmd_KTC_HEATERS_PAUSE(
        self, gcmd
    ):  # pylint: disable=invalid-name, unused-argument
        self.set_all_tool_heaters_off()

    def set_all_tool_heaters_off(self):
        self._heaters_paused = {}
        try:
            for heater in self.all_heaters.values():
                if heater.state > HeaterStateType.OFF:
                    self._heaters_paused[heater.name] = (
                        heater.state
                    )
                    heater.state = HeaterStateType.OFF
        except Exception as e:
            raise Exception("set_all_tool_heaters_off: Error: %s" % str(e)) from e

    cmd_KTC_HEATERS_RESUME_help = (
        "Resumes all heaters previously turned off by KTC_HEATERS_PAUSE."
    )

    def cmd_KTC_HEATERS_RESUME(
        self, gcmd
    ):  # pylint: disable=invalid-name, unused-argument
        self.resume_all_tool_heaters()

    def resume_all_tool_heaters(self):
        try:
            for (
                heater_name,
                state,
            ) in self._heaters_paused.items():
                self.all_heaters[heater_name].state = state
        except Exception as e:
            raise Exception("resume_all_tool_heaters: Error: %s" % str(e)) from e

    def offset_from_gcmd(self, gcmd: "gcode.GCodeCommand", offset: list) -> list[float]:
        for axis in ("X", "Y", "Z"):
            pos = gcmd.get_float(axis, None)
            adjust = gcmd.get_float(axis + "_ADJUST", None)
            if pos is not None:
                offset[XYZ_TO_INDEX[axis]] = pos
            elif adjust is not None:
                offset[XYZ_TO_INDEX[axis]] += adjust
        return offset

    cmd_KTC_TOOL_OFFSET_SAVE_help = (
        "Set and save the tool offset." + _TOOL_HELP + _OFFSET_HELP
    )

    def cmd_KTC_TOOL_OFFSET_SAVE(
        self, gcmd: "gcode.GCodeCommand"
    ):  # pylint: disable=invalid-name
        tool = self.get_tool_from_gcmd(gcmd)
        tool.offset = self.offset_from_gcmd(gcmd, tool.offset)

    cmd_KTC_GLOBAL_OFFSET_SAVE_help = "Set the global tool offset" + _OFFSET_HELP

    def cmd_KTC_GLOBAL_OFFSET_SAVE(self, gcmd):  # pylint: disable=invalid-name
        self.global_offset = self.offset_from_gcmd(gcmd, self.global_offset)

    cmd_KTC_TOOL_OFFSET_APPLY_help = (
        "Set G-Code offset to the one of current tool."
        + "Global offset is also applied."
        + "MOVE= If should move the toolhead, optional."
        + "If not specified, it will not move."
        + "0/FALSE/NO: No move"
        + "1/TRUE/YES: Move"
        + _TOOL_HELP
        + " If not specified, active tool is used."
    )

    def cmd_KTC_TOOL_OFFSET_APPLY(self, gcmd):  # pylint: disable=invalid-name
        tool = self.get_tool_from_gcmd(gcmd)

        param_move = self.parse_bool(gcmd.get("MOVE", "0"))
        run_script = "SET_GCODE_OFFSET "
        for axis in ("X", "Y", "Z"):
            offset = 0.0
            if tool.offset[XYZ_TO_INDEX[axis]] is not None:
                offset += tool.offset[XYZ_TO_INDEX[axis]]
            if self.global_offset[XYZ_TO_INDEX[axis]] is not None:
                offset += self.global_offset[XYZ_TO_INDEX[axis]]
            run_script += f"{axis}={offset} "
        run_script += f"MOVE={param_move}"

        self.log.trace(f"Applying G-Code offset from tool {tool.name}: {run_script}")
        self.gcode.run_script_from_command(run_script)

    ###########################################
    # TOOL REMAPING                           #
    ###########################################

    def _tool_map_to_human_string(self):
        msg = "KTC Tools registered:"

        for tool in self.all_tools.values():
            if tool.number is None:
                toolnr = ""
            else:
                toolnr = str(tool.number)
            msg += f"\n(KTC_T{toolnr}"
            msg += " " * (2 - len(toolnr))
            msg += f") {tool.name}"

        return msg

    cmd_KTC_TOOLS_DISPLAY_help = (
        "Display the current mapping of tools to KTC_T# numbers."
    )

    def cmd_KTC_TOOLS_DISPLAY(
        self, gcmd
    ):  # pylint: disable=invalid-name, unused-argument
        self.log.always(self._tool_map_to_human_string())

    cmd_KTC_TOOL_MAP_NR_help = (
        "Remap a tool to another one."
        + "This is not persistent and will be lost on restart."
        + " [TOOL: Tool name] or [T: Tool number]"
        + " [SET: Tool number]"
        + " [OVERWRITE: 0/1] Default 0. If 1, will overwrite existing mapping."
    )

    def cmd_KTC_TOOL_MAP_NR(self, gcmd):  # pylint: disable=invalid-name
        overwite = self.parse_bool(gcmd.get("OVERWRITE", "0"))
        tool = self.get_tool_from_gcmd(gcmd, allow_none=False)
        set_tool = gcmd.get_int("SET", minval=0)

        if set_tool in self.all_tools_by_number:
            if not overwite:
                raise gcmd.error(
                    f"Tool number {set_tool} is already used"
                    + "by tool {self.all_tools_by_number[set_tool].name}."
                    + " Use OVERWRITE=1 to overwrite."
                )
            else:
                self.all_tools_by_number[set_tool].number = None

        self.all_tools_by_number.pop(tool.number, None)
        self.all_tools_by_number[set_tool] = tool
        tool.number = set_tool

    def get_status(self, eventtime=None):  # pylint: disable=unused-argument
        status = {
            "global_offset": self.global_offset,
            "active_tool": self.active_tool.name,  # Active tool name for GCode compatibility.
            "active_tool_n": self.active_tool.number,  # Active tool number for GCode compatibility.
            "saved_fan_speed": self.saved_fan_speed,
            "tools": list(self.all_tools.keys()),
            "toolchangers": list(self.all_toolchangers.keys()),
            "TOOL_NONE": self.TOOL_NONE.name,
            "TOOL_UNKNOWN": self.TOOL_UNKNOWN.name,
            **self.params,
        }
        return status

    def confirm_ready_for_toolchange(self, tool: KtcBaseToolClass):
        def _printer_is_homed_for_toolchange(self, required_axes: str = ""):
            # If no axes are required, then return True.
            if required_axes == "":
                return True

            curtime = self.printer.get_reactor().monotonic()
            toolhead = self.printer.lookup_object("toolhead")
            homed = toolhead.get_status(curtime)["homed_axes"].upper()

            if all(axis in homed for axis in tuple(required_axes)):
                return True

            return False

        if tool in self.INVALID_TOOLS:
            raise ValueError("Tool is TOOL_NONE or TOOL_UNKNOWN")
        if self.state == self.StateType.ERROR:
            raise ValueError("KTC is in error state")
        if tool.state == tool.StateType.ERROR:
            raise ValueError("Tool is in error state")
        if not _printer_is_homed_for_toolchange(tool.requires_axis_homed):
            raise ValueError(
                "Printer is not homed for toolchange"
                + "Required axis %s not homed for ktc_tool %s."
                % (tool.requires_axis_homed, tool.name)
            )

    def get_tool_from_gcmd(
        self, gcmd: "gcode.GCodeCommand", allow_none: bool = True
    ) -> "ktc_tool.KtcTool":
        """Returns the tool object specified in the gcode command or
        the active tool if none is specified."""
        tool_name: str = gcmd.get("TOOL", None)  # type: ignore
        tool_nr: int = gcmd.get_int("T", None)  # type: ignore
        if tool_name:
            tool = self.all_tools.get(tool_name, None)
            if not tool:
                raise gcmd.error("Tool %s not found" % (tool_name))
        elif tool_nr is not None:
            if tool_nr not in self.all_tools_by_number:
                raise gcmd.error("T%d not found" % (tool_nr))
            tool = self.all_tools_by_number[tool_nr]
        else:
            if (
                self.active_tool == self.TOOL_NONE
                or self.active_tool == self.TOOL_UNKNOWN
            ):
                raise gcmd.error("No tool specified and no active tool")
            tool = self.active_tool
        if not allow_none and (tool == self.TOOL_NONE or tool == self.TOOL_UNKNOWN):
            raise gcmd.error("Tool TOOL_NONE or TOOL_UNKNOWN are not allowed.")
        return tool  # type: ignore

    def get_toolchanger_from_gcmd(
        self, gcmd: "gcode.GCodeCommand"
    ) -> "ktc_toolchanger.KtcToolchanger":
        """Returns the toolchanger object specified in the gcode command
        or the default toolchanger if none is specified and only one is available."""
        toolchanger_name = typing.cast(str, gcmd.get("TOOLCHANGER", None))
        if toolchanger_name:
            toolchanger = self.printer.lookup_object(
                "ktc_toolchanger " + toolchanger_name, None
            )
            if not toolchanger:
                raise gcmd.error("Toolchanger %s not found" % (toolchanger_name))
        else:
            if len(self.all_toolchangers) > 1:
                raise gcmd.error("No toolchanger specified and more than one available")
            toolchanger = self.all_toolchangers[0]
        return toolchanger

    def traverse_tools_from_deepest(self, func):
        def _get_nested_tools(self: Ktc, toolchanger: "ktc_toolchanger.KtcToolchanger"):
            nested_tools = []
            for tool in toolchanger.tools.values():
                if tool in self._tools_having_tc:
                    nested_tools.append(
                        _get_nested_tools(self, self._tools_having_tc[tool])
                    )
                nested_tools.append(tool)
            return nested_tools

        def _recursive_traverse_tools(self: Ktc, item, func):
            if isinstance(item, list):
                for i in item:
                    _recursive_traverse_tools(self, i, func)
            else:
                func(item)

        nested_tools = _get_nested_tools(self, self.default_toolchanger)
        _recursive_traverse_tools(self, nested_tools, func)

    ###########################################
    # DEBUGGING                               #
    ###########################################
    def cmd_KTC_DEBUG_HEATERS(
        self, gcmd
    ):  # pylint: disable=invalid-name, unused-argument
        self.log.always("KTC Debugging Heaters:")
        for heater in self.all_heaters.values():
            self.log.always(
                f"{heater.name}: {heater.state}\n"
                + f"- Active temp: {heater.heater_active_temp}\n"
                + f"- Standby temp: {heater.standby_temp}\n"
                + f"- Active to Standby delay: {heater.active_to_standby_delay}\n"
                + f"- Standby to Powerdown delay: {heater.standby_to_powerdown_delay}\n"
                + "- Timer Active to Standby counting: "
                + f"{heater.timer_heater_active_to_standby_delay.counting_down}\n"
                + "- Timer Active to Standby duration: "
                + f"{heater.timer_heater_active_to_standby_delay.duration}\n"
                + "- Timer Standby to Powerdown counting: "
                + f"{heater.timer_heater_standby_to_powerdown_delay.counting_down}\n"
                + "- Timer Standby to Powerdown duration: "
                + f"{heater.timer_heater_standby_to_powerdown_delay.duration}"
            )

    def cmd_KTC_DEBUG_TOOLS(
        self, gcmd
    ):  # pylint: disable=invalid-name, unused-argument
        self.log.always("KTC Debugging Heaters:")
        for tool in self.all_tools.values():
            if tool in self.INVALID_TOOLS:
                continue
            active_time = self.log.tool_stats[tool.name].start_time_heater_active
            standby_time = self.log.tool_stats[tool.name].start_time_heater_standby
            selected_time = self.log.tool_stats[tool.name].start_time_selected
            time_selecting = self.log.tool_stats[tool.name].start_time_spent_selecting
            time_deselecting = self.log.tool_stats[
                tool.name
            ].start_time_spent_deselecting
            extruder_state = tool.extruder.state

            if (
                active_time
                or standby_time
                or selected_time
                or time_selecting
                or time_deselecting
                or extruder_state != HeaterStateType.OFF
            ):
                self.log.always(
                    f"{tool.name}:\n"
                    + f"- Active time: {active_time}\n"
                    + f"- Standby time: {standby_time}\n"
                    + f"- Selected time: {selected_time}\n"
                    + f"- Time spent selecting: {time_selecting}\n"
                    + f"- Time spent deselecting: {time_deselecting}\n"
                    + f"- state: {tool.state}\n"
                    + f"- extruder state: {tool.extruder.state}\n"
                )

def load_config(config):
    return Ktc(config)
