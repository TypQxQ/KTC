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
  | `MMU_RESET` | Reset the MMU persisted state back to defaults | `CONFIRM=[0\|1]` Must be sepcifed for affirmative action of this dangerous command |
  | `MMU_STATS` | Dump (and optionally reset) the MMU statistics. Note that gate statistics are sent to debug level - usually the logfile) | `RESET=[0\|1]` If 1 the stored statistics will be reset |
  | `MMU_STATUS` | Report on MMU state, capabilities and Tool-to-Gate map | `DETAIL=[0\|1]` Whether to show a more detailed view including EndlessSpool groups and full Tool-To-Gate mapping <br>`SHOWCONFIG=[0\|1]` (default 0) Whether or not to describe the machine configuration in status message |
  <br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Status, Logging and Persisted state
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `MMU_RESET` | Reset the MMU persisted state back to defaults | `CONFIRM=[0\|1]` Must be sepcifed for affirmative action of this dangerous command |
  | `MMU_STATS` | Dump (and optionally reset) the MMU statistics. Note that gate statistics are sent to debug level - usually the logfile) | `RESET=[0\|1]` If 1 the stored statistics will be reset |
  | `MMU_STATUS` | Report on MMU state, capabilities and Tool-to-Gate map | `DETAIL=[0\|1]` Whether to show a more detailed view including EndlessSpool groups and full Tool-To-Gate mapping <br>`SHOWCONFIG=[0\|1]` (default 0) Whether or not to describe the machine configuration in status message |
  <br>


KTCC_SAVE_CURRENT_TOOL
KTCC_SET_PURGE_ON_TOOLCHANGE
KTCC_ENDSTOP_QUERY
KTCC_SET_ALL_TOOL_HEATERS_OFF
KTCC_RESUME_ALL_TOOL_HEATERS

  
  ### Servo and motor control
  | Command | Description | Parameters |
  | ------- | ----------- | ---------- |
  | `MMU_SERVO` | Set the servo to specified postion or a sepcific angle for testing.  | `POS=[up\|down\|move]` Move servo to predetermined position <br>`ANGLE=..` Move servo to specified angle |
  | `MMU_MOTORS_OFF` | Turn off both MMU motors | None |
  | `MMU_SYNC_GEAR_MOTOR` | Explicitly override the synchronization of extruder and gear motors. Note that synchronization is set automatically so this will only be sticky until the next tool change | `SYNC=[0\|1]` Turn gear/extruder synchronization on/off (default 1) <br>`SERVO=[0\|1]` If 1 (the default) servo will engage if SYNC=1 or disengage if SYNC=0 otherwise servo position will not change <br>`IN_PRINT=[0\|1]` If 1, gear stepper current will be set according to `sync_gear_current`. If 0, gear stepper current is set to 100%. The default is automatically determined based on print state but can be overridden with this argument. Only meaningful if `SYNC=1` |
  
  <br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Calibration

```yml
    MMU_CALIBRATE_BOWDEN - Calibration of reference bowden length for gate #0
    MMU_CALIBRATE_ENCODER - Calibration routine for the MMU encoder
    MMU_CALIBRATE_GATES - Optional calibration of individual MMU gate
    MMU_CALIBRATE_GEAR - Calibration routine for gear stepper rotational distance
    MMU_CALIBRATE_SELECTOR - Calibration of the selector positions or postion of specified gate
```
  
  | Command | Description | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Parameters&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
  | ------- | ----------- | ---------- |
  | `MMU_CALIBRATE_GEAR` | Calibration rourine for the the gear stepper rotational distance | `LENGTH=..` length to test over (default 100mm) <br>`MEASURED=..` User measured distance <br>`SAVE=[0\|1]` (default 1) Whether to save the result |
  | `MMU_CALIBRATE_ENCODER` | Calibration routine for MMU encoder | `LENGTH=..` Distance (mm) to measure over. Longer is better, defaults to 400mm <br>`REPEATS=..` Number of times to average over <br>`SPEED=..` Speed of gear motor move. Defaults to long move speed <br>`ACCEL=..` Accel of gear motor move. Defaults to motor setting in ercf_hardware.cfg <br>`MINSPEED=..` & `MAXSPEED=..` If specified the speed is increased over each iteration between these speeds (only for experimentation) <br>`SAVE=[0\|1]` (default 1)  Whether to save the result |
  | `MMU_CALIBRATE_SELECTOR` | Calibration of the selector gate positions. By default will automatically calibrate every gate.  ERCF v1.1 users must specify the bypass block position if fitted.  If GATE to BYPASS option is sepcifed this will update the calibrate for a single gate | `GATE=[0..n]` The individual gate position to calibrate <br>`BYPASS=[0\|1]` Calibrate the bypass position <br>`BYPASS_BLOCK=..` Optional (v1.1 only). Which bearing block contains the bypass where the first one is numbered 1 <br>`SAVE=[0\|1]` (default 1) Whether to save the result |
  | `MMU_CALIBRATE_BOWDEN` | Measure the calibration length of the bowden tube used for fast load movement. This will be performed on gate #0 | `BOWDEN_LENGTH=..` The approximate length of the bowden tube but NOT longer than the real measurement. 50mm less that real is a good starting point <br>`HOMING_MAX=..` (default 100) The distance after the sepcified BOWDEN_LENGTH to search of the extruder entrance <br>`REPEATS=..` (default 3) Number of times to average measurement over <br>`SAVE=[0\|1]` (default 1)  Whether to save the result |
  | `MMU_CALIBRATE_GATES` | Optional calibration for loading of a sepcifed gate or all gates. This is calculated as a ratio of gate #0 and thus this is usually the last calibration step | `GATE=[0..n]` The individual gate position to calibrate <br>`ALL[0\|1]` Calibrate all gates 1..n sequentially (filament must be available in each gate) <br>`LENGTH=..` Distance (mm) to measure over. Longer is better, defaults to 400mm <br>`REPEATS=..` Number of times to average over <br>`SAVE=[0\|1]` (default 1)  Whether to save the result |

<br>

  ## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Testing

```yml
    MMU_SOAKTEST_LOAD_SEQUENCE - Soak test tool load/unload sequence
    MMU_SOAKTEST_SELECTOR - Soak test of selector movement
    MMU_TEST_BUZZ_MOTOR - Simple buzz the selected motor (default gear) for setup testing
    MMU_TEST_CONFIG - Runtime adjustment of MMU configuration for testing or in-print tweaking purposes
    MMU_TEST_ENCODER_RUNOUT - Convenience macro to spoof a filament runout condition
    MMU_TEST_GRIP - Test the MMU grip for a Tool
    MMU_TEST_HOMING_MOVE - Test filament homing move to help debug setup / options
    MMU_TEST_LOAD - For quick testing filament loading from gate to the extruder
    MMU_TEST_MOVE - Test filament move to help debug setup / options
    MMU_TEST_TRACKING - Test the tracking of gear feed and encoder sensing
```
    
  | Command | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Description&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Parameters |
  | ------- | ----------- | ---------- |
  | `MMU_SOAKTEST_SELECTOR` | Reliability testing to put the selector movement under stress to test for failures. Randomly selects gates and occasionally re-homes | `LOOP=..[100]` Number of times to repeat the test <br>`SERVO=[0\|1]` Whether to include the servo down movement in the test |
  | `MMU_SOAKTEST_LOAD_SEQUENCE` | Soak testing of load sequence. Great for testing reliability and repeatability| `LOOP=..[10]` Number of times to loop while testing <br>`RANDOM=[0\|1]` Whether to randomize tool selection <br>`FULL=[0\|1]` Whether to perform full load to nozzle or short load just past encoder |
  | `MMU_TEST_BUZZ_MOTOR` | Buzz the sepcified MMU motor. If the gear motor is buzzed it will also report if filament is detected | `MOTOR=[gear\|selector\|servo]` |
  | `MMU_TEST_GRIP` | Test the MMU grip of the currently selected tool by gripping filament but relaxing the gear motor so you can check for good contact | None |
  | `MMU_TEST_LOAD` | Test loading filament from park position in the gate. (MMU_EJECT will unload) | `LENGTH=..[100]` Test load the specified length of filament into selected tool <br>`FULL=[0\|1]` If set to one a full bowden move will occur and filament will home to extruder |
  | `MMU_TEST_TRACKING | Simple visual test to see how encoder tracks with gear motor | `DIRECTION=[-1\|1]` Direction to perform the test (default load direction) <br>`STEP=[0.5 .. 20]` Size of individual steps (default 1mm) <br>`SENSITIVITY=..` (defaults to expected encoder resolution) Sets the scaling for the +/- mismatch visualization |
  | `MMU_TEST_MOVE` | Simple test move the MMU gear stepper | `MOVE=..[100]` Length of gear move in mm <br>`SPEED=..` (defaults to speed defined to type of motor/homing combination) Stepper move speed <br>`ACCEL=..` (defaults to min accel defined on steppers employed in move) Motor acceleration <br>`MOTOR=[gear\|extruder\|gear+extruder\|extruder+gear]` (default: gear) The motor or motor combination to employ. gear+extruder commands the gear stepper and links extruder to movement, extruder+gear commands the extruder stepper and links gear to movement |
  | `MMU_TEST_HOMING_MOVE` | Testing homing move of filament using multiple stepper combinations specifying endstop and driection of homing move | `MOVE=..[100]` Length of gear move in mm <br>`SPEED=..` (defaults to speed defined to type of motor/homing combination) Stepper move speed <br>`ACCEL=..` Motor accelaration (defaults to min accel defined on steppers employed in homing move) <br>`MOTOR=[gear\|extruder\|gear+extruder\|extruder+gear]` (default: gear) The motor or motor combination to employ. gear+extruder commands the gear stepper and links extruder to movement, extruder+gear commands the extruder stepper and links gear to movement. This is important for homing because the endstop must be on the commanded stepper <br>`ENDSTOP=..` Symbolic name of endstop to home to as defined in mmu_hardware.cfg. Must be defined on the primary stepper <br>`STOP_ON_ENDSTOP=[1\|-1]` (default 1) The direction of homing move. 1 is in the normal direction with endstop firing, -1 is in the reverse direction waiting for endstop to release. Note that virtual (touch) endstops can only be homed in a forward direction |
  | `MMU_TEST_CONFIG` | Dump / Change essential load/unload config options at runtime | Many. Best to run MMU_TEST_CONFIG without options to report all parameters than can be specified |
  | `MMU_TEST_ENCODER_RUNOUT` | Filament runout handler that will also implement EndlessSpool if enabled | `FORCE_RUNOUT=1` is useful for testing to validate your _MMU_ENDLESS_SPOOL\*\* macros |

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
  
