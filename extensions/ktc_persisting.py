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
# This module will also only save the variables when needed and no more.
# This is to avoid excessive writes to the SD card and overhaed on the system.

import os.path, ast, configparser, typing

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile
    from ...klipper.klippy import klippy, reactor
    from. import ktc_log

# Constant values moved here to avoid circular imports
KTC_SAVE_VARIABLES_FILENAME = "~/ktc_variables.cfg"
KTC_SAVE_VARIABLES_DELAY = 10

class KtcPersisting:
    def __init__(self, config: 'configfile.ConfigWrapper'):
        self.printer : 'klippy.Printer' = config.get_printer()
        self.reactor: 'reactor.Reactor' = self.printer.get_reactor()
        self.log = typing.cast('ktc_log.KtcLog', self.printer.load_object(
            config, "ktc_log"
        ))

        self.filename = os.path.expanduser(KTC_SAVE_VARIABLES_FILENAME)

        self.content = {}
        self.ready_to_save = False

        # Set up timer to only save values when needed
        # and no more than once every 10 seconds to allow for
        # multiple changes and avoid excessive writes
        self.timer_save = self.reactor.register_timer(
            self._save_changes_timer_event,
            self.reactor.monotonic() + (KTC_SAVE_VARIABLES_DELAY),
        )

        try:
            if not os.path.exists(self.filename):
                open(self.filename, "w", encoding="utf-8").close()
            self.load_content()
        except Exception as e:
            raise e.with_traceback(e.__traceback__)

    # Remove the timer when Klipper shuts down
    def disconnect(self):
        self.reactor.update_timer(self.timer_save, self.reactor.NEVER)

    def load_content(self):
        sections = {}
        varfile = configparser.ConfigParser()
        try:
            varfile.read(self.filename)
            # Load variables for each section
            for section in varfile.sections():
                sections[section] = {}
                for name, val in varfile.items(section):
                    sections[section][name] = ast.literal_eval(val)
        except Exception as e:
            msg = "Unable to parse existing KTC variable file: %s" % (self.filename,)
            raise Exception(msg) from e
        self.content = sections

    def save_variable(self, varname: str, value: str, section: str = "Variables",
                      force_save: bool = False):
        try:
            value = ast.literal_eval(value)
        except ValueError as e:
            raise Exception("Unable to parse '%s' as a literal: %s" % (value, e)) from e

        if section not in self.content:
            self.log.trace("Creating section %s" % (section,))
            self.content[section] = {}

        self.content[section][varname] = value
        self.ready_to_save = True

        if force_save:
            self.force_save()

    def force_save(self):
        self.ready_to_save = True
        self._save_changes_timer_event(self.reactor.monotonic())

    def _save_changes_timer_event(self, eventtime):
        try:
            if self.ready_to_save:
                self.ready_to_save = False
                self.log.trace("Saving state in logs.")

                # Write file
                varfile = configparser.ConfigParser()
                for section, variables in sorted(self.content.items()):
                    self.log.trace("Saving section %s" % (section,))
                    varfile.add_section(section)
                    for name, val in sorted(variables.items()):
                        varfile.set(section, name, repr(val))

                f = open(self.filename, "w", encoding="utf-8")
                varfile.write(f)
                f.close()
        except Exception as e:
            self.log.debug("_save_changes_timer_event:Exception: %s" % (str(e)))
            raise e.with_traceback(e.__traceback__)
        nextwake = eventtime + KTC_SAVE_VARIABLES_DELAY
        return nextwake

    def get_status(self, eventtime=None):   # pylint: disable=unused-argument
        status = {
            "content": self.content,
        }
        return status


def load_config(config):
    return KtcPersisting(config)
