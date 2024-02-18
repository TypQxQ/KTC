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
    from ...klipper.klippy import configfile, gcode, klippy
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_log, ktc_toolchanger, ktc_tool, ktc, ktc_persisting

# Constants for the restore_axis_on_toolchange variable.
XYZ_TO_INDEX = {"x": 0, "X": 0, "y": 1, "Y": 1, "z": 2, "Z": 2}
INDEX_TO_XYZ = ["X", "Y", "Z"]

# Value of Unknown and None tools.
TOOL_NUMBERLESS_N = -3
TOOL_UNKNOWN_N = -2
TOOL_NONE_N = -1

DEFAULT_HEATER_ACTIVE_TO_POWERDOWN_DELAY = 0.2
DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY = 0.1

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
        self._state = self.StateType.NOT_CONFIGURED

        self.force_deselect_when_parent_deselects: bool = config.getboolean(
            "force_deselect_when_parent_deselects", True)  # type: ignore

        # If this is a empty object then don't load the config.
        if config is None:
            return

        self.printer : 'klippy.Printer' = config.get_printer()
        self.reactor: 'klippy.reactor.Reactor' = self.printer.get_reactor()
        self.gcode = typing.cast('gcode.GCodeDispatch', self.printer.lookup_object("gcode"))
        self.params = self.get_params_dict_from_config(config)
        self.log: 'ktc_log.KtcLog' = None # type: ignore # We are loading it later.
        self._ktc: 'ktc.Ktc' = None # type: ignore # We are loading it later.

        self.state = self.StateType.NOT_CONFIGURED
        self.offset: dict[float, float, float] = None   # type: ignore

        # Get inheritable parameters from the config.
        # Empty strings are overwritten by the parent object in configure_inherited_params.
        self._engage_gcode = config.get("engage_gcode", "")  # type: ignore
        self._disengage_gcode = config.get("disengage_gcode", "")  # type: ignore
        self._init_gcode = config.get("init_gcode", "")  # type: ignore
        self.requires_axis_homed = self.config.get("requires_axis_homed", "")   # type: ignore
        self._tool_select_gcode = config.get("tool_select_gcode", "")     # type: ignore
        self._tool_deselect_gcode = config.get("tool_deselect_gcode", "") # type: ignore
        self.heater_active_to_standby_delay = self.config.getfloat(
            "heater_active_to_standby_delay", None, 0.1)    # type: ignore
        self.heater_active_to_powerdown_delay = self.config.getfloat(
            "heater_active_to_powerdown_delay", None, 0.1)  # type: ignore

        # Get initial values from the config.
        self._initiating_config = {}
        # Offset as a list of 3 floats.
        init: str = ""
        for init in config.get_prefix_options("init_"):
            init = init.strip().lower()
            if init == "init_offset":
                try:
                    v : str = config.get(init)
                    # t = typing.cast(str,self.config.get("init_offset", None))  # type: ignore
                    if v is not None or v != "":
                        vl = [float(x) for x in v.split(",")]
                        if len(vl) != 3:
                            raise ValueError("Offset must be a list of 3 floats.")
                        self._initiating_config['offset'] = vl
                except Exception as e:
                    raise self.config.error(f"Invalid offset for {self.config.get_name()}: {e}")


    def configure_inherited_params(self):
        '''Load inherited parameters from instances that this instance inherits from.
        This is called after all instances are loaded.'''
        # Ref. to the ktc_persisting object. Loaded by ktc_log.
        self._ktc_persistent: 'ktc_persisting.KtcPersisting' = (  # type: ignore # pylint: disable=attribute-defined-outside-init
            self.printer.lookup_object("ktc_persisting")
        )

        # Check if any initiating values are set.
        if len(self._initiating_config) > 0:
            if "offset" in self._initiating_config:
                self.persistent_state = {"offset": self._initiating_config["offset"]}
                raise self.config.error(f"Offset for {self.config.get_name()} successfully aved as"
                    + f" {self._initiating_config['offset']}."
                    +" Remove the offset from the config and restart Klipper to continue.")

        # Check for circular inheritance.
        if self.state >= self.StateType.CONFIGURED:
            return
        elif self.state == self.StateType.CONFIGURING:
            raise ValueError("Can't configure inherited parameters while already configuring "
                             + self.config.get_name())
        self.state = self.StateType.CONFIGURING

        # Ref. to ktc objects.
        self._ktc = typing.cast('ktc.Ktc', self.printer.lookup_object("ktc"))
        self.log = typing.cast('ktc_log.KtcLog', self.printer.lookup_object(
            self.config, "ktc_log"))  # Load the log object.

        # Get Offset from persistent storage
        self.offset = self.persistent_state.get("offset", None)

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

        # If this is the topmost parent.
        if parent == self:
            if self.heater_active_to_powerdown_delay is None:
                self.heater_active_to_powerdown_delay = DEFAULT_HEATER_ACTIVE_TO_POWERDOWN_DELAY
                self.heater_active_to_standby_delay = DEFAULT_HEATER_ACTIVE_TO_STANDBY_DELAY
            if self.offset is None:
                self.offset = [0, 0, 0]

        params_to_inherit = ["_engage_gcode", "_disengage_gcode", "_init_gcode", "offset",
                             "requires_axis_homed", "_tool_select_gcode", "_tool_deselect_gcode",
                             "heater_active_to_standby_delay", "heater_active_to_powerdown_delay",
                             "force_deselect_when_parent_deselects"]
        # Set the parameters from the parent object if they are not set.
        for v in params_to_inherit:
            if getattr(self, v) is None:
                setattr(self, v, getattr(parent, v))

        for v in parent.params: # type: ignore
            if v not in self.params:
                self.params[v] = parent.params[v]   # type: ignore

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
                # List of Integers:
                if value.replace("-", "").replace(" ", "").replace(",", "").isdigit():
                    result[option] = [int(x) for x in value.split(",")]
                # List of Floats:
                elif value.replace(".", "").replace("-", "").replace(
                    " ", "").replace(",", "").isdigit():
                    result[option] = [float(x) for x in value.split(",")]
                # Boolean:
                elif value.lower().strip() in ["true", "false"]:
                    result[option] = config.getboolean(option)
                # Integer:
                elif value.replace("-", "").replace(" ", "").isdigit():
                    result[option] = config.getint(option)
                # Float:
                elif value.replace(".", "").replace("-", "").replace(" ", "").isdigit():
                    result[option] = config.getfloat(option)
                # String:
                elif value.startswith('"') and value.endswith('"'):
                    result[option] = ast.literal_eval(value)
                # String:
                elif value.startswith("'") and value.endswith("'"):
                    result[option] = ast.literal_eval(value)
                # Check if it is a valid String:
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

    @property
    def persistent_state(self) -> dict:
        '''Return the persistent state from file.
        Is initialized inside handle_connect.'''
        if self._ktc_persistent is None:
            self._ktc_persistent: 'ktc_persisting.KtcPersisting' = (  # type: ignore # pylint: disable=attribute-defined-outside-init
                self.printer.lookup_object("ktc_persisting")
            )
        if isinstance(self, KtcBaseToolClass):
            c = "ktc_tool_" + self.name.lower()
        elif isinstance(self, KtcBaseChangerClass):
            c = "ktc_toolchanger_" + self.name.lower()
        elif isinstance(self, KtcBaseClass):
            c = "ktc"
        else:
            raise ValueError(f"Can't get persistent state for object: {type(self)}")

        v: dict = self._ktc_persistent.content.get("State", {})
        return v.get(c, {})

    @persistent_state.setter
    def persistent_state(self, value):
        if self._ktc_persistent is None:
            self._ktc_persistent: 'ktc_persisting.KtcPersisting' = (  # type: ignore # pylint: disable=attribute-defined-outside-init
                self.printer.lookup_object("ktc_persisting")
            )

        if isinstance(self, KtcBaseToolClass):
            c = "ktc_tool_" + self.name.lower()
        elif isinstance(self, KtcBaseChangerClass):
            c = "ktc_toolchanger_" + self.name.lower()
        elif isinstance(self, KtcBaseClass):
            c = "ktc"
        else:
            raise ValueError(f"Can't set persistent state for object: {type(self)}")

        self._ktc_persistent.save_variable(c, str(value), "State", True)

class KtcBaseChangerClass(KtcBaseClass):
    '''Base class for toolchangers. Contains common methods and properties.'''
    def __init__(self, config: 'configfile.ConfigWrapper'):
        super().__init__(config)
        self.name: str = str(config.get_name()).split(" ", 1)[1]
        # The parent tool of the toolchanger if it is not default changer.
        self.parent_tool: 'ktc_tool.KtcTool' = None # type: ignore
        self.selected_tool = None
        self.tools: dict[str, 'ktc_tool.KtcTool'] = {}
        self._engage_gcode_template: klippy_gcode_macro.GCodeMacro = None # type: ignore
        self._disengage_gcode_template: klippy_gcode_macro.GCodeMacro = None # type: ignore

class KtcBaseToolClass(KtcBaseClass):
    '''Base class for tools. Contains common methods and properties.'''
    def __init__(self, config: typing.Optional['configfile.ConfigWrapper'] = None,
                 name: str = "", number: int = TOOL_NUMBERLESS_N):
        super().__init__(config)

        self.name = name        # Override the name in case it is supplied.
        self.number = number
        # Is overridden by the tool object.
        self._toolchanger: 'ktc_toolchanger.KtcToolchanger' = None   # type: ignore
        self.toolchanger = self._toolchanger
        # TODO: Change to array of fans
        self.fan = None
        self.extruder = None
        # TODO: Change to heater object
        self.heater = None
        # 0 = off, 1 = standby temperature, 2 = active temperature.
        self.heater_state = 0
        # Timer to set temperature to standby temperature
        # after heater_active_to_standby_delay seconds. Set if this tool has an extruder.
        self.timer_heater_active_to_standby_delay = None
        # Timer to set temperature to 0 after heater_active_to_powerdown_delay seconds.
        # Set if this tool has an extruder.
        self.timer_heater_active_to_powerdown_delay = None
        # Temperature to set when in active mode.
        # Requred on Physical and virtual tool if any has extruder.
        self.heater_active_temp = 0
        # Temperature to set when in standby mode.
        # Requred on Physical and virtual tool if any has extruder.
        self.heater_standby_temp = 0
        # Time in seconds from being parked to setting temperature to
        # standby the temperature above. Use 0.1 to change imediatley
        # to standby temperature. Requred on Physical tool
        # self.heater_active_to_standby_delay = 0.1
        # Time in seconds from being parked to setting temperature to 0.
        # Use something like 86400 to wait 24h if you want to disable.
        # Requred on Physical tool.
        # self.heater_active_to_powerdown_delay = 600

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
