#!/usr/bin/env python3

# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import sys
import json
import logging

from pyrenode3.wrappers import Emulation, Monitor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("renode.py")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: %s <LOGGING_PORT>" % sys.argv[0])
        exit(1)

    logging_port = int(sys.argv[1])

    e = Emulation()
    m = Monitor()

    m.execute(f"logNetwork {logging_port}")

    print(json.dumps({"rsp": "ready"}))
    sys.stdout.flush()

    while True:
        for line in sys.stdin:
            response = {"err": "internal error: no response generated"}
            try:
                message = json.loads(line)
                if message["cmd"] == "quit":
                    response = {"rsp": "closing"}
                    exit(0)
                output = m.execute(message["cmd"])
                response = {"out": output}
            except json.JSONDecodeError as err:
                logger.error("Parsing error: %s" % str(err))
                response = {"err": "parsing error: %s" % str(err)}
            except Exception as err:
                logger.error("Internal error %s" % str(err))
                response = {"err": "internal error: %s" % str(err)}
            finally:
                print(json.dumps(response))
                sys.stdout.flush()
