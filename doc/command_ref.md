# KTC - Command Reference

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Basic Toolchanger functionality
  | Command | Description | 
  | ------- | ----------- |
  | `KTC_TOOLCHANGER_ENGAGE` | Engage or lock the tool. |
  | `KTC_TOOLCHANGER_DISENGAGE` | Disengage or unlock from the tool. |
  | `KTC_T<index>` | Select the tool with number. |
  | `KTC_DESELECT_ALL` | Recursivley deselects all tools. |
  | `KTC_TOOL_SET_TEMPERATURE [TOOL=<name> \| T=<index>] [ACTV_TMP=<temperature>] [STDB_TMP=<temperature>] [CHNG_STATE=<0\|1\|2>\|<OFF\|STANDBY\|ACTIVE>] [STDB_TIMEOUT=<seconds>] [SHTDWN_TIMEOUT=<seconds>]` | Change temperature settings for active or specified tool. |
  | `KTC_SET_AND_SAVE_PARTFAN_SPEED [TOOL=<name> \| T=<index>] [S=<value>]` | Set the part cooling fan speed for the active or specified tool. If no speed value is specified, the fan will run at full speed by default. |
  | `KTC_TEMPERATURE_WAIT_WITH_TOLERANCE [TOOL=<name> \| T=<index>] [TOLERANCE=<0-9>]` | Waits for the specified tool or heater's temperature to reach its target temperature with a set tolerance. The default tolerance is 1°C. If no tool or heater is specified, it waits for all temperatures to reach their target temperatures. |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Offset commands
  | Command | Description | 
  | ------- | ----------- |
  | `KTC_GLOBAL_OFFSET_SAVE [ [[X=<pos>] [Y=<pos>] [Z=<pos>]] \| [[X_ADJUST=<adjust>] [Y_ADJUST=<adjust>] [Z_ADJUST=<adjust>]] ]` | Set a global position offset that is applied to all tool offsets. Reports the current global offset if no parameter is provided. |
  | `KTC_TOOL_OFFSET_SAVE [TOOL=<name> \| T=<index>] [ [[X=<pos>] [Y=<pos>] [Z=<pos>]] \| [[X_ADJUST=<adjust>] [Y_ADJUST=<adjust>] [Z_ADJUST=<adjust>]] ]` | Save the positional offset of an individual tool to file so it can be used later. Reports the tool offset without global offsets if no offset parameter is provided. |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Tool number mapping commands
  | Command | Description | 
  | ------- | ----------- |
  | `KTC_TOOLS_DISPLAY` | Report the current mapping of tools to other KTC tools. |
  | `KTC_TOOL_MAP_NR TOOL=<name> SET=<index>` | Map a tool to a index. Index must not be already in use. |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Advanced commands, rarely used
  | Command | Description |
  | ------- | ----------- |
  | `KTC_SET_ACTIVE_TOOL [TOOL=<name> \| T=<index>]`|  Set the KTC active tool manually to the specified. For overwriding when loading a tool manually. |
  | `KTC_SET_STATE [TOOL=<name> \| T=<index>] [STATE=<ERROR \| NOT_CONFIGURED \| CONFIGURING \| CONFIGURED \| UNINITIALIZED \| INITIALIZING \| INITIALIZED \| READY \| CHANGING \| ENGAGING \| SELECTING \| DISENGAGING \| DESELECTING \| ENGAGED \| SELECTED \| ACTIVE>]` | Sets the state of the specified tool, toolchanger or the KTC itself. Without state provided, it reports the currently active state. |
  | `KTC_TOOLCHANGER_SET_SELECTED_TOOL TOOL=<name> \| T=<index> [TOOLCHANGER=<value>]` | Manually sets the selected tool of a specified or the default toolchanger. |
  | `KTC_TOOLCHANGER_INITIALIZE` | Manually initialize the specified or default toolchanger. |
  | `KTC_HEATERS_PAUSE` | Turns off all heaters that are configured for tools and saves the changes. The heaters can be resumed later using the command KTC_HEATERS_RESUME. This command does not affect heated beds. |
  | `KTC_HEATERS_RESUME` | Resumes all heaters that were previously turned off by the `KTC_HEATERS_PAUSE` command. |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Status, Logging and Persisted state
  | Command | Description |
  | ------- | ----------- |
  | `KTC_STATS_REPORT` | Report the KTC statistics to console. |
  | `KTC_PRINT_STATS_REPORT` | Report KTC statistics since last print started. |
  | `KTC_RESET_STATS SURE=YES` | Reset all the KTC statistics. |
  | `KTC_RESET_PRINT_STATS` | Run at start of a print to initialize and reset the KTC print statistics | |
  | `KTC_SET_LOG_LEVEL` | Set the log level for the KTC | `LEVEL=[0-3]` How much to log to console: ( 0 = Only the Always messages ) ( 1 = Info messages and above ) ( 2 = Debug messages and above ) ( 3 = Trace messages and above )<br>  `LOGFILE=[0-3]` How much to log to file. Levels as above. |
  | `KTC_LOG_TRACE` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTC_LOG_DEBUG` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTC_LOG_INFO` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTC_LOG_ALWAYS` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Debuging
  | Command | Description |
  | ------- | ----------- |
  | `KTC_DEBUG_HEATERS` | Reports current status of heaters. |
  | `KTC_DEBUG_TOOLS` | Reports current status of tools. |
  <br>
