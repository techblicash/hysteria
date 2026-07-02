from __future__ import annotations

import io
import threading
from pathlib import Path

import pytest

from proxy_gui_client.core.core_manager import CoreManager
from proxy_gui_client.core.models import ProxyNode


class FakeAdapter:
    name = "fake-core"

    def validate_core_path(self, core_path: str) -> None:
        return None

    def generate_config(self, node, settings, output_path):
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return path

    def build_start_command(self, core_path: str, config_path: str) -> list[str]:
        return ["custom-core", "--config", config_path]


class FakePopen:
    last_command: list[str] | None = None

    def __init__(self, command, **kwargs):
        FakePopen.last_command = command
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self.returncode = None
        self._stopped = threading.Event()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self._stopped.wait(timeout or 0.05)
        if self.returncode is None and self._stopped.is_set():
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.returncode = 0
        self._stopped.set()

    def kill(self):
        self.returncode = -9
        self._stopped.set()


class RunningProcess:
    def poll(self):
        return None


def test_core_manager_uses_adapter_command(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("proxy_gui_client.core.core_manager.get_core_adapter", lambda core_type: FakeAdapter())
    monkeypatch.setattr("proxy_gui_client.core.core_manager.subprocess.Popen", FakePopen)
    monkeypatch.setattr("proxy_gui_client.core.core_manager.time.sleep", lambda seconds: None)
    manager = CoreManager()
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")

    config_path = manager.start(node, {"core_type": "fake", "core_path": "fake.exe", "config_path": str(tmp_path / "config.json")})
    manager.stop()

    assert config_path == tmp_path / "config.json"
    assert FakePopen.last_command == ["custom-core", "--config", str(tmp_path / "config.json")]


def test_core_manager_blocks_duplicate_start() -> None:
    manager = CoreManager()
    manager.process = RunningProcess()
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")

    with pytest.raises(RuntimeError, match="已在运行"):
        manager.start(node, {"core_type": "sing-box", "core_path": "missing.exe"})


def test_core_manager_reports_missing_core_path() -> None:
    manager = CoreManager()
    node = ProxyNode(name="demo", type="trojan", server="example.com", port=443, password="p")

    with pytest.raises(RuntimeError, match="does not exist"):
        manager.start(node, {"core_type": "sing-box", "core_path": "missing.exe"})

