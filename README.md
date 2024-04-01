<p align="center">
  <img src="https://github.com/TypQxQ/KTC/assets/24956496/72e5732b-c571-4dd3-9a0a-ca78b13b5b82" alt='A Toolchenager' width='30%'>
  <h1 align="center">KTC - Klipper Toolchanger Code <sub>v.2</sub></h1>
</p>

<p align="center">
Universal Toolchanger helper for Klipper
</p>

<p align="center">
  <a aria-label="Downloads" href="https://github.com/TypQxQ/KTC/releases">
    <img src="https://img.shields.io/github/release/TypQxQ/KTC?display_name=tag&style=flat-square"  alt="Downloads Badge">
  </a>
  <a aria-label="Stars" href="https://github.com/TypQxQ/KTC/stargazers">
    <img src="https://img.shields.io/github/stars/TypQxQ/KTC?style=flat-square"  alt="Stars Badge">
  </a>
  <a aria-label="Forks" href="https://github.com/TypQxQ/KTC/network/members">
    <img src="https://img.shields.io/github/forks/TypQxQ/KTC?style=flat-square" alt="Forks Badge">
  </a>
  <a aria-label="License" href="https://github.com/TypQxQ/KTC/blob/master/LICENSE">
    <img src="https://img.shields.io/github/license/TypQxQ/KTC?style=flat-square" alt="License Badge">
  </a>
  <a aria-label="Codacy Badge" href="https://app.codacy.com/gh/TypQxQ/KTC/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade">
    <img src="https://app.codacy.com/project/badge/Grade/2ba035ce6a444b889d3e9afcd5e9ec87" alt="Codacy Badge">
  </a>
</p>

This adds logic to [Klipper](https://github.com/Klipper3d/klipper) for layered, inherited ToolChanging functionality.

This is a complete rewrite of KTCC v.1 to be more versatile and have infinite levels of toolchangers. Inspiration comes mainly from how RRF enables toolchanging and from the HappyHare project.

I welcome any and all input and contributions. Don't be afraid to make a pull request :D

Complex code example is still under construction.

Thank you!

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Major features:
<ul>
  <li>Support any type of toolchanger and any type of tool.</li>
  <li>Infinite levels of nested changers and tools with inheritance.</li>
  <li>Handles Tool temperature transfers on tool select/deselect with multiple heaters and offsets.</li>
  <li>Standby temperatures for parked tools.</li>
  <li>Handles multiple fans per tool and speed transfer between tools.</li>
  <li>Wait to reach temperature with configurable tolerance for tool.</li>
  <li>Unlimited parameters for each object, accesible by macros.</li>
  <li>Tool number maping. Remap a tool to another, no need to reslice.</li>
  <li>Persitance of state and statistics across restarts.</li>
</ul>

<br>

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Installation

The code requires Klipper to run on Python v.3 and is not compatible with Python v.2.

### 1\. Automatic install with Moonraker autoupdate support
Connect to your klipper machine using SSH and run this one line command:
```
cd ~/ && git clone https://github.com/TypQxQ/KTC.git && bash ~/KTC/install.sh
```

Configure away inside printer.cfg or a file referenced by it.

### 2\. Manual Install
Copy or link the python (`*.py`) files into the `\klipper\klippy\extras` directory.

Copy the macros inside the macros folder and reference them in printer.cfg.

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Minimum Configuration:
* At least one tool needs to be defined, ex:

 `[ktc_tool 0]`

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Help and community:
[The discution forums here on Github](https://github.com/TypQxQ/KTC/discussions)

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Configuration Examples:
Configuration example can be found here:

* [Simple Configuration with one toolchanger](/config/example_config/simple/simple_example.cfg)
* [Full Configuration with one Toolchanger](/config/example_config/complete/complete_example.cfg)
* [Jubilee Toolchanger with Toolchanger and ERCF](https://github.com/TypQxQ/DuetBackup/tree/main/qTC-Klipper/config)

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) References:

**[Configuation Reference](./doc/configuration.md)**<br>
Explains all configurable options.

**[Command Reference](./doc/command_ref.md)**<br>
Lists all the commands available at runtime from Klipper.

**[Object state Reference](./doc/state_ref.md)**<br>
Lists all available object variables available to macros.

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Related projects
  - [kTAMV - Klipper Tool Alignment (using) Machine Vision](https://github.com/TypQxQ/kTAMV)  allows X and Y allignment betwween multiple tools on a 3D printer using a camera that points up towards the nozzle from inside Klipper.

  - [KnobProbe](https://github.com/TypQxQ/KnobProbe_Klipper) allows Z allignment between multiple tools.

  - [Query Endstop Continuesly in Klipper](https://github.com/TypQxQ/Query-Endstop-Continuesly-in-Klipper) Klipper module that adds a G-code command so Klipper will pause until specified endstop is in selected state, triggered or not triggered. Alternativley it can query a specified amount of times.

  - [Klipper Save-Restore  Position](https://github.com/TypQxQ/Klipper-Save-Restore-Position) Adds behaviour as was in Klipper Toolchanger code v.1. Currently not finnished because I see no use for it. Tell me if you need it.

  - [KTCC v.1](https://github.com/TypQxQ/Klipper_ToolChanger)