# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

from typing import cast
from threading import Thread
import logging

from pyrenode3.inits import XwtInit
from pyrenode3.wrappers import Emulation, Monitor

from System import ConsoleColor
from Antmicro.Renode import Emulator
from Antmicro.Renode.UI import ConsoleWindowBackendAnalyzer
from Antmicro.Renode.UserInterface import ShellProvider
from AntShell import Prompt, Shell
from AntShell.Terminal import NavigableTerminalEmulator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("state.py")


class State:
    def __init__(self, logging_port: int, gui_enabled: bool):
        self.running = True

        self.emulation = Emulation()
        self._m = Monitor()
        self._m.internal.Quitted += lambda: logging.debug("closing") or self.quit()
        self.shell = None

        self.execute(f"logNetwork {logging_port}")

        if gui_enabled:
            self._prepare_gui()
        else:
            from Antmicro.Renode.Peripherals.UART import UARTBackend
            from Antmicro.Renode.Analyzers import LoggingUartAnalyzer

            self.emulation.internal.BackendManager.SetPreferredAnalyzer(
                UARTBackend, LoggingUartAnalyzer
            )

    def quit(self):
        if self.shell:
            self.shell.Stop()
        self.running = False

    def execute(self, command: str):
        self._write_shell_command(command)

        out, err = self._m.execute(command)

        self._write_shell_output(out, err)
        return out, err

    def _prepare_gui(self):
        XwtInit()
        monitor = self._m.internal

        terminal = ConsoleWindowBackendAnalyzer(True)
        io = terminal.IO

        shell = ShellProvider.GenerateShell(monitor)
        shell.Terminal = NavigableTerminalEmulator(io)

        Emulator.BeforeExit += shell.Stop
        terminal.Quitted += Emulator.Exit
        terminal.Show()

        monitor.Quitted += shell.Stop
        shell.Quitted += Emulator.Exit

        monitor.Interaction = shell.Writer

        def prompt_change(machine_name):
            self.prompt = (
                Prompt(f"({machine_name}) ", ConsoleColor.DarkYellow)
                if machine_name
                else self.default_prompt
            )
            cast(Shell, self.shell).SetPrompt(self.prompt)

        monitor.MachineChanged += prompt_change

        self.shell = shell
        self.shell.Quitted += lambda: logging.debug("closing") or self.quit()
        self.default_prompt = Prompt("(monitor) ", ConsoleColor.DarkRed)
        self.prompt = self.default_prompt
        self.protocol_prompt = Prompt("(protocol) ", ConsoleColor.DarkRed)

        t = Thread(target=self.shell.Start, args=[True])
        t.start()

    def _write_shell_command(self, command: str):
        if self.shell is None:
            return

        self.shell.Terminal.NewLine()
        self._write_prompt(self.protocol_prompt)
        self.shell.Terminal.WriteRaw(command)
        self.shell.Terminal.NewLine()

    def _write_shell_output(self, out: str, err: str):
        if self.shell is None:
            return

        if out:
            self.shell.Terminal.WriteRaw(out)
        if err:
            self.shell.Writer.WriteError(err)

        # NOTE: this assumes user has no active interaction with Monitor
        self._write_prompt(self.prompt)

    def _write_prompt(self, prompt):
        cast(Shell, self.shell).Terminal.WriteRaw(prompt.Text, prompt.Color)
