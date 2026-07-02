from __future__ import annotations

import json

from proxy_gui_client.core.adapters.singbox import SingBoxAdapter
from proxy_gui_client.core.config_importer import import_clash_yaml, import_config_file, import_singbox_json
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.storage import load_nodes, save_nodes


def write_text(path, content: str):
    path.write_text(content, encoding="utf-8")
    return path


def test_import_clash_vmess_node(tmp_path) -> None:
    path = write_text(
        tmp_path / "config.yaml",
        """
proxies:
  - name: HK-01
    type: vmess
    server: example.com
    port: 443
    uuid: 11111111-1111-1111-1111-111111111111
    alterId: 0
    cipher: auto
    tls: true
    network: ws
    ws-opts:
      path: /path
      headers:
        Host: cdn.example.com
""",
    )

    result = import_clash_yaml(str(path))

    assert result.errors == []
    assert len(result.nodes) == 1
    node = result.nodes[0]
    assert node.name == "HK-01"
    assert node.type == "vmess"
    assert node.uuid == "11111111-1111-1111-1111-111111111111"
    assert node.network == "ws"
    assert node.path == "/path"
    assert node.host == "cdn.example.com"
    assert node.tls is True


def test_import_clash_trojan_node(tmp_path) -> None:
    path = write_text(
        tmp_path / "config.yaml",
        """
proxies:
  - name: SG-01
    type: trojan
    server: example.com
    port: 443
    password: password
    sni: example.com
""",
    )

    result = import_clash_yaml(str(path))

    assert len(result.nodes) == 1
    assert result.nodes[0].type == "trojan"
    assert result.nodes[0].password == "password"
    assert result.nodes[0].sni == "example.com"


def test_import_clash_ss_node(tmp_path) -> None:
    path = write_text(
        tmp_path / "config.yaml",
        """
proxies:
  - name: JP-01
    type: ss
    server: example.com
    port: 8388
    cipher: aes-256-gcm
    password: password
""",
    )

    result = import_clash_yaml(str(path))

    assert len(result.nodes) == 1
    assert result.nodes[0].type == "shadowsocks"
    assert result.nodes[0].method == "aes-256-gcm"


def test_clash_unsupported_type_is_skipped_with_warning(tmp_path) -> None:
    path = write_text(
        tmp_path / "config.yaml",
        """
proxies:
  - name: Bad
    type: hysteria2
    server: example.com
    port: 443
""",
    )

    result = import_clash_yaml(str(path))

    assert result.nodes == []
    assert result.warnings
    assert "unsupported type" in result.warnings[0]


def test_clash_missing_fields_skipped_with_warning(tmp_path) -> None:
    path = write_text(
        tmp_path / "config.yaml",
        """
proxies:
  - name: Missing
    type: vmess
    server: example.com
    port: 443
""",
    )

    result = import_clash_yaml(str(path))

    assert result.nodes == []
    assert any("missing UUID" in warning for warning in result.warnings)


def test_import_singbox_vless_node(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "outbounds": [
                    {
                        "type": "vless",
                        "tag": "node-1",
                        "server": "example.com",
                        "server_port": 443,
                        "uuid": "22222222-2222-2222-2222-222222222222",
                        "tls": {"enabled": True, "server_name": "example.com"},
                        "transport": {"type": "ws", "path": "/path", "headers": {"Host": "cdn.example.com"}},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = import_singbox_json(str(path))

    assert len(result.nodes) == 1
    node = result.nodes[0]
    assert node.type == "vless"
    assert node.name == "node-1"
    assert node.uuid == "22222222-2222-2222-2222-222222222222"
    assert node.sni == "example.com"
    assert node.network == "ws"
    assert node.path == "/path"


def test_import_singbox_trojan_node(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"outbounds": [{"type": "trojan", "tag": "tr", "server": "example.com", "server_port": 443, "password": "p"}]}),
        encoding="utf-8",
    )

    result = import_singbox_json(str(path))

    assert len(result.nodes) == 1
    assert result.nodes[0].type == "trojan"
    assert result.nodes[0].password == "p"


def test_singbox_non_node_outbounds_are_skipped(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"outbounds": [{"type": "direct", "tag": "direct"}, {"type": "block", "tag": "block"}]}), encoding="utf-8")

    result = import_singbox_json(str(path))

    assert result.nodes == []
    assert len(result.warnings) == 2


def test_invalid_yaml_and_json_return_errors(tmp_path) -> None:
    yaml_path = write_text(tmp_path / "bad.yaml", "proxies: [")
    json_path = write_text(tmp_path / "bad.json", "{")

    yaml_result = import_config_file(str(yaml_path))
    json_result = import_config_file(str(json_path))

    assert yaml_result.errors
    assert json_result.errors


def test_old_nodes_json_still_loads(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))
    node = ProxyNode(name="old", type="trojan", server="example.com", port=443, password="p")

    save_nodes([node])
    loaded = load_nodes()

    assert len(loaded) == 1
    assert loaded[0].name == "old"


def test_imported_node_can_generate_singbox_config(tmp_path) -> None:
    path = write_text(
        tmp_path / "config.yaml",
        """
proxies:
  - name: JP-01
    type: ss
    server: example.com
    port: 8388
    cipher: aes-256-gcm
    password: password
""",
    )
    result = import_clash_yaml(str(path))

    config_path = SingBoxAdapter().generate_config(result.nodes[0], {"http_port": 7890, "socks_port": 7891}, tmp_path / "generated.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["outbounds"][0]["type"] == "shadowsocks"

