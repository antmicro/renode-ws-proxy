# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import os
import signal
import psutil
import socket
import logging
import subprocess

from time import sleep
from contextlib import closing

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("renode.py")


# source https://psutil.readthedocs.io/en/latest/#kill-process-tree
def kill_proc_tree(
    pid, sig=signal.SIGTERM, include_parent=True, timeout=None, on_terminate=None
):
    """Kill a process tree (including grandchildren) with signal
    "sig" and return a (gone, still_alive) tuple.
    "on_terminate", if specified, is a callback function which is
    called as soon as a child terminates.
    """
    assert pid != os.getpid(), "won't kill myself"
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    if include_parent:
        children.append(parent)
    for p in children:
        try:
            p.send_signal(sig)
        except psutil.NoSuchProcess:
            pass
    gone, alive = psutil.wait_procs(children, timeout=timeout, callback=on_terminate)
    return (gone, alive)


class RenodeState:
    def __init__(
        self,
        renode_path: str,
        renode_cwd_path: str,
        telnet_base: int = 29170,
        gui_disabled: bool = True,
    ):
        self.renode_process = None
        self.renode_path = renode_path
        self.telnet_base = telnet_base
        self.renode_cwd_path = renode_cwd_path
        self.gui_disabled = gui_disabled

    def start(self, extra_args: list = [], gui: bool = False):
        if self.renode_process and self.renode_process.poll() is None:
            logger.warning("Attempted to start Renode without closing first")
            return False

        renode_args = [
            "-e",
            f"logN {self.telnet_base + 1}",
            "-e",
            f"path add @{self.renode_cwd_path}",
        ]

        if self.gui_disabled or not gui:
            # Disable everything GUI related, enable telnet
            renode_args.extend(
                [
                    "-P",
                    f"{self.telnet_base}",
                    "--hide-monitor",
                    "--hide-log",
                    "--hide-analyzers",
                    "--disable-xwt",
                ]
            )

        renode_args.extend(extra_args)
        self.renode_process = subprocess.Popen(
            [self.renode_path] + renode_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

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

        (gone, alive) = kill_proc_tree(self.renode_process.pid)
        logger.debug(f"Requested to kill Renode, killed {[p.pid for p in gone]}")
        if alive:
            logger.error(f"Failed to kill {[p.pid for p in alive]}")
            return False

        self.renode_process = None
        return True
