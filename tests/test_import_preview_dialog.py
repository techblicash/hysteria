from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from proxy_gui_client.core.import_service import ImportPreview, ImportPreviewItem
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.gui.import_preview_dialog import ImportPreviewDialog


def node(name: str) -> ProxyNode:
    return ProxyNode(name=name, type="trojan", server="example.com", port=443, password="p")


def preview() -> ImportPreview:
    return ImportPreview(
        items=[
            ImportPreviewItem(node=node("new"), status="new", message="New node"),
            ImportPreviewItem(node=node("dup"), status="duplicate_existing", duplicate_existing_index=0, message="Duplicate"),
            ImportPreviewItem(node=node("invalid"), status="invalid", message="Invalid"),
        ],
        total_nodes=3,
        new_count=1,
        duplicate_existing_count=1,
        source_file="demo.yaml",
    )


def test_import_preview_dialog_can_be_constructed() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = ImportPreviewDialog(preview=preview())
    try:
        assert dialog.table.rowCount() == 3
    finally:
        dialog.close()
        app.processEvents()


def test_first_column_is_selection_column() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = ImportPreviewDialog(preview=preview())
    try:
        assert dialog.table.horizontalHeaderItem(0).text() == "选择"
    finally:
        dialog.close()
        app.processEvents()


def test_default_check_states() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = ImportPreviewDialog(preview=preview())
    try:
        assert dialog.table.item(0, 0).checkState() == Qt.Checked
        assert dialog.table.item(1, 0).checkState() == Qt.Unchecked
        assert not (dialog.table.item(2, 0).flags() & Qt.ItemIsUserCheckable)
    finally:
        dialog.close()
        app.processEvents()


def test_selection_buttons_exist() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = ImportPreviewDialog(preview=preview())
    try:
        assert isinstance(dialog.select_all_button, QPushButton)
        assert isinstance(dialog.select_none_button, QPushButton)
        assert isinstance(dialog.select_new_button, QPushButton)
        assert isinstance(dialog.select_duplicates_button, QPushButton)
        assert isinstance(dialog.import_selected_button, QPushButton)
    finally:
        dialog.close()
        app.processEvents()


def test_can_read_selected_indexes() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = ImportPreviewDialog(preview=preview())
    try:
        assert dialog.selected_indexes() == {0}
        dialog.select_duplicate_existing()
        assert dialog.selected_indexes() == {1}
        dialog.select_none()
        assert dialog.selected_indexes() == set()
        dialog.select_all_importable()
        assert dialog.selected_indexes() == {0, 1}
    finally:
        dialog.close()
        app.processEvents()
