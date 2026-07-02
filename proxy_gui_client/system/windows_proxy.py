from __future__ import annotations

import ctypes
import winreg
from dataclasses import dataclass


INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


@dataclass
class ProxyState:
    enabled: int
    server: str
    override: str


def get_proxy_state() -> ProxyState:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
        enabled = _read_value(key, "ProxyEnable", 0)
        server = _read_value(key, "ProxyServer", "")
        override = _read_value(key, "ProxyOverride", "")
    return ProxyState(int(enabled), str(server), str(override))


def enable_system_proxy(host: str = "127.0.0.1", http_port: int = 7890, socks_port: int = 7891) -> None:
    proxy_server = f"http={host}:{http_port};https={host}:{http_port};socks={host}:{socks_port}"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
    _refresh()


def disable_system_proxy() -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
    _refresh()


def restore_proxy_state(state: ProxyState) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, int(state.enabled))
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, state.server)
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, state.override)
    _refresh()


def _read_value(key, name: str, default):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return default


def _refresh() -> None:
    ctypes.windll.Wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
    ctypes.windll.Wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)

