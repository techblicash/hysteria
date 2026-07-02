from __future__ import annotations

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_dedup import find_duplicate_nodes, find_duplicate_nodes_inside, node_identity


def node(**kwargs) -> ProxyNode:
    data = {
        "name": "n",
        "type": "vless",
        "server": "Example.COM ",
        "port": 443,
        "uuid": "11111111-1111-1111-1111-111111111111",
        "network": "WS",
        "tls": True,
        "sni": "SNI.EXAMPLE.COM ",
    }
    data.update(kwargs)
    return ProxyNode(**data)


def test_same_core_fields_are_duplicate() -> None:
    existing = [node()]
    imported = [node(name="other")]

    assert find_duplicate_nodes(imported, existing) == {0: 0}


def test_different_names_same_core_fields_are_duplicate() -> None:
    assert node_identity(node(name="a")) == node_identity(node(name="b"))


def test_same_name_different_server_is_not_duplicate() -> None:
    existing = [node(name="same", server="a.example.com")]
    imported = [node(name="same", server="b.example.com")]

    assert find_duplicate_nodes(imported, existing) == {}


def test_ss_and_shadowsocks_are_same_type() -> None:
    ss = ProxyNode(name="a", type="ss", server="example.com", port=8388, password="p", network="tcp")
    shadowsocks = ProxyNode(name="b", type="shadowsocks", server="example.com", port=8388, password="p", network="tcp")

    assert node_identity(ss) == node_identity(shadowsocks)


def test_empty_fields_do_not_raise() -> None:
    identity = node_identity(ProxyNode(name="", type="", server="", port=0))

    assert isinstance(identity, str)


def test_duplicate_inside_import_file_is_detected() -> None:
    nodes = [node(name="first"), node(name="second"), node(name="third", server="different.example.com")]

    assert find_duplicate_nodes_inside(nodes) == {1: 0}

