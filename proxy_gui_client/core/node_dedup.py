from __future__ import annotations

from proxy_gui_client.core.models import ProxyNode


def node_identity(node: ProxyNode) -> str:
    """Return a stable identity based on connection parameters, not display name."""

    node_type = _normalize_type(node.type)
    credential = _normalize_text(node.uuid) or _normalize_text(node.password)
    parts = [
        node_type,
        _normalize_text(node.server),
        str(_normalize_port(node.port)),
        credential,
        _normalize_text(node.network or "tcp"),
        "tls" if bool(node.tls) else "notls",
        _normalize_text(node.sni),
    ]
    return "|".join(parts)


def find_duplicate_nodes(imported_nodes: list[ProxyNode], existing_nodes: list[ProxyNode]) -> dict[int, int]:
    existing_by_identity: dict[str, int] = {}
    for index, node in enumerate(existing_nodes):
        identity = node_identity(node)
        if identity not in existing_by_identity:
            existing_by_identity[identity] = index

    duplicates: dict[int, int] = {}
    for imported_index, node in enumerate(imported_nodes):
        existing_index = existing_by_identity.get(node_identity(node))
        if existing_index is not None:
            duplicates[imported_index] = existing_index
    return duplicates


def find_duplicate_nodes_inside(nodes: list[ProxyNode]) -> dict[int, int]:
    first_seen: dict[str, int] = {}
    duplicates: dict[int, int] = {}
    for index, node in enumerate(nodes):
        identity = node_identity(node)
        if identity in first_seen:
            duplicates[index] = first_seen[identity]
        else:
            first_seen[identity] = index
    return duplicates


def _normalize_type(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized == "ss":
        return "shadowsocks"
    return normalized


def _normalize_text(value) -> str:
    return str(value or "").strip().lower()


def _normalize_port(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

