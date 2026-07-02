from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", base_dir())).resolve()
    return base_dir()


def package_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    if os.environ.get("PROXY_GUI_CLIENT_DATA_DIR"):
        return Path(os.environ["PROXY_GUI_CLIENT_DATA_DIR"])
    if is_frozen():
        return base_dir() / "data"
    return package_dir() / "data"


def log_dir() -> Path:
    if os.environ.get("PROXY_GUI_CLIENT_LOG_DIR"):
        return Path(os.environ["PROXY_GUI_CLIENT_LOG_DIR"])
    if is_frozen():
        return base_dir() / "logs"
    return package_dir() / "logs"


def cores_dir() -> Path:
    if os.environ.get("PROXY_GUI_CLIENT_CORES_DIR"):
        return Path(os.environ["PROXY_GUI_CLIENT_CORES_DIR"])
    return base_dir() / "cores"


def bundled_data_dir() -> Path:
    if is_frozen():
        return resource_dir() / "data"
    return package_dir() / "data"


def version_file() -> Path:
    if is_frozen():
        return base_dir() / "version.txt"
    return base_dir() / "version.txt"


def resolve_app_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    parts = path.parts
    if len(parts) >= 2 and parts[0] == "proxy_gui_client" and parts[1] == "data":
        return data_dir().joinpath(*parts[2:])
    if parts and parts[0] == "data":
        return data_dir().joinpath(*parts[1:])
    if parts and parts[0] == "cores":
        return cores_dir().joinpath(*parts[1:])
    return base_dir() / path
