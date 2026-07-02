from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from proxy_gui_client.system import autostart


class FakeKey:
    def __init__(self, registry: dict[str, str]):
        self.registry = registry

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeWinreg:
    HKEY_CURRENT_USER = object()
    KEY_SET_VALUE = 1
    KEY_READ = 2
    REG_SZ = 1

    def __init__(self):
        self.registry: dict[str, str] = {}

    def OpenKey(self, root, path, reserved, access):
        return FakeKey(self.registry)

    def SetValueEx(self, key, name, reserved, value_type, value):
        key.registry[name] = value

    def DeleteValue(self, key, name):
        if name not in key.registry:
            raise FileNotFoundError(name)
        del key.registry[name]

    def QueryValueEx(self, key, name):
        if name not in key.registry:
            raise FileNotFoundError(name)
        return key.registry[name], self.REG_SZ


def install_fake_winreg(monkeypatch) -> FakeWinreg:
    fake = FakeWinreg()
    monkeypatch.setitem(sys.modules, "winreg", fake)
    return fake


def test_enable_autostart_writes_command(monkeypatch) -> None:
    fake = install_fake_winreg(monkeypatch)

    autostart.enable_autostart('"C:\\App\\run.bat"')

    assert fake.registry[autostart.VALUE_NAME] == '"C:\\App\\run.bat"'


def test_disable_autostart_deletes_value(monkeypatch) -> None:
    fake = install_fake_winreg(monkeypatch)
    fake.registry[autostart.VALUE_NAME] = '"C:\\App\\run.bat"'

    autostart.disable_autostart()

    assert autostart.VALUE_NAME not in fake.registry


def test_is_autostart_enabled_reads_status(monkeypatch) -> None:
    fake = install_fake_winreg(monkeypatch)
    assert autostart.is_autostart_enabled() is False
    fake.registry[autostart.VALUE_NAME] = '"C:\\App\\run.bat"'

    assert autostart.is_autostart_enabled() is True


def test_build_command_quotes_paths_with_spaces() -> None:
    command = autostart.build_autostart_command(Path(r"C:\Users\Admin User\Documents\hysteria"))

    assert command == r'"C:\Users\Admin User\Documents\hysteria\run.bat"'


def test_autostart_exceptions_are_clear(monkeypatch) -> None:
    broken = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        KEY_SET_VALUE=1,
        OpenKey=lambda *args: (_ for _ in ()).throw(OSError("denied")),
    )
    monkeypatch.setitem(sys.modules, "winreg", broken)

    with pytest.raises(autostart.AutostartError, match="Failed to enable autostart"):
        autostart.enable_autostart()
