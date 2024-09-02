# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging

from websockets.asyncio.server import ServerConnection

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("stream_proxy.py")


class StreamProxy:
    def __init__(self, buffer: int = 1):
        self.connections = {}
        self.buffor = buffer

    async def add_connection(self, program: str, websocket: ServerConnection) -> None:
        proc = await asyncio.create_subprocess_exec(
            f"{program}",
            "--interpreter=mi",
            "--quiet",
            "-ex",
            "set source open off",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.connections[program] = {"websocket": websocket, "process": proc}

    def remove_connection(self, program: str) -> None:
        if program in self.connections and (conn := self.connections.pop(program)):
            logger.info(f"Removing connector {program}")
            if proc := conn.get("process"):
                proc.terminate()
            if websocket := conn.get("websocket"):
                asyncio.create_task(websocket.close())

    async def _ensure_ready(self, ws_path: str) -> None:
        while not all(self.connections.get(ws_path, {}).values()):
            await asyncio.sleep(0.01)

    async def handle_websocket_rx(self, program: str) -> None:
        if not (conn := self.connections.get(program)):
            return
        websocket, proc = conn["websocket"], conn["process"]
        stdin = proc.stdin

        try:
            async for message in websocket:
                # XXX(pkoscik): why is this needed?
                if not message:
                    break
                logger.debug(f"WebSocket -> stdin:{program} >>> {repr(message)}")
                stdin.write(message.encode())
                await stdin.drain()
        except Exception as e:
            logger.error(f"handle_websocket_rx: error: {e}")
        finally:
            self.remove_connection(program)

    async def handle_stdout_rx(self, program: str) -> None:
        if not (conn := self.connections.get(program)):
            return
        websocket, proc = conn["websocket"], conn["process"]
        stdout = proc.stdout

        try:
            while True:
                buf = await stdout.readline()  # read until a newline character
                if not buf:
                    break
                message = buf.decode()
                logger.debug(f"stdout:{program} -> WebSocket >>> {repr(message)}")
                await websocket.send(message)
        except Exception as e:
            logger.error(f"handle_stdout_rx: error: {e}")
        finally:
            self.remove_connection(program)

    async def handle_stderr_rx(self, program: str) -> None:
        if not (conn := self.connections.get(program)):
            return
        websocket, proc = conn["websocket"], conn["process"]
        stderr = proc.stderr

        try:
            while True:
                buf = await stderr.readline()  # read until a newline character
                if not buf:
                    break
                message = buf.decode()
                logger.debug(f"stderr:{program} -> WebSocket >>> {repr(message)}")
                await websocket.send(message)
        except Exception as e:
            logger.error(f"handle_stderr_rx error: {e}")
        finally:
            self.remove_connection(program)
