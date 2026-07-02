from __future__ import annotations

import sys
from pathlib import Path

from proxy_gui_client.core import paths


def clear_path_env(monkeypatch) -> None:
    monkeypatch.delenv("PROXY_GUI_CLIENT_DATA_DIR", raising=False)
    monkeypatch.delenv("PROXY_GUI_CLIENT_LOG_DIR", raising=False)
    monkeypatch.delenv("PROXY_GUI_CLIENT_CORES_DIR", raising=False)


def test_non_frozen_base_dir_is_project_root(monkeypatch) -> None:
    clear_path_env(monkeypatch)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    assert paths.base_dir().name == "hysteria"
    assert paths.data_dir().parts[-2:] == ("proxy_gui_client", "data")
    assert paths.cores_dir() == paths.base_dir() / "cores"


def test_frozen_base_dir_is_executable_parent(monkeypatch, tmp_path) -> None:
    clear_path_env(monkeypatch)
    exe = tmp_path / "ProxyGUI.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert paths.base_dir() == tmp_path
    assert paths.data_dir() == tmp_path / "data"
    assert paths.log_dir() == tmp_path / "logs"
    assert paths.cores_dir() == tmp_path / "cores"


def test_resolve_packaged_data_path(monkeypatch, tmp_path) -> None:
    clear_path_env(monkeypatch)
    exe = tmp_path / "ProxyGUI.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert paths.resolve_app_path("proxy_gui_client/data/generated_config.json") == tmp_path / "data" / "generated_config.json"
    assert paths.resolve_app_path("cores/sing-box/sing-box.exe") == tmp_path / "cores" / "sing-box" / "sing-box.exe"


def test_environment_overrides_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "custom-data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "custom-logs"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_CORES_DIR", str(tmp_path / "custom-cores"))

    assert paths.data_dir() == tmp_path / "custom-data"
    assert paths.log_dir() == tmp_path / "custom-logs"
    assert paths.cores_dir() == tmp_path / "custom-cores"
