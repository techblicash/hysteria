from __future__ import annotations

import json

import pytest

from proxy_gui_client.core.adapters import get_core_adapter
from proxy_gui_client.core.adapters.base import CorePathError
from proxy_gui_client.core.adapters.mihomo import MihomoAdapter
from proxy_gui_client.core.adapters.xray import XrayAdapter
from proxy_gui_client.core.models import ProxyNode


def test_can_get_sing_box_adapter() -> None:
    adapter = get_core_adapter("sing-box")

    assert adapter.name == "sing-box"
    assert adapter.executable_name == "sing-box.exe"
    assert adapter.supports_node_type("vmess") is True


def test_sing_box_adapter_validates_core_path(tmp_path) -> None:
    adapter = get_core_adapter("sing-box")
    exe = tmp_path / "sing-box.exe"
    exe.write_text("fake", encoding="utf-8")

    adapter.validate_core_path(str(exe))

    with pytest.raises(CorePathError, match="does not exist"):
        adapter.validate_core_path(str(tmp_path / "missing.exe"))


def test_sing_box_adapter_generates_valid_config(tmp_path) -> None:
    adapter = get_core_adapter("sing-box")
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="secret")

    config_path = adapter.generate_config(node, {"http_port": 7890, "socks_port": 7891}, tmp_path / "config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["inbounds"][0]["type"] == "http"
    assert config["outbounds"][0]["type"] == "trojan"
    assert config["outbounds"][0]["password"] == "secret"


@pytest.mark.parametrize("adapter", [MihomoAdapter(), XrayAdapter()])
def test_placeholder_adapters_raise_clear_not_implemented(adapter) -> None:
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="secret")

    with pytest.raises(NotImplementedError, match="placeholder"):
        adapter.generate_config(node, {}, "config.json")
    with pytest.raises(NotImplementedError, match="placeholder"):
        adapter.build_start_command("core.exe", "config.json")
    assert adapter.supports_node_type("trojan") is False

