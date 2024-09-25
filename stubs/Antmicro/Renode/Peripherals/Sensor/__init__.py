import abc
import typing
from System import Decimal
from Antmicro.Renode.Peripherals import IPeripheral


class ISensor(IPeripheral, typing.Protocol):
    pass


class IADC(ISensor, typing.Protocol):
    @property
    def ADCChannelCount(self) -> int: ...
    @abc.abstractmethod
    def GetADCValue(self, channel: int) -> int: ...
    @abc.abstractmethod
    def SetADCValue(self, channel: int, value: int) -> None: ...


class ITemperatureSensor(ISensor, typing.Protocol):
    @property
    def Temperature(self) -> Decimal: ...
    @Temperature.setter
    def Temperature(self, value: Decimal) -> Decimal: ...


class IHumiditySensor(ISensor, typing.Protocol):
    @property
    def Humidity(self) -> Decimal: ...
    @Humidity.setter
    def Humidity(self, value: Decimal) -> Decimal: ...


class IMagneticSensor(ISensor, typing.Protocol):
    @property
    def MagneticFluxDensityX(self) -> int: ...
    @MagneticFluxDensityX.setter
    def MagneticFluxDensityX(self, value: int) -> int: ...
    @property
    def MagneticFluxDensityY(self) -> int: ...
    @MagneticFluxDensityY.setter
    def MagneticFluxDensityY(self, value: int) -> int: ...
    @property
    def MagneticFluxDensityZ(self) -> int: ...
    @MagneticFluxDensityZ.setter
    def MagneticFluxDensityZ(self, value: int) -> int: ...
