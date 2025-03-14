from AntShell.Terminal import IIOSource


class SocketIOSource(IIOSource):
    def __init__(self, port: int) -> None: ...
    @property
    def IsAnythingAttached(self) -> bool: ...
    def Dispose(self) -> None: ...
    def Flush(self) -> None: ...
    def Pause(self) -> None: ...
    def Resume(self) -> None: ...
    def Write(self, b: int) -> None: ...
