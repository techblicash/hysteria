from __future__ import annotations

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.subscription_groups import (
    enabled_subscription_groups,
    ensure_subscription_group_settings,
    normalize_subscription_groups,
    stamp_subscription_nodes,
    subscription_source,
)


def test_legacy_subscription_url_migrates_to_group() -> None:
    groups = normalize_subscription_groups({"subscription_url": "https://sub.example/a"})

    assert len(groups) == 1
    assert groups[0]["name"] == "默认订阅"
    assert groups[0]["url"] == "https://sub.example/a"
    assert groups[0]["enabled"] is True


def test_multiple_subscription_groups_are_preserved() -> None:
    settings = {
        "subscription_groups": [
            {"id": "a", "name": "A", "url": "https://a.example", "enabled": True},
            {"id": "b", "name": "B", "url": "https://b.example", "enabled": False},
        ]
    }

    groups = normalize_subscription_groups(settings)

    assert [group["id"] for group in groups] == ["a", "b"]
    assert enabled_subscription_groups(settings)[0]["id"] == "a"


def test_empty_subscription_group_urls_are_skipped() -> None:
    groups = normalize_subscription_groups({"subscription_groups": [{"name": "empty", "url": ""}]})

    assert groups == []


def test_ensure_settings_keeps_legacy_url_compatible() -> None:
    settings = ensure_subscription_group_settings({"subscription_groups": [{"id": "a", "name": "A", "url": "https://a.example"}]})

    assert settings["subscription_url"] == "https://a.example"


def test_stamp_subscription_nodes_sets_group_source() -> None:
    group = {"id": "a", "name": "A", "url": "https://a.example", "enabled": True}
    node = ProxyNode(name="n", type="trojan", server="example.com", port=443, password="p")

    stamped = stamp_subscription_nodes([node], group)

    assert stamped[0].source == subscription_source(group)
    assert stamped[0].source_file == "A"
