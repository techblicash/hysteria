from __future__ import annotations

import json

from proxy_gui_client.core.storage import load_settings, settings_file


def test_old_settings_are_migrated_with_new_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))
    settings_file().parent.mkdir(parents=True, exist_ok=True)
    settings_file().write_text(json.dumps({"core_path": "old.exe", "http_port": 18080}), encoding="utf-8")

    settings = load_settings()

    assert settings["core_type"] == "sing-box"
    assert settings["core_path"] == "old.exe"
    assert settings["http_port"] == 18080
    assert settings["latency_test_url"] == "https://www.gstatic.com/generate_204"
    assert settings["latency_timeout"] == 5
    assert settings["subscription_groups"] == []
    assert settings["routing_mode"] == "global"
    assert "cn" in settings["rule_direct_domain_suffixes"]
    assert settings["rule_proxy_domain_suffixes"] == []
    assert settings["rule_block_domain_suffixes"]
    assert settings["minimize_to_tray"] is True
    assert settings["close_to_tray"] is True
    assert settings["start_minimized"] is False
    assert settings["autostart_enabled"] is False
    assert settings["auto_connect_on_start"] is False
    assert settings["last_selected_node_identity"] == ""
    assert settings["last_selected_node_name"] == ""
    assert settings["tray_show_notifications"] is True
    assert settings["recent_node_identities"] == []
    assert settings["update_check_enabled"] is False
    assert settings["update_check_url"] == ""


def test_legacy_subscription_url_migrates_to_subscription_group(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))
    settings_file().parent.mkdir(parents=True, exist_ok=True)
    settings_file().write_text(json.dumps({"subscription_url": "https://sub.example/list"}), encoding="utf-8")

    settings = load_settings()

    assert settings["subscription_groups"][0]["url"] == "https://sub.example/list"
    assert settings["subscription_groups"][0]["name"] == "默认订阅"
