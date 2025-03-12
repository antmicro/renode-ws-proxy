# Copyright (c) 2025 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

from typing import cast, Protocol
from threading import Thread
import logging
from functools import lru_cache

from pyrenode3.inits import XwtInit
from pyrenode3.wrappers import Emulation, Monitor, Machine
from pyrenode3.conversion import interface_to_class

from System import ConsoleColor
from Antmicro.Renode import Emulator
from Antmicro.Renode.Analyzers import SocketUartAnalyzer
from Antmicro.Renode.Core import EmulationManager
from Antmicro.Renode.Logging import Logger, NetworkBackend
from Antmicro.Renode.Peripherals import (
    IPeripheralExtensions,
    IAnalyzableBackendAnalyzer,
)
from Antmicro.Renode.Peripherals.UART import UARTBackend
from Antmicro.Renode.UI import ConsoleWindowBackendAnalyzer
from Antmicro.Renode.UserInterface import ShellProvider
from Antmicro.Renode.Utilities import SocketIOSource
from AntShell import Prompt, Shell
from AntShell.Terminal import IOProvider, NavigableTerminalEmulator

from renode_instance.utils import csharp_is, get_full_name

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("state.py")


@lru_cache(maxsize=None)
class Command:
    def __init__(self):
        self.commands = {}
        self.default_handler = None

    def run(self, command: str, state: "State", message):
        return self.commands.get(command, self.default_handler)(state, message)

    def register(self, handler):
        self.commands[handler.__name__.replace("_", "-")] = handler

    def register_default(self, handler):
        if self.default_handler is not None:
            raise Exception("Default hander is already set")
        self.default_handler = handler


class EventHandler(Protocol):
    def __call__(self, state: "State", event: str, **payload) -> None: ...


class State:
    def __init__(
        self,
        logging_port: int,
        gui_enabled: bool,
        monitor_forwarding_disabled: bool,
        event_handler: EventHandler,
    ):
        self.running = True
        self.report_event = event_handler

        self.emulation = Emulation()
        self._m = Monitor()
        self._m.internal.Quitted += (
            lambda: logging.debug("closing")
            or self.quit()
            or self.__signal_renode_quitted()
        )
        self.shell = None
        self.monitor_forwarding_disabled = monitor_forwarding_disabled

        Logger.AddBackend(NetworkBackend(logging_port, False), "network", True)
        logger.info(f"Renode logs available at port {logging_port}")

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
            io = IOProvider()
            io.Backend = SocketIOSource(port)

            shell = ShellProvider.GenerateShell(monitor, True)
            shell.Terminal = NavigableTerminalEmulator(io, True)

            def set_analyzer():
                self.emulation.internal.BackendManager.SetPreferredAnalyzer(
                    UARTBackend, SocketUartAnalyzer
                )
                self.emulation.internal.BackendManager.PeripheralBackendAnalyzerCreated += self.__signal_uart_opened_event

            set_analyzer()
            EmulationManager.Instance.EmulationChanged += set_analyzer

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

    def __signal_uart_opened_event(self, analyzer: IAnalyzableBackendAnalyzer):
        if csharp_is(SocketUartAnalyzer, analyzer):
            socket_analyzer = interface_to_class(analyzer)
            port = socket_analyzer.Port
            uart = socket_analyzer.UART
            machine = IPeripheralExtensions.GetMachine(uart)
            name = get_full_name(uart, Machine(machine))
            machineName = self.emulation.internal[machine]
            self.report_event(
                self, "uart-opened", port=port, name=name, machineName=machineName
            )

    def __signal_renode_quitted(self):
        self.report_event(self, "renode-quitted")

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
