from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_cleanup import DuplicateGroup


class CleanupPreviewDialog(QDialog):
    def __init__(self, parent=None, title: str = "清理预览", message: str = "", rows: list[list[str]] | None = None, headers: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 520)

        rows = rows or []
        headers = headers or []
        self.table = QTableWidget(len(rows), len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for row_index, row_values in enumerate(rows):
            for col_index, value in enumerate(row_values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(value))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)


def unavailable_rows(nodes: list[ProxyNode], indexes: list[int]) -> list[list[str]]:
    rows: list[list[str]] = []
    for index in indexes:
        node = nodes[index]
        rows.append(
            [
                str(index + 1),
                node.name,
                node.type,
                node.server,
                "-" if node.tcp_latency_ms is None else f"{node.tcp_latency_ms} ms",
                "-" if node.url_latency_ms is None else f"{node.url_latency_ms} ms",
                node.test_status or "-",
            ]
        )
    return rows


def duplicate_rows(nodes: list[ProxyNode], groups: list[DuplicateGroup]) -> list[list[str]]:
    rows: list[list[str]] = []
    for group_index, group in enumerate(groups, start=1):
        keep = nodes[group.keep_index]
        rows.append([str(group_index), "保留", str(group.keep_index + 1), keep.name, keep.type, keep.server, str(keep.port)])
        for duplicate_index in group.duplicate_indexes:
            node = nodes[duplicate_index]
            rows.append([str(group_index), "删除", str(duplicate_index + 1), node.name, node.type, node.server, str(node.port)])
    return rows
