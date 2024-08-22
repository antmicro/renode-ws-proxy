#!/usr/bin/env python3

# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import sys
import json
import logging
from typing import Iterable, cast

from pyrenode3.wrappers import Emulation, Monitor

from Antmicro.Renode.Peripherals.UART import IUART

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("renode.py")


class Command:
    def __init__(self, default_handler):
        self.commands = {}
        self.default_handler = default_handler

    def __getitem__(self, command):
        return (
            self.commands[command] if command in self.commands else self.default_handler
        )

    def register(self, handler):
        self.commands[handler.__name__] = handler


class State:
    def __init__(self, logging_port: int):
        self.running = True

        self.emulation = Emulation()
        self._m = Monitor()

        self.execute(f"logNetwork {logging_port}")

    def quit(self):
        self.running = False

    def execute(self, command: str):
        return self._m.execute(command)


def execute(state: State, message):
    result = state.execute(message["cmd"])
    logger.debug(f"executing Monitor command `{message['cmd']}` with result {result}")
    return {"out": result}


command = Command(execute)


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

    # TODO: do not assume local name is enough
    names = [
        name for ok, name in map(machine.internal.TryGetLocalName, instances) if ok
    ]

    return {"rsp": names}


@command.register
def machines(state: State, message):
    names = list(cast(Iterable[str], state.emulation.Names))
    return {"rsp": names}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: %s <LOGGING_PORT>" % sys.argv[0])
        exit(1)

    logging_port = int(sys.argv[1])
    logger.debug(f"Starting pyrenode3 with logs on port {logging_port}")
    state = State(logging_port)

    print(json.dumps({"rsp": "ready"}))
    sys.stdout.flush()

    while state.running:
        for line in sys.stdin:
            response = {"err": "internal error: no response generated"}
            try:
                message = json.loads(line)
                response = command[message["cmd"]](state, message)
            except json.JSONDecodeError as e:
                logger.error("Parsing error: %s" % str(e))
                response = {"err": "parsing error: %s" % str(e)}
            except Exception as e:
                logger.error("Internal error %s" % str(e))
                response = {"err": "internal error: %s" % str(e)}
            finally:
                print(json.dumps(response))
                sys.stdout.flush()

                if not state.running:
                    break
