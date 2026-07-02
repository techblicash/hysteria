from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from proxy_gui_client.core.subscription_groups import normalize_subscription_groups
from proxy_gui_client.core.routing import normalize_routing_mode


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.settings = dict(settings or {})

        self.core_type_combo = QComboBox()
        self.core_type_combo.addItems(["sing-box", "Mihomo (experimental)", "Xray (experimental)"])
        current_core = str(self.settings.get("core_type", "sing-box")).lower()
        if current_core in {"mihomo", "clash-meta", "clash.meta"}:
            self.core_type_combo.setCurrentIndex(1)
        elif current_core == "xray":
            self.core_type_combo.setCurrentIndex(2)

        self.core_path_edit = QLineEdit(str(self.settings.get("core_path", "")))
        browse_core = QPushButton("浏览")
        browse_core.clicked.connect(self._browse_core)
        core_row = QHBoxLayout()
        core_row.addWidget(self.core_path_edit)
        core_row.addWidget(browse_core)

        self.config_path_edit = QLineEdit(str(self.settings.get("config_path", "proxy_gui_client/data/generated_config.json")))
        browse_config = QPushButton("选择")
        browse_config.clicked.connect(self._browse_config)
        config_row = QHBoxLayout()
        config_row.addWidget(self.config_path_edit)
        config_row.addWidget(browse_config)

        self.routing_mode_combo = QComboBox()
        self.routing_mode_combo.addItem("全局模式：全部走代理", "global")
        self.routing_mode_combo.addItem("规则模式：局域网/CN 直连，其余代理", "rule")
        self.routing_mode_combo.addItem("直连模式：全部直连", "direct")
        current_routing = normalize_routing_mode(self.settings.get("routing_mode", "global"))
        self.routing_mode_combo.setCurrentIndex(max(0, self.routing_mode_combo.findData(current_routing)))

        self.http_port_spin = QSpinBox()
        self.http_port_spin.setRange(1, 65535)
        self.http_port_spin.setValue(int(self.settings.get("http_port", 7890)))
        self.socks_port_spin = QSpinBox()
        self.socks_port_spin.setRange(1, 65535)
        self.socks_port_spin.setValue(int(self.settings.get("socks_port", 7891)))
        self.subscription_table = QTableWidget(0, 3)
        self.subscription_table.setHorizontalHeaderLabels(["启用", "名称", "链接"])
        self.subscription_table.horizontalHeader().setStretchLastSection(True)
        self._load_subscription_groups()
        self.add_subscription_button = QPushButton("添加订阅组")
        self.delete_subscription_button = QPushButton("删除订阅组")
        self.add_subscription_button.clicked.connect(self._add_subscription_row)
        self.delete_subscription_button.clicked.connect(self._delete_subscription_rows)
        subscription_buttons = QHBoxLayout()
        subscription_buttons.addWidget(self.add_subscription_button)
        subscription_buttons.addWidget(self.delete_subscription_button)
        subscription_buttons.addStretch(1)
        subscription_layout = QVBoxLayout()
        subscription_layout.addWidget(QLabel("订阅组"))
        subscription_layout.addWidget(self.subscription_table)
        subscription_layout.addLayout(subscription_buttons)
        self.latency_url_edit = QLineEdit(str(self.settings.get("latency_test_url", "https://www.gstatic.com/generate_204")))
        self.latency_timeout_spin = QSpinBox()
        self.latency_timeout_spin.setRange(1, 120)
        self.latency_timeout_spin.setValue(int(self.settings.get("latency_timeout", 5)))

        self.proxy_on_start_check = QCheckBox("启动代理后自动开启系统代理")
        self.proxy_on_start_check.setChecked(bool(self.settings.get("system_proxy_on_start", False)))
        self.proxy_off_stop_check = QCheckBox("停止代理后自动关闭系统代理")
        self.proxy_off_stop_check.setChecked(bool(self.settings.get("disable_system_proxy_on_stop", True)))
        self.minimize_to_tray_check = QCheckBox("最小化到托盘")
        self.minimize_to_tray_check.setChecked(bool(self.settings.get("minimize_to_tray", True)))
        self.close_to_tray_check = QCheckBox("关闭窗口时隐藏到托盘")
        self.close_to_tray_check.setChecked(bool(self.settings.get("close_to_tray", True)))
        self.start_minimized_check = QCheckBox("启动时最小化到托盘")
        self.start_minimized_check.setChecked(bool(self.settings.get("start_minimized", False)))
        self.autostart_check = QCheckBox("开机自启")
        self.autostart_check.setChecked(bool(self.settings.get("autostart_enabled", False)))
        self.auto_connect_check = QCheckBox("启动后自动连接上次节点")
        self.auto_connect_check.setChecked(bool(self.settings.get("auto_connect_on_start", False)))
        self.tray_notifications_check = QCheckBox("显示托盘通知")
        self.tray_notifications_check.setChecked(bool(self.settings.get("tray_show_notifications", True)))
        self.update_check_enabled = QCheckBox("启动时检查更新")
        self.update_check_enabled.setChecked(bool(self.settings.get("update_check_enabled", False)))
        self.update_check_url_edit = QLineEdit(str(self.settings.get("update_check_url", "")))

        form = QFormLayout()
        form.addRow("核心类型", self.core_type_combo)
        form.addRow("核心 exe 路径", core_row)
        form.addRow("生成配置路径", config_row)
        form.addRow("代理模式", self.routing_mode_combo)
        form.addRow("HTTP 端口", self.http_port_spin)
        form.addRow("SOCKS5 端口", self.socks_port_spin)
        form.addRow("延迟测试 URL", self.latency_url_edit)
        form.addRow("延迟测试超时(秒)", self.latency_timeout_spin)
        form.addRow("", self.proxy_on_start_check)
        form.addRow("", self.proxy_off_stop_check)
        form.addRow("", self.minimize_to_tray_check)
        form.addRow("", self.close_to_tray_check)
        form.addRow("", self.start_minimized_check)
        form.addRow("", self.autostart_check)
        form.addRow("", self.auto_connect_check)
        form.addRow("", self.tray_notifications_check)
        form.addRow("", self.update_check_enabled)
        form.addRow("更新检查 URL", self.update_check_url_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(subscription_layout)
        layout.addWidget(buttons)

    def get_settings(self) -> dict:
        updated = dict(self.settings)
        core_type = self.core_type_combo.currentText().split(" ", 1)[0]
        updated.update(
            {
                "core_type": core_type,
                "core_path": self.core_path_edit.text().strip(),
                "config_path": self.config_path_edit.text().strip(),
                "routing_mode": self.routing_mode_combo.currentData() or "global",
                "http_port": self.http_port_spin.value(),
                "socks_port": self.socks_port_spin.value(),
                "subscription_groups": self._get_subscription_groups(),
                "subscription_url": self._legacy_subscription_url(),
                "latency_test_url": self.latency_url_edit.text().strip(),
                "latency_timeout": self.latency_timeout_spin.value(),
                "system_proxy_on_start": self.proxy_on_start_check.isChecked(),
                "disable_system_proxy_on_stop": self.proxy_off_stop_check.isChecked(),
                "minimize_to_tray": self.minimize_to_tray_check.isChecked(),
                "close_to_tray": self.close_to_tray_check.isChecked(),
                "start_minimized": self.start_minimized_check.isChecked(),
                "autostart_enabled": self.autostart_check.isChecked(),
                "auto_connect_on_start": self.auto_connect_check.isChecked(),
                "tray_show_notifications": self.tray_notifications_check.isChecked(),
                "update_check_enabled": self.update_check_enabled.isChecked(),
                "update_check_url": self.update_check_url_edit.text().strip(),
            }
        )
        return updated

    def _load_subscription_groups(self) -> None:
        for group in normalize_subscription_groups(self.settings):
            self._add_subscription_row(group)

    def _add_subscription_row(self, group: dict | None = None) -> None:
        group = group or {"id": str(uuid4()), "name": "", "url": "", "enabled": True}
        row = self.subscription_table.rowCount()
        self.subscription_table.insertRow(row)
        enabled = QTableWidgetItem("")
        enabled.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        enabled.setCheckState(Qt.Checked if group.get("enabled", True) else Qt.Unchecked)
        enabled.setData(Qt.UserRole, group.get("id") or str(uuid4()))
        self.subscription_table.setItem(row, 0, enabled)
        self.subscription_table.setItem(row, 1, QTableWidgetItem(str(group.get("name") or "")))
        self.subscription_table.setItem(row, 2, QTableWidgetItem(str(group.get("url") or "")))

    def _delete_subscription_rows(self) -> None:
        rows = sorted({index.row() for index in self.subscription_table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            self.subscription_table.removeRow(row)

    def _get_subscription_groups(self) -> list[dict]:
        groups: list[dict] = []
        for row in range(self.subscription_table.rowCount()):
            enabled_item = self.subscription_table.item(row, 0)
            name_item = self.subscription_table.item(row, 1)
            url_item = self.subscription_table.item(row, 2)
            url = (url_item.text() if url_item else "").strip()
            if not url:
                continue
            group_id = enabled_item.data(Qt.UserRole) if enabled_item else str(uuid4())
            groups.append(
                {
                    "id": str(group_id or uuid4()),
                    "name": (name_item.text() if name_item else "").strip() or f"订阅 {len(groups) + 1}",
                    "url": url,
                    "enabled": enabled_item.checkState() == Qt.Checked if enabled_item else True,
                }
            )
        return groups

    def _legacy_subscription_url(self) -> str:
        groups = self._get_subscription_groups()
        return groups[0]["url"] if groups else ""

    def _browse_core(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 sing-box.exe", str(Path.cwd()), "Executable (*.exe);;All Files (*)")
        if path:
            self.core_path_edit.setText(path)

    def _browse_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "选择生成配置文件", str(Path.cwd() / "proxy_gui_client" / "data" / "generated_config.json"), "JSON (*.json)")
        if path:
            self.config_path_edit.setText(path)
