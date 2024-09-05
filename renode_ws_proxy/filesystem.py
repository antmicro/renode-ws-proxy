# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import os
import re
import shutil
import logging
import zipfile
import urllib.request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("filesystem.py")

class FileSystemState:
    def __init__(self, path: str):
        self.cwd = path
        os.makedirs(self.cwd, exist_ok=True)

    @staticmethod
    def path_info(cwd, path):
        full_path = os.path.join(cwd, path)
        return {
            "name": path,
            "isfile": os.path.isfile(full_path), # If false, the path is a directory
            "islink": os.path.islink(full_path)
        }

    def replace_analyzer(self, file, path='/'):
        file = f"{self.cwd}/{file}"
        with open(file, "r") as sources:
            lines = sources.readlines()
        with open(file, "w") as sources:
            for line in lines:
                try:
                    newLine = re.sub(r"^showAnalyzer ([a-zA-Z0-9]+)", r'emulation CreateServerSocketTerminal 29172 "term"; connector Connect \1 term', line)
                except Exception as e:
                    logger.error(str(e))
                sources.write(newLine)

        return {"success": True}

    def download_extract_zip(self, zip_url, path='/'):
        temp_zip_path = f"{self.cwd}/temp.zip"
        full_path = os.path.normpath(f"{self.cwd}/{path}")
        try:
            urllib.request.urlretrieve(zip_url, temp_zip_path)
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(full_path)
            os.remove(temp_zip_path)
        except Exception as e:
            logger.error(f"Error downloading zip file ({zip_url}): {e}")
            return {"success": False, "error": str(e)}

        return {"success": True, "path": full_path}

    def fetch_from_url(self, url, path='/'):
        fname = os.path.basename(url)
        full_path = os.path.normpath(f"{self.cwd}/{path}/{fname}")
        try:
            urllib.request.urlretrieve(url, full_path)
        except Exception as e:
            logger.error(f"Error downloading file ({url}): {e}")
            return {"success": False, "error": str(e)}

        return {"success": True, "path": full_path}

    def list(self, path):
        full_path = os.path.normpath(f"{self.cwd}/{path}")
        logger.error(full_path)
        try:
            return [self.path_info(full_path, p) for p in os.listdir(full_path)]
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
                "isfile": os.path.isfile(full_path),
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
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
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

    def mkdir(self, path):
        try:
            full_path = os.path.normpath(f"{self.cwd}/{path}")
            os.makedirs(full_path, exist_ok=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        
