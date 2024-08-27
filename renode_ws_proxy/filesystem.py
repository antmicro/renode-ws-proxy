# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import logging
from stat import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("filesystem.py")

class FileSystemState:
    def __init__(self, path: str):
        self.cwd = path

    def list(self):
        try:
            return [path_info(self.cwd, p) for p in os.listdir(self.cwd)]
        except Exception as e:
            logger.error(f"Error listing directory: {self.cwd} >>> {e}")
            return []

    def stat(self, path):
        try:
            full_path = os.path.normpath(f"{self.cwd}/{path}")
            stat = os.lstat(full_path)
            return {
                "success": True,
                "size": stat.st_size,
                "isfile": not S_ISDIR(stat.st_mode),
                "ctime": stat.st_ctime,
                "mtime": stat.st_mtime,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download(self, path):
        try:
            full_path = os.path.normpath(f"{self.cwd}/{path}")
            with open(full_path, "rb") as f:
                return {"success": True, "data": f.read()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def upload(self, path, data):
        try:
            full_path = os.path.normpath(f"{self.cwd}/{path}")
            with open(full_path, 'wb') as file:
                file.write(data)
            return {"success": True, "path": full_path}
        except Exception as e:
            logger.error(f"Error uploading file: {path} >>> {e}")
            return {"success": False, "error": str(e)}

    def remove(self, path):
        try:
            full_path = os.path.normpath(f"{self.cwd}/{path}")
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            return {"success": True, "path": full_path}
        except Exception as e:
            logger.error(f"Error removing file: {path} >>> {e}")
            return {"success": False, "error": str(e)}

    def move(self, path, new_path):
        try:
            full_path = os.path.normpath(f"{self.cwd}/{path}")
            new_full_path = os.path.normpath(f"{self.cwd}/{new_path}")
            shutil.move(full_path, new_full_path)
            return {"success": True, "from": full_path, "to": new_full_path}
        except Exception as e:
            logger.error(f"Error moving file: {path} to {new_path} >>> {e}")
            return {"success": False, "error": str(e)}

    def copy(self, path, new_path):
        try:
            full_path = os.path.normpath(f"{self.cwd}/{path}")
            new_full_path = os.path.normpath(f"{self.cwd}/{new_path}")
            shutil.copy(full_path, new_full_path)
            return {"success": True, "from": full_path, "to": new_full_path}
        except Exception as e:
            logger.error(f"Error copying file: {path} to {new_path} >>> {e}")
            return {"success": False, "error": str(e)}

def path_info(cwd, path):
    full_path = os.path.join(cwd, path)
    return {
        "name": path,
        "isfile": os.path.isfile(full_path), # If false, the path is a directory
        "islink": os.path.islink(full_path)
    }
