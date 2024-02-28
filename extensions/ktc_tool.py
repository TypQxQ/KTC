# KTC - Klipper Tool Changer code (v.2)
# Tool module, for each tool.
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations
import typing, operator, dataclasses
from .ktc_base import (     # pylint: disable=relative-beyond-top-level
    KtcBaseToolClass,
    KtcConstantsClass,
    KtcBaseChangerClass,
    HeaterStateType,
    KtcHeaterSettings,
    KtcToolExtruder,
)
from .ktc_heater import KtcHeater   # pylint: disable=relative-beyond-top-level
# from . import ktc_heater

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy import klippy
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_toolchanger, ktc_log, ktc

    # from . import ktc_persisting

class KtcTool(KtcBaseToolClass, KtcConstantsClass):
    """Class for a single tool in the toolchanger"""

    def __init__(self, config: "configfile.ConfigWrapper"):
        super().__init__(config)
        ##### Name #####
        self.name = config.get_name().split(" ", 1)[1]
        if self.name == self.TOOL_NONE.name or self.name == self.TOOL_UNKNOWN.name:
            raise config.error(
                "Name of section '%s' is not well formated. Name is reserved for internal use."
                % (config.get_name())
            )

        ##### Tool Number #####
        # Will be added to the ktc.tools_by_number dict in ktc._config_tools()
        self.number = config.getint("tool_number", None)  # type: ignore

        ##### Toolchanger #####
        # If none, then the default toolchanger will be set in ktc._config_default_toolchanger()
        toolchanger_name = config.get("toolchanger", None)  # type: ignore # None is default.
        if toolchanger_name is not None:
            self.toolchanger = typing.cast(  # type: ignore
                "ktc_toolchanger.KtcToolchanger",
                self.printer.load_object(config, "ktc_toolchanger " + toolchanger_name),
            )

        self.extruder = KtcToolExtruder()

        # TODO: Delete
        # Heaters and their offsetts
        self.timer_heater_active_to_standby_delay = None  # type: ignore
        self.timer_heater_standby_to_powerdown_delay = None # type: ignore
        # self.heater_state = HeaterStateType.HEATER_STATE_OFF
        # Temperature to set when in active mode.
        # Requred on Physical and virtual tool if any has heaters.
        self._heater_active_temp = 0
        # Temperature to set when in standby mode.
        # Requred on Physical and virtual tool if any has heaters.
        self._heater_standby_temp = 0

    @property
    def toolchanger(self) -> "ktc_toolchanger.KtcToolchanger":
        return self._toolchanger

    @toolchanger.setter
    def toolchanger(self, value):
        if value is not None and not isinstance(value, KtcBaseChangerClass):
            raise ValueError("Toolchanger must be a KtcToolchanger object.")
        self._toolchanger = value  # type: ignore

    def configure_inherited_params(self):
        # If this is TOOL_NONE or TOOL_UNKNOWN.
        if self.config is None:
            return

        super().configure_inherited_params()

        self.gcode_macro = typing.cast('klippy_gcode_macro.PrinterGCodeMacro', # type: ignore # pylint: disable=attribute-defined-outside-init
                                  self.printer.lookup_object("gcode_macro"))    # type: ignore

        self.extruder.active_to_standby_delay = self._heater_active_to_standby_delay_in_config
        self.extruder.standby_to_powerdown_delay = self._heater_standby_to_powerdown_delay_in_config
        # Settings for any heaters.
        if self._heaters_config is not None:
            heaters = self._heaters_config.split(",")
            for heater_string in heaters:
                heater_string = heater_string.replace(" ", "")
                if heater_string == "":
                    continue
                heater_settings = KtcHeaterSettings.from_string(heater_string)
                self.extruder.heaters.append(heater_settings)
                # Initialize the heater if first time used.
                if heater_settings.name not in self._ktc.all_heaters:
                    self._ktc.all_heaters[heater_settings.name] = (
                        self.printer.load_object(
                        self.config, "ktc_heater " + heater_settings.name)
                    )

        self.state = self.StateType.CONFIGURED

    def cmd_SelectTool(self, gcmd): # pylint: disable=invalid-name
        self.log.trace("KTC Tool " + str(self.number) + " Selected.")
        # Allow either one.
        restore_mode = self._ktc.ktc_parse_restore_type(gcmd.get("R", None), None)
        restore_mode = self._ktc.ktc_parse_restore_type(
            gcmd.get("RESTORE_POSITION_TYPE", None), restore_mode
        )

        self.select(restore_mode, True)

    def select(self, restore_mode=None, final_selected=False):
        self.state = self.StateType.SELECTING
        try:
            self.log.always("KTC Tool %s Selecting." % self.name)
            at = self._ktc.active_tool

            # TODO: Remove when debugged.
            self.log.trace(f"Current KTC Tool is {at.name}.")
            self.log.trace(f"Selecting KTC Tool {self.name} as final_selected: {final_selected}.")

            # None of this is needed if this is not the final tool.
            if final_selected:
                # If already selected as final tool then do nothing.
                if self == at:
                    return

                if at == self.TOOL_UNKNOWN:
                    msg = ("Unknown tool already mounted."
                        + "Can't automatically deselect unknown tool"
                        + " before selecting new tool.")
                    self.log.always(msg)
                    raise self.printer.command_error(msg)

                self._ktc.confirm_ready_for_toolchange(self)

                # If the new tool to be selected has any heaters prepare warmup before
                # actual tool change so all moves will be done while heating up.
                if len(self.extruder.heaters) > 0:
                    self.set_heater(heater_state=HeaterStateType.HEATER_STATE_ACTIVE)

                # If optional RESTORE_POSITION_TYPE parameter is passed then save current position.
                # Otherwise do not change either the restore_axis_on_toolchange or saved_position.
                # This makes it possible to call SAVE_POSITION or SAVE_CURRENT_POSITION
                # before the actual T command.
                if restore_mode is not None:
                    self._ktc.SaveCurrentPosition(
                        restore_mode
                    )  # Sets restore_axis_on_toolchange and saves current position

                # If another tool is selected it needs to be deselected first.
                if at is not self.TOOL_NONE:
                    # If the new tool is on the same toolchanger as the current tool.
                    if self.toolchanger == at.toolchanger:
                        at.deselect()
                    # If on different toolchanger:
                    else:
                        # First deselect all tools recursively.
                        tools = self._get_list_from_tool_traversal_conditional(
                            at, "force_deselect_when_parent_deselects", True)
                        for t in tools:
                            t.deselect()
                        # Then select the new tools recursively in reverse order.
                        tools = self._get_list_from_tool_traversal_conditional(
                            self, "state", self.StateType.ENGAGED, operator.ne)
                        for t in reversed(tools):
                            t.select()

            # If already selected then do nothing.
            if self.state == self.StateType.SELECTED or self.state == self.StateType.ACTIVE:
                return

            # Now we asume tool has been dropped if needed be.
            # Increase the number of selects started.
            self.log.tool_stats[self.name].selects_started += 1
            # Log the time it takes for tool mount.
            self.log.track_tool_selecting_start(self)

            # Run the gcode for pickup.
            try:
                # self.state = self.StateType.SELECTING
                tool_select_gcode_template = self.gcode_macro.load_template(
                    self.config, "", self._tool_select_gcode)
                context = tool_select_gcode_template.create_template_context()
                context['myself'] = self.get_status()
                context['ktc'] = self._ktc.get_status()
                context['STATE_TYPE'] = self.StateType
                tool_select_gcode_template.run_gcode_from_command(context)
                # Check that the gcode has changed the state.
            except Exception as e:
                raise Exception("Failed to run tool_select_gcode: " + str(e)) from e
            if self.state == self.StateType.SELECTING:
                raise self.config.error(
                    ("tool_select_gcode has not changed the state while running "
                    + "code in tool_select_gcode. Use for example "
                    + "'KTC_SET_TOOL_STATE TOOL={myself.name} STATE=SELECTED' to "
                    + "indicate it is selected successfully. Or ERROR if it failed.")
                )
            elif self.state == self.StateType.ERROR:
                raise self.config.error(
                    ("tool_select_gcode changed the state to ERROR while running.")
                )

            # Restore fan if has a fan.
            if self.fan is not None:
                self.gcode.run_script_from_command(
                    "SET_FAN_SPEED FAN="
                    + self.fan
                    + " SPEED="
                    + str(self._ktc.get_status()["saved_fan_speed"])
                )

            self.log.tool_stats[self.name].selects_completed += 1
            self.log.track_tool_selecting_end(self)

            if final_selected and self.state == self.StateType.SELECTED:
                self._ktc.active_tool = self
                self.log.track_tool_selected_start(self)
                self.state = self.StateType.ACTIVE

        except Exception as e:
            self.log.always("KTC Tool %s failed to select: %s" % (self.name, str(e)))
            self.state = self.StateType.ERROR
            self._ktc.state = self.StateType.ERROR
            raise e from e

    @KtcBaseToolClass.state.setter
    def state(self, value):
        KtcBaseToolClass.state.fset(self, value)    # Call super class setter.

        if value == self.StateType.SELECTED:
            self.log.always("KTC Tool %s is now selected." % self.name)
            self.toolchanger.selected_tool = self
        elif value == self.StateType.ACTIVE:
            self.log.always("KTC Tool %s is now active." % self.name)
            self.toolchanger.selected_tool = self
            self._ktc.active_tool = self
        elif value == self.StateType.READY:
            self.log.always("KTC Tool %s is now desekected and ready." % self.name)
            if self.toolchanger.selected_tool == self:
                self.toolchanger.selected_tool = self.TOOL_NONE
            if self._ktc.active_tool == self:
                self._ktc.active_tool = self.TOOL_NONE
        elif value == self.StateType.ERROR:
            self.log.always("KTC Tool %s is now in error state." % self.name)
            self.toolchanger.selected_tool = self.TOOL_UNKNOWN
            self._ktc.active_tool = self.TOOL_UNKNOWN



    def deselect(self, force_unload=False):    # pylint: disable=arguments-differ
        # TODO: Also check if any tool over this one should be deselected?
        self.state = self.StateType.DESELECTING
        try:
            # Check if homed
            self._ktc.confirm_ready_for_toolchange(self)

            self.log.track_tool_selected_end(self)
            self.log.track_tool_deselecting_start(self)
            self.log.tool_stats[self.name].deselects_started += 1

            # Turn off fan if has a fan.
            if self.fan is not None:
                self.gcode.run_script_from_command(
                    "SET_FAN_SPEED FAN=" + self.fan + " SPEED=0"
                )

            try:
                gcode_template = self.gcode_macro.load_template(
                    self.config, "", self._tool_deselect_gcode)
                context = gcode_template.create_template_context()
                context['myself'] = self.get_status()
                context['ktc'] = self._ktc.get_status()
                context['STATE_TYPE'] = self.StateType
                gcode_template.run_gcode_from_command(context)
            except Exception as e:
                raise Exception("Failed to run tool_deselect_gcode: " + str(e)) from e
            # Check that the gcode has changed the state.
            if self.state == self.StateType.ENGAGING:
                raise self.config.error(
                    ("tool_deselect_gcode has not changed the state while running "
                    + "code in tool_select_gcode. Use for example "
                    + "'KTC_SET_TOOL_STATE TOOL={myself.name} STATE=SELECTED' to "
                    + "indicate it is selected successfully. Or ERROR if it failed.")
                )
            elif self.state == self.StateType.ERROR:
                raise self.config.error(
                    ("tool_select_gcode has changed the state to ERROR while running.")
                )

            self._ktc.active_tool = self.TOOL_NONE  # Dropoff successfull
            self.log.track_tool_deselecting_end(
                self
            )  # Log the time it takes for tool change.
        except Exception as e:
            self.log.always("KTC Tool %s failed to deselect: %s" % (self.name, str(e)))
            self.state = self.StateType.ERROR
            self._ktc.state = self.StateType.ERROR
            raise e from e

    def _get_list_from_tool_traversal_conditional(
        self, start_tool: KtcBaseToolClass, param: str,
        value, condition = operator.eq) -> typing.List[KtcTool]:
        return_list = []

        if (start_tool is None or
            start_tool == self.TOOL_NONE or
            start_tool == self.TOOL_UNKNOWN or
            start_tool == self._ktc):
            return return_list

        if condition(getattr(start_tool, param), value):
            return_list.append(start_tool)

        upper_tool = start_tool.toolchanger.parent_tool

        if upper_tool is not None:
            return_list += self._get_list_from_tool_traversal_conditional(
                upper_tool, param, value, condition)

        return return_list

    def set_offset(self, **kwargs):
        for arg, value in kwargs.items():
            if arg == "x_pos":
                self.offset[0] = float(value)
            elif arg == "x_adjust":
                self.offset[0] += float(value)
            elif arg == "y_pos":
                self.offset[1] = float(value)
            elif arg == "y_adjust":
                self.offset[1] += float(value)
            elif arg == "z_pos":
                self.offset[2] = float(value)
            elif arg == "z_adjust":
                self.offset[2] += float(value)

        self.log.always(
            "ktc_tool %s offset now set to: %f, %f, %f."
            % (
                self.name,
                float(self.offset[0]),
                float(self.offset[1]),
                float(self.offset[2]),
            )
        )

    def _set_heater_state(self, heater_state):
        for heater in self.extruder.heaters:
            self._ktc.all_heaters[heater.name].state = heater_state

    def set_heater(self, **kwargs):
        if len(self.extruder.heaters) < 1:
            self.log.debug(
                "set_heater: KTC Tool %s has no heaters! Nothing to do." % self.name
            )
            return None

        self.log.trace("set_heater: KTC Tool %s heater is at begingin %s. %s*C, %s*C"
                       % (self.name, self.extruder.state, self.extruder.active_temp,
                            self.extruder.standby_temp))

        # TODO: Check that we get the right heater.
        # printer_heater = self.printer.lookup_object(self.extruder.heaters[0]).get_heater()

        curtime = self.printer.get_reactor().monotonic()
        changing_timer = False

        return
        # Heater of self can point to the one of parent if it is inherited.
        # Get topmost tool for heater.
        tool_for_tracking_heater = KtcTool._get_topmost_tool_for_heater(self)

        # First set state if changed, so we set correct temps.
        if "heater_state" in kwargs:
            chng_state = kwargs["heater_state"]
        for i in kwargs:
            if i == "heater_active_temp":
                self._heater_active_temp = kwargs[i]
                if int(self.heater_state) == KtcHeater.StateType.HEATER_STATE_ACTIVE:
                    heater.set_temp(self._heater_active_temp)
            elif i == "heater_standby_temp":
                self._heater_standby_temp = kwargs[i]
                if int(self.heater_state) == KtcHeater.StateType.HEATER_STATE_STANDBY:
                    heater.set_temp(self._heater_standby_temp)
            elif i == "heater_active_to_standby_delay":
                self.heater_active_to_standby_delay = kwargs[i]
                changing_timer = True
            elif i == "heater_standby_to_powerdown_delay":
                self.heater_standby_to_powerdown_delay = kwargs[i]
                changing_timer = True

        # If already in standby and timers are counting down, i.e. have not triggered since set in standby, then reset the ones counting down.
        if (
            int(self.heater_state) == KtcHeater.StateType.HEATER_STATE_STANDBY
            and changing_timer
        ):
            if (
                self.timer_heater_standby_to_powerdown_delay.get_status()[
                    "counting_down"
                ]
                == True
            ):
                self.timer_heater_standby_to_powerdown_delay.set_timer(
                    self.heater_standby_to_powerdown_delay, self.name
                )
                if self.heater_standby_to_powerdown_delay > 2:
                    self.log.info(
                        "KTC Tool %s: heater will shut down in %s seconds."
                        % (
                            self.name,
                            self.log.seconds_to_human_string(
                                self.heater_standby_to_powerdown_delay
                            ),
                        )
                    )
            if (
                self.timer_heater_active_to_standby_delay.get_status()["counting_down"]
                == True
            ):
                self.timer_heater_active_to_standby_delay.set_timer(
                    self.heater_active_to_standby_delay, self.name
                )
                if self.heater_active_to_standby_delay > 2:
                    self.log.info(
                        "KTC Tool %s heater will go in standby in %s seconds."
                        % (
                            self.name,
                            self.log.seconds_to_human_string(
                                self.heater_active_to_standby_delay
                            ),
                        )
                    )

        # Change Active mode, Continuing with part two of temp changing.:
        if "heater_state" in kwargs:
            if (
                self.heater_state == chng_state
            ):  # If we don't actually change the state don't do anything.
                if chng_state == KtcHeater.StateType.HEATER_STATE_ACTIVE:
                    self.log.trace(
                        "set_heater: KTC Tool %s heater state not changed. Setting active temp."
                        % self.name
                    )
                    heater.set_temp(self._heater_active_temp)
                elif chng_state == KtcHeater.StateType.HEATER_STATE_STANDBY:
                    self.log.trace(
                        "set_heater: KTC Tool %s heater state not changed. Setting standby temp."
                        % self.name
                    )
                    heater.set_temp(self._heater_standby_temp)
                else:
                    self.log.trace(
                        "set_heater: KTC Tool %s heater state not changed." % self.name
                    )
                return None
            if (
                chng_state == KtcHeater.StateType.HEATER_STATE_OFF
            ):  # If Change to Shutdown
                self.log.trace(
                    "set_heater: KTC Tool %s heater state now OFF." % self.name
                )
                self.timer_heater_active_to_standby_delay.set_timer(0, self.name)
                self.timer_heater_standby_to_powerdown_delay.set_timer(0.1, self.name)
                # self.log.track_heater_standby_end(self)                                                # Set the standby as finishes in statistics.
                # self.log.track_heater_active_end(self)                                                # Set the active as finishes in statistics.
            elif (
                chng_state == KtcHeater.StateType.HEATER_STATE_ACTIVE
            ):  # Else If Active
                self.log.trace("set_heater: T%d heater state now ACTIVE." % self.name)
                self.timer_heater_active_to_standby_delay.set_timer(0, self.name)
                self.timer_heater_standby_to_powerdown_delay.set_timer(0, self.name)
                heater.set_temp(self._heater_active_temp)
                self.log.track_heater_standby_end(
                    self._ktc.all_tools[tool_for_tracking_heater]
                )  # Set the standby as finishes in statistics.
                self.log.track_heater_active_start(
                    self._ktc.all_tools[tool_for_tracking_heater]
                )  # Set the active as started in statistics.                                               # Set the active as started in statistics.
            elif (
                chng_state == KtcHeater.StateType.HEATER_STATE_STANDBY
            ):  # Else If Standby
                self.log.trace("set_heater: T%d heater state now STANDBY." % self.name)
                if int(
                    self.heater_state
                ) == KtcHeater.StateType.HEATER_STATE_ACTIVE and int(
                    self._heater_standby_temp
                ) < int(
                    heater.get_status(curtime)["temperature"]
                ):
                    self.timer_heater_active_to_standby_delay.set_timer(
                        self.heater_active_to_standby_delay, self.name
                    )
                    self.timer_heater_standby_to_powerdown_delay.set_timer(
                        self.heater_standby_to_powerdown_delay, self.name
                    )
                    if self.heater_active_to_standby_delay > 2:
                        self.log.always(
                            "KTC Tool %s heater will go in standby in %s seconds."
                            % (
                                self.name,
                                self.log.seconds_to_human_string(
                                    self.heater_active_to_standby_delay
                                ),
                            )
                        )
                else:  # Else (Standby temperature is lower than the current temperature)
                    self.log.trace(
                        "set_heater: KTC Tool %s standbytemp:%d;heater_state:%d; current_temp:%d."
                        % (
                            self.name,
                            int(self.heater_state),
                            int(self._heater_standby_temp),
                            int(heater.get_status(curtime)["temperature"]),
                        )
                    )
                    self.timer_heater_active_to_standby_delay.set_timer(0.1, self.name)
                    self.timer_heater_standby_to_powerdown_delay.set_timer(
                        self.heater_standby_to_powerdown_delay, self.name
                    )
                if self.heater_standby_to_powerdown_delay > 2:
                    self.log.always(
                        "KTC Tool %s heater will shut down in %s seconds."
                        % (
                            self.name,
                            self.log.seconds_to_human_string(
                                self.heater_standby_to_powerdown_delay
                            ),
                        )
                    )
            self.heater_state = chng_state

        # self.log.info("KTC Tool %s heater is at end %s. %s*C" % (self.name, self.heater_state, self._heater_active_temp ))

    def get_status(self, eventtime=None):  # pylint: disable=unused-argument
        status = {
            "name": self.name,
            "number": self.number,
            "state": self.state,
            "toolchanger": self.toolchanger.name,
            "fan": self.fan,
            "offset": self.offset,
            "heater_names": [heater.name for heater in self.extruder.heaters],
            "heater_state": self.extruder.state,
            "heater_active_temp": self.extruder.active_temp,
            "heater_standby_temp": self.extruder.standby_temp,
            "heater_active_to_standby_delay": self.extruder.active_to_standby_delay,
            "idle_to_powerdown_next_wake": self.extruder.standby_to_powerdown_delay,
            "params_available": str(self.params.keys()),
            **self.params,
        }
        return status

    ###########################################
    # Dataclassess for KtcTool
    ###########################################
def load_config_prefix(config):
    return KtcTool(config)
