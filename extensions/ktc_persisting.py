# KTC - Klipper Tool Changer code (v.2)
# Persistent storage of variables for the KTC
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

# This is based on the Klipper save_variables.py to be able to 
# save variables from KTC inddependent of other plugins.
# Using the default save_variables.py will cause conflicts when 
# other plugins such as HappyHare tries to reference the file again.
# This will use a different filename to avoid this incompatibility.
# 
# This plugin will also only save the variables when needed and no more.
# This is to avoid excessive writes to the SD card and overhaed on the system.

import os.path, ast, configparser
from . import ktc, ktc_log

class KtcPersisting:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.log: ktc_log.Ktc_Log = self.printer.load_object(
            config, "ktc_log"
        )  # Load the log object.

        self.filename = os.path.expanduser(ktc.KTC_SAVE_VARIABLES_FILENAME)

        self.vars = {}
        self.ready_to_save = False

        # Set up timer to only save values when needed
        # and no more than once every 10 seconds to allow for
        # multiple changes and avoid excessive writes
        self.timer_save = self.reactor.register_timer(
            self._save_changes_timer_event,
            self.reactor.monotonic() + (ktc.KTC_SAVE_VARIABLES_DELAY),
        )

        try:
            if not os.path.exists(self.filename):
                open(self.filename, "w").close()
            self.load_vars()
        except Exception as e:
            raise e.with_traceback(e.__traceback__)

    # Remove the timer when Klipper shuts down
    def disconnect(self):
        self.reactor.update_timer(self.timer_save, self.reactor.NEVER)

    def load_vars(self):
        allvars = {}
        varfile = configparser.ConfigParser()
        try:
            varfile.read(self.filename)
            # Load variables for each section
            for section in varfile.sections():
                allvars[section] = {}
                for name, val in varfile.items(section):
                    allvars[section][name] = ast.literal_eval(val)
        except:
            msg = "Unable to parse existing KTC variable file: %s" % (self.filename,)
            raise msg
        self.vars = allvars

    def save_variable(self, varname: str, value: str, section: str ="Variables", force_save: bool=False) -> None:
        try:
            self.log.trace("save_variable  %s %s, value type %s" % (varname, value, type(value)))
            value = ast.literal_eval(value)
        except ValueError as e:
            raise Exception("Unable to parse '%s' as a literal: %s" % (value, e))

        if not section in self.vars:
            self.log.trace("Creating section %s" % (section,))
            self.vars[section] = {}

        self.vars[section][varname] = value
        self.log.trace("save_variable  %s" % (varname,))
        self.ready_to_save = True

        if force_save:
            self._save_changes_timer_event(self.reactor.monotonic())

    def _save_changes_timer_event(self, eventtime):
        try:
            if self.ready_to_save:
                self.ready_to_save = False
                self.log.trace("Saving state in logs.")

                # Write file
                varfile = configparser.ConfigParser()
                for section, vars in sorted(self.vars.items()):
                    self.log.trace("Saving section %s" % (section,))
                    varfile.add_section(section)
                    for name, val in sorted(vars.items()):
                        varfile.set(section, name, repr(val))

                f = open(self.filename, "w")
                varfile.write(f)
                f.close()
        except Exception as e:
            self.log.debug("_save_changes_timer_event:Exception: %s" % (str(e)))
            raise e.with_traceback(e.__traceback__)
        nextwake = eventtime + ktc.KTC_SAVE_VARIABLES_DELAY
        return nextwake

    def get_status(self, eventtime=None):
        status = {
            "vars": self.vars,
        }
        return status


def load_config(config):
    return KtcPersisting(config)
