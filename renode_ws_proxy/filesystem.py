# Copyright (c) 2024 Antmicro <www.antmicro.com>
#
# SPDX-License-Identifier: Apache-2.0

import os
import re
import shutil
import logging
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("filesystem.py")


class FileSystemState:
    def __init__(self, base: str, *, path: Optional[str] = None):
        self.cwd = Path(base)
        if path is not None:
            self.cwd = self.__resolve_path(path)
        self.cwd.mkdir(parents=True, exist_ok=True)

    def __resolve_path(self, path: str | Path, *, base: Optional[Path] = None):
        if base is None:
            base = self.cwd
        path_ = Path(path)
        parts = path_.parts[1:] if path_.is_absolute() else path_.parts
        return Path(*base.parts, *parts)

    def __path_info(self, path: str, *, base: Optional[Path] = None):
        full_path = self.__resolve_path(path, base=base)
        return {
            "name": path,
            "isfile": full_path.is_file(),  # If false, the path is a directory
            "islink": full_path.is_symlink(),
        }

    def replace_analyzer(self, file):
        file = self.__resolve_path(file)
        try:
            with file.open("r") as sources:
                lines = sources.readlines()
            with file.open("w") as sources:
                for line in lines:
                    line = re.sub(
                        r"^showAnalyzer ([a-zA-Z0-9_.]+)",
                        r'emulation CreateServerSocketTerminal 29172 "term"; connector Connect \1 term',
                        line,
                    )
                    sources.write(line)

            return {"success": True}
        except Exception as e:
            logger.error(f"Error replacing analyzers ({file}): {e}")
            return {"success": False, "error": str(e)}

    def download_extract_zip(self, zip_url):
        temp_zip_path = self.__resolve_path("temp.zip")
        try:
            urllib.request.urlretrieve(zip_url, temp_zip_path)
            with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
                zip_ref.extractall(self.cwd)
            os.remove(temp_zip_path)
        except Exception as e:
            logger.error(f"Error downloading zip file ({zip_url}): {e}")
            return {"success": False, "error": str(e)}

        return {"success": True, "path": str(self.cwd)}

    def fetch_from_url(self, url):
        fname = os.path.basename(url)
        full_path = self.__resolve_path(fname)
        try:
            urllib.request.urlretrieve(url, full_path)
        except Exception as e:
            logger.error(f"Error downloading file ({url}): {e}")
            return {"success": False, "error": str(e)}

        return {"success": True, "path": str(full_path)}

    def list(self, path: str):
        full_path = self.__resolve_path(path)
        try:
            return {
                "success": True,
                "data": [
                    self.__path_info(p, base=full_path) for p in os.listdir(full_path)
                ],
            }
        except Exception as e:
            logger.error(f"Error listing directory: {self.cwd} >>> {e}")
            return {"success": False, "error": str(e)}

    def stat(self, path: str):
        try:
            full_path = self.__resolve_path(path)
            stat = full_path.lstat()
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
            full_path = self.__resolve_path(path)
            data = full_path.read_bytes()
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def upload(self, path, data):
        try:
            full_path = self.__resolve_path(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            return {"success": True, "path": str(full_path)}
        except Exception as e:
            logger.error(f"Error uploading file: {path} >>> {e}")
            return {"success": False, "error": str(e)}

    def remove(self, path):
        try:
            full_path = self.__resolve_path(path)
            if full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                full_path.unlink()
            return {"success": True, "path": str(full_path)}
        except Exception as e:
            logger.error(f"Error removing file: {path} >>> {e}")
            return {"success": False, "error": str(e)}

    def move(self, path, new_path):
        try:
            full_path = self.__resolve_path(path)
            new_full_path = self.__resolve_path(new_path)
            full_path.rename(new_full_path)
            return {"success": True, "from": str(full_path), "to": str(new_full_path)}
        except Exception as e:
            logger.error(f"Error moving file: {path} to {new_path} >>> {e}")
            return {"success": False, "error": str(e)}

    def copy(self, path, new_path):
        try:
            full_path = self.__resolve_path(path)
            new_full_path = self.__resolve_path(new_path)
            shutil.copy(full_path, new_full_path)
            return {"success": True, "from": str(full_path), "to": str(new_full_path)}
        except Exception as e:
            logger.error(f"Error copying file: {path} to {new_path} >>> {e}")
            return {"success": False, "error": str(e)}

    def mkdir(self, path):
        try:
            full_path = self.__resolve_path(path)
            full_path.mkdir(parents=True, exist_ok=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resolve_path(self, path: str | Path):
        return self.__resolve_path(path)
