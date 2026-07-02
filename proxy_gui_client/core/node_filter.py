from __future__ import annotations

from dataclasses import dataclass

from proxy_gui_client.core.models import ProxyNode


@dataclass
class NodeFilterOptions:
    keyword: str = ""
    node_type: str = "all"
    source: str = "all"
    availability: str = "all"
    sort_by: str = "default"


def filter_and_sort_nodes(nodes: list[ProxyNode], options: NodeFilterOptions) -> list[tuple[int, ProxyNode]]:
    result = [(index, node) for index, node in enumerate(nodes) if _matches(node, options)]
    if options.sort_by == "name":
        result.sort(key=lambda item: _text(item[1].name))
    elif options.sort_by == "type":
        result.sort(key=lambda item: _type(item[1].type))
    elif options.sort_by == "tcp_latency":
        result.sort(key=lambda item: _latency_key(item[1].tcp_latency_ms))
    elif options.sort_by == "url_latency":
        result.sort(key=lambda item: _latency_key(item[1].url_latency_ms))
    elif options.sort_by == "source":
        result.sort(key=lambda item: source_category(item[1]))
    elif options.sort_by == "imported_at":
        result.sort(key=lambda item: item[1].imported_at or "")
    return result


def source_category(node: ProxyNode) -> str:
    source = _text(node.source)
    if not source or source == "manual":
        return "manual"
    if source == "config_file":
        return "config_file"
    if source == "unknown":
        return "unknown"
    return "subscription"


def _matches(node: ProxyNode, options: NodeFilterOptions) -> bool:
    keyword = _text(options.keyword)
    if keyword:
        haystack = " ".join(
            [
                node.name or "",
                node.server or "",
                node.type or "",
                node.source or "",
                node.source_file or "",
            ]
        ).lower()
        if keyword not in haystack:
            return False

    wanted_type = _type(options.node_type)
    if wanted_type != "all" and _type(node.type) != wanted_type:
        return False

    wanted_source = _text(options.source)
    if wanted_source != "all" and source_category(node) != wanted_source:
        return False

    availability = _text(options.availability)
    if availability != "all" and not _availability_matches(node, availability):
        return False
    return True


def _availability_matches(node: ProxyNode, availability: str) -> bool:
    status = _text(node.test_status)
    if availability == "tcp_available":
        return node.tcp_latency_ms is not None
    if availability == "url_available":
        return node.url_latency_ms is not None
    if availability == "failed":
        return "fail" in status or "失败" in status
    if availability == "untested":
        return node.tcp_latency_ms is None and node.url_latency_ms is None and not status
    return True


def _latency_key(value: int | None) -> tuple[int, int]:
    if value is None:
        return (1, 0)
    return (0, int(value))


def _type(value: str) -> str:
    normalized = _text(value)
    if normalized == "ss":
        return "shadowsocks"
    return normalized


def _text(value) -> str:
    return str(value or "").strip().lower()

