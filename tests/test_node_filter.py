from __future__ import annotations

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_filter import NodeFilterOptions, filter_and_sort_nodes
from proxy_gui_client.core.table_preferences import normalize_filter_preferences


def node(**kwargs) -> ProxyNode:
    data = {"name": "", "type": "trojan", "server": "", "port": 443, "password": "p"}
    data.update(kwargs)
    return ProxyNode(**data)


def names(result):
    return [item.name for _, item in result]


def test_keyword_searches_name() -> None:
    nodes = [node(name="Hong Kong", server="a.com"), node(name="Singapore", server="b.com")]

    result = filter_and_sort_nodes(nodes, NodeFilterOptions(keyword="hong"))

    assert names(result) == ["Hong Kong"]


def test_keyword_searches_server() -> None:
    nodes = [node(name="A", server="hk.example.com"), node(name="B", server="sg.example.com")]

    result = filter_and_sort_nodes(nodes, NodeFilterOptions(keyword="sg.example"))

    assert names(result) == ["B"]


def test_filter_by_type() -> None:
    nodes = [node(name="A", type="vmess", uuid="u"), node(name="B", type="trojan")]

    result = filter_and_sort_nodes(nodes, NodeFilterOptions(node_type="vmess"))

    assert names(result) == ["A"]


def test_filter_by_source() -> None:
    nodes = [node(name="A", source="manual"), node(name="B", source="config_file"), node(name="C", source="https://sub.example")]

    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(source="config_file"))) == ["B"]
    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(source="subscription"))) == ["C"]


def test_filter_by_availability() -> None:
    nodes = [
        node(name="tcp", tcp_latency_ms=10),
        node(name="url", url_latency_ms=20),
        node(name="failed", test_status="TCP failed"),
        node(name="untested"),
    ]

    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(availability="tcp_available"))) == ["tcp"]
    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(availability="url_available"))) == ["url"]
    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(availability="failed"))) == ["failed"]
    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(availability="untested"))) == ["untested"]


def test_sort_by_tcp_latency() -> None:
    nodes = [node(name="slow", tcp_latency_ms=100), node(name="none"), node(name="fast", tcp_latency_ms=10)]

    result = filter_and_sort_nodes(nodes, NodeFilterOptions(sort_by="tcp_latency"))

    assert names(result) == ["fast", "slow", "none"]


def test_sort_by_url_latency() -> None:
    nodes = [node(name="slow", url_latency_ms=100), node(name="fast", url_latency_ms=5)]

    result = filter_and_sort_nodes(nodes, NodeFilterOptions(sort_by="url_latency"))

    assert names(result) == ["fast", "slow"]


def test_result_preserves_original_index() -> None:
    nodes = [node(name="A"), node(name="B", server="target")]

    result = filter_and_sort_nodes(nodes, NodeFilterOptions(keyword="target"))

    assert result[0][0] == 1


def test_empty_fields_do_not_raise() -> None:
    result = filter_and_sort_nodes([ProxyNode(name="", type="", server="", port=0)], NodeFilterOptions(keyword=""))

    assert len(result) == 1


def test_restored_filter_preferences_can_be_used_for_filtering() -> None:
    preferences = normalize_filter_preferences(
        {"node_filter_preferences": {"keyword": "hk", "node_type": "trojan", "source": "manual", "availability": "all", "sort_by": "name"}}
    )
    options = NodeFilterOptions(
        keyword=preferences["keyword"],
        node_type=preferences["node_type"],
        source=preferences["source"],
        availability=preferences["availability"],
        sort_by=preferences["sort_by"],
    )
    nodes = [node(name="HK 2"), node(name="SG"), node(name="HK 1")]

    assert names(filter_and_sort_nodes(nodes, options)) == ["HK 1", "HK 2"]


def test_empty_keyword_does_not_filter() -> None:
    nodes = [node(name="A"), node(name="B")]

    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(keyword=""))) == ["A", "B"]


def test_invalid_sort_by_keeps_default_order() -> None:
    nodes = [node(name="B"), node(name="A")]

    assert names(filter_and_sort_nodes(nodes, NodeFilterOptions(sort_by="bad"))) == ["B", "A"]
