# KTC - Klipper Tool Changer code (v.2)
# Tool module, for each tool.
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from typing import TYPE_CHECKING
from . import ktc   # Toolchanger has a type check on ln 210.

if TYPE_CHECKING:
    import configfile
    import klippy
    import gcode
    from . import ktc_log, ktc_toolchanger


class KtcTool(ktc.KtcBaseClass):
    """Class for a single tool in the toolchanger."""
    HEATER_STATE_OFF = 0
    HEATER_STATE_STANDBY = 1
    HEATER_STATE_ACTIVE = 2

    def __init__(self, config = None, name: str = "", number: int = -3):
        # Initialize all static variables before loading from config so we can declare constant tools in ktc.
        self.config = config
        self._toolchanger = None            # Internal Toolchanger object. Used for property setter.

        self.name: str = name               # Name of the tool.
        self.number: int = number           # Tool number to register this tool as. Default as not defined, -3.
        self.extruder = None                # Name of extruder connected to this tool. Defaults to None.
        self.params = {}
        
        # TODO: Change this to a list of fans.
        self.fan = None                     # Name of general fan configuration connected to this tool as a part fan. Defaults to "none".

        self.requires_axis_homed: str = ""  # If set to "X", "Y", "Z" or a combination of them, then the tool will require the axis to be homed before it can be selected. Defaults to "".
        self.lazy_home_when_parking = None  # (default: 0 - disabled) - When set to 1, will home unhomed XY axes if needed and will not move any axis if already homed and parked. 2 Will also home Z if not homed.
                                            # Wipe. -1 = none, 1= Only load filament, 2= Wipe in front of carriage, 3= Pebble wiper, 4= First Silicone, then pebble. Defaults to None.
        self.zone = None                    # Position of the parking zone in the format X, Y, Z. Defaults to None.
        self.park = None                    # Position to move to when fully parking the tool in the dock in the format X, Y

        self.offset = None                  # Offset of the nozzle in the format X, Y, Z

        #TODO: Removed from config. Need to be removed from code.
        self.is_virtual = False
        self.parentTool_id = -2 #self.ktc.TOOL_NONE_N      # Parent tool is used as a Physical parent for all tools of this group. Only used if the tool i virtual. None gets remaped to -1.
        self.parentTool = None              # Initialize physical parent as a dummy object.


        # self.pickup_gcode = None            # The plain gcode string for pickup of the tool.
        # self.dropoff_gcode = None           # The plain gcode string for droppoff of the tool.

        #TODO: Needs moving to regular gcode.
        self.virtual_toolload_gcode = None  # The plain gcode string is to load for virtual tool having this tool as parent. This is for loading the virtual tool.
        self.virtual_toolunload_gcode = None# The plain gcode string is to unload for virtual tool having this tool as parent. This is for unloading the virtual tool.

        self.unload_virtual_at_dropoff = None          # If it takes long time to unload/load it may be faster to leave it loaded and force unload at end of print.

        self.virtual_loaded = -1            # The abstract tool loaded in the physical tool.



        self.heater_state = 0               # 0 = off, 1 = standby temperature, 2 = active temperature. Placeholder.
        self.timer_idle_to_standby = None   # Timer to set temperature to standby temperature after idle_to_standby_time seconds. Set if this tool has an extruder.
        self.timer_idle_to_powerdown = None # Timer to set temperature to 0 after idle_to_powerdown_time seconds. Set if this tool has an extruder.
        self.heater_active_temp = 0         # Temperature to set when in active mode. Placeholder. Requred on Physical and virtual tool if any has extruder.
        self.heater_standby_temp = 0        # Temperature to set when in standby mode.  Placeholder. Requred on Physical and virtual tool if any has extruder.
        self.idle_to_standby_time = 0.1    # Time in seconds from being parked to setting temperature to standby the temperature above. Use 0.1 to change imediatley to standby temperature. Requred on Physical tool
        self.idle_to_powerdown_time = 600   # Time in seconds from being parked to setting temperature to 0. Use something like 86400 to wait 24h if you want to disable. Requred on Physical tool.


        # If called without config then just return a dummy object.
        if config is None:
            return

        # Initialize object references.
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.ktc : 'ktc.Ktc' = self.printer.load_object(config, 'ktc')
        self.log : 'ktc_log.KtcLog' = self.printer.load_object(config, 'ktc_log')

        ##### Name #####
        self.name = config.get_name().split(" ", 1)[1]
        if self.name == self.ktc.TOOL_NONE.name or self.name == self.ktc.TOOL_UNKNOWN.name:
            raise config.error(
                    "Name of section '%s' is not well formated. Name is reserved for internal use."
                    % (config.get_name()))

        ##### Tool Number #####
        # Will be added to the ktc.tools_by_number dict in ktc._config_tools()
        self.number = config.getint('tool_number', None)
        

        ###### Inherited parameters from toolchanger #####
        # Empty parameters are overriden after the toolchanger is loaded.
        # Tool Selection and Deselection G-Code macros
        self.tool_select_gcode_template = self.gcode_macro.load_template(self.config, "tool_select_gcode", "")
        self.tool_deselect_gcode_template = self.gcode_macro.load_template(self.config, "tool_deselect_gcode", "")
        
        ##### Inherited Parameters #####
        # self.requires_axis_homed = self.config_get('requires_axis_homed')
        _ = self.config.get('requires_axis_homed', "")

        ##### Toolchanger #####
        # If none, then the default toolchanger will be set in ktc._config_default_toolchanger()
        toolchanger_name = config.get('toolchanger', None)
        if toolchanger_name is not None:
            self.toolchanger = self.printer.load_object(config, "ktc_toolchanger " + toolchanger_name)

        ##### Params #####
        self.params = self.ktc.get_params_dict_from_config(config)

        ##### Physical Parent #####
        self.parentTool_id = config.getint('parent_tool', self.ktc.TOOL_NONE_N)

        # TODO: Change this to use the ktc_toolchanger instead of parentTool.
        self.parentTool = KtcTool()     # Initialize physical parent as a dummy object.
        try:
            if self.parentTool_id >= 0 and not self.parentTool_id == int(self.number):
                self.parentTool = self.printer.lookup_object("ktc_tool " + str(self.parentTool_id))
        except Exception as e:
            raise config.error(
                    "Physical parent of section '%s' is not well formated: %s"
                    % (config.get_name(), str(e)))

        ##### Is Virtual #####     # Might be deprecated in future.
        if self.parentTool_id != self.ktc.TOOL_NONE_N:
            self.is_virtual = True
       
        ##### Extruder #####
        self.extruder = self._config_get('extruder')

        ##### Fan #####
        self.fan = self._config_get('fan')

        ##### Lazy Home when parking #####
        self.lazy_home_when_parking = False # self._config_getbool('lazy_home_when_parking', False)

        ##### Coordinates #####
        try:
            self.zone = self._config_get('zone')
            if not isinstance(self.zone, list):
                self.zone = str(self.zone).split(',')
            self.park = self._config_get('park')
            if not isinstance(self.park, list):
                self.park = str(self.park).split(',')
            self.offset = self._config_get('offset')
            if not isinstance(self.offset, list):
                self.offset = str(self.offset).split(',')

            # Remove any accidental blank spaces.
            self.zone = [s.strip() for s in self.zone]
            self.park = [s.strip() for s in self.park]
            self.offset = [s.strip() for s in self.offset]

            if len(self.zone) != 3:
                raise config.error("zone Offset is malformed, must be a list of x,y,z If you want it blank, use 0,0,0")
            if len(self.park) != 3:
                raise config.error("park Offset is malformed, must be a list of x,y,z If you want it blank, use 0,0,0")
            if len(self.offset) != 3:
                raise config.error("offset Offset is malformed, must be a list of x,y,z. If you want it blank, use 0,0,0")

        except Exception as e:
            raise config.error(
                    "Coordinates of section '%s' is not well formated: %s"
                    % (config.get_name(), str(e)))

        ##### Standby settings (if the tool has an extruder) #####
        if self.extruder is not None:
            self.idle_to_standby_time = self._config_getfloat("idle_to_standby_time", self.idle_to_standby_time)

            self.idle_to_powerdown_time = self._config_getfloat("idle_to_powerdown_time", self.idle_to_powerdown_time)
            # if self.idle_to_powerdown_time is None:
            #     self.idle_to_powerdown_time = self.toolgroup.idle_to_powerdown_time

            # TODO: Change this to use the ktc_toolchanger instead of parentTool.
            # If this tool has a diffrent parent than itself and it's extruder is diffrent
            if self.parentTool_id > self.ktc.TOOL_NONE_N and self.parentTool_id != int(self.number) and self.extruder != self.parentTool.extruder:
                # Use parent's timer for the child tool.
                self.timer_idle_to_standby = self.parentTool.get_timer_to_standby()
                self.timer_idle_to_powerdown = self.parentTool.get_timer_to_powerdown()
            else:
                # Set up new timers.
                self.timer_idle_to_standby = ktc_ToolStandbyTempTimer(self.printer, self.name, ktc_ToolStandbyTempTimer.TIMER_TO_STANDBY)
                self.timer_idle_to_powerdown = ktc_ToolStandbyTempTimer(self.printer, self.name, ktc_ToolStandbyTempTimer.TIMER_TO_SHUTDOWN)

        ##### G-Code VirtualToolChange #####
        if self.is_virtual:
            self.virtual_toolload_gcode_template = self._get_gcode_template_with_inheritence('virtual_toolload_gcode')
            self.virtual_toolunload_gcode_template = self._get_gcode_template_with_inheritence('virtual_toolunload_gcode')

        ##### Register Tool select command #####
        if self.number is not None:
            self.gcode.register_command("KTC_T" + str(self.number), self.cmd_SelectTool, desc=self.cmd_SelectTool_help)
            
        ##### Add to list of tools #####
        self.ktc.tools[self.name] = self
        if self.toolchanger is not None:
            self.toolchanger.tools[self.name] = self
            
    @property
    def toolchanger(self) -> 'ktc_toolchanger.KtcToolchanger':
        return self._toolchanger
    
    @toolchanger.setter
    def toolchanger(self, value):
        # TODO: Change this to use the base class instead of the specific class.
        if not isinstance(value, ktc.KtcBaseClass):
            raise ValueError("Toolchanger must be a KtcToolchanger object.")
        self._toolchanger = value
        self.configure_inherited_params()
        
    def configure_inherited_params(self):
        if self.config is None: return
        ##### G-Code ToolChange #####
        self.tool_select_gcode_template = self.gcode_macro.load_template(self.config, "tool_select_gcode", self.toolchanger.tool_select_gcode)
        self.tool_deselect_gcode_template = self.gcode_macro.load_template(self.config, "tool_deselect_gcode", self.toolchanger.tool_deselect_gcode)
        
        ##### Inherited Parameters #####
        self.requires_axis_homed = self.config.get('requires_axis_homed', self.toolchanger.requires_axis_homed)
        if self.requires_axis_homed != "": 
            self.log.trace("KTC Tool %s requires_axis_homed: %s" % (self.name, self.requires_axis_homed))


    def _config_getbool(self, config_param, default_value = None):
        inherited_value = default_value
        if self.parentTool.config is not None:
            inherited_value = self.parentTool.config.getboolean(config_param, default_value)
        return self.config.getboolean(config_param, inherited_value)

    def _config_getfloat(self, config_param, default_value = None):
        inherited_value = default_value
        if self.parentTool.config is not None:
            inherited_value = self.parentTool.config.getfloat(config_param, default_value)
        return self.config.getfloat(config_param, inherited_value)

    def _config_get(self, config_param, default_value = None):
        inherited_value = default_value
        if self.parentTool.config is not None:
            inherited_value = self.parentTool.config.get(config_param, default_value)
        return self.config.get(config_param, inherited_value)

    def _get_gcode_template_with_inheritence(self, config_param, optional = False):
        temp_gcode = self.parentTool.get_config(config_param)                   # First try to get gcode parameter from eventual physical Parent.
        # if temp_gcode is None:                                          # If didn't get any from physical parent,
        #     temp_gcode =  self.toolgroup.get_config(config_param)       # try getting from toolgroup.

        if optional and temp_gcode is None:
            temp_gcode = ""

        # gcode = self.get_config(config_param, temp_gcode)               # Get from this config and fallback on previous.
        template = self.gcode_macro.load_template(self.config, config_param, temp_gcode)
        return template

    def get_config(self, config_param, default = None):
        if self.config is None: return None
        return self.config.get(config_param, default)
        
    cmd_SelectTool_help = "Select Tool"
    def cmd_SelectTool(self, gcmd):
        self.log.trace("KTC T" + str(self.number) + " Selected.")
        # Allow either one.
        restore_mode = self.ktc.ktc_parse_restore_type(gcmd.get('R', None), None)
        restore_mode = self.ktc.ktc_parse_restore_type(gcmd.get('RESTORE_POSITION_TYPE', None), restore_mode)

        # TODO: Change this to use the name mapping instead of number.
        # Check if the requested tool has been remaped to another one.
        tool_is_remaped = self.ktc.tool_is_remaped(self.number)

        if tool_is_remaped > -1:
            self.log.always("ktc_Tool %d is remaped to Tool %d" % (self.number, tool_is_remaped))
            remaped_tool = self.printer.lookup_object('ktc_tool ' + str(tool_is_remaped))
            remaped_tool.select_tool_actual(restore_mode)
            return
        else:
            self.select_tool_actual(restore_mode)

    # To avoid recursive remaping.
    def select_tool_actual(self, restore_mode = None):
        current_tool_id = int(self.ktc.active_tool_n)

        self.log.trace("Current Tool is T" + str(current_tool_id) + ".")
        # self.log.trace("This tool is_virtual is " + str(self.is_virtual) + ".")

        if current_tool_id == self.number:              # If trying to select the already selected tool:
            return                                      # Exit

        if current_tool_id == self.ktc.TOOL_UNKNOWN.number:
            msg = "KtcTool.select_tool_actual: Unknown tool already mounted Can't park it before selecting new tool."
            self.log.always(msg)
            raise self.printer.command_error(msg)
        
        self.log.tool_stats[self.name].selects_started += 1


        if self.extruder is not None:               # If the new tool to be selected has an extruder prepare warmup before actual tool change so all unload commands will be done while heating up.
            self.set_heater(heater_state = self.HEATER_STATE_ACTIVE)

        # If optional RESTORE_POSITION_TYPE parameter is passed then save current position.
        # Otherwise do not change either the restore_axis_on_toolchange or saved_position.
        # This makes it possible to call SAVE_POSITION or SAVE_CURRENT_POSITION before the actual T command.
        if restore_mode is not None:
            self.ktc.SaveCurrentPosition(restore_mode) # Sets restore_axis_on_toolchange and saves current position

        # Drop any tools already mounted if not virtual on same.
        if current_tool_id > self.ktc.TOOL_NONE_N:              # If there is a current tool already selected and it's a known tool.
            # TODO: Change this to nicer code.
            self.log.track_tool_selected_end(self.ktc.tools_by_number[current_tool_id]) # Log that the current tool is to be unmounted.

            current_tool = self.printer.lookup_object('ktc_tool ' + str(current_tool_id))
           
            # If the next tool is not another virtual tool on the same physical tool.
            if int(self.parentTool_id ==  self.ktc.TOOL_NONE_N or 
                        self.parentTool_id) !=  int( 
                        current_tool.get_status()["parentTool_id"]
                        ):
                self.log.info("Will Dropoff():%s" % str(current_tool_id))
                current_tool.Dropoff()
                current_tool_id = self.ktc.TOOL_NONE_N
            else: # If it's another virtual tool on the same parent physical tool.
                self.log.info("Dropoff: T" + str(current_tool_id) + "- Virtual - Running UnloadVirtual")
                current_tool.UnloadVirtual()



        # Now we asume tool has been dropped if needed be.

        # Check if this is a virtual tool.
        if not self.is_virtual:
            self.log.trace("cmd_SelectTool: T%s - Not Virtual - Pickup" % str(self.number))
            self.Pickup()
        else:
            if current_tool_id > self.ktc.TOOL_NONE_N:                 # If still has a selected tool: (This tool is a virtual tool with same physical tool as the last)
                current_tool = self.printer.lookup_object('ktc_tool ' + str(current_tool_id))
                self.log.trace("cmd_SelectTool: T" + str(self.number) + "- Virtual - Physical Tool is not Dropped - ")
                if self.parentTool_id > self.ktc.TOOL_NONE_N and self.parentTool_id == current_tool.get_status()["parentTool_id"]:
                    self.log.trace("cmd_SelectTool: T" + str(self.number) + "- Virtual - Same physical tool - Pickup")
                    self.LoadVirtual()
                else:
                    msg = "cmd_SelectTool: T" + str(self.number) + "- Virtual - Not Same physical tool"
                    msg += "Shouldn't reach this because it is dropped in previous."
                    self.log.debug(msg)
                    raise Exception(msg)
            else: # New Physical tool with a virtual tool.
                parentTool = self.printer.lookup_object('ktc_tool ' + str(self.parentTool_id))
                parentTool_virtual_loaded = parentTool.get_status()["virtual_loaded"]
                self.log.trace("cmd_SelectTool: T" + str(self.number) + "- Virtual - Picking upp physical tool")
                self.Pickup()

                # If the new physical tool already has another virtual tool loaded:
                if parentTool_virtual_loaded > self.ktc.TOOL_NONE_N:
                    # TODO: Change this to use the name mapping instead of number.
                    if parentTool_virtual_loaded != self.number:
                        self.log.info("cmd_SelectTool: T" + str(parentTool_virtual_loaded) + "- Virtual - Running UnloadVirtual")

                        uv : KtcTool = self.printer.lookup_object('ktc_tool ' + str(parentTool_virtual_loaded))
                        if uv.extruder is not None:               # If the new tool to be selected has an extruder prepare warmup before actual tool change so all unload commands will be done while heating up.
                            curtime = self.printer.get_reactor().monotonic()
                            # heater = self.printer.lookup_object(self.extruder).get_heater()

                            uv.set_heater(heater_state = self.HEATER_STATE_ACTIVE)
                            # if int(self.heater_state) == self.HEATER_STATE_ACTIVE and int(self.heater_standby_temp) < int(heater.get_status(curtime)["temperature"]):
                            self.ktc._Temperature_wait_with_tolerance(curtime, self.extruder, 2)
                        uv.UnloadVirtual()
                        self.set_heater(heater_state = self.HEATER_STATE_ACTIVE)


                self.log.trace("cmd_SelectTool: T" + str(self.number) + "- Virtual - Picked up physical tool and now Loading virtual tool.")
                self.LoadVirtual()

        self.ktc.active_tool = self
        self.log.track_tool_selected_start(self)


    def Pickup(self):
        self.log.track_tool_selecting_start(self)                 # Log the time it takes for tool mount.

        # Check if homed
        if not self.ktc.printer_is_homed_for_toolchange():
            raise self.printer.command_error("KtcTool.Pickup: Printer not homed and Lazy homing option for tool %s is: %s" % (self.name, str(self.lazy_home_when_parking)))

        # If has an extruder then activate that extruder.
        if self.extruder is not None:
            self.gcode.run_script_from_command(
                "ACTIVATE_EXTRUDER extruder=%s" % 
                (self.extruder))

        # Run the gcode for pickup.
        try:
            context = self.tool_select_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            self.tool_select_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception("Pickup gcode: Script running error: %s" % (str(e)))

        # Restore fan if has a fan.
        if self.fan is not None:
            self.gcode.run_script_from_command(
                "SET_FAN_SPEED FAN=" + self.fan + " SPEED=" + str(self.ktc.get_status()['saved_fan_speed']))

        # Save current picked up tool and print on screen.
        self.ktc.active_tool = self
        if self.is_virtual:
            self.log.always("Physical Tool for T%d picked up." % (self.number))
        else:
            self.log.always("T%d picked up." % (self.number))

        self.log.track_tool_selecting_end(self)

    def Dropoff(self, force_virtual_unload = False):
        self.log.always("Dropoff: T%s - Running." % str(self.number))

        self.log.track_tool_selected_end(self) # Log that the current tool is to be unmounted.

        # Check if homed
        if not self.ktc.printer_is_homed_for_toolchange():
            self.log.always("KtcTool.Dropoff: Printer not homed and Lazy homing option is: " + str(self.lazy_home_when_parking))
            return None

        # Turn off fan if has a fan.
        if self.fan is not None:
            self.gcode.run_script_from_command(
                "SET_FAN_SPEED FAN=" + self.fan + " SPEED=0" )

        # Check if this is a virtual tool.
        self.log.trace("Dropoff: T" + str(self.number) + "- is_virtual: " + str(self.is_virtual))
        if self.is_virtual:
            # Only dropoff if it is required.
            if self.unload_virtual_at_dropoff or force_virtual_unload:
                self.log.debug("T%s: unload_virtual_at_dropoff: %s, force_virtual_unload: %s" % (str(self.number), str(self.unload_virtual_at_dropoff), str(force_virtual_unload)))
                self.log.info("Dropoff: T" + str(self.number) + "- Virtual - Running UnloadVirtual")
                self.UnloadVirtual()

        self.log.track_tool_deselecting_start(self)                 # Log the time it takes for tool change.
        # Run the gcode for dropoff.
        try:
            context = self.tool_deselect_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            self.tool_deselect_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception("Dropoff gcode: Script running error: %s" % (str(e)))

        self.ktc.active_tool = self.ktc.TOOL_NONE                 # Dropoff successfull
        self.log.track_tool_deselecting_end(self)                 # Log the time it takes for tool change.


    def LoadVirtual(self):
        self.log.info("Loading virtual tool: T%d." % self.number)
        self.log.track_tool_selecting_start(self)                 # Log the time it takes for tool mount.

        # Run the gcode for Virtual Load.
        try:
            context = self.virtual_toolload_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            self.virtual_toolload_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception("virtual_toolload_gcode: Script running error: %s" % (str(e)))

        # TODO: Change this to use the ktc_toolchanger instead of parentTool.
        parentTool = self.printer.lookup_object('ktc_tool ' + str(self.parentTool_id))
        parentTool.set_virtual_loaded(self.number)

        # Save current picked up tool and print on screen.
        self.ktc.active_tool = self
        self.log.trace("Virtual T%d Loaded" % (self.number))
        self.log.track_tool_selecting_end(self)             # Log number of toolchanges and the time it takes for tool mounting.

    def set_virtual_loaded(self, value = -1):
        self.virtual_loaded = value
        self.log.trace("Saved VirtualToolLoaded for T%s as: %s" % (str(self.number), str(value)))


    def UnloadVirtual(self):
        self.log.info("Unloading virtual tool: T%d." % self.number)
        self.log.track_tool_deselecting_start(self)                 # Log the time it takes for tool unload.

        # Run the gcode for Virtual Unload.
        try:
            context = self.virtual_toolunload_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self.ktc.get_status()
            self.virtual_toolunload_gcode_template.run_gcode_from_command(context)
        except Exception as e:
            raise Exception("virtual_toolunload_gcode: Script running error:\n%s" % str(e))

        parentTool = self.printer.lookup_object('ktc_tool ' + str(self.parentTool_id))
        parentTool.set_virtual_loaded(-1)

        # Save current picked up tool and print on screen.
        self.ktc.active_tool = self
        self.log.trace("Virtual T%d Unloaded" % (int(self.number)))

        self.log.track_tool_deselecting_end(self)                 # Log the time it takes for tool unload. 

    def set_offset(self, **kwargs):
        for i in kwargs:
            if i == "x_pos":
                self.offset[0] = float(kwargs[i])
            elif i == "x_adjust":
                self.offset[0] = float(self.offset[0]) + float(kwargs[i])
            elif i == "y_pos":
                self.offset[1] = float(kwargs[i])
            elif i == "y_adjust":
                self.offset[1] = float(self.offset[1]) + float(kwargs[i])
            elif i == "z_pos":
                self.offset[2] = float(kwargs[i])
            elif i == "z_adjust":
                self.offset[2] = float(self.offset[2]) + float(kwargs[i])

        self.log.always("T%d offset now set to: %f, %f, %f." % (int(self.number), float(self.offset[0]), float(self.offset[1]), float(self.offset[2])))

    def _set_state(self, heater_state):
        self.heater_state = heater_state


    def set_heater(self, **kwargs):
        if self.extruder is None:
            self.log.debug("set_heater: T%d has no extruder! Nothing to do." % self.number )
            return None

        # self.log.info("T%d heater is at begingin %s. %s*C" % (self.name, self.heater_state, self.heater_active_temp ))

        heater = self.printer.lookup_object(self.extruder).get_heater()
        curtime = self.printer.get_reactor().monotonic()
        changing_timer = False
        
        # self is always pointing to virtual tool but its timers and extruder are always pointing to the physical tool. When changing multiple virtual tools heaters the statistics can remain open when changing by timers of the parent if another one got in between.
        # Therefore it's important for all heater statistics to only point to physical parent.

        # TODO: Change this to use the ktc_toolchanger instead of parentTool.
        if self.is_virtual == True:
            tool_for_tracking_heater = self.parentTool_id
        else:
            tool_for_tracking_heater = self.name

        # First set state if changed, so we set correct temps.
        if "heater_state" in kwargs:
            chng_state = kwargs["heater_state"]
        for i in kwargs:
            if i == "heater_active_temp":
                self.heater_active_temp = kwargs[i]
                if int(self.heater_state) == self.HEATER_STATE_ACTIVE:
                    heater.set_temp(self.heater_active_temp)
            elif i == "heater_standby_temp":
                self.heater_standby_temp = kwargs[i]
                if int(self.heater_state) == self.HEATER_STATE_STANDBY:
                    heater.set_temp(self.heater_standby_temp)
            elif i == "idle_to_standby_time":
                self.idle_to_standby_time = kwargs[i]
                changing_timer = True
            elif i == "idle_to_powerdown_time":
                self.idle_to_powerdown_time = kwargs[i]
                changing_timer = True

        # If already in standby and timers are counting down, i.e. have not triggered since set in standby, then reset the ones counting down.
        if int(self.heater_state) == self.HEATER_STATE_STANDBY and changing_timer:
            if self.timer_idle_to_powerdown.get_status()["counting_down"] == True:
                self.timer_idle_to_powerdown.set_timer(self.idle_to_powerdown_time, self.name)
                if self.idle_to_powerdown_time > 2:
                    self.log.info("KTC Tool %s: heater will shut down in %s seconds." % (self.name, self.log.seconds_to_human_string(self.idle_to_powerdown_time) ))
            if self.timer_idle_to_standby.get_status()["counting_down"] == True:
                self.timer_idle_to_standby.set_timer(self.idle_to_standby_time, self.name)
                if self.idle_to_standby_time > 2:
                    self.log.info("KTC Tool %s heater will go in standby in %s seconds." % (self.name, self.log.seconds_to_human_string(self.idle_to_standby_time) ))


        # Change Active mode, Continuing with part two of temp changing.:
        if "heater_state" in kwargs:
            if self.heater_state == chng_state:                                                         # If we don't actually change the state don't do anything.
                if chng_state == self.HEATER_STATE_ACTIVE:
                    self.log.trace("set_heater: KTC Tool %s heater state not changed. Setting active temp." % self.name )
                    heater.set_temp(self.heater_active_temp)
                elif chng_state == self.HEATER_STATE_STANDBY:
                    self.log.trace("set_heater: KTC Tool %s heater state not changed. Setting standby temp." % self.name )
                    heater.set_temp(self.heater_standby_temp)
                else:
                    self.log.trace("set_heater: KTC Tool %s heater state not changed." % self.name )
                return None
            if chng_state == self.HEATER_STATE_OFF:                                                                         # If Change to Shutdown
                self.log.trace("set_heater: KTC Tool %s heater state now OFF." % self.name )
                self.timer_idle_to_standby.set_timer(0, self.name)
                self.timer_idle_to_powerdown.set_timer(0.1, self.name)
                # self.log.track_heater_standby_end(self)                                                # Set the standby as finishes in statistics.
                # self.log.track_heater_active_end(self)                                                # Set the active as finishes in statistics.
            elif chng_state == self.HEATER_STATE_ACTIVE:                                                                       # Else If Active
                self.log.trace("set_heater: T%d heater state now ACTIVE." % self.name )
                self.timer_idle_to_standby.set_timer(0, self.name)
                self.timer_idle_to_powerdown.set_timer(0, self.name)
                heater.set_temp(self.heater_active_temp)
                self.log.track_heater_standby_end(self.ktc.tools[tool_for_tracking_heater])     # Set the standby as finishes in statistics.
                self.log.track_heater_active_start(self.ktc.tools[tool_for_tracking_heater])    # Set the active as started in statistics.                                               # Set the active as started in statistics.
            elif chng_state == self.HEATER_STATE_STANDBY:                                                                       # Else If Standby
                self.log.trace("set_heater: T%d heater state now STANDBY." % self.name )
                if int(self.heater_state) == self.HEATER_STATE_ACTIVE and int(self.heater_standby_temp) < int(heater.get_status(curtime)["temperature"]):
                    self.timer_idle_to_standby.set_timer(self.idle_to_standby_time, self.name)
                    self.timer_idle_to_powerdown.set_timer(self.idle_to_powerdown_time, self.name)
                    if self.idle_to_standby_time > 2:
                        self.log.always("KTC Tool %s heater will go in standby in %s seconds." % (self.name, self.log.seconds_to_human_string(self.idle_to_standby_time) ))
                else:                                                                                   # Else (Standby temperature is lower than the current temperature)
                    self.log.trace("set_heater: KTC Tool %s standbytemp:%d;heater_state:%d; current_temp:%d." % (self.name, int(self.heater_state), int(self.heater_standby_temp), int(heater.get_status(curtime)["temperature"])))
                    self.timer_idle_to_standby.set_timer(0.1, self.name)
                    self.timer_idle_to_powerdown.set_timer(self.idle_to_powerdown_time, self.name)
                if self.idle_to_powerdown_time > 2:
                    self.log.always("KTC Tool %s heater will shut down in %s seconds." % (self.name, self.log.seconds_to_human_string(self.idle_to_powerdown_time)))
            self.heater_state = chng_state

        # self.log.info("KTC Tool %s heater is at end %s. %s*C" % (self.name, self.heater_state, self.heater_active_temp ))


    def get_timer_to_standby(self):
        return self.timer_idle_to_standby

    def get_timer_to_powerdown(self):
        return self.timer_idle_to_powerdown

    def get_status(self, eventtime= None):
        status = {
            "name": self.name,
            "number": self.number,
            "toolchanger": self.toolchanger.name,
            "parentTool_id": self.parentTool_id,
            "extruder": self.extruder,
            "fan": self.fan,
            "lazy_home_when_parking": self.lazy_home_when_parking,
            "zone": self.zone,
            "park": self.park,
            "offset": self.offset,
            "heater_state": self.heater_state,
            "heater_active_temp": self.heater_active_temp,
            "heater_standby_temp": self.heater_standby_temp,
            "idle_to_standby_time": self.idle_to_standby_time,
            "idle_to_powerdown_next_wake": self.idle_to_powerdown_time,
            "virtual_loaded": self.virtual_loaded,
            "unload_virtual_at_dropoff": self.unload_virtual_at_dropoff,
            **self.params,
        }
        return status

    # Based on DelayedGcode.
class ktc_ToolStandbyTempTimer:
    TIMER_TO_SHUTDOWN = 0
    TIMER_TO_STANDBY = 1

    def __init__(self, printer, tool_id, temp_type):
        self.printer = printer
        self.tool_id = tool_id
        self.last_virtual_tool_using_physical_timer = None

        self.duration = 0.
        self.temp_type = temp_type      # 0= Time to shutdown, 1= Time to standby.

        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.timer_handler = None
        self.inside_timer = self.repeat = False
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.log = self.printer.lookup_object('ktc_log')

        self.counting_down = False
        self.nextwake = self.reactor.NEVER


    def _handle_ready(self):
        self.timer_handler = self.reactor.register_timer(
            self._standby_tool_temp_timer_event, self.reactor.NEVER)

    def _standby_tool_temp_timer_event(self, eventtime):
        self.inside_timer = True
        self.counting_down = False
        try:
            if self.last_virtual_tool_using_physical_timer is None:
                raise Exception("last_virtual_tool_using_physical_timer is < None")

            tool: KtcTool = self.printer.lookup_object("ktc_tool " + str(self.last_virtual_tool_using_physical_timer))
            if tool.is_virtual == True:
                tool_for_tracking_heater = tool.parentTool_id
            else:
                tool_for_tracking_heater = tool.name

            self.log.trace(
                "_standby_tool_temp_timer_event: Running for T%s. temp_type:%s. %s" % 
                (str(self.tool_id), 
                 "Time to shutdown" if self.temp_type == 0 else "Time to standby", 
                 ("For virtual tool T%s" % str(self.last_virtual_tool_using_physical_timer) ) 
                 if  self.last_virtual_tool_using_physical_timer != self.tool_id else ""))

            temperature = 0
            heater = self.printer.lookup_object(tool.extruder).get_heater()
            if self.temp_type == self.TIMER_TO_STANDBY:
                self.log.track_heater_standby_start(self.tool_id)                                                # Set the standby as started in statistics.
                temperature = tool.get_status()["heater_standby_temp"]
                heater.set_temp(temperature)
            else:
                self.log.track_heater_standby_end(self)                                                # Set the standby as finishes in statistics.

                tool.get_timer_to_standby().set_timer(0, self.last_virtual_tool_using_physical_timer)        # Stop Standby timer.
                tool._set_state(KtcTool.HEATER_STATE_OFF)        # Set off state.
                heater.set_temp(0)        # Set temperature to 0.

            self.log.track_heater_active_end(self)                                               # Set the active as finishes in statistics.

        except Exception as e:
            raise Exception("Failed to set Standby temp for tool T%s: %s. %s" % (str(self.tool_id), 
                                                                                 ("for virtual T%s" % str(self.last_virtual_tool_using_physical_timer)),
                                                                                 str(e)))  # if actual_tool_calling != self.tool_id else ""

        self.nextwake = self.reactor.NEVER
        if self.repeat:
            self.nextwake = eventtime + self.duration
            self.counting_down = True
        self.inside_timer = self.repeat = False
        return self.nextwake

    def set_timer(self, duration, actual_tool_calling):
        actual_tool_calling = actual_tool_calling
        self.log.trace(str(self.timer_handler) + ".set_timer: T%s %s, temp_type:%s, duration:%s." % (
            str(self.tool_id), 
            ("for virtual T%s" % str(actual_tool_calling)) if actual_tool_calling != self.tool_id else "",
            ("Standby" if self.temp_type == 1 else "OFF"), 
            str(duration)))
        self.duration = float(duration)
        self.last_virtual_tool_using_physical_timer = actual_tool_calling
        if self.inside_timer:
            self.repeat = (self.duration != 0.)
        else:
            waketime = self.reactor.NEVER
            if self.duration:
                waketime = self.reactor.monotonic() + self.duration
                self.nextwake = waketime
            self.reactor.update_timer(self.timer_handler, waketime)
            self.counting_down = True

    def get_status(self, eventtime= None):
        status = {
            "temp_type": self.temp_type,
            "duration": self.duration,
            "counting_down": self.counting_down,
            "next_wake": self._time_left(),
        }
        return status

    def _time_left(self):
        if self.nextwake == self.reactor.NEVER:
            return "never"
        else:
            return str( self.nextwake - self.reactor.monotonic() )

    ###########################################
    # Dataclassess for KtcTool
    ###########################################



def load_config_prefix(config):
    return KtcTool(config)
