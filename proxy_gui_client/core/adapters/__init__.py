from __future__ import annotations

from proxy_gui_client.core.adapters.base import (
    BaseCoreAdapter,
    CoreAdapterError,
    CoreConfigError,
    CorePathError,
    UnsupportedCoreError,
)
from proxy_gui_client.core.adapters.mihomo import MihomoAdapter
from proxy_gui_client.core.adapters.singbox import SingBoxAdapter
from proxy_gui_client.core.adapters.xray import XrayAdapter


def normalize_core_type(core_type: str | None) -> str:
    return (core_type or "sing-box").strip().lower().replace("_", "-")


def get_core_adapter(core_type: str | None) -> BaseCoreAdapter:
    normalized = normalize_core_type(core_type)
    if normalized in {"sing-box", "singbox"}:
        return SingBoxAdapter()
    if normalized in {"mihomo", "clash-meta", "clash.meta"}:
        return MihomoAdapter()
    if normalized == "xray":
        return XrayAdapter()
    raise UnsupportedCoreError(f"Unsupported core type: {core_type}")


__all__ = [
    "BaseCoreAdapter",
    "CoreAdapterError",
    "CoreConfigError",
    "CorePathError",
    "UnsupportedCoreError",
    "get_core_adapter",
]

