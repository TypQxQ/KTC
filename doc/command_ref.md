# KTCC - Command Reference

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Basic Toolchanger functionality

  | Command | Description | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Parameters&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
  | ------- | ----------- | ---------- |
  | `KTCC_TOOL_LOCK` | Lock the tool to the toolhead. |  |
  | `KTCC_TOOL_UNLOCK` | Unlock the toolhead from tool. |  |
  | `KTCC_Tn` | Activates heater, pick up and readyy the tool. If tool is mapped to another one then that tool will be selected instead. | `RESTORE_AXIS=[XYZ]` Restore specified axis position to the latest saved. |
  | `KTCC_TOOL_DROPOFF_ALL` | Unloads and parks the current tool without picking up another tool, leaving the toolhead free and unlocked. Actual active extruder eill still be last used one as Klipper needs an active extruder. |  |
  | `SET_TOOL_TEMPERATURE` | Set tool temperature. If `TOOL` parameter is omited then current tool is set. | `TOOL=[0..n]` Optional if other than current loaded tool<br>`ACTV_TMP=...` Set Active temperature, optional<br> `STDB_TMP =...` Standby temperature, optional<br> `CHNG_STATE=[0\|1\|2]` Change Heater State, optional:<br>(0 = Off) \| (1 = Standby) \| (2 = Active)<br> `SHTDWN_TIMEOUT=...` Time in seconds to wait with the heater in standby before changing it to off, optional. <br>  `STDB_TIMEOUT=...` Time in seconds to linger at Active temp. after setting the heater to standby when the standby temperature is lower than current tool temperature, optional.<br> `SHTDWN_TIMEOUT` is used for example so a tool used only on first few layers shuts down after 30 minutes of inactivity and won't stay at 175*C standby for the rest of a 72h print.<br> `STDB_TIMEOUT=` Time to linger at Active temp. after setting the heater to standby. Could be used for a tool with long heatup times and is only put in standby short periods of thme throughout a print and  should stay at active temperature longer time. |
  | `KTCC_SET_AND_SAVE_PARTFAN_SPEED` | Set the partcooling fan speed current or specified tool. Fan speed is carried over between toolchanges. | `S=[0-255 \| 0-1]` Fan speed with either a maximum of 255 or 1.<br> `P=[0-n]` Tool number if not current tool to set fan to. |
  | `TEMPERATURE_WAIT_WITH_TOLERANCE` | Waits for all temperatures, or a specified tool or heater's temperature. This command can be used without any additional parameters and then waits for bed and current extruder. Only one of either TOOL or HEATER may be used. | `TOOL=[0-n]` Tool number to wait for, optional.<br> `HEATER=[0-n]` Heater number. 0="heater_bed", 1="extruder", 2="extruder1", 3="extruder2", etc. Only works if named as default, this way, optional.<br> `TOLERANCE=[0-n]` Tolerance in degC. Defaults to 1*C. Wait will wait until heater is in range of set temperature +/- tolerance. |
  <br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Offset commands
  | Command | Description | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Parameters&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp |
  | ------- | ----------- | ---------- |
  | `KTCC_SET_GLOBAL_OFFSET` | Set a global offset that can be applied to all tools. Can use absolute offset or adjust relative to current offset. | `X=...` Set the new offset for the axis.<br> `Y=...` As above.<br> `Z=...` As above.<br> ----------<br>`X_ADJUST=...` Adjust the offset position incramentally.<br> `Y_ADJUST=...` As above.<br> `Z_ADJUST=...` As above.<br>  |
  | `KTCC_SET_TOOL_OFFSET` | Set the offset of an individual tool. Can use absolute offset or adjust relative to current offset. | `TOOL=[0-n]` Tool number, optional. If not provided, the current tool is used.<br> ----------<br> `X=...` Set the new offset for the axis.<br> `Y=...` As above.<br> `Z=...` As above.<br> ----------<br>`X_ADJUST=...` Adjust the offset position incramentally.<br> `Y_ADJUST=...` As above.<br> `Z_ADJUST=...` As above.<br>  |
  | `KTCC_SET_GCODE_OFFSET_FOR_CURRENT_TOOL` | Sets the Klipper G-Code offset to the one for the current tool. | `MOVE=[0\|1]` Wheteher to move the toolhead to the new offset. ( 0 = Do not move, default ) ( 1 = Move )<br>  |
  <br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Position saving and restoring commands
  | Command | Description | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Parameters&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp |
  | ------- | ----------- | ---------- |
  | `KTCC_SAVE_POSITION` | Save the specified G-Code position for later restore. Without parameters it will set to not restoring axis. | `X=...` Set the restore position and set this axis to be restored.<br> `Y=...` As above.<br> `Z=...` As above. |
  | `KTCC_SAVE_CURRENT_POSITION` | Save the current G-Code position for later restore. Without parameters it will save previousley saved axis. | `RESTORE_POSITION_TYPE=[XYZ] or [0\|1\|2]` Axis to save or tyoe ( 0 = No restore ), ( 1 = Restore XY ), ( 2 = Restore XYZ ) |
  | `KTCC_RESTORE_POSITION` | Restore a previously saved G-Code position. With no parameters it will Restore to previousley saved type. | `RESTORE_POSITION_TYPE=[XYZ] or [0\|1\|2]` Axis to save or tyoe ( 0 = No restore ), ( 1 = Restore XY ), ( 2 = Restore XYZ ) |
  <br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Tool remapping commands
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `KTCC_DISPLAY_TOOL_MAP` | Dump the current mapping of tools to other KTCC tools. |  |
  | `KTCC_REMAP_TOOL` | Remap a tool to another one. | `RESET=[0\|1]` If 1 the stored tooö remap will be reset.<br> `TOOL=[0-n]` The toolnumber to remap.<br> `SET=[0-n]` The toolnumber to remap to. |
  <br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Status, Logging and Persisted state
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `KTCC_SAVE_CURRENT_TOOL` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_SET_PURGE_ON_TOOLCHANGE` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_ENDSTOP_QUERY` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_SET_ALL_TOOL_HEATERS_OFF` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_LOG_TRACE` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_RESUME_ALL_TOOL_HEATERS` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  <br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Status, Logging and Persisted state
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `KTCC_DUMP_STATS` | Dump the KTCC statistics to console. |  |
  | `KTCC_RESET_STATS` | Reset all the KTCC statistics. | `SUERE=[yes\|no]` If "yes" the stored statistics will be reset. |
  | `KTCC_INIT_PRINT_STATS` | Run at start of a print to initialize and reset the KTCC print statistics | |
  | `KTCC_DUMP_PRINT_STATS` | Run at end of a print to dump statistics since last print reset to console. | |
  | `KTCC_SET_LOG_LEVEL` | Set the log level for the KTCC | `LEVEL=[0-3]` How much to log to console: ( 0 = Only the Always messages ) ( 1 = Info messages and above ) ( 2 = Debug messages and above ) ( 3 = Trace messages and above )<br>  `LOGFILE=[0-3]` How much to log to file. Levels as above. |
  | `KTCC_LOG_TRACE` |  Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_LOG_DEBUG` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_LOG_INFO` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  | `KTCC_LOG_ALWAYS` | Send a message to log at this logging level | `MSG=...` The message to be sent |
  <br>

<br>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) User defined/configurable macros (defined in mmu_software.cfg)

  | Macro | Description | Supplied Parameters |
  | ----- | ----------- | ------------------- |
  | `_MMU_PRE_UNLOAD` | Called prior to unloading on toolchange | |
  | `_MMU_POST_LOAD` | Called subsequent to loading new filament on toolchange| |
  | `_MMU_ENDLESS_SPOOL_PRE_UNLOAD` | Called prior to unloading the remains of the current filament | |
  | `_MMU_ENDLESS_SPOOL_POST_LOAD` | Called subsequent to loading filament in the new gate in the sequence | |
  | `_MMU_FORM_TIP_STANDALONE` | Called to create tip on filament when not in print (and under the control of the slicer). You tune this macro by modifying the defaults to the parameters | |
  | `_MMU_ACTION_CHANGED` | Callback that is called everytime the `printer.ercf.action` is updated. Great for contolling LED lights, etc | |
  | `_MMU_LOAD_SEQUENCE` | Called when MMU is asked to load filament | `FILAMENT_POS` `LENGTH` `FULL` `HOME_EXTRUDER` `SKIP_EXTRUDER` `EXTRUDER_ONLY` |
  | `_MMU_UNLOAD_SEQUENCE` | Called when MMU is asked to unload filament | `FILAMENT_POS` `LENGTH` `EXTRUDER_ONLY` `PARK_POS` |

<br>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Internal macros for custom composition of load/unload sequences

  | Macro | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Description&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Parameters |
  | ----- | ----------- | ---------- |
  | `_MMU_STEP_LOAD_ENCODER` | User composable loading step: Move filament from gate to start of bowden using encoder | |
  | `_MMU_STEP_LOAD_BOWDEN` | User composable loading step: Smart loading of bowden | `LENGTH=..` |
  | `_MMU_STEP_HOME_EXTRUDER` | User composable loading step: Extruder collision detection | |
  | `_MMU_STEP_LOAD_TOOLHEAD` | User composable loading step: Toolhead loading | `EXTRUDER_ONLY=[0\|1]` |
  | `_MMU_STEP_UNLOAD_TOOLHEAD` | User composable unloading step: Toolhead unloading | `EXTRUDER_ONLY=[0\|1]` `PARK_POS=..` |
  | `_MMU_STEP_UNLOAD_BOWDEN` | User composable unloading step: Smart unloading of bowden | `FULL=[0\|1]` `LENGTH=..` |
  | `_MMU_STEP_UNLOAD_ENCODER` | User composable unloading step: Move filament from start of bowden and park in the gate using encoder | `FULL=[0\|1]` |
  | `_MMU_STEP_SET_FILAMENT` | User composable loading step: Set filament position state | `STATE=[0..8]` `SILENT=[0\|1]` |
  | `_MMU_STEP_MOVE` | User composable loading step: Generic move | `MOVE=..[100]` Length of gear move in mm <br>`SPEED=..` (defaults to speed defined to type of motor/homing combination) Stepper move speed <br>`ACCEL=..` (defaults to min accel defined on steppers employed in move) Motor acceleration <br>`MOTOR=[gear\|extruder\|gear+extruder\|extruder+gear]` (default: gear) The motor or motor combination to employ. gear+extruder commands the gear stepper and links extruder to movement, extruder+gear commands the extruder stepper and links gear to movement |
  | `_MMU_STEP_HOMING_MOVE` | User composable loading step: Generic homing move | `MOVE=..[100]` Length of gear move in mm <br>`SPEED=..` (defaults to speed defined to type of motor/homing combination) Stepper move speed <br>`ACCEL=..` Motor accelaration (defaults to min accel defined on steppers employed in homing move) <br>`MOTOR=[gear\|extruder\|gear+extruder\|extruder+gear]` (default: gear) The motor or motor combination to employ. gear+extruder commands the gear stepper and links extruder to movement, extruder+gear commands the extruder stepper and links gear to movement. This is important for homing because the endstop must be on the commanded stepper <br>`ENDSTOP=..` Symbolic name of endstop to home to as defined in mmu_hardware.cfg. Must be defined on the primary stepper <br>`STOP_ON_ENDSTOP=[1\|-1]` (default 1) The direction of homing move. 1 is in the normal direction with endstop firing, -1 is in the reverse direction waiting for endstop to release. Note that virtual (touch) endstops can only be homed in a forward direction |

> [!NOTE]  
> *Working reference PAUSE / RESUME / CANCEL_PRINT macros are defined in `client_macros.cfg` and can be used/modified if you don't already have your own*

<br>
  
