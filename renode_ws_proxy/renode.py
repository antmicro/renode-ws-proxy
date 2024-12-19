# Copyright (c) 2025 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import sys
from typing import IO, Optional, cast
import logging
import subprocess
import json
import multiprocessing
from multiprocessing.connection import Connection
import io
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("renode.py")


class RenodeState:
    def __init__(
        self,
        renode_path: str,
        logging_port: int = 29170,
        gui_disabled: bool = True,
        monitor_forwarding_disabled: bool = False,
    ):
        self.renode = None
        self.renode_path = Path(renode_path)
        assert self.renode_path.exists()
        self.logging_port = logging_port
        self.gui_disabled = gui_disabled
        self.monitor_forwarding_disabled = monitor_forwarding_disabled
        self.lock = asyncio.Lock()

    async def start(self, gui: bool, cwd: Path):
        async with self.lock:
            if self.renode is not None and self.renode.poll() is None:
                logger.warning("Attempting to start Renode, but it is already running")
                return False

            args = [
                str(self.logging_port),
                str(gui),
                str(self.monitor_forwarding_disabled),
            ]

            logger.debug(f"Loading Renode from {self.renode_path}")
            pyrenode3_env = {
                **os.environ,
                "PYRENODE_BIN": str(self.renode_path),
                "PYRENODE_RUNTIME": "coreclr",  # TODO: make it configurable
            }

            self.renode = subprocess.Popen(
                [sys.executable, "-m", "renode_instance.renode"] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=pyrenode3_env,
                cwd=cwd,
            )

            logger.info(f"Started Renode (pyrenode3) with PID: {self.renode.pid}")

            ATTEMPTS = 10
            for i in range(ATTEMPTS):
                logger.debug(f"Waiting for Renode instance ({i + 1}/{ATTEMPTS})")
                output = self._renode_read(timeout=1)
                if output is None:
                    continue

                if "rsp" in output and output["rsp"] == "ready":
                    logger.info("Renode instance is ready")
                    return self.renode.pid
                else:
                    logger.error(f"Received illegal starting response: {output}")
                    break

            await self.kill()
            return False

    async def execute(self, command: str, **kwargs):
        async with self.lock:
            if self.renode is None:
                logger.warning(
                    "Attempted to issue a request to Renode, but never started"
                )
                return False, "Renode not started"
            if self.renode.poll() is not None:
                logger.warning(
                    "Attempted to issue a request to Renode, but it is closed"
                )
                return False, "Renode is closed"

            self._renode_write({"cmd": command, **kwargs})
            output = self._renode_read()
            assert output is not None

            if "rsp" in output:
                return output["rsp"], None
            if "out" in output and len(output["out"]) == 2:
                return output["out"][0], output["out"][1]
            if "err" in output:
                return False, f"Renode: {output['err']}"

            return False, "Communication with Renode error"

    def _renode_read(self, timeout: Optional[int] = None):
        assert self.renode
        (recv, send) = multiprocessing.Pipe(duplex=False)
        if timeout is None:
            self._renode_read_blocking(send)
            return recv.recv()
        # Do the blocking readline in a thread to support timeouts
        # Thread safe since we do not access any self() method while waiting
        # Have to store the output in a mutable variable since there is no simple way to access a threads return value
        read_task = multiprocessing.Process(target=self._renode_read_blocking(send))
        read_task.daemon = True
        read_task.start()
        if recv.poll(timeout=timeout):
            # recived data
            return recv.recv()
        else:
            # Timeout reached
            read_task.terminate()
            return None

    def _renode_read_blocking(self, pipe: Connection):
        assert self.renode
        # NOTE: stdout is guaranteed to be present because we only spawn Renode with stdout set to PIPE
        stdout = cast(io.BufferedReader, self.renode.stdout)
        pipe.send(json.loads(stdout.readline()))

    def _renode_write(self, request):
        assert self.renode
        # NOTE: stdin is guaranteed to be present because we only spawn Renode with stdin set to PIPE
        stdin = cast(IO[bytes], self.renode.stdin)

        request_line = json.dumps(request)

        stdin.write((request_line + "\n").encode())
        stdin.flush()

    def _wait_for_renode_termination(self, debug_log: str):
        assert self.renode
        ATTEMPTS = 10
        for i in range(ATTEMPTS):
            if self.renode.returncode is not None:
                self.renode = None
                return True
            logger.debug(f"{debug_log} ({i + 1}/{ATTEMPTS})")

            try:
                self.renode.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                pass

        if self.renode.returncode:
            self.renode = None
            return True

        return False

    async def kill(self):
        async with self.lock:
            if not self.renode:
                logger.warning(
                    "Requested to kill Renode, but subprocess has not been created"
                )
                return False

            await self.execute("quit")
            if self._wait_for_renode_termination(
                "Waiting for Renode instance to finish"
            ):
                logger.info("Renode has been shutdown")
                return True

            self.renode.kill()
            if self._wait_for_renode_termination("Waiting for Renode process"):
                logger.info("Renode has been killed")
                return True

            logger.error(f"Failed to kill Renode PID: {self.renode.pid}")
            return False
