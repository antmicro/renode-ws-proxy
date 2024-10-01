# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Type, Optional, Iterable
import logging
from functools import lru_cache
from clr import GetClrType

from renode_instance.state import State

from pyrenode3.wrappers import Machine

from Antmicro.Renode.Peripherals import IPeripheral

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("utils.py")


@lru_cache(maxsize=None)
class Command:
    def __init__(self):
        self.commands = {}
        self.default_handler = None

    def run(self, command: str, state: State, message):
        return self.commands.get(command, self.default_handler)(state, message)

    def register(self, handler):
        self.commands[handler.__name__.replace("_", "-")] = handler

    def register_default(self, handler):
        if self.default_handler is not None:
            raise Exception("Default hander is already set")
        self.default_handler = handler


def csharp_is(T: Type, obj: Any) -> bool:
    return GetClrType(T).IsInstanceOfType(obj)


def csharp_as(T: Type, obj: Any) -> Optional[Any]:
    return T(obj) if csharp_is(T, obj) else None


def get_full_name(peripheral: IPeripheral, machine: Machine) -> Optional[str]:
    ok, local_name = machine.internal.TryGetLocalName(peripheral)
    if not ok:
        return None

    for path in _get_full_name(peripheral, local_name, machine):
        return path

    return None


def _get_full_name(
    peripheral: IPeripheral, local_name: str, machine: Machine
) -> Iterable[str]:
    parents = machine.internal.GetParentPeripherals(peripheral)

    res = [
        (parent, parent_local_name)
        for ok, parent_local_name, parent in [
            (*machine.internal.TryGetLocalName(parent), parent) for parent in parents
        ]
        if ok
    ]

    for parent, parent_local_name in res:
        if parent_local_name == "sysbus":
            yield f"sysbus.{local_name}"
            return

        for path in _get_full_name(parent, parent_local_name, machine):
            yield f"{path}.{local_name}"
