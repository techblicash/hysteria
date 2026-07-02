from __future__ import annotations

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_batch_ops import BatchEditOptions, apply_batch_edit


def node(name: str = "node") -> ProxyNode:
    return ProxyNode(
        name=name,
        type="trojan",
        server="example.com",
        port=443,
        password="p",
        source="manual",
        source_file="old.yaml",
        tcp_latency_ms=10,
        url_latency_ms=20,
        test_status="URL OK",
        last_tested_at="2026-01-01T00:00:00+00:00",
    )


def test_batch_modify_source() -> None:
    result = apply_batch_edit([node()], [0], BatchEditOptions(source="config_file"))

    assert result.nodes[0].source == "config_file"
    assert result.updated_count == 1


def test_batch_modify_source_file() -> None:
    result = apply_batch_edit([node()], [0], BatchEditOptions(source_file_action="set", source_file_value="new.yaml"))

    assert result.nodes[0].source_file == "new.yaml"


def test_batch_add_name_prefix() -> None:
    result = apply_batch_edit([node("A")], [0], BatchEditOptions(name_prefix="[HK] "))

    assert result.nodes[0].name == "[HK] A"


def test_batch_add_name_suffix() -> None:
    result = apply_batch_edit([node("A")], [0], BatchEditOptions(name_suffix=" - backup"))

    assert result.nodes[0].name == "A - backup"


def test_batch_clear_test_results() -> None:
    result = apply_batch_edit([node()], [0], BatchEditOptions(clear_test_results=True))

    updated = result.nodes[0]
    assert updated.tcp_latency_ms is None
    assert updated.url_latency_ms is None
    assert updated.test_status == ""
    assert updated.last_tested_at == ""


def test_unchecked_fields_are_not_modified() -> None:
    original = node("A")
    before = original.to_dict()
    result = apply_batch_edit([original], [0], BatchEditOptions())

    assert result.nodes[0].to_dict() == before
    assert result.updated_count == 0


def test_empty_selection_does_not_modify_nodes() -> None:
    nodes = [node("A")]

    result = apply_batch_edit(nodes, [], BatchEditOptions(source="unknown"))

    assert result.nodes == nodes
    assert result.updated_count == 0
