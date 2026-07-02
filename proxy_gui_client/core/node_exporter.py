from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from proxy_gui_client.core.adapters.base import CoreConfigError
from proxy_gui_client.core.adapters.singbox import SingBoxAdapter
from proxy_gui_client.core.models import ProxyNode


@dataclass
class ExportResult:
    exported_count: int = 0
    skipped_count: int = 0
    warnings: list[str] = field(default_factory=list)


def export_nodes_project_json(nodes: list[ProxyNode], path: str) -> ExportResult:
    _ensure_nodes(nodes)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([node.to_dict() for node in nodes], indent=2, ensure_ascii=False), encoding="utf-8")
    return ExportResult(exported_count=len(nodes))


def export_nodes_singbox_json(nodes: list[ProxyNode], path: str) -> ExportResult:
    _ensure_nodes(nodes)
    adapter = SingBoxAdapter()
    outbounds: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, node in enumerate(nodes):
        try:
            outbound = adapter._node_to_outbound(node)
        except (CoreConfigError, ValueError, TypeError) as exc:
            warnings.append(f"Node {node.name or index + 1} skipped: {exc}")
            continue
        outbound["tag"] = node.name or f"node-{index + 1}"
        outbounds.append(outbound)

    if not outbounds:
        raise ValueError("No supported nodes can be exported to sing-box JSON")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"outbounds": outbounds}, indent=2, ensure_ascii=False), encoding="utf-8")
    return ExportResult(exported_count=len(outbounds), skipped_count=len(nodes) - len(outbounds), warnings=warnings)


def export_nodes_clash_yaml(nodes: list[ProxyNode], path: str) -> ExportResult:
    _ensure_nodes(nodes)
    proxies: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, node in enumerate(nodes):
        proxy = _node_to_clash_proxy(node, index, warnings)
        if proxy:
            proxies.append(proxy)

    if not proxies:
        raise ValueError("No supported nodes can be exported to Clash YAML")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump({"proxies": proxies}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return ExportResult(exported_count=len(proxies), skipped_count=len(nodes) - len(proxies), warnings=warnings)


def _ensure_nodes(nodes: list[ProxyNode]) -> None:
    if not nodes:
        raise ValueError("No nodes selected for export")


def _node_to_clash_proxy(node: ProxyNode, index: int, warnings: list[str]) -> dict[str, Any] | None:
    node_type = (node.type or "").strip().lower()
    if node_type == "shadowsocks":
        node_type = "ss"
    if node_type not in {"vmess", "vless", "trojan", "ss"}:
        warnings.append(f"Node {node.name or index + 1} skipped: unsupported type {node.type or '<missing>'}")
        return None
    if not node.server or not node.port:
        warnings.append(f"Node {node.name or index + 1} skipped: missing server or port")
        return None

    proxy: dict[str, Any] = {
        "name": node.name or f"node-{index + 1}",
        "type": node_type,
        "server": node.server,
        "port": int(node.port),
    }
    if node_type in {"vmess", "vless"}:
        if not node.uuid:
            warnings.append(f"Node {node.name or index + 1} skipped: missing UUID")
            return None
        proxy["uuid"] = node.uuid
        if node_type == "vmess":
            proxy["alterId"] = int(node.extra.get("alter_id", 0) if node.extra else 0)
            proxy["cipher"] = node.security or "auto"
        if node.flow:
            proxy["flow"] = node.flow
    elif node_type == "trojan":
        if not node.password:
            warnings.append(f"Node {node.name or index + 1} skipped: missing password")
            return None
        proxy["password"] = node.password
    elif node_type == "ss":
        if not node.method or not node.password:
            warnings.append(f"Node {node.name or index + 1} skipped: missing cipher or password")
            return None
        proxy["cipher"] = node.method
        proxy["password"] = node.password

    if node.tls:
        proxy["tls"] = True
    if node.sni:
        proxy["sni"] = node.sni
    network = (node.network or "tcp").lower()
    if network and network != "tcp":
        proxy["network"] = network
        if network == "ws":
            ws_opts: dict[str, Any] = {}
            if node.path:
                ws_opts["path"] = node.path
            if node.host:
                ws_opts["headers"] = {"Host": node.host}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
    return proxy
