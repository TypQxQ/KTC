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
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from ...klipper.klippy import klippy
    # from . import ktc_log, ktc_toolchanger, ktc_tool, ktc

class KtcHeater:

    DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY = 0.1
    DEFAULT_HEATER_STANDBY_TO_POWERDOWN_DELAY = 0.2

    def __init__(self):
        self.state = self.StateType.HEATER_STATE_OFF
        # Timer to set temperature to standby temperature
        # after heater_active_to_standby_delay seconds. Set if this tool has an heaters.
        self.timer_heater_active_to_standby_delay = None
        # Timer to set temperature to 0 after heater_standby_to_powerdown_delay seconds.
        # Set if this tool has an heaters.
        self.timer_heater_standby_to_powerdown_delay = None
        # Temperature to set when in active mode.
        # Requred on Physical and virtual tool if any has heaters.
        self._heater_active_temp = 0
        # Temperature to set when in standby mode.
        # Requred on Physical and virtual tool if any has heaters.
        self._heater_standby_temp = 0

    @unique
    class StateType(IntEnum):
        HEATER_STATE_OFF = 0
        HEATER_STATE_STANDBY = 1
        HEATER_STATE_ACTIVE = 2

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

# @dataclasses_json.dataclass_json
@dataclasses.dataclass
class KtcHeaterSettings:
    name: str
    active_to_standby_delay: float
    standby_to_powerdown_delay: float
    offset: float

    def __init__(self, name: str,
                 active_to_standby_delay: float,
                 standby_to_powerdown_delay: float,
                 offset: float):
        self.name = name
        self.active_to_standby_delay = active_to_standby_delay
        self.standby_to_powerdown_delay = standby_to_powerdown_delay
        self.offset = offset

    @classmethod
    def from_list(cls, list_value: list):
        temp = [list_value[0],
                KtcHeater.DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY,
                KtcHeater.DEFAULT_HEATER_STANDBY_TO_POWERDOWN_DELAY,
                0.0      # Default temperature offset
                ]
        for i, val in enumerate(list_value[1:]):
            temp[i+1] = float(val)
        return cls(*temp)

    @classmethod
    def from_string(cls, string_value: str):
        list_value = string_value.split(',')
        return cls.from_list(list_value)

    def to_dict(self):
        return {'name': self.name,
                'active_to_standby_delay': self.active_to_standby_delay,
                'standby_to_powerdown_delay': self.standby_to_powerdown_delay,
                'offset': self.offset}

    @classmethod
    def from_dict(cls, data):
        return cls(name=data['name'],
                   active_to_standby_delay=data['active_to_standby_delay'],
                   standby_to_powerdown_delay=data['standby_to_powerdown_delay'],
                   offset=data['offset'])
