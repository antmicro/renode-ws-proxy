# Copyright (c) 2025 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import logging

from Antmicro.Renode.Peripherals.Miscellaneous import Button, ILed

from renode_instance.state import State, Command
from renode_instance.utils import get_full_name

command = Command()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("gpio.py")


@command.register
def buttons(state: State, message):
    if "machine" not in message:
        return {"err": "missing required argument 'machine'"}

    machine = state.emulation.get_mach(message["machine"])

    if not machine:
        return {"err": "provided machine does not exist"}

    instances: list[Button] = machine.internal.GetPeripheralsOfType[Button]()

    names = [
        name
        for name in [get_full_name(instance, machine) for instance in instances]
        if name
    ]

    return {"rsp": names}


@command.register
def leds(state: State, message):
    if "machine" not in message:
        return {"err": "missing required argument 'machine'"}

    machine = state.emulation.get_mach(message["machine"])

    if not machine:
        return {"err": "provided machine does not exist"}

    instances: list[ILed] = machine.internal.GetPeripheralsOfType[ILed]()

    names = [
        name
        for name in [get_full_name(instance, machine) for instance in instances]
        if name
    ]

    return {"rsp": names}


@command.register
def button_set(state: State, message):
    for argument in ["machine", "peripheral", "value"]:
        if argument not in message:
            return {"err": f"missing required argument '{argument}'"}

    periph_name = message["peripheral"]

    machine = state.emulation.get_mach(message["machine"])
    if not machine:
        return {"err": "provided machine does not exist"}

    ok, button = machine.internal.TryGetByName[Button](periph_name)
    if not ok:
        return {"err": f"Button {periph_name} not found"}

    value = message["value"]

    if value and button.Pressed:
        return {"err": f"trying to press button {periph_name} which is already pressed"}
    elif not value and not button.Pressed:
        return {"err": f"trying to release button {periph_name} which is not pressed"}

    if value:
        button.Press()
    else:
        button.Release()

    return {"rsp": "ok"}
