from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from proxy_gui_client.core.table_preferences import (
    DEFAULT_NODE_FILTER_PREFERENCES,
    DEFAULT_TABLE_COLUMN_WIDTHS,
)
from proxy_gui_client.core.routing import (
    DEFAULT_BLOCK_DOMAIN_SUFFIXES,
    DEFAULT_DIRECT_DOMAIN_SUFFIXES,
    DEFAULT_DIRECT_IP_CIDRS,
)


@dataclass
class ProxyNode:
    """Serializable proxy node definition used by the GUI and config generator."""

    name: str
    type: str
    server: str
    port: int
    id: str = field(default_factory=lambda: str(uuid4()))
    uuid: str = ""
    password: str = ""
    method: str = ""
    security: str = ""
    network: str = "tcp"
    path: str = ""
    host: str = ""
    sni: str = ""
    tls: bool = False
    flow: str = ""
    source: str = "manual"
    source_file: str = ""
    imported_at: str = ""
    latency_ms: int | None = None
    tcp_latency_ms: int | None = None
    url_latency_ms: int | None = None
    test_status: str = ""
    last_tested_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProxyNode":
        payload = dict(data)
        payload.setdefault("id", str(uuid4()))
        payload.setdefault("network", "tcp")
        payload.setdefault("source", "manual")
        payload.setdefault("source_file", "")
        payload.setdefault("imported_at", "")
        payload.setdefault("last_tested_at", "")
        payload.setdefault("extra", {})
        payload["port"] = int(payload.get("port") or 0)
        return cls(**{key: payload.get(key) for key in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "server": self.server,
            "port": self.port,
            "uuid": self.uuid,
            "password": self.password,
            "method": self.method,
            "security": self.security,
            "network": self.network,
            "path": self.path,
            "host": self.host,
            "sni": self.sni,
            "tls": self.tls,
            "flow": self.flow,
            "source": self.source,
            "source_file": self.source_file,
            "imported_at": self.imported_at,
            "latency_ms": self.latency_ms,
            "tcp_latency_ms": self.tcp_latency_ms,
            "url_latency_ms": self.url_latency_ms,
            "test_status": self.test_status,
            "last_tested_at": self.last_tested_at,
            "extra": self.extra,
        }


DEFAULT_SETTINGS: dict[str, Any] = {
    "core_type": "sing-box",
    "core_path": "cores/sing-box/sing-box.exe",
    "config_path": "data/generated_config.json",
    "http_port": 7890,
    "socks_port": 7891,
    "subscription_url": "",
    "subscription_groups": [],
    "test_timeout_seconds": 5,
    "latency_test_url": "https://www.gstatic.com/generate_204",
    "latency_timeout": 5,
    "system_proxy_on_start": False,
    "disable_system_proxy_on_stop": True,
    "routing_mode": "global",
    "rule_direct_domain_suffixes": list(DEFAULT_DIRECT_DOMAIN_SUFFIXES),
    "rule_direct_ip_cidrs": list(DEFAULT_DIRECT_IP_CIDRS),
    "rule_proxy_domain_suffixes": [],
    "rule_block_domain_suffixes": list(DEFAULT_BLOCK_DOMAIN_SUFFIXES),
    "table_column_widths": dict(DEFAULT_TABLE_COLUMN_WIDTHS),
    "node_filter_preferences": dict(DEFAULT_NODE_FILTER_PREFERENCES),
    "minimize_to_tray": True,
    "close_to_tray": True,
    "start_minimized": False,
    "autostart_enabled": False,
    "auto_connect_on_start": False,
    "last_selected_node_identity": "",
    "last_selected_node_name": "",
    "tray_show_notifications": True,
    "recent_node_identities": [],
    "update_check_enabled": False,
    "update_check_url": "",
}
