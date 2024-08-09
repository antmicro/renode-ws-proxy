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
    RENODE_PID_PATH = '/tmp/renode_pid'

    def __init__(self, renode_path: str, telnet_base: int = 29170, renode_cwd_path: str = "/tmp/renode/"):
        self.renode_pid = None
        self.renode_path = renode_path
        self.telnet_base = telnet_base
        self.renode_cwd_path = renode_cwd_path

    def start(self, extra_args: list = []):
        renode_args = [
            '-P', f'{self.telnet_base}',
            '-e', f'logN {self.telnet_base + 1}',
            '-e', f'path set @{self.renode_cwd_path}',
            '--pid-file', f'{self.RENODE_PID_PATH}',

            # Disable everything GUI related
            '--hide-monitor', '--hide-log',
            '--hide-analyzers', '--disable-xwt',

            *extra_args
        ]
        subprocess.Popen([self.renode_path] + renode_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        # Block until Renode opens the monitor socket
        # TODO(pkoscik): add timeout
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            while sock.connect_ex(("localhost", self.telnet_base)):
                sleep(1)

        # This is safe as we have already waited for the socket to open
        with open(self.RENODE_PID_PATH, 'r') as f:
            self.renode_pid = int(f.read())

        logger.info(f"Started Renode with PID: {self.renode_pid}")
        return self.renode_pid

    def kill(self):
        if not self.renode_pid:
            logger.warning("Requested to kill Renode, but self.renode_pid is None")
            return False

        for _ in range(5):
            os.kill(self.renode_pid, signal.SIGINT)
            sleep(1)
            if not psutil.pid_exists(self.renode_pid):
                self.renode_pid = None
                return True

        logger.error(f"Failed to kill Renode PID: {self.renode_pid}")
        return False
