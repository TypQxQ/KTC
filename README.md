<p align="center">
  <img src="https://github.com/TypQxQ/KTCC/assets/24956496/72e5732b-c571-4dd3-9a0a-ca78b13b5b82" alt='A Toolchenager' width='30%'>
  <h1 align="center">KTC - Klipper Tool Changer code <sub>v.2</sub></h1>
</p>

<p align="center">
Universal Toolchanger helper for Klipper
</p>

<p align="center">
  <a aria-label="Downloads" href="https://github.com/TypQxQ/KTC/releases">
    <img src="https://img.shields.io/github/release/TypQxQ/KTC?display_name=tag&style=flat-square">
  </a>
  <a aria-label="Stars" href="https://github.com/TypQxQ/KTC/stargazers">
    <img src="https://img.shields.io/github/stars/TypQxQ/KTC?style=flat-square">
  </a>
  <a aria-label="Forks" href="https://github.com/TypQxQ/KTC/network/members">
    <img src="https://img.shields.io/github/forks/TypQxQ/KTC?style=flat-square">
  </a>
  <a aria-label="License" href="https://github.com/TypQxQ/KTC/blob/master/LICENSE">
    <img src="https://img.shields.io/github/license/TypQxQ/KTC?style=flat-square">
  </a>
</p>

This helps [Klipper](https://github.com/Klipper3d/klipper) with ToolChanging functionality.

This is a complete rewrite of [KTCC v.1](https://github.com/TypQxQ/Klipper_ToolChanger) to be more versatile and have indefinite levels of toolchangers. Inspiration comes mainly from how RRF enables toolchanging and from the HappyHare project.

# !!!!!!!!!!!!!!!!!!!!!!!!!!
# This is still under development
Published for preview.
The code works but the documentation is not finished yet.
# !!!!!!!!!!!!!!!!!!!!!!!!!!

I welcome any and all input and contributions. Don't be afraid to make a pull request :D

Thank you!

## Readme Table of Contents
**[Major feature](#---major-features)**<br>
**[Installation](#---installation)**<br>
\- [1-Automatic install with Moonraker Autoupdate Support](#1-automatic-install-with-Moonraker-autoupdate-aupport)<br>
\- [2-Manual Install](#2-manual-install)<br>
**[Minimum Configuration](#---minimum-configuration)**<br>
**[Configuration Examples](#---configuration-examples)**<br>
**[G-Code commands](#---g-code-commands)**<br>
**[Values accesible from Macro for each object](#---values-accesible-from-macro-for-each-object)**<br>

#### Other Docs:

**[Command Reference](./doc/command_ref.md)**<br>
**[Harware Configuration, Movement and Homing](./doc/hardware_config.md)**<br>
**[Configuation Reference](./doc/configuration.md)**<br>
**[Gcode Customization](./doc/gcode_customization.md)**<br>

<br>
 
## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Major features:
<ul>
  <li>Support any type of toolchanger and any type of tool.</li>
  <li>Infinite levels of nested changers and tools</li>
  <li>Handles fan speed transfer between tools.</li>
  <li>Handles Tool temperature transfers on tool select/deselect.</li>
  <li>Standby temperatures for parked tools</li>
  <li>Tools can have multiple heaters and fans.</li>
  <li>Tools don't need to be extruders/hotends, can be anything.</li>
  <li>Wait to reach temperature with configurable tolerance for tool.</li>
  <li>Current Tool persists at powerdown. Default but optional.</li>
  <li>Unlimited parameters for each object, accesible by macros.</li>
  <li>Tool number maping. Remap a tool to another, no need to reslice.</li>
  <li>Persitance of state and statistics across restarts.</li>
  <li>Sophisticated logging options (console and file)</li>
  <li>Moonraker update-manager support</li>
</ul>

<br>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Installation

### 1\. Automatic install with Moonraker Autoupdate Support
This plugin assumes that you installed Klipper into your home directory (usually `/home/pi`).

1) Clone this repo into your home directory where Klipper is installed:
```
cd ~
git clone https://github.com/TypQxQ/KTC.git
```

2) Run the `install.sh` script
```
~/KTC/install.sh
```

If you encouter errors after an automatic Klipper update you can safetly run the `install.sh` scipt again to repair the links to the extension.

### 2\. Manual Install
Copy or link the python (`*.py`) files into the `\klipper\klippy\extras` directory. Assuming Then restart Klipper to pick up the extensions.
Add the files in the macros folder to the macros folder.

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Minimum Configuration:
* At least one tool needs to be defined, ex:

 `[ktc_tool 0]`

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Help and community:
Discuss it on Discord:
<iframe src="https://discord.com/widget?id=1219262213492310106&theme=dark" width="800" height="300" allowtransparency="true" frameborder="0" sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts"></iframe>


## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Configuration Examples:
Configuration example can be found here:

* [Simple Configuration with one toolchanger](/config/example_config/simple/simple_example.cfg)
* [Full Configuration with one Toolchanger](/config/example_config/complete/complete_example.cfg)
* [Jubilee Toolchanger with Toolchanger and ERCF]


## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) G-Code commands:
Reffer to the [Command Reference](./doc/command_ref.md).<br>

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Values accesible from Macro for each object

  Macros used by KTC have this objects accesible

- **ktc** is accesible by all.
  - `global_offset` - Global offset.
  - `active_tool` - Name of the active tool. Special names are: 'tool_unknown' and 'tool_none'. 
  - `active_tool_n` - Tool Number if any of the active tool. Special numbers are: -2 for 'tool_unknown' and -1 for 'tool_none'. 
  - `saved_fan_speed` - Speed saved at each fanspeedchange to be recovered at Toolchange.
  - `state` - State of KTC, one of STATE_TYPE.
  - `tools` - List of all tool names.
  - `toolchangers` - List of all toolchangers.
  - `params_available` - List of available custom parameters as specified in the configuration file.
  - `params_*` - parameter in the above list.

- **Tool** - The tool calling this macro is referenced as `myself` in `tool_select_gcode:` and `tool_deselect_gcode:`. One can write `{myself.name}` which would return `3` for a tool named so.
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

- **Toolchanger** - The toolchanger calling this macro is referenced as `myself` in `init_gcode:`, `engage_gcode:` and `disengage_gcode:`. One can write `{myself.name}` which would return `Jubilee` for a toolchanger named so.
  - `name` - Tool name. 0, 1, 2, etc.
  - `selected_tool` - Name of the selected tool. Special names are: 'tool_unknown' and 'tool_none'. 
  - `selected_tool_n` - Tool Number if any of the selected tool. Special numbers are: -2 for 'tool_unknown' and -1 for 'tool_none'. 
  - `init_mode` - When this toolchanger is initialized: 'manual', 'on_start' or 'on_first_use'
  - `state` - State of the toolchanger, one of STATE_TYPE.
  - `tools` - List of all tool names attached to this toolchanger.
  - `params_available` - List of available custom parameters as specified in the configuration file.
  - `params_*` - parameter in the above list.

- **STATE_TYPE** Constant listing the difrent states ktc, a tool or toolchanger can have:
States can be set like: `KTC_TOOLCHANGER_SET_STATE TOOLCHANGER={myself.name} STATE=READY`
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

## ![#f03c15](/doc/f03c15.png) ![#c5f015](/doc/c5f015.png) ![#1589F0](/doc/1589F0.png) Example configuration
My corrent configuration is for v.2 where work progresses fast.

