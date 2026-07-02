from __future__ import annotations

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_cleanup import (
    delete_nodes_by_indexes,
    duplicate_indexes_to_delete,
    find_duplicate_groups,
    find_unavailable_node_indexes,
    is_unavailable_node,
)


def node(name: str, server: str = "example.com", password: str = "p") -> ProxyNode:
    return ProxyNode(name=name, type="trojan", server=server, port=443, password=password)


def test_identifies_failed_node() -> None:
    failed = node("failed")
    failed.test_status = "URL 失败：请求超时"

    assert is_unavailable_node(failed) is True


def test_untested_node_is_not_unavailable() -> None:
    untested = node("untested")

    assert is_unavailable_node(untested) is False


def test_identifies_duplicate_groups() -> None:
    nodes = [node("a"), node("b"), node("c", server="c.example.com")]

    groups = find_duplicate_groups(nodes)

    assert len(groups) == 1
    assert groups[0].keep_index == 0
    assert groups[0].duplicate_indexes == [1]


def test_duplicate_cleanup_keeps_first_by_default() -> None:
    nodes = [node("first"), node("second"), node("other", server="other.example.com")]
    groups = find_duplicate_groups(nodes)

    indexes = duplicate_indexes_to_delete(groups)
    cleaned = delete_nodes_by_indexes(nodes, indexes)

    assert [item.name for item in cleaned] == ["first", "other"]


def test_delete_uses_original_indexes_not_display_order() -> None:
    nodes = [node("zero"), node("one"), node("two")]

    cleaned = delete_nodes_by_indexes(nodes, [2, 0])

    assert [item.name for item in cleaned] == ["one"]


def test_cleanup_count_after_unavailable_delete() -> None:
    nodes = [node("ok"), node("failed"), node("untested")]
    nodes[1].test_status = "TCP failed"
    indexes = find_unavailable_node_indexes(nodes)

    cleaned = delete_nodes_by_indexes(nodes, indexes)

    assert len(cleaned) == 2
    assert [item.name for item in cleaned] == ["ok", "untested"]
