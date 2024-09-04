from Antmicro.Renode.UserInterface import Monitor
from AntShell import Shell
from AntShell.Terminal import IOProvider
from typing import Any


class ConsoleWindowBackendAnalyzer:
    IO: IOProvider
    Quitted: Any

    def __init__(self, isMonitorWindow: bool): ...
    def Show(self): ...


class CommandLineInterface:
    @staticmethod
    def PrepareXwtMonitorShell(monitor: Monitor) -> Shell: ...
