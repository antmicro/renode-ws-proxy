# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import os
import psutil
import socket
import signal
import logging
import subprocess

from time import sleep
from contextlib import closing

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("renode.py")


class RenodeState:
    def __init__(self, renode_path: str, telnet_base: int = 29170, renode_cwd_path: str = "/tmp/renode/", gui_disabled: bool = True):
        self.renode_process = None
        self.renode_path = renode_path
        self.telnet_base = telnet_base
        self.renode_cwd_path = renode_cwd_path
        self.gui_disabled = gui_disabled

    def start(self, extra_args: list = []):
        renode_args = [
            '-e', f'logN {self.telnet_base + 1}',
            '-e', f'path add @{self.renode_cwd_path}',
        ]

        if self.gui_disabled:
            # Disable everything GUI related, enable telnet
            renode_args.extend([
                '-P', f'{self.telnet_base}',
                '--hide-monitor', '--hide-log',
                '--hide-analyzers', '--disable-xwt',
            ])

        renode_args.extend(extra_args)
        self.renode_process = subprocess.Popen([self.renode_path] + renode_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        if self.gui_disabled:
            # Block until Renode opens the monitor socket
            # TODO(pkoscik): add timeout
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                while sock.connect_ex(("localhost", self.telnet_base)):
                    sleep(1)

        logger.info(f"Started Renode process (PID: {self.renode_process.pid})")
        return True

    def kill(self):
        if not self.renode_process:
            logger.warning("Requested to kill Renode, but self.renode_process is None")
            return False

        for i in range(5):
            if self.renode_process.poll() is not None:
                self.renode_process = None
                logger.info("Killed Renode process")
                return True

            logger.info(f"Attempting to kill renode for the {i + 1} time! (PID: {self.renode_process.pid})")
            self.renode_process.kill()
            sleep(1)

        logger.error(f"Failed to kill Renode process: {self.renode_process}")
        return False
