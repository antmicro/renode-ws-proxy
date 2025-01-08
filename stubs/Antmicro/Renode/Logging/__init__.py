class ILoggerBackend: ...


class Logger:
    @staticmethod
    def AddBackend(backend: ILoggerBackend, name: str, overwrite: bool = False): ...


class LoggerBackend(ILoggerBackend): ...


class TextBackend(LoggerBackend): ...


class NetworkBackend(TextBackend):
    def __init__(self, port: int) -> None: ...
