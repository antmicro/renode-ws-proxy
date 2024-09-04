from AntShell import Shell


class Monitor: ...


class ShellProvider:
    @staticmethod
    def GenerateShell(monitor: Monitor, forceVCursor: bool = False) -> Shell: ...
