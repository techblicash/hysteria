from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import requests

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.proxy_latency import url_proxy_latency_ms
from proxy_gui_client.core.storage import load_settings, settings_file


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


class FakeProcess:
    def __init__(self, command, stdout_text: str = "", stderr_text: str = "", returncode=None, **kwargs):
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = None
        self.terminated = False
        self.killed = False
        self._event = threading.Event()
        if returncode is not None:
            self.returncode = returncode
            self._event.set()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            self._event.wait(timeout or 0.01)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0
        self._event.set()

    def kill(self):
        self.killed = True
        self.returncode = -9
        self._event.set()


def test_url_latency_missing_core_path_returns_failure() -> None:
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")

    result = url_proxy_latency_ms(node, {"core_type": "sing-box", "core_path": "missing.exe"})

    assert result.ok is False
    assert "does not exist" in (result.error or "")
    assert result.error_category == "core_path_missing"


def test_url_latency_passes_timeout_and_cleans_process(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("proxy_gui_client.core.proxy_latency.find_free_port_pair", lambda: (19080, 19081))
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")
    core = tmp_path / "sing-box.exe"
    core.write_text("fake", encoding="utf-8")
    captured = {}
    process_box = {}

    def fake_popen(command, **kwargs):
        process = FakeProcess(command, **kwargs)
        process_box["process"] = process
        captured["config_path"] = command[-1]
        return process

    def fake_get(url, proxies, timeout):
        captured["url"] = url
        captured["proxies"] = proxies
        captured["timeout"] = timeout
        return FakeResponse()

    result = url_proxy_latency_ms(
        node,
        {
            "core_type": "sing-box",
            "core_path": str(core),
            "http_port": 18080,
            "socks_port": 18081,
            "latency_test_url": "https://example.com/health",
            "latency_timeout": 9,
        },
        popen_factory=fake_popen,
        request_get=fake_get,
        startup_wait_seconds=0,
    )

    assert result.ok is True
    assert result.latency_ms is not None
    assert captured["url"] == "https://example.com/health"
    assert captured["timeout"] == 9
    assert captured["proxies"]["https"] == "http://127.0.0.1:19080"
    assert process_box["process"].terminated is True
    assert Path(captured["config_path"]).exists() is False


def test_url_latency_uses_temporary_ports_not_formal_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr("proxy_gui_client.core.proxy_latency.find_free_port_pair", lambda: (19080, 19081))
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")
    core = tmp_path / "sing-box.exe"
    core.write_text("fake", encoding="utf-8")
    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        config = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
        captured["http_port"] = config["inbounds"][0]["listen_port"]
        captured["socks_port"] = config["inbounds"][1]["listen_port"]
        return FakeProcess(command, **kwargs)

    def fake_get(url, proxies, timeout):
        captured["proxy"] = proxies["https"]
        return FakeResponse()

    result = url_proxy_latency_ms(
        node,
        {
            "core_type": "sing-box",
            "core_path": str(core),
            "http_port": 18080,
            "socks_port": 18081,
            "latency_test_url": "https://example.com/health",
            "latency_timeout": 5,
        },
        popen_factory=fake_popen,
        request_get=fake_get,
        startup_wait_seconds=0,
    )

    assert result.ok is True
    assert result.http_port == 19080
    assert result.socks_port == 19081
    assert captured["http_port"] == 19080
    assert captured["socks_port"] == 19081
    assert captured["proxy"] == "http://127.0.0.1:19080"
    assert captured["http_port"] != 18080
    assert captured["socks_port"] != 18081


def test_url_latency_does_not_rewrite_settings_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr("proxy_gui_client.core.proxy_latency.find_free_port_pair", lambda: (19080, 19081))
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")
    core = tmp_path / "sing-box.exe"
    core.write_text("fake", encoding="utf-8")
    settings_file().parent.mkdir(parents=True, exist_ok=True)
    settings_file().write_text(
        json.dumps({"core_type": "sing-box", "core_path": str(core), "http_port": 18080, "socks_port": 18081}),
        encoding="utf-8",
    )
    settings = load_settings()

    result = url_proxy_latency_ms(
        node,
        settings,
        popen_factory=lambda command, **kwargs: FakeProcess(command, **kwargs),
        request_get=lambda url, proxies, timeout: FakeResponse(),
        startup_wait_seconds=0,
    )
    after = json.loads(settings_file().read_text(encoding="utf-8"))

    assert result.ok is True
    assert after["http_port"] == 18080
    assert after["socks_port"] == 18081


def test_url_latency_immediate_core_exit_includes_stdout_stderr(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("proxy_gui_client.core.proxy_latency.find_free_port_pair", lambda: (19080, 19081))
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")
    core = tmp_path / "sing-box.exe"
    core.write_text("fake", encoding="utf-8")

    def fake_popen(command, **kwargs):
        return FakeProcess(
            command,
            stdout_text="core booting\n",
            stderr_text="listen tcp 127.0.0.1:19080: bind: address already in use\n",
            returncode=1,
        )

    result = url_proxy_latency_ms(
        node,
        {"core_type": "sing-box", "core_path": str(core), "latency_test_url": "https://example.com/health"},
        popen_factory=fake_popen,
        request_get=lambda url, proxies, timeout: FakeResponse(),
        startup_wait_seconds=0,
    )

    assert result.ok is False
    assert result.error_category == "port_conflict"
    assert "address already in use" in (result.core_stderr_tail or "")
    assert "core booting" in (result.core_stdout_tail or "")


def test_url_latency_request_timeout_has_timeout_category(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("proxy_gui_client.core.proxy_latency.find_free_port_pair", lambda: (19080, 19081))
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")
    core = tmp_path / "sing-box.exe"
    core.write_text("fake", encoding="utf-8")
    process_box = {}

    def fake_popen(command, **kwargs):
        process = FakeProcess(command, stdout_text="ready\n", stderr_text="")
        process_box["process"] = process
        return process

    def fake_get(url, proxies, timeout):
        raise requests.exceptions.Timeout("timed out")

    result = url_proxy_latency_ms(
        node,
        {"core_type": "sing-box", "core_path": str(core), "latency_test_url": "https://example.com/health", "latency_timeout": 1},
        popen_factory=fake_popen,
        request_get=fake_get,
        startup_wait_seconds=0,
    )

    assert result.ok is False
    assert result.error_category == "timeout"
    assert "timeout" in (result.error or "")
    assert process_box["process"].terminated is True


def test_url_latency_failure_log_tail_is_bounded(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("proxy_gui_client.core.proxy_latency.find_free_port_pair", lambda: (19080, 19081))
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")
    core = tmp_path / "sing-box.exe"
    core.write_text("fake", encoding="utf-8")
    long_stderr = "\n".join(f"stderr-line-{index}-" + "x" * 300 for index in range(80))

    result = url_proxy_latency_ms(
        node,
        {"core_type": "sing-box", "core_path": str(core), "latency_test_url": "https://example.com/health"},
        popen_factory=lambda command, **kwargs: FakeProcess(command, stderr_text=long_stderr, returncode=1),
        request_get=lambda url, proxies, timeout: FakeResponse(),
        startup_wait_seconds=0,
    )

    assert result.ok is False
    assert result.core_stderr_tail is not None
    assert len(result.core_stderr_tail) <= 4000
