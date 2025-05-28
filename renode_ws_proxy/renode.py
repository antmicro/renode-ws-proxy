# Copyright (c) 2025 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import sys
from typing import Optional, cast
import logging
import json
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
        self.started_event = asyncio.Event()
        self.event_enqueued = asyncio.Event()
        self.response_enqueued = asyncio.Event()
        self.event_queue = []
        self.response_queue = []
        self.monitored_event_names = []

    async def read_loop(self) -> None:
        while await self.started_event.wait():
            assert self.renode and self.renode.stdout
            message = json.loads(await self.renode.stdout.readline())

            if "evt" in message:
                self.event_queue.append(message)
                self.event_enqueued.set()
            else:
                self.response_queue.append(message)
                self.response_enqueued.set()

    async def log_loop(self) -> None:
        while await self.started_event.wait():
            assert self.renode and self.renode.stderr
            logger.debug(await self.renode.stderr.readline())

    async def get_event(self) -> Optional[dict]:
        self.event_enqueued.clear()
        if len(self.event_queue) == 0:
            await self.event_enqueued.wait()

        event = self.event_queue.pop()["evt"]
        if (
            len(self.monitored_event_names) > 0
            and event["event"] not in self.monitored_event_names
        ):
            return

        return event

    async def _response(self) -> dict:
        self.response_enqueued.clear()
        if len(self.response_queue) == 0:
            await self.response_enqueued.wait()

        return self.response_queue.pop()

    async def start(self, gui: bool, cwd: Path) -> int | bool:
        async with self.lock:
            if self.renode is not None and self.renode.returncode is None:
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

            self.renode = await asyncio.subprocess.create_subprocess_exec(
                sys.executable,
                "-m",
                "renode_instance.renode",
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                env=pyrenode3_env,
                cwd=cwd,
            )
            assert self.renode and self.renode.stdout

            logger.info(f"Started Renode (pyrenode3) with PID: {self.renode.pid}")

            ATTEMPTS = 10
            for i in range(ATTEMPTS):
                logger.debug(f"Waiting for Renode instance ({i + 1}/{ATTEMPTS})")
                message = ""

                try:
                    message = await asyncio.wait_for(
                        self.renode.stdout.readline(), timeout=1
                    )
                except asyncio.TimeoutError:
                    continue

                output = json.loads(message)

                if "rsp" in output and output["rsp"] == "ready":
                    logger.info("Renode instance is ready")
                    self.started_event.set()
                    return self.renode.pid
                else:
                    logger.error(f"Received illegal starting response: {output}")
                    break

            await self.kill()
            return False

    async def execute(self, command: str, **kwargs) -> tuple[bool | str, Optional[str]]:
        async with self.lock:
            if self.renode is None:
                logger.warning(
                    "Attempted to issue a request to Renode, but never started"
                )
                return False, "Renode not started"
            if self.renode.returncode is not None:
                logger.warning(
                    "Attempted to issue a request to Renode, but it is closed"
                )
                return False, "Renode is closed"

            self._renode_write({"cmd": command, **kwargs})
            output = await self._response()

            if "rsp" in output:
                return output["rsp"], None
            if "out" in output and len(output["out"]) == 2:
                return output["out"][0], output["out"][1]
            if "err" in output:
                return False, f"Renode: {output['err']}"

            return False, "Communication with Renode error"

    def _renode_write(self, request) -> None:
        assert self.renode and self.renode.stdin
        # NOTE: stdin is guaranteed to be present because we only spawn Renode with stdin set to PIPE
        stdin = cast(asyncio.StreamWriter, self.renode.stdin)

        request_line = json.dumps(request)

        stdin.write((request_line + "\n").encode())
        # stdin.flush()

    async def _wait_for_renode_termination(self, debug_log: str) -> bool:
        assert self.renode
        ATTEMPTS = 10
        for i in range(ATTEMPTS):
            if self.renode.returncode is not None:
                self.renode = None
                return True
            logger.debug(f"{debug_log} ({i + 1}/{ATTEMPTS})")

            try:
                await asyncio.wait_for(self.renode.communicate(), timeout=1)
            except asyncio.TimeoutError:
                pass

        if self.renode.returncode:
            self.renode = None
            return True

        return False

    async def kill(self) -> bool:
        async with self.lock:
            self.started_event.clear()
            if not self.renode:
                logger.warning(
                    "Requested to kill Renode, but subprocess has not been created"
                )
                return False

            try:
                await asyncio.wait_for(self.execute("quit"), timeout=0.5)
                if await self._wait_for_renode_termination(
                    "Waiting for Renode instance to finish"
                ):
                    logger.info("Renode has been shutdown")
                    return True
            except asyncio.TimeoutError:
                pass

            self.renode.kill()
            if await self._wait_for_renode_termination(
                "Waiting for Renode process to terminate"
            ):
                logger.info("Renode has been killed")
                return True

            logger.error(f"Failed to kill Renode PID: {self.renode.pid}")
            return False

    def filter_events(self, events: list[str]) -> None:
        self.monitored_event_names = events
