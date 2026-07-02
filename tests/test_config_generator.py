from __future__ import annotations

import json

import pytest

from proxy_gui_client.core.config_generator import ConfigGenerationError, generate_sing_box_config
from proxy_gui_client.core.models import ProxyNode


def base_settings() -> dict:
    return {"http_port": 7890, "socks_port": 7891}


def nodes_by_type() -> list[ProxyNode]:
    return [
        ProxyNode(name="vmess", type="vmess", server="vmess.example.com", port=443, uuid="u", security="auto"),
        ProxyNode(name="vless", type="vless", server="vless.example.com", port=443, uuid="u", security="tls", tls=True),
        ProxyNode(name="trojan", type="trojan", server="trojan.example.com", port=443, password="p", tls=True),
        ProxyNode(name="ss", type="shadowsocks", server="ss.example.com", port=8388, method="aes-256-gcm", password="p"),
    ]


def test_generated_config_is_json_serializable() -> None:
    config = generate_sing_box_config(nodes_by_type()[0], base_settings())

    encoded = json.dumps(config)

    assert json.loads(encoded)["route"]["final"] == "proxy"


def test_rule_mode_generates_route_rules() -> None:
    config = generate_sing_box_config(nodes_by_type()[0], {**base_settings(), "routing_mode": "rule"})

    assert config["route"]["final"] == "proxy"
    assert config["route"]["rules"]


def test_direct_mode_generates_direct_final_route() -> None:
    config = generate_sing_box_config(nodes_by_type()[0], {**base_settings(), "routing_mode": "direct"})

    assert config["route"]["final"] == "direct"


def test_http_and_socks_inbounds_exist() -> None:
    config = generate_sing_box_config(nodes_by_type()[0], base_settings())
    inbounds = {item["type"]: item for item in config["inbounds"]}

    assert inbounds["http"]["listen"] == "127.0.0.1"
    assert inbounds["http"]["listen_port"] == 7890
    assert inbounds["socks"]["listen"] == "127.0.0.1"
    assert inbounds["socks"]["listen_port"] == 7891


@pytest.mark.parametrize("node", nodes_by_type())
def test_different_protocols_generate_outbound(node: ProxyNode) -> None:
    config = generate_sing_box_config(node, base_settings())

    outbound = config["outbounds"][0]

    assert outbound["tag"] == "proxy"
    assert outbound["type"] == node.type
    assert outbound["server"] == node.server
    assert outbound["server_port"] == node.port


@pytest.mark.parametrize(
    "node, message",
    [
        (ProxyNode(name="bad", type="vmess", server="", port=443, uuid="u"), "服务器地址"),
        (ProxyNode(name="bad", type="vmess", server="example.com", port=443), "UUID"),
        (ProxyNode(name="bad", type="trojan", server="example.com", port=443), "密码"),
        (ProxyNode(name="bad", type="shadowsocks", server="example.com", port=8388, method="aes-256-gcm"), "加密方法或密码"),
    ],
)
def test_missing_required_fields_raise_clear_error(node: ProxyNode, message: str) -> None:
    with pytest.raises(ConfigGenerationError, match=message):
        generate_sing_box_config(node, base_settings())


def test_duplicate_inbound_ports_raise_clear_error() -> None:
    with pytest.raises(ConfigGenerationError, match="不能相同"):
        generate_sing_box_config(nodes_by_type()[0], {"http_port": 7890, "socks_port": 7890})
