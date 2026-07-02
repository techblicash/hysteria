from __future__ import annotations

import json

import pytest
import yaml

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_exporter import (
    export_nodes_clash_yaml,
    export_nodes_project_json,
    export_nodes_singbox_json,
)


def trojan(name: str = "trojan") -> ProxyNode:
    return ProxyNode(name=name, type="trojan", server="example.com", port=443, password="p", tls=True, sni="example.com")


def ss(name: str = "ss") -> ProxyNode:
    return ProxyNode(name=name, type="shadowsocks", server="ss.example.com", port=8388, method="aes-256-gcm", password="p")


def test_export_project_json(tmp_path) -> None:
    path = tmp_path / "nodes.json"

    result = export_nodes_project_json([trojan()], str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert result.exported_count == 1
    assert data[0]["name"] == "trojan"


def test_export_singbox_json(tmp_path) -> None:
    path = tmp_path / "singbox.json"

    result = export_nodes_singbox_json([trojan("T")], str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert result.exported_count == 1
    assert data["outbounds"][0]["type"] == "trojan"
    assert data["outbounds"][0]["tag"] == "T"


def test_export_clash_yaml(tmp_path) -> None:
    path = tmp_path / "clash.yaml"

    result = export_nodes_clash_yaml([ss("S")], str(path))

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert result.exported_count == 1
    assert data["proxies"][0]["type"] == "ss"
    assert data["proxies"][0]["cipher"] == "aes-256-gcm"


def test_empty_node_list_export_fails(tmp_path) -> None:
    with pytest.raises(ValueError, match="No nodes"):
        export_nodes_project_json([], str(tmp_path / "empty.json"))


def test_unsupported_protocol_is_skipped_with_warning(tmp_path) -> None:
    path = tmp_path / "mixed.yaml"
    unsupported = ProxyNode(name="bad", type="hysteria2", server="h.example.com", port=443)

    result = export_nodes_clash_yaml([trojan("ok"), unsupported], str(path))

    assert result.exported_count == 1
    assert result.skipped_count == 1
    assert result.warnings


def test_exported_project_json_can_be_read_as_proxy_nodes(tmp_path) -> None:
    path = tmp_path / "nodes.json"
    export_nodes_project_json([trojan("T")], str(path))

    loaded = [ProxyNode.from_dict(item) for item in json.loads(path.read_text(encoding="utf-8"))]

    assert loaded[0].name == "T"
    assert loaded[0].password == "p"
