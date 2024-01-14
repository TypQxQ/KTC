# KTC - Klipper Tool Changer code (v.2)
# Toollock and general Tool support
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
import ast
from . import ktc_log, ktc_toolchanger, ktc_save_variables

KTC_SAVE_VARIABLES_FILENAME = "~/ktc_variables.cfg"
KTC_SAVE_VARIABLES_DELAY = 10

VARS_KTC_TOOL_MAP = "ktc_state_tool_remap"

XYZ_TO_INDEX = {'x': 0, 'X':0, 'y':1, 'Y': 1, 'z': 2, 'Z':2}
INDEX_TO_XYZ = ['X','Y','Z']

class ktc:
    def __init__(self, config):
        self.config = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.log : ktc_log.Ktc_Log = self.printer.load_object(config, 'ktc_log')  # Load the log object.

        self.saved_fan_speed = 0          # Saved partcooling fan speed when deselecting a tool with a fan.
        self.active_tool = ktc_toolchanger.TOOL_UNKNOWN
        self.global_offset = [0,0,0]      # Global offset for all tools.
        self.params = get_params_dict(config)

        self.tool_map = {}
        self.last_endstop_query = {}
        self.changes_made_by_set_all_tool_heaters_off={}
        self.saved_position = None
        self.restore_axis_on_toolchange = '' # string of axis to restore: XYZ


        self.global_offset = config.get('global_offset', "0,0,0")
        if isinstance(self.global_offset, str):
            offset_list = self.global_offset.split(',')
            if len(offset_list) == 3 and all(x.replace('.', '').isdigit() for x in offset_list):
                self.global_offset = [float(x) for x in offset_list]
            else:
                raise ValueError("global_offset is not a string containing 3 float numbers separated by ,")
        else:
            raise TypeError("global_offset is not a string")

        # Register commands
        handlers = [
            'KTC_OVERRIDE_CURRENT_TOOL',
            'KTC_DROPOFF', 'KTC_SET_AND_SAVE_PARTFAN_SPEED', 'KTC_TEMPERATURE_WAIT_WITH_TOLERANCE', 
            'KTC_SET_TOOL_TEMPERATURE', 'KTC_SET_GLOBAL_OFFSET', 'KTC_SET_TOOL_OFFSET',
            'KTC_SAVE_POSITION', 'KTC_SAVE_CURRENT_POSITION', 'KTC_RESTORE_POSITION',   # Current possition can be saved without parameters to KTC_SAVE_POSITION.
            'KTC_SET_GCODE_OFFSET_FOR_CURRENT_TOOL',        # Maybe remove?
            'KTC_DISPLAY_TOOL_MAP', 'KTC_REMAP_TOOL', 
            'KTC_ENDSTOP_QUERY',                            # Move to own file.
            'KTC_SET_ALL_TOOL_HEATERS_OFF', 'KTC_RESUME_ALL_TOOL_HEATERS']
        # 'KTC_TOOL_LOCK', 'KTC_TOOL_UNLOCK',
        for cmd in handlers:
            func = getattr(self, 'cmd_' + cmd)
            desc = getattr(self, 'cmd_' + cmd + '_help', None)
            self.gcode.register_command(cmd, func, False, desc)

        # Register events
        self.printer.register_event_handler('klippy:connect', self.handle_connect)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        # self.printer.register_event_handler("klippy:disconnect", self.handle_disconnect)

    def handle_connect(self):
        # Load the persistent variables object
        self.ktc_persistent : ktc_save_variables.KtcSaveVariables = self.printer.load_object(self.config, 'ktc_save_variables')

    def handle_ready(self):
        # Load persistent Tool remaping. Should be done after connect event where tools are initialized.
        self.tool_map = self.log.ktc_persistent.vars.get(VARS_KTC_TOOL_MAP, {})
        self.tool_map = {}
        
        try:
            if len(self.tool_map) > 0:
                self.log.always(self._tool_map_to_human_string())
        except Exception as e:
            self.log.always('Warning: Error booting up KTC: %s' % str(e))

    def set_current_tool_state(self, t : int):
        self.active_tool = t
        self.log.trace("Saving current tool: " + str(t))
        self.ktc_persistent.save_variable('current_tool', str(t), section="State", force_save=True)

    cmd_KTC_DROPOFF_help = "Deselect all tools"
    def cmd_KTC_DROPOFF(self, gcmd = None):
        self.log.trace("KTC_TOOL_DROPOFF_ALL running. ")# + gcmd.get_raw_command_parameters())
        if self.active_tool == "-2":
            raise self.printer.command_error("cmd_KTC_TOOL_DROPOFF_ALL: Unknown tool already mounted Can't park unknown tool.")
        if self.active_tool != "-1":
            self.printer.lookup_object('ktc_tool ' + str(self.active_tool)).Dropoff( force_virtual_unload = True )
        

        try:
            # Need to check all tools at least once but reload them after each time.
            all_checked_once = False
            while not all_checked_once:
                all_tools = dict(self.printer.lookup_objects('ktc_tool'))
                all_checked_once =True # If no breaks in next For loop then we can exit the While loop.
                for tool_name, tool in all_tools.items():
                    # If there is a virtual tool loaded:
                    if tool.get_status()["virtual_loaded"] > ktc_toolchanger.TOOL_UNLOCKED:
                        # Pickup and then unload and drop the tool.
                        self.log.trace("cmd_KTC_TOOL_DROPOFF_ALL: Picking up and dropping forced: %s." % str(tool.get_status()["virtual_loaded"]))
                        self.printer.lookup_object('ktc_tool ' + str(tool.get_status()["virtual_loaded"])).select_tool_actual()
                        self.printer.lookup_object('ktc_tool ' + str(tool.get_status()["virtual_loaded"])).Dropoff( force_virtual_unload = True )
                        all_checked_once =False # Do not exit while loop.
                        break # Break for loop to start again.

        except Exception as e:
            raise Exception('cmd_KTC_TOOL_DROPOFF_ALL: Error: %s' % str(e))

    cmd_KTC_OVERRIDE_CURRENT_TOOL_help = "Override the current tool as to be the specified tool."
    def cmd_KTC_OVERRIDE_CURRENT_TOOL(self, gcmd):
        t = gcmd.get_int('T', None, minval=-2)
        if t is not None:
            self.set_current_tool_state(t)

    cmd_KTC_SET_AND_SAVE_PARTFAN_SPEED_help = "Save the fan speed to be recovered at ToolChange."
    def cmd_KTC_SET_AND_SAVE_PARTFAN_SPEED(self, gcmd):
        fanspeed = gcmd.get_float('S', 1, minval=0, maxval=255)
        tool_id = gcmd.get_int('P', int(self.active_tool), minval=0)

        # The minval above doesn't seem to work.
        if tool_id < 0:
            self.log.always("cmd_KTC_SET_AND_SAVE_PARTFAN_SPEED: Invalid tool:"+str(tool_id))
            return None

        # If value is >1 asume it is given in 0-255 and convert to percentage.
        if fanspeed > 1:
            fanspeed=float(fanspeed / 255.0)

        self.SetAndSaveFanSpeed(tool_id, fanspeed)

    #
    # Todo: 
    # Implement Fan Scale. Inspired by https://github.com/jschuh/klipper-macros/blob/main/fans.cfg
    # Can change fan scale for diffrent materials or tools from slicer. Maybe max and min too?
    #    
    def SetAndSaveFanSpeed(self, tool_id, fanspeed):
        # Check if the requested tool has been remaped to another one.
        tool_is_remaped = self.tool_is_remaped(int(tool_id))
        if tool_is_remaped > -1:
            tool_id = tool_is_remaped


        tool = self.printer.lookup_object('ktc_tool ' + str(tool_id))

        if tool.fan is None:
            self.log.debug("ktc.SetAndSaveFanSpeed: Tool %s has no fan." % str(tool_id))
        else:
            self.SaveFanSpeed(fanspeed)
            self.gcode.run_script_from_command(
                "SET_FAN_SPEED FAN=%s SPEED=%f" % 
                (tool.fan, 
                fanspeed))

    cmd_KTC_TEMPERATURE_WAIT_WITH_TOLERANCE_help = "Waits for current tool temperature, or a specified (TOOL) tool or (HEATER) heater's temperature within (TOLERANCE) tolerance."
#  Waits for all temperatures, or a specified tool or heater's temperature.
#  This command can be used without any additional parameters.
#  Without parameters it waits for bed and current extruder.
#  Only one of either P or H may be used.
#
#  TOOL=nnn Tool number.
#  HEATER=nnn Heater number. 0="heater_bed", 1="extruder", 2="extruder1", etc.
#  TOLERANCE=nnn Tolerance in degC. Defaults to 1*C. Wait will wait until heater is between set temperature +/- tolerance.
    def cmd_KTC_TEMPERATURE_WAIT_WITH_TOLERANCE(self, gcmd):
        curtime = self.printer.get_reactor().monotonic()
        heater_name = None
        tool_id = gcmd.get_int('TOOL', None, minval=0)
        heater_id = gcmd.get_int('HEATER', None, minval=0)
        tolerance = gcmd.get_int('TOLERANCE', 1, minval=0, maxval=50)

        if tool_id is not None and heater_id is not None:
            self.log.always("cmd_KTC_TEMPERATURE_WAIT_WITH_TOLERANCE: Can't use both P and H parameter at the same time.")
            return None
        elif tool_id is None and heater_id is None:
            tool_id = self.active_tool
            if int(self.active_tool) >= 0:
                heater_name = self.printer.lookup_object('ktc_tool ' + self.active_tool).get_status()["extruder"]
            #wait for bed
            self._Temperature_wait_with_tolerance(curtime, "heater_bed", tolerance)

        else:                                               # Only heater or tool is specified
            if tool_id is not None:
                # Check if the requested tool has been remaped to another one.
                tool_is_remaped = self.tool_is_remaped(int(tool_id))
                if tool_is_remaped > -1:
                    tool_id = tool_is_remaped

                heater_name = self.printer.lookup_object(   # Set the heater_name to the extruder of the tool.
                    'ktc_tool ' + str(tool_id)).get_status(curtime)["extruder"]
            elif heater_id == 0:                            # Else If 0, then heater_bed.
                heater_name = "heater_bed"                      # Set heater_name to "heater_bed".

            elif heater_id == 1:                            # Else If h is 1 then use for first extruder.
                heater_name = "extruder"                        # Set heater_name to first extruder which has no number.
            else:                                           # Else is another heater number.
                heater_name = "extruder" + str(heater_id - 1)   # Because bed is heater_number 0 extruders will be numbered one less than H parameter.
        if heater_name is not None:
            self._Temperature_wait_with_tolerance(curtime, heater_name, tolerance)


    def _Temperature_wait_with_tolerance(self, curtime, heater_name, tolerance):
        target_temp = int(self.printer.lookup_object(       # Get the heaters target temperature.
                    heater_name).get_status(curtime)["target"]
                          )
        
        if target_temp > 40:                                # Only wait if set temperature is over 40*C
            self.log.always("Wait for heater " + heater_name + " to reach " + str(target_temp) + " with a tolerance of " + str(tolerance) + ".")
            self.gcode.run_script_from_command(
                "TEMPERATURE_WAIT SENSOR=" + heater_name + 
                " MINIMUM=" + str(target_temp - tolerance) + 
                " MAXIMUM=" + str(target_temp + tolerance) )
            self.log.always("Wait for heater " + heater_name + " complete.")

    def _get_tool_id_from_gcmd(self, gcmd):
        tool_id = gcmd.get_int('TOOL', None, minval=0)

        if tool_id is None:
            tool_id = self.active_tool
        if not int(tool_id) > ktc_toolchanger.TOOL_UNLOCKED:
            self.log.always("_get_tool_id_from_gcmd: Tool " + str(tool_id) + " is not valid.")
            return None
        else:
            # Check if the requested tool has been remaped to another one.
            tool_is_remaped = self.tool_is_remaped(int(tool_id))
            if tool_is_remaped > ktc_toolchanger.TOOL_UNLOCKED:
                tool_id = tool_is_remaped
        return tool_id


    cmd_KTC_SET_TOOL_TEMPERATURE_help = "Waits for all temperatures, or a specified (TOOL) tool or (HEATER) heater's temperature within (TOLERANCE) tolerance."
#  Set tool temperature.
#  TOOL= Tool number, optional. If this parameter is not provided, the current tool is used.
#  STDB_TMP= Standby temperature(s), optional
#  ACTV_TMP= Active temperature(s), optional
#  CHNG_STATE = Change Heater State, optional: 0 = off, 1 = standby temperature(s), 2 = active temperature(s).
#  STDB_TIMEOUT = Time in seconds to wait between changing heater state to standby and setting heater target temperature to standby temperature when standby temperature is lower than tool temperature.
#      Use for example 0.1 to change immediately to standby temperature.
#  SHTDWN_TIMEOUT = Time in seconds to wait from docking tool to shutting off the heater, optional.
#      Use for example 86400 to wait 24h if you want to disable shutdown timer.
    def cmd_KTC_SET_TOOL_TEMPERATURE(self, gcmd):
        tool_id = self._get_tool_id_from_gcmd(gcmd)
        if tool_id is None: return

        stdb_tmp = gcmd.get_float('STDB_TMP', None, minval=0)
        actv_tmp = gcmd.get_float('ACTV_TMP', None, minval=0)
        chng_state = gcmd.get_int('CHNG_STATE', None, minval=0, maxval=2)
        stdb_timeout = gcmd.get_float('STDB_TIMEOUT', None, minval=0)
        shtdwn_timeout = gcmd.get_float('SHTDWN_TIMEOUT', None, minval=0)

        self.log.trace("cmd_KTC_SET_TOOL_TEMPERATURE: T%s: stdb_tmp:%s, actv_tmp:%s, chng_state:%s, stdb_timeout:%s, shtdwn_timeout:%s." % ( str(tool_id), str(stdb_tmp), str(actv_tmp), str(chng_state), str(stdb_timeout), str(shtdwn_timeout) ) )

        if self.printer.lookup_object('ktc_tool ' + str(tool_id)).get_status()["extruder"] is None:
            self.log.trace("cmd_KTC_SET_TOOL_TEMPERATURE: T%s has no extruder! Nothing to do." % str(tool_id))
            return None

        tool = self.printer.lookup_object('ktc_tool ' + str(tool_id))
        set_heater_cmd = {}

        if stdb_tmp is not None:
            set_heater_cmd["heater_standby_temp"] = int(stdb_tmp)
        if actv_tmp is not None:
            set_heater_cmd["heater_active_temp"] = int(actv_tmp)
        if stdb_timeout is not None:
            set_heater_cmd["idle_to_standby_time"] = stdb_timeout
        if shtdwn_timeout is not None:
            set_heater_cmd["idle_to_powerdown_time"] = shtdwn_timeout
        if chng_state is not None:
            set_heater_cmd["heater_state"] = chng_state
            # tool.set_heater(heater_state= chng_state)
        if len(set_heater_cmd) > 0:
            tool.set_heater(**set_heater_cmd)
        else:
            # Print out the current set of temperature settings for the tool if no changes are provided.
            msg = "T%s Current Temperature Settings" % str(tool_id)
            msg += "\n Active temperature %s - %d*C - Active to Standby timer: %d seconds" % ( "*" if tool.heater_state == 2 else " ", tool.heater_active_temp, tool.idle_to_standby_time)
            msg += "\n Standby temperature %s - %d*C - Standby to Off timer: %d seconds" % ( "*" if tool.heater_state == 1 else " ", tool.heater_standby_temp, tool.idle_to_powerdown_time)
            if tool.heater_state != 3:
                if tool.timer_idle_to_standby.get_status()["next_wake"] == True:
                    msg += "\n Will go to standby temperature in in %s seconds." % tool.timer_idle_to_standby.get_status()["next_wake"]
                if tool.timer_idle_to_powerdown.get_status()["counting_down"] == True:
                    msg += "\n Will power down in %s seconds." % tool.timer_idle_to_powerdown.get_status()["next_wake"]
            gcmd.respond_info(msg)

    cmd_KTC_SET_ALL_TOOL_HEATERS_OFF_help = "Turns off all heaters and saves changes made to be resumed by KTC_RESUME_ALL_TOOL_HEATERS."
    def cmd_KTC_SET_ALL_TOOL_HEATERS_OFF(self, gcmd):
        self.set_all_tool_heaters_off()

    def set_all_tool_heaters_off(self):
        all_tools = dict(self.printer.lookup_objects('ktc_tool'))
        self.changes_made_by_set_all_tool_heaters_off = {}

        try:
            for tool_name, tool in all_tools.items():
                if tool.get_status()["extruder"] is None:
                    # self.log.trace("set_all_tool_heaters_off: T%s has no extruder! Nothing to do." % str(tool_name))
                    continue
                if tool.get_status()["heater_state"] == 0:
                    # self.log.trace("set_all_tool_heaters_off: T%s already off! Nothing to do." % str(tool_name))
                    continue
                self.log.trace("set_all_tool_heaters_off: T%s saved with heater_state: %str." % ( str(tool_name), str(tool.get_status()["heater_state"])))
                self.changes_made_by_set_all_tool_heaters_off[tool_name] = tool.get_status()["heater_state"]
                tool.set_heater(heater_state = 0)
        except Exception as e:
            raise Exception('set_all_tool_heaters_off: Error: %s' % str(e))

    cmd_KTC_RESUME_ALL_TOOL_HEATERS_help = "Resumes all heaters previously turned off by KTC_SET_ALL_TOOL_HEATERS_OFF."
    def cmd_KTC_RESUME_ALL_TOOL_HEATERS(self, gcmd):
        self.resume_all_tool_heaters()

    def resume_all_tool_heaters(self):
        try:
            # Loop it 2 times, first for all heaters standby and then the active.

            for tool_name, v in self.changes_made_by_set_all_tool_heaters_off.items():
                if v == 1:
                    self.printer.lookup_object(str(tool_name)).set_heater(heater_state = v)

            for tool_name, v in self.changes_made_by_set_all_tool_heaters_off.items():
                if v == 2:
                    self.printer.lookup_object(str(tool_name)).set_heater(heater_state = v)

        except Exception as e:
            raise Exception('set_all_tool_heaters_off: Error: %s' % str(e))

    cmd_KTC_SET_TOOL_OFFSET_help = "Set an individual tool offset"
    def cmd_KTC_SET_TOOL_OFFSET(self, gcmd):
        tool_id = self._get_tool_id_from_gcmd(gcmd)
        if tool_id is None: return

        x_pos = gcmd.get_float('X', None)
        x_adjust = gcmd.get_float('X_ADJUST', None)
        y_pos = gcmd.get_float('Y', None)
        y_adjust = gcmd.get_float('Y_ADJUST', None)
        z_pos = gcmd.get_float('Z', None)
        z_adjust = gcmd.get_float('Z_ADJUST', None)

        tool = self.printer.lookup_object('ktc_tool ' + str(tool_id))
        set_offset_cmd = {}

        if x_pos is not None:
            set_offset_cmd["x_pos"] = x_pos
        elif x_adjust is not None:
            set_offset_cmd["x_adjust"] = x_adjust
        if y_pos is not None:
            set_offset_cmd["y_pos"] = y_pos
        elif y_adjust is not None:
            set_offset_cmd["y_adjust"] = y_adjust
        if z_pos is not None:
            set_offset_cmd["z_pos"] = z_pos
        elif z_adjust is not None:
            set_offset_cmd["z_adjust"] = z_adjust
        if len(set_offset_cmd) > 0:
            tool.set_offset(**set_offset_cmd)

    cmd_KTC_SET_GLOBAL_OFFSET_help = "Set the global tool offset"
    def cmd_KTC_SET_GLOBAL_OFFSET(self, gcmd):
        x_pos = gcmd.get_float('X', None)
        x_adjust = gcmd.get_float('X_ADJUST', None)
        y_pos = gcmd.get_float('Y', None)
        y_adjust = gcmd.get_float('Y_ADJUST', None)
        z_pos = gcmd.get_float('Z', None)
        z_adjust = gcmd.get_float('Z_ADJUST', None)

        if x_pos is not None:
            self.global_offset[0] = float(x_pos)
        elif x_adjust is not None:
            self.global_offset[0] = float(self.global_offset[0]) + float(x_adjust)
        if y_pos is not None:
            self.global_offset[1] = float(y_pos)
        elif y_adjust is not None:
            self.global_offset[1] = float(self.global_offset[1]) + float(y_adjust)
        if z_pos is not None:
            self.global_offset[2] = float(z_pos)
        elif z_adjust is not None:
            self.global_offset[2] = float(self.global_offset[2]) + float(z_adjust)

        self.log.trace("Global offset now set to: %f, %f, %f." % (float(self.global_offset[0]), float(self.global_offset[1]), float(self.global_offset[2])))

    def SaveFanSpeed(self, fanspeed):
        self.saved_fan_speed = float(fanspeed)
       
    cmd_KTC_SAVE_POSITION_help = "Save the specified G-Code position for later restore."
#   Saves the axis positions to be restored.
#   Without parameters it will set to not restoring axis.
    def cmd_KTC_SAVE_POSITION(self, gcmd):
        param_X = gcmd.get_float('X', None)
        param_Y = gcmd.get_float('Y', None)
        param_Z = gcmd.get_float('Z', None)
        self.SavePosition(param_X, param_Y, param_Z)

    def SavePosition(self, param_X = None, param_Y = None, param_Z = None):
        self.saved_position = [param_X, param_Y, param_Z]

        restore_axis = ''
        if param_X is not None:
            restore_axis += 'X'
        if param_Y is not None:
            restore_axis += 'Y'
        if param_Z is not None:
            restore_axis += 'Z'
        self.restore_axis_on_toolchange = restore_axis

    cmd_KTC_SAVE_CURRENT_POSITION_help = "Save the current G-Code position."
#  Saves current position. 
#  RESTORE_POSITION_TYPE= Type of restore, optional. If not specified, restore_position_on_toolchange_type will not be changed.
#    0: No restore
#    1: Restore XY
#    2: Restore XYZ
#    XYZ: Restore specified axis

    def cmd_KTC_SAVE_CURRENT_POSITION(self, gcmd):
        # Save optional RESTORE_POSITION_TYPE parameter to restore_position_on_toolchange_type variable.
        restore_axis = ktc_parse_restore_type(gcmd, 'RESTORE_POSITION_TYPE')
        self.SaveCurrentPosition(restore_axis)

    def SaveCurrentPosition(self, restore_axis = None):
        if restore_axis is not None:
            self.restore_axis_on_toolchange = restore_axis        
        gcode_move = self.printer.lookup_object('gcode_move')
        self.saved_position = gcode_move._get_gcode_position()

    cmd_KTC_RESTORE_POSITION_help = "Restore a previously saved G-Code position."
#  Restores the previously saved possition.
#   With no parameters it will Restore to previousley saved type.
#  RESTORE_POSITION_TYPE= Type of restore, optional. If not specified, previousley saved restore_position_on_toolchange_type will be used.
#    0: No restore
#    1: Restore XY
#    2: Restore XYZ
#    XYZ: Restore specified axis
    def cmd_KTC_RESTORE_POSITION(self, gcmd):
        self.restore_axis_on_toolchange = ktc_parse_restore_type(gcmd, 'RESTORE_POSITION_TYPE', default=self.restore_axis_on_toolchange)
        self.log.trace("KTC_RESTORE_POSITION running: " + str(self.restore_axis_on_toolchange))
        speed = gcmd.get_int('F', None)

        if not self.restore_axis_on_toolchange:
            return # No axis to restore

        if self.saved_position is None:
            raise gcmd.error("No previously saved g-code position.")

        try:
            p = self.saved_position
            cmd = 'G1'
            for t in self.restore_axis_on_toolchange:
                cmd += ' %s%.3f' % (t, p[XYZ_TO_INDEX[t]])
            if speed:
                cmd += " F%i" % (speed,)

            # Restore position
            self.log.trace("KTC_RESTORE_POSITION running: " + cmd)
            self.gcode.run_script_from_command(cmd)
        except:
            raise gcmd.error("Could not restore position.")

    cmd_KTC_SET_GCODE_OFFSET_FOR_CURRENT_TOOL_help = "Set G-Code offset to the one of current tool."
#  Sets the G-Code offset to the one of the current tool.
#   With no parameters it will not move the toolhead.
#  MOVE= If should move the toolhead, optional. If not specified, it will not move.
#    0: No move
#    1: Move
    def cmd_KTC_SET_GCODE_OFFSET_FOR_CURRENT_TOOL(self, gcmd):
        current_tool_id = int(self.get_status()['active_tool']) 

        self.log.trace("Setting offsets to those of T" + str(current_tool_id) + ".")

        if current_tool_id <= ktc_toolchanger.TOOL_UNLOCKED:
            msg = "KTC_SET_GCODE_OFFSET_FOR_CURRENT_TOOL: Unknown tool mounted. Can't set offsets."
            self.log.always(msg)
            # raise self.printer.command_error(msg)
        else:
            # If optional MOVE parameter is passed as 0 or 1
            param_Move = gcmd.get_int('MOVE', 0, minval=0, maxval=1)
            current_tool = self.printer.lookup_object('ktc_tool ' + str(current_tool_id))
            self.log.trace("SET_GCODE_OFFSET X=%s Y=%s Z=%s MOVE=%s" % (str(current_tool.offset[0]), str(current_tool.offset[1]), str(current_tool.offset[2]), str(param_Move)))
            self.gcode.run_script_from_command("SET_GCODE_OFFSET X=%s Y=%s Z=%s MOVE=%s" % (str(current_tool.offset[0]), str(current_tool.offset[1]), str(current_tool.offset[2]), str(param_Move)))

###########################################
# TOOL REMAPING                           #
###########################################

    def _set_tool_to_tool(self, from_tool, to_tool):
        #Check first if to_tool is a valid tool.
        tools = self.printer.lookup_objects('ktc_tool')
        if not [item for item in tools if item[0] == ('ktc_tool ' + str(to_tool))]:
            self.log.always("Tool %s not a valid tool" % str(to_tool))
            return False

        # Set the new tool.
        self.tool_map[from_tool] = to_tool
        self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=%s VALUE='%s'" % (VARS_KTC_TOOL_MAP, self.tool_map))

    def _tool_map_to_human_string(self):
        msg = "Number of tools remaped: " + str(len(self.tool_map))

        for from_tool, to_tool in self.tool_map.items():
            msg += "\nTool %s-> Tool %s" % ( str(from_tool), str(to_tool))

        return msg

    def tool_is_remaped(self, tool_to_check):
        if tool_to_check in self.tool_map:
            return self.tool_map[tool_to_check]
        else:
            return -1

    def _remap_tool(self, tool, gate, available):
        self._set_tool_to_tool(tool, gate)
        # self._set_tool_status(gate, available)

    def _reset_tool_mapping(self):
        self.log.debug("Resetting Tool map")
        self.tool_map = {}
        self.gcode.run_script_from_command("SAVE_VARIABLE VARIABLE=%s VALUE='%s'" % (VARS_KTC_TOOL_MAP, self.tool_map))

### GCODE COMMANDS FOR TOOL REMAP LOGIC ##################################

    cmd_KTC_DISPLAY_TOOL_MAP_help = "Display the current mapping of tools to other KTC tools." # Used with endless spool" in the future
    def cmd_KTC_DISPLAY_TOOL_MAP(self, gcmd):
        summary = gcmd.get_int('SUMMARY', 0, minval=0, maxval=1)
        self.log.always(self._tool_map_to_human_string())

    cmd_KTC_REMAP_TOOL_help = "Remap a tool to another one."
    def cmd_KTC_REMAP_TOOL(self, gcmd):
        reset = gcmd.get_int('RESET', 0, minval=0, maxval=1)
        if reset == 1:
            self._reset_tool_mapping()
        else:
            from_tool = gcmd.get_int('TOOL', -1, minval=0)
            to_tool = gcmd.get_int('SET', minval=0)
            available = 1 #gcmd.get_int('AVAILABLE', -1, minval=0, maxval=1)  #For future endless spool mode.
            # if available == -1:
            #     available = self.tool_status[to_tool]
            if from_tool != -1:
                self._remap_tool(from_tool, to_tool, available)
            # else:
            #     self._set_tool_status(to_tool, available)
        self.log.info(self._tool_map_to_human_string())

### GCODE COMMANDS FOR waiting on endstop (Jubilee sytle toollock) ##################################

    cmd_KTC_ENDSTOP_QUERY_help = "Wait for a ENDSTOP= untill it is TRIGGERED=0/[1] or ATEMPTS=#"
    def cmd_KTC_ENDSTOP_QUERY(self, gcmd):
        endstop_name = gcmd.get('ENDSTOP') #'manual_stepper tool_lock'
        should_be_triggered = bool(gcmd.get_int('TRIGGERED', 1, minval=0, maxval=1))
        atempts = gcmd.get_int('ATEMPTS', -1, minval=1)
        self.query_endstop(endstop_name, should_be_triggered, atempts)

    def query_endstop(self, endstop_name, should_be_triggered=True, atempts=-1):
        # Get endstops
        endstop = None
        query_endstops = self.printer.lookup_object('query_endstops')
        for es, name in query_endstops.endstops:
            if name == endstop_name:
                endstop = es
                break
        if endstop is None:
            raise Exception("Unknown endstop '%s'" % (endstop_name))

        toolhead = self.printer.lookup_object("toolhead")
        eventtime = self.reactor.monotonic()

        dwell = 0.1
        if atempts == -1:
            dwell = 1.0

        i=0
        while not self.printer.is_shutdown():
            i += 1
            last_move_time = toolhead.get_last_move_time()
            is_triggered = bool(endstop.query_endstop(last_move_time))
            self.log.trace("Check #%d of %s endstop: %s" % (i, endstop_name, ("Triggered" if is_triggered else "Not Triggered")))
            if is_triggered == should_be_triggered:
                break
            # If not running continuesly then check for atempts.
            if atempts > 0 and atempts <= i:
                break
            eventtime = self.reactor.pause(eventtime + dwell)
        # if i > 1 or atempts == 1:
        # self.log.debug("Endstop %s is %s Triggered after #%d checks." % (endstop_name, ("" if is_triggered else "Not"), i))

        self.last_endstop_query[endstop_name] = is_triggered

    def get_status(self, eventtime= None):
        status = {
            "global_offset": self.global_offset,
            "active_tool": self.active_tool,
            "saved_fan_speed": self.saved_fan_speed,
            "restore_axis_on_toolchange": self.restore_axis_on_toolchange,
            "saved_position": self.saved_position,
            "last_endstop_query": self.last_endstop_query,
            ** self.params
        }
        return status

    def _get_tool_from_gcmd(self, gcmd):
        tool_name = gcmd.get('TOOL', None)
        tool_nr = gcmd.get_int('T', None)
        if tool_name:
            tool = self.printer.lookup_object(tool_name)
        elif tool_nr is not None:
            tool = self.lookup_tool(tool_nr)
            if not tool:
                raise gcmd.error("SET_TOOL_TEMPERATURE: T%d not found" % (tool_nr))
        else:
            tool = self.active_tool
            if not tool:
                raise gcmd.error("SET_TOOL_TEMPERATURE: No tool specified and no active tool")
        return tool

###########################################
# Static Class functions
###########################################

# parses legacy type into string of axis names.
# Raises gcode error on fail
def ktc_parse_restore_type(gcmd, arg_name, default = None):
    type = gcmd.get(arg_name, None)
    if type is None:
        return default
    elif type == '0':
        return ''
    elif type == '1':
        return 'XY'
    elif type == '2':
        return 'XYZ'
    # Validate this is XYZ
    for c in type:
        if c not in XYZ_TO_INDEX:
            raise gcmd.error("Invalid RESTORE_POSITION_TYPE")
    return type

# Parses a string into a list of floats.
def get_params_dict(config):
    result = {}
    for option in config.get_prefix_options('params_'):
        try:
            result[option] = ast.literal_eval(config.get(option))
        except ValueError as e:
            raise config.error(
                "Option '%s' in section '%s' is not a valid literal" % (
                    option, config.get_name()))
    return result

def load_config(config):
    return ktc(config)
