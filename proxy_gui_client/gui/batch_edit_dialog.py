from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from proxy_gui_client.core.node_batch_ops import BatchEditOptions


class BatchEditDialog(QDialog):
    def __init__(self, parent=None, count: int = 0):
        super().__init__(parent)
        self.setWindowTitle("批量编辑节点")
        self.resize(460, 260)

        self.source_check = QCheckBox("修改 source")
        self.source_combo = QComboBox()
        self.source_combo.addItems(["manual", "subscription", "config_file", "unknown"])

        self.source_file_check = QCheckBox("修改 source_file")
        self.source_file_action = QComboBox()
        self.source_file_action.addItem("清空", "clear")
        self.source_file_action.addItem("设置为指定文本", "set")
        self.source_file_edit = QLineEdit()

        self.prefix_check = QCheckBox("添加名称前缀")
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("[HK] ")

        self.suffix_check = QCheckBox("添加名称后缀")
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText(" - backup")

        self.clear_tests_check = QCheckBox("清除延迟测试结果")

        form = QFormLayout()
        form.addRow(QLabel(f"将影响 {count} 个节点。只会修改勾选的项目。"))
        form.addRow(self.source_check, self.source_combo)
        form.addRow(self.source_file_check, self.source_file_action)
        form.addRow("source_file 文本", self.source_file_edit)
        form.addRow(self.prefix_check, self.prefix_edit)
        form.addRow(self.suffix_check, self.suffix_edit)
        form.addRow("", self.clear_tests_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_options(self) -> BatchEditOptions:
        source = self.source_combo.currentText() if self.source_check.isChecked() else None
        source_file_action = self.source_file_action.currentData() if self.source_file_check.isChecked() else "keep"
        return BatchEditOptions(
            source=source,
            source_file_action=source_file_action,
            source_file_value=self.source_file_edit.text().strip(),
            name_prefix=self.prefix_edit.text() if self.prefix_check.isChecked() else "",
            name_suffix=self.suffix_edit.text() if self.suffix_check.isChecked() else "",
            clear_test_results=self.clear_tests_check.isChecked(),
        )
