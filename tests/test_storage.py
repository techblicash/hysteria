from __future__ import annotations

import json

from proxy_gui_client.core.models import DEFAULT_SETTINGS, ProxyNode
from proxy_gui_client.core.storage import (
    ensure_app_dirs,
    load_nodes,
    load_settings,
    nodes_file,
    save_nodes,
    save_settings,
    settings_file,
)


def test_missing_files_are_created(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))

    ensure_app_dirs()

    assert nodes_file().exists()
    assert settings_file().exists()
    assert json.loads(nodes_file().read_text(encoding="utf-8")) == []
    assert load_settings()["http_port"] == DEFAULT_SETTINGS["http_port"]


def test_settings_read_write(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))

    save_settings({"core_path": r"C:\Tools\sing-box\sing-box.exe", "http_port": 18080, "socks_port": 18081})
    settings = load_settings()

    assert settings["core_path"] == r"C:\Tools\sing-box\sing-box.exe"
    assert settings["http_port"] == 18080
    assert settings["socks_port"] == 18081
    assert "subscription_url" in settings


def test_nodes_read_write(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")

    save_nodes([node])
    loaded = load_nodes()

    assert len(loaded) == 1
    assert loaded[0].id == node.id
    assert loaded[0].name == "demo"
    assert loaded[0].password == "p"

