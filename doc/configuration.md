# KTC Configuration reference

This document is a reference for options available in the Klipper Toolchanger Code
config file.

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Configuration file structure

The configuration for KTC can be saved in one or multiple files that are referenced by printer.cfg

Minimum amount of information is one `[ktc_tool name]` section that will initiate one tool with a name.

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Structure

One KTC object can be configured and will contain one default toolchanger.
The default toolchanger can contain one or multiple tools. Each tool can have a toolchanger:

- [ktc]
    - [ktc_toolchanger Default]
        - [ktc_tool 0]
            - [ktc_toolchanger SubChanger]
                - [ktc_tool 0-0]
                - [ktc_tool 0-1]
                - [ktc_tool 0-2]
                - [ktc_tool 0-3]
        - [ktc_tool 1]
        - [ktc_tool 2]

### Inheritance

Inheritable options are propagated down the object tree until overridden.

For the previous structure, the following code would set all tools to require_axis_homed except for those under the toolchanger named "SubChanger" whose tools have no required axis to home and ktc_tool 2 that requires all XYZ as in default.
```
[ktc]
requires_axis_homed = XY

[ktc_toolchanger SubChanger]
requires_axis_homed = None

[ktc_tool 2]
requires_axis_homed =
```
### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Initiating options

Some options that are stored inside the persistance file can overriden from configuration. When klipper starts and finds such a option, it will save it to persistant state and raise an error prompting to delete or comment out the option in the config file. This is to have a clear source for the setting to be read from at startup and counter any ambiguity.

```
#init_offset = 0.0, 0.0, 0.0
#   Used to initiate tool offset from configuration. Saved to state. Inheritable.
#   Option must be removed or commented out after being run once.
#   Use the 'KTC_TOOL_OFFSET_SAVE' to specify at runtime.

#init_global_offset = 0.0, 0.0, 0.0
#   This only aplies to ktc object.
#   Option must be removed or commented out after being run once.
#   Use the 'KTC_GLOBAL_OFFSET_SAVE' to specify at runtime.
```

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Inheritable options

The following options can be set to either ktc, ktc_toolchanger or ktc_tool and will propagate down the object tree untill overridden by specifying it as empty `option=` or with a overriding value.

When not specified they will be initialized with the default value as below.

```
#engage_gcode = ""
#   Macro name or G-code to run when 'KTC_TOOLCHANGER_ENGAGE' runs for a ktc_toolchanger.
#   The toolchanger state is set to 'ENGAGING' at the begining and
#     the code here needs to change it to 'ENGAGED' or 'ERROR'.

#disengage_gcode
#   Macro name or G-code to run when 'KTC_TOOLCHANGER_DISENGAGE' runs for a ktc_toolchanger.
#   The toolchanger state is set to 'DISENGAGING' at the begining and
#     the code here needs to change it to 'READY' or 'ERROR'.

#init_gcode = ""
#   Macro name or G-code to run when 'KTC_TOOLCHANGER_INITIALIZE' runs for a ktc_toolchanger.
#   The toolchanger state is set to 'INITIALIZING' at the begining and
#     the code here needs to change it to 'INITIALIZED', 'READY' or 'ERROR'.

#tool_select_gcode = ""
#   Macro name or G-code to run when selecting a tool,
#     for example 'KTC_T' runs for a ktc_tool.
#   The toolchanger state is set to 'SELECTING' at the begining and
#     the code here needs to change it to 'SELECTED' or 'ERROR'.

#tool_deselect_gcode = ""
#   Macro name or G-code to run when selecting a tool,
#     for example 'KTC_T' or 'KTC_DESELECT_ALL' runs for a ktc_tool.
#   The toolchanger state is set to 'DESELECTING' at the begining and
#     the code here needs to change it to 'READY' or 'ERROR'.

#force_deselect_when_parent_deselects = True
#   Used with nested toolchangers.
#   Forces all child tools to deselect before deselecting the parent.
#   For the toolchanger in the 'Strcture' example above when changing from 0-1 to 2:
#     If True then it will deselect 0-1 and 0 before selecting 2.
#     If False then it will deselect 0 before selecting 2. 0-1 will be selected on ERCF
#      toolchanger and 2 will be selected on the main toolchanger and active on ktc.
#      When changing back to 0-1 from 2, it will select 0 and not need to select 0-1 again.
#      This saves time on expensive toolchanges.

#parent_must_be_selected_on_deselect = True
#   Used with nested toolchangers having 'force_deselect_when_parent_deselects = False'
#   When deselecting all tools with 'KTC_DESELECT_ALL' if 0-1 is selected but not 0 is:
#     If True, it will first select 0 before deselecting 0-1 and then 0.
#     If False, it will run 'tool_deselect_gcode' for 0-1 while not 0 is selected.
#   Setting it to False can be usefull when the tools are not dependent on eachother.

#heater = 
#   Used by ktc_tool to specify if the tool has one or more heaters and if it has a offset.
#   Heater names are comma separated with optional collon separated temperature offset.
#     'heater = extruder3:-100, extruder2'
#     Will set the tool to have 2 heaters. When setting temperature to 210*C, 
#       ktc will set the temperature to 210 for extruder2 and 110 for extruder3
#   Having multiple heaters per tool allows preheating filament for high speed printing.
#   When waiting for temperatures, KTC will wait for all the heaters on the tool.

#fans =
#   Used by ktc_tool to specify if the tool has one or more partcooling fans
#     and if it has a offset.
#   Fan names are comma separated with optional collon separated speed offset.
#     'fans = partfan_t11:-0.2, curtain_cooler'
#     Will set the tool to have 2 fans. When setting fan speed to 80%, 
#       ktc will set the speed to 80% for curtain_cooler and 64% for partfan_t11

#requires_axis_homed = XYZ
#   Specifies axis to ensure are homed before trying to select or deselect a tool.
#   'requires_axis_homed =' disables any check of axis.

#heater_active_to_standby_delay = 0.1
#   When changing the heaters of a tool from active to standby, the temperatures
#     will not change imediatley but after the specified time in seconds.
#   0.1 seconds is actually instant. This can be usefull for verry short toolchanges
#     to spped up the time it takes to get up to active tool temerature.

#heater_standby_to_powerdown_delay = 600
#   After the heaters of a tool have entered standby, a timer will start counting down
#     to the specified seconds and then change state to turn off the heaters.
#   Default is 10 minutes. This prevents having a tool run hot for a long time when
#     not being used. When selecting the tool again, it will enter active mode and heat
#     back up.

```

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Custom parameters

User defined parameters can be set to the ktc, any tool or toolchanger. Theese are also inherited. To specify such a parameter use the prefix "params_". For example `params_meltzone_lenght = 14`. All user parameters are accessible from macros as read-only. They can be named as anything as long as they have the right prefix and do not use spaces or invalid characters.

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) [KTC]

The topmost object contains inheritable options that will be inherited by all other objects unless they are specifically overridden.

```
[ktc]
#propagate_state = True
#   Propagate state when changed on a tool, down through the tree to the ktc object.
#   For example setting a tool state as selected will set it's changer to engaged.

#default_toolchanger = <name of the only ktc_toolchanger object>
#   This is required when specifying more than one ktc_toolchanger section.
#   Otherwise it will default to the name of the only
#   ktc_toolchanger object available.

#debug_with_profile = False
#   Use profiler to measure time it takes to run diffrent commands and output to ktc.log
```

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) [ktc_toolchanger]

For each toolchanger. If no such section is defined a toolchanger named default_toolchanger with the default options will be created.

```
[ktc_toolchanger default_toolchanger]
#parent_tool = <None>
#   Not applicable for default_toolchanger and required for all other.
#   Specifies the tool this toolchanger has as parent.
```

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) [ktc_tool]

Requires one ktc_tool section for each tool to be used. Only the section name is required as all other options have default values.

```
[ktc_tool name_of_this_tool]
#tool_number = -3
#   Map this tool to a number. Available numbers start at 0. Needs one to be usefull.
#   Default -3 denotes it not having a number.

#toolchanger = <ktc.default_toolchanger>
#   The name of the toolchanger when using layered toolchangers.
#   Defauts to the 'default_toolchanger' of ktc.

```

## ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Log and persistance

KTC uses it's owm logging module that creates a file named "ktc.log".

Persistant options are saved in a file named "ktc_variables.cfg" and does not require any conflicting configurations of Klippers "varaibles.cfg" file.

The log module needs no referenced in the configuration if using default options while the persistance module has no options.

```
[ktc_log]
#log_level = 1
#   Determines the amount of logging displayed on the console.
#   Log levels:
#   - 0 = Only the Always messages
#   - 1 = Info messages and above
#   - 2 = Debug messages and above
#   - 3 = Trace messages and above

#logfile_level = 3
#   Determines the amount of logging saved to file, levels as above.

#rollover_logfile_at_startup = False
#   When enabled, it will clear the log file existing under another name at each startup.
#   Usefull when debugging.
```
