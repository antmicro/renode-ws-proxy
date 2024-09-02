from Antmicro.Renode.UserInterface import Monitor
from AntShell import Shell


class CommandLineInterface:
    @staticmethod
    def PrepareXwtMonitorShell(monitor: Monitor) -> Shell: ...
