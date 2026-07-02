from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from proxy_gui_client.core.connection_state import ConnectionState
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_dedup import node_identity


class TrayController(QObject):
    show_requested = Signal()
    hide_requested = Signal()
    toggle_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    enable_system_proxy_requested = Signal()
    disable_system_proxy_requested = Signal()
    test_latency_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    node_switch_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, parent)
        self.menu = QMenu(parent)
        self.quick_menu = QMenu("快速切换节点", self.menu)
        self.recent_menu = QMenu("最近使用节点", self.menu)
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _build_menu(self) -> None:
        self.show_action = QAction("显示主窗口", self.menu)
        self.hide_action = QAction("隐藏主窗口", self.menu)
        self.start_action = QAction("启动代理", self.menu)
        self.stop_action = QAction("停止代理", self.menu)
        self.enable_proxy_action = QAction("开启系统代理", self.menu)
        self.disable_proxy_action = QAction("关闭系统代理", self.menu)
        self.test_latency_action = QAction("测试当前节点延迟", self.menu)
        self.settings_action = QAction("设置", self.menu)
        self.quit_action = QAction("退出程序", self.menu)

        self.show_action.triggered.connect(self.show_requested.emit)
        self.hide_action.triggered.connect(self.hide_requested.emit)
        self.start_action.triggered.connect(self.start_requested.emit)
        self.stop_action.triggered.connect(self.stop_requested.emit)
        self.enable_proxy_action.triggered.connect(self.enable_system_proxy_requested.emit)
        self.disable_proxy_action.triggered.connect(self.disable_system_proxy_requested.emit)
        self.test_latency_action.triggered.connect(self.test_latency_requested.emit)
        self.settings_action.triggered.connect(self.settings_requested.emit)
        self.quit_action.triggered.connect(self.quit_requested.emit)

        for item in [
            self.show_action,
            self.hide_action,
            self.start_action,
            self.stop_action,
            self.enable_proxy_action,
            self.disable_proxy_action,
        ]:
            self.menu.addAction(item)
        self.menu.addMenu(self.quick_menu)
        self.menu.addMenu(self.recent_menu)
        self.menu.addAction(self.test_latency_action)
        self.menu.addAction(self.settings_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

    def update_state(self, state: ConnectionState) -> None:
        self.tray.setToolTip(state.display_text())
        self.start_action.setEnabled(state.status not in {"starting", "running"})
        self.stop_action.setEnabled(state.status in {"starting", "running", "error"})

    def update_node_menus(self, nodes: list[ProxyNode], recent_identities: list[str]) -> None:
        self.quick_menu.clear()
        quick_nodes = sorted(
            enumerate(nodes),
            key=lambda item: (_latency_sort_key(item[1]), item[1].name.lower()),
        )[:20]
        if not quick_nodes:
            action = self.quick_menu.addAction("没有节点")
            action.setEnabled(False)
        for index, node in quick_nodes:
            action = self.quick_menu.addAction(_node_label(node))
            action.triggered.connect(lambda _checked=False, node_index=index: self.node_switch_requested.emit(node_index))

        self.recent_menu.clear()
        by_identity = {node_identity(node): (index, node) for index, node in enumerate(nodes)}
        added = 0
        for identity in recent_identities:
            match = by_identity.get(identity)
            if not match:
                continue
            index, node = match
            action = self.recent_menu.addAction(_node_label(node))
            action.triggered.connect(lambda _checked=False, node_index=index: self.node_switch_requested.emit(node_index))
            added += 1
        if added == 0:
            action = self.recent_menu.addAction("没有最近节点")
            action.setEnabled(False)

    def show_message(self, title: str, message: str) -> None:
        if self.tray.supportsMessages():
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_requested.emit()


def _node_label(node: ProxyNode) -> str:
    parts = [node.name or node.server or "未命名", node.type or "unknown"]
    latencies: list[str] = []
    if node.tcp_latency_ms is not None:
        latencies.append(f"TCP {node.tcp_latency_ms}ms")
    if node.url_latency_ms is not None:
        latencies.append(f"URL {node.url_latency_ms}ms")
    if latencies:
        parts.append(" / ".join(latencies))
    return " | ".join(parts)


def _latency_sort_key(node: ProxyNode) -> tuple[int, int]:
    values = [value for value in [node.url_latency_ms, node.tcp_latency_ms] if value is not None]
    if not values:
        return (1, 0)
    return (0, min(values))
