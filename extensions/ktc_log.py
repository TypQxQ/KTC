# KTC - Klipper Tool Changer code (v.2)
# Log and statistics module
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# Based on and inspired by ERCF-Software-V3      Copyright (C) 2021  moggieuk#6538 (discord)
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

from __future__ import annotations  # To reference the class itself in type hints
import logging, threading, queue, time, ast, dataclasses
import math, os.path, copy, re
from . import ktc_persisting


####################################
# Main Logging Class for KTC       #
####################################
class Ktc_Log:
    def __init__(self, config):
        # Initialize object variables
        self.config = config
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        # Register event handlers
        self.printer.register_event_handler('klippy:connect', self.handle_connect)
        self.printer.register_event_handler("klippy:disconnect", self.handle_disconnect)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

        # Read and load configuration
        self.log_level = config.getint('log_level', 1, minval=0, maxval=3)
        self.logfile_level = config.getint('logfile_level', 3, minval=-1, maxval=4)

        # Initialize Logger variable
        self._ktc_logger = None

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
            self._ktc_logger = logging.getLogger('ktc')
            self._ktc_logger.setLevel(logging.INFO)
            self._ktc_logger.addHandler(queue_handler)
            
        # Statistics variables
        self.total_stats = Swap_Statistics()
        self.changer_stats: dict[str, Changer_Statistics] = {}
        self.tool_stats : dict[str, Tool_Statistics] = {}
        self.print_stats = Swap_Statistics()
        self.print_changer_stats: dict[str, Changer_Statistics] = {}
        self.print_tool_stats : dict[str, Tool_Statistics] = {}

    def handle_connect(self):
        # Load the persistent variables object
        self.ktc_persistent : ktc_persisting.KtcPersisting = self.printer.load_object(self.config, 'ktc_persisting')

        # Register G-code commands
        handlers = [
            'KTC_LOG_TRACE', 'KTC_LOG_DEBUG', 'KTC_LOG_INFO', 'KTC_LOG_ALWAYS', 
            'KTC_SET_LOG_LEVEL', 'KTC_DUMP_STATS', 'KTC_RESET_STATS',
            'KTC_INIT_PRINT_STATS', 'KTC_DUMP_PRINT_STATS', 'KTC_SAVE_STATS']
        for cmd in handlers:
            func = getattr(self, 'cmd_' + cmd)
            desc = getattr(self, 'cmd_' + cmd + '_help', None)
            self.gcode.register_command(cmd, func, False, desc)

        # Load persihabele statitstics 
        self._load_persisted_state()

        # Init persihabele statistics
        self._reset_print_statistics()

    def handle_ready(self):
        self.always('KTC Log Ready')

    def handle_disconnect(self):
        self.ktc_persistent.disconnect()

####################################
# LOGGING FUNCTIONS                #
####################################
    def always(self, message):
        if self._ktc_logger:
            self._ktc_logger.info(message)
        self.gcode.respond_info(message)

    def info(self, message):
        if self._ktc_logger and self.logfile_level > 0:
            self._ktc_logger.info(message)
        if self.log_level > 0:
            self.gcode.respond_info(message)

    def debug(self, message):
        message = "- DEBUG: %s" % message
        if self._ktc_logger and self.logfile_level > 1:
            self._ktc_logger.info(message)
        if self.log_level > 1:
            self.gcode.respond_info(message)

    def trace(self, message):
        message = "- - TRACE: %s" % message
        if self._ktc_logger and self.logfile_level > 2:
            self._ktc_logger.info(message)
        if self.log_level > 2:
            self.gcode.respond_info(message)

####################################
# STATISTICS FUNCTIONS             #
####################################
    def _load_persisted_state(self):
        self.trace("Loading persisted state.")
        
        # Load general statistics
        loaded_stats : dict = self.ktc_persistent.content.get("Statistics", {})
        if loaded_stats == {}:
            self.debug("Did not find any saved statistics. Initialized empty.")
        
        swap_stats_dict : dict = loaded_stats.get("total", {})
        try:
            if swap_stats_dict == {}:
                self.debug("Couldn't find any saved total statistics.")
            
            for key, value in swap_stats_dict.items():
                setattr(self.total_stats, key, value)
    
        except Exception as e:
            self.debug("Unexpected error while loading persistent swap stats: %s" % e)
        
        self.trace("_load_persisted_state: Loading changer stats.")
        # Load tool statistics

        self.changer_stats = self._get_persisted_items('Statistics', 'ktc_tool_changer', Changer_Statistics )
        self.changer_stats = self._get_persisted_items('Statistics', 'ktc_tool', Changer_Statistics )

        # self.trace("_load_persisted_state: Loading tool stats.")
        # # Load tool statistics
        # self.tool_stats = {}
        # for tool in self.printer.lookup_objects('ktc_tool'):
        #     try:
        #         toolname=str(tool[0])
        #         toolname=toolname.split(" ", 1)[1]
                
        #         self.tool_stats[toolname] = Tool_Statistics()
                
        #         tool_stats_dict : dict[str, Tool_Statistics] = loaded_stats.get("tool_%s" % toolname, {})

        #         if tool_stats_dict is None or tool_stats_dict == {}:
        #             raise Exception("Couldn't find any saved tool stats for tool_.%s" % toolname)
                
        #         for key, value in tool_stats_dict.items():
        #             if hasattr(self.tool_stats[toolname], key):
        #                 setattr(self.tool_stats[toolname], key, value)
                
        #         #  Backwards compatibility. delete this after a while
        #         self.tool_stats[toolname].time_spent_mounting = tool_stats_dict.get("total_time_spent_mounting", 0)
        #         self.tool_stats[toolname].time_spent_unmounting = tool_stats_dict.get("total_time_spent_unmounting", 0)
                
        
        #     except Exception as e:
        #         self.debug("Unexpected error while loading persistent tool stats: %s" % str(e))
        #         self.debug("Resetting tool stats for tool: %s" % toolname)
        #         self.tool_stats[toolname] = Tool_Statistics()
        # self.trace("_load_persisted_state: Done loading tool stats.")

    def _get_persisted_items(self, section: str, item_type: str, Stat_Type):
        self.trace("_get_persisted_items: Loading %s stats." % section)

        loaded_stats : dict = self.ktc_persistent.content.get(section, {})
        if loaded_stats == {}:
            self.debug("Did not find a saved %s section. Initialized empty." % section)

        items = {}
        for item in self.printer.lookup_objects(item_type):
            try:
                item_name=str(item[0]).split(" ", 1)[1]
                
                items[item_name] = Stat_Type()
                
                item_dict = loaded_stats.get("tool_%s" % item_name, {})

                if item_dict == {}:
                    raise("Couldn't find the item %s in the saved %s section." % (item_name, section))
                
                for key, value in item_dict.items():
                    if hasattr(items[item_name], key):
                        setattr(items[item_name], key, value)
               
            except Exception as e:
                self.debug("Error while loading persistent section %s stats: %s" % (section, str(e)))
                self.debug("Resetting section %s stats for item: %s" % (section, item_name))
                items[item_name] = Stat_Type()
        self.trace("_load_persisted_state: Done loading tool stats.")

    # This could be optimized to only save for the changed tool and not iterate over all tools but it's not a big deal
    def _persist_statistics(self):
        try:
            # Save general statistics
            swap_stats_dict = dataclasses.asdict(self.total_stats)
            self.ktc_persistent.save_variable("total", str(swap_stats_dict), section="Statistics")
            
            self._set_persisted_items("Statistics", "ktc_tool_changer", self.changer_stats)
            self._set_persisted_items("Statistics", "ktc_tool", self.tool_stats)
            
            # # Save tool statistics for each tool
            # for tid, tool in self.tool_stats.items():
            #     self.trace("_persist_statistics: Saving tool stats for tool: %s" % tid)
            #     # Convert to dict and remove the start_time_* variables so we don't save them
            #     tool_dict = dataclasses.asdict(tool)
            #     tool_dict = {k: v for k, v in tool_dict.items() if not k.startswith("start_time_")}

            #     # Save the tool statistics
            #     self.ktc_persistent.save_variable("tool_%s" % tid, 
            #                                       str(tool_dict),
            #                                       section="Statistics")
        except Exception as e:
            self.debug("Unexpected error whiles saving variables in _persist_statistics: %s" % e)

    def _set_persisted_items(self, section: str, item_type: str, items: dict[str, Tool_Statistics]):
        try:
            # Save tool statistics for each tool
            for item_name, item in items.items():
                self.trace("_persist_statistics: Saving %s stats for item: %s" % (section, item_name))
                # Convert to dict and remove the start_time_* variables so we don't save them
                item_dict = dataclasses.asdict(item)
                item_dict = {k: v for k, v in item_dict.items() if not k.startswith("start_time_")}

                # Save the tool statistics
                self.ktc_persistent.save_variable(item_type + "_%s" % item_name,
                                                  str(item_dict),
                                                  section=section)
        except Exception as e:
            self.debug("Unexpected error whiles saving %s in %s: %s. Not saved." % (item_type, section, e))

    def _reset_statistics(self):
        self.debug("Reseting KTC statistics.")
        self.total_stats = Swap_Statistics()

        self.changer_stats : dict[str, Changer_Statistics] = {}
        for changer in self.printer.lookup_objects('ktc_tool_changer'):
            self.changer_stats[str(changer[0]).split(" ", 1)[1]] = Changer_Statistics()
        
        self.tool_stats : dict[str, Tool_Statistics] = {}
        for tool in self.printer.lookup_objects('ktc_tool'):
            self.tool_stats[str(tool[0]).split(" ", 1)[1]] = Tool_Statistics()

    def _reset_print_statistics(self):
        self.print_stats = copy.deepcopy(self.total_stats)
        self.print_changer_stats = copy.deepcopy(self.changer_stats)
        self.print_tool_stats = copy.deepcopy(self.tool_stats)

    def _dump_statistics(self):
        msg = "KTC Total Statistics:\n"
        msg += self._changer_stats_to_human_string(self.total_stats)

        msg += "Changer Statistics:\n"
        sorted_items = natural_keys_sorting(self.changer_stats.keys())
        for id in sorted_items:
            msg += self._changer_stats_to_human_string(id, self.changer_stats[id])

        msg += "Tool Statistics:\n"
        sorted_tools = natural_keys_sorting(self.tool_stats.keys())
        for tid in sorted_tools:
            msg += self._tool_stats_to_human_string(tid)

        self.always(msg)

    def _dump_print_statistics(self):
        msg = "KTC Statistics for this print:\n"
        msg += self._changer_stats_to_human_string(self.print_stats)

        msg += "Changer Statistics:\n"
        sorted_items = natural_keys_sorting(self.print_changer_stats.keys())
        for id in sorted_items:
            msg += self._changer_stats_to_human_string(id, self.print_changer_stats[id])

        msg += "Tool Statistics for this print:\n"
        sorted_items = natural_keys_sorting(self.print_tool_stats.keys())
        for id in sorted_items:
            msg += self._changer_stats_to_human_string(id, self.print_tool_stats[id])
                
    @staticmethod
    def _changer_stats_to_human_string(s: Changer_Statistics) -> str:
        if s.time_spent_mounting > 0:
            result = "\n%s spent mounting tools" % (
                seconds_to_human_string(s.time_spent_mounting))
        if s.time_spent_unmounting > 0:
            result += "\n%s spent unmounting tools" % (
                seconds_to_human_string(s.time_spent_unmounting))
        if s.engages > 0:
            result += "\n%d engages completed" % s.engages
        if s.disengages > 0:
            result += "\n%d disengages completed" % s.disengages
        if s.selects > 0:
            result += "\n%d tool selects completed" % s.selects
        if s.deselects > 0:
            result += "\n%d tool deselectss completed" % s.deselects
        result += "\n------------\n"
        return result

    def _tool_stats_to_human_string(self, tid: str) -> str:
        t = self.tool_stats[tid]
        result = "Tool %s:\n" % (tid)

        result += "Selects %d/%d completed in %s. (%s/select).\n" % (
        # result += "Completed %d out of %d selects in %s. Average of %s per toolmount.\n" % (
            t.selects_completed, t.selects_started,
            seconds_to_human_string(t.time_spent_mounting),
            seconds_to_human_string(division(
                t.time_spent_mounting, t.selects_completed)))
        
        # result += "Time spent mounting: %s\n" % seconds_to_human_string(t.time_spent_mounting)

        result += "Deselects %d/%d completed in %s. (%s/deselect).\n" % (
        # result += "Completed %d out of %d deselectss in %s. Average of %s per toolunmount.\n" % (
            t.deselects_completed, t.deselects_started,
            seconds_to_human_string(t.time_spent_unmounting),
            seconds_to_human_string(division(
                t.time_spent_unmounting, t.deselects_completed)))

        result += "%s spent selected." % seconds_to_human_string(t.time_selected)
        
        if t.time_heater_active > 0:
            result += " %s with active heater" % (
                seconds_to_human_string(t.time_heater_active))
        
        if t.time_heater_standby > 0:
            result += ", %s with standby heater" % (
                seconds_to_human_string(t.time_heater_standby))
        result += "."
        
        result += "\n------------\n"
        return result
        
    def _increase_tool_time_diff(self, tool_id: str, final_time_key: str, changer_time_key: str = None):
        try:
            start_time_attr = getattr(self.tool_stats[tool_id],
                                      "start_" + final_time_key, 0)
            if start_time_attr == 0:
                return None
            
            time_spent = start_time_attr - time.time()
            prev_final_time = getattr(self.tool_stats[tool_id], final_time_key, 0)
            
            if time_spent < 0:
                time_spent = 0
                
            setattr(
                self.tool_stats[tool_id], final_time_key, 
                prev_final_time + time_spent)
            start_time_attr = 0
            # setattr(
            #     self.tool_stats[tool_id], "start_" + final_time_key, 0)
            
            self.trace("_increase_tool_time_diff for Tool: %s: start_time_attr: %s, self.tool_stats[tool_id].start_time_attr: %s" % (
                tool_id, start_time_attr, getattr(self.tool_stats[tool_id],
                                      "start_" + final_time_key, "Not found")))
            
            if changer_time_key is not None:
                prev_changer_time = getattr(self.total_stats, changer_time_key, 0)
                setattr(
                    self.total_stats, changer_time_key, 
                    prev_changer_time + time_spent)
                
        except Exception as e:
            # Handle any exceptions that occur during the process
            print(f"An error occurred in KTC_Log._increase_tool_time_diff(): {e}")

    def track_mount_start(self, tool_id: str):
        self.tool_stats[tool_id].start_time_spent_mounting = time.time()
        self.tool_stats[tool_id].selects_started += 1
        
    def track_mount_end(self, tool_id: str):
        self.trace("track_mount_end: Running for Tool: %s." % (tool_id))
        self._increase_tool_time_diff(tool_id, "time_spent_mounting", "time_spent_mounting")
        self.tool_stats[tool_id].selects_completed += 1
        
        # start_time = self.tool_stats[tool_id].start_time_spent_mounting
        # if start_time is not None and start_time != 0:
        #     time_spent = time.time() - start_time
        #     self.tool_stats[tool_id].time_spent_mounting += time_spent
        #     self.total_stats.time_spent_mounting += time_spent
        #     self.tool_stats[tool_id].start_time_spent_mounting = 0
        
        self._persist_statistics()

    def track_unmount_start(self, tool_id: str):
        self.tool_stats[tool_id].start_time_unmount = time.time()
        self.tool_stats[tool_id].deselects_started += 1

    def track_unmount_end(self, tool_id):
        # self.trace("track_unmount_end: Running for Tool: %s." % (tool_id))
        start_time = self.tool_stats[tool_id].start_time_unmount
        if start_time is not None and start_time != 0:
            # self.trace("track_unmount_end: start_time is not None for Tool: %s." % (tool_id))
            time_spent = time.time() - start_time
            self.tool_stats[tool_id].time_spent_unmounting += time_spent
            self.total_stats.time_spent_unmounting += time_spent
            self.tool_stats[tool_id].start_time_unmount = 0
            self.tool_stats[tool_id].deselects_completed += 1
            self.total_stats.deselects += 1
            self._persist_statistics()

    def track_selected_tool_start(self, tool_id):
        self.tool_stats[str(tool_id)].start_time_selected = time.time()
        self.tool_stats[str(tool_id)].selects_completed += 1
        self.total_stats.selects += 1

    def track_selected_tool_end(self, tool_id):
        self._increase_tool_time_diff(tool_id, "time_selected")
        self._persist_statistics()

    def track_active_heater_start(self, tool_id):
        self.tool_stats[str(tool_id)].start_time_active = time.time()

    def track_active_heater_end(self, tool_id):
        self._increase_tool_time_diff(tool_id, "time_active")
        self._persist_statistics()

    def track_standby_heater_start(self, tool_id):
        self.tool_stats[str(tool_id)].start_time_standby = time.time()

    def track_standby_heater_end(self, tool_id):
        self._increase_tool_time_diff(tool_id, "time_standby")
        self._persist_statistics()

### LOGGING AND STATISTICS FUNCTIONS GCODE FUNCTIONS
    # TODO: Remove this function after a while
    cmd_KTC_SAVE_STATS_help = "Save the KTC statistics"
    def cmd_KTC_SAVE_STATS(self, gcmd):
        self._persist_statistics()
    
    cmd_KTC_RESET_STATS_help = "Reset the KTC statistics"
    def cmd_KTC_RESET_STATS(self, gcmd):
        param = gcmd.get('SURE', "no")
        if param.lower() == "yes":
            self._reset_statistics()
            self._reset_print_statistics()
            self._persist_statistics()
            self._dump_statistics()
            self.always("Statistics RESET.")
        else:
            message = "Are you sure you want to reset KTC statistics?\n"
            message += "If so, run with parameter SURE=YES:\n"
            message += "KTC_RESET_STATS SURE=YES"
            self.gcode.respond_info(message)

    cmd_KTC_DUMP_STATS_help = "Dump the KTC statistics"
    def cmd_KTC_DUMP_STATS(self, gcmd):
        self._dump_statistics()

    cmd_KTC_INIT_PRINT_STATS_help = "Run at start of a print to initialize the KTC print statistics"
    def cmd_KTC_INIT_PRINT_STATS(self, gcmd):
        self._reset_print_statistics()

    cmd_KTC_DUMP_PRINT_STATS_help = "Run at end of a print to list statistics since last print reset."
    def cmd_KTC_DUMP_PRINT_STATS(self, gcmd):
        self._dump_print_statistics()

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
# Statistics Data Classes          #
####################################
@dataclasses.dataclass
class Swap_Statistics:
    time_spent_mounting: int = 0
    time_spent_unmounting: int = 0
    engages: int = 0
    disengages: int = 0
    selects: int = 0
    deselects: int = 0

@dataclasses.dataclass
class Changer_Statistics:
    engages: int = 0
    disengages: int = 0
    selects: int = 0
    deselects: int = 0
    time_spent_mounting: int = 0
    time_spent_unmounting: int = 0

@dataclasses.dataclass
class Tool_Statistics:
    selects_completed: int = 0
    selects_completed: int = 0
    deselects_completed: int = 0
    deselects_completed: int = 0
    selects_started: int = 0
    deselects_started: int = 0
    time_selected: int = 0
    time_heater_active: int = 0
    time_heater_standby: int = 0
    time_spent_mounting: int = 0
    time_spent_unmounting: int = 0
    start_time_selected: int = 0 #TRACKED_START_TIME_SELECTED
    start_time_active: int = 0   # TRACKED_START_TIME_ACTIVE
    start_time_standby: int = 0  # TRACKED_START_TIME_STANDBY
    start_time_spent_mounting: int = 0    # TRACKED_MOUNT_START_TIME
    start_time_unmount: int = 0  # TRACKED_UNMOUNT_START_TIME

def natural_keys_sorting(list_to_sort):
    return sorted(list_to_sort, key=natural_sorting)

def natural_sorting(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [ __atoi(c) for c in re.split(r'(\d+)', text) ]

def __atoi(text):
    return int(text) if text.isdigit() else text

def seconds_to_human_string(seconds):
    result = ""
    hours = int(math.floor(seconds / 3600.))
    if hours >= 1:
        result += "%d hours " % hours
    minutes = int(math.floor(seconds / 60.) % 60)
    if hours >= 1 or minutes >= 1:
        result += "%d minutes " % minutes
    result += "%d seconds" % int((math.floor(seconds) % 60))
    return result

# Function to avoid division by zero
def division(dividend, divisor):
    return dividend/divisor if divisor else 0

####################################
def load_config(config):
    return Ktc_Log(config)

