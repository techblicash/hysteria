from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from proxy_gui_client.core.models import ProxyNode


SUPPORTED_TYPES = {"vmess", "vless", "trojan", "ss", "shadowsocks"}
NON_NODE_OUTBOUNDS = {"direct", "block", "dns", "selector", "urltest", "url-test", "wireguard", "hysteria", "hysteria2"}


@dataclass
class ImportResult:
    nodes: list[ProxyNode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def import_config_file(path: str) -> ImportResult:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return import_clash_yaml(path)
    if suffix == ".json":
        return import_singbox_json(path)

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return ImportResult(errors=[f"Failed to read config file: {exc}"])
    stripped = content.lstrip()
    if stripped.startswith("{"):
        return _import_singbox_json_text(content, str(file_path))
    return _import_clash_yaml_text(content, str(file_path))


def import_clash_yaml(path: str) -> ImportResult:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        return ImportResult(errors=[f"Failed to read Clash YAML: {exc}"])
    return _import_clash_yaml_text(content, path)


def import_singbox_json(path: str) -> ImportResult:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        return ImportResult(errors=[f"Failed to read sing-box JSON: {exc}"])
    return _import_singbox_json_text(content, path)


def _import_clash_yaml_text(content: str, source: str) -> ImportResult:
    result = ImportResult()
    try:
        data = yaml.safe_load(content)
    except Exception as exc:
        return ImportResult(errors=[f"Invalid Clash YAML: {exc}"])
    if not isinstance(data, dict):
        return ImportResult(errors=["Invalid Clash YAML: top-level document must be a mapping"])
    proxies = data.get("proxies")
    if not isinstance(proxies, list):
        return ImportResult(errors=["Invalid Clash YAML: missing proxies list"])

    for index, item in enumerate(proxies):
        if not isinstance(item, dict):
            result.warnings.append(f"Clash proxy #{index + 1} skipped: item is not a mapping")
            continue
        node = _clash_proxy_to_node(item, source, result.warnings, index)
        if node:
            result.nodes.append(node)
    return result


def _import_singbox_json_text(content: str, source: str) -> ImportResult:
    result = ImportResult()
    try:
        data = json.loads(content)
    except Exception as exc:
        return ImportResult(errors=[f"Invalid sing-box JSON: {exc}"])
    if not isinstance(data, dict):
        return ImportResult(errors=["Invalid sing-box JSON: top-level document must be an object"])
    outbounds = data.get("outbounds")
    if not isinstance(outbounds, list):
        return ImportResult(errors=["Invalid sing-box JSON: missing outbounds list"])

    for index, item in enumerate(outbounds):
        if not isinstance(item, dict):
            result.warnings.append(f"sing-box outbound #{index + 1} skipped: item is not an object")
            continue
        node = _singbox_outbound_to_node(item, source, result.warnings, index)
        if node:
            result.nodes.append(node)
    return result


def _clash_proxy_to_node(item: dict[str, Any], source: str, warnings: list[str], index: int) -> ProxyNode | None:
    raw_type = str(item.get("type", "")).lower()
    node_type = _normalize_type(raw_type)
    name = str(item.get("name") or f"clash-node-{index + 1}")
    if node_type not in SUPPORTED_TYPES:
        warnings.append(f"Clash proxy {name} skipped: unsupported type {raw_type or '<missing>'}")
        return None

    server = str(item.get("server") or "")
    port = _safe_int(item.get("port"))
    if not server or not port:
        warnings.append(f"Clash proxy {name} skipped: missing server or port")
        return None

    uuid = str(item.get("uuid") or item.get("id") or "")
    password = str(item.get("password") or "")
    method = str(item.get("cipher") or item.get("method") or "")
    if node_type in {"vmess", "vless"} and not uuid:
        warnings.append(f"Clash proxy {name} skipped: missing UUID")
        return None
    if node_type == "trojan" and not password:
        warnings.append(f"Clash proxy {name} skipped: missing password")
        return None
    if node_type == "shadowsocks" and (not method or not password):
        warnings.append(f"Clash proxy {name} skipped: missing cipher or password")
        return None

    network = str(item.get("network") or "tcp")
    ws_opts = item.get("ws-opts") if isinstance(item.get("ws-opts"), dict) else {}
    ws_headers = ws_opts.get("headers") if isinstance(ws_opts.get("headers"), dict) else {}
    grpc_opts = item.get("grpc-opts") if isinstance(item.get("grpc-opts"), dict) else {}
    tls = bool(item.get("tls") or item.get("skip-cert-verify") or item.get("sni"))
    return ProxyNode(
        name=name,
        type=node_type,
        server=server,
        port=port,
        uuid=uuid,
        password=password,
        method=method,
        security=str(item.get("cipher") or item.get("security") or "auto") if node_type == "vmess" else str(item.get("security") or ""),
        network=network,
        path=str(ws_opts.get("path") or item.get("path") or ""),
        host=str(ws_headers.get("Host") or ws_headers.get("host") or item.get("servername") or ""),
        sni=str(item.get("sni") or item.get("servername") or ""),
        tls=tls,
        flow=str(item.get("flow") or ""),
        source=source,
        extra={
            "import_format": "clash",
            "alter_id": int(item.get("alterId") or item.get("alter-id") or 0),
            "udp": bool(item.get("udp", False)),
            "grpc_service_name": grpc_opts.get("grpc-service-name") if isinstance(grpc_opts, dict) else "",
        },
    )


def _singbox_outbound_to_node(item: dict[str, Any], source: str, warnings: list[str], index: int) -> ProxyNode | None:
    raw_type = str(item.get("type", "")).lower()
    if raw_type in NON_NODE_OUTBOUNDS:
        warnings.append(f"sing-box outbound {item.get('tag') or index + 1} skipped: non-node outbound {raw_type}")
        return None
    node_type = _normalize_type(raw_type)
    name = str(item.get("tag") or f"sing-box-node-{index + 1}")
    if node_type not in SUPPORTED_TYPES:
        warnings.append(f"sing-box outbound {name} skipped: unsupported type {raw_type or '<missing>'}")
        return None

    server = str(item.get("server") or "")
    port = _safe_int(item.get("server_port") or item.get("server-port") or item.get("port"))
    if not server or not port:
        warnings.append(f"sing-box outbound {name} skipped: missing server or server_port")
        return None

    uuid = str(item.get("uuid") or "")
    password = str(item.get("password") or "")
    method = str(item.get("method") or "")
    if node_type in {"vmess", "vless"} and not uuid:
        warnings.append(f"sing-box outbound {name} skipped: missing UUID")
        return None
    if node_type == "trojan" and not password:
        warnings.append(f"sing-box outbound {name} skipped: missing password")
        return None
    if node_type == "shadowsocks" and (not method or not password):
        warnings.append(f"sing-box outbound {name} skipped: missing method or password")
        return None

    tls_obj = item.get("tls") if isinstance(item.get("tls"), dict) else {}
    transport = item.get("transport") if isinstance(item.get("transport"), dict) else {}
    headers = transport.get("headers") if isinstance(transport.get("headers"), dict) else {}
    return ProxyNode(
        name=name,
        type=node_type,
        server=server,
        port=port,
        uuid=uuid,
        password=password,
        method=method,
        security=str(item.get("security") or ""),
        network=str(transport.get("type") or "tcp"),
        path=str(transport.get("path") or ""),
        host=str(headers.get("Host") or headers.get("host") or ""),
        sni=str(tls_obj.get("server_name") or tls_obj.get("server-name") or ""),
        tls=bool(tls_obj.get("enabled", False)),
        flow=str(item.get("flow") or ""),
        source=source,
        extra={"import_format": "sing-box", "raw_type": raw_type},
    )


def _normalize_type(node_type: str) -> str:
    normalized = node_type.lower()
    if normalized == "ss":
        return "shadowsocks"
    return normalized


def _safe_int(value: Any) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return 0
    if 1 <= port <= 65535:
        return port
    return 0
