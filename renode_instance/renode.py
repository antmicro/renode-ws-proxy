#!/usr/bin/env python3

# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import sys
import json
import logging
from typing import Iterable, cast
import select
import io

from sys import exit
from pyrenode3.wrappers import Emulation, Monitor

from Antmicro.Renode.Peripherals.UART import IUART
from AntShell import Shell

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("renode.py")


class Command:
    def __init__(self, default_handler):
        self.commands = {}
        self.default_handler = default_handler

    def __getitem__(self, command):
        return (
            self.commands[command] if command in self.commands else self.default_handler
        )

    def register(self, handler):
        self.commands[handler.__name__] = handler


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
        from threading import Thread
        from pyrenode3.inits import XwtInit
        from Antmicro.Renode.UI import ConsoleWindowBackendAnalyzer
        from Antmicro.Renode.UserInterface import ShellProvider
        from AntShell.Terminal import NavigableTerminalEmulator
        from Antmicro.Renode import Emulator
        from AntShell import Prompt
        from System import ConsoleColor

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


def execute(state: State, message):
    result = state.execute(message["cmd"])
    logger.debug(f"executing Monitor command `{message['cmd']}` with result {result}")
    return {"out": result}


command = Command(execute)


@command.register
def quit(state: State, message):
    state.quit()
    logger.debug("closing")
    return {"rsp": "closing"}


@command.register
def uarts(state: State, message):
    if "machine" not in message:
        return {"err": "missing required argument 'machine'"}

    machine = state.emulation.get_mach(message["machine"])

    if not machine:
        return {"err": "provided machine does not exist"}

    instances = machine.internal.GetPeripheralsOfType[IUART]()

    # TODO: do not assume local name is enough
    names = [
        name for ok, name in map(machine.internal.TryGetLocalName, instances) if ok
    ]

    return {"rsp": names}


@command.register
def machines(state: State, message):
    names = list(cast(Iterable[str], state.emulation.Names))
    return {"rsp": names}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: %s <LOGGING_PORT> [ENABLE_GUI]" % sys.argv[0])
        exit(1)

    gui_enabled = False if len(sys.argv) < 3 else "true".startswith(sys.argv[2].lower())
    if gui_enabled:
        logger.info("GUI is enabled")

    logging_port = int(sys.argv[1])
    logger.debug(f"Starting pyrenode3 with logs on port {logging_port}")
    state = State(logging_port, gui_enabled)

    print(json.dumps({"rsp": "ready"}))
    sys.stdout.flush()

    while state.running:
        if not select.select([sys.stdin], [], [], 0.1)[0]:
            continue
        if b"\n" not in cast(io.BufferedReader, sys.stdin.buffer).peek(
            io.DEFAULT_BUFFER_SIZE
        ):
            continue
        line = sys.stdin.readline()
        if not line:
            continue

        response = {"err": "internal error: no response generated"}
        try:
            message = json.loads(line)
            response = command[message["cmd"]](state, message)
        except json.JSONDecodeError as e:
            logger.error("Parsing error: %s" % str(e))
            response = {"err": "parsing error: %s" % str(e)}
        except Exception as e:
            logger.error("Internal error %s" % str(e))
            response = {"err": "internal error: %s" % str(e)}
        finally:
            print(json.dumps(response))
            sys.stdout.flush()
