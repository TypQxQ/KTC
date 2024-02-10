# Development doc for KTC

## Setting up enviroment.
This is how I set it up and made all type checkings work.
The standard dev enviroment is using VSCode and working in the KTC directory in the home of the Pi youd for printing.
The git should point to the repository used for development.
Add a symbolic link to Klipper with the folowing command, asuming files are as below:
> ln -s ~/klipper/klippy/ ~/KTC/extensions/klippy
Add a .gitignore file inside the working directory, having this line:
> /extensions/klippy/
That's it.

> Using inherited classes from Ktc code can use the BaseClass for typechecks and not cross import.
> This minimizes risk for circular imports.
>
> Each class can import ktc and ktc can not import them inside the init().
> The classes should not import or load eachother inside the init()

## Load paths
### Minimum configuration load path:
Minimum configuration would be one tool declared.

- The tool loads ktc in it's init.
- ktc loads ktc_persistent at init.
- ktc_persistent loads log at init.
- ktc_persistent loads persistent data from file at init.
- ktc_config_default_toolchanger adds default_toolchanger
- ktc_config_default_toolchanger adds the toolchanger to ktc.toolchangers
- ktc._config_tools adds the tool(s) to ktc.default_toolchanger.tools
- ktc._config_tools adds the tool(s) to ktc.all_toolls

1- (Run configure_inherited_params recursevly)
    1- Run on ktc
        2- Run on default_toolchanger
        3- Make a dictionary of tools that are toolchanger parents.
        3- Run on first tool of default_toolchanger
            4- Run on first toolchanger having the above tool as parent from (3)
All obj having ran configure_inherited_params get configured = true.
If "inherits from" is a tool/changer that has not configured == true and not the same toolchanger (for tools) then error: "inherit from must point to obj on same or previous level."


- ktc runs .initialize() on all toolchangers with .init_mode == "ON_START" recursevly.


## Base clases defined in ktc.py

> ### KtcBaseClass:
> The base all Ktc Classes inherits.
> - functions:
>   - __init__:   Optional config. If config is not None, Load self.config, self.printer and self.gcode reference.
>   - configure_inherited_params:     Loads inherited parameters from instances that this instance inherits from.
> - variables:
>   - self.config:
>   - self.name:
>   - self.printer:
>   - self.gcode:
>   - self.reactor:

> ### KtcBaseChangerClass(KtcBaseClass)
> The base all Ktc_Toolchanger inherits.
> - functions:
>   - __init__: config required.
>   - configure_inherited_params:     Loads inherited parameters from instances that this instance inherits from.
> - variables:
>   - self.parent_tool:     None if main toolchanger. Otherwise the tool this tool uses
>   - self.tools{}:         List of all tools on the toolchanger.
>   - self.active_tool:     Selected Tool.

> ### KtcBaseToolClass(KtcBaseClass)
> The base all Ktc_Toolchanger inherits.
> - functions:
>   - __init__: config required.
>   - configure_inherited_params:     Loads inherited parameters from instances that this instance inherits from.
> - variables:
>   - self.parent_tool:     None if main toolchanger. Otherwise the tool this tool uses
>   - self.tools{}:         List of all tools on the toolchanger.
>   - self.active_tool:     Selected Tool.



> ### KtcConstantsClass:
> Class to include CONSTANTS. This are instances of KtcBaseToolClass so they must be inherited paralel.
> - CONSTANTS:
>   - TOOL_NUMBERLESS_N = TOOL_NUMBERLESS_N
>   - TOOL_NONE_N: -1
>   - TOOL_UNKNOWN_N: -2
>   - TOOL_UNKNOWN: Instance KtcBaseToolClass: name="tool_unknown", number=TOOL_UNKNOWN_N
>   - TOOL_NONE = Instance KtcBaseToolClass:name="tool_none", number=TOOL_NONE_N


## Python files:


> ###class INIT_MODE(str, Enum):
>   Constants for the initialization mode of the toolchanger.
>   Inherits from str so it can be JSON serializable.
>   Not using StrEnum as it was first introduced in Python 3.11.
>   Enum was introduced in Python 3.4.



ktc.py has all common methods that need only initialized once.
    -constants
    TOOL_UNKNOWN :  Special tool indicating stateunknown.
    TOOL_NONE :     Special tool when known state is that a toolchanger has no tool engaged.

    - configurable    
    global_offset:  X,Y,Z.
    params_*:   Aditional personizable options that can be used by macros.
    default_toolchanger:Toolchanger object 
    params_*:           Aditional personizable options that can be used by macros.

    -params
    tools:              dict[tool_name:tool]
    tools_by_number:    dict[int, ktc_tool.KtcTool]
    self.toolchangers:  dict[str, ktc_toolchanger.KtcToolchanger]

    -get_status
    global_offset:      X,Y,Z
    active_tool:
?   active_tool_n:
    saved_fan_speed:
?   restore_axis_on_toolchange:
?   saved_position
    tools:              list of tool names
    TOOL_NONE:          TOOL_NONE.name
    TOOL_UNKNOWN:       TOOL_UNKNOWN.name
    **self.params


ktc_log.py is is initialized once and used for logging, statistics and saving persistant settings like offsets.


ktc_toolchanger.py is initialized for each toolchanger system and can have a parent_tool.
    - configurable
    Name:       is case sensitive and can contain spaces
    params_*:           Aditional personizable options that can be used by macros.
    disengage_gcode:    G-Code run when disengaging 
    init_mode:          When to initialize the toolchanger: manual, on_start, on_first_use, homing_start, homing_end
                        Can also be set to manual and called manualy inside the homing file for example.
    init_order:         Defaults to independent Required if not default, not usable on default.
                        Defaults to manual.
    parent_tool:    Required for changers other than the default.
    init_gcode:         G-code running on initialization. active_tool is loaded before running this
    engage_gcode:       G-code running when engaging tool-lock.
    disengage_gcode:    G-code running when disengaging tool-lock.

    -params
    tools:              dict[tool_name:tool]
    persistent_state:   Get or Set the persistend state. ex. ['active_tool':'20']
    state :         ktc_toolchanger.STATE attr indicating current state.
    init_mode:      ktc_toolchanger.INIT_MODE attr indicating method of initialization.
    active_tool:    tool object currently active. Defaults to TOOL_UNKNOWN
    init_order:     
    <!-- active_tool_n:  The toolnumber of the active_tool. -->
    tools:                

    - get_status:
    tools:          list of tool.names in tools
    active_tool:    active_tool.name
    init_mode:      ktc_toolchanger.INIT_MODE attr indicating method of initialization.
    active_tool:    tool object currently active. Defaults to TOOL_UNKNOWN

    - methods
    engage :        method to engage the tool lock. Locking the tool
    disengage :     method to disengage the tool lock. Unlocking the tool.
    change :        method to change the tool.
    init:           Method to init the changer. 
                        Loads persisted active_tool.
                        Then checks if a init_gcode has been specified.
                            If no init_gcode is specified then it will set state to STATE.INITIALIZED.
                            If init_gcode is specified, it will run it.
                                Atleast myself.state should be set for example to STATE.INITIALIZED.
                                Can access this context: 
                                    myself: The ktc_toolchanger being initialized.
                                    ktc:    The ktc object.
                                    STATE:  Constants for setting and comparing myself.state
                                    INIT_MODE: Constants for setting and comparing myself.init_mode

    - G-Code commands                                

    

ktc_tool.py is initialized for each tool.
    Name is case sensitive and can contain spaces
    params_*:        Aditional personizable options that can be used by macros.
    toolchanger:     Optional alternative. Uses default if not specified.
    
    Offset is overwritten to persistant variable.





# To try to keep terms apart:
Inheritance: tool <- inheriting_tool <- toolchanger <- tool <-  inheriting_tool <- toolchanger <- ktc

Each tool has a id (name) (ktc_tool name) and a nr.

# Select: Tool is selected and loaded for use, be it a physical or a virtual on physical.
    When a child tool is selected it will be active on it's toolchanger and on ktc while the parent only on it's toolchanger.
# Deselect: Tool is deselected and unloaded, be it a physical or a virtual on physical.

# Pickup: Tool is physically picked up and attached to the toolchanger head.
# Droppoff: Tool is physically parked and dropped of the toolchanger head.

Maybe delete?
# ToolLock: Tool is locked in place.
# ToolUnLock: Toollock is disengaged and tool is free.



class ktc_MeanLayerTime:
    def __init__(self, printer):
        # Run before toolchange to set time like in StandbyToolTimer.
        # Save time for last 5 (except for first) layers
        # Provide a mean layer time.
        # Have Tool have a min and max 2standby time.
        # If mean time for 3 layers is higher than max, then set min time.
        # Reset time if layer time is higher than max time. Pause or anything else that has happened.
        # Method to reset layer times.
        pass
