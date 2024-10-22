#!/usr/bin/env python3

# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import sys
from sys import exit
import json
import logging
from typing import Iterable, cast

import pyrenode3  # noqa: F401
from Antmicro.Renode.Peripherals.UART import IUART

from renode_instance.state import State
from renode_instance.utils import Command, get_full_name
import renode_instance.sensors  # noqa: F401

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("renode.py")

command = Command()


@command.register_default
def execute(state: State, message):
    result = state.execute(message["cmd"])
    logger.debug(f"executing Monitor command `{message['cmd']}` with result {result}")
    return {"out": result}


@command.register
def quit(state: State, message):
    state.quit()
    logger.debug("closing")
    return {"rsp": "closing"}


@command.register
def uarts(state: State, message):
    if "machine" not in message:
        return {"err": "missing required argument 'machine'"}

    machine = state.emulation.get_mach(message["machine"])

    if not machine:
        return {"err": "provided machine does not exist"}

    instances = machine.internal.GetPeripheralsOfType[IUART]()

    names = [
        name
        for name in [get_full_name(instance, machine) for instance in instances]
        if name
    ]

    return {"rsp": names}


@command.register
def machines(state: State, message):
    names = list(cast(Iterable[str], state.emulation.Names))
    return {"rsp": names}


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: %s <LOGGING_PORT> [ENABLE_GUI] [DISABLE_MONITOR_FORWARDING]"
            % sys.argv[0]
        )
        exit(1)

    gui_enabled = False if len(sys.argv) < 3 else "true".startswith(sys.argv[2].lower())
    if gui_enabled:
        logger.info("GUI is enabled")

    monitor_forwarding_disabled = (
        False if len(sys.argv) < 4 else "true".startswith(sys.argv[3].lower())
    )
    if monitor_forwarding_disabled:
        logger.info("Protocol messages are disabled")

    logging_port = int(sys.argv[1])
    logger.debug(f"Starting pyrenode3 with logs on port {logging_port}")
    state = State(logging_port, gui_enabled, monitor_forwarding_disabled)

    print(json.dumps({"rsp": "ready"}))
    sys.stdout.flush()

    while state.running:
        line = sys.stdin.readline()
        if not line:
            continue

        response = {"err": "internal error: no response generated"}
        try:
            message = json.loads(line)
            response = command.run(message["cmd"], state, message)
        except json.JSONDecodeError as e:
            logger.error("Parsing error: %s" % str(e))
            response = {"err": "parsing error: %s" % str(e)}
        except Exception as e:
            logger.error("Internal error %s" % str(e))
            response = {"err": "internal error: %s" % str(e)}
        finally:
            print(json.dumps(response))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
