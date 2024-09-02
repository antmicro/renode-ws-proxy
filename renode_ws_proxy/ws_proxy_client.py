#!/usr/bin/env python

# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import tty
import termios
import asyncio
import websockets
import sys
import logging

from renode_ws_proxy.protocols import Message, Response, DATA_PROTOCOL_VERSION

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ws_proxy_client.py")


proxy_command_map = {
    # Proxy commands
    'sr': Message(version=DATA_PROTOCOL_VERSION, action="spawn", payload={"name": "renode"}).to_json(),
    'kr': Message(version=DATA_PROTOCOL_VERSION, action="kill", payload={"name": "renode"}).to_json(),
    'sg': Message(version=DATA_PROTOCOL_VERSION, action="spawn", payload={"name": "gdb"}).to_json(),
    'kg': Message(version=DATA_PROTOCOL_VERSION, action="kill", payload={"name": "gdb"}).to_json(),
    'gstr': Message(version=DATA_PROTOCOL_VERSION, action="status", payload={"name": "renode"}).to_json(),
    'gsta': Message(version=DATA_PROTOCOL_VERSION, action="status", payload={"name": "run"}).to_json(),
    'gstt': Message(version=DATA_PROTOCOL_VERSION, action="status", payload={"name": "telnet"}).to_json(),
    'cmd': Message(version=DATA_PROTOCOL_VERSION, action="command", payload={"name": "ls -lahv"}).to_json(),
}

telnet_command_map = {
    # Telnet commands
    'lg': "log \"test\"\r\n",
    'ld': "i @test.resc\r\n",
    'st': "s\r\n",
    "ph": "path\r\n",
    "pp": "p\r\n",
}

fs_command_map = {
    'ls': Message(version=DATA_PROTOCOL_VERSION, action="list", payload={"args": []}).to_json(),
    'mv': Message(version=DATA_PROTOCOL_VERSION, action="move", payload={"args": ["fname1", "fname2"]}).to_json(),
    'cp': Message(version=DATA_PROTOCOL_VERSION, action="copy", payload={"args": ["fname1", "fname2"]}).to_json(),
    'up': Message(version=DATA_PROTOCOL_VERSION, action="upld", payload={"args": ["fname_up"], "data": "test"}).to_json(),
    'dn': Message(version=DATA_PROTOCOL_VERSION, action="dwnl", payload={"args": ["fname"]}).to_json(),
}


async def send_input(websocket):
    logger.debug('Starting input handler...')
    telnet_context = 'telnet' in websocket.path
    fs_context = 'fs' in websocket.path
    run_context = "run" in websocket.path

    if telnet_context and fs_context:
        raise ValueError("this is not possible?")

    try:
        if telnet_context or run_context:
            logger.setLevel(logging.CRITICAL)

            # Save original terminal settings
            orig_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin)

            current_line = []

            try:
                while True:
                    # Reading character by character
                    user_input = await asyncio.to_thread(sys.stdin.read, 1)

                    if user_input:
                        if user_input == '\x7f':  # Backspace character
                            if current_line:
                                # Remove the last character from the terminal
                                sys.stdout.write('\b \b')
                                sys.stdout.flush()
                                current_line.pop()
                        else:
                            # Echo the character locally
                            sys.stdout.write(user_input)
                            sys.stdout.flush()
                            current_line.append(user_input)

                        # Send the character over WebSocket
                        cmd = user_input
                        await websocket.send(cmd)
                        logger.info(f"Client -> WebSocket: {repr(user_input)}")
            finally:
                # Restore original terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, orig_settings)

        else:
            while True:
                # Reading a full line in other contexts
                user_input = await asyncio.to_thread(input)
                if user_input:
                    if fs_context:
                        cmd = fs_command_map[user_input]
                    else:
                        cmd = proxy_command_map[user_input]

                    await websocket.send(cmd)
                    logger.info(f"Client -> WebSocket: {repr(user_input)}")

    except (EOFError, websockets.ConnectionClosed):
        logger.info("Input stream closed or connection closed")
    except Exception as e:
        logger.error(f"Error sending message: {e}")


async def receive_messages(websocket):
    logger.debug('Starting message receiver...')
    telnet_context = 'telnet' in websocket.path
    fs_context = 'fs' in websocket.path
    run_context = "run" in websocket.path

    if telnet_context and fs_context:
        raise ValueError("this is not possible?")

    try:
        async for message in websocket:
            resp = None
            if telnet_context or run_context:
                resp = message
                logger.setLevel(logging.CRITICAL)
                print(resp, end='')
            else:
                resp = Response.from_json(message)
                logger.info(f"WebSocket -> Client: {resp}")

    except websockets.ConnectionClosed:
        logger.info("Connection closed")
    except Exception as e:
        logger.error(f"Error receiving message: {e}")


async def websocket_client():
    if len(sys.argv) < 2:
        print("Usage: python3 ./ws_proxy_client.py <uri>")
        exit(1)

    uri = sys.argv[1]

    try:
        async with websockets.connect(uri) as websocket:
            logger.info(f"Connected to {uri}")

            await asyncio.gather(
                send_input(websocket),
                receive_messages(websocket)
            )
    except Exception as e:
        logger.error(f"Connection error: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(websocket_client())
