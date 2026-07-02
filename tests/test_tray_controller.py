from __future__ import annotations

from PySide6.QtWidgets import QApplication

from proxy_gui_client.core.connection_state import ConnectionState
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_dedup import node_identity
from proxy_gui_client.gui.tray_controller import TrayController


def node(name: str, server: str = "example.com", latency: int | None = None) -> ProxyNode:
    return ProxyNode(name=name, type="trojan", server=server, port=443, password="p", tcp_latency_ms=latency)


def test_tray_menu_can_be_constructed() -> None:
    app = QApplication.instance() or QApplication([])
    tray = TrayController()
    try:
        assert tray.menu is not None
        assert tray.quick_menu is not None
        assert tray.recent_menu is not None
    finally:
        tray.tray.hide()
        app.processEvents()


def test_state_change_updates_tooltip() -> None:
    app = QApplication.instance() or QApplication([])
    tray = TrayController()
    try:
        tray.update_state(ConnectionState(status="running", node_name="A"))
        assert tray.tray.toolTip() == "已连接：A"
    finally:
        tray.tray.hide()
        app.processEvents()


def test_quick_node_menu_can_generate_items() -> None:
    app = QApplication.instance() or QApplication([])
    tray = TrayController()
    try:
        tray.update_node_menus([node("A"), node("B", server="b.example.com", latency=10)], [])
        assert len(tray.quick_menu.actions()) == 2
    finally:
        tray.tray.hide()
        app.processEvents()


def test_recent_menu_skips_missing_nodes() -> None:
    app = QApplication.instance() or QApplication([])
    tray = TrayController()
    existing = node("A")
    missing = node("Missing", server="missing.example.com")
    try:
        tray.update_node_menus([existing], [node_identity(missing), node_identity(existing)])
        actions = tray.recent_menu.actions()
        assert len(actions) == 1
        assert "A" in actions[0].text()
    finally:
        tray.tray.hide()
        app.processEvents()
