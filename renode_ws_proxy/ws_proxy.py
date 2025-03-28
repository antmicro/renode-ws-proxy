#!/usr/bin/env python3

# Copyright (c) 2025 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import re
import asyncio
import logging
import subprocess
import argparse
from typing import cast, Optional, Iterable, TypeAlias
from pathlib import Path

from base64 import standard_b64decode, standard_b64encode
from websockets.asyncio.server import serve, ServerConnection
import sys
from sys import exit

from renode_ws_proxy.telnet_proxy import TelnetProxy
from renode_ws_proxy.argparser import parse_args, version_str
from renode_ws_proxy.stream_proxy import StreamProxy
from renode_ws_proxy.filesystem import FileSystemState
from renode_ws_proxy.renode import RenodeState
from renode_ws_proxy.protocols import (
    Message,
    Response,
    Event,
    DATA_PROTOCOL_VERSION,
    _SUCCESS,
    _FAIL,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ws_proxy.py")

LOGLEVEL = logging.DEBUG
renode_cwd = "/tmp/renode"

ProtocolTaskResult: TypeAlias = tuple[Optional[str], Iterable[asyncio.Task]]

tasks_to_cancel_on_forced_exit: set[asyncio.Task] = set()


async def parse_proxy_request(
    request: str, filesystem_state: FileSystemState
) -> ProtocolTaskResult:
    """HELPER FUNCTIONS"""

    async def handle_spawn(mess, ret):
        software = mess.payload["name"]
        tasks = set()
        if software == "renode":
            cwd = Path(mess.payload.get("cwd", filesystem_state.cwd))
            if not cwd.is_absolute():
                cwd = filesystem_state.resolve_path(cwd)
            gui = mess.payload.get("gui", False)
            logger.debug("Spawning new Renode instance")
            if await renode_state.start(gui, cwd):
                ret.status = _SUCCESS

                async def prepare_event() -> ProtocolTaskResult:
                    logger.debug("Awaiting Renode event")
                    event: Optional[str] = None

                    if raw_event := await renode_state.get_event():
                        event = Event.from_renode_event(raw_event).to_json()

                    return event, {asyncio.Task(prepare_event())}

                read_task = asyncio.Task(renode_state.read_loop())
                log_task = asyncio.Task(renode_state.log_loop())

                tasks_to_cancel_on_forced_exit.add(read_task)
                tasks_to_cancel_on_forced_exit.add(log_task)

                tasks = {
                    read_task,
                    asyncio.Task(prepare_event()),
                    log_task,
                }
        return ret, tasks

    async def handle_kill(mess, ret):
        software = mess.payload["name"]
        if software == "renode":
            for telnet in list(telnet_proxy.connections):
                telnet_proxy.remove_connection(telnet)
            ret.status = _SUCCESS if await renode_state.kill() else _FAIL
        else:
            raise ValueError(f"Killing {software} is not supported")
        return ret

    def handle_status(mess, ret):
        software = mess.payload["name"]
        if software == "renode":
            if renode_state.renode:
                ret.status = _SUCCESS
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

    async def handle_exec_monitor(mess, ret):
        commands = mess.payload["commands"]
        ret.data = []
        for command in commands:
            logger.debug(f"Executing monitor command: '{command}'")
            res, err = await renode_state.execute(command)
            if res or not err:
                ret.data.append(res)
            else:
                ret.error = err
                return ret

        ret.status = _SUCCESS
        return ret

    async def handle_exec_renode(mess, ret):
        command = mess.payload["command"]
        args = mess.payload.get("args", {})
        logger.debug(f"Executing command: '{command}'")

        res, err = await renode_state.execute(command, **args)
        if res or not err:
            ret.status = _SUCCESS
            ret.data = res
        else:
            ret.error = err
        return ret

    def handle_command(mess, ret):
        command = mess.payload["name"]
        logger.info(f"Executing {command.split()}")
        process = subprocess.Popen(
            command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        ret.status = _SUCCESS if not process.returncode else _FAIL
        ret.data = {"stdout": stdout, "stderr": stderr}
        return ret

    ret = Response(version=DATA_PROTOCOL_VERSION, status=_FAIL)
    tasks = set()

    """ PARSING """
    try:
        mess = Message.from_json(request)
        mess.validate()
        logger.debug(f"Deserialized Message: {truncate(request, 300)}")
        ret.id = mess.id

        if not mess.action:
            return ret.to_json(), tasks

        if mess.action == "spawn":
            ret, tasks = await handle_spawn(mess, ret)
        elif mess.action == "kill":
            ret = await handle_kill(mess, ret)
        elif mess.action == "status":
            ret = handle_status(mess, ret)
        elif mess.action == "command":
            ret = handle_command(mess, ret)
        elif mess.action == "exec-monitor":
            ret = await handle_exec_monitor(mess, ret)
        elif mess.action == "exec-renode":
            ret = await handle_exec_renode(mess, ret)
        elif mess.action == "fs/list":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            result = filesystem_state.list(path)
            ret.error = result.get("error")
            ret.data = result.get("data")
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/mkdir":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            result = filesystem_state.mkdir(path)
            success = result["success"]
            if not success:
                ret.error = cast(str, result["error"])
            ret.status = _SUCCESS if success else _FAIL
        elif mess.action == "fs/stat":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            result = filesystem_state.stat(path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/dwnl":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            result = filesystem_state.download(path)
            success = result["success"]
            if success:
                ret.data = standard_b64encode(result["data"]).decode()
            else:
                ret.error = result["error"]
            ret.status = _SUCCESS if success else _FAIL
        elif mess.action == "fs/upld":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
                or "data" not in mess.payload
                or not isinstance(mess.payload["data"], str)
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            data = mess.payload["data"]
            result = filesystem_state.upload(path, standard_b64decode(data))
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/remove":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            result = filesystem_state.remove(path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/move":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 2
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            new_path = mess.payload["args"][1]
            result = filesystem_state.move(path, new_path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/copy":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 2
            ):
                raise ValueError("Bad payload")
            path = mess.payload["args"][0]
            new_path = mess.payload["args"][1]
            result = filesystem_state.copy(path, new_path)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/fetch":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            url = mess.payload["args"][0]
            result = filesystem_state.fetch_from_url(url)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "fs/zip":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            url = mess.payload["args"][0]
            result = filesystem_state.download_extract_zip(url)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "tweak/socket":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
                or len(mess.payload["args"]) < 1
            ):
                raise ValueError("Bad payload")
            file = mess.payload["args"][0]
            result = filesystem_state.replace_analyzer(file)
            ret.data = result
            ret.status = _SUCCESS if result["success"] else _FAIL
        elif mess.action == "filter-events":
            if (
                mess.payload is None
                or "args" not in mess.payload
                or not isinstance(mess.payload["args"], list)
            ):
                raise ValueError("Bad payload")

            renode_state.filter_events(mess.payload["args"])
            ret.status = _SUCCESS

        else:
            raise ValueError(f"Operation {mess.action} not supported")

    except Exception as e:
        ret.error = str(e)

    return ret.to_json(), tasks


async def protocol(websocket: ServerConnection, cwd: Optional[str] = None):
    filesystem_state = FileSystemState(renode_cwd, path=cwd)

    async def handle_request(message) -> ProtocolTaskResult:
        response, tasks = await parse_proxy_request(message, filesystem_state)
        logger.debug(f"WebSocket protocol respond: {truncate(response, 300)}")
        return response, tasks

    async def get_request() -> ProtocolTaskResult:
        message = await websocket.recv(decode=True)
        # NOTE: message will always be a string because we pass decode=True to recv
        message = cast(str, message)
        logger.debug(f"WebSocket protocol request: {truncate(message, 300)}")
        return None, {
            asyncio.Task(handle_request(message)),
            asyncio.Task(get_request()),
        }

    pending = {asyncio.Task(get_request())}

    try:
        while True:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                response, tasks = task.result()
                pending.update(tasks)
                if response:
                    await websocket.send(response)

    except Exception as e:
        logger.error(f"Error: {e}")
        await websocket.close()
    finally:
        for task in pending:
            task.cancel()
        await renode_state.kill()


async def telnet(websocket: ServerConnection, port_str: str):
    port = int(port_str)
    try:
        await telnet_proxy.add_connection(port, websocket)
        asyncio.create_task(telnet_proxy.handle_telnet_rx(port))
        await telnet_proxy.handle_websocket_rx(port)
    except Exception as e:
        logger.error(f"Connection error: {e}")
        await websocket.close()
    finally:
        telnet_proxy.remove_connection(port)


async def stream(websocket: ServerConnection, program: str):
    if not program and not default_gdb:
        logger.error(
            "Can't open gdb connection without its binary. Pass it using -g [gdb] flag or pass valid program in the url."
        )
        await websocket.close()
        return

    program = program if program else default_gdb
    logger.debug(f"stream: starting {program}")
    try:
        await stream_proxy.add_connection(program, websocket)
        asyncio.create_task(stream_proxy.handle_stdout_rx(program))
        # TODO: Investigate if forwarding stderr is needed and if so, do so on a separate channel
        #       For now everything works as expected without forwarding stderr
        # asyncio.create_task(stream_proxy.handle_stderr_rx(program))
        await stream_proxy.handle_websocket_rx(program)
    except Exception as e:
        logger.error(f"Connection error: {e}")
        await websocket.close()
    finally:
        stream_proxy.remove_connection(program)


async def websocket_handler(websocket: ServerConnection) -> None:
    path = websocket.request.path if websocket.request is not None else ""
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
    (re.compile(r"^/proxy$"), protocol, []),
    (re.compile(r"^/proxy/(?P<cwd>.*)$"), protocol, ["cwd"]),
    # Telnet Proxy
    (re.compile(r"^/telnet/(?P<port_str>\w+)$"), telnet, ["port_str"]),
    # Stream Proxy
    (re.compile(r"^/run/(?P<program>.*)$"), stream, ["program"]),
]


def truncate(message, length):
    message = repr(message)
    return message[:length] + " [...]" if len(message) > length else message


async def main(args: argparse.Namespace):
    global \
        telnet_proxy, \
        stream_proxy, \
        renode_state, \
        default_gdb, \
        renode_cwd, \
        tasks_to_cancel_on_forced_exit

    renode_path = args.renode_binary
    renode_cwd = args.renode_execution_dir
    default_gdb = args.gdb

    logger.info(f"Running {version_str}")

    if args.disable_renode_gui:
        logger.info("RENODE_PROXY_GUI_DISABLED is set, Renode cannot be run with GUI")

    if args.disable_proxy_monitor_forwarding:
        logger.info(
            "RENODE_PROXY_MONITOR_FORWARDING_DISABLED is set, Renode won't write protocol based Monitor interactions to Monitor shell"
        )

    telnet_proxy = TelnetProxy()
    stream_proxy = StreamProxy()
    renode_state = RenodeState(
        renode_path=renode_path,
        gui_disabled=args.disable_renode_gui,
        monitor_forwarding_disabled=args.disable_proxy_monitor_forwarding,
    )

    # XXX: the `max_size` parameter is a temporary workaround for uploading large `elf` files!
    async with serve(websocket_handler, None, args.port, max_size=100000000):
        try:
            await asyncio.get_running_loop().create_future()
        except asyncio.exceptions.CancelledError:
            logger.error("exit requested")
            for task in tasks_to_cancel_on_forced_exit:
                task.cancel()
            tasks_to_cancel_on_forced_exit = set()
            await renode_state.kill()

    # NOTE: Without this sleep, app throws an exception that can't be handled.
    # See: https://github.com/python/cpython/issues/114177
    await asyncio.sleep(0.5)


def run():
    args = parse_args()
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        logger.setLevel(LOGLEVEL)

    asyncio.run(main(args))


if __name__ == "__main__":
    # Workaround to enable support for bundlers like pyinstaller
    if (
        len(sys.argv) > 2
        and sys.argv[1] == "-m"
        and sys.argv[2] == "renode_instance.renode"
    ):
        from renode_instance.renode import main as renode_main

        sys.argv[1:] = sys.argv[3:]
        renode_main()
        exit()
    run()
