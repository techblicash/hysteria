from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from proxy_gui_client.core.batch_latency import (
    BatchLatencyUpdate,
    CancellationToken,
    run_batch_tcp_tests,
    run_batch_url_tests,
)
from proxy_gui_client.core.config_importer import import_config_file
from proxy_gui_client.core.connection_state import ConnectionState
from proxy_gui_client.core.core_manager import CoreManager
from proxy_gui_client.core.import_service import apply_import_strategy, apply_selected_import, build_import_preview
from proxy_gui_client.core.latency import tcp_latency_ms
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_batch_ops import apply_batch_edit
from proxy_gui_client.core.node_backup import backup_nodes, restore_nodes_from_backup
from proxy_gui_client.core.node_cleanup import (
    delete_nodes_by_indexes,
    duplicate_indexes_to_delete,
    find_duplicate_groups,
    find_unavailable_node_indexes,
)
from proxy_gui_client.core.node_dedup import node_identity
from proxy_gui_client.core.node_exporter import export_nodes_clash_yaml, export_nodes_project_json, export_nodes_singbox_json
from proxy_gui_client.core.node_filter import NodeFilterOptions, filter_and_sort_nodes, source_category
from proxy_gui_client.core.proxy_latency import UrlLatencyResult, url_proxy_latency_ms
from proxy_gui_client.core.storage import (
    clear_system_proxy_marker,
    ensure_app_dirs,
    load_nodes,
    load_settings,
    load_system_proxy_marker,
    log_dir,
    mark_system_proxy_enabled,
    save_nodes,
    save_settings,
)
from proxy_gui_client.core.subscription import fetch_subscription
from proxy_gui_client.core.subscription_groups import enabled_subscription_groups, stamp_subscription_nodes, subscription_source
from proxy_gui_client.core.table_preferences import (
    TABLE_COLUMN_KEYS,
    ensure_table_preferences,
    normalize_filter_preferences,
    normalize_table_column_widths,
    update_filter_preference,
    update_table_column_width,
)
from proxy_gui_client.core.updater import UpdateCheckResult, check_update_from_url, get_current_version, should_prompt_update
from proxy_gui_client.gui.batch_edit_dialog import BatchEditDialog
from proxy_gui_client.gui.cleanup_preview_dialog import CleanupPreviewDialog, duplicate_rows, unavailable_rows
from proxy_gui_client.gui.import_preview_dialog import ImportPreviewDialog
from proxy_gui_client.gui.node_editor import NodeEditorDialog
from proxy_gui_client.gui.settings_dialog import SettingsDialog
from proxy_gui_client.gui.tray_controller import TrayController
from proxy_gui_client.system.autostart import disable_autostart, enable_autostart
from proxy_gui_client.system.windows_proxy import (
    ProxyState,
    disable_system_proxy,
    enable_system_proxy,
    get_proxy_state,
    restore_proxy_state,
)


class GuiSignals(QObject):
    log = Signal(str)
    core_exited = Signal(int)


@dataclass
class SubscriptionRefreshResult:
    nodes: list[ProxyNode] = field(default_factory=list)
    refreshed_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    group_count: int = 0


class SubscriptionWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, groups: list[dict]):
        super().__init__()
        self.groups = groups

    def run(self) -> None:
        result = SubscriptionRefreshResult(group_count=len(self.groups))
        for group in self.groups:
            name = str(group.get("name") or group.get("url") or "subscription")
            url = str(group.get("url") or "")
            try:
                nodes = fetch_subscription(url)
                result.nodes.extend(stamp_subscription_nodes(nodes, group))
                result.refreshed_sources.append(subscription_source(group))
            except Exception as exc:
                result.warnings.append(f"{name}: {exc}")
        if result.nodes:
            self.finished_ok.emit(result)
        else:
            details = "; ".join(result.warnings[:5])
            self.failed.emit(details or "没有订阅组刷新成功")


class UpdateCheckWorker(QThread):
    finished_result = Signal(object)

    def __init__(self, url: str, current_version: str):
        super().__init__()
        self.url = url
        self.current_version = current_version

    def run(self) -> None:
        self.finished_result.emit(check_update_from_url(self.url, self.current_version))


class LatencyWorker(QThread):
    result = Signal(str, str, int)
    failed = Signal(str, str, object)
    status = Signal(str, str)
    done = Signal()

    def __init__(self, nodes: list[ProxyNode], settings: dict):
        super().__init__()
        self.nodes = nodes
        self.settings = dict(settings)

    def run(self) -> None:
        for node in self.nodes:
            self.status.emit(node.id, "Testing TCP")
            try:
                latency = tcp_latency_ms(node, float(self.settings.get("test_timeout_seconds", 5)))
                self.result.emit(node.id, "tcp", latency)
            except Exception as exc:
                self.failed.emit(node.id, "tcp", str(exc))
                continue
            self.status.emit(node.id, "Testing URL")
            result = url_proxy_latency_ms(node, self.settings)
            if result.http_port:
                self.status.emit(node.id, f"URL temporary HTTP port: {result.http_port}")
            if result.ok and result.latency_ms is not None:
                self.result.emit(node.id, "url", result.latency_ms)
            else:
                self.failed.emit(node.id, "url", result)
        self.done.emit()


class BatchLatencyWorker(QThread):
    update = Signal(object)
    done = Signal(object)

    def __init__(self, kind: str, indexed_nodes: list[tuple[int, ProxyNode]], settings: dict):
        super().__init__()
        self.kind = kind
        self.indexed_nodes = indexed_nodes
        self.settings = dict(settings)
        self.cancel_token = CancellationToken()

    def cancel(self) -> None:
        self.cancel_token.cancel()

    def run(self) -> None:
        if self.kind == "tcp":
            summary = run_batch_tcp_tests(
                self.indexed_nodes,
                timeout_seconds=float(self.settings.get("test_timeout_seconds", 5)),
                max_workers=8,
                on_result=self.update.emit,
                cancel_token=self.cancel_token,
            )
        else:
            summary = run_batch_url_tests(
                self.indexed_nodes,
                settings=self.settings,
                max_workers=2,
                on_result=self.update.emit,
                cancel_token=self.cancel_token,
            )
        self.done.emit(summary)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_app_dirs()
        self.setWindowTitle("Proxy GUI Client MVP")
        self.resize(1220, 760)

        self.nodes = load_nodes()
        self.settings = ensure_table_preferences(load_settings())
        self.displayed_nodes: list[tuple[int, ProxyNode]] = []
        self.signals = GuiSignals()
        self.signals.log.connect(self.append_log)
        self.signals.core_exited.connect(self.on_core_exited)
        self.core_manager = CoreManager(self.signals.log.emit, self.signals.core_exited.emit)
        self.connection_state = ConnectionState()
        self.original_proxy_state = self._safe_get_proxy_state()
        self.proxy_changed_by_app = False
        self.subscription_worker: SubscriptionWorker | None = None
        self.update_worker: UpdateCheckWorker | None = None
        self.latency_worker: LatencyWorker | None = None
        self.batch_worker: BatchLatencyWorker | None = None
        self._applying_column_widths = False
        self.running_node_id: str | None = None
        self.force_quit = False

        self.status_label = QLabel(self.connection_state.display_text())
        self._build_controls()
        self._build_table()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.tray_controller = TrayController(self)
        self._connect_tray()

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addLayout(self.action_buttons)
        layout.addLayout(self.filter_row_one)
        layout.addLayout(self.filter_row_two)
        layout.addWidget(self.node_table, 2)
        layout.addLayout(self.node_buttons)
        layout.addWidget(QLabel("核心日志"))
        layout.addWidget(self.log_view, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.refresh_table()
        self.set_batch_running(False)
        self.update_connection_state()
        self.update_tray_node_menus()
        self.append_log("程序启动完成")
        QTimer.singleShot(0, self.check_previous_proxy_marker)
        QTimer.singleShot(100, self.check_updates_on_start)
        QTimer.singleShot(200, self.auto_connect_last_node)

    def _build_controls(self) -> None:
        self.start_button = QPushButton("启动代理")
        self.stop_button = QPushButton("停止代理")
        self.test_button = QPushButton("测试延迟")
        self.refresh_button = QPushButton("刷新订阅")
        self.import_button = QPushButton("导入配置")
        self.settings_button = QPushButton("设置")
        self.enable_proxy_button = QPushButton("开启系统代理")
        self.disable_proxy_button = QPushButton("关闭系统代理")

        self.start_button.clicked.connect(self.start_proxy)
        self.stop_button.clicked.connect(self.stop_proxy)
        self.test_button.clicked.connect(self.test_latency)
        self.refresh_button.clicked.connect(self.refresh_subscription)
        self.import_button.clicked.connect(self.import_config)
        self.settings_button.clicked.connect(self.open_settings)
        self.enable_proxy_button.clicked.connect(self.enable_proxy)
        self.disable_proxy_button.clicked.connect(self.disable_proxy)

        self.action_buttons = QHBoxLayout()
        for button in [
            self.start_button,
            self.stop_button,
            self.test_button,
            self.refresh_button,
            self.import_button,
            self.settings_button,
            self.enable_proxy_button,
            self.disable_proxy_button,
        ]:
            self.action_buttons.addWidget(button)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索名称 / 服务器 / 类型 / 来源")

        self.type_filter = QComboBox()
        self._add_combo_items(self.type_filter, [("全部", "all"), ("vmess", "vmess"), ("vless", "vless"), ("trojan", "trojan"), ("ss / shadowsocks", "shadowsocks")])
        self.source_filter = QComboBox()
        self._add_combo_items(self.source_filter, [("全部", "all"), ("manual", "manual"), ("subscription", "subscription"), ("config_file", "config_file"), ("unknown", "unknown")])
        self.availability_filter = QComboBox()
        self._add_combo_items(
            self.availability_filter,
            [("全部", "all"), ("TCP 可用", "tcp_available"), ("URL 可用", "url_available"), ("测试失败", "failed"), ("未测试", "untested")],
        )
        self.sort_combo = QComboBox()
        self._add_combo_items(
            self.sort_combo,
            [
                ("默认顺序", "default"),
                ("名称", "name"),
                ("类型", "type"),
                ("TCP 延迟从低到高", "tcp_latency"),
                ("URL 延迟从低到高", "url_latency"),
                ("来源", "source"),
                ("导入时间", "imported_at"),
            ],
        )
        self.batch_scope_combo = QComboBox()
        self._add_combo_items(self.batch_scope_combo, [("当前筛选结果", "filtered"), ("当前选中节点", "selected")])
        self._restore_filter_preferences()
        self.search_edit.textChanged.connect(self.on_filter_preferences_changed)
        for combo in [self.type_filter, self.source_filter, self.availability_filter, self.sort_combo, self.batch_scope_combo]:
            combo.currentIndexChanged.connect(self.on_filter_preferences_changed)

        self.batch_tcp_button = QPushButton("批量 TCP 测试")
        self.batch_url_button = QPushButton("批量 URL 测试")
        self.stop_batch_button = QPushButton("停止批量测试")
        self.clear_tests_button = QPushButton("清除测试结果")
        self.batch_tcp_button.clicked.connect(lambda: self.start_batch_latency("tcp"))
        self.batch_url_button.clicked.connect(lambda: self.start_batch_latency("url"))
        self.stop_batch_button.clicked.connect(self.stop_batch_latency)
        self.clear_tests_button.clicked.connect(self.clear_test_results)

        self.filter_row_one = QHBoxLayout()
        self.filter_row_one.addWidget(QLabel("搜索"))
        self.filter_row_one.addWidget(self.search_edit, 2)
        self.filter_row_one.addWidget(QLabel("类型"))
        self.filter_row_one.addWidget(self.type_filter)
        self.filter_row_one.addWidget(QLabel("来源"))
        self.filter_row_one.addWidget(self.source_filter)
        self.filter_row_one.addWidget(QLabel("可用性"))
        self.filter_row_one.addWidget(self.availability_filter)

        self.filter_row_two = QHBoxLayout()
        self.filter_row_two.addWidget(QLabel("排序"))
        self.filter_row_two.addWidget(self.sort_combo)
        self.filter_row_two.addWidget(QLabel("测试范围"))
        self.filter_row_two.addWidget(self.batch_scope_combo)
        self.filter_row_two.addStretch(1)
        self.filter_row_two.addWidget(self.batch_tcp_button)
        self.filter_row_two.addWidget(self.batch_url_button)
        self.filter_row_two.addWidget(self.stop_batch_button)
        self.filter_row_two.addWidget(self.clear_tests_button)

        self.add_button = QPushButton("添加节点")
        self.edit_button = QPushButton("编辑节点")
        self.delete_button = QPushButton("删除节点")
        self.delete_selected_button = QPushButton("删除选中节点")
        self.export_selected_button = QPushButton("导出选中节点")
        self.backup_nodes_button = QPushButton("备份全部节点")
        self.restore_nodes_button = QPushButton("恢复节点备份")
        self.batch_edit_button = QPushButton("批量编辑")
        self.cleanup_unavailable_button = QPushButton("清理不可用")
        self.cleanup_duplicates_button = QPushButton("清理重复")
        self.add_button.clicked.connect(self.add_node)
        self.edit_button.clicked.connect(self.edit_node)
        self.delete_button.clicked.connect(self.delete_node)
        self.delete_selected_button.clicked.connect(self.delete_selected_nodes)
        self.export_selected_button.clicked.connect(self.export_selected_nodes)
        self.backup_nodes_button.clicked.connect(self.backup_all_nodes)
        self.restore_nodes_button.clicked.connect(self.restore_node_backup)
        self.batch_edit_button.clicked.connect(self.batch_edit_nodes)
        self.cleanup_unavailable_button.clicked.connect(self.cleanup_unavailable_nodes)
        self.cleanup_duplicates_button.clicked.connect(self.cleanup_duplicate_nodes)

        self.node_buttons = QHBoxLayout()
        self.node_buttons.addWidget(self.add_button)
        self.node_buttons.addWidget(self.edit_button)
        self.node_buttons.addWidget(self.delete_button)
        self.node_buttons.addWidget(self.delete_selected_button)
        self.node_buttons.addWidget(self.export_selected_button)
        self.node_buttons.addWidget(self.backup_nodes_button)
        self.node_buttons.addWidget(self.restore_nodes_button)
        self.node_buttons.addWidget(self.batch_edit_button)
        self.node_buttons.addWidget(self.cleanup_unavailable_button)
        self.node_buttons.addWidget(self.cleanup_duplicates_button)
        self.node_buttons.addStretch(1)

    def _build_table(self) -> None:
        self.node_table = QTableWidget(0, 8)
        self.node_table.setHorizontalHeaderLabels(["名称", "类型", "服务器", "端口", "来源", "TCP 延迟", "URL 延迟", "测试状态"])
        header = self.node_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.apply_table_column_widths()
        header.sectionResized.connect(self.on_table_section_resized)
        self.node_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.node_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.node_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.node_table.doubleClicked.connect(self.edit_node)

    def _connect_tray(self) -> None:
        self.tray_controller.show_requested.connect(self.show_main_window)
        self.tray_controller.hide_requested.connect(self.hide_to_tray)
        self.tray_controller.toggle_requested.connect(self.toggle_tray_visibility)
        self.tray_controller.start_requested.connect(self.start_proxy)
        self.tray_controller.stop_requested.connect(self.stop_proxy)
        self.tray_controller.enable_system_proxy_requested.connect(self.enable_proxy)
        self.tray_controller.disable_system_proxy_requested.connect(self.disable_proxy)
        self.tray_controller.test_latency_requested.connect(self.test_latency)
        self.tray_controller.settings_requested.connect(self.open_settings)
        self.tray_controller.quit_requested.connect(self.quit_application)
        self.tray_controller.node_switch_requested.connect(self.switch_to_node)

    def update_connection_state(self) -> None:
        text = self.connection_state.display_text()
        self.status_label.setText(f"状态：{text}")
        if hasattr(self, "tray_controller"):
            self.tray_controller.update_state(self.connection_state)

    def update_tray_node_menus(self) -> None:
        if hasattr(self, "tray_controller"):
            self.tray_controller.update_node_menus(self.nodes, list(self.settings.get("recent_node_identities", [])))

    def show_main_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self) -> None:
        self.hide()
        if self.settings.get("tray_show_notifications", True):
            self.tray_controller.show_message("Proxy GUI Client", "程序已隐藏到系统托盘")

    def toggle_tray_visibility(self) -> None:
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.show_main_window()

    def should_start_minimized(self) -> bool:
        return bool(self.settings.get("start_minimized", False))

    def auto_connect_last_node(self) -> None:
        if not self.settings.get("auto_connect_on_start", False):
            return
        identity = str(self.settings.get("last_selected_node_identity", "") or "")
        if not identity:
            self.append_log("已启用自动连接，但没有上次节点记录")
            return
        index = self.find_node_index_by_identity(identity)
        if index is None:
            self.append_log("自动连接失败：上次节点不存在")
            return
        self.select_node_by_index(index)
        node = self.nodes[index]
        self.append_log(f"启动后自动连接上次节点: {node.name}")
        self.start_proxy_with_node(node)

    def check_updates_on_start(self) -> None:
        current_version = get_current_version()
        self.append_log(f"当前版本: {current_version}")
        if not self.settings.get("update_check_enabled", False):
            return
        update_url = str(self.settings.get("update_check_url", "") or "").strip()
        if not update_url:
            self.append_log("已启用更新检查，但未配置更新检查 URL")
            return
        self.update_worker = UpdateCheckWorker(update_url, current_version)
        self.update_worker.finished_result.connect(self.on_update_check_finished)
        self.update_worker.start()

    @Slot(object)
    def on_update_check_finished(self, result: UpdateCheckResult) -> None:
        if result.error:
            self.append_log(f"更新检查失败: {result.error}")
            return
        if not should_prompt_update(result):
            self.append_log("当前已是最新版本")
            return
        answer = QMessageBox.question(self, "发现新版本", f"发现新版本：{result.latest_version}\n是否下载更新？")
        if answer == QMessageBox.Yes:
            self.append_log(f"发现新版本 {result.latest_version}，当前版本 {result.current_version}。下载更新逻辑尚未启用。{result.release_url}")
            QMessageBox.information(self, "更新下载", "当前版本只实现更新检查和提示，暂未自动下载。请前往发布页面手动下载。")

    def apply_table_column_widths(self) -> None:
        widths = normalize_table_column_widths(self.settings)
        self._applying_column_widths = True
        try:
            for column, key in enumerate(TABLE_COLUMN_KEYS):
                self.node_table.setColumnWidth(column, widths[key])
        finally:
            self._applying_column_widths = False

    @Slot(int, int, int)
    def on_table_section_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        if self._applying_column_widths or logical_index < 0 or logical_index >= len(TABLE_COLUMN_KEYS):
            return
        self.settings = update_table_column_width(self.settings, TABLE_COLUMN_KEYS[logical_index], new_size)
        save_settings(self.settings)

    def _add_combo_items(self, combo: QComboBox, items: list[tuple[str, str]]) -> None:
        for label, value in items:
            combo.addItem(label, value)

    def _restore_filter_preferences(self) -> None:
        preferences = normalize_filter_preferences(self.settings)
        self.search_edit.setText(preferences["keyword"])
        self._select_combo_data(self.type_filter, preferences["node_type"])
        self._select_combo_data(self.source_filter, preferences["source"])
        self._select_combo_data(self.availability_filter, preferences["availability"])
        self._select_combo_data(self.sort_combo, preferences["sort_by"])
        self._select_combo_data(self.batch_scope_combo, preferences["batch_scope"])

    def _select_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def current_filter_options(self) -> NodeFilterOptions:
        return NodeFilterOptions(
            keyword=self.search_edit.text(),
            node_type=self.type_filter.currentData() or "all",
            source=self.source_filter.currentData() or "all",
            availability=self.availability_filter.currentData() or "all",
            sort_by=self.sort_combo.currentData() or "default",
        )

    def on_filter_preferences_changed(self) -> None:
        preferences = {
            "keyword": self.search_edit.text(),
            "node_type": self.type_filter.currentData() or "all",
            "source": self.source_filter.currentData() or "all",
            "availability": self.availability_filter.currentData() or "all",
            "sort_by": self.sort_combo.currentData() or "default",
            "batch_scope": self.batch_scope_combo.currentData() or "filtered",
        }
        self.settings["node_filter_preferences"] = preferences
        self.settings = ensure_table_preferences(self.settings)
        save_settings(self.settings)
        self.refresh_table()

    def refresh_table(self) -> None:
        self.displayed_nodes = filter_and_sort_nodes(self.nodes, self.current_filter_options())
        self.node_table.setRowCount(len(self.displayed_nodes))
        for row, (original_index, node) in enumerate(self.displayed_nodes):
            values = [
                node.name,
                node.type,
                node.server,
                str(node.port),
                source_category(node),
                "-" if node.tcp_latency_ms is None else f"{node.tcp_latency_ms} ms",
                "-" if node.url_latency_ms is None else f"{node.url_latency_ms} ms",
                node.test_status or "-",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.UserRole, original_index)
                self.node_table.setItem(row, col, item)
        self.update_tray_node_menus()

    @Slot(str)
    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.log_view.append(line)
        try:
            log_dir().mkdir(parents=True, exist_ok=True)
            with (log_dir() / "app.log").open("a", encoding="utf-8") as file:
                file.write(line + "\n")
        except Exception:
            pass

    def selected_node_index(self, log_multi: bool = False) -> int | None:
        selected = self.node_table.selectionModel().selectedRows()
        if not selected:
            return None
        current_row = self.node_table.currentRow()
        selected_rows = {index.row() for index in selected}
        row = current_row if current_row in selected_rows else selected[0].row()
        if log_multi and len(selected) > 1:
            self.append_log("已选择多个节点，单节点操作将使用当前焦点行或第一行。")
        item = self.node_table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def selected_node_indexes(self) -> list[int]:
        selected = self.node_table.selectionModel().selectedRows()
        indexes: list[int] = []
        for selected_index in selected:
            item = self.node_table.item(selected_index.row(), 0)
            if item is None:
                continue
            original_index = item.data(Qt.UserRole)
            if isinstance(original_index, int) and 0 <= original_index < len(self.nodes):
                indexes.append(original_index)
        return sorted(set(indexes))

    def selected_node(self) -> ProxyNode | None:
        index = self.selected_node_index(log_multi=True)
        if index is None:
            return None
        if index < 0 or index >= len(self.nodes):
            return None
        return self.nodes[index]

    def select_node_by_index(self, node_index: int) -> bool:
        for row in range(self.node_table.rowCount()):
            item = self.node_table.item(row, 0)
            if item and item.data(Qt.UserRole) == node_index:
                self.node_table.selectRow(row)
                self.node_table.setCurrentCell(row, 0)
                return True
        return False

    def find_node_index_by_identity(self, identity: str) -> int | None:
        for index, node in enumerate(self.nodes):
            if node_identity(node) == identity:
                return index
        return None

    def record_node_usage(self, node: ProxyNode) -> None:
        identity = node_identity(node)
        recent = [item for item in self.settings.get("recent_node_identities", []) if item != identity]
        recent.insert(0, identity)
        self.settings["recent_node_identities"] = recent[:10]
        self.settings["last_selected_node_identity"] = identity
        self.settings["last_selected_node_name"] = node.name
        save_settings(self.settings)
        self.update_tray_node_menus()

    def switch_to_node(self, node_index: int) -> None:
        if node_index < 0 or node_index >= len(self.nodes):
            self.append_log("切换节点失败：节点不存在")
            return
        node = self.nodes[node_index]
        visible = self.select_node_by_index(node_index)
        self.record_node_usage(node)
        if not visible:
            self.append_log("节点已切换，但当前筛选条件下不可见")
        if self.core_manager.is_running:
            self.append_log(f"快速切换节点并重启代理: {node.name}")
            self.restart_proxy_with_node(node)
        else:
            self.append_log(f"已切换当前节点: {node.name}")

    def restart_proxy_with_node(self, node: ProxyNode) -> None:
        try:
            self.connection_state.set_stopping()
            self.update_connection_state()
            self.core_manager.stop()
            self.running_node_id = None
            self.connection_state.set_starting(node.name)
            self.update_connection_state()
            config_path = self.core_manager.start(node, self.settings)
            self.running_node_id = node.id
            self.connection_state.set_running(node.name)
            self.update_connection_state()
            self.record_node_usage(node)
            self.append_log(f"已切换节点并重新生成配置: {config_path}")
        except Exception as exc:
            self.connection_state.set_error(str(exc))
            self.update_connection_state()
            self.show_error("切换节点失败", exc)

    def add_node(self) -> None:
        dialog = NodeEditorDialog(self)
        if dialog.exec():
            node = dialog.get_node()
            self.nodes.append(node)
            self._save_nodes()
            self.append_log(f"已添加节点: {node.name}")

    def edit_node(self) -> None:
        index = self.selected_node_index(log_multi=True)
        if index is None:
            self.warn("请先选择一个节点")
            return
        node = self.nodes[index]
        dialog = NodeEditorDialog(self, node)
        if dialog.exec():
            updated = dialog.get_node()
            self.nodes[index] = updated
            self._save_nodes()
            self.append_log(f"已更新节点: {updated.name}")

    def delete_node(self) -> None:
        index = self.selected_node_index(log_multi=True)
        if index is None:
            self.warn("请先选择一个节点")
            return
        node = self.nodes[index]
        answer = QMessageBox.question(self, "删除节点", f"确认删除节点“{node.name}”？")
        if answer != QMessageBox.Yes:
            return
        del self.nodes[index]
        self._save_nodes()
        self.append_log(f"已删除节点: {node.name}")

    def delete_selected_nodes(self) -> None:
        indexes = self.selected_node_indexes()
        if not indexes:
            self.append_log("请先选择要删除的节点")
            return
        answer = QMessageBox.question(self, "删除选中节点", f"确认删除选中的 {len(indexes)} 个节点？")
        if answer != QMessageBox.Yes:
            return
        deleting_running = any(self.nodes[index].id == self.running_node_id for index in indexes)
        for index in sorted(indexes, reverse=True):
            del self.nodes[index]
        self._save_nodes()
        self.append_log(f"已删除选中节点 {len(indexes)} 个")
        if deleting_running:
            self.append_log("已删除的节点包含当前运行节点；当前代理进程不会自动停止。")

    def export_selected_nodes(self) -> None:
        nodes = self._nodes_for_export()
        if not nodes:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出节点",
            str(Path.cwd() / "nodes_export.json"),
            "项目 JSON (*.json);;sing-box JSON (*.json);;Clash YAML (*.yaml *.yml)",
        )
        if not path:
            return
        try:
            export_path = self._with_export_suffix(path, selected_filter)
            result = self._export_nodes_by_filter(nodes, export_path, selected_filter)
            self.append_log(f"已导出节点: {export_path}，数量 {result.exported_count}，跳过 {result.skipped_count}")
            for warning in result.warnings[:10]:
                self.append_log(f"导出警告: {warning}")
        except Exception as exc:
            self.show_error("导出节点失败", exc)

    def backup_all_nodes(self) -> None:
        if not self.nodes:
            self.warn("当前没有可备份的节点")
            return
        default_name = f"nodes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "备份全部节点", str(Path.cwd() / default_name), "项目 JSON (*.json)")
        if not path:
            return
        try:
            backup_path = self._ensure_suffix(path, ".json")
            result = backup_nodes(self.nodes, backup_path)
            self.append_log(f"已备份全部节点: {result.path}，数量 {result.count}")
        except Exception as exc:
            self.show_error("备份节点失败", exc)

    def restore_node_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "恢复节点备份", "", "项目 JSON (*.json);;All Files (*)")
        if not path:
            return

        mode_box = QMessageBox(self)
        mode_box.setWindowTitle("恢复节点备份")
        mode_box.setText("请选择恢复方式")
        merge_button = mode_box.addButton("合并到当前节点列表", QMessageBox.AcceptRole)
        replace_button = mode_box.addButton("替换当前全部节点", QMessageBox.DestructiveRole)
        mode_box.addButton(QMessageBox.Cancel)
        mode_box.exec()
        clicked = mode_box.clickedButton()
        if clicked == merge_button:
            mode = "merge"
        elif clicked == replace_button:
            confirm = QMessageBox.question(self, "确认替换", "替换会清空当前全部节点并使用备份内容，是否继续？")
            if confirm != QMessageBox.Yes:
                return
            mode = "replace"
        else:
            return

        result = restore_nodes_from_backup(self.nodes, path, mode)
        if result.errors:
            self.show_error("恢复节点备份失败", RuntimeError("; ".join(result.errors)))
            return
        self.nodes = result.nodes
        self._save_nodes()
        mode_text = "合并" if mode == "merge" else "替换"
        self.append_log(
            f"节点备份恢复完成: {mode_text}，恢复 {result.restored_count} 个，跳过 {result.skipped_count} 个，覆盖 {result.overwritten_count} 个"
        )
        for warning in result.warnings[:10]:
            self.append_log(f"恢复警告: {warning}")

    def batch_edit_nodes(self) -> None:
        indexes = self.selected_node_indexes()
        if not indexes:
            self.append_log("请先选择要批量编辑的节点")
            return
        dialog = BatchEditDialog(self, len(indexes))
        if not dialog.exec():
            return
        options = dialog.get_options()
        answer = QMessageBox.question(self, "确认批量编辑", f"确认修改选中的 {len(indexes)} 个节点？")
        if answer != QMessageBox.Yes:
            return
        result = apply_batch_edit(self.nodes, indexes, options)
        self.nodes = result.nodes
        self._save_nodes()
        self.append_log(f"批量编辑完成，修改 {result.updated_count} 个节点")

    def cleanup_unavailable_nodes(self) -> None:
        selected = self.selected_node_indexes()
        if selected:
            answer = QMessageBox.question(self, "清理不可用", f"检测到已选中 {len(selected)} 个节点，是否只检查选中节点？选择 No 将检查当前筛选结果。")
            candidate_indexes = selected if answer == QMessageBox.Yes else [index for index, _node in self.displayed_nodes]
        else:
            candidate_indexes = [index for index, _node in self.displayed_nodes]
        indexes = find_unavailable_node_indexes(self.nodes, candidate_indexes)
        if not indexes:
            self.append_log("未发现可清理的不可用节点")
            return
        dialog = CleanupPreviewDialog(
            self,
            "清理不可用节点预览",
            f"将删除 {len(indexes)} 个不可用节点。未测试节点不会被删除。",
            unavailable_rows(self.nodes, indexes),
            ["原始序号", "名称", "类型", "服务器", "TCP 延迟", "URL 延迟", "测试状态"],
        )
        if not dialog.exec():
            return
        deleting_running = any(self.nodes[index].id == self.running_node_id for index in indexes)
        self.nodes = delete_nodes_by_indexes(self.nodes, indexes)
        self._save_nodes()
        self.append_log(f"已清理不可用节点 {len(indexes)} 个")
        if deleting_running:
            self.append_log("清理列表包含当前运行节点；当前代理进程不会自动停止。")

    def cleanup_duplicate_nodes(self) -> None:
        groups = find_duplicate_groups(self.nodes)
        indexes = duplicate_indexes_to_delete(groups)
        if not indexes:
            self.append_log("未发现重复节点")
            return
        dialog = CleanupPreviewDialog(
            self,
            "清理重复节点预览",
            f"发现 {len(groups)} 组重复节点，将默认保留每组第一个节点并删除后续重复项，共删除 {len(indexes)} 个。",
            duplicate_rows(self.nodes, groups),
            ["组", "操作", "原始序号", "名称", "类型", "服务器", "端口"],
        )
        if not dialog.exec():
            return
        deleting_running = any(self.nodes[index].id == self.running_node_id for index in indexes)
        self.nodes = delete_nodes_by_indexes(self.nodes, indexes)
        self._save_nodes()
        self.append_log(f"已清理重复节点 {len(indexes)} 个，保留 {len(groups)} 个重复组首节点")
        if deleting_running:
            self.append_log("清理列表包含当前运行节点；当前代理进程不会自动停止。")

    def _nodes_for_export(self) -> list[ProxyNode]:
        indexes = self.selected_node_indexes()
        if indexes:
            return [self.nodes[index] for index in indexes]
        if not self.displayed_nodes:
            self.warn("当前筛选结果没有可导出的节点")
            return []
        answer = QMessageBox.question(self, "导出节点", f"当前未选择节点，是否导出当前筛选结果中的 {len(self.displayed_nodes)} 个节点？")
        if answer != QMessageBox.Yes:
            return []
        return [node for _index, node in self.displayed_nodes]

    def _export_nodes_by_filter(self, nodes: list[ProxyNode], path: str, selected_filter: str):
        if "sing-box" in selected_filter:
            return export_nodes_singbox_json(nodes, path)
        if "Clash" in selected_filter:
            return export_nodes_clash_yaml(nodes, path)
        return export_nodes_project_json(nodes, path)

    def _with_export_suffix(self, path: str, selected_filter: str) -> str:
        if "Clash" in selected_filter:
            return self._ensure_suffix(path, ".yaml")
        return self._ensure_suffix(path, ".json")

    def _ensure_suffix(self, path: str, suffix: str) -> str:
        file_path = Path(path)
        if file_path.suffix:
            return str(file_path)
        return str(file_path.with_suffix(suffix))

    def open_settings(self) -> None:
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec():
            old_settings = dict(self.settings)
            new_settings = dialog.get_settings()
            try:
                self.apply_autostart_setting(old_settings, new_settings)
            except Exception as exc:
                self.show_error("开机自启设置失败", exc)
                return
            self.settings = new_settings
            save_settings(self.settings)
            self.update_tray_node_menus()
            self.append_log("设置已保存")

    def apply_autostart_setting(self, old_settings: dict, new_settings: dict) -> None:
        if bool(old_settings.get("autostart_enabled", False)) == bool(new_settings.get("autostart_enabled", False)):
            return
        if new_settings.get("autostart_enabled", False):
            enable_autostart()
        else:
            disable_autostart()

    def start_proxy(self) -> None:
        node = self.selected_node()
        if not node:
            self.warn("请先选择一个节点")
            return
        self.start_proxy_with_node(node)

    def start_proxy_with_node(self, node: ProxyNode) -> None:
        try:
            self.connection_state.set_starting(node.name)
            self.update_connection_state()
            config_path = self.core_manager.start(node, self.settings)
            self.running_node_id = node.id
            self.connection_state.set_running(node.name)
            self.update_connection_state()
            self.record_node_usage(node)
            self.append_log(f"已生成配置: {config_path}")
            if self.settings.get("system_proxy_on_start"):
                self.enable_proxy()
        except Exception as exc:
            self.connection_state.set_error(str(exc))
            self.update_connection_state()
            self.show_error("启动失败", exc)

    def stop_proxy(self) -> None:
        try:
            self.connection_state.set_stopping()
            self.update_connection_state()
            self.core_manager.stop()
            self.running_node_id = None
            self.connection_state.set_disconnected()
            self.update_connection_state()
            if self.settings.get("disable_system_proxy_on_stop", True) and self.proxy_changed_by_app:
                self.restore_proxy()
        except Exception as exc:
            self.connection_state.set_error(str(exc))
            self.update_connection_state()
            self.show_error("停止失败", exc)

    def enable_proxy(self) -> None:
        try:
            if not self.proxy_changed_by_app:
                self.original_proxy_state = self._safe_get_proxy_state()
            enable_system_proxy("127.0.0.1", int(self.settings.get("http_port", 7890)), int(self.settings.get("socks_port", 7891)))
            self.proxy_changed_by_app = True
            mark_system_proxy_enabled(
                {"enabled": self.original_proxy_state.enabled, "server": self.original_proxy_state.server, "override": self.original_proxy_state.override}
            )
            self.append_log("Windows 系统代理已开启")
        except Exception as exc:
            self.show_error("开启系统代理失败", exc)

    def disable_proxy(self) -> None:
        try:
            disable_system_proxy()
            self.proxy_changed_by_app = False
            clear_system_proxy_marker()
            self.append_log("Windows 系统代理已关闭")
        except Exception as exc:
            self.show_error("关闭系统代理失败", exc)

    def restore_proxy(self) -> None:
        try:
            restore_proxy_state(self.original_proxy_state)
            self.proxy_changed_by_app = False
            clear_system_proxy_marker()
            self.append_log("已恢复程序启动前的 Windows 系统代理设置")
        except Exception as exc:
            self.show_error("恢复系统代理失败", exc)
            raise

    def refresh_subscription(self) -> None:
        groups = enabled_subscription_groups(self.settings)
        if not groups:
            self.warn("请先在设置中添加并启用订阅组")
            return
        if self.subscription_worker and self.subscription_worker.isRunning():
            self.warn("订阅刷新正在进行")
            return
        self.refresh_button.setEnabled(False)
        self.append_log(f"开始拉取订阅组，共 {len(groups)} 个...")
        self.subscription_worker = SubscriptionWorker(groups)
        self.subscription_worker.finished_ok.connect(self.on_subscription_finished)
        self.subscription_worker.failed.connect(self.on_subscription_failed)
        self.subscription_worker.finished.connect(lambda: self.refresh_button.setEnabled(True))
        self.subscription_worker.start()

    @Slot(object)
    def on_subscription_finished(self, result: SubscriptionRefreshResult) -> None:
        refreshed_sources = set(result.refreshed_sources)
        existing = [node for node in self.nodes if node.source not in refreshed_sources]
        self.nodes = existing + result.nodes
        self._save_nodes()
        self.append_log(f"订阅刷新完成，成功刷新 {len(refreshed_sources)}/{result.group_count} 个组，导入 {len(result.nodes)} 个节点")
        for warning in result.warnings[:10]:
            self.append_log(f"订阅警告: {warning}")

    @Slot(str)
    def on_subscription_failed(self, message: str) -> None:
        self.show_error("刷新订阅失败", RuntimeError(message))

    def import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入代理配置",
            "",
            "Proxy Config (*.yaml *.yml *.json);;YAML (*.yaml *.yml);;JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        result = import_config_file(path)
        preview = build_import_preview(result, self.nodes, path)
        self.append_log(f"导入配置文件: {path}")
        self.append_log(
            f"导入预览: 解析 {preview.total_nodes} 个节点，新增 {preview.new_count} 个，"
            f"现有重复 {preview.duplicate_existing_count} 个，文件内重复 {preview.duplicate_inside_file_count} 个，"
            f"warnings {len(preview.warnings)} 条，errors {len(preview.errors)} 条"
        )
        dialog = ImportPreviewDialog(self, preview)
        if not dialog.exec():
            self.append_log("导入已取消，未修改节点列表")
            return
        selected_count = 0
        if dialog.selected_strategy == "import_selected":
            selected_indexes = dialog.selected_indexes()
            selected_count = len(selected_indexes)
            apply_result = apply_selected_import(self.nodes, preview, selected_indexes)
        else:
            apply_result = apply_import_strategy(self.nodes, preview, dialog.selected_strategy)
        if apply_result.cancelled:
            self.append_log("导入已取消，未修改节点列表")
            return
        self.nodes = apply_result.nodes
        self._save_nodes()
        if dialog.selected_strategy == "import_selected":
            self.append_log(f"导入勾选项: 勾选 {selected_count} 项")
        self.append_log(
            f"导入策略: {dialog.selected_strategy}; 导入 {apply_result.imported_count} 个，"
            f"覆盖 {apply_result.overwritten_count} 个，跳过 {apply_result.skipped_count} 个，重命名 {apply_result.renamed_count} 个"
        )
        for warning in preview.warnings[:10]:
            self.append_log(f"导入警告: {warning}")
        for error in preview.errors[:10]:
            self.append_log(f"导入错误: {error}")
        for warning in apply_result.warnings[:10]:
            self.append_log(f"导入处理警告: {warning}")
        if apply_result.imported_count == 0:
            self.warn("没有导入任何节点。请查看日志中的 warnings/errors 或选择其他导入策略。")

    def test_latency(self) -> None:
        node = self.selected_node()
        if not node:
            self.warn("请先选择一个节点")
            return
        if self.latency_worker and self.latency_worker.isRunning():
            self.warn("延迟测试正在进行")
            return
        self.test_button.setEnabled(False)
        self.append_log(f"开始测试节点: {node.name}")
        self.latency_worker = LatencyWorker([node], self.settings)
        self.latency_worker.result.connect(self.on_latency_result)
        self.latency_worker.failed.connect(self.on_latency_failed)
        self.latency_worker.status.connect(self.on_latency_status)
        self.latency_worker.done.connect(self.on_latency_done)
        self.latency_worker.start()

    @Slot(str, str, int)
    def on_latency_result(self, node_id: str, kind: str, latency: int) -> None:
        for node in self.nodes:
            if node.id == node_id:
                self._apply_latency_success(node, kind, latency)
                self.append_log(f"节点 {node.name} {kind.upper()} 延迟: {latency} ms")
                break
        self._save_nodes()

    @Slot(str, str, object)
    def on_latency_failed(self, node_id: str, kind: str, payload) -> None:
        for node in self.nodes:
            if node.id == node_id:
                self._apply_latency_failure(node, kind, payload)
                break
        self._save_nodes()

    @Slot(str, str)
    def on_latency_status(self, node_id: str, status: str) -> None:
        for node in self.nodes:
            if node.id == node_id:
                node.test_status = status
                if status.startswith("URL temporary HTTP port"):
                    self.append_log(f"节点 {node.name} URL 延迟测试使用临时端口: {status}")
                break
        self._save_nodes()

    @Slot()
    def on_latency_done(self) -> None:
        self.test_button.setEnabled(True)
        self.append_log("延迟测试完成")

    def batch_target_nodes(self) -> list[tuple[int, ProxyNode]]:
        scope = self.batch_scope_combo.currentData() or "filtered"
        if scope == "selected":
            indexes = self.selected_node_indexes()
            if not indexes:
                self.warn("请先选择要测试的节点")
                return []
            return [(index, self.nodes[index]) for index in indexes]
        return list(self.displayed_nodes)

    def start_batch_latency(self, kind: str) -> None:
        if self.batch_worker and self.batch_worker.isRunning():
            self.warn("批量测试正在进行")
            return
        indexed_nodes = self.batch_target_nodes()
        if not indexed_nodes:
            if (self.batch_scope_combo.currentData() or "filtered") == "filtered":
                self.warn("当前筛选结果没有可测试节点")
            return
        scope_text = "当前选中节点" if (self.batch_scope_combo.currentData() or "filtered") == "selected" else "当前筛选结果"
        self.append_log(f"开始批量 {kind.upper()} 测试，范围：{scope_text}，共 {len(indexed_nodes)} 个节点")
        self.batch_worker = BatchLatencyWorker(kind, indexed_nodes, self.settings)
        self.batch_worker.update.connect(self.on_batch_latency_update)
        self.batch_worker.done.connect(self.on_batch_latency_done)
        self.set_batch_running(True)
        self.batch_worker.start()

    def stop_batch_latency(self) -> None:
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.cancel()
            self.stop_batch_button.setEnabled(False)
            self.append_log("已请求停止批量测试，正在等待当前节点完成...")

    @Slot(object)
    def on_batch_latency_update(self, update: BatchLatencyUpdate) -> None:
        if update.node_index < 0 or update.node_index >= len(self.nodes):
            return
        node = self.nodes[update.node_index]
        if update.ok and update.latency_ms is not None:
            self._apply_latency_success(node, update.kind, update.latency_ms)
            self.append_log(f"批量测试成功: {node.name} {update.kind.upper()} {update.latency_ms} ms")
        else:
            self._apply_latency_failure(node, update.kind, update.error)
            self.append_log(f"批量测试失败: {node.name} {update.kind.upper()} {update.error}")
        self._save_nodes()

    @Slot(object)
    def on_batch_latency_done(self, summary) -> None:
        self.set_batch_running(False)
        save_nodes(self.nodes)
        fastest = self.nodes[summary.fastest_node_index].name if summary.fastest_node_index is not None and summary.fastest_node_index < len(self.nodes) else "-"
        status = "已停止" if summary.cancelled else "完成"
        self.append_log(
            f"批量测试{status}: 总数 {summary.total}, 成功 {summary.success_count}, 失败 {summary.failure_count}, "
            f"平均 {summary.average_latency_ms if summary.average_latency_ms is not None else '-'} ms, 最快 {fastest}"
        )

    def set_batch_running(self, running: bool) -> None:
        self.batch_tcp_button.setEnabled(not running)
        self.batch_url_button.setEnabled(not running)
        self.stop_batch_button.setEnabled(running)
        self.clear_tests_button.setEnabled(not running)

    def clear_test_results(self) -> None:
        indexes = self.selected_node_indexes()
        if indexes:
            scope_text = "选中节点"
        else:
            indexes = [index for index, _node in self.displayed_nodes]
            if not indexes:
                self.warn("当前筛选结果没有可清除的节点")
                return
            answer = QMessageBox.question(
                self,
                "清除测试结果",
                f"当前未选择节点，是否清除当前筛选结果中的 {len(indexes)} 个节点测试结果？",
            )
            if answer != QMessageBox.Yes:
                return
            scope_text = "当前筛选结果"

        for index in indexes:
            node = self.nodes[index]
            node.tcp_latency_ms = None
            node.url_latency_ms = None
            node.latency_ms = None
            node.test_status = ""
            node.last_tested_at = ""
        self._save_nodes()
        self.append_log(f"已清除{scope_text}中 {len(indexes)} 个节点的测试结果")

    def _apply_latency_success(self, node: ProxyNode, kind: str, latency: int) -> None:
        if kind == "tcp":
            node.tcp_latency_ms = latency
            node.latency_ms = latency
            node.test_status = "TCP OK"
        else:
            node.url_latency_ms = latency
            node.test_status = "URL OK"
        node.last_tested_at = _now_iso()

    def _apply_latency_failure(self, node: ProxyNode, kind: str, payload) -> None:
        if kind == "tcp":
            node.tcp_latency_ms = None
            node.latency_ms = None
            node.test_status = "TCP failed"
            self.append_log(f"节点 {node.name} TCP 延迟测试失败: {payload}")
        else:
            result = payload if isinstance(payload, UrlLatencyResult) else None
            message = result.error if result else str(payload)
            category = result.error_category if result else None
            node.url_latency_ms = None
            node.test_status = f"URL 失败：{_category_label(category)}"
            self.append_log(f"节点 {node.name} URL 延迟测试失败: {message}")
            if result and result.test_url:
                self.append_log(f"测试 URL: {result.test_url}")
            if result and result.http_port:
                self.append_log(f"临时 HTTP 端口: {result.http_port}")
            if result and result.core_stderr_tail:
                self.append_log("临时核心 stderr 摘要:")
                self.append_log(result.core_stderr_tail)
            if result and result.core_stdout_tail:
                self.append_log("临时核心 stdout 摘要:")
                self.append_log(result.core_stdout_tail)
        node.last_tested_at = _now_iso()

    @Slot(int)
    def on_core_exited(self, code: int) -> None:
        self.running_node_id = None
        self.connection_state.set_disconnected()
        self.update_connection_state()
        self.append_log(f"核心已退出 ({code})")

    def _save_nodes(self) -> None:
        save_nodes(self.nodes)
        self.refresh_table()

    def warn(self, message: str) -> None:
        QMessageBox.warning(self, "提示", message)

    def show_error(self, title: str, exc: Exception) -> None:
        self.append_log(f"{title}: {exc}")
        self.append_log(traceback.format_exc())
        QMessageBox.critical(self, title, str(exc))

    def quit_application(self) -> None:
        self.force_quit = True
        if self.perform_shutdown(confirm_running=False, ask_restore=False):
            QApplication.quit()

    def perform_shutdown(self, confirm_running: bool = True, ask_restore: bool = True) -> bool:
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.cancel()
            self.batch_worker.wait(3000)
        if self.core_manager.is_running:
            if confirm_running:
                answer = QMessageBox.question(self, "退出", "代理核心仍在运行，是否停止并退出？")
                if answer != QMessageBox.Yes:
                    return False
            self.core_manager.stop()
            self.running_node_id = None
            self.connection_state.set_disconnected()
            self.update_connection_state()
        if self.proxy_changed_by_app:
            should_restore = True
            if ask_restore:
                answer = QMessageBox.question(self, "恢复系统代理", "是否恢复程序启动前的 Windows 系统代理设置？")
                should_restore = answer == QMessageBox.Yes
            if should_restore:
                try:
                    self.restore_proxy()
                except Exception as exc:
                    self.show_error("恢复系统代理失败", exc)
                    return False
        save_nodes(self.nodes)
        save_settings(self.settings)
        return True

    def closeEvent(self, event) -> None:
        if not self.force_quit and self.settings.get("close_to_tray", True):
            self.hide_to_tray()
            event.ignore()
            return
        if self.perform_shutdown(confirm_running=True, ask_restore=True):
            event.accept()
            if not self.force_quit:
                QTimer.singleShot(0, QApplication.quit)
        else:
            event.ignore()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.WindowStateChange and self.isMinimized() and self.settings.get("minimize_to_tray", True):
            QTimer.singleShot(0, self.hide_to_tray)
        super().changeEvent(event)

    def check_previous_proxy_marker(self) -> None:
        marker = load_system_proxy_marker()
        if marker is None:
            return
        self.append_log("检测到上次运行可能未正常恢复系统代理")
        answer = QMessageBox.question(self, "系统代理提示", "检测到上次运行可能由本程序开启了系统代理但未正常恢复。是否恢复上次记录的系统代理设置？")
        if answer != QMessageBox.Yes:
            return
        try:
            state = ProxyState(int(marker.get("enabled", 0)), str(marker.get("server", "")), str(marker.get("override", "")))
            restore_proxy_state(state)
            clear_system_proxy_marker()
            self.append_log("已根据上次记录恢复系统代理设置")
        except Exception as exc:
            self.show_error("恢复系统代理失败", exc)

    def _safe_get_proxy_state(self) -> ProxyState:
        try:
            return get_proxy_state()
        except Exception as exc:
            if hasattr(self, "log_view"):
                self.append_log(f"读取系统代理状态失败，将按关闭状态处理: {exc}")
            return ProxyState(0, "", "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _category_label(category: str | None) -> str:
    labels = {
        "core_path_missing": "核心路径错误",
        "config_generation_failed": "配置错误",
        "core_start_failed": "核心启动失败",
        "port_conflict": "端口占用",
        "request_failed": "请求失败",
        "timeout": "请求超时",
        "cleanup_failed": "清理失败",
    }
    return labels.get(category or "", "未知错误")
