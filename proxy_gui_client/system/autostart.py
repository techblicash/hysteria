from __future__ import annotations

from pathlib import Path

from proxy_gui_client.core.paths import is_frozen


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ProxyGuiClient"


class AutostartError(RuntimeError):
    pass


def enable_autostart(command: str | None = None) -> None:
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command or build_autostart_command())
    except Exception as exc:
        raise AutostartError(f"Failed to enable autostart: {exc}") from exc


def disable_autostart() -> None:
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                return
    except Exception as exc:
        raise AutostartError(f"Failed to disable autostart: {exc}") from exc


def is_autostart_enabled() -> bool:
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except Exception as exc:
        raise AutostartError(f"Failed to read autostart status: {exc}") from exc


def build_autostart_command(project_root: Path | None = None) -> str:
    if is_frozen():
        import sys

        return f'"{Path(sys.executable).resolve()}"'
    root = project_root or Path(__file__).resolve().parents[2]
    run_bat = root / "run.bat"
    return f'"{run_bat}"'


def _winreg():
    try:
        import winreg
    except Exception as exc:
        raise AutostartError("Windows registry is not available on this platform") from exc
    return winreg
