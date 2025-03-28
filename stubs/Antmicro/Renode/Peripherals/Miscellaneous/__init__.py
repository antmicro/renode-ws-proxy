from typing import Any
from Antmicro.Renode.Peripherals import IPeripheral


class ILed(IPeripheral): ...


class LED(ILed):
    StateChanged: Any


class Button(IPeripheral):
    StateChanged: Any
