from __future__ import annotations

from dataclasses import dataclass, field

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_dedup import node_identity


@dataclass
class DuplicateGroup:
    identity: str
    keep_index: int
    duplicate_indexes: list[int] = field(default_factory=list)


def is_unavailable_node(node: ProxyNode) -> bool:
    status = str(node.test_status or "").strip().lower()
    if "失败" in status or "failed" in status:
        return True
    if node.last_tested_at and node.tcp_latency_ms is None and node.url_latency_ms is None:
        return True
    return False


def find_unavailable_node_indexes(nodes: list[ProxyNode], candidate_indexes: list[int] | None = None) -> list[int]:
    indexes = candidate_indexes if candidate_indexes is not None else list(range(len(nodes)))
    return [index for index in indexes if 0 <= index < len(nodes) and is_unavailable_node(nodes[index])]


def find_duplicate_groups(nodes: list[ProxyNode], candidate_indexes: list[int] | None = None) -> list[DuplicateGroup]:
    indexes = candidate_indexes if candidate_indexes is not None else list(range(len(nodes)))
    first_seen: dict[str, int] = {}
    groups: dict[str, DuplicateGroup] = {}
    for index in indexes:
        if index < 0 or index >= len(nodes):
            continue
        identity = node_identity(nodes[index])
        if identity in first_seen:
            group = groups.setdefault(identity, DuplicateGroup(identity=identity, keep_index=first_seen[identity]))
            group.duplicate_indexes.append(index)
        else:
            first_seen[identity] = index
    return list(groups.values())


def duplicate_indexes_to_delete(groups: list[DuplicateGroup]) -> list[int]:
    indexes: list[int] = []
    for group in groups:
        indexes.extend(group.duplicate_indexes)
    return sorted(set(indexes))


def delete_nodes_by_indexes(nodes: list[ProxyNode], indexes: list[int]) -> list[ProxyNode]:
    updated = list(nodes)
    for index in sorted({index for index in indexes if 0 <= index < len(updated)}, reverse=True):
        del updated[index]
    return updated
