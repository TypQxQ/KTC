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
import logging, logging.handlers, re
import threading, queue, time, dataclasses
import math, os.path, copy, operator
import typing

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy import klippy
    from . import ktc_toolchanger, ktc_tool, ktc_persisting, ktc, ktc_heater

LINE_SEPARATOR = "\n--------------------------------------------------------\n"
SECTION_SEPARATOR = (
    "\n========================================================\n"
)

class KtcLog:
    """Main Logging and statistics Class for KTC (Klipper Tool Changer)"""

    ####################################
    # INITIALIZATION METHODS         #
    ####################################
    def __init__(self, config: 'configfile.ConfigWrapper'):
        """
        Initialize the KtcLog object.

        Parameters:
        - config: The configuration object.

        Returns:
        None
        """
        # Initialize object variables
        self.config = config
        self.printer : 'klippy.Printer' = config.get_printer()
        self.gcode = typing.cast('gcode.GCodeDispatch', self.printer.lookup_object("gcode"))

        # Register event handlers
        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        self.printer.register_event_handler("klippy:disconnect", self._handle_disconnect)
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

        # Read and load configuration
        self.log_level = config.getint(
            "log_level", default=1,      #type: ignore # Klippy is not type checked.
            minval=0, maxval=3)
        self.logfile_level = config.getint(
            "logfile_level", default=3,  #type: ignore # Klippy is not type checked.
            minval=-1, maxval=4)

        # Initialize Logger variable
        self._ktc_logger = None

        # Setup background file based logging before logging any messages
        if self.logfile_level >= 0:
            logfile_path = self.printer.start_args["log_file"]
            dirname = os.path.dirname(logfile_path)
            if dirname is None:
                ktc_log = os.path.expanduser("~/ktc.log")
            else:
                ktc_log = dirname + "/ktc.log"
            self.queue_listener = KtcQueueListener(ktc_log)
            self.queue_listener.setFormatter(
                KtcMultiLineFormatter("%(asctime)s %(message)s", datefmt="%I:%M:%S")
            )
            queue_handler = KtcQueueHandler(self.queue_listener.bg_queue)
            self._ktc_logger = logging.getLogger("ktc")
            self._ktc_logger.setLevel(logging.INFO)
            self._ktc_logger.addHandler(queue_handler)

        self._rollover_logfile_at_startup = typing.cast(bool, config.getboolean(
            "rollover_logfile_at_startup", default=False))
        if self._rollover_logfile_at_startup and self.logfile_level:
            self.queue_listener.doRollover()
            self.debug("Forced rollover of KTC log file done.")

        # Statistics variables
        self.changer_stats: typing.Dict[str, ChangerStatisticsClass] = {}
        self.tool_stats: typing.Dict[str, ToolStatisticsClass] = {}
        self.print_changer_stats: typing.Dict[str, ChangerStatisticsClass] = {}
        self.print_tool_stats: typing.Dict[str, ToolStatisticsClass] = {}

    def _handle_connect(self):
        '''Handle the connect event. This is called when the printer connects to Klipper.'''
        self._ktc = typing.cast('ktc.Ktc', self.printer.lookup_object("ktc"))

        # Load the persistent variables object here to avoid circular dependencies
        self._ktc_persistent = typing.cast(      # pylint: disable=attribute-defined-outside-init
            'ktc_persisting.KtcPersisting', self.printer.lookup_object( "ktc_persisting"))

        # Register G-code commands
        handlers = [
            "KTC_LOG_TRACE",
            "KTC_LOG_DEBUG",
            "KTC_LOG_INFO",
            "KTC_LOG_ALWAYS",
            "KTC_SET_LOG_LEVEL",
            "KTC_STATS_REPORT",
            "KTC_RESET_STATS",
            "KTC_RESET_PRINT_STATS",
            "KTC_PRINT_STATS_REPORT",
        ]
        for cmd in handlers:
            func = getattr(self, "cmd_" + cmd)
            desc = getattr(self, "cmd_" + cmd + "_help", None)
            self.gcode.register_command(cmd, func, False, desc)

        # Load persihabele statitstics from file
        self._load_persisted_state()

        # Init persihabele print statistics
        self._reset_print_statistics()

    def _handle_ready(self):
        """Handle the ready event. This is called when the printer is ready to receive commands."""
        self.always("KTC Log Ready")

    def _handle_disconnect(self):
        """Handle the disconnect event. This is called when the printer disconnects from Klipper."""
        self.always("Klipper disconnected! Closing KTC log.")
        if self.queue_listener:
            self.queue_listener.stop()
        if self._ktc_persistent is not None:
            self._ktc_persistent.disconnect()  # Close the persistent variables file

    ####################################
    # LOGGING METHODS                  #
    ####################################
    def always(self, message):
        """Log a message to the console and to the log file if enabled."""
        if self._ktc_logger:
            self._ktc_logger.info(message)
        self.gcode.respond_info(message)

    def info(self, message):
        """Log an info message to the console and to the log file if enabled and 
        log_level is 1 or higher."""
        if self._ktc_logger and self.logfile_level > 0:
            self._ktc_logger.info(message)
        if self.log_level > 0:
            self.gcode.respond_info(message)

    def debug(self, message):
        """Log a debug message to the console and to the log file if enabled and 
        log_level is 2 or higher."""
        message = "- DEBUG: %s" % message
        if self._ktc_logger and self.logfile_level > 1:
            self._ktc_logger.info(message)
        if self.log_level > 1:
            self.gcode.respond_info(message)

    def trace(self, message):
        """Log a trace message to the console and to the log file if enabled and 
        log_level is 3 or higher."""
        message = "- - TRACE: %s" % message
        if self._ktc_logger and self.logfile_level > 2:
            self._ktc_logger.info(message)
        if self.log_level > 2:
            self.gcode.respond_info(message)

    ####################################
    # STATISTICS LOADING  METHODS    #
    ####################################
    def _load_persisted_state(self):
        """Load the persisted state from the file"""
        self.trace("Loading persisted state.")

        # Load general statistics
        loaded_stats: typing.Dict = self._ktc_persistent.content.get("Statistics", {})
        if loaded_stats == {}:
            self.debug("Did not find any saved statistics. Initialized empty.")

        self.changer_stats = self._get_persisted_items(
            "Statistics", "ktc_toolchanger", ChangerStatisticsClass
        )
        self.tool_stats = self._get_persisted_items(
            "Statistics", "ktc_tool", ToolStatisticsClass
        )

    def _get_persisted_items(
        self, section: str, module_name: str, stat_type : type[typing.Any]
    ):
        """Load the persisted state from the file for a given section and item type
        For example, load all persisted ktc_toolchanger stats from the Statistics section.
        Return a dict with the loaded items."""

        loaded_stats: dict = self._ktc_persistent.content.get(section, {})
        if loaded_stats == {}:
            self.debug("Did not find a saved %s section. Initialized empty." % section)

        items: typing.Dict[str, stat_type] = {}
        for item in self.printer.lookup_objects(module_name):
            item_name = ""
            try:
                item_name = str(item[0]).split(" ", 1)[1]

                items[item_name] = stat_type()
                item_dict = loaded_stats.get((module_name + "_" + item_name).lower(), {})

                if item_dict == {}:
                    raise Exception(
                        "Couldn't find the item %s in the saved %s section."
                        % ((item_name), section)
                    )

                for key, value in item_dict.items():
                    if hasattr(items[item_name], key):
                        setattr(items[item_name], key, value)
            except Exception as e:
                self.debug(
                    "Error while loading persistent section %s stats: %s"
                    % (section, str(e))
                )
                self.debug(
                    "Resetting section %s stats for item: %s" % (section, item_name)
                )
                items[item_name] = stat_type()
        return items

    ####################################
    # STATISTICS SAVING  METHODS     #
    ####################################
    def _persist_statistics(self):
        """Save all the statistics to the file"""
        try:
            self._set_persisted_items(
                "Statistics", "ktc_toolchanger", self.changer_stats
            )
            self._set_persisted_items("Statistics", "ktc_tool", self.tool_stats)
        except Exception as e:
            self.debug(
                "Unexpected error whiles saving variables in _persist_statistics: %s"
                % e
            )

    def _set_persisted_items(
        self,
        section: str,
        module_name: str,
        items: typing.MutableMapping[str, typing.Any],
    ):
        """Save the statistics to the file for a given section and item type"""
        try:
            # Save tool statistics for each tool
            for item_name, item in items.items():
                # self.trace(
                #     "_persist_statistics: Saving %s stats for item: %s"
                #     % (section, item_name)
                # )
                # Convert to dict and remove the start_time_* variables so we don't save them
                item_dict = dataclasses.asdict(item)
                item_dict = {
                    k: v
                    for k, v in item_dict.items()
                    if not k.startswith("start_time_")
                }

                # Save the tool statistics to file
                self._ktc_persistent.save_variable(
                    module_name + "_" + item_name, str(item_dict), section=section
                )
        except Exception as e:
            self.debug(
                "Unexpected error whiles saving %s in %s: %s. Not saved."
                % (module_name, section, e)
            )

    ####################################
    # STATISTICS RESET METHODS       #
    ####################################
    def _reset_statistics(self):
        """Reset all the statistics to 0"""
        self.always("Reseting KTC statistics.")

        self.changer_stats = {}
        for changer in self.printer.lookup_objects("ktc_tool_changer"):
            self.changer_stats[str(changer[0]).split(" ", 1)[1]] = ChangerStatisticsClass()

        self.tool_stats = {}
        for tool in self.printer.lookup_objects("ktc_tool"):
            self.tool_stats[str(tool[0]).split(" ", 1)[1]] = ToolStatisticsClass()

    def _reset_print_statistics(self):
        """Reset all the print statistics to same as regular statistics.
        This is called at the start of each print to reset the print statistics.
        The print statistics are subtracted from the regular statistics to get 
        the statistics for the print."""
        self.print_changer_stats = copy.deepcopy(self.changer_stats)
        self.print_tool_stats = copy.deepcopy(self.tool_stats)

    ####################################
    # STATISTICS PRESENTATION METHODS#
    ####################################
    def _dump_statistics(self, since_print_start=False):
        """Dump all the statistics to the console.
        If since_print_start is True, subtract the print stats from the total stats
        and only print the stats for the start of the print."""

        msg = ""
        temp_msg = ""
        if not since_print_start:
            msg_header = "KTC Total Statistics:"
        else:
            msg_header = "KTC Statistics since start of print:\n"

        ##############################  Total
        # This will add the total stats for all changers as a sum and then print them
        temp_msg += self._changer_stats_to_human_string("", since_print_start)
        if temp_msg != "":
            msg += temp_msg + SECTION_SEPARATOR
            temp_msg = ""

        # If has more than one changer, print the stats for each changer
        if len(self.changer_stats.keys()) > 1:
            ##############################  Changers
            # This will print the stats for each changer in a sorted order
            sorted_items = natural_keys_sorting(self.changer_stats.keys())
            for changer_name in sorted_items:
                changer_temp_msg = self._changer_stats_to_human_string(
                    changer_name, since_print_start
                )
                if changer_temp_msg != "":
                    temp_msg += changer_temp_msg + LINE_SEPARATOR

        # If got stats for at least one changer, add them to the message
        # and replace the last line separator with a section separator
        if temp_msg != "" and temp_msg.endswith(LINE_SEPARATOR):
            temp_msg = temp_msg[: -len(LINE_SEPARATOR)]
            msg += temp_msg + (SECTION_SEPARATOR)
            temp_msg = ""

        ##############################  Tools
        # last_tool_was_empty = True
        sorted_items = natural_keys_sorting(self.tool_stats.keys())
        for tool_name in sorted_items:
            # Get the stats for the tool
            temp_tool_msg = self._tool_stats_to_human_string(
                tool_name, since_print_start
            )
            if temp_tool_msg != "":
                temp_msg += temp_tool_msg + LINE_SEPARATOR

        if temp_msg != "" and temp_msg.endswith(LINE_SEPARATOR):
            temp_msg = temp_msg[: -len(LINE_SEPARATOR)]
            msg += temp_msg + SECTION_SEPARATOR
            temp_msg = ""

        # Dump the message to the console and to the log file if enabled
        if msg != "":
            self.always(msg_header + msg)
        else:
            self.always(msg_header + "No statistics recorded.")

    def _changer_stats_to_human_string(
        self, changer_name: str = "", since_print_start=False
    ) -> str:
        """Return a human readable string with the statistics for a given 
        changer. If changer_name is None, return the sum of all changers."""
        result = ""

        if changer_name is None or changer_name == "":
            result_header = ""
        else:
            result_header = "Changer %s:" % changer_name

        tool_stats_sum = self._sum_tool_stats_for_changer(
            changer_name, since_print_start
        )

        ##############################  Selects
        # 264 selects completed(100.0%) in 1:00:00, avg. 13.2s.
        if tool_stats_sum.selects_started > 0:
            result += "\n%s selects completed(%.1f%%) in %s. Avg. %s." % (
                KtcLog.bignumber_to_human_string(tool_stats_sum.selects_completed),
                (
                    tool_stats_sum.selects_completed
                    / tool_stats_sum.selects_started
                    * 100
                ),
                KtcLog.seconds_to_human_string(tool_stats_sum.time_spent_selecting),
                KtcLog.seconds_to_human_string(
                    safe_division(
                        tool_stats_sum.time_spent_selecting,
                        tool_stats_sum.selects_completed,
                    )
                ),
            )

        ##############################  Deselects
        # 264 deselects completed(100.0%) in 1:00:00, avg. 13.2s.
        if tool_stats_sum.deselects_started > 0:
            result += "\n%s deselects completed(%.1f%%)" % (
                KtcLog.bignumber_to_human_string(tool_stats_sum.deselects_completed),
                (
                    tool_stats_sum.deselects_completed
                    / tool_stats_sum.deselects_started
                    * 100
                ),
            )
            result += " in %s." % (
                KtcLog.seconds_to_human_string(tool_stats_sum.time_spent_deselecting)
            )
            result += " Avg. %s." % (
                KtcLog.seconds_to_human_string(
                    safe_division(
                        tool_stats_sum.time_spent_deselecting,
                        tool_stats_sum.deselects_completed,
                    )
                )
            )

        ############################## Engages/Disengages
        # 264 engages and 264 disengages completed.
        # Check if total or specific changer
        changer_stats = ChangerStatisticsClass()
        if changer_name is None or changer_name == "":
            # Add up all the stats for all changers
            for item in self.printer.lookup_objects("ktc_tool_changer"):
                item_name = str(item[0]).split(" ", 1)[1]
                # Check if we display the stats for the start of the print or the total stats
                if not since_print_start:
                    changer_stats += self.changer_stats[item_name]
                else:
                    changer_stats += (
                        self.changer_stats[item_name]
                        - self.print_changer_stats[item_name]
                    )
        else:
            # Check if we display the stats for the start of the print or the total stats
            if not since_print_start:
                changer_stats = self.changer_stats[changer_name]
            else:
                changer_stats = (
                    self.changer_stats[changer_name]
                    - self.print_changer_stats[changer_name]
                )

        # When there are engages, print them
        if changer_stats.engages > 0:
            result += "\n%s engages " % KtcLog.bignumber_to_human_string(changer_stats.engages)

        # Middle of the sentence logic.
        if changer_stats.engages > 0 and changer_stats.disengages > 0:
            result += " and "
        elif changer_stats.disengages > 0:
            result += "\n"
        elif changer_stats.engages > 0:
            result += "."

        # When there are disengages, print them
        if changer_stats.disengages > 0:
            result += "%d disengages completed" % changer_stats.disengages

        ############################## Final
        if result != "":
            result = result_header + result
        return result

    def _sum_tool_stats_for_changer(
        self, changer_name: str, since_print_start=False
    ) -> ToolStatisticsClass:
        """Add up all tool stats for a changer and return a dict with the sum.
        If since_print_start is True, subtract the print stats from the total stats"""

        result = ToolStatisticsClass()

        if changer_name is None or changer_name == "":
            # Get all tools for all changers
            tools_to_sum = typing.cast(
                'ktc.Ktc',self.printer.lookup_object("ktc")).all_tools.items()
        else:
            # Get all tools for the specified changer
            tools_to_sum = typing.cast('ktc_toolchanger.KtcToolchanger', self.printer.lookup_object(
                "ktc_toolchanger " + changer_name
            )).tools.items()

        for tool_name, _ in tools_to_sum:
            # Check if the tool_name has stats (None and Unknown has no stats now).
            if tool_name in self.tool_stats:
                result += self.tool_stats[tool_name]

                if since_print_start:
                    result -= self.print_tool_stats[tool_name]

        return result

    def _tool_stats_to_human_string(
        self, tool_name: str, since_print_start=False
    ) -> str:
        """Return a human readable string with the statistics for a given tool"""
        t = self.tool_stats[tool_name]
        if since_print_start:
            t -= self.print_tool_stats[tool_name]
        result = ""
        result_header = "Tool %s:\n" % (tool_name)

        ##############################  Selected time
        # Selected 1:00:00.
        if t.time_selected > 0:
            result += "Selected %s." % KtcLog.seconds_to_human_string(t.time_selected)
        ##############################  Selects
        # 264 selects completed(100.0%) in 1:00:00, avg. 13.2s.
        if t.selects_started > 0 or not since_print_start:
            result += "\n%s selects completed(%.1f%%)" % (
                KtcLog.bignumber_to_human_string(t.selects_completed),
                (t.selects_completed / t.selects_started * 100),
            )
            result += " in %s." % (KtcLog.seconds_to_human_string(t.time_spent_selecting))
            result += " Avg. %s." % (
                KtcLog.seconds_to_human_string(
                    safe_division(t.time_spent_selecting, t.selects_completed)
                )
            )

        ##############################  Deselects
        # 264 deselects completed(100.0%) in 1:00:00, avg. 13.2s.
        if t.deselects_started > 0:
            result += "\n%s deselects completed(%.1f%%)" % (
                KtcLog.bignumber_to_human_string(t.deselects_completed),
                (t.deselects_completed / t.deselects_started * 100),
            )
            result += " in %s." % (KtcLog.seconds_to_human_string(t.time_spent_deselecting))
            result += " Avg. %s." % (
                KtcLog.seconds_to_human_string(
                    safe_division(t.time_spent_deselecting, t.deselects_completed)
                )
            )

        ##############################  Active times
        # 1:00:00 with heater active and 1:00:00 with heater in standby.
        if t.time_heater_active > 0 or t.time_heater_standby > 0:
            result += "\n%s with heater active" % (
                KtcLog.seconds_to_human_string(t.time_heater_active)
            )

            if t.time_heater_standby > 0:
                result += "and %s with heater in standby" % (
                    KtcLog.seconds_to_human_string(t.time_heater_standby)
                )
            result += "."

        if result != "":
            result = result_header + result
        return result

    ### STATISTICS INCREMENTING CHANGER METHODS
    def track_changer_engage(self, changer: 'ktc_toolchanger.KtcToolchanger'):
        self.changer_stats[changer.name].engages += 1
        self._persist_statistics()

    def track_changer_disengage(self, changer: 'ktc_toolchanger.KtcToolchanger'):
        self.changer_stats[changer.name].disengages += 1
        self._persist_statistics()

    ### STATISTICS INCREMENTING TOOL METHODS
    # Having all here makes it easier to change how the statistics are tracked
    # at a later time. It also makes it easy to search for all places where
    # statistics are tracked for debugging.
    def track_tool_selecting_start(self, tool: 'ktc_tool.KtcTool'):
        self.tool_stats[tool.name].start_time_spent_selecting = int(time.time())
        self.tool_stats[tool.name].selects_started += 1

    def track_tool_selecting_end(self, tool: 'ktc_tool.KtcTool'):
        self._increase_tool_time_diff(tool, "time_spent_selecting")
        self.tool_stats[tool.name].selects_completed += 1
        self._persist_statistics()

    def track_tool_deselecting_start(self, tool: 'ktc_tool.KtcTool'):
        self.tool_stats[tool.name].start_time_spent_deselecting = int(time.time())
        self.tool_stats[tool.name].deselects_started += 1

    def track_tool_deselecting_end(self, tool: 'ktc_tool.KtcTool'):
        self._increase_tool_time_diff(tool, "time_spent_deselecting")
        self.tool_stats[tool.name].deselects_completed += 1
        self._persist_statistics()

    def track_tool_selected_start(self, tool: 'ktc_tool.KtcTool'):
        self.tool_stats[tool.name].start_time_selected = int(time.time())
        self.tool_stats[tool.name].selects_completed += 1

    def track_tool_selected_end(self, tool: 'ktc_tool.KtcTool'):
        self._increase_tool_time_diff(tool, "time_selected")
        self._persist_statistics()

    # Heater tracking
    # Active start is called when the extruder state changes to ACTIVE.
    # Will call actve end for all other tools having any of the same heaters and
    # having running active timers.

    # Standby start is called when the heater timer is run for standby
    # and will set the active end for any tool having any of the same heaters and being in 
    # standby mode.

    # Active end and Standby end is also tracked when the extruder state changes to OFF
    # and will set the active end and standby end for any tool having any of the same
    # heaters and being in off or standby and having running statistics timers.
    def track_heater_active_start(self, tool: 'ktc_tool.KtcTool'):
        self.tool_stats[tool.name].start_time_heater_active = int(time.time())
        self.track_heater_active_end_for_other_tools(tool)
        self.debug(
            f"track_heater_active_start: Tool: {tool.name}")

    def track_heater_active_end_for_tools_having_heater(self, heater: 'ktc_heater.KtcHeater'):
        for tool in self._ktc.all_tools.values():
            if tool not in self._ktc.INVALID_TOOLS:
                # self.debug(
                #     "track_heater_active_end_for_tools_having_heater: "
                #     + f"Heater: {heater.name}: Tool: {tool.name} .start_time_heater_active: "
                #     + f"{self.tool_stats[tool.name].start_time_heater_active}")
                if self.tool_stats[tool.name].start_time_heater_active:
                    # self.debug(
                    #     "track_heater_active_end_for_tools_having_heater: "
                    #     + f"Tool: {tool.name}: Is in Active mode."
                    #     + f" Will check if heater: {heater.name} is in heater_names: "
                    #     + f"{tool.extruder.heater_names()}")

                    if heater.name in tool.extruder.heater_names():
                        self.debug(
                            "track_heater_active_end_for_tools_having_heater: "
                            + f"Heater: {heater.name}: Active end called for tool: {tool.name}")
                        self.track_heater_active_end(tool)

    def track_heater_active_end_for_other_tools(self, tool_still_active: 'ktc_tool.KtcTool'):
        '''Called when a tool changes state to active. 
        Will call active end for all other tools having any of the same heaters and
        having running active timers.'''
        invalid_tools = (tool_still_active, self._ktc.TOOL_NONE, self._ktc.TOOL_UNKNOWN, None)
        for tool in tool_still_active._ktc.all_tools.values():  # pylint: disable=protected-access
            if tool not in invalid_tools:
                if self.tool_stats[tool.name].start_time_heater_active:
                    for heater_name in tool.extruder.heater_names():
                        if heater_name in tool_still_active.extruder.heater_names():
                            self.debug(
                                "track_heater_active_end_for_other_tools: "
                                + f"Tool: {tool_still_active.name}: "
                                + f"Active end called for tool: {tool.name}")
                            self.track_heater_active_end(tool)

    def track_heater_standby_start_for_standby_tools_having_heater(
        self, heater: 'ktc_heater.KtcHeater'):
        '''Called by the HeaterTimer when the heater is set to standby.'''
        for tool in self._ktc.all_tools.values():
            if tool not in self._ktc.INVALID_TOOLS:
                # self.debug(
                #     "track_heater_standby_start_for_standby_tools_having_heater: "
                #     + f"Tool: {tool.name} .extruder.state: {tool.extruder.state}")
                if tool.extruder.state == 1:
                    # self.debug(
                    #     "track_heater_standby_start_for_standby_tools_having_heater: "
                    #     + f"Tool: {tool.name}: Is in Standby mode."
                    #     + f" Will check if heater: {heater.name} is in heater_names: "
                    #     + f"{tool.extruder.heater_names()}")
                    if heater.name in tool.extruder.heater_names():
                        self.debug(
                            "track_heater_standby_start_for_standby_tools_having_heater: "
                            + f"Heater {heater.name} is in tool: {tool.name}")
                        self.track_heater_standby_start(tool)
                        # self.debug(
                        #     "track_heater_standby_start_for_standby_tools_having_heater: "
                        #     + f"Tool: {tool.name}: Standby start called for tool: {tool.name}")

    def track_heater_end_for_tools_having_heater(self, heater: 'ktc_heater.KtcHeater'):
        '''Called by the HeaterTimer when the heater is set to off.'''
        for tool in self._ktc.all_tools.values():
            if tool not in self._ktc.INVALID_TOOLS:
                if self.tool_stats[tool.name].start_time_heater_standby:
                    if heater.name in tool.extruder.heater_names():
                        if self.tool_stats[tool.name].start_time_heater_standby:
                            self.debug(
                                "track_heater_end_for_tools_having_heater: "
                                + f"Heater: {heater.name}: Standby end called "
                                + "for tool: {tool.name}")
                            self.track_heater_standby_end(tool)
                if self.tool_stats[tool.name].start_time_heater_active:
                    if heater.name in tool.extruder.heater_names():
                        if self.tool_stats[tool.name].start_time_heater_active:
                            self.debug(
                                "track_heater_end_for_tools_having_heater: "
                                + f"Heater: {heater.name}: Active end called for tool: {tool.name}")
                            self.track_heater_active_end(tool)

    def track_heater_active_end(self, tool: 'ktc_tool.KtcTool'):
        self.debug(
            f"track_heater_active_end: Tool: {tool.name}")
        self._increase_tool_time_diff(tool, "time_heater_active")
        self._persist_statistics()

    def track_heater_standby_start(self, tool: 'ktc_tool.KtcTool'):
        self.debug(
            f"track_heater_standby_start: Tool: {tool.name}")
        self.tool_stats[tool.name].start_time_heater_standby = int(time.time())

    def track_heater_standby_end(self, tool: 'ktc_tool.KtcTool'):
        self.debug(
            f"track_heater_standby_end: Tool: {tool.name}")
        self._increase_tool_time_diff(tool, "time_heater_standby")
        self._persist_statistics()

    def _increase_tool_time_diff(self, tool: 'ktc_tool.KtcTool', final_time_key: str):
        """Increase the time difference for a tools statistics."""
        try:
            start_time = getattr(
                self.tool_stats[tool.name], "start_" + final_time_key, 0
            )
            if start_time == 0:
                return

            time_spent = max(time.time() - start_time, 0)

            final_time = getattr(self.tool_stats[tool.name], final_time_key, 0)
            final_time += time_spent

            setattr(self.tool_stats[tool.name], "start_" + final_time_key, 0)
        except Exception as e:
            # Handle any exceptions that occur during the process
            self.always(f"An error occurred in KTC_Log._increase_tool_time_diff(): {e}")

    ####################################
    # STATIC METHODS: data to string   #
    ####################################
    @staticmethod
    def seconds_to_human_string(seconds, long_format=False):
        """Convert a number of seconds to a human readable string in the format 1h 2m 3s
        or 1 hours 2 minutes 3 seconds if long_format is True."""
        result = ""
        hours = int(math.floor(seconds / 3600.0))
        if long_format:
            if hours >= 1:
                result += "%d hours " % hours
            minutes = int(math.floor(seconds / 60.0) % 60)
            if hours >= 1 or minutes >= 1:
                result += "%d minutes " % minutes
            result += "%d seconds" % int((math.floor(seconds) % 60))
        else:
            if hours >= 1:
                result += "%dh " % hours
            minutes = int(math.floor(seconds / 60.0) % 60)
            if hours >= 1 or minutes >= 1:
                result += "%dm " % minutes
            result += "%ds" % int((math.floor(seconds) % 60))
        return result

    @staticmethod
    def bignumber_to_human_string(number):
        """Convert a number to a human readable string in the format 1.2K, 2.3M, 3.4B etc."""
        if number >= 1000000000:
            return "%.1fB" % (number / 1000000000)
        if number >= 1000000:
            return "%.1fM" % (number / 1000000)
        if number >= 1000:
            return "%.1fK" % (number / 1000)
        return "%d" % number

    ####################################
    # HELPER FUNCTIONS: data to string #
    ####################################

    ### LOGGING AND STATISTICS METHODS GCODE
    cmd_KTC_RESET_STATS_help = "Reset the KTC statistics"
    def cmd_KTC_RESET_STATS(self, gcmd):
        param = gcmd.get("SURE", "no")
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

    cmd_KTC_STATS_REPORT_help = "Dump the KTC statistics"
    def cmd_KTC_STATS_REPORT(self, gcmd): # pylint: disable=unused-argument
        self._dump_statistics()

    cmd_KTC_RESET_PRINT_STATS_help = (
        "Run at start of a print to initialize the KTC print statistics"
    )
    def cmd_KTC_RESET_PRINT_STATS(self, gcmd):   # pylint: disable=unused-argument
        self._reset_print_statistics()

    cmd_KTC_PRINT_STATS_REPORT_help = (
        "Run at end of a print to list statistics since last print reset."
    )
    def cmd_KTC_PRINT_STATS_REPORT(self, gcmd):   # pylint: disable=unused-argument
        self._dump_statistics(since_print_start=True)

    cmd_KTC_SET_LOG_LEVEL_help = "Set the log level for the KTC"
    def cmd_KTC_SET_LOG_LEVEL(self, gcmd):
        self.log_level = gcmd.get_int("LEVEL", self.log_level, minval=0, maxval=4)
        self.logfile_level = gcmd.get_int(
            "LOGFILE", self.logfile_level, minval=0, maxval=4
        )

    cmd_KTC_LOG_ALWAYS_help = "Log allways MSG"
    def cmd_KTC_LOG_ALWAYS(self, gcmd):
        msg = gcmd.get("MSG")
        self.always(msg)

    cmd_KTC_LOG_INFO_help = "Log info MSG"
    def cmd_KTC_LOG_INFO(self, gcmd):
        msg = gcmd.get("MSG")
        self.info(msg)

    cmd_KTC_LOG_DEBUG_help = "Log debug MSG"
    def cmd_KTC_LOG_DEBUG(self, gcmd):
        msg = gcmd.get("MSG")
        self.debug(msg)

    cmd_KTC_LOG_TRACE_help = "Log trace MSG"
    def cmd_KTC_LOG_TRACE(self, gcmd):
        msg = gcmd.get("MSG")
        self.trace(msg)


####################################
# LOGGING Que Handling             #
####################################
# Forward all messages through a queue (polled by background thread)
class KtcQueueHandler(logging.Handler):
    def __init__(self, myqueue):
        logging.Handler.__init__(self)
        self.queue = myqueue

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
            self, filename, when="midnight", backupCount=5
        )
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
# Statistics Data Classes          #
####################################
@dataclasses.dataclass
class StatisticsBaseClass:
    '''Used for type hinting.'''
    def __add__(self, other):
        return self._add_subtract_stat(self, other, operator.add)

    def __sub__(self, other):
        return self._add_subtract_stat(self, other, operator.sub)

    @staticmethod
    def _add_subtract_stat(a, b, op):
        """Add or subtract two statistics objects and return the result"""
        result = copy.deepcopy(a)
        for f in dataclasses.fields(result):
            setattr(result, f.name, op(getattr(a, f.name), getattr(b, f.name)))
        return result

@dataclasses.dataclass
class ChangerStatisticsClass(StatisticsBaseClass):
    """Statistics for a tool changer"""

    engages: int = 0
    disengages: int = 0

@dataclasses.dataclass
class ToolStatisticsClass(StatisticsBaseClass):
    """Statistics for a tool"""

    selects_completed: int = 0
    deselects_completed: int = 0
    selects_started: int = 0
    deselects_started: int = 0
    time_selected: int = 0
    time_heater_active: int = 0
    time_heater_standby: int = 0
    time_spent_selecting: int = 0
    time_spent_deselecting: int = 0
    start_time_selected: int = 0  # TRACKED_START_TIME_SELECTED
    start_time_heater_active: int = 0  # TRACKED_START_TIME_ACTIVE
    start_time_heater_standby: int = 0  # TRACKED_START_time_heater_standby
    start_time_spent_selecting: int = 0  # TRACKED_MOUNT_START_TIME
    start_time_spent_deselecting: int = 0  # TRACKED_UNMOUNT_START_TIME



####################################
# MultiLineFormater                #
####################################
# Class to improve formatting of multi-line KTC messages
class KtcMultiLineFormatter(logging.Formatter):
    def format(self, record):
        indent = " " * 9
        lines = super(KtcMultiLineFormatter, self).format(record)
        return lines.replace("\n", "\n" + indent)

####################################
# HELPER FUNCTIONS: Natural Sorting#
####################################
# https://stackoverflow.com/questions/5967500/how-to-correctly-sort-a-string-with-a-number-inside
def natural_keys_sorting(list_to_sort):
    return sorted(list_to_sort, key=natural_sorting)

def natural_sorting(text):
    """
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    """
    return [__atoi(c) for c in re.split(r"(\d+)", text)]

def __atoi(text):
    return int(text) if text.isdigit() else text


# Function to avoid division by zero
def safe_division(dividend, divisor):
    return dividend / divisor if divisor else 0


####################################
def load_config(config):
    return KtcLog(config)
