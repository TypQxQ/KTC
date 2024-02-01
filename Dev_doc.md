ktc.py has all common functions that need only initialized once.
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
?   last_endstop_query
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
    init_mode:          When to initialize the toolchanger: manual, on_start or on_first_use.
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
    active_tool:    tool object currently active. Defaults to ktc.TOOL_UNKNOWN
    init_order:     
    <!-- active_tool_n:  The toolnumber of the active_tool. -->
    tools:                

    - get_status:
    tools:          list of tool.names in tools
    active_tool:    active_tool.name
    init_mode:      ktc_toolchanger.INIT_MODE attr indicating method of initialization.
    active_tool:    tool object currently active. Defaults to ktc.TOOL_UNKNOWN

    - functions
    engage :        Function to engage the tool lock. Locking the tool
    disengage :     Function to disengage the tool lock. Unlocking the tool.
    change :        Function to change the tool.
    init:           Function to init the changer. 
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



ToDo:
    
    Check what happens when selecting TOOL_UNKNOWN and has no stats...

    ktc_persisting sparar innnan den hämtar nya. Både statistik och active_tool.
    KTC_SAVE_VARIABLES_FILENAME och KTC_SAVE_VARIABLES_DELAY borde laddas från config filen när de finns.

    initialize_tool_lock to use ktc_persistent
    Add option to save instantly (when for example current tool is changed.)

    cmd_KTC_DROPOFF should itterate trough toolchangers recursevly reverse from current_tool.

    initialize_tool_lock move from tool_changer to ktc and do recusevly.

    refactor tool_id to be string and posibly more than one word, check tool_statistics[tool_id] where it asumes a number.

    Move all config initializations that need loaded components from init to _after_loaded.
    Inherits: to tool.
        Add variable _initialized to all configurable.
    parent_tool move to ktc_toolchanger.
    Move shaper to variable array
    Change init_printer_to_last_tool to moment when it should be initialized.
    Remove purge_on_toolchange.

    Prova att sätta ktc_persistent i egen fil och ladda med ktc_persistent.

    Maybe change "printer_is_homed_for_toolchange" function name to toolchanger_ready.
    lazy_home_when_parking to reflect what axis can be used when not homed for each tool?

    Check ktc.handle_ready if can be moved to connect after tools are refactored.

    A tool can have multiple partcooling fans.

    current_tool_id change to active_tool_n?

    Add logic to compare ktc_tool < > on number. None allways being smallest.

# To try to keep terms apart:
Each tool has a id (name) (ktc_tool name) and a nr.



# Select: Tool is selected and loaded for use, be it a physical or a virtual on physical.
    When a child tool is selected it will be active on it's toolchanger and on ktc while the parent only on it's toolchanger.
# Deselect: Tool is deselected and unloaded, be it a physical or a virtual on physical.

# Pickup: Tool is physically picked up and attached to the toolchanger head.
# Droppoff: Tool is physically parked and dropped of the toolchanger head.

Maybe delete?
# ToolLock: Tool is locked in place.
# ToolUnLock: Toollock is disengaged and tool is free.
