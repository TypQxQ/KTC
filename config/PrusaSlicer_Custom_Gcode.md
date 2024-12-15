Here are the custom G-codes I use in PrusaSlicer on my ToolChanger as an example.
This haven't been updated so use with caution

Start G-code:
 - I don't heat the tools before actually using them so I don't degrade filament.
 - Using e3d Revo the heatup times for the tools are verry fast.
```
KTCC_INIT_PRINT_STATS

; Heat the bed first
M140 S[first_layer_bed_temperature]
; Wait for bed to reach temperature with 2 degrees tolerance
M116 H0 W2
M568 P[initial_extruder] R{if not is_nil(idle_temperature[initial_extruder])} R{idle_temperature[initial_extruder]}{else} R100{endif} S{first_layer_temperature[initial_extruder]} A1

G28

G0 Z3 F5000	; Ensure nozzle is at 3mm over the bed
T[initial_extruder]	; Mount extruder first used (even if only one extruder used). Waits for temperature inside the script.
```

End G-code
```
; Custom gcode to run at end of print
M104 S0 		; turn off temperature
G10 P0 S0 R0 A0	; turn off extruder 0
G10 P1 S0 R0 A0	; turn off extruder 1
G10 P2 S0 R0 A0	; turn off extruder 2
M140 S0 		; turn off bed
T_1		; dropoff current tool
G91 		; relative moves
G0 Z20  		; move bed down another 30mm
G90 		; absolute moves
G0 X1 Y1 F30000	; Move toolhead out of the way
SAVE_POSITION         ; Reset saved position.
KTCC_DUMP_PRINT_STATS ; Print statistics to console.
```

ToolChange G-code
  - Sets the temperature before activating the tool in case this is the first time the tool is selected.
  - On first layer it sets the temperature for the next tool to first layer temperature.
```
{if layer_num < 1}M568 P[next_extruder] {if not is_nil(idle_temperature[initial_extruder])} R{idle_temperature[initial_extruder]}{else} R100{endif} S{first_layer_temperature[next_extruder]} A2 ;First layer temperature
{else}M568 P[next_extruder] {if not is_nil(idle_temperature[initial_extruder])} R{idle_temperature[initial_extruder]}{else} R100{endif} S{first_layer_temperature[next_extruder]} A2 ;Other layer temperature
{endif}
G91 		; relative moves
G0 Z1  		; move bed down 1mm to add a Z-hop style on toolchange.
G90 		; absolute moves
T{next_extruder} ; Actual ToolChange
```
