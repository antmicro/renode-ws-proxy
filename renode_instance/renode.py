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
from clr import GetClrType

from sys import exit
from pyrenode3.wrappers import Emulation, Monitor

from System import Decimal
from Antmicro.Renode.Peripherals.UART import IUART
from Antmicro.Renode.Peripherals.Sensor import (
    ISensor,
    ITemperatureSensor,
    IADC,
    IHumiditySensor,
    IMagneticSensor,
)
from AntShell import Shell

MAX_UINT = (1 << 32) - 1
MAX_INT = (1 << 31) - 1
MIN_INT = -(1 << 31)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("renode.py")


def csharp_is(T, obj):
    return GetClrType(T).IsInstanceOfType(obj)


def csharp_as(T, obj):
    return T(obj) if csharp_is(T, obj) else None


def get_full_name(peripheral, machine):
    ok, localName = machine.internal.TryGetLocalName(peripheral)
    if not ok:
        return None

    for path in _get_full_name(peripheral, localName, machine):
        return path

    return None


def _get_full_name(peripheral, localName, machine):
    parents = machine.internal.GetParentPeripherals(peripheral)

    res = [
        (parent, parentLocalName)
        for ok, parentLocalName, parent in [
            (*machine.internal.TryGetLocalName(parent), parent) for parent in parents
        ]
        if ok
    ]

    for parent, parentLocalName in res:
        if parentLocalName == "sysbus":
            yield f"sysbus.{localName}"
            return

        for path in _get_full_name(parent, parentLocalName, machine):
            yield f"{path}.{localName}"


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

    names = [
        name
        for name in [get_full_name(instance, machine) for instance in instances]
        if name
    ]

    return {"rsp": names}


sensor_type = {
    "temperature": ITemperatureSensor,
    # "acceleration": ,
    # "angular-rate": ,
    "voltage": IADC,
    # "ecg": ,
    "humidity": IHumiditySensor,
    # "pressure": ,
    "magnetic-flux-density": IMagneticSensor,
}


def assert_3d(value, minv: int, maxv: int):
    assert minv <= value["x"] <= maxv
    assert minv <= value["y"] <= maxv
    assert minv <= value["z"] <= maxv


def set_magnetic_sensor_data(obj: IMagneticSensor, value):
    assert_3d(value, MIN_INT, MAX_INT)
    obj.MagneticFluxDensityX = value["x"]
    obj.MagneticFluxDensityY = value["y"]
    obj.MagneticFluxDensityZ = value["z"]


def get_magnetic_sensor_data(obj: IMagneticSensor):
    return {
        "x": obj.MagneticFluxDensityX,
        "y": obj.MagneticFluxDensityY,
        "z": obj.MagneticFluxDensityZ,
    }


def set_temperature(obj: ITemperatureSensor, value: int):
    assert MIN_INT <= value <= MAX_INT
    obj.Temperature = Decimal(int(value) / 1e3)


def set_voltage(obj: IADC, value: int):
    assert 0 <= value <= MAX_UINT
    obj.SetADCValue(0, value)


def set_humidity(obj: IHumiditySensor, value: int):
    assert 0 <= value <= MAX_UINT
    obj.Humidity = Decimal(int(value) / 1e3)


sensor_setter = {
    "temperature": lambda obj, value: set_temperature(
        cast(ITemperatureSensor, obj), value
    ),
    "voltage": lambda obj, value: set_voltage(cast(IADC, obj), value),
    "humidity": lambda obj, value: set_humidity(cast(IHumiditySensor, obj), value),
    "magnetic-flux-density": lambda obj, value: set_magnetic_sensor_data(
        cast(IMagneticSensor, obj), value
    ),
}

sensor_getter = {
    "temperature": lambda obj: int(
        Decimal.ToDouble(cast(ITemperatureSensor, obj).Temperature) * 1e3
    ),
    "voltage": lambda obj: cast(IADC, obj).GetADCValue(0),
    "humidity": lambda obj: int(
        Decimal.ToDouble(cast(IHumiditySensor, obj).Humidity) * 1e3
    ),
    "magnetic-flux-density": lambda obj: get_magnetic_sensor_data(
        cast(IMagneticSensor, obj)
    ),
}


@command.register
def sensors(state: State, message):
    if "machine" not in message:
        return {"err": "missing required argument 'machine'"}

    machine = state.emulation.get_mach(message["machine"])

    if not machine:
        return {"err": "provided machine does not exist"}

    type = ISensor
    if "type" in message:
        if message["type"] not in sensor_type:
            return {"err": f"not supported 'type' value: '{message["type"]}'"}
        type = sensor_type[message["type"]]

    instances = machine.internal.GetPeripheralsOfType[type]()

    for instance in instances:
        logger.error(get_full_name(instance, machine))

    instance_names = [
        (get_full_name(instance, machine), instance) for instance in instances
    ]

    sensor_instances = [
        {
            "name": name,
            "types": [
                stype_name
                for stype_name, stype in sensor_type.items()
                if csharp_is(stype, instance)
            ],
        }
        for name, instance in instance_names
        if name
    ]

    return {"rsp": sensor_instances}


@command.register
def sensor_set(state: State, message):
    for argument in ["machine", "peripheral", "type", "value"]:
        if argument not in message:
            return {"err": f"missing required argument '{argument}'"}

    machine = state.emulation.get_mach(message["machine"])
    if not machine:
        return {"err": "provided machine does not exist"}
    type = message["type"]
    ok, perpheral = machine.internal.TryGetByName[sensor_type[type]](
        message["peripheral"]
    )
    if not ok:
        return {
            "err": f"peripheral {message["peripheral"]} implementing '{type}' not found"
        }
    value = message["value"]

    sensor_setter[type](perpheral, value)
    return {"rsp": "ok"}


@command.register
def sensor_get(state: State, message):
    for argument in ["machine", "peripheral", "type"]:
        if argument not in message:
            return {"err": f"missing required argument '{argument}'"}

    machine = state.emulation.get_mach(message["machine"])
    if not machine:
        return {"err": "provided machine does not exist"}
    type = message["type"]
    perpheral = machine.internal[message["peripheral"]]
    sensor = csharp_as(sensor_type[type], perpheral)

    if sensor is None:
        return {
            "err": f"peripheral {message["peripheral"]} implementing '{type}' not found"
        }

    return {"rsp": sensor_getter[type](sensor)}


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
            response = command[message["cmd"].replace("-", "_")](state, message)
        except json.JSONDecodeError as e:
            logger.error("Parsing error: %s" % str(e))
            response = {"err": "parsing error: %s" % str(e)}
        except Exception as e:
            logger.error("Internal error %s" % str(e))
            response = {"err": "internal error: %s" % str(e)}
        finally:
            print(json.dumps(response))
            sys.stdout.flush()
