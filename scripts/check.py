from __future__ import annotations

import compileall
import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_compileall() -> None:
    print("==> compileall")
    ok = compileall.compile_dir(str(ROOT / "proxy_gui_client"), quiet=1)
    if not ok:
        raise SystemExit("compileall failed")


def run_pytest() -> None:
    print("==> pytest")
    result = subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_import_smoke() -> None:
    print("==> import smoke")
    modules = [
        "proxy_gui_client",
        "proxy_gui_client.main",
        "proxy_gui_client.core.models",
        "proxy_gui_client.core.paths",
        "proxy_gui_client.core.storage",
        "proxy_gui_client.core.node_parser",
        "proxy_gui_client.core.config_importer",
        "proxy_gui_client.core.node_dedup",
        "proxy_gui_client.core.node_batch_ops",
        "proxy_gui_client.core.node_cleanup",
        "proxy_gui_client.core.node_exporter",
        "proxy_gui_client.core.node_backup",
        "proxy_gui_client.core.import_service",
        "proxy_gui_client.core.node_filter",
        "proxy_gui_client.core.batch_latency",
        "proxy_gui_client.core.table_preferences",
        "proxy_gui_client.core.connection_state",
        "proxy_gui_client.core.routing",
        "proxy_gui_client.core.updater",
        "proxy_gui_client.core.config_generator",
        "proxy_gui_client.core.core_manager",
        "proxy_gui_client.core.subscription",
        "proxy_gui_client.core.subscription_groups",
        "proxy_gui_client.core.latency",
        "proxy_gui_client.core.port_utils",
        "proxy_gui_client.core.process_utils",
        "proxy_gui_client.core.proxy_latency",
        "proxy_gui_client.core.adapters",
        "proxy_gui_client.core.adapters.base",
        "proxy_gui_client.core.adapters.singbox",
        "proxy_gui_client.core.adapters.mihomo",
        "proxy_gui_client.core.adapters.xray",
        "proxy_gui_client.gui.tray_controller",
        "proxy_gui_client.system.autostart",
    ]
    for module in modules:
        importlib.import_module(module)


def run_dir_creation_check() -> None:
    print("==> data/log directory check")
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        log_dir = Path(tmp) / "logs"
        os.environ["PROXY_GUI_CLIENT_DATA_DIR"] = str(data_dir)
        os.environ["PROXY_GUI_CLIENT_LOG_DIR"] = str(log_dir)
        storage = importlib.import_module("proxy_gui_client.core.storage")
        storage.ensure_app_dirs()
        assert data_dir.exists()
        assert log_dir.exists()
        assert storage.nodes_file().exists()
        assert storage.settings_file().exists()


def main() -> int:
    os.chdir(ROOT)
    run_compileall()
    run_pytest()
    run_import_smoke()
    run_dir_creation_check()
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
