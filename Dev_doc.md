# Development doc for KTC

## Setting up enviroment.
It is assumed KTC and Klipper folders are in same directory for typing to work.

## Why so many classes?
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
            4b- Run on next
        3b- Run on next
All obj having ran configure_inherited_params get state=configured.

## SELECT
- If no tool is selected then just select
- If active tool needs deselecting, deselect.
- Check if toolchanger on same level has a tool selected
    - Check if tool needs force deselect.
- Check if toolchanger over this needs deselecting

- If tool on same changer is selected deselect first.
- If active tool is on changer under a sibling
- If active tool is on changer 


## Tool Heaters
When a tool has a heater it checks if a heater obj exists for it in ktc.all_heaters[]
If it exists, then link to it.
If it does not exist, create with own timers. Own object.
When selecting tool, check if heater changes.
- Setting state
    - State is set on tool.extruder.
        - For each heater it sets state if ACTIVE
            - Sets timers and ACTIVE temperatures with offset.
        - For each heater it checks if active on another tool too
            - If STANDBY
                - Set to STANDBY
                - Sets timers and STANDBY temperatures with offset.
            - If OFF
                - just set to OFF


- ktc runs .initialize() on all toolchangers with .init_mode == "ON_START" recursevly.

## Configuration:
### Inheritable
- engage_gcode = "":    Gcode to run at toochanger engage, status from READY to ENGAGED
- disengage_gcode = "": Gcode to run at toochanger disengage, status from ENGAGED to READY
- init_gcode = "":      Gcode to run at toolchanger initialization, from CONFIGURED to READY. If used, it is important tha  t the Gcode changes the state of toolchanger.
- requires_axis_homed = "": Axis in XYZ to be required before tool can be changed, for select
- tool_select_gcode = "":   Gcode to run whan selecting the tool, from ready to SELECTED
- tool_deselect_gcode = "": Oposite of above.
- standby_to_powerdown_time = 0.1:     Seconds to wait when a tool has been deselected, before changing temperature on heater to standy temperature. 0.1 is a tenth of a second.
Use something like  86400 to wait 24h if you want to run indefinitly.
- heater_standby_to_powerdown_delay = 0.2: As above but from active to off.
- init_offset = "":     Toolhead offset. If not set anywhere, will default to "0.0,0.0,0.0". Must be deleted after the value has been read once. Can be put in again to overwrite to other value. Or use the KTC_TOOL_OFFSET_SAVE GCode command.
- force_deselect_when_parent_deselects = True: 
    Does nothing for tools on default toolchanger.
    When deselecting the parent tool, deselect this tool first. Otherwise it will be left
    selected on the toolchanger but not active on ktc.
- parent_must_be_selected_on_deselect = True:
    Does nothing for tools on default toolchanger or tools having force_deselect_when_parent_deselects True.
    Used to speed up multilayer toolchanging when False.
    When deselecting the tool and the parent tool for this tools toolchanger is not selected, select it recursivley for all tools also having this as True, before deselecting.
- heater: A list of heaters and their offset: Example: "heater0:0, preheater:-100.5"
    This configures heater0 and heater1 where preheater will be set to 100 degrees less than the configured temperature for the tool.
    At least heater_name is required if tool has a heater.
    To override inheritance, add it without any values: "heater:"

    When the tool is deselected, the heater goes in standby after "active to standby delay" seconds and then to off after "standby to powerdown time". This is so the heater waits in standby for short toolchanges and shuts down if not used for a while. 
    Speeds up toolchanging while providing security

### NonInheritable
#### KTC (all optional)
- propagate_state = True. When state is changed on a tool then it's toolchanger and the ktc object also changes state accordigly. Use False if you need to control the state manually from GCode.


#### KtcToolchanger
- init_mode = MANUAL:    When is the toolchanger initialized in relation to printer start and homing.
- init_order = INDEPENDENT:   And in relation to the parent tool.
- force_deselect_when_parent_deselects = False
- parent_tool = ""

### KtcTool
tool_number = None:     For use with "T#" gcode commands in by slicer. Defaults to not using.
toolchanger = Default:  Toolchanger this is on, defaults to Default changer.


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
    persistent_state:   Get the persistend state. ex. {'active_tool':'20',}
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
    persistent_state_set: Set the persistend state. ex. {'active_tool':'20',}
    - G-Code commands                                

    

ktc_tool.py is initialized for each tool.
    Name is case sensitive and can contain spaces
    params_*:        Aditional personizable options that can be used by macros.
    toolchanger:     Optional alternative. Uses default if not specified.
    
    Offset is overwritten to persistant variable.



- If final_selected has same changer as active_tool.
    - Deselect active_tool and continue selecting final_selected.
- Else
    - Recursivly check tools from active_tool to ktc if force_deselect_when_parent_change.
        - Deselect those tools while checking.
    - Recursivly check all layers from final_selected to ktc If not selected
        - Add to ordered list?
        - Select all tools in ordered list one by one.

Function get_list_from_tool_traversal_(checking)(start_tool, parameter_to_check, value_to_check, comparer_to_check)

force_deselect_when_parent_deselects
final_selected



# To try to keep terms apart:
Inheritance: tool <- inheriting_tool <- toolchanger <- tool <-  inheriting_tool <- toolchanger <- ktc
- Add T# macros if option (default) is True. Do trough adding a gcodemacro object and rename any existing. Maybe renaming to random number, recursive until not already existing.
Each tool has a id (name) (ktc_tool name) and a nr.

# Select: Tool is selected and loaded for use, be it a physical or a virtual on physical.
    When a child tool is selected it will be active on it's toolchanger and on ktc while the parent only on it's toolchanger.
# Deselect: Tool is deselected and unloaded, be it a physical or a virtual on physical.

## TESTS TO DO
- Check if it selects previous tool for deselecting a tool that needs tool selected.
- If T0 -> T11 -> Deselect_all should: Deselect T11, select T20, deselect T0, deselect T20.

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


- Extruder -> heater_collection (HeaterCollectionWrapper)
- Add context as constants that are inherited. Add a ktc._run_gcode_from_context()
- Combine KTC_SET_STATUS with TOOL and TOOLCHANGER

- Idea for preprocessing to get time of toolchange is using a module that has a opiton named time before ToolChange.
    - CMD in GCODE before waiting for bed to reach temperature.
    - The cmd is searching for T# commands that do toolchange.
    - Parse chunks of rows before T# and see how much time it takes.
        - If takes less than option above then add a chunk, but not more than untill previous T#.
        - If takes more than option above then note row and have T# heat up when gcode file has been run past that command.
        - Check line once a second or twice a second, configurable.
-Maybe using something from:
    https://github.com/Annex-Engineering/klipper_estimator