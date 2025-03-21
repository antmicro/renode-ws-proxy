from importlib import metadata
from os import environ, path

import shutil
import argparse
from typing import Optional

from renode_ws_proxy.protocols import DATA_PROTOCOL_VERSION

default_gdb = "gdb-multiarch"
version_str = f"renode-ws-proxy={metadata.version('renode-ws-proxy')} protocol={DATA_PROTOCOL_VERSION}"


def valid_program(path: str) -> str:
    lookup = shutil.which(path)
    if lookup is None:
        raise argparse.ArgumentTypeError(f"{path} is not a file or cannot be executed")
    return lookup


def valid_gdb(path: Optional[str]) -> str:
    if path:
        return valid_program(path)

    predefined_binaries = ["gdb-multiarch", "gdb"]
    for binary in predefined_binaries:
        if shutil.which(binary):
            return binary

    raise argparse.ArgumentTypeError(
        f"Could not detect any gdb from {predefined_binaries} in PATH. Try passing custom path with a '-g' flag."
    )


def existing_directory(dir: str) -> str:
    if not path.isdir(dir):
        raise argparse.ArgumentTypeError(f"{dir} is not a directory")
    return dir


def validate_bool_value(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.lower() in ["1", "true", "yes"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="renode-ws-proxy",
        description="WebSocket based server for managing remote Renode instance",
    )
    parser.add_argument(
        "renode_binary", type=valid_program, help="path to Renode portable binary"
    )
    parser.add_argument(
        "renode_execution_dir",
        type=existing_directory,
        help="path/directory used as a Renode workspace",
    )

    # NOTE: There are 3 possible cases with a -g flag.
    # Flag is not present - skip using default_gdb, check for `/run/<program>` path in requests
    # Flag is present, but without argument - check if one from predefined gdbs is present. If not - raise an error.
    # Flag is present with argument - check if passed argument does exist. If not - raise an error.
    parser.add_argument(
        "-g",
        "--gdb",
        const="",
        nargs="?",
        type=valid_gdb,
        help=f"path to gdb binary that will be used (defaults to {default_gdb})",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=21234,
        help="WebSocket server port (defaults to 21234)",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=version_str,
        help="display renode-ws-proxy and data protocol version",
    )

    parser.add_argument(
        "--disable-renode-gui",
        action=argparse.BooleanOptionalAction,
        default=validate_bool_value(environ.get("RENODE_PROXY_GUI_DISABLED")),
        help="Turns off Renode GUI",
    )
    parser.add_argument(
        "--disable-proxy-monitor-forwarding",
        action=argparse.BooleanOptionalAction,
        default=validate_bool_value(
            environ.get("RENODE_PROXY_MONITOR_FORWARDING_DISABLED")
        ),
        help="Turns off writing protocol based Monitor interactions to the Monitor shell",
    )

    return parser.parse_args()
