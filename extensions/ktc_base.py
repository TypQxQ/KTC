# KTC - Klipper Tool Changer code (v.2)
# Base classes and types for KTC to inherit from.
# This file is part of the KTC extension for the Klipper firmware.
# This should not import any other KTC module but can be imported by any KTC module.
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
import ast, typing
from enum import IntEnum, unique, Enum

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from .klippy import configfile, gcode
    from .klippy import klippy
    from . import ktc_log, ktc_toolchanger, ktc_tool, ktc

# Constants for the restore_axis_on_toolchange variable.
XYZ_TO_INDEX = {"x": 0, "X": 0, "y": 1, "Y": 1, "z": 2, "Z": 2}
INDEX_TO_XYZ = ["X", "Y", "Z"]

# Value of Unknown and None tools.
TOOL_NUMBERLESS_N = -3
TOOL_UNKNOWN_N = -2
TOOL_NONE_N = -1

class KtcConfigurableEnum(Enum):
    @classmethod
    def get_value_from_configuration(cls, config: 'configfile.ConfigWrapper', value_name: str,
                                     default_name: typing.Optional[str] = None):
        val = typing.cast(str, config.get(value_name, default_name))  # type: ignore
        val = val.strip().upper()
        if val == "":
            raise ValueError(f"Value {value_name} not found in configuration.")
        if val not in cls.list_valid_values():
            raise ValueError(f"Value {val} not valid for {value_name}"
                                +f" in configuration for {config.get_name()}."
                + f"Valid values are: {cls.list_valid_values()}")
        return cls[val]

    @classmethod
    def list_valid_values(cls):
        return [str(name) for name in cls.__members__]

    def __str__(self):
        return f"'{self.name}'"

class KtcBaseClass:
    """Base class for KTC. Contains common methods and properties."""
    def __init__(self, config: typing.Optional['configfile.ConfigWrapper'] = None):
        self.config = typing.cast('configfile.ConfigWrapper', config)
        self.name: str = ""

        # Can contain "X", "Y", "Z" or a combination.
        self.requires_axis_homed: str = ""
        self.log = None # type: ignore # We are loading it later.
        self._state = self.StateType.NOT_CONFIGURED

        # If this is a empty object then don't load the config.
        if config is None:
            return

        self.printer : 'klippy.Printer' = config.get_printer()
        self.reactor: 'klippy.reactor.Reactor' = self.printer.get_reactor()
        self.gcode = typing.cast('gcode.GCodeDispatch', self.printer.lookup_object("gcode"))
        self.params = self.get_params_dict_from_config(config)
        self.log = None # type: ignore # We are loading it later.
        self._ktc = None # type: ignore # We are loading it later.

        # Get inheritable parameters from the config.
        self._engage_gcode = config.get("engage_gcode", "")  # type: ignore
        self._disengage_gcode = config.get("disengage_gcode", "")  # type: ignore
        self._init_gcode = config.get("init_gcode", "")  # type: ignore
        self.requires_axis_homed = self.config.get("requires_axis_homed", "")   # type: ignore
        self._tool_select_gcode = config.get("tool_select_gcode", "")     # type: ignore
        self._tool_deselect_gcode = config.get("tool_deselect_gcode", "") # type: ignore

    def configure_inherited_params(self):
        '''Load inherited parameters from instances that this instance inherits from.'''
        if self.state >= self.StateType.CONFIGURED:
            return
        elif self.state == self.StateType.CONFIGURING:
            raise ValueError("Can't configure inherited parameters while already configuring "
                             + self.config.get_name())
        self.state = self.StateType.CONFIGURING

        self._ktc = typing.cast('ktc.Ktc', self.printer.lookup_object("ktc"))
        self.log = typing.cast('ktc_log.KtcLog', self.printer.load_object(
            self.config, "ktc_log"))  # Load the log object.

        #  Set the parent object
        if isinstance(self, KtcBaseToolClass):
            parent = self.toolchanger
        elif isinstance(self, KtcBaseChangerClass):
            parent = self.parent_tool
            if parent is None:
                parent = typing.cast('ktc.Ktc', self.printer.lookup_object("ktc"))
        elif isinstance(self, KtcBaseClass):
            parent = self
        else:
            raise ValueError("Can't configure inherited parameters for object: " + str(type(self)))

        if self._engage_gcode == "":
            self._engage_gcode = parent._engage_gcode                   # type: ignore # pylint: disable=protected-access
        if self._disengage_gcode == "":
            self._disengage_gcode = parent._disengage_gcode             # type: ignore # pylint: disable=protected-access
        if self._init_gcode == "":
            self._init_gcode = parent._init_gcode                       # type: ignore # pylint: disable=protected-access
        if self.requires_axis_homed == "":
            self.requires_axis_homed = parent.requires_axis_homed       # type: ignore # pylint: disable=protected-access
        if self._tool_select_gcode == "":
            self._tool_select_gcode = parent._tool_select_gcode         # type: ignore # pylint: disable=protected-access
        if self._tool_deselect_gcode == "":
            self._tool_deselect_gcode = parent._tool_deselect_gcode     # type: ignore # pylint: disable=protected-access

    @staticmethod
    def get_params_dict_from_config(config: 'configfile.ConfigWrapper'):
        """Get a dict of atributes starting with params_ from the config."""
        result = {}

        if config is None or not config.has_section(config.get_name()):
            return result

        # Get all options that start with "params_" and add them to the result dict.
        for option in config.get_prefix_options("params_"):
            try:
                value : str = config.get(option)
                if value.lower() in ["true", "false"]:
                    result[option] = config.getboolean(option)
                elif value.isdigit():
                    result[option] = config.getint(option)
                elif value.replace(".", "").isdigit():
                    result[option] = config.getfloat(option)
                elif value.startswith('"') and value.endswith('"'):
                    result[option] = ast.literal_eval(value)
                elif value.startswith("'") and value.endswith("'"):
                    result[option] = ast.literal_eval(value)
                else:
                    result[option] = ast.literal_eval('"' + value + '"')
            except ValueError as e:
                raise config.error(
                    "Option '%s' in section '%s' is not a valid literal: %s."
                    % (option, config.get_name(), e)
                )
        return result

    @unique
    class StateType(IntEnum, KtcConfigurableEnum):
        """Constants for the status of the toolchanger.
        Using dataclasses to allow for easy traversal of the values."""
        ERROR= -50              # Toolchanger or tool is in error state.
        NOT_CONFIGURED = -12    # Toolchanger or tool is not configured.
        CONFIGURING = -11       # Toolchanger or tool is configuring.
        CONFIGURED = -10        # Toolchanger or tool is configured but not initialized.
        UNINITIALIZED = -2      # Toolchanger or tool is uninitialized.
        INITIALIZING = -1       # Toolchanger or tool is initializing.
        INITIALIZED = 0         # Toolchanger or tool is initialized but not ready.
        READY = 1               # Toolchanger or tool is ready to be used.
        CHANGING = 2            # Toolchanger or tool is changing tool.
        ENGAGING = 3            # Toolchanger or tool is engaging.
        DISENGAGING = 4         # Toolchanger or tool is disengaging.
        ENGAGED = 5             # Tollchanger or tool is engaged.
        ACTIVE = 10             # Tool is active as main engaged tool for ktc.

        @classmethod
        def list_valid_values(cls):
            return [name for name, _ in cls.__members__]

        def __str__(self):
            return f'{self.name}'

    @property
    def state(self):
        return self._state
    @state.setter
    def state(self, value):
        self._state = self.StateType[str(value).upper()]

class KtcBaseChangerClass(KtcBaseClass):
    '''Base class for toolchangers. Contains common methods and properties.'''
    def __init__(self, config: 'configfile.ConfigWrapper'):
        super().__init__(config)
        self.name: str = str(config.get_name()).split(" ", 1)[1]
        self.parent_tool = None # The parent tool of the toolchanger if it is not default changer.
        # TODO: Change to selected_tool
        self.selected_tool = None
        self.tools: dict[str, 'ktc_tool.KtcTool'] = {}

class KtcBaseToolClass(KtcBaseClass):
    '''Base class for tools. Contains common methods and properties.'''
    def __init__(self, config: typing.Optional['configfile.ConfigWrapper'] = None,
                 name: str = "", number: int = TOOL_NUMBERLESS_N):
        super().__init__(config)

        self.name = name        # Override the name in case it is supplied.
        self.number = number
        self.toolchanger: typing.Optional['ktc_toolchanger.KtcToolchanger'] = None
        # TODO: Change to array of fans
        self.fan = None
        self.extruder = None
        self.heater = None
        # 0 = off, 1 = standby temperature, 2 = active temperature.
        self.heater_state = 0
        # Timer to set temperature to standby temperature
        # after idle_to_standby_time seconds. Set if this tool has an extruder.
        self.timer_idle_to_standby = None
        # Timer to set temperature to 0 after idle_to_powerdown_time seconds.
        # Set if this tool has an extruder.
        self.timer_idle_to_powerdown = None
        # Temperature to set when in active mode. Placeholder.
        # Requred on Physical and virtual tool if any has extruder.
        self.heater_active_temp = 0
        # Temperature to set when in standby mode.  Placeholder.
        # Requred on Physical and virtual tool if any has extruder.
        self.heater_standby_temp = 0
        # Time in seconds from being parked to setting temperature to
        # standby the temperature above. Use 0.1 to change imediatley
        # to standby temperature. Requred on Physical tool
        self.idle_to_standby_time = 0.1
        # Time in seconds from being parked to setting temperature to 0.
        # Use something like 86400 to wait 24h if you want to disable.
        # Requred on Physical tool.
        self.idle_to_powerdown_time = 600
        self.offset = [0, 0, 0]

    def set_offset(self, **kwargs):
        '''Set the offset of the tool.'''

class KtcConstantsClass:
    '''Constants for KTC. These are to be inherited by other classes.'''
    # Value of Unknown and None tools are set in module scope.
    TOOL_NUMBERLESS_N = TOOL_NUMBERLESS_N
    TOOL_UNKNOWN_N = TOOL_UNKNOWN_N
    TOOL_NONE_N = TOOL_NONE_N
    TOOL_UNKNOWN = typing.cast(
        'ktc_tool.KtcTool',
        KtcBaseToolClass(name="tool_unknown", number=TOOL_UNKNOWN_N))
    TOOL_NONE = typing.cast(
        'ktc_tool.KtcTool',
        KtcBaseToolClass(name="tool_none", number=TOOL_NONE_N))
    TOOL_NONE.state = TOOL_UNKNOWN.state = KtcBaseClass.StateType.CONFIGURED
