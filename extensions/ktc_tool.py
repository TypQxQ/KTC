# KTC - Klipper Tool Changer code (v.2)
# Tool module, for each tool.
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import typing
from .ktc_base import (
    KtcBaseToolClass,
    KtcConstantsClass,
    KtcBaseChangerClass,
)  # pylint: disable=relative-beyond-top-level, wildcard-import

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy import klippy
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_toolchanger

    # from . import ktc_persisting
    from .ktc_heater import KtcHeater


class KtcTool(KtcBaseToolClass, KtcConstantsClass):
    """Class for a single tool in the toolchanger"""

    def __init__(self, config: "configfile.ConfigWrapper"):
        super().__init__(config)

        # TODO: Removed from config. Need to be removed from code.
        self.is_virtual = False
        # Parent tool is used as a Physical parent for all tools of this group.
        # Only used if the tool i virtual. None gets remaped to -1.
        self.parentTool_id = self.TOOL_NONE_N
        self.parentTool = None  # Initialize physical parent as a dummy object.
        self.virtual_loaded = -1  # The abstract tool loaded in the physical tool.

        # TODO: Needs moving to regular gcode.
        self.virtual_toolload_gcode = None
        self.virtual_toolunload_gcode = None
        # If it takes long time to unload/load it may be faster to
        # leave it loaded and force unload at end of print.
        self.force_unload_when_parent_unloads = False
        self.unload_virtual_at_dropoff = None

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

        # TODO: Change this to use the ktc_toolchanger instead of parentTool.
        self.parentTool = None  # Initialize physical parent as a dummy object.

        # TODO: Change to array of extruders.
        ##### Extruder #####
        self.extruder = config.get("extruder", None)  # type: ignore

        # TODO: Change to array of fans.
        ##### Fan #####
        self.fan = config.get("fan", None)  # type: ignore

        self.timer_heater_active_to_standby_delay: "ktc_ToolStandbyTempTimer" = None  # type: ignore
        self.timer_heater_active_to_powerdown_delay:"ktc_ToolStandbyTempTimer" = None # type: ignore

    @property
    def toolchanger(self) -> "ktc_toolchanger.KtcToolchanger":
        return self._toolchanger

    @toolchanger.setter
    def toolchanger(self, value):
        # TODO: Change this to use the base class instead of the specific class.
        if value is not None and not isinstance(value, KtcBaseChangerClass):
            raise ValueError("Toolchanger must be a KtcToolchanger object.")
        self._toolchanger = value  # type: ignore

    def configure_inherited_params(self):
        super().configure_inherited_params()
        if self.config is None:
            return

        ##### Standby settings (if the tool has an extruder) #####
        if self.extruder is not None:
            self.timer_heater_active_to_standby_delay = ktc_ToolStandbyTempTimer(
                self.printer, self.name, ktc_ToolStandbyTempTimer.TIMER_TO_STANDBY
            )
            self.timer_heater_active_to_powerdown_delay = ktc_ToolStandbyTempTimer(
                self.printer, self.name, ktc_ToolStandbyTempTimer.TIMER_TO_SHUTDOWN
            )
        # If this tool is a subtool of another tool and 
        # the etruder is not overriden then use the inherited extruder.
        elif self.toolchanger.parent_tool is not None and (
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

    # def select(self):
    #     return

    # # To avoid recursive remaping.
    # def select_tool_actual(self, restore_mode=None):
        current_tool_id = int(self._ktc.active_tool_n)

        self.log.trace("Current Tool is T" + str(current_tool_id) + ".")
        # self.log.trace("This tool is_virtual is " + str(self.is_virtual) + ".")

        if (
            current_tool_id == self.number
        ):  # If trying to select the already selected tool:
            return  # Exit

        if current_tool_id == self.TOOL_UNKNOWN.number:
            msg = ("KtcTool.select_tool_actual: Unknown tool already mounted." 
                   + "Can't park it before selecting new tool.")
            self.log.always(msg)
            raise self.printer.command_error(msg)

        self.log.tool_stats[self.name].selects_started += 1

        if (
            self.extruder is not None
        ):  # If the new tool to be selected has an extruder prepare warmup before actual tool change so all unload commands will be done while heating up.
            self.set_heater(heater_state=KtcHeater.StateType.HEATER_STATE_ACTIVE)

        # If optional RESTORE_POSITION_TYPE parameter is passed then save current position.
        # Otherwise do not change either the restore_axis_on_toolchange or saved_position.
        # This makes it possible to call SAVE_POSITION or SAVE_CURRENT_POSITION before the actual T command.
        if restore_mode is not None:
            self._ktc.SaveCurrentPosition(
                restore_mode
            )  # Sets restore_axis_on_toolchange and saves current position

        # Drop any tools already mounted if not virtual on same.
        if (
            current_tool_id > self.TOOL_NONE_N
        ):  # If there is a current tool already selected and it's a known tool.
            # TODO: Change this to nicer code.
            self.log.track_tool_selected_end(
                self._ktc.all_tools_by_number[current_tool_id]
            )  # Log that the current tool is to be unmounted.

            current_tool = self.printer.lookup_object(
                "ktc_tool " + str(current_tool_id)
            )

            # If the next tool is not another virtual tool on the same physical tool.
            if int(self.parentTool_id == self.TOOL_NONE_N or self.parentTool_id) != int(
                current_tool.get_status()["parentTool_id"]
            ):
                self.log.info("Will Dropoff():%s" % str(current_tool_id))
                current_tool.Dropoff()
                current_tool_id = self.TOOL_NONE_N
            else:  # If it's another virtual tool on the same parent physical tool.
                self.log.info(
                    "Dropoff: T"
                    + str(current_tool_id)
                    + "- Virtual - Running UnloadVirtual"
                )
                current_tool.UnloadVirtual()

        # Now we asume tool has been dropped if needed be.

        # Check if this is a virtual tool.
        if not self.is_virtual:
            self.log.trace(
                "cmd_SelectTool: T%s - Not Virtual - Pickup" % str(self.number)
            )
            self.Pickup()
        else:
            if (
                current_tool_id > self.TOOL_NONE_N
            ):  # If still has a selected tool: (This tool is a virtual tool with same physical tool as the last)
                current_tool = self.printer.lookup_object(
                    "ktc_tool " + str(current_tool_id)
                )
                self.log.trace(
                    "cmd_SelectTool: T"
                    + str(self.number)
                    + "- Virtual - Physical Tool is not Dropped - "
                )
                if (
                    self.parentTool_id > self.TOOL_NONE_N
                    and self.parentTool_id == current_tool.get_status()["parentTool_id"]
                ):
                    self.log.trace(
                        "cmd_SelectTool: T"
                        + str(self.number)
                        + "- Virtual - Same physical tool - Pickup"
                    )
                    self.LoadVirtual()
                else:
                    msg = (
                        "cmd_SelectTool: T"
                        + str(self.number)
                        + "- Virtual - Not Same physical tool"
                    )
                    msg += "Shouldn't reach this because it is dropped in previous."
                    self.log.debug(msg)
                    raise Exception(msg)
            else:  # New Physical tool with a virtual tool.
                parentTool = self.printer.lookup_object(
                    "ktc_tool " + str(self.parentTool_id)
                )
                parentTool_virtual_loaded = parentTool.get_status()["virtual_loaded"]
                self.log.trace(
                    "cmd_SelectTool: T"
                    + str(self.number)
                    + "- Virtual - Picking upp physical tool"
                )
                self.Pickup()

                # If the new physical tool already has another virtual tool loaded:
                if parentTool_virtual_loaded > self.TOOL_NONE_N:
                    # TODO: Change this to use the name mapping instead of number.
                    if parentTool_virtual_loaded != self.number:
                        self.log.info(
                            "cmd_SelectTool: T"
                            + str(parentTool_virtual_loaded)
                            + "- Virtual - Running UnloadVirtual"
                        )

                        uv: KtcTool = self.printer.lookup_object(
                            "ktc_tool " + str(parentTool_virtual_loaded)
                        )
                        if (
                            uv.extruder is not None
                        ):  # If the new tool to be selected has an extruder prepare warmup before actual tool change so all unload commands will be done while heating up.
                            curtime = self.printer.get_reactor().monotonic()
                            # heater = self.printer.lookup_object(self.extruder).get_heater()

                            uv.set_heater(
                                heater_state=KtcHeater.StateType.HEATER_STATE_ACTIVE
                            )
                            # if int(self.heater_state) == KtcHeater.StateType.HEATER_STATE_ACTIVE and int(self.heater_standby_temp) < int(heater.get_status(curtime)["temperature"]):
                            self._ktc._Temperature_wait_with_tolerance(
                                curtime, self.extruder, 2
                            )
                        uv.UnloadVirtual()
                        self.set_heater(
                            heater_state=KtcHeater.StateType.HEATER_STATE_ACTIVE
                        )

                self.log.trace(
                    "cmd_SelectTool: T"
                    + str(self.number)
                    + "- Virtual - Picked up physical tool and now Loading virtual tool."
                )
                self.LoadVirtual()

        self._ktc.active_tool = self
        self.log.track_tool_selected_start(self)

    def Pickup(self):
        self.log.track_tool_selecting_start(
            self
        )  # Log the time it takes for tool mount.

        # Check if homed
        if not self._ktc.printer_is_homed_for_toolchange():
            raise self.printer.command_error(
                "KtcTool.Pickup: Printer not homed and Lazy homing option for tool %s is: "
                % (self.name)
            )

        # If has an extruder then activate that extruder.
        if self.extruder is not None:
            self.gcode.run_script_from_command(
                "ACTIVATE_EXTRUDER extruder=%s" % (self.extruder)
            )

        # Run the gcode for pickup.
        try:
            context = self.tool_select_gcode_template.create_template_context()
            context["myself"] = self.get_status()
            context["ktc"] = self._ktc.get_status()
            self.tool_select_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception("Pickup gcode: Script running error: %s" % (str(e)))

        # Restore fan if has a fan.
        if self.fan is not None:
            self.gcode.run_script_from_command(
                "SET_FAN_SPEED FAN="
                + self.fan
                + " SPEED="
                + str(self._ktc.get_status()["saved_fan_speed"])
            )

        # Save current picked up tool and print on screen.
        self._ktc.active_tool = self
        if self.is_virtual:
            self.log.always("Physical Tool for T%d picked up." % (self.number))
        else:
            self.log.always("T%d picked up." % (self.number))

        self.log.track_tool_selecting_end(self)

    def Dropoff(self, force_virtual_unload=False):
        self.log.always("Dropoff: T%s - Running." % str(self.number))

        self.log.track_tool_selected_end(
            self
        )  # Log that the current tool is to be unmounted.

        # Check if homed
        if not self._ktc.printer_is_homed_for_toolchange():
            self.log.always("KtcTool.Dropoff: Printer not homed")
            return None

        # Turn off fan if has a fan.
        if self.fan is not None:
            self.gcode.run_script_from_command(
                "SET_FAN_SPEED FAN=" + self.fan + " SPEED=0"
            )

        # Check if this is a virtual tool.
        self.log.trace(
            "Dropoff: T" + str(self.number) + "- is_virtual: " + str(self.is_virtual)
        )
        if self.is_virtual:
            # Only dropoff if it is required.
            if self.unload_virtual_at_dropoff or force_virtual_unload:
                self.log.debug(
                    "T%s: unload_virtual_at_dropoff: %s, force_virtual_unload: %s"
                    % (
                        str(self.number),
                        str(self.unload_virtual_at_dropoff),
                        str(force_virtual_unload),
                    )
                )
                self.log.info(
                    "Dropoff: T"
                    + str(self.number)
                    + "- Virtual - Running UnloadVirtual"
                )
                self.UnloadVirtual()

        self.log.track_tool_deselecting_start(
            self
        )  # Log the time it takes for tool change.
        # Run the gcode for dropoff.
        try:
            context = self._tool_deselect_gcode_template.create_template_context()
            context["myself"] = self.get_status()
            context["ktc"] = self._ktc.get_status()
            self._tool_deselect_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception("Dropoff gcode: Script running error: %s" % (str(e)))

        self._ktc.active_tool = self.TOOL_NONE  # Dropoff successfull
        self.log.track_tool_deselecting_end(
            self
        )  # Log the time it takes for tool change.

    def LoadVirtual(self):
        self.log.info("Loading virtual tool: T%d." % self.number)
        self.log.track_tool_selecting_start(
            self
        )  # Log the time it takes for tool mount.

        # Run the gcode for Virtual Load.
        try:
            context = self.virtual_toolload_gcode_template.create_template_context()
            context["myself"] = self.get_status()
            context["ktc"] = self._ktc.get_status()
            self.virtual_toolload_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception(
                "virtual_toolload_gcode: Script running error: %s" % (str(e))
            )

        # TODO: Change this to use the ktc_toolchanger instead of parentTool.
        parentTool = self.printer.lookup_object("ktc_tool " + str(self.parentTool_id))
        parentTool.set_virtual_loaded(self.number)

        # Save current picked up tool and print on screen.
        self._ktc.active_tool = self
        self.log.trace("Virtual T%d Loaded" % (self.number))
        self.log.track_tool_selecting_end(
            self
        )  # Log number of toolchanges and the time it takes for tool mounting.

    def set_virtual_loaded(self, value=-1):
        self.virtual_loaded = value
        self.log.trace(
            "Saved VirtualToolLoaded for T%s as: %s" % (str(self.number), str(value))
        )

    def UnloadVirtual(self):
        self.log.info("Unloading virtual tool: T%d." % self.number)
        self.log.track_tool_deselecting_start(
            self
        )  # Log the time it takes for tool unload.

        # Run the gcode for Virtual Unload.
        try:
            context = self.virtual_toolunload_gcode_template.create_template_context()
            context["myself"] = self.get_status()
            context["ktc"] = self._ktc.get_status()
            self.virtual_toolunload_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception(
                "virtual_toolunload_gcode: Script running error:\n%s" % str(e)
            )

        parentTool = self.printer.lookup_object("ktc_tool " + str(self.parentTool_id))
        parentTool.set_virtual_loaded(-1)

        # Save current picked up tool and print on screen.
        self._ktc.active_tool = self
        self.log.trace("Virtual T%d Unloaded" % (int(self.number)))

        self.log.track_tool_deselecting_end(
            self
        )  # Log the time it takes for tool unload.

    def set_offset(self, **kwargs):
        for i in kwargs:
            if i == "x_pos":
                self.offset[0] = float(kwargs[i])
            elif i == "x_adjust":
                self.offset[0] = float(self.offset[0]) + float(kwargs[i])
            elif i == "y_pos":
                self.offset[1] = float(kwargs[i])
            elif i == "y_adjust":
                self.offset[1] = float(self.offset[1]) + float(kwargs[i])
            elif i == "z_pos":
                self.offset[2] = float(kwargs[i])
            elif i == "z_adjust":
                self.offset[2] = float(self.offset[2]) + float(kwargs[i])

        self.log.always(
            "T%d offset now set to: %f, %f, %f."
            % (
                int(self.number),
                float(self.offset[0]),
                float(self.offset[1]),
                float(self.offset[2]),
            )
        )

    def _set_state(self, heater_state):
        self.heater_state = heater_state

    def set_heater(self, **kwargs):
        if self.extruder is None:
            self.log.debug(
                "set_heater: T%d has no extruder! Nothing to do." % self.number
            )
            return None

        # self.log.info("T%d heater is at begingin %s. %s*C" % (self.name, self.heater_state, self.heater_active_temp ))

        heater = self.printer.lookup_object(self.extruder).get_heater()
        curtime = self.printer.get_reactor().monotonic()
        changing_timer = False

        # self is always pointing to virtual tool but its timers and extruder are always pointing to the physical tool. When changing multiple virtual tools heaters the statistics can remain open when changing by timers of the parent if another one got in between.
        # Therefore it's important for all heater statistics to only point to physical parent.

        # TODO: Change this to use the ktc_toolchanger instead of parentTool.
        if self.is_virtual == True:
            tool_for_tracking_heater = self.parentTool_id
        else:
            tool_for_tracking_heater = self.name

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
            "parentTool_id": self.parentTool_id,
            "extruder": self.extruder,
            "fan": self.fan,
            "offset": self.offset,
            "heater_state": self.heater_state,
            "heater_active_temp": self.heater_active_temp,
            "heater_standby_temp": self.heater_standby_temp,
            "heater_active_to_standby_delay": self.heater_active_to_standby_delay,
            "idle_to_powerdown_next_wake": self.heater_active_to_powerdown_delay,
            "virtual_loaded": self.virtual_loaded,
            "unload_virtual_at_dropoff": self.unload_virtual_at_dropoff,
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
            if tool.is_virtual == True:
                tool_for_tracking_heater = tool.parentTool_id
            else:
                tool_for_tracking_heater = tool.name

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
            heater = self.printer.lookup_object(tool.extruder).get_heater()
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
                tool._set_state(KtcHeater.StateType.HEATER_STATE_OFF)  # Set off state.
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
