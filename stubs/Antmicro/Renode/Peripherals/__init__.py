import abc
import typing
from Antmicro.Renode import IEmulationElement


class IAnalyzable(IEmulationElement, typing.Protocol):
    pass


class IPeripheral(IAnalyzable, typing.Protocol):
    @abc.abstractmethod
    def Reset(self) -> None: ...
