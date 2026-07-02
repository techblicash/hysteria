from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)
from uuid import uuid4

from proxy_gui_client.core.models import ProxyNode


class NodeEditorDialog(QDialog):
    def __init__(self, parent=None, node: ProxyNode | None = None):
        super().__init__(parent)
        self.setWindowTitle("编辑节点" if node else "添加节点")
        self._node = node

        self.name_edit = QLineEdit(node.name if node else "")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["vmess", "vless", "trojan", "shadowsocks"])
        if node:
            index = self.type_combo.findText(node.type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

        self.server_edit = QLineEdit(node.server if node else "")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(node.port) if node and node.port else 443)

        self.uuid_edit = QLineEdit(node.uuid if node else "")
        self.password_edit = QLineEdit(node.password if node else "")
        self.method_edit = QLineEdit(node.method if node else "")
        self.security_edit = QLineEdit(node.security if node else "")
        self.network_edit = QLineEdit(node.network if node else "tcp")
        self.path_edit = QLineEdit(node.path if node else "")
        self.host_edit = QLineEdit(node.host if node else "")
        self.sni_edit = QLineEdit(node.sni if node else "")
        self.flow_edit = QLineEdit(node.flow if node else "")
        self.tls_check = QCheckBox("启用 TLS")
        self.tls_check.setChecked(bool(node.tls) if node else False)

        form = QFormLayout()
        form.addRow("名称", self.name_edit)
        form.addRow("类型", self.type_combo)
        form.addRow("服务器", self.server_edit)
        form.addRow("端口", self.port_spin)
        form.addRow("UUID / 用户 ID", self.uuid_edit)
        form.addRow("密码 / 密钥", self.password_edit)
        form.addRow("SS 加密方法", self.method_edit)
        form.addRow("安全类型", self.security_edit)
        form.addRow("传输协议", self.network_edit)
        form.addRow("路径", self.path_edit)
        form.addRow("Host", self.host_edit)
        form.addRow("SNI", self.sni_edit)
        form.addRow("Flow", self.flow_edit)
        form.addRow("", self.tls_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_node(self) -> ProxyNode:
        node_id = self._node.id if self._node else str(uuid4())
        source = self._node.source if self._node else "manual"
        latency = self._node.latency_ms if self._node else None
        return ProxyNode(
            id=node_id,
            name=self.name_edit.text().strip() or self.server_edit.text().strip() or "未命名节点",
            type=self.type_combo.currentText(),
            server=self.server_edit.text().strip(),
            port=self.port_spin.value(),
            uuid=self.uuid_edit.text().strip(),
            password=self.password_edit.text().strip(),
            method=self.method_edit.text().strip(),
            security=self.security_edit.text().strip(),
            network=self.network_edit.text().strip() or "tcp",
            path=self.path_edit.text().strip(),
            host=self.host_edit.text().strip(),
            sni=self.sni_edit.text().strip(),
            flow=self.flow_edit.text().strip(),
            tls=self.tls_check.isChecked(),
            source=source,
            source_file=self._node.source_file if self._node else "",
            imported_at=self._node.imported_at if self._node else "",
            latency_ms=latency,
            tcp_latency_ms=self._node.tcp_latency_ms if self._node else None,
            url_latency_ms=self._node.url_latency_ms if self._node else None,
            test_status=self._node.test_status if self._node else "",
            last_tested_at=self._node.last_tested_at if self._node else "",
            extra=self._node.extra if self._node else {},
        )
