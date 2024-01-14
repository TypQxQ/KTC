# This is copied from the save_variables.py to be able to save variables from the KTC inddependent of other plugins.
# Using the default save_variables.py will cause conflicts when other plugins such as HappyHare tries to load it again.
# Will use a different filename to avoid this.
import os.path, ast, configparser
from . import ktc_log, ktc

class KtcSaveVariables:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.log : ktc_log.Ktc_Log = self.printer.load_object(config, 'ktc_log')  # Load the log object.
        
        self.filename = os.path.expanduser(ktc.KTC_SAVE_VARIABLES_FILENAME)

        self.vars = {}
        self.ready_to_save = False

        # Set up timer to only save values when needed 
        # and no more than once every 10 seconds to allow for
        # multiple changes and avoid excessive writes
        self.timer_save = self.reactor.register_timer(
            self._save_changes_timer_event, self.reactor.monotonic() 
            + (ktc.KTC_SAVE_VARIABLES_DELAY))

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

    def save_variable(self, varname, value, section='Variables', force_save=False):
        # self.log.trace("Saving variable '%s' as '%s' to the '%s' section" % (varname, value, section))
        try:
            value = ast.literal_eval(value)
        except ValueError as e:
            raise Exception("Unable to parse '%s' as a literal" % (value,))

        if not section in self.vars:
            self.vars[section] = {}

        self.vars[section][varname] = value
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
                    varfile.add_section(section)
                    for name, val in sorted(vars.items()):
                        varfile.set(section, name, repr(val))
                        # self.log.trace("Saving to file variable '%s' as '%s' in section '%s'" % (name, val, section))

                f = open(self.filename, "w")
                varfile.write(f)
                f.close()
        except Exception as e:
            self.log.debug("_save_changes_timer_event:Exception: %s" % (str(e)))
            raise e.with_traceback(e.__traceback__)
        nextwake = eventtime + ktc.KTC_SAVE_VARIABLES_DELAY
        return nextwake
    
    def get_status(self, eventtime= None):
        status = {
            "vars": self.vars,
        }
        return status

def load_config(config):
    return KtcSaveVariables(config)
