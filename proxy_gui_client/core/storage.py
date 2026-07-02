from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .models import DEFAULT_SETTINGS, ProxyNode
from .paths import bundled_data_dir, data_dir, is_frozen, log_dir, resolve_app_path
from .subscription_groups import ensure_subscription_group_settings
from .table_preferences import ensure_table_preferences


def nodes_file() -> Path:
    return data_dir() / "nodes.json"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def proxy_marker_file() -> Path:
    return data_dir() / "proxy_enabled_by_app.json"


DATA_DIR = data_dir()
LOG_DIR = log_dir()
NODES_FILE = nodes_file()
SETTINGS_FILE = settings_file()


def ensure_app_dirs() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    log_dir().mkdir(parents=True, exist_ok=True)
    if not nodes_file().exists():
        _copy_bundled_file("nodes.json", nodes_file(), "[]")
    if not settings_file().exists():
        _copy_bundled_file("settings.json", settings_file(), json.dumps(DEFAULT_SETTINGS, indent=2, ensure_ascii=False))


def load_nodes() -> list[ProxyNode]:
    ensure_app_dirs()
    try:
        data = json.loads(nodes_file().read_text(encoding="utf-8"))
        return [ProxyNode.from_dict(item) for item in data if isinstance(item, dict)]
    except Exception:
        return []


def save_nodes(nodes: list[ProxyNode]) -> None:
    ensure_app_dirs()
    payload = [node.to_dict() for node in nodes]
    nodes_file().write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_settings() -> dict[str, Any]:
    ensure_app_dirs()
    try:
        loaded = json.loads(settings_file().read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    settings = dict(DEFAULT_SETTINGS)
    settings.update({key: value for key, value in loaded.items() if value is not None})
    settings = _normalize_runtime_paths(settings)
    return ensure_table_preferences(ensure_subscription_group_settings(settings))


def save_settings(settings: dict[str, Any]) -> None:
    ensure_app_dirs()
    merged = dict(DEFAULT_SETTINGS)
    merged.update(settings)
    merged = ensure_table_preferences(ensure_subscription_group_settings(merged))
    settings_file().write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")


def mark_system_proxy_enabled(state: dict[str, Any]) -> None:
    ensure_app_dirs()
    proxy_marker_file().write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_system_proxy_marker() -> dict[str, Any] | None:
    ensure_app_dirs()
    path = proxy_marker_file()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def clear_system_proxy_marker() -> None:
    path = proxy_marker_file()
    if path.exists():
        path.unlink()


def _normalize_runtime_paths(settings: dict[str, Any]) -> dict[str, Any]:
    if not is_frozen():
        return settings
    updated = dict(settings)
    core_path = str(updated.get("core_path") or "")
    if core_path and Path(core_path).is_absolute() and not Path(core_path).exists():
        default_core = str(DEFAULT_SETTINGS.get("core_path") or "")
        if resolve_app_path(default_core).exists():
            updated["core_path"] = default_core
    return updated


def _copy_bundled_file(name: str, target: Path, fallback: str) -> None:
    source = bundled_data_dir() / name
    try:
        if is_frozen() and source.exists() and source.resolve() != target.resolve():
            shutil.copyfile(source, target)
            return
    except OSError:
        pass
    target.write_text(fallback, encoding="utf-8")
