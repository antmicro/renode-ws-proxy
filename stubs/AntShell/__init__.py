from typing import Any, Optional
from System import ConsoleColor
from AntShell.Terminal import NavigableTerminalEmulator


class Prompt:
    def __init__(self, text: str, color: ConsoleColor): ...


class Shell:
    Quitted: Any
    Terminal: NavigableTerminalEmulator
    Writer: Any

    def Start(self, stopOnError: bool = False): ...
    def Stop(self): ...
    def SetPrompt(self, p: Optional[Prompt]): ...
