# KTC - Klipper Tool Changer code (v.2)
# Heater control for controlling the temperature of the tools
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import typing
from enum import IntEnum, unique

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from ...klipper.klippy import klippy
    # from . import ktc_log, ktc_toolchanger, ktc_tool, ktc

class KtcHeater:

    def __init__(self):
        self. _state = self.StateType.HEATER_STATE_OFF

    @unique
    class StateType(IntEnum):
        HEATER_STATE_OFF = 0
        HEATER_STATE_STANDBY = 1
        HEATER_STATE_ACTIVE = 2
