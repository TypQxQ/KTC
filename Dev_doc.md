ktc.py has all common functions that need only initialized once.
    TOOL_UNKNOWN :  Special tool indicating stateunknown.
    TOOL_NONE :     Special tool when known state is that a toolchanger has no tool engaged.

ktc_log.py is is initialized once and used for logging, statistics and saving persistant settings like offsets.

ktc_toolchanger.py is initialized for each toolchanger system and can have a parent_tool.
    engage :        Function to engage the tool lock. Locking the tool
    disengage :     Function to disengage the tool lock. Unlocking the tool.
    engaged :       Bool to display state.
    change :        Function to change the tool.

    

ktc_tool.py is initialized for each tool.
    toolchanger Optional alternative. Uses default if not specified.
    Offset is overwritten to persistant variable.



ToDo:
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



# Mount: Tool is selected and loaded for use, be it a physical or a virtual on physical.
    A parent tool is mounted but not selected when a child tool is selected.
# Unmount: Tool is unselected and unloaded, be it a physical or a virtual on physical.

# Pickup: Tool is physically picked up and attached to the toolchanger head.
# Droppoff: Tool is physically parked and dropped of the toolchanger head.

Maybe delete?
# ToolLock: Tool is locked in place.
# ToolUnLock: Toollock is disengaged and tool is free.
