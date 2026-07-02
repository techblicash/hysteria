from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from proxy_gui_client.core.adapters.base import BaseCoreAdapter, CoreConfigError
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.routing import build_singbox_route


class SingBoxAdapter(BaseCoreAdapter):
    name = "sing-box"
    executable_name = "sing-box.exe"
    supported_node_types = {"vmess", "vless", "trojan", "shadowsocks", "ss"}

    def generate_config(self, node: ProxyNode, settings: dict[str, Any], output_path: str | Path) -> Path:
        if not self.supports_node_type(node.type):
            raise CoreConfigError(f"sing-box does not support node type in this MVP: {node.type}")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        config = self.generate_config_dict(node, settings)
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def generate_config_dict(self, node: ProxyNode, settings: dict[str, Any]) -> dict[str, Any]:
        http_port = int(settings.get("http_port") or self.get_default_http_port())
        socks_port = int(settings.get("socks_port") or self.get_default_socks_port())
        _validate_port(http_port, "HTTP listen port")
        _validate_port(socks_port, "SOCKS5 listen port")
        if http_port == socks_port:
            raise CoreConfigError("HTTP 端口和 SOCKS5 端口不能相同")
        outbound = self._node_to_outbound(node)
        return {
            "log": {"level": "info", "timestamp": True},
            "inbounds": [
                {"type": "http", "tag": "http-in", "listen": "127.0.0.1", "listen_port": http_port},
                {"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": socks_port},
            ],
            "outbounds": [
                outbound,
                {"type": "direct", "tag": "direct"},
                {"type": "block", "tag": "block"},
            ],
            "route": build_singbox_route(settings),
        }

    def build_start_command(self, core_path: str, config_path: str) -> list[str]:
        return [str(Path(core_path).expanduser()), "run", "-c", str(config_path)]

    def supports_node_type(self, node_type: str) -> bool:
        return node_type.lower() in self.supported_node_types

    def get_default_http_port(self) -> int:
        return 7890

    def get_default_socks_port(self) -> int:
        return 7891

    def _node_to_outbound(self, node: ProxyNode) -> dict[str, Any]:
        node_type = node.type.lower()
        if node_type == "ss":
            node_type = "shadowsocks"
        if not node.server or not node.port:
            raise CoreConfigError("节点缺少服务器地址或端口")
        _validate_port(int(node.port), "节点端口")

        base: dict[str, Any] = {
            "type": node_type,
            "tag": "proxy",
            "server": node.server,
            "server_port": int(node.port),
        }
        if node_type == "vmess":
            if not node.uuid:
                raise CoreConfigError("VMess 节点缺少 UUID")
            base.update(
                {
                    "uuid": node.uuid,
                    "security": node.security or "auto",
                    "alter_id": int(node.extra.get("alter_id", 0) if node.extra else 0),
                }
            )
        elif node_type == "vless":
            if not node.uuid:
                raise CoreConfigError("VLESS 节点缺少 UUID")
            base["uuid"] = node.uuid
            if node.flow:
                base["flow"] = node.flow
        elif node_type == "trojan":
            if not node.password:
                raise CoreConfigError("Trojan 节点缺少密码")
            base["password"] = node.password
        elif node_type == "shadowsocks":
            if not node.method or not node.password:
                raise CoreConfigError("Shadowsocks 节点缺少加密方法或密码")
            base.update({"method": node.method, "password": node.password})
        else:
            raise CoreConfigError(f"暂不支持的节点类型: {node.type}")

        tls = _build_tls(node)
        if tls:
            base["tls"] = tls
        transport = _build_transport(node)
        if transport:
            base["transport"] = transport
        return base


def _validate_port(port: int, label: str) -> None:
    if port < 1 or port > 65535:
        raise CoreConfigError(f"{label}必须在 1-65535 之间")


def _build_tls(node: ProxyNode) -> dict[str, Any] | None:
    if not node.tls and node.security not in {"tls", "reality"}:
        return None
    tls: dict[str, Any] = {"enabled": True}
    if node.sni:
        tls["server_name"] = node.sni
    if node.security == "reality":
        tls["reality"] = {"enabled": True}
        public_key = node.extra.get("pbk") if node.extra else ""
        short_id = node.extra.get("sid") if node.extra else ""
        if public_key:
            tls["reality"]["public_key"] = public_key
        if short_id:
            tls["reality"]["short_id"] = short_id
    return tls


def _build_transport(node: ProxyNode) -> dict[str, Any] | None:
    network = (node.network or "tcp").lower()
    if network in {"tcp", ""}:
        return None
    if network == "ws":
        transport: dict[str, Any] = {"type": "ws"}
        if node.path:
            transport["path"] = node.path
        if node.host:
            transport["headers"] = {"Host": node.host}
        return transport
    if network in {"grpc", "http", "quic"}:
        return {"type": network}
    return {"type": network}
