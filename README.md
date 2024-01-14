<p align="center">
  <img src="https://github.com/TypQxQ/KTCC/assets/24956496/72e5732b-c571-4dd3-9a0a-ca78b13b5b82" alt='A Toolchenager' width='30%'>
  <h1 align="center">KTC - Klipper Tool Changer code <sub>v.2</sub></h1>
</p>

<p align="center">
Universal Toolchanger driver for Klipper
</p>

<p align="center">
  <a aria-label="Downloads" href="https://github.com/TypQxQ/KTCC/releases">
    <img src="https://img.shields.io/github/release/TypQxQ/KTCC?display_name=tag&style=flat-square">
  </a>
  <a aria-label="Stars" href="https://github.com/TypQxQ/KTCC/stargazers">
    <img src="https://img.shields.io/github/stars/TypQxQ/KTCC?style=flat-square">
  </a>
  <a aria-label="Forks" href="https://github.com/TypQxQ/KTCC/network/members">
    <img src="https://img.shields.io/github/forks/TypQxQ/KTCC?style=flat-square">
  </a>
  <a aria-label="License" href="https://github.com/TypQxQ/KTCC/blob/master/LICENSE">
    <img src="https://img.shields.io/github/license/TypQxQ/KTCC?style=flat-square">
  </a>
</p>

This is what gives [Klipper](https://github.com/Klipper3d/klipper) ToolChanging functionality.
It began as a collection of macros when I transitioned a toolchanger from Duet RepRap Firmware to Klipper.
After that it evolved to Python scripts and for version 2 I have renamed most everything with to KTC prefix for consistency.
This makes easier to enable Mainsail and KlipperScreen integration.
Inspiration comes mainly from how RRF enables toolchanging and from the HappyHare project.

I welcome any and all input and contributions. Don't be afraid to make a pull request :D

Thank you!
<p align="center">
!!!!!!!!!!!!!!!!!!!!!!!!
This is still under development and not functional.
!!!!!!!!!!!!!!!!!!!!!!!!
</p>

## Readme Table of Contents
**[Major feature](#major-features)**<br>
**[Installation](#installation)**<br>
**[Basic Commands](#---basic-commands-and-printer-variables)**<br>
**[Setup & Calibration](#---setup-and-calibration)**<br>
**[Important Concepts and Features](#---important-concepts-and-features)**<br>
\- [1. How to handle errors](#1-how-to-handle-errors)<br>
\- [2. State and Persistence](#2-state-and-persistence)<br>
\- [3. Tool to Gate Mapping](#3-tool-to-gate-ttg-mapping)<br>
\- [4. Synchronized Gear/Extruder](#4-synchronized-gearextruder-motors)<br>
\- [5. Clog, Runout, EndlessSpool, Flowrate](#5-clogrunout-detection-endlessspool-and-flowrate-monitoring)<br>
\- [6. Logging me](#6-logging)<br>
\- [7. Pause/Resume/Cancel](#7-pause--resume--cancel_print-macros)<br>
\- [8. Recovering MMU state](#8-recovering-mmu-state)<br>
\- [9. Gate statistics](#9-gate-statistics)<br>
\- [10. Filament bypass](#10-filament-bypass)<br>
\- [11. Pre-print functions](#11-useful-pre-print-functionality)<br>
\- [12. Gate map, Filament type and color](#12-gate-map-describing-filament-type-color-and-status)<br>
**[Loading and Unloading Sequences](#---filament-loading-and-unloading-sequences)**<br>
**[KlipperScreen Happy Hare Edition](#---klipperscreen-happy-hare-edition)**<br>
**[My Testing / Setup](#---my-testing)**<br>
**[Revision History](#---revision-history)**<br>

#### Other Docs:

**[Command Reference](./doc/command_ref.md)**<br>
**[Harware Configuration, Movement and Homing](./doc/hardware_config.md)**<br>
**[Calibration Guide](./doc/calibration.md)**<br>
**[Configuation Reference](./doc/configuration.md)**<br>
**[Gcode Customization](./doc/gcode_customization.md)**<br>

<br>
 
## Major features:
<ul>
  <li>Support any type of toolchanger and any type of tool</li>
  <li>Tools don't need to be extruders/hotends, can be anything.</li>
  <li>Each Tool is treated as an object and has it's own configuration having configurable coordinates for parking, tool offset, extruder, part cooling fan, etc.</li>
  <li>Tools don't need to be extruders/hotends, can be anything.</li>
  <li>Virtual tools - One tool can have multiple tools. Your T0-T8 can be on same extruder, fan and heater but having an MMU while T9 is another extruder and T10-T12 is another tool with 3 markers that can switched by a servo and finally T13 is a pick and place tool.</li>
  <li>Multiple tools can be grouped in ToolGroup. -Most configuration can be inherited from the group and overwritten when needed by the tool config section.</li>
  <li>Partcooling Fan speed is carried over on toolchange if the tool has a fan. M106/M107 defaults to fan of current_tool  but can also specify another tool.</li>
  <li>Extensive extruder temperature control:</li>
  <ul>
    <li>A tool heater can be set as Active, Standby or Off mode</li>
    <li>Diffrent Active and Standby temperatures for any tool. Switches to Active when selected and to Standby when Parked.</li>
    <li>Configurable delay from Standby to off when parked. If tool isn't used for 30 minutes it cools down until used again.</li>
    <li>Wait to reach temperature with configurable tolerance.</li>
    <li>Position prior to toolchange can optionaly be saved and restored after toolchange. Configurable axis.</li>
  </ul>
  <li>Current Tool persists at powerdown. Default but optional.</li>
  <li>Tool remaping. Remap a tool to another, no need to reslice.</li>
  <li>Sophisticated logging options (console and ktcc.log file)</li>
  <li>Moonraker update-manager support</li>
  <li>Persitance of state and statistics across restarts.</li>
  <li>Vast customization options!</li>
</ul>

<br>
 
## Installation
The module can be installed into an existing Klipper installation with the install script. Once installed it will be added to Moonraker update-manager to easy updates like other Klipper plugins:

```
cd ~
git clone https://github.com/TypQxQ/KTCC.git
cd KTCC

./install.sh -i
```

The `-i` option will bring up an interactive installer to aid setting some confusing parameters. For EASY-BRD and Fysetc ERB installations it will also configure all the pins for you. If not run with the `-i` flag the new template `mmu*.cfg` files will not be installed. Note that if existing `mmu*.cfg` files are found the old versions will be moved to numbered backups like `<file>.<date>` extension instead so as not to overwrite an existing configuration. If you still choose not to install the new `mmu*.cfg` files automatically be sure to examine them closely and compare to the supplied templates (this is completely different software from the original)
<br>

Note that the installer will look for Klipper install and config in standard locations. If you have customized locations or multiple Klipper instances on the same rpi, or the installer fails to find Klipper you can use the `-k` and `-c` flags to override the klipper home directory and klipper config directory respectively.
<br>

> [!IMPORTANT]  
> `mmu.cfg`, `mmu_hardware.cfg`, `mmu_software.cfg` & `mmu_parameters.cfg` must all be referenced by your `printer.cfg` master config file with `mmu.cfg` and `mmu_hardware.cfg` listed first (the easiest way to achieve this is simply with `[include mmu/base/*.cfg]`) . `client_macros.cfg` should also be referenced if you don't already have working PAUSE / RESUME / CANCEL_PRINT macros (but be sure to read the section before on macro expectations and review the default macros). The install script can also include these config files for you.
<br>

**Pro tip:** if you are concerned about running `install.sh -i` then run like this: `install.sh -i -c /tmp -k /tmp` This will build the `*.cfg` files for you but put then in /tmp. You can then read them, pull out the bits your want to augment existing install or simply see what the answers to the various questions will do...

```
Usage: ./install.sh [-k <klipper_home_dir>] [-c <klipper_config_dir>] [-i] [-u]
     -i for interactive install
     -u for uninstall
(no flags for safe re-install / upgrade)
```

> [!WARNING]  
> ERCF v1.1 users: the original encoder can be problematic. A new backward compatible alternative is available in the ERCF v2.0 project and is strongly recommended. If you insist on fighting with the original encoder be sure to read my [notes on Encoder problems](doc/ercf_encoder_v11.md) - the better the encoder the better this software will work with ERCF design.

<br>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Basic Commands and Printer Variables

Happy Hare has a built in help system to aid remembering the command set. It can accessed with the `MMU_HELP` command and can also be used to view testing commands and user extensible macros which are called by Happy Hare on certain conditions. The full list of commands and options can be [found here](./doc/command_ref.md). Also Happy Hare exposes a large array of 'printer' variables that are useful in your own macros.

<details>
<summary><sub>🔹 Click to read more....</sub></summary>
<br>
 
  > MMU_HELP

```yml
    Happy Hare MMU commands: (use MMU_HELP MACROS=1 TESTING=1 for full command set)
    MMU - Enable/Disable functionality and reset state
    MMU_CHANGE_TOOL - Perform a tool swap
    MMU_CHECK_GATES - Automatically inspects gate(s), parks filament and marks availability
    MMU_STATS - Dump (and optionally reset) the MMU statistics
    MMU_EJECT - Eject filament and park it in the MMU or optionally unloads just the extruder (EXTRUDER_ONLY=1)
    MMU_ENCODER - Display encoder position or temporarily enable/disable detection logic in encoder
    MMU_ENDLESS_SPOOL - Redefine the EndlessSpool groups
    MMU_FORM_TIP - Convenience macro for calling the standalone tip forming functionality
    MMU_HELP - Display the complete set of MMU commands and function
    MMU_HOME - Home the MMU selector
    MMU_LOAD - Loads filament on current tool/gate or optionally loads just the extruder for bypass or recovery usage (EXTUDER_ONLY=1)
    MMU_MOTORS_OFF - Turn off both MMU motors
    MMU_PAUSE - Pause the current print and lock the MMU operations
    MMU_PRELOAD - Preloads filament at specified or current gate
    MMU_RECOVER - Recover the filament location and set MMU state after manual intervention/movement
    MMU_REMAP_TTG - Remap a tool to a specific gate and set gate availability
    MMU_RESET - Forget persisted state and re-initialize defaults
    MMU_SELECT - Select the specified logical tool (following TTG map) or physical gate
    MMU_SELECT_BYPASS - Select the filament bypass
    MMU_SERVO - Move MMU servo to position specified position or angle
    MMU_SET_GATE_MAP - Define the type and color of filaments on each gate
    MMU_STATUS - Complete dump of current MMU state and important configuration
    MMU_SYNC_GEAR_MOTOR - Sync the MMU gear motor to the extruder stepper
```

> MMU_HELP MACROS=1 TESTING=1

To additionaly see testing command set and macros.
<br>
Happy Hare exposes a large array of 'printer' variables that are useful in your own macros.

```yml
    printer.mmu.enabled : {bool} True if MMU is enabled
    printer.mmu.is_locked : {bool} True if MMU is paused after an error
    printer.mmu.is_homed : {bool} True if MMU has been homed
    printer.mmu.tool : {int} 0..n | -1 for unknown | -2 for bypass
    printer.mmu.gate : {int} 0..n | -1 for unknown
    printer.mmu.material : {string} Material type for current gate (useful for print_start macro)
    printer.mmu.next_tool : {int} 0..n | -1 for unknown | -2 for bypass (during a tool change)
    printer.mmu.last_tool : {int} 0..n | -1 for unknown | -2 for bypass (during a tool change after unload)
    printer.mmu.last_toolchange : {string} description of last change similar to M117 display
    printer.mmu.clog_detection : {int} 0 (off) | 1 (manual) | 2 (auto)
    printer.mmu.endless_spool : {int} 0 (disabled) | 1 (enabled)
    printer.mmu.filament : {string} Loaded | Unloaded | Unknown
    printer.mmu.filament_pos : {int} state machine - exact location of filament
    printer.mmu.filament_direction : {int} 1 (load( | -1 (unload)
    printer.mmu.servo : {string} Up | Down | Move | Unknown
    printer.mmu.ttg_map : {list} defined gate for each tool
    printer.mmu.gate_status : {list} per gate: 0 empty | 1 available | 2 available from buffer |  -1 unknown
    printer.mmu.gate_material : {list} of material names, one per gate
    printer.mmu.gate_color : {list} of color names, one per gate
    printer.mmu.endless_spool_groups : {list} membership group (int) for each tool
    printer.mmu.action : {string} Idle | Loading | Unloading | Forming Tip | Heating | Loading Ext | Exiting Ext | Checking | Homing | Selecting
    printer.mmu.has_bypass : {int} 0 (not available) | 1 (available)
    printer.mmu.sync_drive : {bool} True if gear stepper is currently synced to extruder
```

Optionally exposed on mmu_encoder (if fitted):

```yml
    printer['mmu_encoder mmu_encoder'].encoder_pos : {float} Encoder position measurement in mm
    printer['mmu_encoder mmu_encoder'].detection_length : {float} The detection length for clog detection
    printer['mmu_encoder mmu_encoder'].min_headroom : {float} How close clog detection was from firing on current tool change
    printer['mmu_encoder mmu_encoder'].headroom : {float} Current headroom of clog detection (i.e. distance from trigger point)
    printer['mmu_encoder mmu_encoder'].desired_headroom : {float} Desired headroom (mm) for automatic clog detection
    printer['mmu_encoder mmu_encoder'].detection_mode : {int} Same as printer.mmu.clog_detection
    printer['mmu_encoder mmu_encoder'].enabled : {bool} Whether encoder is currently enabled for clog detection
    printer['mmu_encoder mmu_encoder'].flow_rate : {int} % flowrate (extruder movement compared to encoder movement)
```

</details>

<br>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Setup and Calibration:

Configuration and calibration will vary slightly depending on your particular brand of MMU althought the steps are essentially the same with some being dependent on hardware configuration. Here are the five basic steps.

### 1\. Important MMU Vendor / Version Specification

Happy Hare functionality will vary with MMU vendor. After running the installer it is important to verify `mmu_vendor` and `mmu_version` correctly in `mmu_parameters.cfg` because they define the basic capabilities and options in Happy Hare. The only complication is that in order to support the many variations of ERCF v1.1 the correct suffix must be specified depending on modifications/upgrades.

<details>
<summary><sub>🔹 Read more about vendor/version specification...</sub></summary>
<br>


  
At it's simplest you need for each extruder tool to specify extruder, fan, offset to first tool or probe.
Then specify four macros: pickup, dropoff, toollock and toolunlock.
It doesn't matter if you lock the tool by a servo, a stepper or moving in a special way as long as it can be written in GCODE.

You can hardcode one pickup and dropoff macro for each tool or only one that uses the parameters stored for each tool to for example aproach he ZONE fast, slower to PARKING place, or the PARKING coordinates could be where a robotic arm picks up the tool. You decide how to use it :D

This is working great for my printer and sharing this because there is nothing like it for Klipper.

## Features

* **Each Tool is treated as an object and has it's own configuration** -
having configurable coordinates for parking, zoning, tool offset, 
meltzonelength, extruder, fan, etc. You can use all or none.
*  **Multiple tools can be grouped in ToolGroup.** -Most configuration can
be inherited from the group if not specified in the tool config section.
* **Tools don't need to be extruders/hotends**, can be anything.
* **User defineable macro to Lock / Unlock** - Uses custom gcodes in config 
like the gcode_button. This can call a macro or multiple lines. 
* **User defineable macro to Pickup / Dropoff tools** - Can be inherited from group so one for many or you specify a macro or code for each.
In the macro, `myself` refers to the calling toolobject so you can get 
myself.id for tool number or myself.offset[0] for X offset in the macro.
Ex. having same pickup gcode macro inherited for all tools from a group 
except for one that uses another type of toolwipe and has it's own pickup_gcode.
* **Fan speed** is carried over on toolchange if the tool has a fan. Also
`M106`/`M107` defaults to current_tool to set fan speed but can also use a Pnnn 
parameter to specify another tool.
* **Extruder temperature control** - 
  - Definable for any tool with a Pnnn parameter or defaults to current_tool
  - Has diffrent Active and Standby temperatures.
  - Can be set in Active, Standby or Off mode.
  - Can have delayed Standby and Off. Configured and/or customized with N and O parameters at runtime.
    - Example. Set Standby temperature 30 sec after putting the tool in standby and in Off after 30 minutes of not being activated.
    - Or set Time to standby to 0.1 for instant standby and Time to Powerdown to 604800 for a having it powered for a week.
    - Usefull when having sporadic toolchanges in a large print or many toolchanges in a small print.
  - Wait to reach temperature with tolerance. Set temperature +/- configurable tolerance.
* **Global ToolLock parameters** - example purge_on_toolchange can be set 
to false when aligning tools with TAMV/ZTATP automation. 
* Current Tool is saved and restored at powerdown. Default but optional.
* Position prior to toolchange can optionaly be saved and restored so the tool returns from where it came.
* Logging including to file functionality. You can keep the console log to a minimum and send debugging information to `ktcc.log` located in the same directory as Klipper logs.
*  **Virtual tools** - A tool can be virtual and have a physical parent,
inheriting all nonspecified configuration from parent, parent group and
then toolgroup. Use case example of an ERCF on a PLA tool,a ERCF on a 
PETG tool, one tool without virtual tools for abrasive and yet another
tool with 3 markers that can switch between 3 markers by rotation.
# Statistics are saved for total but also per print:
```
ToolChanger Statistics:
KTCC Statistics:
7 hours 52 minutes 36 seconds spent mounting tools
6 hours 42 minutes 46 seconds spent unmounting tools
30 tool locks completed
37 tool unlocks completed
462 tool mounts completed
461 tool dropoffs completed
------------
Tool#0:
Completed 220 out of 221 mounts in 3 hours 43 minutes 21 seconds. Average of 1 minutes 0 seconds per toolmount.
Completed 219 out of 220 unmounts in 3 hours 12 minutes 33 seconds. Average of 52 seconds per toolunmount.
1 hours 4 minutes 16 seconds spent selected. 23 hours 7 minutes 14 seconds with active heater and 49 minutes 44 seconds with standby heater.
------------
Tool#1:
Completed 124 out of 124 mounts in 2 hours 5 minutes 7 seconds. Average of 1 minutes 0 seconds per toolmount.
Completed 124 out of 125 unmounts in 1 hours 49 minutes 5 seconds. Average of 52 seconds per toolunmount.
10 hours 44 minutes 21 seconds spent selected. 0 seconds with active heater and 0 seconds with standby heater.
------------
Tool#49:
Completed 8 out of 8 mounts in 1 minutes 7 seconds. Average of 8 seconds per toolmount.
Completed 8 out of 8 unmounts in 42 seconds. Average of 5 seconds per toolunmount.
4 minutes 51 seconds spent selected. 0 seconds with active heater and 0 seconds with standby heater.
------------
```

## Installation Instructions
### Install with Moonraker Autoupdate Support
This plugin assumes that you installed Klipper into your home directory (usually `/home/pi`). 

1) Clone this repo into your home directory where Klipper is installed:
```
cd ~
git clone https://github.com/TypQxQ/Klipper_ToolChanger.git
```

2) Edit `moonraker.conf` by adding the following entry:
```
[update_manager client klipper_toolchanger]
type: git_repo
path: ~/Klipper_ToolChanger
origin: https://github.com/TypQxQ/Klipper_ToolChanger.git
install_script: install.sh
is_system_service: False
```

3) Run the `install.sh` script
```
~/Klipper_ToolChanger/install.sh
```

Klipper_ToolChanger will show up in the update the next time you restart moonraker, or you can restart mooraker right away with: `sudo systemctl restart moonraker`.
If you encouter errors after an automatic Klipper update you can safetly run the `install.sh` scipt again to repair the links to the extension.

### Manual Install
Copy the python (`*.py`) files into the `\klipper\klipper\extras` directory. Assuming Klipper is installed in your home directory:
```
cp ./*.py ~/klipper/klippy/extras/
```
Then restart Klipper to pick up the extensions.

## To do:
* Add selectable automatic calculation of active times based on previous times. Ex:
  * Mean Layer time Standby mode. - Save time at every layerchange and at toolchange set to mean time of last 3 layers *2 or at last layer *1.5 with a Maximum and a minimum time. Needs to be analyzed further.
  * Save the time it was in Standby last time and apply a fuzzfactor. Put tool in standby and heatup with presumption that next time will be aproximatley after the same time as last. +/- Fuzzfactor.

## Configuration requirements
* `[input_shaper]` needs to be used for input shaper to wordk.

## G-Code commands:
* `TOOL_LOCK` - Lock command
* `TOOL_UNLOCK` - Unlock command
* `KTCC_Tn` - T0, T1, T2, etc... A select command is created for each tool. 
  * `R` - Calls SAVE_CURRENT_POSITION with the variable as a RESTORE_POSITION_TYPE. For example "T0 R1" will call "SAVE_CURRENT_POSITION RESTORE_POSITION_TYPE=1" before moving. Positioned is restored with "RESTORE_POSITION" from below.
* `KTCC_TOOL_DROPOFF_ALL` - Dropoff the current tool without picking up another tool
* `SET_AND_SAVE_FAN_SPEED` - Set the fan speed of specified tool or current tool if no `P` is supplied. Then save to be recovered at ToolChange.
  * `S` - Fan speed 0-255 or 0-1, default is 1, full speed.
  * `P` - Fan of this tool. Default current tool.
* `TEMPERATURE_WAIT_WITH_TOLERANCE` - Waits for all temperatures, or a specified tool or heater's temperature.
This command can be used without any additional parameters. Without parameters it waits for bed and current extruder. Only one of either TOOL or HEATER may be used.
  - `TOOL` - Tool number.
  - `HEATER` - Heater number. 0="heater_bed", 1="extruder", 2="extruder1", 3="extruder2", etc. Only works if named as default, this way.
  - `TOLERANCE` - Tolerance in degC. Defaults to 1*C. Wait will wait until heater is between set temperature +/- tolerance.
* `SET_TOOL_TEMPERATURE` - Set tool temperature.
  * `TOOL` - Tool number, optional. If this parameter is not provided, the current tool is used.
  * `STDB_TMP` - Standby temperature(s), optional
  * `ACTV_TMP` - Active temperature(s), optional
  * `CHNG_STATE` - Change Heater State, optional: 0 = off, 1 = standby temperature(s), 2 = active temperature(s).
  * `STDB_TIMEOUT` - Time in seconds to wait between changing heater state to standby and setting heater target temperature to standby temperature when standby temperature is lower than tool temperature.
    * Use for example 0.1 to change immediately to standby temperature.
  * `SHTDWN_TIMEOUT` - Time in seconds to wait from docking tool to shutting off the heater, optional.
    * Use for example 86400 to wait 24h if you want to disable shutdown timer.
* `SET_GLOBAL_OFFSET` - Set a global offset that can be applied to all tools
  * `X` / `Y` / `Z` - Set the X/Y/Z offset position
  * `X_ADJUST` / `Y_ADJUST` / `Z_ADJUST` - Adjust the X/Y/Z offset position incramentally
* `SET_TOOL_OFFSET` - Set the offset of an individual tool
  * `TOOL` - Tool number, optional. If this parameter is not provided, the current tool is used.
  * `X` / `Y` / `Z` - Set the X/Y/Z offset position
  * `X_ADJUST` /`Y_ADJUST` / `Z_ADJUST` - Adjust the X/Y/Z offset position incramentally  
* `SET_PURGE_ON_TOOLCHANGE` - Sets a global variable that can disable all purging (can be used in macros) when loading/unloading. For example when doing a TAMV/ZTATP tool alignement.
* `SAVE_POSITION` - Sets the Restore type and saves specified position for the toolhead. This command is usually used inside the custom g-code of the slicer software. The restore_position_on_toolchange_type will be changed to reflect the passed parameters.
  * X= X position to save
  * Y= Y position to save
  * Z= Z position to save
* `SAVE_CURRENT_POSITION` - Save the current G-Code position of the toolhead. This command is usually used inside the pickup_gcode script or the custom g-code of the slicer software.
  * RESTORE_POSITION_TYPE= Type of restore, optional. If not specified, restore_position_on_toolchange_type will not be changed. 
    * 0/Empty: No restore
    * XYZ: Restore specified axis
    * 1: Restore XY
    * 2: Restore XYZ
* `RESTORE_POSITION` - Restore position to the latest saved position. This command is usually used inside the pickup_gcode script.
  * RESTORE_POSITION_TYPE= Type of restore, optional. If not specified, type set during save will be used.
    * 0/Empty: No restore
    * XYZ: Restore specified axis
    * 1: Restore XY
    * 2: Restore XYZ
* `KTCC_SET_GCODE_OFFSET_FOR_CURRENT_TOOL` - 
* `KTCC_LOG_TRACE` - Send a message to log at this logging level.
  * MSG= The message to be sent.
* `KTCC_LOG_DEBUG` - As above for this level.
* `KTCC_LOG_INFO` - As above for this level.
* `KTCC_LOG_ALWAYS` - As above for this level.
* `KTCC_SET_LOG_LEVEL` - Set the log level for the KTCC
  * LEVEL= Level of logging to print on screen
    * 0: Only the Always messages
    * 1: Info messages and above
    * 2: Debug messages and above
    * 3: Trace messages and above
  * LOGFILE= Level of logging to save to file, KTCC.log in same directory as other logs.
* `KTCC_DUMP_STATS` - Dump the KTCC statistics
* `KTCC_RESET_STATS` - Resets all saved statistics, you may regret this.
* `KTCC_INIT_PRINT_STATS` - Run at start of a print to reset the KTCC print statistics.
* `KTCC_DUMP_PRINT_STATS` - Run at end of a print to list statistics since last print reset.
* `KTCC_DISPLAY_TOOL_MAP` - Display the current mapping of tools to other KTCC tools.
* `KTCC_REMAP_TOOL` - The command to remap a tool or reset the remaping. 'KTCC_REMAP_TOOL TOOL=0 SET=5' will remap KTCC_T0 to KTCC_T5. State is saved and reloaded after restart.
  * RESET= 1
    * 0: Default, do not reset.
    * 1: Reset all remaps.
  * TOOL= The toolnumber you want to remap
  * SET= The toolnumber you want to remap to.

## Values accesible from Macro for each object
- **Toollock**
  - `global_offset` - Global offset.
  - `tool_current` - -2: Unknown tool locked, -1: No tool locked, 0: and up are toolnames.
  - `saved_fan_speed` - Speed saved at each fanspeedchange to be recovered at Toolchange.
  - `purge_on_toolchange` - For use in macros to enable/disable purge/wipe code globaly.
  - `restore_axis_on_toolchange` - The axis to restore position:
    - : No restore
    - XY: Restore XY
    - XYZ: Restore XYZ
    - Etc
  - `saved_position` - The position saved when the latest T# command had a RESTORE_POSITION parameter to other than 0
- **Tool** - The tool calling this macro is referenced as `myself` in macros. When running for example `T3` to pickup the physical tool, in `pickup_gcode:` of one can write `{myself.name}` which would return `3`.
  - `name` - id. 0, 1, 2, etc.
  - `is_virtual` - If this tool has another layer of toolchange possible.
  - `physical_parent_id` - Parent physical tool that holds tool coordinates. Can be same as this.
  - `extruder` - extruder name as configured.
  - `fan` - fan name.
  - `lazy_home_when_parking` - When set to 1, will home unhomed XY axes if needed and will not move any axis if already homed and parked. 2 Will also home Z if not homed.
  - `meltzonelength` - Meltzonelength to unload/load filament at toolpak. See e3d documentation.
  - `zone` - Fast aproach coordinates when parking
  - `park` - Parking spot, slow aproach.
  - `offset` - Tool offset.
  - `heater_state` - 0 = off, 1 = standby temperature, 2 = active temperature. Placeholder.
  - `heater_active_temp` - Temperature to set when in active mode.
  - `heater_standby_temp` - Temperature to set when in standby mode.
  - `idle_to_standby_time` - Time in seconds from being parked to setting temperature to standby the temperature above. Use 0.1 to change imediatley to standby temperature.
  - `idle_to_powerdown_time` - Time in seconds from being parked to setting temperature to 0. Use something like 86400 to wait 24h if you want to disable. Requred on Physical tool.
- **ToolGroup**
  - `is_virtual` - As above
  - `physical_parent_id` - As above
  - `lazy_home_when_parking` - As above

## Example configuration
My full and updated configuration file backup can be found here:
https://github.com/TypQxQ/DuetBackup/tree/main/qTC-Klipper

## Updates 09/03/2023
Added Tool Remap. Point one or more tools to another one. Including fan and temperature. This is persistent at reboot.
* `KTCC_DISPLAY_TOOL_MAP` - Display the current mapping of tools to other KTCC tools.
* `KTCC_REMAP_TOOL` - The command to remap a tool or reset the remaping.
* `KTCC_CHECK_TOOL_REMAP` - Display all tool remaps.


## Updates 08/03/2023
Added per print statistics and a wrapper around G28 to disable saving statistics while homing.
The latter led to MCU Timer to close error when loading a tool at homing.
* `KTCC_INIT_PRINT_STATS` - Run at start of a print to reset the KTCC print statistics.
* `KTCC_DUMP_PRINT_STATS` - Run at end of a print to list statistics since last print reset.

## Updates 22/02/2023
This is not a simple upgrade, it has some configuration updates.
A namechange to KTCC (Klipper Tool Changer Code) is also in the works).

- **News:**
  - Virtual Tools
  - Logfile
  - Statistics

- **Changes to Configuration:**
  - LogLevel under ToolLock is deprecated.
  - Must include new section ```[ktcclog]``` before all other Toollock, tool, and the others..
  - New ```virtual_toolload_gcode:`` parameter to tools.
  - New ```virtual_toolunload_gcode:`` parameter to tools.

- **Changes to commands:**
  - T_1 => KTCC_TOOL_DROPOFF_ALL
  - T# => KTCC_T# (ex. T0 => KTCC_T0)

- **New  commands:**
  - KTCC_SET_GCODE_OFFSET_FOR_CURRENT_TOOL
  - KTCC_LOG_TRACE
  - KTCC_LOG_DEBUG
  - KTCC_LOG_INFO
  - KTCC_LOG_ALWAYS
  - KTCC_SET_LOG_LEVEL
  - KTCC_DUMP_STATS
  - KTCC_RESET_STATS
# KTC
Klipper Tool Changer code v.2
