# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import telnetlib3

from websockets.asyncio.server import ServerConnection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("telnet_proxy.py")


class TelnetProxy:
    def __init__(self):
        self.connections = {}

    async def add_connection(self, port: str, websocket: ServerConnection) -> None:
        reader, writer = await telnetlib3.open_connection('localhost', port)
        self.connections[port] = {
            'websocket': websocket,
            'tnReader': reader,
            'tnWriter': writer
        }

    def remove_connection(self, port: str) -> None:
        if port in self.connections and (conn := self.connections.pop(port)):
            logger.info(f"Removing Telnet:{port} proxy")
            if tn_writer := conn.get('tnWriter'):
                tn_writer.close()
            if tn_reader := conn.get('tnReader'):
                tn_reader.feed_eof()
            if websocket := conn.get('websocket'):
                asyncio.create_task(websocket.close())

    async def _ensure_ready(self, port: str) -> None:
        while not all(self.connections.get(port, {}).values()):
            await asyncio.sleep(0.01)

    async def handle_websocket_rx(self, port: str) -> None:
        if not (conn := self.connections.get(port)):
            return
        websocket, tn_writer = conn['websocket'], conn['tnWriter']
        await self._ensure_ready(port)

        try:
            async for message in websocket:
                # XXX(pkoscik): why is this needed?
                if not message:
                    break
                logger.debug(
                    f"WebSocket -> Telnet:{port} >>> {repr(message)}"
                )
                tn_writer.write(message)
        except Exception as e:
            logger.error(f"handle_websocket_rx: error: {e}")
        finally:
            self.remove_connection(port)

    async def handle_telnet_rx(self, port: str) -> None:
        if not (conn := self.connections.get(port)):
            return
        websocket, tn_reader = conn['websocket'], conn['tnReader']
        await self._ensure_ready(port)

        try:
            message = await tn_reader.read(128)
            while len(message) > 0:
                logger.debug(
                    f"Telnet:{port} -> WebSocket >>> {repr(message)}"
                )
                await websocket.send(message)
                message = await tn_reader.read(128)
        except Exception as e:
            logger.error(f"handle_telnet_rx: error: {e}")
        finally:
            self.remove_connection(port)
