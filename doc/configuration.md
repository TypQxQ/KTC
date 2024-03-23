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

The following options are inherited from troughout the structure untill overridden. Overriding with a default value ca be done by using a empty option like `option=`.

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

They are inherited by child objects that do not have a override.

```
#init_offset = 0.0, 0.0, 0.0

#init_global_offset = 0.0, 0.0, 0.0
```
The inheritable options can be specified for any section and will only be used for inheritance if not needed for the specific section type.

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Custom parameters

User defined parameters can be set to the ktc, any tool or toolchanger. Theese are also inherited. To specify such a parameter use the prefix "params_". For example `params_meltzone_lenght = 14`. All user parameters are accessible from macros as read-only. They can be named as anything as long as they have the right prefix and do not use spaces or invalid characters.

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) Inheritable options

The following options are inherited:

```
#engage_gcode = ""

#disengage_gcode

#init_gcode = ""

#tool_select_gcode = ""

#tool_deselect_gcode = ""

#force_deselect_when_parent_deselects = True

#parent_must_be_selected_on_deselect = True

#heater = 

#fans =

#requires_axis_homed = XYZ

#heater_active_to_standby_delay = 0.1

#heater_standby_to_powerdown_delay = 600

```

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) [KTC]

The topmost object contains inheritable options that will be inherited by all other objects unless they are specifically overridden.

```
[ktc]
#propagate_state = True
#   Propa
#default_toolchanger = <name of the only ktc_toolchanger object>
#   This is required when specifying more than one ktc_toolchanger section.
#   Otherwise it will default to the name of the only
#   ktc_toolchanger object available.
#debug_with_profile = False
```

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) [ktc_toolchanger]

For each toolchanger. If no such section is defined a toolchanger named default_toolchanger with the default options will be created.

```
[ktc_toolchanger default_toolchanger]
parent_tool = <None>
#   Not applicable for default_toolchanger and required for any other.
#   Specifies the tool this toolchanger has as parent.
```

### ![#f98b00](/doc/f98b00.png) ![#fe3263](/doc/fe3263.png) ![#0fefa9](/doc/0fefa9.png) ![#085afe](/doc/085afe.png) [ktc_tool]

Requires one ktc_tool section for each tool to be used. Only the section name is required as all other options have default values.

```
[ktc_tool]
tool_number = -3
toolchanger = <ktc.default_toolchanger>
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
```
