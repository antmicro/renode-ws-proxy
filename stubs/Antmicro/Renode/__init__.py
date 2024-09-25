from typing import Any, Protocol


class Emulator:
    BeforeExit: Any

    @staticmethod
    def Exit(): ...


class IEmulationElement(Protocol):
    pass
