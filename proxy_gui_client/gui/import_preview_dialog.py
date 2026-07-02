from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from proxy_gui_client.core.import_service import ImportPreview, ImportStrategy


CHECK_COLUMN = 0


class ImportPreviewDialog(QDialog):
    def __init__(self, parent=None, preview: ImportPreview | None = None):
        super().__init__(parent)
        self.preview = preview or ImportPreview()
        self.selected_strategy: ImportStrategy = "cancel"
        self.setWindowTitle("导入配置预览")
        self.resize(1080, 660)

        summary = QLabel(
            f"文件: {self.preview.source_file or '-'} | "
            f"解析节点: {self.preview.total_nodes} | "
            f"新节点: {self.preview.new_count} | "
            f"现有重复: {self.preview.duplicate_existing_count} | "
            f"文件内重复: {self.preview.duplicate_inside_file_count}"
        )

        self.table = QTableWidget(len(self.preview.items), 8)
        self.table.setHorizontalHeaderLabels(["选择", "状态", "名称", "类型", "服务器", "端口", "来源", "说明"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for row, item in enumerate(self.preview.items):
            node = item.node
            check_item = QTableWidgetItem("")
            if item.status == "invalid":
                check_item.setFlags(Qt.ItemIsSelectable)
                check_item.setCheckState(Qt.Unchecked)
            else:
                check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                check_item.setCheckState(Qt.Checked if item.status == "new" else Qt.Unchecked)
            self.table.setItem(row, CHECK_COLUMN, check_item)

            values = [
                item.status,
                node.name,
                node.type,
                node.server,
                str(node.port),
                node.source_file or self.preview.source_file or node.source or "-",
                item.message,
            ]
            for offset, value in enumerate(values, start=1):
                table_item = QTableWidgetItem(value)
                if item.status != "new":
                    table_item.setForeground(Qt.darkYellow)
                self.table.setItem(row, offset, table_item)

        details = QTextEdit()
        details.setReadOnly(True)
        lines: list[str] = []
        if self.preview.errors:
            lines.append("Errors:")
            lines.extend(f"- {error}" for error in self.preview.errors[:20])
        if self.preview.warnings:
            if lines:
                lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in self.preview.warnings[:20])
        if not lines:
            lines.append("没有解析错误或警告。")
        details.setPlainText("\n".join(lines))

        self.select_all_button = QPushButton("全选")
        self.select_none_button = QPushButton("全不选")
        self.select_new_button = QPushButton("只选新增")
        self.select_duplicates_button = QPushButton("只选重复")
        self.import_selected_button = QPushButton("导入勾选项")
        self.new_only_button = QPushButton("只导入新增")
        self.overwrite_button = QPushButton("覆盖已有重复")
        self.rename_button = QPushButton("全部导入并重命名")
        self.cancel_button = QPushButton("取消")

        can_import = any(item.status != "invalid" for item in self.preview.items)
        for button in [
            self.select_all_button,
            self.select_none_button,
            self.select_new_button,
            self.select_duplicates_button,
            self.import_selected_button,
            self.new_only_button,
            self.overwrite_button,
            self.rename_button,
        ]:
            button.setEnabled(can_import)

        self.select_all_button.clicked.connect(self.select_all_importable)
        self.select_none_button.clicked.connect(self.select_none)
        self.select_new_button.clicked.connect(self.select_new)
        self.select_duplicates_button.clicked.connect(self.select_duplicate_existing)
        self.import_selected_button.clicked.connect(lambda: self._accept_strategy("import_selected"))
        self.new_only_button.clicked.connect(lambda: self._accept_strategy("import_new_only"))
        self.overwrite_button.clicked.connect(lambda: self._accept_strategy("overwrite_existing"))
        self.rename_button.clicked.connect(lambda: self._accept_strategy("import_all_rename"))
        self.cancel_button.clicked.connect(self.reject)

        selection_buttons = QHBoxLayout()
        selection_buttons.addWidget(self.select_all_button)
        selection_buttons.addWidget(self.select_none_button)
        selection_buttons.addWidget(self.select_new_button)
        selection_buttons.addWidget(self.select_duplicates_button)
        selection_buttons.addStretch(1)

        strategy_buttons = QHBoxLayout()
        strategy_buttons.addStretch(1)
        strategy_buttons.addWidget(self.import_selected_button)
        strategy_buttons.addWidget(self.new_only_button)
        strategy_buttons.addWidget(self.overwrite_button)
        strategy_buttons.addWidget(self.rename_button)
        strategy_buttons.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addWidget(self.table, 3)
        layout.addLayout(selection_buttons)
        layout.addWidget(QLabel("Warnings / Errors"))
        layout.addWidget(details, 1)
        layout.addLayout(strategy_buttons)

    def selected_indexes(self) -> set[int]:
        selected: set[int] = set()
        for row, item in enumerate(self.preview.items):
            check_item = self.table.item(row, CHECK_COLUMN)
            if item.status != "invalid" and check_item and check_item.checkState() == Qt.Checked:
                selected.add(row)
        return selected

    def select_all_importable(self) -> None:
        self._set_checked(lambda item: item.status != "invalid")

    def select_none(self) -> None:
        self._set_checked(lambda item: False)

    def select_new(self) -> None:
        self._set_checked(lambda item: item.status == "new")

    def select_duplicate_existing(self) -> None:
        self._set_checked(lambda item: item.status == "duplicate_existing")

    def _set_checked(self, predicate) -> None:
        for row, item in enumerate(self.preview.items):
            check_item = self.table.item(row, CHECK_COLUMN)
            if not check_item or item.status == "invalid":
                continue
            check_item.setCheckState(Qt.Checked if predicate(item) else Qt.Unchecked)

    def _accept_strategy(self, strategy: ImportStrategy) -> None:
        self.selected_strategy = strategy
        self.accept()
