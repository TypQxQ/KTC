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

@unique
class HeaterStateType(IntEnum):
    OFF = 0
    STANDBY = 1
    ACTIVE = 2

    @classmethod
    def parse_heater_state(cls, state: str):
        state = str(state).strip()
        if state is not None:
            if state.lower() in ["0", "off"]:
                return cls.OFF
            elif state.lower() in ["1", "standby"]:
                return cls.STANDBY
            elif state.lower() in ["2", "active"]:
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

    def __init__(self, name: str,
                 temperature_offset: float):
        self.name = name
        self.temperature_offset = temperature_offset

    @classmethod
    def from_list(cls, list_value: list):
        temp = [list_value[0],
                0.0      # Default temperature temperature_offset
                ]
        for i, val in enumerate(list_value[1:]):
            temp[i+1] = float(val)
        return cls(*temp)

    @classmethod
    def from_string(cls, string_value: str):
        list_value = string_value.split(':')
        return cls.from_list(list_value)

    @classmethod
    def from_dict(cls, data):
        return cls(name=data['name'],
                   temperature_offset=data['temperature_offset'])

    def to_dict(self):
        return {'name': self.name,
                'temperature_offset': self.temperature_offset}

class KtcToolExtruder:
    def __init__(self, tool: 'ktc_tool.KtcTool'):
        self._tool = tool
        self._ktc = tool._ktc
        self._state = HeaterStateType.OFF
        self._active_temp = 0
        self._standby_temp = 0
        self._active_to_standby_delay = DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY
        self._standby_to_powerdown_delay = DEFAULT_HEATER_STANDBY_TO_POWERDOWN_DELAY
        self.heaters: list["KtcHeaterSettings"] = []
        # dataclasses.field(default_factory=list)

    def heater_names(self) -> list[str]:
        return [heater.name for heater in self.heaters]

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value: HeaterStateType):
        if self._state == value:
            return
        self._state = value

        # Allways set active state on all heaters
        if value == HeaterStateType.ACTIVE:
            for hn in self.heaters:
                self._ktc.all_heaters[hn.name].set_state(value, self._tool)
            return

        # Change state on all heaters not active on another tool
        for hn in self.heaters:
            # If the heater is active on another tool do nothing
            is_active_with_other_tool = False
            for tool in self._ktc.all_tools.values():
                if tool not in [self._tool, self._ktc.TOOL_NONE, self._ktc.TOOL_UNKNOWN]:
                    if (hn.name in tool.extruder.heater_names() and
                        tool.extruder.state == HeaterStateType.ACTIVE):
                        is_active_with_other_tool = True
            if not is_active_with_other_tool:
                self._ktc.all_heaters[hn.name].set_state(value, self._tool)

    @property
    def active_temp(self):
        return self._active_temp
    @active_temp.setter
    def active_temp(self, value):
        self._active_temp = value
        if self.state == HeaterStateType.ACTIVE:
            for hs in self.heaters:
                self._ktc.all_heaters[hs.name].heater_active_temp = value

    @property
    def standby_temp(self):
        return self._standby_temp
    @standby_temp.setter
    def standby_temp(self, value):
        self._standby_temp = value
        if self.state == HeaterStateType.STANDBY:
            for hs in self.heaters:
                self._ktc.all_heaters[hs.name].heater_standby_temp = value

    @property
    def active_to_standby_delay(self):
        return self._active_to_standby_delay
    @active_to_standby_delay.setter
    def active_to_standby_delay(self, value):
        self._active_to_standby_delay = value
        # If heater is active on only this tool or
        # standby on only this tool and the timer is counting down

        if self.state == HeaterStateType.ACTIVE or self.state == HeaterStateType.STANDBY:
            for hs in self.heaters:
                ht = self._ktc.all_heaters[hs.name]
                if (ht.state == HeaterStateType.ACTIVE or
                    (ht.state == HeaterStateType.STANDBY and
                     ht.timer_heater_active_to_standby_delay.counting_down)):
                    ht.active_to_standby_delay = value

    @property
    def standby_to_powerdown_delay(self):
        return self._standby_to_powerdown_delay
    @standby_to_powerdown_delay.setter
    def standby_to_powerdown_delay(self, value):
        self._standby_to_powerdown_delay = value
        if self.state == HeaterStateType.STANDBY:
            for hs in self.heaters:
                self._ktc.all_heaters[hs.name].standby_to_powerdown_delay = value

class KtcHeater:
    def __init__(self, config: 'configfile.ConfigWrapper'):
        self.printer : 'klippy.Printer' = config.get_printer()
        self.name = config.get_name()
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
        self._heater_standby_temp = 0

        self.__active_to_standby_delay = DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY
        self.__standby_to_powerdown_delay = DEFAULT_HEATER_STANDBY_TO_POWERDOWN_DELAY

        self.heater_object = typing.cast(
            'klippy_heaters.Heater',
            self.printer.load_object(config, "self.name")
            )

    @property
    def active_to_standby_delay(self):
        return self.__active_to_standby_delay
    @active_to_standby_delay.setter
    def active_to_standby_delay(self, value):
        self.__active_to_standby_delay = value
        self.timer_heater_active_to_standby_delay.set_timer(value, self.name)

    @property
    def standby_to_powerdown_delay(self):
        return self.__standby_to_powerdown_delay
    @standby_to_powerdown_delay.setter
    def standby_to_powerdown_delay(self, value):
        self.__standby_to_powerdown_delay = value
        self.timer_heater_standby_to_powerdown_delay.set_timer(value, self.name)

    @property
    def state(self):
        return self._state
    # @state.setter
    # def state(self, value):
    #     raise NotImplementedError("Not implemented, use set_state instead")

    # Need to have a reference to the calling tool to 
    # be able to check if the heater is active on another tool.
    def set_state(self, value: HeaterStateType, calloing_tool: 'ktc_tool.KtcTool'):
        if self._state == value:
            return

        # If heater is active on another tool then do nothing
        if self._state == HeaterStateType.ACTIVE:
            _ktc = typing.cast(
                    'ktc.Ktc',
                    self.printer.lookup_object("ktc"))

            for tool in _ktc.all_tools.values():
                if tool not in [calloing_tool, _ktc.TOOL_NONE, _ktc.TOOL_UNKNOWN]:
                    if tool.extruder.state == HeaterStateType.ACTIVE:
                        return

        self._state = value
        if value == HeaterStateType.ACTIVE:
            self.timer_heater_standby_to_powerdown_delay.set_timer(
                0, self.name)
            self.timer_heater_active_to_standby_delay.set_timer(
                0, self.name)
            self.heater_object.set_temp(self._heater_active_temp)
        elif value == HeaterStateType.STANDBY:
            self.timer_heater_standby_to_powerdown_delay.set_timer(
                self.standby_to_powerdown_delay, self.name)
            if self.state == HeaterStateType.ACTIVE:
                self.timer_heater_active_to_standby_delay.set_timer(
                    self.active_to_standby_delay, self.name)
            else:
                self.timer_heater_active_to_standby_delay.set_timer(
                    0.1, self.name)
        elif value == HeaterStateType.OFF:
            self.timer_heater_active_to_standby_delay.set_timer(
                0, self.name)
            self.timer_heater_standby_to_powerdown_delay.set_timer(
                0.1, self.name)
            
    @property
    def heater_active_temp(self):
        return self._heater_active_temp
    @heater_active_temp.setter
    def heater_active_temp(self, value):
        self._heater_active_temp = value
        if self.state == HeaterStateType.ACTIVE:
            self.heater_object.set_temp(value)

    @property
    def heater_standby_temp(self):
        return self._heater_standby_temp
    @heater_standby_temp.setter
    def heater_standby_temp(self, value):
        self._heater_standby_temp = value
        if (self.state == HeaterStateType.STANDBY and
            not self.timer_heater_active_to_standby_delay.counting_down
        ):
            self.heater_object.set_temp(value)

class KtcHeaterTimer:
    def __init__(self, printer: 'klippy.Printer', heater, timer_type):
        self.printer = printer
        self.heater = heater

        # self.last_virtual_tool_using_physical_timer = None

        self.duration = 0.0
        self.timer_type = timer_type  # 0= Time to shutdown, 1= Time to standby.

        self.reactor: 'reactor.Reactor' =  self.printer.get_reactor()
        self.gcode = typing.cast('gcode.GCodeDispatch', self.printer.lookup_object("gcode"))
        self.timer_handler = None
        self.inside_timer = self.repeat = False
        self.printer.register_event_handler("klippy:ready", self.__handle_ready)
        self.log = self.printer.lookup_object("ktc_log")

        self.counting_down = False
        self.nextwake = self.reactor.NEVER

    def __handle_ready(self):
        self.timer_handler = self.reactor.register_timer(
            self._standby_tool_temp_timer_event, self.reactor.NEVER
        )

    def _standby_tool_temp_timer_event(self, eventtime):
        self.inside_timer = True
        self.counting_down = False
        try:
            if self.last_virtual_tool_using_physical_timer is None:
                raise Exception("last_virtual_tool_using_physical_timer is < None")

            tool: 'ktc_tool.KtcTool' = self.printer.lookup_object(
                "ktc_tool " + str(self.last_virtual_tool_using_physical_timer)
            )

            self.log.trace(
                "_standby_tool_temp_timer_event: Running for T%s. timer_type:%s. %s"
                % (
                    str(self.tool_id),
                    "Time to shutdown" if self.timer_type == 0 else "Time to standby",
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
            heater = self.printer.lookup_object(tool.extrude).get_heater()
            if self.timer_type == TimerType.TIMER_TO_STANDBY:
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
                tool._set_heater_state(KtcHeater.StateType.OFF)  # Set off state.
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
            + ".set_timer: T%s %s, timer_type:%s, duration:%s."
            % (
                str(self.tool_id),
                (
                    ("for virtual T%s" % str(actual_tool_calling))
                    if actual_tool_calling != self.tool_id
                    else ""
                ),
                ("Standby" if self.timer_type == 1 else "OFF"),
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


    def get_timer_to_standby(self):
        return self.timer_heater_active_to_standby_delay

    def get_timer_to_powerdown(self):
        return self.timer_heater_standby_to_powerdown_delay

def load_config_prefix(config):
    return KtcHeater(config)
