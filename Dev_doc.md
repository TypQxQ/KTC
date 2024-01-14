ktc.py has all common functions that need only initialized once.

ktc_log.py is is initialized once and used for logging, statistics and saving persistant settings like offsets.

ktc_toolchanger.py is initialized for each toolchanger system and can have a parent_tool.

ktc_tool.py is initialized for each tool.
    Offset is overwritten to persistant variable.




ToDo:
    ktc_save_variables sparar innnan den hämtar nya. Både statistik och active_tool.

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


# To try to keep terms apart:
# Mount: Tool is selected and loaded for use, be it a physical or a virtual on physical.
# Unmopunt: Tool is unselected and unloaded, be it a physical or a virtual on physical.
# Pickup: Tool is physically picked up and attached to the toolchanger head.
# Droppoff: Tool is physically parked and dropped of the toolchanger head.
# ToolLock: Toollock is engaged.
# ToolUnLock: Toollock is disengaged.

