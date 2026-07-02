from __future__ import annotations

from pathlib import Path
from typing import Any

from proxy_gui_client.core.adapters.base import CoreConfigError
from proxy_gui_client.core.adapters.singbox import SingBoxAdapter
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.storage import resolve_app_path


ConfigGenerationError = CoreConfigError


def generate_sing_box_config(node: ProxyNode, settings: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible wrapper for tests and old call sites."""

    return SingBoxAdapter().generate_config_dict(node, settings)


def write_sing_box_config(node: ProxyNode, settings: dict[str, Any]) -> Path:
    """Backward-compatible wrapper for tests and old call sites."""

    path = resolve_app_path(str(settings.get("config_path") or "proxy_gui_client/data/generated_config.json"))
    return SingBoxAdapter().generate_config(node, settings, path)

