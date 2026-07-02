from __future__ import annotations

from typing import Any, Literal


RoutingMode = Literal["global", "rule", "direct"]

VALID_ROUTING_MODES = {"global", "rule", "direct"}

DEFAULT_DIRECT_DOMAIN_SUFFIXES = [
    "localhost",
    "local",
    "lan",
    "cn",
]

DEFAULT_DIRECT_IP_CIDRS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "::1/128",
    "fc00::/7",
]

DEFAULT_BLOCK_DOMAIN_SUFFIXES = [
    "doubleclick.net",
    "googlesyndication.com",
]


def normalize_routing_mode(value: Any) -> RoutingMode:
    mode = str(value or "global").strip().lower()
    return mode if mode in VALID_ROUTING_MODES else "global"  # type: ignore[return-value]


def build_singbox_route(settings: dict[str, Any]) -> dict[str, Any]:
    mode = normalize_routing_mode(settings.get("routing_mode", "global"))
    if mode == "direct":
        return {"final": "direct"}
    if mode == "global":
        return {"final": "proxy"}

    rules: list[dict[str, Any]] = []
    block_domains = _string_list(settings.get("rule_block_domain_suffixes"), DEFAULT_BLOCK_DOMAIN_SUFFIXES)
    direct_domains = _string_list(settings.get("rule_direct_domain_suffixes"), DEFAULT_DIRECT_DOMAIN_SUFFIXES)
    direct_ip_cidrs = _string_list(settings.get("rule_direct_ip_cidrs"), DEFAULT_DIRECT_IP_CIDRS)
    proxy_domains = _string_list(settings.get("rule_proxy_domain_suffixes"), [])

    if block_domains:
        rules.append({"domain_suffix": block_domains, "outbound": "block"})
    if direct_ip_cidrs:
        rules.append({"ip_cidr": direct_ip_cidrs, "outbound": "direct"})
    if direct_domains:
        rules.append({"domain_suffix": direct_domains, "outbound": "direct"})
    if proxy_domains:
        rules.append({"domain_suffix": proxy_domains, "outbound": "proxy"})
    return {"rules": rules, "final": "proxy"}


def _string_list(value: Any, default: list[str]) -> list[str]:
    raw = value if isinstance(value, list) else default
    items: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items
