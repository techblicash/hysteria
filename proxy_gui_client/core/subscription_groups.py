from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from proxy_gui_client.core.models import ProxyNode


def normalize_subscription_groups(settings: dict[str, Any]) -> list[dict[str, Any]]:
    raw_groups = settings.get("subscription_groups")
    groups: list[dict[str, Any]] = []
    if isinstance(raw_groups, list):
        for index, item in enumerate(raw_groups):
            if not isinstance(item, dict):
                continue
            group = _normalize_group(item, index)
            if group["url"]:
                groups.append(group)

    legacy_url = str(settings.get("subscription_url", "") or "").strip()
    if legacy_url and not any(group["url"] == legacy_url for group in groups):
        groups.append(
            {
                "id": "legacy",
                "name": "默认订阅",
                "url": legacy_url,
                "enabled": True,
            }
        )
    return groups


def ensure_subscription_group_settings(settings: dict[str, Any]) -> dict[str, Any]:
    updated = dict(settings)
    groups = normalize_subscription_groups(updated)
    updated["subscription_groups"] = groups
    if groups and not str(updated.get("subscription_url", "") or "").strip():
        updated["subscription_url"] = groups[0]["url"]
    return updated


def subscription_source(group: dict[str, Any]) -> str:
    return f"subscription:{group.get('id') or group.get('url') or 'unknown'}"


def stamp_subscription_nodes(nodes: list[ProxyNode], group: dict[str, Any]) -> list[ProxyNode]:
    stamped: list[ProxyNode] = []
    source = subscription_source(group)
    source_file = str(group.get("name") or group.get("url") or "subscription")
    for node in nodes:
        data = node.to_dict()
        data.update({"source": source, "source_file": source_file})
        stamped.append(ProxyNode.from_dict(data))
    return stamped


def enabled_subscription_groups(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(group) for group in normalize_subscription_groups(settings) if group.get("enabled", True)]


def _normalize_group(item: dict[str, Any], index: int) -> dict[str, Any]:
    group_id = str(item.get("id") or uuid4())
    url = str(item.get("url") or "").strip()
    name = str(item.get("name") or "").strip() or f"订阅 {index + 1}"
    return {
        "id": group_id,
        "name": name,
        "url": url,
        "enabled": bool(item.get("enabled", True)),
    }
