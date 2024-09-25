from typing import Any, SupportsInt, overload


class Decimal:
    def __init__(self, value: float) -> None: ...
    @staticmethod
    def ToDouble(d: "Decimal") -> float: ...


class Type:
    def IsInstanceOfType(self, obj: Any) -> bool: ...


# pyright: reportNoOverloadImplementation=none
class ConsoleColor(SupportsInt):
    @overload
    def __init__(self, value: int) -> None: ...
    @overload
    def __init__(self, value: int, force_if_true: bool) -> None: ...
    def __int__(self) -> int: ...

    # Values:
    Black: "ConsoleColor"  # 0
    DarkBlue: "ConsoleColor"  # 1
    DarkGreen: "ConsoleColor"  # 2
    DarkCyan: "ConsoleColor"  # 3
    DarkRed: "ConsoleColor"  # 4
    DarkMagenta: "ConsoleColor"  # 5
    DarkYellow: "ConsoleColor"  # 6
    Gray: "ConsoleColor"  # 7
    DarkGray: "ConsoleColor"  # 8
    Blue: "ConsoleColor"  # 9
    Green: "ConsoleColor"  # 10
    Cyan: "ConsoleColor"  # 11
    Red: "ConsoleColor"  # 12
    Magenta: "ConsoleColor"  # 13
    Yellow: "ConsoleColor"  # 14
    White: "ConsoleColor"  # 15
