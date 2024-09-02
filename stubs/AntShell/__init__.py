from typing import Any


class Shell:
    Quitted: Any

    def Start(self, stopOnError: bool = False): ...
