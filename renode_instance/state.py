# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

from typing import cast
from threading import Thread
import logging

from Antmicro.Renode.Utilities import SocketIOSource
from pyrenode3.inits import XwtInit
from pyrenode3.wrappers import Emulation, Monitor

from System import ConsoleColor
from Antmicro.Renode import Emulator
from Antmicro.Renode.UI import ConsoleWindowBackendAnalyzer
from Antmicro.Renode.UserInterface import ShellProvider
from AntShell import Prompt, Shell
from AntShell.Terminal import IOProvider, NavigableTerminalEmulator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("state.py")


class State:
    def __init__(
        self, logging_port: int, gui_enabled: bool, monitor_forwarding_disabled: bool
    ):
        self.running = True

        self.emulation = Emulation()
        self._m = Monitor()
        self._m.internal.Quitted += lambda: logging.debug("closing") or self.quit()
        self.shell = None
        self.monitor_forwarding_disabled = monitor_forwarding_disabled

        self.execute(f"logNetwork {logging_port}")

        self.__prepare_monitor(gui_enabled, logging_port - 1)

    def quit(self):
        if self.shell:
            self.shell.Stop()
        self.running = False

    def execute(self, command: str):
        self._write_shell_command(command)

        out, err = self._m.execute(command)

        self._write_shell_output(out, err)
        return out, err

    def __prepare_monitor(self, gui_enabled: bool, port: int):
        monitor = self._m.internal

        if gui_enabled:
            XwtInit()
            terminal = ConsoleWindowBackendAnalyzer(True)
            io = terminal.IO

            shell = ShellProvider.GenerateShell(monitor)
            shell.Terminal = NavigableTerminalEmulator(io)

            terminal.Quitted += Emulator.Exit
            terminal.Show()
        else:
            from Antmicro.Renode.Peripherals.UART import UARTBackend
            from Antmicro.Renode.Analyzers import LoggingUartAnalyzer

            io = IOProvider()
            io.Backend = SocketIOSource(port)

            shell = ShellProvider.GenerateShell(monitor, True)
            shell.Terminal = NavigableTerminalEmulator(io, True)

            self.emulation.internal.BackendManager.SetPreferredAnalyzer(
                UARTBackend, LoggingUartAnalyzer
            )

        Emulator.BeforeExit += shell.Stop

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

        if not self.monitor_forwarding_disabled:
            self.protocol_prompt = Prompt("\r\n(protocol) ", ConsoleColor.DarkRed)

        t = Thread(target=self.shell.Start, args=[True])
        t.start()

    def _write_shell_command(self, command: str):
        if self.shell is None or self.monitor_forwarding_disabled:
            return

        self._write_prompt(self.protocol_prompt)
        self.shell.Terminal.WriteRaw(command)
        self.shell.Terminal.NewLine()

    def _write_shell_output(self, out: str, err: str):
        if self.shell is None or self.monitor_forwarding_disabled:
            return

        if out:
            self.shell.Terminal.WriteRaw(out)
        if err:
            self.shell.Writer.WriteError(err)

        # NOTE: this assumes user has no active interaction with Monitor
        self._write_prompt(self.prompt)

    def _write_prompt(self, prompt):
        cast(Shell, self.shell).Terminal.WriteRaw(prompt.Text, prompt.Color)
