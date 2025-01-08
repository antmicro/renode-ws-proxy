import abc
import typing
from Antmicro.Renode import IEmulationElement
from Antmicro.Renode.Core import IMachine
from Antmicro.Renode.Peripherals.UART import IUART


class IAnalyzable(IEmulationElement, typing.Protocol):
    pass


class IPeripheral(IAnalyzable, typing.Protocol):
    @abc.abstractmethod
    def Reset(self) -> None: ...


class IAnalyzableBackendAnalyzer:
    pass


class IPeripheralExtensions(typing.Protocol):
    @abc.abstractstaticmethod
    def GetMachine(uart: IUART) -> IMachine: ...
