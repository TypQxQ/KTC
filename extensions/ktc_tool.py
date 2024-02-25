# KTC - Klipper Tool Changer code (v.2)
# Tool module, for each tool.
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations
import typing, operator
from .ktc_base import (     # pylint: disable=relative-beyond-top-level
    KtcBaseToolClass,
    KtcConstantsClass,
    KtcBaseChangerClass,
)
from .ktc_heater import KtcHeater   # pylint: disable=relative-beyond-top-level

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy import klippy
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_toolchanger

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
        # Heaters and their offsetts
        self.timer_heater_active_to_standby_delay: "ktc_ToolStandbyTempTimer" = None  # type: ignore
        self.timer_heater_active_to_powerdown_delay:"ktc_ToolStandbyTempTimer" = None # type: ignore

    @property
    def toolchanger(self) -> "ktc_toolchanger.KtcToolchanger":
        return self._toolchanger

    @toolchanger.setter
    def toolchanger(self, value):
        if value is not None and not isinstance(value, KtcBaseChangerClass):
            raise ValueError("Toolchanger must be a KtcToolchanger object.")
        self._toolchanger = value  # type: ignore

    def configure_inherited_params(self):
        super().configure_inherited_params()
        if self.config is None:
            return

        self.gcode_macro = typing.cast('klippy_gcode_macro.PrinterGCodeMacro', # type: ignore # pylint: disable=attribute-defined-outside-init
                                  self.printer.lookup_object("gcode_macro"))    # type: ignore

        if self._heaters_config is not None:
            heaters = self.config.getlists(
                "", default= self._heaters_config, seps=(',', '\n'), # type: ignore
                parser=str)
        else:
            heaters = []
        self.log.trace(f"Number of heaters for {self.config.get_name()}: {len(heaters)}")
        if len(heaters) > 0:
            self.log.trace(f"Firt heater is of type: {type(heaters[0])}")
            for h in heaters:
                # Default as: heater_name, active to standby delay, powerdown from standby time, temperature offset
                if len(h) > 0:
                    default = [h[0], 0.1, 0.1, 0.0]
                    if h[0] == "":
                        continue
                    elif len(h) > 1:
                        for i, v in enumerate(h[1:]):
                            h[i+1] = float(v)
                    self.heaters.append(h)
                    if h[0] not in self._ktc.all_heaters:
                        self._ktc.all_heaters[h[0]] = KtcHeater()
                        self.log.trace(f"Added heater {h[0]} to all_heaters.")
                    else:
                        self.log.trace(f"Heater {h[0]} already in all_heaters.")


        ##### Standby settings (if the tool has an heaters) #####
        # if self.heaters != "":
        #     heaters = self.heaters.split(",")
        #     for heater in heaters:
        #         if heater.contains("!"):
        #             heater, offset = heater.split("!")
        #         else:
        #             offset = 0
        #         # self.heaters[heater] = float(offset)
                
        #         if self._ktc.all_heaters.get(heater) is None:
        #             self._ktc.all_heaters[heater] = KtcHeater()
                    
            # if len(self.heaters) > 0:
                
            #     # If the heater is not already initialized then do it.
            #     if self._ktc.all_heaters.get(heater) is None:
            #         self._ktc.all_heaters[heater] = KtcHeater()
                    
            #     self.timer_heater_active_to_standby_delay = ktc_ToolStandbyTempTimer(
            #         self.printer, self.name, ktc_ToolStandbyTempTimer.TIMER_TO_STANDBY
            #     )
            #     self.timer_heater_active_to_powerdown_delay = ktc_ToolStandbyTempTimer(
            #         self.printer, self.name, ktc_ToolStandbyTempTimer.TIMER_TO_SHUTDOWN
            #     )


        # If this tool is a subtool of another tool and
        # the etruder is not overriden then use the inherited heaters.
        # elif
        if self.toolchanger.parent_tool is not None and (
            self.toolchanger.parent_tool.timer_heater_active_to_standby_delay
            is not None
            ):
            self.timer_heater_active_to_standby_delay = (
                self.toolchanger.parent_tool.timer_heater_active_to_standby_delay
            )
            self.timer_heater_active_to_powerdown_delay = (
                self.toolchanger.parent_tool.timer_heater_active_to_powerdown_delay
            )

        self.state = self.StateType.CONFIGURED

    def cmd_SelectTool(self, gcmd):
        self.log.trace("KTC Tool " + str(self.number) + " Selected.")
        # Allow either one.
        restore_mode = self._ktc.ktc_parse_restore_type(gcmd.get("R", None), None)
        restore_mode = self._ktc.ktc_parse_restore_type(
            gcmd.get("RESTORE_POSITION_TYPE", None), restore_mode
        )

        self.select(restore_mode, True)

        # TODO: Change this to use the name mapping instead of number.
        # Check if the requested tool has been remaped to another one.
    #     tool_is_remaped = self._ktc.tool_is_remaped(self.number)

    #     if tool_is_remaped > -1:
    #         self.log.always(
    #             "ktc_Tool %d is remaped to Tool %d" % (self.number, tool_is_remaped)
    #         )
    #         remaped_tool = self.printer.lookup_object(
    #             "ktc_tool " + str(tool_is_remaped)
    #         )
    #         remaped_tool.select_tool_actual(restore_mode)
    #         return
    #     else:
    #         self.select_tool_actual(restore_mode)

    def select(self, restore_mode=None, final_selected=False):

    # # To avoid recursive remaping.
    # def select_tool_actual(self, restore_mode=None):
        # current_tool_id = int(self._ktc.active_tool_n)
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
                msg = ("KtcTool.select: Unknown tool already mounted."
                    + "Can't automatically deselect unknown before "
                    + "selecting new tool.")
                self.log.always(msg)
                raise self.printer.command_error(msg)

            # If the new tool to be selected has an heaters prepare warmup before
            # actual tool change so all moves will be done while heating up.
            if self.heaters is not None:
                self.set_heater(heater_state=KtcHeater.StateType.HEATER_STATE_ACTIVE)

            # If optional RESTORE_POSITION_TYPE parameter is passed then save current position.
            # Otherwise do not change either the restore_axis_on_toolchange or saved_position.
            # This makes it possible to call SAVE_POSITION or SAVE_CURRENT_POSITION
            # before the actual T command.
            if restore_mode is not None:
                self._ktc.SaveCurrentPosition(
                    restore_mode
                )  # Sets restore_axis_on_toolchange and saves current position

            # Check if this is final tool and any tool is active.
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
        if self.state == self.StateType.ENGAGED:
            return


        # Now we asume tool has been dropped if needed be.
        # Increase the number of selects started.
        self.log.tool_stats[self.name].selects_started += 1
        # Log the time it takes for tool mount.
        self.log.track_tool_selecting_start(self)

        # Check if homed
        if not self._ktc.printer_is_homed_for_toolchange(self.requires_axis_homed):
            raise self.printer.command_error(
                "KtcTool.select: Required axis %s not homed for ktc_tool %s."
                % (self.requires_axis_homed, self.name)
            )

        # Run the gcode for pickup.
        try:
            self.state = self.StateType.SELECTING
            tool_select_gcode_template = self.gcode_macro.load_template(
                self.config, "", self._tool_select_gcode)
            context = tool_select_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self._ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            tool_select_gcode_template.run_gcode_from_command(context)
            # Check that the gcode has changed the state.
        except Exception as e:
            raise Exception(f"ktc_tool {self.name} "
                            + "failed to run tool_select_gcode: " + str(e)) from e
        if self.state == self.StateType.SELECTING:
            raise self.config.error(
                (f"ktc_tool {self.name} has not changed the state while running "
                + "code in tool_select_gcode. Use for example "
                + "'KTC_SET_TOOL_STATE TOOLCHANGER={myself.name} STATE=ENGAGED' to "
                + "indicate it is selected successfully.")
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

        if final_selected:
            self._ktc.active_tool = self
            self.log.track_tool_selected_start(self)
            self.state = self.StateType.ACTIVE

    def deselect(self, force_unload=False):    # pylint: disable=arguments-differ
        # TODO: Also check if any tool over this one should be deselected.

        # Check if homed
        if not self._ktc.printer_is_homed_for_toolchange(self.requires_axis_homed):
            raise self.printer.command_error(
                "KtcTool.deselect: Required axis %s not homed for ktc_tool %s."
                % (self.requires_axis_homed, self.name)
            )

        self.log.track_tool_selected_end(self)
        self.log.track_tool_deselecting_start(self)

        # Turn off fan if has a fan.
        if self.fan is not None:
            self.gcode.run_script_from_command(
                "SET_FAN_SPEED FAN=" + self.fan + " SPEED=0"
            )

        try:
            self.state = self.StateType.DESELECTING
            gcode_template = self.gcode_macro.load_template(
                self.config, "", self._tool_select_gcode)
            context = gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self._ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception(f"ktc_tool {self.name} "
                            + "failed to run tool_deselect_gcode: " + str(e)) from e
        # Check that the gcode has changed the state.
        if self.state == self.StateType.ENGAGING:
            raise self.config.error(
                (f"ktc_tool {self.name} has not changed the state while running "
                + "code in tool_select_gcode. Use for example "
                + "'KTC_SET_TOOL_STATE TOOLCHANGER={myself.name} STATE=ENGAGED' to "
                + "indicate it is selected successfully.")
            )
        elif self.state == self.StateType.ERROR:
            raise self.config.error(
                (f"ktc_tool {self.name} has changed the state to ERROR while running "
                + "code in tool_select_gcode.")
            )

        self._ktc.active_tool = self.TOOL_NONE  # Dropoff successfull
        self.log.track_tool_deselecting_end(
            self
        )  # Log the time it takes for tool change.

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
        self.heater_state = heater_state

    @staticmethod
    def _get_topmost_tool_for_heater(tool: KtcTool) -> KtcTool:
        pt = tool.toolchanger.parent_tool
        if pt is not None:
            if (pt.heater is not None and
                pt.heater == tool.heater):
                return KtcTool._get_topmost_tool_for_heater(pt)
            else:
                return tool
        else:
            return tool

    def set_heater(self, **kwargs):
        if self.heaters is None:
            self.log.debug(
                "set_heater: KTC Tool %s has no heaters! Nothing to do." % self.name
            )
            return None

        self.log.trace("set_heater: KTC Tool %s heater is at begingin %s. %s*C"
                       % (self.name, self.heater_state, self.heater_active_temp ))

        heater = self.printer.lookup_object(self.heaters).get_heater()
        curtime = self.printer.get_reactor().monotonic()
        changing_timer = False

        # Heater of self can point to the one of parent if it is inherited.
        # Get topmost tool for heater.
        tool_for_tracking_heater = KtcTool._get_topmost_tool_for_heater(self)

        # First set state if changed, so we set correct temps.
        if "heater_state" in kwargs:
            chng_state = kwargs["heater_state"]
        for i in kwargs:
            if i == "heater_active_temp":
                self.heater_active_temp = kwargs[i]
                if int(self.heater_state) == KtcHeater.StateType.HEATER_STATE_ACTIVE:
                    heater.set_temp(self.heater_active_temp)
            elif i == "heater_standby_temp":
                self.heater_standby_temp = kwargs[i]
                if int(self.heater_state) == KtcHeater.StateType.HEATER_STATE_STANDBY:
                    heater.set_temp(self.heater_standby_temp)
            elif i == "heater_active_to_standby_delay":
                self.heater_active_to_standby_delay = kwargs[i]
                changing_timer = True
            elif i == "heater_active_to_powerdown_delay":
                self.heater_active_to_powerdown_delay = kwargs[i]
                changing_timer = True

        # If already in standby and timers are counting down, i.e. have not triggered since set in standby, then reset the ones counting down.
        if (
            int(self.heater_state) == KtcHeater.StateType.HEATER_STATE_STANDBY
            and changing_timer
        ):
            if (
                self.timer_heater_active_to_powerdown_delay.get_status()[
                    "counting_down"
                ]
                == True
            ):
                self.timer_heater_active_to_powerdown_delay.set_timer(
                    self.heater_active_to_powerdown_delay, self.name
                )
                if self.heater_active_to_powerdown_delay > 2:
                    self.log.info(
                        "KTC Tool %s: heater will shut down in %s seconds."
                        % (
                            self.name,
                            self.log.seconds_to_human_string(
                                self.heater_active_to_powerdown_delay
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
                    heater.set_temp(self.heater_active_temp)
                elif chng_state == KtcHeater.StateType.HEATER_STATE_STANDBY:
                    self.log.trace(
                        "set_heater: KTC Tool %s heater state not changed. Setting standby temp."
                        % self.name
                    )
                    heater.set_temp(self.heater_standby_temp)
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
                self.timer_heater_active_to_powerdown_delay.set_timer(0.1, self.name)
                # self.log.track_heater_standby_end(self)                                                # Set the standby as finishes in statistics.
                # self.log.track_heater_active_end(self)                                                # Set the active as finishes in statistics.
            elif (
                chng_state == KtcHeater.StateType.HEATER_STATE_ACTIVE
            ):  # Else If Active
                self.log.trace("set_heater: T%d heater state now ACTIVE." % self.name)
                self.timer_heater_active_to_standby_delay.set_timer(0, self.name)
                self.timer_heater_active_to_powerdown_delay.set_timer(0, self.name)
                heater.set_temp(self.heater_active_temp)
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
                    self.heater_standby_temp
                ) < int(
                    heater.get_status(curtime)["temperature"]
                ):
                    self.timer_heater_active_to_standby_delay.set_timer(
                        self.heater_active_to_standby_delay, self.name
                    )
                    self.timer_heater_active_to_powerdown_delay.set_timer(
                        self.heater_active_to_powerdown_delay, self.name
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
                            int(self.heater_standby_temp),
                            int(heater.get_status(curtime)["temperature"]),
                        )
                    )
                    self.timer_heater_active_to_standby_delay.set_timer(0.1, self.name)
                    self.timer_heater_active_to_powerdown_delay.set_timer(
                        self.heater_active_to_powerdown_delay, self.name
                    )
                if self.heater_active_to_powerdown_delay > 2:
                    self.log.always(
                        "KTC Tool %s heater will shut down in %s seconds."
                        % (
                            self.name,
                            self.log.seconds_to_human_string(
                                self.heater_active_to_powerdown_delay
                            ),
                        )
                    )
            self.heater_state = chng_state

        # self.log.info("KTC Tool %s heater is at end %s. %s*C" % (self.name, self.heater_state, self.heater_active_temp ))

    def get_timer_to_standby(self):
        return self.timer_heater_active_to_standby_delay

    def get_timer_to_powerdown(self):
        return self.timer_heater_active_to_powerdown_delay

    def get_status(self, eventtime=None):  # pylint: disable=unused-argument
        status = {
            "name": self.name,
            "number": self.number,
            "toolchanger": self.toolchanger.name,
            "heaters": self.heaters,
            "fan": self.fan,
            "offset": self.offset,
            "heater_state": self.heater_state,
            "heater_active_temp": self.heater_active_temp,
            "heater_standby_temp": self.heater_standby_temp,
            "heater_active_to_standby_delay": self.heater_active_to_standby_delay,
            "idle_to_powerdown_next_wake": self.heater_active_to_powerdown_delay,
            **self.params,
        }
        return status

    # Based on DelayedGcode.


class ktc_ToolStandbyTempTimer:
    TIMER_TO_SHUTDOWN = 0
    TIMER_TO_STANDBY = 1

    def __init__(self, printer, tool_id, temp_type):
        self.printer = printer
        self.tool_id = tool_id
        self.last_virtual_tool_using_physical_timer = None

        self.duration = 0.0
        self.temp_type = temp_type  # 0= Time to shutdown, 1= Time to standby.

        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.timer_handler = None
        self.inside_timer = self.repeat = False
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.log = self.printer.lookup_object("ktc_log")

        self.counting_down = False
        self.nextwake = self.reactor.NEVER

    def _handle_ready(self):
        self.timer_handler = self.reactor.register_timer(
            self._standby_tool_temp_timer_event, self.reactor.NEVER
        )

    def _standby_tool_temp_timer_event(self, eventtime):
        self.inside_timer = True
        self.counting_down = False
        try:
            if self.last_virtual_tool_using_physical_timer is None:
                raise Exception("last_virtual_tool_using_physical_timer is < None")

            tool: KtcTool = self.printer.lookup_object(
                "ktc_tool " + str(self.last_virtual_tool_using_physical_timer)
            )

            self.log.trace(
                "_standby_tool_temp_timer_event: Running for T%s. temp_type:%s. %s"
                % (
                    str(self.tool_id),
                    "Time to shutdown" if self.temp_type == 0 else "Time to standby",
                    (
                        (
                            "For virtual tool T%s"
                            % str(self.last_virtual_tool_using_physical_timer)
                        )
                        if self.last_virtual_tool_using_physical_timer != self.tool_id
                        else ""
                    ),
                )
            )

            temperature = 0
            # TODO: This isnot working.
            heater = self.printer.lookup_object(tool.heaters).get_heater()
            if self.temp_type == self.TIMER_TO_STANDBY:
                self.log.track_heater_standby_start(
                    self.tool_id
                )  # Set the standby as started in statistics.
                temperature = tool.get_status()["heater_standby_temp"]
                heater.set_temp(temperature)
            else:
                self.log.track_heater_standby_end(
                    self
                )  # Set the standby as finishes in statistics.

                tool.get_timer_to_standby().set_timer(
                    0, self.last_virtual_tool_using_physical_timer
                )  # Stop Standby timer.
                tool._set_heater_state(KtcHeater.StateType.HEATER_STATE_OFF)  # Set off state.
                heater.set_temp(0)  # Set temperature to 0.

            self.log.track_heater_active_end(
                self
            )  # Set the active as finishes in statistics.

        except Exception as e:
            raise Exception(
                "Failed to set Standby temp for tool T%s: %s. %s"
                % (
                    str(self.tool_id),
                    (
                        "for virtual T%s"
                        % str(self.last_virtual_tool_using_physical_timer)
                    ),
                    str(e),
                )
            )  # if actual_tool_calling != self.tool_id else ""

        self.nextwake = self.reactor.NEVER
        if self.repeat:
            self.nextwake = eventtime + self.duration
            self.counting_down = True
        self.inside_timer = self.repeat = False
        return self.nextwake

    def set_timer(self, duration, actual_tool_calling):
        actual_tool_calling = actual_tool_calling
        self.log.trace(
            str(self.timer_handler)
            + ".set_timer: T%s %s, temp_type:%s, duration:%s."
            % (
                str(self.tool_id),
                (
                    ("for virtual T%s" % str(actual_tool_calling))
                    if actual_tool_calling != self.tool_id
                    else ""
                ),
                ("Standby" if self.temp_type == 1 else "OFF"),
                str(duration),
            )
        )
        self.duration = float(duration)
        self.last_virtual_tool_using_physical_timer = actual_tool_calling
        if self.inside_timer:
            self.repeat = self.duration != 0.0
        else:
            waketime = self.reactor.NEVER
            if self.duration:
                waketime = self.reactor.monotonic() + self.duration
                self.nextwake = waketime
            self.reactor.update_timer(self.timer_handler, waketime)
            self.counting_down = True

    def get_status(self, eventtime=None):  # pylint: disable=unused-argument
        status = {
            "temp_type": self.temp_type,
            "duration": self.duration,
            "counting_down": self.counting_down,
            "next_wake": self._time_left(),
        }
        return status

    def _time_left(self):
        if self.nextwake == self.reactor.NEVER:
            return "never"
        else:
            return str(self.nextwake - self.reactor.monotonic())

    ###########################################
    # Dataclassess for KtcTool
    ###########################################


def load_config_prefix(config):
    return KtcTool(config)
