# Macros used by KTC have this object states accesible
## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) **KTC** - Is always accessible
  - `global_offset` - Global offset.
  - `active_tool` - Name of the active tool. Special names are: 'tool_unknown' and 'tool_none'. 
  - `active_tool_n` - Tool Number if any of the active tool. Special numbers are: -2 for 'tool_unknown' and -1 for 'tool_none'. 
  - `saved_fan_speed` - Speed saved at each fanspeedchange to be recovered at Toolchange.
  - `state` - State of KTC, one of STATE_TYPE.
  - `tools` - List of all tool names.
  - `toolchangers` - List of all toolchangers.
  - `params_available` - List of available custom parameters as specified in the configuration file.
  - `params_*` - parameter in the above list.

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) **Tool** - The tool calling this macro is referenced as `myself` in `tool_select_gcode:` and `tool_deselect_gcode:`. One can write `{myself.name}` which would return `3` for a tool named so.
  - `name` - Tool name. 0, 1, 2, etc.
  - `number` - Tool number.
  - `state` - State of the tool, one of STATE_TYPE.
  - `toolchanger` - Name of toolchanger this tool is on.
  - `heater_names` - List of heaters this tool has.
  - `heater_state` - Current state for the tools heaters. 0 = off, 1 = standby temperature, 2 = active temperature.
  - `fans` - List of fans this tool has.
  - `offset` - Tool offset as a list of [X,Y,Z]. Global offset is added if set.
  - `heater_active_temp` - Temperature to set when in active mode.
  - `heater_standby_temp` - Temperature to set when in standby mode.
  - `heater_active_to_standby_delay` - Time in seconds from setting temperature to standby that the temperature actualy changes. Use 0.1 to change imediatley to standby temperature.
  - `standby_to_powerdown_delay` - Time in seconds from being parked to setting temperature to 0. Use something like 86400 to wait 24h if you want to disable. Requred on Physical tool.
  - `params_available` - List of available custom parameters as specified in the configuration file.
  - `params_*` - parameter in the above list.

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) **Toolchanger** - The toolchanger calling this macro is referenced as `myself` in `init_gcode:`, `engage_gcode:` and `disengage_gcode:`. One can write `{myself.name}` which would return `Jubilee` for a toolchanger named so.
  - `name` - Tool name. 0, 1, 2, etc.
  - `selected_tool` - Name of the selected tool. Special names are: 'tool_unknown' and 'tool_none'. 
  - `selected_tool_n` - Tool Number if any of the selected tool. Special numbers are: -2 for 'tool_unknown' and -1 for 'tool_none'. 
  - `init_mode` - When this toolchanger is initialized: 'manual', 'on_start' or 'on_first_use'
  - `state` - State of the toolchanger, one of STATE_TYPE.
  - `tools` - List of all tool names attached to this toolchanger.
  - `params_available` - List of available custom parameters as specified in the configuration file.
  - `params_*` - parameter in the above list.

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) **STATE_TYPE** Constant valuse that the state of  ktc, a tool or toolchanger can have.
States can be set like: `KTC_SET_STATE TOOLCHANGER={myself.name} STATE=READY`
  - `ERROR` - Toolchanger or tool is in error state.
  - `NOT_CONFIGURED` - Toolchanger or tool is not configured.
  - `CONFIGURING` - Toolchanger or tool is configuring.
  - `CONFIGURED` - Toolchanger or tool is configured but not initialized.
  - `UNINITIALIZED` - Toolchanger or tool is uninitialized.
  - `INITIALIZING` - Toolchanger or tool is initializing.
  - `INITIALIZED` - Toolchanger or tool is initialized but not ready.
  - `READY` - Toolchanger or tool is ready to be used.
  - `CHANGING` - Toolchanger or tool is changing tool.
  - `ENGAGING` - Toolchanger is engaging.
  - `SELECTING` - Tool is selecting.
  - `DISENGAGING` - Toolchanger or tool is disengaging.
  - `DESELECTING` - Tool is deselecting.
  - `ENGAGED` - Tollchanger or tool is engaged.
  - `SELECTED` - Tool is selected.
  - `ACTIVE` - Tool is active as main engaged tool for ktc.
