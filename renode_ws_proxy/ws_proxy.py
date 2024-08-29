#!/usr/bin/env python3

# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

from os import environ, path
import re
import sys
import asyncio
import logging
import subprocess

from base64 import standard_b64decode, standard_b64encode

from websockets.server import serve
from websockets import WebSocketServerProtocol

from renode_ws_proxy.telnet_proxy import TelnetProxy
from renode_ws_proxy.stream_proxy import StreamProxy
from renode_ws_proxy.filesystem import FileSystemState
from renode_ws_proxy.renode import RenodeState
from renode_ws_proxy.protocols import (
    Message,
    Response,
    DATA_PROTOCOL_VERSION,
    _SUCCESS,
    _FAIL,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ws_proxy.py")

LOGLEVEL = logging.DEBUG


async def parse_proxy_request(request: str) -> str:
    """ HELPER FUNCTIONS """
    def handle_spawn(mess, ret):
        software = mess.payload["name"]
        args = mess.payload.get("args", [])
        if software == "renode":
            if pid := renode_state.start(args):
                ret.status = _SUCCESS
                ret.data = {"pid": pid}
        return ret

    def handle_kill(mess, ret):
        software = mess.payload["name"]
        if software == "renode":
            for telnet in list(telnet_proxy.connections):
                telnet_proxy.remove_connection(telnet)
            ret.status = _SUCCESS if renode_state.kill() else _FAIL
        else:
            raise ValueError(f"Killing {software} is not supported")
        return ret

    def handle_status(mess, ret):
        software = mess.payload["name"]
        if software == "renode":
            if pid := renode_state.renode_pid:
                ret.status = _SUCCESS
                ret.data = {"pid": pid}
            else:
                ret.error = "Renode not started"
        elif software == "telnet":
            if connections := list(telnet_proxy.connections):
                ret.status = _SUCCESS
                ret.data = connections
            else:
                ret.error = "No telnet connections"
        elif software == "run":
            if connections := list(stream_proxy.connections):
                ret.status = _SUCCESS
                ret.data = connections
            else:
                ret.error = "No stream connections"
        else:
            raise ValueError(f"Getting status for {software} is not supported")
        return ret

    def handle_command(mess, ret):
        command = mess.payload["name"]
        logger.info(f"Executing {command.split()}")
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        ret.status = _SUCCESS if not process.returncode else _FAIL
        ret.data = {'stdout': stdout, 'stderr': stderr}
        return ret

    """ PARSING """
    try:
        mess = Message.from_json(request)
        logger.debug(f"Deserialized Message: {mess}")

        ret = Response(version=DATA_PROTOCOL_VERSION, status=_FAIL)

        if not mess.action:
            return ret.to_json()

        if mess.action == "spawn":
            ret = handle_spawn(mess, ret)
        elif mess.action == "kill":
            ret = handle_kill(mess, ret)
        elif mess.action == "status":
            ret = handle_status(mess, ret)
        elif mess.action == "command":
            ret = handle_command(mess, ret)
        elif mess.action == "fs/list":
            ret.data = filesystem_state.list()
            ret.status = _SUCCESS if ret.data else _FAIL
        elif mess.action == "fs/stat":
            path = mess.payload["args"][0]
            result = filesystem_state.stat(path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/dwnl":
            path = mess.payload["args"][0]
            ret.data = standard_b64encode(filesystem_state.download(path))
            ret.status = _SUCCESS if ret.data else _FAIL
        elif mess.action == "fs/upld":
            path = mess.payload["args"][0]
            data = mess.payload["data"]
            result = filesystem_state.upload(path, standard_b64decode(data))
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/remove":
            path = mess.payload["args"][0]
            result = filesystem_state.remove(path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/move":
            path = mess.payload["args"][0]
            new_path = mess.payload["args"][1]
            result = filesystem_state.move(path, new_path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/copy":
            path = mess.payload["args"][0]
            new_path = mess.payload["args"][1]
            result = filesystem_state.copy(path, new_path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        else:
            raise ValueError(f"Operation {mess.action} not supported")

    except Exception as e:
        ret.error = str(e)

    return ret.to_json()


async def protocol(websocket: WebSocketServerProtocol):
    handler = {
        '/proxy': parse_proxy_request,
    }[websocket.path]

    try:
        async for message in websocket:
            logger.debug(f"WebSocket protocol handler ({websocket.path}) received: {repr(message)}")
            resp = await handler(message)
            await websocket.send(resp)
            logger.debug(f"WebSocket protocol handler ({websocket.path}) responded: {repr(resp)}")
    except Exception as e:
        logger.error(f"Error: {e}")
        await websocket.close()


async def telnet(websocket: WebSocketServerProtocol, port: str):
    try:
        await telnet_proxy.add_connection(port, websocket)
        asyncio.create_task(telnet_proxy.handle_telnet_rx(port))
        await telnet_proxy.handle_websocket_rx(port)
    except Exception as e:
        logger.error(f"Connection error: {e}")
        await websocket.close()
    finally:
        telnet_proxy.remove_connection(port)


async def stream(websocket: WebSocketServerProtocol, program: str):
    try:
        await stream_proxy.add_connection(program, websocket)
        asyncio.create_task(stream_proxy.handle_stdout_rx(program))
        asyncio.create_task(stream_proxy.handle_stderr_rx(program))
        await stream_proxy.handle_websocket_rx(program)
    except Exception as e:
        logger.error(f"Connection error: {e}")
        await websocket.close()
    finally:
        stream_proxy.remove_connection(program)


async def websocket_handler(websocket: WebSocketServerProtocol, path: str) -> None:
    logger.info(f"Connecting WebSocket {path}")

    for pattern, handler, param_names in path_handlers:
        match = pattern.match(path)
        if match:
            params = {name: match.group(name) for name in param_names}
            try:
                await handler(websocket, **params)
            except Exception as e:
                logger.error(f"Connection error: {e}")
                await websocket.close()
            finally:
                logger.info("Running post disconnect handler")
            return

    logger.error(f"No handler for path: {path}")
    await websocket.close()


path_handlers = [
    # WebSocket protocol
    (re.compile(r'^/proxy$'), protocol, []),

    # Telnet Proxy
    (re.compile(r'^/telnet/(?P<port>\w+)$'), telnet, ['port']),

    # Stream Proxy
    (re.compile(r'^/run/(?P<program>.*)$'), stream, ['program']),
]

def usage():
    print("renode-ws-proxy: WebSocket based server for managing remote Renode instance")
    print()
    print("Usage:\nrenode-ws-proxy <RENODE_BINARY> <RENODE_EXECUTION_DIR> <PORT>")
    print("    RENODE_BINARY: path/command to start Renode")
    print("    RENODE_EXECUTION_DIR: path/directory used as a Renode workspace")
    print("    PORT: WebSocket server port (defaults to 21234)")

async def main():
    global telnet_proxy, stream_proxy, renode_state, filesystem_state

    try:
        if sys.argv[1] in ['help', '--help', '-h']:
            usage()
            exit(0)

        RENODE_PATH = sys.argv[1]
        if not path.isfile(RENODE_PATH):
            raise FileNotFoundError(f'{RENODE_PATH} not a file! Exiting')
        RENODE_CWD = sys.argv[2]
        if not path.isdir(RENODE_CWD):
            raise FileNotFoundError(f'{RENODE_CWD} not a directory! Exiting')
        WS_PORT = sys.argv[3] if len(sys.argv) > 3 else 21234
    except IndexError:
        usage()
        exit(1)

    renode_gui_enabled = environ.get('RENODE_PROXY_GUI_ENABLED', False)
    if renode_gui_enabled:
        logger.info('RENODE_PROXY_GUI_ENABLED is set, Renode will be run with GUI')

    telnet_proxy = TelnetProxy()
    stream_proxy = StreamProxy()
    filesystem_state = FileSystemState()
    renode_state = RenodeState(
        renode_path=RENODE_PATH,
        renode_cwd_path=RENODE_CWD,
        gui_disabled=not renode_gui_enabled
    )

    # XXX: the `max_size` parameter is a temporary workaround for uploading large `elf` files!
    async with serve(websocket_handler, "0.0.0.0", WS_PORT, max_size=100000000):
        try:
            await asyncio.Future()
        except asyncio.exceptions.CancelledError:
            logger.error("exit requested")
            renode_state.kill()


def run():
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        logger.setLevel(LOGLEVEL)
    asyncio.run(main())


if __name__ == '__main__':
    run()
