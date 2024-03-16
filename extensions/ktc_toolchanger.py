# KTC - Klipper Tool Changer code
# Toollock and general Tool support
#
# Copyright (C) 2024  Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#

# from enum import unique
import typing
# import cProfile, pstats
from enum import unique
from .ktc_base import KtcConstantsClass, KtcBaseChangerClass, KtcConfigurableEnum # pylint: disable=relative-beyond-top-level

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile
    from ...klipper.klippy.extras import gcode_macro as klippy_gcode_macro
    from . import ktc_persisting, ktc_tool

@typing.final
class KtcToolchanger(KtcBaseChangerClass, KtcConstantsClass):
    """Class initialized for each toolchanger.
    At least one toolchanger will be initialized for each printer.
    A "default_toolchanger" will be initialized if no toolchanger
    is specified in the config."""

    def __init__(self, config: 'configfile.ConfigWrapper'):
        # Most of the function is inherited from the base class.
        super().__init__(config)

        # When is the toolchanger initialized in relation to printer start and homing.
        self.init_mode = self.InitModeType.get_value_from_configuration(
            config, "init_mode", self.InitModeType.MANUAL)        # type: ignore

        # And in relation to the parent tool.
        self.init_order = self.InitOrderType.get_value_from_configuration(
            config, "init_order", self.InitOrderType.INDEPENDENT)

        self._selected_tool = self.TOOL_UNKNOWN  # The currently active tool. Default is unknown.

        # Load the parent tool if it is defined.
        parent_tool_name = config.get("parent_tool", None)  # type: ignore
        if parent_tool_name is not None and parent_tool_name != "":
            self.parent_tool = typing.cast('ktc_tool.KtcTool',
                                           self.printer.load_object(    # type: ignore
                config, "ktc_tool " + parent_tool_name))  # type: ignore
            if self.parent_tool is None:
                raise config.error(
                    "parent_tool %s not found for ktc_toolchanger %s."
                    % (parent_tool_name, self.name)
                )

    @property
    def selected_tool(self):
        return self._selected_tool

    @selected_tool.setter
    def selected_tool(self, value: 'ktc_tool.KtcTool'):
        if self._selected_tool == value:
            return
        self._selected_tool = value
        self.persistent_state = {"selected_tool": value.name}

    def configure_inherited_params(self):
        super().configure_inherited_params()
        self.gcode_macro = typing.cast('klippy_gcode_macro.PrinterGCodeMacro', # type: ignore # pylint: disable=attribute-defined-outside-init
                                  self.printer.lookup_object("gcode_macro"))    # type: ignore
        self.state = self.StateType.CONFIGURED  # pylint: disable=attribute-defined-outside-init # pylint bug

    def initialize(self):
        """Initialize the tool lock."""
        # Sanity check. If the parent tool is not defined,
        # the init_order should be set to independent.
        if (self.init_order != self.InitOrderType.INDEPENDENT and
            self.parent_tool is not None):
            raise Exception(
                "Toolchanger %s has no parent tool " % self.name
                + "defined but init_order is set to AFTER_PARENT."
            )

        # If tool is anything but configured, log it.
        if self.state != self.StateType.CONFIGURED:
            self.log.debug("Initializing toolchanger %s from state %s." % (self.name, self.state))
        self.state = self.StateType.INITIALIZING

        # Order check. If dependent on parent.
        if (self.init_order == self.InitOrderType.AFTER_PARENT_INITIALIZATION or
            self.init_order == self.InitOrderType.AFTER_PARENT_SELECTED):
            # Initialize parent if not already.
            if self.parent_tool.toolchanger.state < self.StateType.INITIALIZED:
                self.parent_tool.toolchanger.initialize()
            # Select parent if not already and needed.
            if self.init_order == self.InitOrderType.AFTER_PARENT_SELECTED:
                self.parent_tool.select()

        # Restore the active tool from the persistent variables.
        selected_tool_name = str.lower(self.persistent_state.get(
            "selected_tool", self.TOOL_UNKNOWN.name
        ))

        # Set the active tool to the tool with the name from the persistent variables.
        # If not found in the tools that are loaded for this changer, set it to TOOL_UNKNOWN.
        if selected_tool_name == self.TOOL_NONE.name:
            self.selected_tool = self.TOOL_NONE
        else:
            self.selected_tool = self.tools.get(selected_tool_name, self.TOOL_UNKNOWN)

        if (self.selected_tool == self.TOOL_UNKNOWN and
            selected_tool_name != self.TOOL_UNKNOWN.name
            ):
            self.log.always(
                "Initial tool %s not found for ktc_toolchanger %s. Using tool %s."
                % (selected_tool_name, self.name, self.selected_tool.name)
            )

        # Run the init gcode template if it is defined.
        if self._init_gcode != "":
            init_gcode_template = self.gcode_macro.load_template(   # type: ignore
                self.config, "", self._init_gcode)
            context = init_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self._ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            init_gcode_template.run_gcode_from_command(context)
            # Check that the gcode has changed the state.
            if self.state == self.StateType.CONFIGURED:
                raise self.config.error(
                    ("ktc_toolchanger %s: init_gcode did not " % self.name)
                    + "change the state. Use for example "
                    + "'KTC_TOOLCHANGER_SET_STATE TOOLCHANGER={myself.name} STATE=READY' to "
                    + "change the state to READY."
                )
        else:
            self.state = self.StateType.READY

        # Set the tool as engaged. Fir tools it is equivalent to selected.
        self.selected_tool.state = self.StateType.ENGAGED

    def engage(self, disregard_engaged=False):
        '''Engage the lock on the tool so it can be removed.'''
        try:
            if self.state < self.StateType.INITIALIZING:
                raise Exception(
                    "Status is: %s. Can't engage %s." % (self.state, self.name)
                )

            if self._engage_gcode == "":
                self.state = self.StateType.ENGAGED
                return

            if not disregard_engaged and self.state == self.StateType.ENGAGED:
                self.log.always(
                    "ktc_toolchanger %s is already engaged with tool %s."
                    % (self.name, self.selected_tool.name)
                    + " DISREGARD_ENGAGED is not set. No action taken."
                )
                return

            if self.state >= self.StateType.ENGAGING:
                self.state = self.StateType.ENGAGING

            engage_gcode_template = self.gcode_macro.load_template(
                self.config, "", self._engage_gcode)
            context = engage_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self._ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            engage_gcode_template.run_gcode_from_command(context)

            if (self.state == self.StateType.ENGAGING or
                self.state == self.StateType.INITIALIZING):
                raise self.config.error(
                    ("engage_gcode did not change the state. Use for example "
                    + "'KTC_TOOLCHANGER_SET_STATE TOOLCHANGER={myself.name} STATE=ENGAGED' to "
                    + "change the state to ENGAGED. Or ERROR if it failed.")
                )
            elif self.state == self.StateType.ERROR:
                raise self.config.error(
                    "disengage_gcode failed. Check the logs for more information."
                )

            self.log.changer_stats[self.name].engages += 1
            self.log.trace(f"ktc_toolchanger.engage(): Setting state to {self.state}.")
        except Exception as e:
            self.state = self.StateType.ERROR
            # self._ktc.state = self.StateType.ERROR
            raise self.printer.command_error(
                "Engage failed for ktc_toolchanger %s with error: %s" 
                % (self.name, e)) from e

    def disengage(self, disregard_disengaged=True):
        """Disengage the lock on the tool so it can be removed."""
        try:
            if self.state < self.StateType.INITIALIZING:
                raise Exception(
                    "Status is: %s. Can't disengage %s." % (self.state, self.name)
                )

            if self._disengage_gcode == "":
                self.state = self.StateType.READY
                return

            if not disregard_disengaged and self.state == self.StateType.READY:
                self.log.always(
                    "ktc_toolchanger %s is already disengaged with tool %s."
                    % (self.name, self.selected_tool.name)
                    + " DISREGARD_DISENGAGED is not set. No action taken."
                )
                return

            if self.state >= self.StateType.DISENGAGING:
                self.state = self.StateType.DISENGAGING

            disengage_gcode_template = self.gcode_macro.load_template(
                self.config, "", self._disengage_gcode)
            context = disengage_gcode_template.create_template_context()
            context['myself'] = self.get_status()
            context['ktc'] = self._ktc.get_status()
            context['STATE_TYPE'] = self.StateType
            disengage_gcode_template.run_gcode_from_command(context)

            if (self.state == self.StateType.DISENGAGING or
                self.state == self.StateType.INITIALIZING):
                raise self.config.error(
                    ("disengage_gcode did not "
                    + "change the state. Use for example "
                    + "'KTC_TOOLCHANGER_SET_STATE TOOLCHANGER={myself.name} STATE=READY' to "
                    + "change the state to READY. Or ERROR if it failed.")
                )
            elif self.state == self.StateType.ERROR:
                raise self.config.error(
                    "disengage_gcode failed. Check the logs for more information."
                )

            self.log.changer_stats[self.name].disengages += 1
            self.log.trace("ktc_toolchanger.engage(): Setting state to %s." % self.state)
        except Exception as e:
            self.state = self.StateType.ERROR
            # self._ktc.state = self.StateType.ERROR
            raise self.printer.command_error(
                "Disengage failed for ktc_toolchanger %s with error: %s" %
                (self.name, e))

    @KtcBaseChangerClass.state.setter
    def state(self, value):
        super(KtcBaseChangerClass, type(self)).state.fset(self, value)  # type: ignore
        # TODO: Remove when debugged.
        self.log.always(
            f"KTC Toolchanger {self.name} is now {str(self.state).lower()}."
        )

        if self._ktc.propagate_state:
            self._ktc.state = value

        if value == self.StateType.ENGAGING:
            self.selected_tool = self.TOOL_UNKNOWN
        elif value == self.StateType.READY:
            self.selected_tool = self.TOOL_NONE
        elif value == self.StateType.ERROR:
            self.log.always("KTC Toolchanger %s is now in error state." % self.name)
            self.selected_tool = self.TOOL_UNKNOWN

    def get_status(self, eventtime=None):   # pylint: disable=unused-argument
        status = {
            # "global_offset": self.global_offset,
            "name": self.name,
            "selected_tool": self.selected_tool.name,
            "selected_tool_n": self.selected_tool.number,
            "state": self.state,
            "init_mode": self.init_mode,
            "tools": list(self.tools),
            "params_available": str(self.params.keys()),
            **self.params,
        }
        return status

    @unique
    class InitModeType(str, KtcConfigurableEnum):
        """Constants for the initialization mode of the toolchanger.
        Inherits from str so it can be JSON serializable."""
        MANUAL = "manual"
        ON_START = "on_start"
        ON_FIRST_USE = "on_first_use"
        # Can be manual and call KTC_TOOLCHANGER_INITIALIZE from gcode homing macro.
            # HOMING_START = "homing_start"
            # HOMING_END = "homing_end"

    @unique
    class InitOrderType(str, KtcConfigurableEnum):
        """Constants for the initialization order of the toolchanger."""
        INDEPENDENT  = "independent"
        AFTER_PARENT_SELECTED = "after_parent_selected"
        AFTER_PARENT_INITIALIZATION = "after_parent_initialization"

def load_config_prefix(config):
    """Load the toolchanger object with the given config.
    This is called by Klipper to initialize the toolchanger object."""
    # prof = cProfile.Profile()

    # retval = prof.runcall(KtcToolchanger, config)

    # output = io.StringIO()
    # stats = pstats.Stats(prof, stream=output).sort_stats('cumtime')
    # stats.print_stats()
    # stats_string = output.getvalue()
    # output.close()
    # carriage_return_count = stats_string.count('\n')
    # if carriage_return_count >= 20:
    #     index = -1
    #     for _ in range(20):
    #         index = stats_string.find('\n', index + 1)
    #     # index now contains the index of the 10th carriage return
    # else:
    #     index = len(stats_string) - 1
    # retval.init_profile = stats_string[:index]

    # return retval

    return KtcToolchanger(config)
