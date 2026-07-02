from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from proxy_gui_client.core.models import ProxyNode


class CoreAdapterError(RuntimeError):
    """Base exception for proxy core adapter errors."""


class CorePathError(CoreAdapterError):
    """Raised when the configured core executable is invalid."""


class CoreConfigError(CoreAdapterError):
    """Raised when a core config cannot be generated."""


class UnsupportedCoreError(CoreAdapterError):
    """Raised when an unknown core type is requested."""


class BaseCoreAdapter(ABC):
    name: str
    executable_name: str

    def validate_core_path(self, core_path: str) -> None:
        path = Path(str(core_path or "")).expanduser()
        if not str(core_path or "").strip():
            raise CorePathError(f"Please configure {self.executable_name} path first.")
        if not path.exists():
            raise CorePathError(f"Core executable does not exist: {path}")
        if not path.is_file():
            raise CorePathError(f"Core path is not a file: {path}")

    @abstractmethod
    def generate_config(self, node: ProxyNode, settings: dict[str, Any], output_path: str | Path) -> Path:
        raise NotImplementedError

    @abstractmethod
    def build_start_command(self, core_path: str, config_path: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def supports_node_type(self, node_type: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_default_http_port(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_default_socks_port(self) -> int:
        raise NotImplementedError


class PlaceholderCoreAdapter(BaseCoreAdapter):
    def generate_config(self, node: ProxyNode, settings: dict[str, Any], output_path: str | Path) -> Path:
        raise NotImplementedError(f"{self.name} adapter is a placeholder and cannot generate config yet.")

    def build_start_command(self, core_path: str, config_path: str) -> list[str]:
        raise NotImplementedError(f"{self.name} adapter is a placeholder and cannot build start command yet.")

    def supports_node_type(self, node_type: str) -> bool:
        return False

    def get_default_http_port(self) -> int:
        return 7890

    def get_default_socks_port(self) -> int:
        return 7891

