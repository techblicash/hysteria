from __future__ import annotations

from proxy_gui_client.core.routing import build_singbox_route, normalize_routing_mode


def test_normalize_invalid_routing_mode_falls_back_to_global() -> None:
    assert normalize_routing_mode("bad") == "global"


def test_global_mode_routes_final_to_proxy() -> None:
    route = build_singbox_route({"routing_mode": "global"})

    assert route == {"final": "proxy"}


def test_direct_mode_routes_final_to_direct() -> None:
    route = build_singbox_route({"routing_mode": "direct"})

    assert route == {"final": "direct"}


def test_rule_mode_contains_direct_and_block_rules() -> None:
    route = build_singbox_route({"routing_mode": "rule"})

    assert route["final"] == "proxy"
    assert any(rule.get("outbound") == "direct" for rule in route["rules"])
    assert any(rule.get("outbound") == "block" for rule in route["rules"])


def test_rule_mode_supports_custom_proxy_domains() -> None:
    route = build_singbox_route({"routing_mode": "rule", "rule_proxy_domain_suffixes": ["example.com"]})

    assert {"domain_suffix": ["example.com"], "outbound": "proxy"} in route["rules"]
