from typing import Any
from enum import Enum, auto

from Antmicro.Renode.Peripherals import IPeripheral
from pyrenode3 import wrappers


class Emulation:
    EmulationChanged: Any


class EmulationManager:
    Instance: Emulation


class IMachine:
    PeripheralsChanged: Any


class Machine(IMachine, wrappers.Machine): ...


class PeripheralsChangedEventArgs:
    class PeripheralChangeType(Enum):
        Addition = auto()
        Removal = auto()
        Moved = auto()
        CompleteRemoval = auto()
        NameChanged = auto()

    Operation: "PeripheralChangeType"
    Peripheral: IPeripheral
