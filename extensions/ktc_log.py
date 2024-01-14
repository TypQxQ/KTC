# KTC - Klipper Tool Changer code (v.2)
# Log and statistics module
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# Based on and inspired by ERCF-Software-V3      Copyright (C) 2021  moggieuk#6538 (discord)
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

import logging, threading, queue, time, ast
import math, os.path, copy
from . import ktc_save_variables

TRACKED_START_TIME_SELECTED = "tracked_start_time_selected"
TRACKED_START_TIME_ACTIVE = "tracked_start_time_active"
TRACKED_START_TIME_STANDBY = "tracked_start_time_standby"
TRACKED_UNMOUNT_START_TIME = "tracked_unmount_start_time"
TRACKED_MOUNT_START_TIME = "tracked_mount_start_time"


####################################
# Main Logging Class for KTC       #
####################################
class Ktc_Log:
    EMPTY_TOOL_STATS = {'toolmounts_completed': 0, 'toolunmounts_completed': 0, 'toolmounts_started': 0, 'toolunmounts_started': 0, 'time_selected': 0, 'time_heater_active': 0, 'time_heater_standby': 0, TRACKED_START_TIME_SELECTED:0, TRACKED_START_TIME_ACTIVE:0, TRACKED_START_TIME_STANDBY:0, 'total_time_spent_unmounting':0, 'total_time_spent_mounting':0}

    def __init__(self, config):
        # Initialize object variables
        self.config = config
        self.gcode = config.get_printer().lookup_object('gcode')
        self.printer = config.get_printer()

        # Register event handlers
        self.printer.register_event_handler('klippy:connect', self.handle_connect)
        self.printer.register_event_handler("klippy:disconnect", self.handle_disconnect)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

        # Read and load configuration
        self.log_level = config.getint('log_level', 1, minval=0, maxval=3)
        self.logfile_level = config.getint('logfile_level', 3, minval=-1, maxval=4)
        self.log_statistics = config.getint('log_statistics', 0, minval=0, maxval=1)
        self.log_visual = config.getint('log_visual', 1, minval=0, maxval=2)

        # Initialize Logger variable
        self.ktc_logger = None

        # Setup background file based logging before logging any messages
        if self.logfile_level >= 0:
            logfile_path = self.printer.start_args['log_file']
            dirname = os.path.dirname(logfile_path)
            if dirname == None:
                ktc_log = os.path.expanduser('~/ktc.log')
            else:
                ktc_log = dirname + '/ktc.log'
            self.queue_listener = KtcQueueListener(ktc_log)
            self.queue_listener.setFormatter(KtcMultiLineFormatter('%(asctime)s %(message)s', datefmt='%I:%M:%S'))
            queue_handler = KtcQueueHandler(self.queue_listener.bg_queue)
            self.ktc_logger = logging.getLogger('ktc')
            self.ktc_logger.setLevel(logging.INFO)
            self.ktc_logger.addHandler(queue_handler)

        # Register G-code commands
        handlers = [
            'KTC_LOG_TRACE', 'KTC_LOG_DEBUG', 'KTC_LOG_INFO', 'KTC_LOG_ALWAYS', 
            'KTC_SET_LOG_LEVEL', 'KTC_DUMP_STATS', 'KTC_RESET_STATS',
            'KTC_INIT_PRINT_STATS', 'KTC_DUMP_PRINT_STATS']
        for cmd in handlers:
            func = getattr(self, 'cmd_' + cmd)
            desc = getattr(self, 'cmd_' + cmd + '_help', None)
            self.gcode.register_command(cmd, func, False, desc)

    def handle_connect(self):
        # Load the persistent variables object
        self.ktc_persistent : ktc_save_variables.KtcSaveVariables = self.printer.load_object(self.config, 'ktc_save_variables')

        # Load persihabele statitstics 
        self._load_persisted_state()

        # Init persihabele statistics
        self._reset_print_statistics()

    def handle_disconnect(self):
        self.ktc_persistent.disconnect()

    def handle_ready(self):
        self.always('KlipperToolChangerCode Ready')

    def _load_persisted_state(self):
        self.trace("_load_persisted_state: Running.")
        
        stats = self.ktc_persistent.vars.get("Statistics", {})
        if stats is None or stats == {}:
            self.debug("Did not find any saved statistics.")
        
        swap_stats = stats.get("swap", {})
        try:
            if swap_stats is None or swap_stats == {}:
                raise Exception("Couldn't find any saved statistics.")
            self.total_time_spent_mounting = swap_stats['total_time_spent_mounting'] or 0
            self.total_time_spent_unmounting = swap_stats['total_time_spent_unmounting'] or 0
            self.total_toollocks = swap_stats['total_toollocks'] or 0
            self.total_toolunlocks = swap_stats['total_toolunlocks'] or 0
            self.total_toolmounts = swap_stats['total_toolmounts'] or 0
            self.total_toolunmounts = swap_stats['total_toolunmounts'] or 0
        except Exception as e:
            self.debug("Unexpected error while loading persistent swap stats: %s" % e)
            # Initializing statistics if unable to load from file
            self._reset_statistics()

        self.tool_statistics = {}
        for tool in self.printer.lookup_objects('ktc_tool'):
            try:
                toolname=str(tool[0])
                # toolname=toolname[toolname.rindex(' ')+1:]
                toolname=toolname.split(" ", 1)[1]
                self.tool_statistics[toolname] = stats.get("tool_%s" % toolname, self.EMPTY_TOOL_STATS.copy())
                self.tool_statistics[toolname][TRACKED_START_TIME_SELECTED] = 0
                self.tool_statistics[toolname][TRACKED_START_TIME_ACTIVE] = 0
                self.tool_statistics[toolname][TRACKED_START_TIME_STANDBY] = 0
                self.tool_statistics[toolname][TRACKED_UNMOUNT_START_TIME] = 0
                self.tool_statistics[toolname][TRACKED_MOUNT_START_TIME] = 0

            except Exception as e:
                self.debug("Unexpected error while loading persistent tool stats: %s" % e)
                
    def _reset_print_statistics(self):
        # Init persihabele statistics
        self.print_time_spent_mounting = self.total_time_spent_mounting
        self.print_time_spent_unmounting = self.total_time_spent_unmounting
        self.print_toollocks = self.total_toollocks
        self.print_toolunlocks = self.total_toolunlocks
        self.print_toolmounts = self.total_toolmounts
        self.print_toolunmounts = self.total_toolunmounts
        self.print_tool_statistics = copy.deepcopy(self.tool_statistics)

####################################
# LOGGING FUNCTIONS                #
####################################
    def always(self, message):
        if self.ktc_logger:
            self.ktc_logger.info(message)
        self.gcode.respond_info(message)

    def info(self, message):
        if self.ktc_logger and self.logfile_level > 0:
            self.ktc_logger.info(message)
        if self.log_level > 0:
            self.gcode.respond_info(message)

    def debug(self, message):
        message = "- DEBUG: %s" % message
        if self.ktc_logger and self.logfile_level > 1:
            self.ktc_logger.info(message)
        if self.log_level > 1:
            self.gcode.respond_info(message)

    def trace(self, message):
        message = "- - TRACE: %s" % message
        if self.ktc_logger and self.logfile_level > 2:
            self.ktc_logger.info(message)
        if self.log_level > 2:
            self.gcode.respond_info(message)

    # Fun visual display of KTC state
    def _display_visual_state(self):
        if self.log_visual > 0 and not self.calibrating:
            self.always(self._state_to_human_string())

    def _log_level_to_human_string(self, level):
        log = "OFF"
        if level > 2: log = "TRACE"
        elif level > 1: log = "DEBUG"
        elif level > 0: log = "INFO"
        elif level > -1: log = "ESSENTIAL MESSAGES"
        return log

    def _visual_log_level_to_human_string(self, level):
        log = "OFF"
        if level > 1: log = "SHORT"
        elif level > 0: log = "LONG"
        return log



####################################
# STATISTICS FUNCTIONS             #
####################################
    def _reset_statistics(self):
        self.debug("Reseting KTC statistics.")
        # self.total_mounts = 0
        self.total_time_spent_mounting = 0
        self.total_time_spent_unmounting = 0
        self.tracked_mount_start_time = 0
        # self.tracked_unmount_start_time = 0
        self.pause_start_time = 0
        self.total_toollocks = 0
        self.total_toolunlocks = 0
        self.total_toolmounts = 0
        self.total_toolunmounts = 0

        self.tool_statistics = {}
        for tool in self.printer.lookup_objects('ktc_tool'):
            try:
                toolname=str(tool[0])
                toolname=toolname[toolname.rindex(' ')+1:]
                self.tool_statistics[toolname] = self.EMPTY_TOOL_STATS.copy()
                self.tool_statistics[toolname][TRACKED_START_TIME_SELECTED] = 0
                self.tool_statistics[toolname][TRACKED_START_TIME_ACTIVE] = 0
                self.tool_statistics[toolname][TRACKED_START_TIME_STANDBY] = 0
                self.tool_statistics[toolname][TRACKED_UNMOUNT_START_TIME] = 0
                self.tool_statistics[toolname][TRACKED_MOUNT_START_TIME] = 0

            except Exception as e:
                self.debug("Unexpected error in toolstast: %s" % e)


    def track_mount_start(self, tool_id):
        # self.trace("track_mount_start: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics(tool_id, TRACKED_MOUNT_START_TIME, time.time())
        

    def track_mount_end(self, tool_id):
        self.trace("track_mount_end: Running for Tool: %s." % (tool_id))
        start_time = self.tool_statistics[str(tool_id)][TRACKED_MOUNT_START_TIME]
        if start_time is not None and start_time != 0:
            # self.trace("track_mount_end: start_time is not None for Tool: %s." % (tool_id))
            time_spent = time.time() - start_time
            self.increase_tool_statistics(tool_id, 'total_time_spent_mounting', time_spent)
            self.total_time_spent_mounting += time_spent
            self._set_tool_statistics(tool_id, TRACKED_MOUNT_START_TIME, 0)
            self._persist_statistics()
    def track_unmount_start(self, tool_id):
        # self.trace("track_unmount_start: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics(tool_id, TRACKED_UNMOUNT_START_TIME, time.time())
        self.increase_tool_statistics(tool_id, 'toolunmounts_started')

    def track_unmount_end(self, tool_id):
        # self.trace("track_unmount_end: Running for Tool: %s." % (tool_id))
        start_time = self.tool_statistics[str(tool_id)][TRACKED_UNMOUNT_START_TIME]
        if start_time is not None and start_time != 0:
            # self.trace("track_unmount_end: start_time is not None for Tool: %s." % (tool_id))
            time_spent = time.time() - start_time
            self.increase_tool_statistics(tool_id, 'total_time_spent_unmounting', time_spent)
            self.total_time_spent_unmounting += time_spent
            self._set_tool_statistics(tool_id, TRACKED_UNMOUNT_START_TIME, 0)
            self.increase_tool_statistics(tool_id, 'toolunmounts_completed')
            self.increase_statistics('total_toolunmounts')
            self._persist_statistics()


    def increase_statistics(self, key, count=1):
        try:
            # self.trace("increase_statistics: Running. Provided to record tool stats while key: %s and count: %s" % (str(key), str(count)))
            if key == 'total_toolmounts':
                self.total_toolmounts += int(count)
            elif key == 'total_toolunmounts':
                self.total_toolunmounts += int(count)
            elif key == 'total_toollocks':
                self.total_toollocks += int(count)
            elif key == 'total_toolunlocks':
                self.total_toolunlocks += int(count)
            self._persist_statistics()
        except Exception as e:
            self.debug("Exception whilst tracking tool stats: %s" % str(e))
            self.debug("increase_statistics: Error while increasing stats while key: %s and count: %s" % (str(key), str(count)))

    def track_selected_tool_start(self, tool_id):
        # self.trace("track_selected_tool_start: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics(tool_id, TRACKED_START_TIME_SELECTED, time.time())
        self.increase_statistics('total_toolmounts')
        self.increase_tool_statistics(tool_id, 'toolmounts_completed')

    def track_selected_tool_end(self, tool_id):
        # self.trace("track_selected_tool_end: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics_time_diff(tool_id, 'time_selected', TRACKED_START_TIME_SELECTED)
        self._persist_statistics()

    def track_active_heater_start(self, tool_id):
        # self.trace("track_active_heater_start: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics(tool_id, TRACKED_START_TIME_ACTIVE, time.time())

    def track_active_heater_end(self, tool_id):
        # self.trace("track_active_heater_end: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics_time_diff(tool_id, 'time_heater_active', TRACKED_START_TIME_ACTIVE)
        self._persist_statistics()

    def track_standby_heater_start(self, tool_id):
        # self.trace("track_standby_heater_start: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics(tool_id, TRACKED_START_TIME_STANDBY, time.time())

    def track_standby_heater_end(self, tool_id):
        # self.trace("track_standby_heater_end: Running for Tool: %s." % (tool_id))
        self._set_tool_statistics_time_diff(tool_id, 'time_heater_standby', TRACKED_START_TIME_STANDBY)
        self._persist_statistics()

    def _seconds_to_human_string(self, seconds):
        result = ""
        hours = int(math.floor(seconds / 3600.))
        if hours >= 1:
            result += "%d hours " % hours
        minutes = int(math.floor(seconds / 60.) % 60)
        if hours >= 1 or minutes >= 1:
            result += "%d minutes " % minutes
        result += "%d seconds" % int((math.floor(seconds) % 60))
        return result

    def _swap_statistics_to_human_string(self):
        msg = "KTC Statistics:"
        # msg += "\n%d swaps completed" % self.total_mounts
        msg += "\n%s spent mounting tools" % self._seconds_to_human_string(self.total_time_spent_mounting)
        msg += "\n%s spent unmounting tools" % self._seconds_to_human_string(self.total_time_spent_unmounting)
        msg += "\n%d tool locks completed" % self.total_toollocks
        msg += "\n%d tool unlocks completed" % self.total_toolunlocks
        msg += "\n%d tool mounts completed" % self.total_toolmounts
        msg += "\n%d tool unmounts completed" % self.total_toolunmounts
        return msg

    def _swap_print_statistics_to_human_string(self):
        msg = "KTC Statistics for this print:"
        # msg += "\n%d swaps completed" % self.total_mounts
        msg += "\n%s spent mounting tools" % self._seconds_to_human_string(self.total_time_spent_mounting-self.print_time_spent_mounting)
        msg += "\n%s spent unmounting tools" % self._seconds_to_human_string(self.total_time_spent_unmounting-self.print_time_spent_unmounting)
        msg += "\n%d tool locks completed" % (self.total_toollocks-self.print_toollocks)
        msg += "\n%d tool unlocks completed" % (self.total_toolunlocks-self.print_toolunlocks)
        msg += "\n%d tool mounts completed" % (self.total_toolmounts-self.print_toolmounts)
        msg += "\n%d tool unmounts completed" % (self.total_toolunmounts-self.print_toolunmounts)
        return msg

    def _division(self, dividend, divisor):
        try:
            return dividend/divisor
        except ZeroDivisionError:
            return 0

    def _dump_statistics(self, report=False):
        if self.log_statistics or report:
            msg = "ToolChanger Statistics:\n"
            msg += self._swap_statistics_to_human_string()
            msg += "\n------------\n"

            msg += "Tool Statistics:\n"

            # First convert to int so we get right order.
            res = {int(k):v for k,v in self.tool_statistics.items()}
            for tid in res:
                tool_id= str(tid)
                msg += "Tool#%s:\n" % (tool_id)
                msg += "Completed %d out of %d mounts in %s. Average of %s per toolmount.\n" % (self.tool_statistics[str(tool_id)]['toolmounts_completed'], self.tool_statistics[str(tool_id)]['toolmounts_started'], self._seconds_to_human_string(self.tool_statistics[str(tool_id)]['total_time_spent_mounting']), self._seconds_to_human_string(self._division(self.tool_statistics[str(tool_id)]['total_time_spent_mounting'], self.tool_statistics[str(tool_id)]['toolmounts_completed'])))
                msg += "Completed %d out of %d unmounts in %s. Average of %s per toolunmount.\n" % (self.tool_statistics[str(tool_id)]['toolunmounts_completed'], self.tool_statistics[str(tool_id)]['toolunmounts_started'], self._seconds_to_human_string(self.tool_statistics[str(tool_id)]['total_time_spent_unmounting']), self._seconds_to_human_string(self._division(self.tool_statistics[str(tool_id)]['total_time_spent_unmounting'], self.tool_statistics[str(tool_id)]['toolunmounts_completed'])))
                msg += "%s spent selected." % self._seconds_to_human_string(self.tool_statistics[str(tool_id)]['time_selected'])
                tool = self.printer.lookup_object('ktc_tool ' + str(tool_id))
                if tool.is_virtual != True or tool.name==tool.parentTool_id:
                    if tool.extruder is not None:
                        msg += " %s with active heater and %s with standby heater." % (self._seconds_to_human_string(self.tool_statistics[str(tool_id)]['time_heater_active']), self._seconds_to_human_string(self.tool_statistics[str(tool_id)]['time_heater_standby']))
                msg += "\n------------\n"
                

        self.always(msg)

    def _dump_print_statistics(self, report=False):
        if self.log_statistics or report:
            msg = "ToolChanger Statistics for this print:\n"
            msg += self._swap_print_statistics_to_human_string()
            msg += "\n------------\n"

            msg += "Tool Statistics for this print:\n"

            # First convert to int so we get right order.
            res = {int(k):v for k,v in self.tool_statistics.items()}
            for tid in res:
                tool_id= str(tid)
                ts = self.tool_statistics[str(tool_id)]
                pts = self.print_tool_statistics[str(tool_id)]
                msg += "Tool#%s:\n" % (tool_id)
                msg += "Completed %d out of %d mounts in %s. Average of %s per toolmount.\n" % ((ts['toolmounts_completed']-pts['toolmounts_completed']), (ts['toolmounts_started']-pts['toolmounts_started']), self._seconds_to_human_string(ts['total_time_spent_mounting']-pts['total_time_spent_mounting']), self._seconds_to_human_string(self._division((ts['total_time_spent_mounting']-pts['total_time_spent_mounting']), (ts['toolmounts_completed']-ts['toolmounts_completed']))))
                msg += "Completed %d out of %d unmounts in %s. Average of %s per toolunmount.\n" % (ts['toolunmounts_completed']-pts['toolunmounts_completed'], ts['toolunmounts_started']-pts['toolunmounts_started'], self._seconds_to_human_string(ts['total_time_spent_unmounting']-pts['total_time_spent_unmounting']), self._seconds_to_human_string(self._division(ts['total_time_spent_unmounting']-pts['total_time_spent_unmounting'], ts['toolunmounts_completed']-pts['toolunmounts_completed'])))
                msg += "%s spent selected. %s with active heater and %s with standby heater.\n" % (self._seconds_to_human_string(ts['time_selected']-pts['time_selected']), self._seconds_to_human_string(ts['time_heater_active']-pts['time_heater_active']), self._seconds_to_human_string(ts['time_heater_standby']-pts['time_heater_standby']))
                msg += "------------\n"
        self.always(msg)



    def _persist_statistics(self):
        swap_stats = {
            # 'total_mounts': self.total_mounts,
            'total_time_spent_mounting': round(self.total_time_spent_mounting, 1),
            'total_time_spent_unmounting': round(self.total_time_spent_unmounting, 1),
            'total_toolunlocks': self.total_toolunlocks,
            'total_toollocks': self.total_toollocks,
            'total_toolmounts': self.total_toolmounts,
            'total_toolunmounts': self.total_toolunmounts
            }
        try:
            self.ktc_persistent.save_variable("swap", str(swap_stats), section="Statistics")

            for tool in self.tool_statistics:
                self.ktc_persistent.save_variable("tool_%s" % tool, str(self.tool_statistics[tool]), section="Statistics")
        except Exception as e:
            self.debug("Unexpected error whiles saving variables in _persist_statistics: %s" % e)

                
    def increase_tool_statistics(self, tool_id, key, count=1):
        try:
            # self.trace("increase_tool_statistics: Running for Tool: %s. Provided to record tool stats while key: %s and count: %s" % (tool_id, str(key), str(count)))
            # if self.tool_statistics.get(str(tool_id)) is not None:
            if str(tool_id) in self.tool_statistics:
                if self.tool_statistics[str(tool_id)][key] is None:
                    self.tool_statistics[str(tool_id)][key]=0
                # self.trace("increase_tool_statistics: Before running for Tool: %s. Key: %s is: %s" % (tool_id, str(key), str(self.tool_statistics[str(tool_id)][key])))
                if isinstance(count, float):
                    self.tool_statistics[str(tool_id)][key] = round(self.tool_statistics[str(tool_id)][key] + count, 3)
                else:
                    self.tool_statistics[str(tool_id)][key] += count
                # self.trace("increase_tool_statistics: After running for Tool: %s. Key: %s is: %s" % (tool_id, str(key), str(self.tool_statistics[str(tool_id)][key])))
            else:
                self.debug("increase_tool_statistics: Unknown tool provided to record tool stats: %s" % tool_id)
                # self.debug(str(self.tool_statistics))
        except Exception as e:
            self.debug("Exception whilst tracking tool stats: %s" % str(e))
            self.debug("increase_tool_statistics: Error while tool: %s provided to record tool stats while key: %s and count: %s" % (tool_id, str(key), str(count)))
        # self.trace("increase_tool_statistics: Tool: %s provided to record tool stats while key: %s and count: %s" % (tool_id, str(key), str(count)))

    def _set_tool_statistics(self, tool_id, key, value):
        # self.trace("_set_tool_statistics:Running for Tool: %s provided to record tool stats while key: %s and value: %s" % (tool_id, str(key), str(value)))
        try:
            if str(tool_id) in self.tool_statistics:
                self.tool_statistics[str(tool_id)][key] = value
            else:
                self.debug("_set_tool_statistics: Unknown tool: %s provided to record tool stats while key: %s and value: %s" % (tool_id, str(key), str(value)))
        except Exception as e:
            self.debug("Exception whilst tracking tool stats: %s" % str(e))
            self.debug("_set_tool_statistics: Error while tool: %s provided to record tool stats while key: %s and value: %s" % (tool_id, str(key), str(value)))

    def _set_tool_statistics_time_diff(self, tool_id, final_time_key, start_time_key):
        try:
            if str(tool_id) in self.tool_statistics:
                tool_stat= self.tool_statistics[str(tool_id)]
                if tool_stat[start_time_key] is not None and tool_stat[start_time_key] != 0:
                    if tool_stat[final_time_key] is not None and tool_stat[final_time_key] != 0:
                        tool_stat[final_time_key] += time.time() - tool_stat[start_time_key]
                    else:
                        tool_stat[final_time_key] = time.time() - tool_stat[start_time_key]
                    tool_stat[start_time_key] = 0
            else:
                self.debug("_set_tool_statistics_time_diff: Unknown tool: %s provided to record tool stats while final_time_key: %s and start_time_key: %s" % (tool_id, str(final_time_key), str(start_time_key)))
        except Exception as e:
            self.debug("Exception whilst tracking tool stats: %s" % str(e))
            self.debug("_set_tool_statistics_time_diff: Error while tool: %s provided to record tool stats while final_time_key: %s and start_time_key: %s" % (tool_id, str(final_time_key), str(start_time_key)))

### LOGGING AND STATISTICS FUNCTIONS GCODE FUNCTIONS

    cmd_KTC_RESET_STATS_help = "Reset the KTC statistics"
    def cmd_KTC_RESET_STATS(self, gcmd):
        param = gcmd.get('SURE', "no")
        if param.lower() == "yes":
            self._reset_statistics()
            self._reset_print_statistics()
            self._persist_statistics()
            self._dump_statistics(True)
            self.always("Statistics RESET.")
        else:
            message = "Are you sure you want to reset KTC statistics?\n"
            message += "If so, run with parameter SURE=YES:\n"
            message += "KTC_RESET_STATS SURE=YES"
            self.gcode.respond_info(message)

    cmd_KTC_DUMP_STATS_help = "Dump the KTC statistics"
    def cmd_KTC_DUMP_STATS(self, gcmd):
        self._dump_statistics(True)

    cmd_KTC_INIT_PRINT_STATS_help = "Run at start of a print to initialize the KTC print statistics"
    def cmd_KTC_INIT_PRINT_STATS(self, gcmd):
        self._reset_print_statistics()

    cmd_KTC_DUMP_PRINT_STATS_help = "Run at end of a print to list statistics since last print reset."
    def cmd_KTC_DUMP_PRINT_STATS(self, gcmd):
        self._dump_print_statistics(True)

    cmd_KTC_SET_LOG_LEVEL_help = "Set the log level for the KTC"
    def cmd_KTC_SET_LOG_LEVEL(self, gcmd):
        self.log_level = gcmd.get_int('LEVEL', self.log_level, minval=0, maxval=4)
        self.logfile_level = gcmd.get_int('LOGFILE', self.logfile_level, minval=0, maxval=4)

    cmd_KTC_LOG_ALWAYS_help = "Log allways MSG"
    def cmd_KTC_LOG_ALWAYS(self, gcmd):
        msg = gcmd.get('MSG')
        self.always(msg)

    cmd_KTC_LOG_INFO_help = "Log info MSG"
    def cmd_KTC_LOG_INFO(self, gcmd):
        msg = gcmd.get('MSG')
        self.info(msg)

    cmd_KTC_LOG_DEBUG_help = "Log debug MSG"
    def cmd_KTC_LOG_DEBUG(self, gcmd):
        msg = gcmd.get('MSG')
        self.debug(msg)

    cmd_KTC_LOG_TRACE_help = "Log trace MSG"
    def cmd_KTC_LOG_TRACE(self, gcmd):
        msg = gcmd.get('MSG')
        self.trace(msg)

####################################
# LOGGING Que Handling             #
####################################
# Forward all messages through a queue (polled by background thread)
class KtcQueueHandler(logging.Handler):
    def __init__(self, queue):
        logging.Handler.__init__(self)
        self.queue = queue

    def emit(self, record):
        try:
            self.format(record)
            record.msg = record.message
            record.args = None
            record.exc_info = None
            self.queue.put_nowait(record)
        except Exception:
            self.handleError(record)

# Poll log queue on background thread and log each message to logfile
class KtcQueueListener(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename):
        logging.handlers.TimedRotatingFileHandler.__init__(
            self, filename, when='midnight', backupCount=5)
        self.bg_queue = queue.Queue()
        self.bg_thread = threading.Thread(target=self._bg_thread)
        self.bg_thread.start()

    def _bg_thread(self):
        while True:
            record = self.bg_queue.get(True)
            if record is None:
                break
            self.handle(record)

    def stop(self):
        self.bg_queue.put_nowait(None)
        self.bg_thread.join()

####################################
# MultiLineFormater                #
####################################
# Class to improve formatting of multi-line KTC messages
class KtcMultiLineFormatter(logging.Formatter):
    def format(self, record):
        indent = ' ' * 9
        lines = super(KtcMultiLineFormatter, self).format(record)
        return lines.replace('\n', '\n' + indent)

####################################
def load_config(config):
    return Ktc_Log(config)

