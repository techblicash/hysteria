from __future__ import annotations

import base64
import json

from proxy_gui_client.core.node_parser import parse_share_links, parse_subscription_payload


def b64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def test_parse_vmess_link() -> None:
    payload = {
        "v": "2",
        "ps": "vmess-demo",
        "add": "vmess.example.com",
        "port": "443",
        "id": "11111111-1111-1111-1111-111111111111",
        "aid": "0",
        "net": "ws",
        "path": "/ws",
        "host": "cdn.example.com",
        "tls": "tls",
        "scy": "auto",
    }

    nodes = parse_share_links("vmess://" + b64(json.dumps(payload)))

    assert len(nodes) == 1
    node = nodes[0]
    assert node.type == "vmess"
    assert node.name == "vmess-demo"
    assert node.server == "vmess.example.com"
    assert node.port == 443
    assert node.uuid == "11111111-1111-1111-1111-111111111111"
    assert node.network == "ws"
    assert node.tls is True


def test_parse_vless_link() -> None:
    nodes = parse_share_links(
        "vless://22222222-2222-2222-2222-222222222222@vless.example.com:8443"
        "?security=tls&type=ws&path=%2Fedge&host=cdn.example.com&sni=sni.example.com#vless-demo"
    )

    assert len(nodes) == 1
    node = nodes[0]
    assert node.type == "vless"
    assert node.name == "vless-demo"
    assert node.server == "vless.example.com"
    assert node.port == 8443
    assert node.uuid == "22222222-2222-2222-2222-222222222222"
    assert node.path == "/edge"
    assert node.tls is True


def test_parse_trojan_link() -> None:
    nodes = parse_share_links(
        "trojan://secret-password@trojan.example.com:443?security=tls&sni=trojan.example.com#trojan-demo"
    )

    assert len(nodes) == 1
    node = nodes[0]
    assert node.type == "trojan"
    assert node.name == "trojan-demo"
    assert node.server == "trojan.example.com"
    assert node.password == "secret-password"
    assert node.tls is True


def test_parse_ss_link() -> None:
    encoded = b64("aes-256-gcm:secret@ss.example.com:8388")

    nodes = parse_share_links(f"ss://{encoded}#ss-demo")

    assert len(nodes) == 1
    node = nodes[0]
    assert node.type == "shadowsocks"
    assert node.name == "ss-demo"
    assert node.server == "ss.example.com"
    assert node.port == 8388
    assert node.method == "aes-256-gcm"
    assert node.password == "secret"


def test_parse_base64_subscription() -> None:
    body = "\n".join(
        [
            "trojan://secret@one.example.com:443#one",
            "ss://" + b64("aes-128-gcm:pass@two.example.com:8388") + "#two",
        ]
    )

    nodes = parse_subscription_payload(b64(body))

    assert [node.name for node in nodes] == ["one", "two"]


def test_invalid_links_do_not_crash() -> None:
    errors: list[str] = []

    nodes = parse_subscription_payload("vmess://not-base64\nnot-a-link\nvless://missing-port", errors=errors)

    assert nodes == []
    assert errors

