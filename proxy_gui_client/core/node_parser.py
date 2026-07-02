from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, unquote, urlparse

from .models import ProxyNode


class NodeParseError(ValueError):
    pass


def _decode_base64(value: str) -> str:
    cleaned = value.strip().replace("\n", "").replace("\r", "")
    padding = "=" * (-len(cleaned) % 4)
    return base64.urlsafe_b64decode((cleaned + padding).encode("utf-8")).decode("utf-8")


def parse_share_links(text: str, source: str = "subscription", errors: list[str] | None = None) -> list[ProxyNode]:
    nodes: list[ProxyNode] = []
    for raw_line in text.replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        try:
            if line.startswith("vmess://"):
                nodes.append(_parse_vmess(line, source))
            elif line.startswith("vless://"):
                nodes.append(_parse_vless(line, source))
            elif line.startswith("trojan://"):
                nodes.append(_parse_trojan(line, source))
            elif line.startswith("ss://"):
                nodes.append(_parse_ss(line, source))
        except Exception as exc:
            if errors is not None:
                errors.append(f"{line[:80]}: {exc}")
    return nodes


def parse_subscription_payload(payload: str, source: str = "subscription", errors: list[str] | None = None) -> list[ProxyNode]:
    direct_nodes = parse_share_links(payload, source, errors)
    if direct_nodes:
        return direct_nodes
    try:
        decoded = _decode_base64(payload)
    except Exception as exc:
        if errors is not None:
            errors.append(f"Base64 decode failed: {exc}")
        return []
    return parse_share_links(decoded, source, errors)


def _query(parsed) -> dict[str, str]:
    return {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}


def _name_from_fragment(parsed, fallback: str) -> str:
    return unquote(parsed.fragment) if parsed.fragment else fallback


def _parse_vmess(link: str, source: str) -> ProxyNode:
    try:
        data = json.loads(_decode_base64(link.removeprefix("vmess://")))
    except Exception as exc:
        raise NodeParseError(f"invalid vmess payload: {exc}") from exc
    network = data.get("net") or "tcp"
    return ProxyNode(
        name=data.get("ps") or data.get("add") or "vmess",
        type="vmess",
        server=data.get("add") or "",
        port=int(data.get("port") or 0),
        uuid=data.get("id") or "",
        security=data.get("scy") or data.get("security") or "auto",
        network=network,
        path=data.get("path") or "",
        host=data.get("host") or "",
        sni=data.get("sni") or data.get("host") or "",
        tls=str(data.get("tls") or "").lower() in {"tls", "true", "1"},
        source=source,
        extra={"alter_id": int(data.get("aid") or 0)},
    )


def _parse_vless(link: str, source: str) -> ProxyNode:
    parsed = urlparse(link)
    query = _query(parsed)
    _require_host_port(parsed, "vless")
    security = query.get("security", "")
    network = query.get("type", "tcp")
    return ProxyNode(
        name=_name_from_fragment(parsed, parsed.hostname or "vless"),
        type="vless",
        server=parsed.hostname or "",
        port=int(parsed.port or 0),
        uuid=unquote(parsed.username or ""),
        security=security,
        network=network,
        path=unquote(query.get("path", "")),
        host=query.get("host", ""),
        sni=query.get("sni", ""),
        tls=security == "tls",
        flow=query.get("flow", ""),
        source=source,
        extra=query,
    )


def _parse_trojan(link: str, source: str) -> ProxyNode:
    parsed = urlparse(link)
    query = _query(parsed)
    _require_host_port(parsed, "trojan")
    security = query.get("security", "tls")
    return ProxyNode(
        name=_name_from_fragment(parsed, parsed.hostname or "trojan"),
        type="trojan",
        server=parsed.hostname or "",
        port=int(parsed.port or 0),
        password=unquote(parsed.username or ""),
        security=security,
        network=query.get("type", "tcp"),
        path=unquote(query.get("path", "")),
        host=query.get("host", ""),
        sni=query.get("sni", ""),
        tls=security != "none",
        source=source,
        extra=query,
    )


def _parse_ss(link: str, source: str) -> ProxyNode:
    body = link.removeprefix("ss://")
    name = "shadowsocks"
    if "#" in body:
        body, fragment = body.split("#", 1)
        name = unquote(fragment) or name

    plugin = ""
    if "?" in body:
        body, query_string = body.split("?", 1)
        query = parse_qs(query_string)
        plugin = query.get("plugin", [""])[-1]

    parsed = urlparse("ss://" + body)
    if parsed.hostname and parsed.username:
        server = parsed.hostname
        port = int(parsed.port or 0)
        if parsed.password is not None:
            method = unquote(parsed.username)
            password = unquote(parsed.password)
        else:
            credentials = _decode_base64(unquote(parsed.username))
            method, password = credentials.split(":", 1)
    else:
        try:
            decoded = _decode_base64(body)
            credentials, server_part = decoded.rsplit("@", 1)
            method, password = credentials.split(":", 1)
            server, port_text = server_part.rsplit(":", 1)
            port = int(port_text)
        except Exception as exc:
            raise NodeParseError(f"invalid shadowsocks payload: {exc}") from exc

    return ProxyNode(
        name=name,
        type="shadowsocks",
        server=server,
        port=port,
        method=method,
        password=password,
        source=source,
        extra={"plugin": plugin} if plugin else {},
    )


def _require_host_port(parsed, scheme: str) -> None:
    if not parsed.hostname:
        raise NodeParseError(f"{scheme} link is missing server")
    try:
        if not parsed.port:
            raise NodeParseError(f"{scheme} link is missing port")
    except ValueError as exc:
        raise NodeParseError(f"{scheme} link has invalid port") from exc
