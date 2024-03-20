# KTC - Command Reference

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) All commands
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
  | `KTC_SET_ACTIVE_TOOL` |  Set the current loaded tool manually to the specified. When loading a tool manually | `T=[-2-n]` Tool to set as current. ( -2 = Unknown tool ), ( -1 = Toollock unlocked without tool ) |
  | `KTC_SET_STATE` | . |  |
  | `KTC_TOOL_SET_STATE` | . |  |
  | `KTC_TOOLCHANGER_SET_STATE` | . |  |
  | `KTC_TOOLCHANGER_SET_SELECTED_TOOL` | . |  |
  | `KTC_SET_PURGE_ON_TOOLCHANGE` |  Sets a global variable that can disable all purging (can be used in macros) when loading/unloading tools. For example for automated tool alignement such as TAMV/ZTATP. | `VALUE=[0\|1]` If enabled or disabled. |
  | `KTC_TOOLCHANGER_INITIALIZE` | Wait for a ENDSTOP untill it is in the specified state indefinitly or for maximum atempts if specified. Checking state once a second. | `ENDSTOP=...` Name of the endstop to wait for.<br> `TRIGGERED=[0\|1]` If should be waiting for it to be triggered (1) or open (0).<br> `ATEMPTS=...` Number of atempts to make, indefinitly if not specified. |
  | `KTC_HEATERS_PAUSE` | Turns off all heaters configured for tools and saves changes made to be resumed later by KTC_RESUME_ALL_TOOL_HEATERS. This does not affect heated beds or other heaters not defined as aan extruder in tools. | |
  | `KTC_HEATERS_RESUME` |  Resumes all heaters previously turned off by KTC_SET_ALL_TOOL_HEATERS_OFF. | `MSG=...` The message to be sent |
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











  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Basic Toolchanger functionality

  | Command | Description | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Parameters&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
  | ------- | ----------- | ---------- |
  | `KTC_TOOLCHANGER_ENGAGE` | Engage or lock the tool. |  |
  | `KTC_TOOLCHANGER_DISENGAGE` | Disengage or unlock from the tool. |  |
  | `KTC_Tn` | Activates heater, pick up and readyy the tool. If tool is mapped to another one then that tool will be selected instead. | `RESTORE_AXIS=[XYZ]` Restore specified axis position to the latest saved. |
  | `KTC_DESELECT_ALL` | Unloads and parks the current tool without picking up another tool, leaving the toolhead free and unlocked. Actual active extruder eill still be last used one as Klipper needs an active extruder. |  |
  | `KTC_TOOL_SET_TEMPERATURE` | Set tool temperature. If `TOOL` parameter is omited then current tool is set. | `TOOL=[0..n]` Optional if other than current loaded tool<br>`ACTV_TMP=...` Set Active temperature, optional<br> `STDB_TMP =...` Standby temperature, optional<br> `CHNG_STATE=[0\|1\|2]` Change Heater State, optional:<br>(0 = Off) \| (1 = Standby) \| (2 = Active)<br> `SHTDWN_TIMEOUT=...` Time in seconds to wait with the heater in standby before changing it to off, optional. <br>  `STDB_TIMEOUT=...` Time in seconds to linger at Active temp. after setting the heater to standby when the standby temperature is lower than current tool temperature, optional.<br> `SHTDWN_TIMEOUT` is used for example so a tool used only on first few layers shuts down after 30 minutes of inactivity and won't stay at 175*C standby for the rest of a 72h print.<br> `STDB_TIMEOUT=` Time to linger at Active temp. after setting the heater to standby. Could be used for a tool with long heatup times and is only put in standby short periods of thme throughout a print and  should stay at active temperature longer time. |
  | `KTC_SET_AND_SAVE_PARTFAN_SPEED` | Set the partcooling fan speed current or specified tool. Fan speed is carried over between toolchanges. | `S=[0-255 \| 0-1]` Fan speed with either a maximum of 255 or 1.<br> `P=[0-n]` Tool number if not current tool to set fan to. |
  | `KTC_TEMPERATURE_WAIT_WITH_TOLERANCE` | Waits for all temperatures, or a specified tool or heater's temperature. This command can be used without any additional parameters and then waits for bed and current extruder. Only one of either TOOL or HEATER may be used. | `TOOL=[0-n]` Tool number to wait for, optional.<br> `HEATER=[0-n]` Heater number. 0="heater_bed", 1="extruder", 2="extruder1", 3="extruder2", etc. Only works if named as default, this way, optional.<br> `TOLERANCE=[0-n]` Tolerance in degC. Defaults to 1*C. Wait will wait until heater is in range of set temperature +/- tolerance. |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Offset commands
  | Command | Description | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Parameters&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp |
  | ------- | ----------- | ---------- |
  | `KTC_GLOBAL_OFFSET_SAVE` | Set a global offset that can be applied to all tools. Can use absolute offset or adjust relative to current offset. | `X=...` Set the new offset for the axis.<br> `Y=...` As above.<br> `Z=...` As above.<br> ----------<br>`X_ADJUST=...` Adjust the offset position incramentally.<br> `Y_ADJUST=...` As above.<br> `Z_ADJUST=...` As above.<br>  |
  | `KTC_TOOL_OFFSET_SAVE` | Set the offset of an individual tool. Can use absolute offset or adjust relative to current offset. | `TOOL=[0-n]` Tool number, optional. If not provided, the current tool is used.<br> ----------<br> `X=...` Set the new offset for the axis.<br> `Y=...` As above.<br> `Z=...` As above.<br> ----------<br>`X_ADJUST=...` Adjust the offset position incramentally.<br> `Y_ADJUST=...` As above.<br> `Z_ADJUST=...` As above.<br>  |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Tool remapping commands
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `KTC_TOOLS_DISPLAY` | Dump the current mapping of tools to other KTC tools. |  |
  | `KTC_TOOL_MAP_NR` | Remap a tool to another one. | `RESET=[0\|1]` If 1 the stored tooö remap will be reset.<br> `TOOL=[0-n]` The toolnumber to remap.<br> `SET=[0-n]` The toolnumber to remap to. |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Advanced commands, rarely used
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `KTC_SET_ACTIVE_TOOL` |  Set the current loaded tool manually to the specified. When loading a tool manually | `T=[-2-n]` Tool to set as current. ( -2 = Unknown tool ), ( -1 = Toollock unlocked without tool ) |
  | `KTC_SET_STATE` | . |  |
  | `KTC_TOOL_SET_STATE` | . |  |
  | `KTC_TOOLCHANGER_SET_STATE` | . |  |
  | `KTC_TOOLCHANGER_SET_SELECTED_TOOL` | . |  |
  | `KTC_SET_PURGE_ON_TOOLCHANGE` |  Sets a global variable that can disable all purging (can be used in macros) when loading/unloading tools. For example for automated tool alignement such as TAMV/ZTATP. | `VALUE=[0\|1]` If enabled or disabled. |
  | `KTC_TOOLCHANGER_INITIALIZE` | Wait for a ENDSTOP untill it is in the specified state indefinitly or for maximum atempts if specified. Checking state once a second. | `ENDSTOP=...` Name of the endstop to wait for.<br> `TRIGGERED=[0\|1]` If should be waiting for it to be triggered (1) or open (0).<br> `ATEMPTS=...` Number of atempts to make, indefinitly if not specified. |
  | `KTC_HEATERS_PAUSE` | Turns off all heaters configured for tools and saves changes made to be resumed later by KTC_RESUME_ALL_TOOL_HEATERS. This does not affect heated beds or other heaters not defined as aan extruder in tools. | |
  | `KTC_HEATERS_RESUME` |  Resumes all heaters previously turned off by KTC_SET_ALL_TOOL_HEATERS_OFF. | `MSG=...` The message to be sent |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Status, Logging and Persisted state
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `KTC_DUMP_STATS` | Dump the KTC statistics to console. |  |
  | `KTC_RESET_STATS` | Reset all the KTC statistics. | `SUERE=[yes\|no]` If "yes" the stored statistics will be reset. |
  | `KTC_RESET_PRINT_STATS` | Run at start of a print to initialize and reset the KTC print statistics | |
  | `KTC_DUMP_PRINT_STATS` | Run at end of a print to report statistics since last print reset to console. | |
  | `KTC_SET_LOG_LEVEL` | Set the log level for the KTC | `LEVEL=[0-3]` How much to log to console: ( 0 = Only the Always messages ) ( 1 = Info messages and above ) ( 2 = Debug messages and above ) ( 3 = Trace messages and above )<br>  `LOGFILE=[0-3]` How much to log to file. Levels as above. |
  | `KTC_LOG_TRACE` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTC_LOG_DEBUG` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTC_LOG_INFO` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTC_LOG_ALWAYS` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  <br>

  ## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Debuging
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `KTC_DEBUG_HEATERS` | Dumps information about heaters not being off. |  |
  | `KTC_DEBUG_TOOLS` | Dumps information about tools. | `SUERE=[yes\|no]` If "yes" the stored statistics will be reset. |
  <br>
