ktc.py has all common functions that need only initialized once.

ktc_log.py is is initialized once and used for logging, statistics and saving persistant settings like offsets.

ktc_toolchanger.py is initialized for each toolchanger system and can have a parent_tool.

ktc_tool.py is initialized for each tool.
    Offset is overwritten to persistant variable.




ToDo:
    Move all config initializations that need loaded components from init to _after_loaded.
    Remove ToolGroup.
    Inherits: to tool.
        Add variable _initialized to all configurable.
    parent_tool move to ktc_toolchanger.
    Move shaper to variable array



# To try to keep terms apart:
# Mount: Tool is selected and loaded for use, be it a physical or a virtual on physical.
# Unmopunt: Tool is unselected and unloaded, be it a physical or a virtual on physical.
# Pickup: Tool is physically picked up and attached to the toolchanger head.
# Droppoff: Tool is physically parked and dropped of the toolchanger head.
# ToolLock: Toollock is engaged.
# ToolUnLock: Toollock is disengaged.

