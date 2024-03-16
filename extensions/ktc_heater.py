# KTC - Klipper Tool Changer code (v.2)
# Heater control for controlling the temperature of the tools
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import typing, dataclasses
from enum import IntEnum, unique

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode, klippy, reactor
    from ...klipper.klippy.extras import heaters as klippy_heaters

    # from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_log, ktc_toolchanger, ktc_tool, ktc

DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY = 0.1
DEFAULT_HEATER_STANDBY_TO_POWERDOWN_DELAY = 0.2
NOW = 0.1
NEVER = 0


@unique
class HeaterStateType(IntEnum):
    OFF = 0
    STANDBY = 1
    ACTIVE = 2

    @classmethod
    def parse_heater_state(cls, state: str):
        state = str(state).strip()
        if state is not None:
            if state.lower() in ("0", "off"):
                return cls.OFF
            elif state.lower() in ("1", "standby"):
                return cls.STANDBY
            elif state.lower() in("2", "active"):
                return cls.ACTIVE
            else:
                raise ValueError(
                    f"Invalid value for heater state: {state}. "
                    + "Valid values are: 0/OFF, 1/STANDBY, 2/ACTIVE."
                )


@unique
class HeaterTimerType(IntEnum):
    TIMER_TO_SHUTDOWN = 0
    TIMER_TO_STANDBY = 1


# @dataclasses_json.dataclass_json
@dataclasses.dataclass
class KtcHeaterSettings:
    name: str
    temperature_offset: float

    def __init__(self, name: str, temperature_offset: float):
        self.name = name
        self.temperature_offset = temperature_offset

    @classmethod
    def from_list(cls, list_value: list):
        temp = [list_value[0], 0.0]  # Default temperature temperature_offset
        for i, val in enumerate(list_value[1:]):
            temp[i + 1] = float(val)
        return cls(*temp)

    @classmethod
    def from_string(cls, string_value: str):
        list_value = string_value.split(":")
        return cls.from_list(list_value)

    @classmethod
    def from_dict(cls, data):
        return cls(name=data["name"], temperature_offset=data["temperature_offset"])

    def to_dict(self):
        return {"name": self.name, "temperature_offset": self.temperature_offset}


class KtcToolExtruder:
    def __init__(self, tool: "ktc_tool.KtcTool"):
        self._tool = tool
        self._state = HeaterStateType.OFF
        self._active_temp = 0
        self._standby_temp = 0
        self._active_to_standby_delay = DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY
        self._standby_to_powerdown_delay = DEFAULT_HEATER_STANDBY_TO_POWERDOWN_DELAY
        self.heaters: list["KtcHeaterSettings"] = []
        # dataclasses.field(default_factory=list)

        if tool.name not in ("tool_unknown", "tool_none"):
            self._ktc = tool._ktc

    def heater_names(self) -> list[str]:
        return [heater.name for heater in self.heaters]

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value: HeaterStateType):
        self._state = value
        self._tool._ktc.log.trace(
            f"In extr. Setting heater state to {value} "
            + f"for tool {self._tool.name}"
        )

        # Allways set active state on all heaters
        if value == HeaterStateType.ACTIVE:
            self._tool._ktc.log.trace(
                f"In extr. Setting heater state to ACTIVE "
                + f"for tool {self._tool.name}"
                + f" with active_temp {self._active_temp}"
            )
            for hs in self.heaters:
                self._tool._ktc.all_heaters[hs.name].heater_active_temp = (
                    self._active_temp + hs.temperature_offset
                )
                self._tool._ktc.all_heaters[hs.name].state = value
            self._tool._ktc.log.track_heater_active_start(self._tool)
            return

        # For STANDY and OFF, check if the heater is active on another tool.
        heaters_active_with_other_tool: list[str] = []
        invalid_tools = (
                self._tool,
                self._tool._ktc.TOOL_NONE,
                self._tool._ktc.TOOL_UNKNOWN,
                None,
            )
        for tool in self._tool._ktc.all_tools.values():
            if tool not in invalid_tools:
                if tool.extruder.state == HeaterStateType.ACTIVE:
                    heaters_active_with_other_tool.extend(tool.extruder.heater_names())

        for hs in self.heaters:
            if hs.name not in heaters_active_with_other_tool:
                if value == HeaterStateType.STANDBY:
                    self._tool._ktc.log.trace(
                        f"Setting heater state to STANDBY for tool {self._tool.name}"
                        + f" with heater {hs.name} and "
                        + f"active_to_standby_delay {self._active_to_standby_delay}, "
                        + f"standby_to_powerdown_delay {self._standby_to_powerdown_delay}"
                    )
                    self._tool._ktc.all_heaters[hs.name].standby_temp = (
                        self._standby_temp + hs.temperature_offset
                    )
                    self._tool._ktc.log.trace(
                        f".standby_temp is {self._tool._ktc.all_heaters[hs.name].standby_temp}, "
                        + f"._standby_temp is {self._standby_temp}, "
                        + f"temperature_offset is {hs.temperature_offset}"
                    )
                    self._tool._ktc.all_heaters[hs.name].active_to_standby_delay = (
                        self.active_to_standby_delay
                    )
                    self._tool._ktc.all_heaters[hs.name].standby_to_powerdown_delay = (
                        self.standby_to_powerdown_delay
                    )
                self._tool._ktc.all_heaters[hs.name].state = value
            else:
                # Can't track standby for tool if heater is in active state on another tool.
                self._tool._ktc.log.trace(
                    f"Tool {self._tool.name} has heater {hs.name} active on another tool. "
                )
                self._tool._ktc.log.track_heater_active_end(self._tool)
                self._tool._ktc.log.track_heater_standby_end(self._tool)
                self._state = HeaterStateType.OFF

    @property
    def active_temp(self):
        return self._active_temp

    @active_temp.setter
    def active_temp(self, value):
        self._active_temp = value
        if self.state == HeaterStateType.ACTIVE:
            for hs in self.heaters:
                self._tool._ktc.all_heaters[hs.name].heater_active_temp = (
                    value + hs.temperature_offset
                )

    @property
    def standby_temp(self):
        return self._standby_temp

    @standby_temp.setter
    def standby_temp(self, value):
        self._standby_temp = value
        if self.state == HeaterStateType.STANDBY:
            for hs in self.heaters:
                self._tool._ktc.all_heaters[hs.name].standby_temp = value

    @property
    def active_to_standby_delay(self):
        return self._active_to_standby_delay

    @active_to_standby_delay.setter
    def active_to_standby_delay(self, value):
        self._active_to_standby_delay = value
        # If heater is active on only this tool or
        # standby on only this tool and the timer is counting down

        if (
            self.state == HeaterStateType.ACTIVE
            or self.state == HeaterStateType.STANDBY
        ):
            for hs in self.heaters:
                ht = self._tool._ktc.all_heaters[hs.name]
                if ht.state == HeaterStateType.ACTIVE or (
                    ht.state == HeaterStateType.STANDBY
                    and ht.timer_heater_active_to_standby_delay.counting_down
                ):
                    ht.active_to_standby_delay = value

    @property
    def standby_to_powerdown_delay(self):
        return self._standby_to_powerdown_delay

    @standby_to_powerdown_delay.setter
    def standby_to_powerdown_delay(self, value):
        self._standby_to_powerdown_delay = value

        self._tool._ktc.log.trace(
            f"Setting standby_to_powerdown_delay to {value} for tool {self._tool.name}"
            + f" with state {self.state}"
        )

        if self.state == HeaterStateType.STANDBY:
            for hs in self.heaters:
                if (
                    self._tool._ktc.all_heaters[hs.name].state
                    == HeaterStateType.STANDBY
                    and self._tool._ktc.all_heaters[
                        hs.name
                    ].timer_heater_standby_to_powerdown_delay.counting_down
                ):
                    self._tool._ktc.all_heaters[hs.name].standby_to_powerdown_delay = (
                        value
                    )


class KtcHeater:
    def __init__(self, config: "configfile.ConfigWrapper"):
        self.printer: "klippy.Printer" = config.get_printer()
        self.name = typing.cast(str, config.get_name().split(" ", 1)[1])
        self.temperature_offset = 0.0

        self._state = HeaterStateType.OFF
        # Timer to set temperature to standby temperature
        # after heater_active_to_standby_delay seconds. Set if this tool has an heaters.
        self.timer_heater_active_to_standby_delay = KtcHeaterTimer(
            self.printer, self, HeaterTimerType.TIMER_TO_STANDBY
        )

        # Timer to set temperature to 0 after heater_standby_to_powerdown_delay seconds.
        # Set if this tool has an heaters.
        self.timer_heater_standby_to_powerdown_delay = KtcHeaterTimer(
            self.printer, self, HeaterTimerType.TIMER_TO_SHUTDOWN
        )

        # Temperature to set when in active mode.
        # Requred on Physical and virtual tool if any has heaters.
        self._heater_active_temp = 0
        # Temperature to set when in standby mode.
        # Requred on Physical and virtual tool if any has heaters.
        self._standby_temp = 0

        self.__active_to_standby_delay = DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY
        self.__standby_to_powerdown_delay = DEFAULT_HEATER_STANDBY_TO_POWERDOWN_DELAY

        self.klippy_heater = typing.cast(
            "klippy_heaters.Heater",
            self.printer.lookup_object("heaters").lookup_heater(self.name),
        )

    @property
    def active_to_standby_delay(self) -> float:
        return self.__active_to_standby_delay

    @active_to_standby_delay.setter
    def active_to_standby_delay(self, value: float):
        self.__active_to_standby_delay = value
        self.printer.lookup_object("ktc_log").trace(
            f"Setting heater_active_to_standby_delay to {value} for heater {self.name}"
        )
        if self.state == HeaterStateType.STANDBY:
            self.printer.lookup_object("ktc_log").trace(
                f"Setting timer for active to standby to {value} for heater {self.name}"
            )
            self.timer_heater_active_to_standby_delay.set_timer(value)

    @property
    def standby_to_powerdown_delay(self) -> float:
        return self.__standby_to_powerdown_delay

    @standby_to_powerdown_delay.setter
    def standby_to_powerdown_delay(self, value: float):
        self.__standby_to_powerdown_delay = value
        self.printer.lookup_object("ktc_log").trace(
            f"Setting timer for standby to powerdown to {value} for heater {self.name}"
            + f" with state {self.state}"
        )
        if self.state == HeaterStateType.OFF:
            self.printer.lookup_object("ktc_log").trace("State is OFF")
            self.timer_heater_standby_to_powerdown_delay.set_timer(value)

    @property
    def state(self) -> HeaterStateType:
        return self._state

    @state.setter
    def state(self, value: HeaterStateType) -> None:
        """Set the state of the heater. The state can be OFF, STANDBY or ACTIVE.
        Disregard the previous state.
        Restart the timers if the state is changed to STANDBY."""
        self.printer.lookup_object("ktc_log").trace(
            f"In heater.state.setter. Setting heater state to {value} for heater {self.name}"
        )

        set_timer_to_standby = self.timer_heater_active_to_standby_delay.set_timer
        set_timer_to_powerdown = self.timer_heater_standby_to_powerdown_delay.set_timer

        if value == HeaterStateType.ACTIVE:
            set_timer_to_standby(NEVER)
            set_timer_to_powerdown(NEVER)
            # Log the start of the heater
            self.printer.lookup_object("ktc_log").trace(
                f"Setting heater state to ACTIVE for heater {self.name}"
                + f" with klippy heater {self.klippy_heater.name}"
                + f" and heater_active_temp {self.heater_active_temp}"
            )
            self.klippy_heater.set_temp(self.heater_active_temp)
        elif value == HeaterStateType.STANDBY:
            if self._state != HeaterStateType.ACTIVE:
                self.printer.lookup_object("ktc_log").trace(
                    "Heater state is set to STANDBY without being ACTIVE first."
                    + f" State is {self._state} for heater {self.name}"
                )
                set_timer_to_standby(NOW)
            else:
                if self.timer_heater_active_to_standby_delay.counting_down:
                    self.printer.lookup_object("ktc_log").trace(
                        "Heater state is set to STANDBY while the active to "
                        + "standby timer is counting down."
                    )
                    set_timer_to_standby(NOW)
                else:
                    self.printer.lookup_object("ktc_log").trace(
                        f"Setting heater state to STANDBY for heater {self.name}"
                        + f" with klippy heater {self.klippy_heater.name}"
                        + f" and delay {self.active_to_standby_delay}"
                    )
                    set_timer_to_standby(self.active_to_standby_delay)
            # set_timer_to_powerdown(self.standby_to_powerdown_delay)
        elif value == HeaterStateType.OFF:
            set_timer_to_standby(NEVER)
            set_timer_to_powerdown(NOW)
        self._state = value

    @property
    def heater_active_temp(self):
        return self._heater_active_temp

    @heater_active_temp.setter
    def heater_active_temp(self, value):
        self._heater_active_temp = value if value > 0 else 0
        if self.state == HeaterStateType.ACTIVE:
            self.klippy_heater.set_temp(self._heater_active_temp)

    @property
    def standby_temp(self):
        return self._standby_temp

    @standby_temp.setter
    def standby_temp(self, value):
        self._standby_temp = value if value > 0 else 0
        if (
            self.state == HeaterStateType.STANDBY
            and not self.timer_heater_active_to_standby_delay.counting_down
        ):
            self.klippy_heater.set_temp(self._standby_temp)


class KtcHeaterTimer:
    def __init__(
        self, printer: "klippy.Printer", heater: KtcHeater, timer_type: HeaterTimerType
    ):
        self.printer = printer
        self.heater = heater

        self.duration = 0.0
        self.timer_type = timer_type  # 0= Time to shutdown, 1= Time to standby.

        self.reactor: "reactor.Reactor" = self.printer.get_reactor()
        self.gcode = typing.cast(
            "gcode.GCodeDispatch", self.printer.lookup_object("gcode")
        )
        self.timer_handler = None
        self.inside_timer = self.repeat = False
        self.printer.register_event_handler("klippy:ready", self.__handle_ready)
        self.log = typing.cast("ktc_log.KtcLog", self.printer.lookup_object("ktc_log"))

        self.counting_down = False
        self.nextwake = self.reactor.NEVER

    def __handle_ready(self):
        self.timer_handler = self.reactor.register_timer(
            self._temp_timer_event, self.reactor.NEVER
        )

    def _temp_timer_event(self, eventtime):
        self.inside_timer = True
        self.counting_down = False
        self.log.trace(
            f"Running heater timer for {self.heater.name}: "
            + f"{('Standby' if self.timer_type == HeaterTimerType.TIMER_TO_STANDBY else 'OFF')}"
        )

        try:
            if self.timer_type == HeaterTimerType.TIMER_TO_STANDBY:
                self.log.track_heater_standby_start_for_standby_tools_having_heater(
                    self.heater
                )
                self.log.track_heater_active_end_for_tools_having_heater(self.heater)
                self.heater.klippy_heater.set_temp(self.heater.standby_temp)
                self.heater.timer_heater_active_to_standby_delay.set_timer(NEVER)
                self.heater.timer_heater_standby_to_powerdown_delay.set_timer(
                    self.heater.standby_to_powerdown_delay
                )
                self.log.trace(
                    f"Setting temperature to {self.heater.standby_temp} "
                    + f"for heater {self.heater.name} "
                )
            else:
                self.heater.klippy_heater.set_temp(0)
                self.heater.timer_heater_active_to_standby_delay.set_timer(NEVER)
                self.heater.timer_heater_standby_to_powerdown_delay.set_timer(NEVER)
                self.log.trace(
                    f"Setting temperature to 0 for heater {self.heater.name} "
                )
                self.log.track_heater_end_for_tools_having_heater(self.heater)

        except Exception as e:
            self.log.always(
                f"Failed to run {('Standby' if self.timer_type == 1 else 'OFF')} "
                + f"timer for heater {self.heater.name}: {str(e)}"
            )
            raise Exception(
                f"Failed to run{('Standby' if self.timer_type == 1 else 'OFF')} "
                + f"timer for heater {self.heater.name}: {str(e)}"
            ) from e

        if self.repeat:
            self.nextwake = eventtime + self.duration
            self.counting_down = True
        else:
            self.nextwake = self.reactor.NEVER
        self.inside_timer = self.repeat = False
        return self.nextwake

    def set_timer(self, duration: float):
        """Set the timer for the heater and the duration.
        If duration is 0, the timer is stopped."""
        self.duration = float(duration)
        if self.inside_timer:
            self.repeat = self.duration != 0.0
        else:
            waketime = self.reactor.NEVER
            if self.duration:
                waketime = self.reactor.monotonic() + self.duration
                self.nextwake = waketime
            self.reactor.update_timer(self.timer_handler, waketime)
            self.log.trace(
                f"heatertimer set_timer {self.timer_type}: "
                + f"duration: {self.duration}, "
                + f"nextwake: {self._time_left()}"
                f"counting_down: {self.counting_down}"
            )
            if self.duration:
                self.counting_down = True
            else:
                self.counting_down = False

        self.log.trace(
            f"Time until heater {str(self.heater.name)} "
            + f"changes to {('Standby' if self.timer_type == 1 else 'OFF')}:"
            + f"{self._time_left()}"
        )

    def get_status(self, eventtime=None):  # pylint: disable=unused-argument
        status = {
            "timer_type": self.timer_type,
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


def load_config_prefix(config):
    return KtcHeater(config)
