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
from .ktc_heater import HeaterStateType, KtcHeaterSettings   # pylint: disable=relative-beyond-top-level

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_toolchanger

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

    @property
    def toolchanger(self) -> "ktc_toolchanger.KtcToolchanger":
        return self._toolchanger

    @toolchanger.setter
    def toolchanger(self, value):
        if value is not None and not isinstance(value, KtcBaseChangerClass):
            raise ValueError("Toolchanger must be a KtcToolchanger object.")
        self._toolchanger = value  # type: ignore

    @KtcBaseToolClass.state.setter
    def state(self, value):
        super(KtcBaseToolClass, type(self)).state.fset(self, value) # type: ignore

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
            heaters = self._heaters_config.replace(" ", "").split(",")
            for heater_string in heaters:
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

    def cmd_SelectTool(self, gcmd): # pylint: disable=invalid-name, unused-argument
        self.log.trace("KTC Tool " + str(self.number) + " Selected.")
        self.run_with_profile(self.select, final_selected=True)

    def select(self, final_selected=False):
        self.state = self.StateType.SELECTING
        try:
            self.log.always("KTC Tool %s Selecting." % self.name)
            at = self._ktc.active_tool

            # Check if homed
            self._ktc.confirm_ready_for_toolchange(self)

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

                # If the new tool to be selected has any heaters prepare warmup before
                # actual tool change so all moves will be done while heating up.
                if len(self.extruder.heaters) > 0:
                    self.set_heaters(heater_state=HeaterStateType.ACTIVE)

                # Put all other active heaters in standby.
                for heater in ( heater for heater in self._ktc.all_heaters.values()
                                if heater.state == HeaterStateType.ACTIVE
                                and heater.name not in self.extruder.heater_names()):
                    heater.state = HeaterStateType.STANDBY

                # If another tool is selected it needs to be deselected first.
                if at is not self.TOOL_NONE:
                    # If the new tool is on the same toolchanger as the current tool.
                    if self.toolchanger == at.toolchanger:
                        at.deselect()
                    # If on different toolchanger:
                    else:
                        # First deselect all tools recursively.
                        # Only if force_deselect_when_parent_deselects is True for the tool.
                        tools = self._get_list_from_tool_traversal_conditional(
                            at, "force_deselect_when_parent_deselects", True)
                        for t in tools:
                            t.deselect()
                            # Check if the tool to be deselected is on the same toolchanger.
                            # Then don't deselect beyond that tool.
                            if t.toolchanger == self.toolchanger:
                                break
                        # Then select the new tools recursively in reverse order
                        # by getting the list of tools not already selected.
                        tools = self._get_list_from_tool_traversal_conditional(
                            self, "state", self.StateType.SELECTED, operator.ne)
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
                self.state = self.StateType.SELECTING
                self.toolchanger.state = self.toolchanger.StateType.CHANGING
                self._ktc.state = self.StateType.CHANGING
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
                    + "'KTC_SET_STATE TOOL={myself.name} STATE=SELECTED' to "
                    + "indicate it is selected successfully. Or ERROR if it failed.")
                )
            elif self.state == self.StateType.ERROR:
                raise self.config.error(
                    ("tool_select_gcode changed the state to ERROR while running.")
                )

            if final_selected and self.state == self.StateType.SELECTED:
                # Restore fan if has a fan.
                for fan in self.fans:
                    self.gcode.run_script_from_command(
                        "SET_FAN_SPEED FAN="
                        + fan[0]
                        + " SPEED="
                        + str(self._ktc.saved_fan_speed * float(fan[1]))
                    )

                self._ktc.active_tool = self
                self.log.track_tool_selected_start(self)
                self.state = self.StateType.ACTIVE

            self.log.tool_stats[self.name].selects_completed += 1

        except Exception as e:
            self.log.always("KTC Tool %s failed to select: %s" % (self.name, str(e)))
            self.state = self.StateType.ERROR
            self._ktc.state = self.StateType.ERROR
            raise e from e
        finally:
            self.log.track_tool_selecting_end(self)

    def deselect(self):    # pylint: disable=arguments-differ
        self.state = self.StateType.DESELECTING
        try:
            # Check if homed
            self._ktc.confirm_ready_for_toolchange(self)

            self.log.track_tool_selected_end(self)
            self.log.track_tool_deselecting_start(self)
            self.log.tool_stats[self.name].deselects_started += 1

            self.extruder.state = HeaterStateType.STANDBY

            # Turn off fan if has a fan.
            self._ktc.tool_fan_speed_set(self, 0)

            # Check if toolchanger is not topmost and
            # parent tool must be selected on deselect and
            # parent tool is not selected.
            if (
                self.toolchanger.parent_tool is not None and
                self.parent_must_be_selected_on_deselect and
                self.toolchanger.parent_tool.state != self.StateType.SELECTED
                ):
                tools_to_select = self._get_list_from_tool_traversal_conditional(
                    self, "parent_must_be_selected_on_deselect", True)
                for t in reversed(tools_to_select):
                    t.select()

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
            if self.state == self.StateType.DESELECTING:
                raise self.config.error(
                    ("tool_deselect_gcode has not changed the state while running "
                    + "code in tool_select_gcode. Use for example "
                    + "'KTC_SET_STATE TOOL={myself.name} STATE=SELECTED' to "
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

        if start_tool in (
            self.TOOL_NONE,
            self.TOOL_UNKNOWN,
            self._ktc,
            None
        ):
            return return_list

        if condition(getattr(start_tool, param), value):
            return_list.append(start_tool)

        upper_tool = start_tool.toolchanger.parent_tool

        if upper_tool is not None:
            return_list += self._get_list_from_tool_traversal_conditional(
                upper_tool, param, value, condition)

        return return_list

    def set_heaters(self, **kwargs) -> None:
        if len(self.extruder.heaters) < 1:
            self.log.debug(
                "set_heater: KTC Tool %s has no heaters! Nothing to do." % self.name
            )
            return None

        self.log.trace(f"set_heater: KTC Tool {self.name} heater is at begining " +
                       f"{self.extruder.state}. {self.extruder.active_temp}*C, " +
                       f"{self.extruder.standby_temp}*C")

        changing_timer = False
        ex = self.extruder

        if self in self.INVALID_TOOLS:
            self.log.always("KTC Tool %s is not a valid tool to set heaters for." % self.name)
            return

        for i in kwargs:    # pylint: disable=consider-using-dict-items
            if i == "heater_active_temp":
                ex.active_temp = kwargs[i]
            elif i == "heater_standby_temp":
                ex.standby_temp = kwargs[i]
            elif i == "heater_active_to_standby_delay":
                ex.active_to_standby_delay = kwargs[i]
                changing_timer = True
            elif i == "heater_standby_to_powerdown_delay":
                ex.standby_to_powerdown_delay = kwargs[i]
                changing_timer = True
        if "heater_state" in kwargs:
            chng_state = HeaterStateType.parse_heater_state(kwargs["heater_state"])
            ex.state = chng_state

        # If already in standby and timers are counting down,
        # i.e. have not triggered since set in standby,
        # then reset the ones counting down.
        if ex.state == HeaterStateType.STANDBY and changing_timer:
            self.log.trace("ex.state == HeaterStateType.STANDBY and changing_timer.")
            for hs in ex.heaters:
                ht = self._ktc.all_heaters[hs.name]
                if ht.timer_heater_standby_to_powerdown_delay.counting_down:
                    ht.timer_heater_standby_to_powerdown_delay.set_timer(
                        ex.standby_to_powerdown_delay)
                if ht.timer_heater_active_to_standby_delay.counting_down:
                    ht.timer_heater_active_to_standby_delay.set_timer(
                        ex.active_to_standby_delay)

    def get_status(self, eventtime=None):  # pylint: disable=unused-argument
        status = {
            "name": self.name,
            "number": self.number,
            "state": self.state,
            "toolchanger": self.toolchanger.name,
            "fans": self.fans,
            "offset": [self.offset[i] + self._ktc.global_offset[i] for i in range(3)],
            "heater_names": [heater.name for heater in self.extruder.heaters],
            "heater_state": self.extruder.state,
            "heater_active_temp": self.extruder.active_temp,
            "heater_standby_temp": self.extruder.standby_temp,
            "heater_active_to_standby_delay": self.extruder.active_to_standby_delay,
            "standby_to_powerdown_delay": self.extruder.standby_to_powerdown_delay,
            "params_available": str(self.params.keys()),
            **self.params,
        }
        return status

    ###########################################
    # Dataclassess for KtcTool
    ###########################################
def load_config_prefix(config):
    return KtcTool(config)
