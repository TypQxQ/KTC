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


class Ktc_Log:
    """Main Logging and statistics Class for KTC (Klipper Tool Changer)"""
    
    ####################################
    # INITIALIZATION FUNCTIONS         #
    ####################################
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
        """Handle the connect event. This is called when the printer connects to Klipper."""
        # Load the persistent variables object here to avoid circular dependencies
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

        # Load persihabele statitstics from file
        self._load_persisted_state()

        # Init persihabele print statistics
        self._reset_print_statistics()

    def handle_ready(self):
        """Handle the ready event. This is called when the printer is ready to receive commands."""
        self.always('KTC Log Ready')

    def handle_disconnect(self):
        """Handle the disconnect event. This is called when the printer disconnects from Klipper."""
        self.ktc_persistent.disconnect() # Close the persistent variables file

####################################
# LOGGING FUNCTIONS                #
####################################
    def always(self, message):
        """Log a message to the console and to the log file if enabled."""
        if self._ktc_logger:
            self._ktc_logger.info(message)
        self.gcode.respond_info(message)

    def info(self, message):
        """Log an info message to the console and to the log file if enabled and log_level is 1 or higher."""
        if self._ktc_logger and self.logfile_level > 0:
            self._ktc_logger.info(message)
        if self.log_level > 0:
            self.gcode.respond_info(message)

    def debug(self, message):
        """Log a debug message to the console and to the log file if enabled and log_level is 2 or higher."""
        message = "- DEBUG: %s" % message
        if self._ktc_logger and self.logfile_level > 1:
            self._ktc_logger.info(message)
        if self.log_level > 1:
            self.gcode.respond_info(message)

    def trace(self, message):
        """Log a trace message to the console and to the log file if enabled and log_level is 3 or higher."""
        message = "- - TRACE: %s" % message
        if self._ktc_logger and self.logfile_level > 2:
            self._ktc_logger.info(message)
        if self.log_level > 2:
            self.gcode.respond_info(message)

####################################
# STATISTICS LOADING  FUNCTIONS    #
####################################
    def _load_persisted_state(self):
        """Load the persisted state from the file"""
        self.trace("Loading persisted state.")
        
        # Load general statistics
        loaded_stats : dict = self.ktc_persistent.content.get("Statistics", {})
        if loaded_stats == {}:
            self.debug("Did not find any saved statistics. Initialized empty.")
        
        # swap_stats_dict : dict = loaded_stats.get("total", {})
        # try:
        #     if swap_stats_dict == {}:
        #         self.debug("Couldn't find any saved total statistics.")
            
        #     for key, value in swap_stats_dict.items():
        #         setattr(self.total_stats, key, value)
    
        # except Exception as e:
        #     self.debug("Unexpected error while loading persistent swap stats: %s" % e)
        
        self.changer_stats = self._get_persisted_items("Statistics", "ktc_toolchanger", Changer_Statistics )
        self.tool_stats = self._get_persisted_items("Statistics", "ktc_tool", Tool_Statistics )

    def _get_persisted_items(self, section: str, item_type: str, Stat_Type) -> dict[str, Stat_Type]:
        """Load the persisted state from the file for a given section and item type
        For example, load all persisted ktc_toolchanger stats from the Statistics section.
        Return a dict with the loaded items."""

        loaded_stats : dict = self.ktc_persistent.content.get(section, {})
        if loaded_stats == {}:
            self.debug("Did not find a saved %s section. Initialized empty." % section)

        items = {}
        for item in self.printer.lookup_objects(item_type):
            try:
                item_name=str(item[0]).split(" ", 1)[1]
                
                items[item_name] = Stat_Type()
                item_dict = loaded_stats.get((item_type + "_" + item_name).lower(), {})

                if item_dict == {}:
                    raise Exception("Couldn't find the item %s in the saved %s section." % ((item_name), section))
                
                for key, value in item_dict.items():
                    if hasattr(items[item_name], key):
                        setattr(items[item_name], key, value)
            except Exception as e:
                self.debug("Error while loading persistent section %s stats: %s" % (section, str(e)))
                self.debug("Resetting section %s stats for item: %s" % (section, item_name))
                items[item_name] = Stat_Type()
        return items

####################################
# STATISTICS SAVING  FUNCTIONS     #
####################################
    # This could be optimized to only save for the changed tool and not iterate over all tools but it's not a big deal
    def _persist_statistics(self):
        """Save all the statistics to the file"""
        try:
            # Save general statistics
            # swap_stats_dict = dataclasses.asdict(self.total_stats)
            # self.ktc_persistent.save_variable("total", str(swap_stats_dict), section="Statistics")
            
            self._set_persisted_items("Statistics", "ktc_toolchanger", self.changer_stats)
            self._set_persisted_items("Statistics", "ktc_tool", self.tool_stats)
        except Exception as e:
            self.debug("Unexpected error whiles saving variables in _persist_statistics: %s" % e)

    def _set_persisted_items(self, section: str, item_type: str, items: dict[str, Tool_Statistics | Changer_Statistics]):
        """Save the statistics to the file for a given section and item type"""
        try:
            # Save tool statistics for each tool
            for item_name, item in items.items():
                self.trace("_persist_statistics: Saving %s stats for item: %s" % (section, item_name))
                # Convert to dict and remove the start_time_* variables so we don't save them
                item_dict = dataclasses.asdict(item)
                item_dict = {k: v for k, v in item_dict.items() if not k.startswith("start_time_")}

                # Save the tool statistics to file
                self.ktc_persistent.save_variable(item_type + "_" + item_name,
                                                  str(item_dict),
                                                  section=section)
        except Exception as e:
            self.debug("Unexpected error whiles saving %s in %s: %s. Not saved." % (item_type, section, e))

####################################
# STATISTICS RESET FUNCTIONS       #
####################################
    def _reset_statistics(self):
        """Reset all the statistics to 0"""
        self.always("Reseting KTC statistics.")
        self.total_stats = Swap_Statistics()

        self.changer_stats : dict[str, Changer_Statistics] = {}
        for changer in self.printer.lookup_objects('ktc_tool_changer'):
            self.changer_stats[str(changer[0]).split(" ", 1)[1]] = Changer_Statistics()
        
        self.tool_stats : dict[str, Tool_Statistics] = {}
        for tool in self.printer.lookup_objects('ktc_tool'):
            self.tool_stats[str(tool[0]).split(" ", 1)[1]] = Tool_Statistics()

    def _reset_print_statistics(self):
        """Reset all the print statistics to same as regular statistics.
        This is called at the start of each print to reset the print statistics.
        The print statistics are subtracted from the regular statistics to get the statistics for the print."""
        self.print_stats = copy.deepcopy(self.total_stats)
        self.print_changer_stats = copy.deepcopy(self.changer_stats)
        self.print_tool_stats = copy.deepcopy(self.tool_stats)

####################################
# STATISTICS PRESENTATION FUNCTIONS#
####################################
    def _dump_statistics(self, since_print_start = False):
        """Dump all the statistics to the console.
        If since_print_start is True, subtract the print stats from the total stats
        and only print the stats for the start of the print."""

        if not since_print_start:
            msg = "KTC Total Statistics:\n"
        else:
            msg = "KTC Statistics since start of print:\n"

        # If has only one changer then only print for that changer as total stats are the same
        if len(self.changer_stats.keys()) == 1:
            self._dump_statistics_for_changer(list(self.changer_stats.keys())[0])
        else:
            # This will add the total stats for all changers as a sum and then print them
            msg += self._total_stats_to_human_string()

            # This will print the stats for each changer in a sorted order
            msg += "Changer Statistics:\n"
            sorted_items = natural_keys_sorting(self.changer_stats.keys())
            for changer_name in sorted_items:
                msg += self._changer_stats_to_human_string(changer_name, since_print_start)

        msg += "Tool Statistics:\n"
        sorted_tools = natural_keys_sorting(self.tool_stats.keys())
        for tol_name in sorted_tools:
            msg += self._tool_stats_to_human_string(tol_name, since_print_start)

        # Dump the message to the console and to the log file if enabled
        self.always(msg)
                
    def _total_stats_to_human_string(self) -> str:
        return ""
    
    def _changer_stats_to_human_string(self, changer_name: str, since_print_start = False) -> str:
        selects = None
        deselects = None
        time_spent_selecting = None
        time_spent_deselecting = None
        
        result = ("Changer %s:" % changer_name)
        changer = self.printer.lookup_object('ktc_toolchanger %s' % changer_name)
        
        for tool in self.printer.lookup_object('ktc_toolchanger %s' % changer_name).tools:
            sum_stats = self._sum_tool_stats_for_changer(changer_name, since_print_start)
        
        ############################## Test 1        
        # if sum_stats["time_spent_selecting"] > 0:
        #     result += "\nSpent %s selecting" % (
        #         seconds_to_human_string(sum_stats["time_spent_selecting"]))
        # if sum_stats["time_spent_deselecting"] > 0 and sum_stats["time_spent_deselecting"] > 0:
        #     result += " and "
        # else:
        #     result += "\nSpent "
        # if sum_stats["time_spent_deselecting"] > 0:
        #     result += "%s deselecting tools." % (
        #         seconds_to_human_string(sum_stats["time_spent_deselecting"]))
        
        ############################## Test 2
        # if sum_stats["time_spent_selecting"] > 0:
        #     result += "\nSpent %s selecting %s times with %.1f success rate." % (
        #         seconds_to_human_string(sum_stats["time_spent_selecting"]),
        #         bignumber_to_human_string(sum_stats["selects_completed"]),
        #         (sum_stats["selects_completed"] / sum_stats["selects_started"] * 100))
        # if sum_stats["time_spent_deselecting"] > 0:
        #     result += "\nSpent %s deselecting %s times with %.1f success rate." % (
        #         seconds_to_human_string(sum_stats["time_spent_deselecting"]),
        #         bignumber_to_human_string(sum_stats["deselects_completed"]),
        #         (sum_stats["deselects_completed"] / sum_stats["deselects_started"] * 100))

        ############################## Test 3
        # 264 selects completed in 1:00:00. Avg. 13.2s. 0.0% failed.
        
        # if sum_stats["time_spent_selecting"] > 0:
        #     result += "\n%s selects completed in %s. Avg. %s. %.1f%% failed." % (
        #         bignumber_to_human_string(sum_stats["selects_completed"]),
        #         seconds_to_human_string(sum_stats["time_spent_selecting"]),
        #         seconds_to_human_string(division(
        #             sum_stats["time_spent_selecting"], sum_stats["selects_completed"])),
        #         (sum_stats["selects_completed"] / sum_stats["selects_started"] * 100))
        # if sum_stats["time_spent_deselecting"] > 0:
        #     result += "\n%s deselects completed in %s. Avg. %s. %.1f%% failed." % (
        #         bignumber_to_human_string(sum_stats["deselects_completed"]),
        #         seconds_to_human_string(sum_stats["time_spent_deselecting"]),
        #         seconds_to_human_string(division(
        #             sum_stats["time_spent_deselecting"], sum_stats["deselects_completed"])),
        #         (sum_stats["deselects_completed"] / sum_stats["deselects_started"] * 100))

        ############################## Test 4
        # 264 selects completed(100.0%) in 1:00:00, avg. 13.2s.
        
        if sum_stats["time_spent_selecting"] > 0:
            result += "\n%s selects completed(%.1f%%) in %s. Avg. %s." % (
                bignumber_to_human_string(sum_stats["selects_completed"]),
                (sum_stats["selects_completed"] / sum_stats["selects_started"] * 100),
                seconds_to_human_string(sum_stats["time_spent_selecting"]),
                seconds_to_human_string(division(
                    sum_stats["time_spent_selecting"], sum_stats["selects_completed"]))
                )
        if sum_stats["time_spent_deselecting"] > 0:
            result += "\n%s deselects completed(%.1f%%) in %s. Avg. %s." % (
                bignumber_to_human_string(sum_stats["deselects_completed"]),
                (sum_stats["deselects_completed"] / sum_stats["deselects_started"] * 100),
                seconds_to_human_string(sum_stats["time_spent_deselecting"]),
                seconds_to_human_string(division(
                    sum_stats["time_spent_deselecting"], sum_stats["deselects_completed"])))

        ############################## Test Engages/Disengages
        self.trace("_changer_stats_to_human_string for %s: engages: %d, disengages: %d" % (
            changer_name, self.changer_stats[changer_name].engages, self.changer_stats[changer_name].disengages))
        
        if self.changer_stats[changer_name].engages > 0:
            result += "\n%s engages " % bignumber_to_human_string(self.changer_stats[changer_name].engages)

        if self.changer_stats[changer_name].engages > 0 and self.changer_stats[changer_name].disengages > 0:
            result += " and "
        elif self.changer_stats[changer_name].disengages > 0:
            result += "\n"
        elif self.changer_stats[changer_name].engages > 0:
            result += "."
            
        if self.changer_stats[changer_name].disengages > 0:
            result += "%d disengages completed" % self.changer_stats[changer_name].disengages
        ##############################
    
        

        # if sum_stats["selects_completed"] > 0:
        #     result += "\n%s/%s tool selects completed (%.1f%%)" % (
        #         bignumber_to_human_string(sum_stats["selects_completed"]), 
        #         bignumber_to_human_string(sum_stats["selects_started"]),
        #         (sum_stats["selects_completed"] / sum_stats["selects_started"] * 100))
        # if sum_stats["deselects_completed"] > 0:
        #     result += "\n%s/%s tool deselectss completed (%.1f%%)" % (
        #         bignumber_to_human_string(sum_stats["deselects_completed"]), 
        #         bignumber_to_human_string(sum_stats["deselects_started"]),
        #         (sum_stats["deselects_completed"] / sum_stats["deselects_started"] * 100))
        result += "\n------------\n"
        return result

    def _sum_tool_stats_for_changer(self, changer_name: str, since_print_start = False) -> dict:
        """Add up all tool stats for a changer and return a dict with the sum.
        If since_print_start is True, subtract the print stats from the total stats"""
        result = {
            "selects_completed": 0,
            "deselects_completed": 0,
            "selects_started": 0,
            "deselects_started": 0,
            "time_spent_selecting": 0,
            "time_spent_deselecting": 0
        }
    
        for tool_name, tool in self.printer.lookup_object('ktc_toolchanger %s' % changer_name).tools.items():
            result["selects_completed"] += self.tool_stats[tool_name].selects_completed
            result["deselects_completed"] += self.tool_stats[tool_name].deselects_completed
            result["selects_started"] += self.tool_stats[tool_name].selects_started
            result["deselects_started"] += self.tool_stats[tool_name].deselects_started
            result["time_spent_selecting"] += self.tool_stats[tool_name].time_spent_selecting
            result["time_spent_deselecting"] += self.tool_stats[tool_name].time_spent_deselecting
            
            if since_print_start:
                result["selects_completed"] -= self.print_tool_stats[tool_name].selects_completed
                result["deselects_completed"] -= self.print_tool_stats[tool_name].deselects_completed
                result["selects_started"] -= self.print_tool_stats[tool_name].selects_started
                result["deselects_started"] -= self.print_tool_stats[tool_name].deselects_started
                result["time_spent_selecting"] -= self.print_tool_stats[tool_name].time_spent_selecting
                result["time_spent_deselecting"] -= self.print_tool_stats[tool_name].time_spent_deselecting

        return result


    def _tool_stats_to_human_string(self, tol_name: str, since_print_start = False) -> str:
        """Return a human readable string with the statistics for a given tool"""
        t = self.tool_stats[tol_name]
        result = "Tool %s:\n" % (tol_name)

        result += "Selects %d/%d completed in %s. (%s/select).\n" % (
        # result += "Completed %d out of %d selects in %s. Average of %s per toolmount.\n" % (
            t.selects_completed, t.selects_started,
            seconds_to_human_string(t.time_spent_selecting),
            seconds_to_human_string(division(
                t.time_spent_selecting, t.selects_completed)))
        
        # result += "Time spent mounting: %s\n" % seconds_to_human_string(t.time_spent_selecting)

        result += "Deselects %d/%d completed in %s. (%s/deselect).\n" % (
        # result += "Completed %d out of %d deselectss in %s. Average of %s per toolunmount.\n" % (
            t.deselects_completed, t.deselects_started,
            seconds_to_human_string(t.time_spent_deselecting),
            seconds_to_human_string(division(
                t.time_spent_deselecting, t.deselects_completed)))

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

    def track_select_start(self, tool):
        self.tool_stats[tool.name].start_time_spent_selecting = time.time()
        self.tool_stats[tool.name].selects_started += 1
        self.changer_stats[tool.toolchanger.name].selects_started += 1
        
    def track_select_end(self, tool_id: str):
        self.trace("track_select_end: Running for Tool: %s." % (tool_id))
        self._increase_tool_time_diff(tool_id, "time_spent_selecting", "time_spent_selecting")
        self.tool_stats[tool_id].selects_completed += 1
        self.changer_stats[tool_id].selects += 1
        
        # start_time = self.tool_stats[tool_id].start_time_spent_selecting
        # if start_time is not None and start_time != 0:
        #     time_spent = time.time() - start_time
        #     self.tool_stats[tool_id].time_spent_selecting += time_spent
        #     self.total_stats.time_spent_selecting += time_spent
        #     self.tool_stats[tool_id].start_time_spent_selecting = 0
        
        self._persist_statistics()

    def track_deselect_start(self, tool_id: str):
        self.tool_stats[tool_id].start_time_unmount = time.time()
        self.tool_stats[tool_id].deselects_started += 1

    def track_deselect_end(self, tool_id):
        # self.trace("track_deselect_end: Running for Tool: %s." % (tool_id))
        start_time = self.tool_stats[tool_id].start_time_unmount
        if start_time is not None and start_time != 0:
            # self.trace("track_deselect_end: start_time is not None for Tool: %s." % (tool_id))
            time_spent = time.time() - start_time
            self.tool_stats[tool_id].time_spent_deselecting += time_spent
            self.total_stats.time_spent_deselecting += time_spent
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
        self._dump_statistics(since_print_start = True)

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
    time_spent_selecting: int = 0
    time_spent_deselecting: int = 0
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
    time_spent_selecting: int = 0
    time_spent_deselecting: int = 0

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
    time_spent_selecting: int = 0
    time_spent_deselecting: int = 0
    start_time_selected: int = 0 #TRACKED_START_TIME_SELECTED
    start_time_active: int = 0   # TRACKED_START_TIME_ACTIVE
    start_time_standby: int = 0  # TRACKED_START_TIME_STANDBY
    start_time_spent_selecting: int = 0    # TRACKED_MOUNT_START_TIME
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

def seconds_to_human_string(seconds, long_format = False):
    """Convert a number of seconds to a human readable string in the format 1h 2m 3s
    or 1 hours 2 minutes 3 seconds if long_format is True."""
    result = ""
    hours = int(math.floor(seconds / 3600.))
    if long_format:
        if hours >= 1:
            result += "%d hours " % hours
        minutes = int(math.floor(seconds / 60.) % 60)
        if hours >= 1 or minutes >= 1:
            result += "%d minutes " % minutes
        result += "%d seconds" % int((math.floor(seconds) % 60))
    else:
        if hours >= 1:
            result += "%dh " % hours
        minutes = int(math.floor(seconds / 60.) % 60)
        if hours >= 1 or minutes >= 1:
            result += "%dm " % minutes
        result += "%ds" % int((math.floor(seconds) % 60))
    return result

def bignumber_to_human_string(number):
    """Convert a number to a human readable string in the format 1.2K, 2.3M, 3.4B etc."""
    if number >= 1000000000:
        return "%.1fB" % (number / 1000000000)
    if number >= 1000000:
        return "%.1fM" % (number / 1000000)
    if number >= 1000:
        return "%.1fK" % (number / 1000)
    return "%d" % number

# Function to avoid division by zero
def division(dividend, divisor):
    return dividend/divisor if divisor else 0

####################################
def load_config(config):
    return Ktc_Log(config)

