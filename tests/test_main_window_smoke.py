from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QApplication, QPushButton


def test_main_window_table_selection_and_batch_controls(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))

    app = QApplication.instance() or QApplication([])
    from proxy_gui_client.gui.main_window import MainWindow

    window = MainWindow()
    try:
        assert window.node_table.selectionMode() == QAbstractItemView.ExtendedSelection
        assert window.batch_scope_combo is not None
        assert window.batch_scope_combo.findData("filtered") >= 0
        assert window.batch_scope_combo.findData("selected") >= 0
        assert isinstance(window.clear_tests_button, QPushButton)
        assert isinstance(window.delete_selected_button, QPushButton)
        assert isinstance(window.export_selected_button, QPushButton)
        assert isinstance(window.backup_nodes_button, QPushButton)
        assert isinstance(window.restore_nodes_button, QPushButton)
        assert isinstance(window.batch_edit_button, QPushButton)
        assert isinstance(window.cleanup_unavailable_button, QPushButton)
        assert isinstance(window.cleanup_duplicates_button, QPushButton)
        assert window.tray_controller is not None

        from proxy_gui_client.gui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(window, window.settings)
        try:
            assert dialog.minimize_to_tray_check is not None
            assert dialog.close_to_tray_check is not None
            assert dialog.start_minimized_check is not None
            assert dialog.autostart_check is not None
            assert dialog.auto_connect_check is not None
            assert dialog.tray_notifications_check is not None
            assert dialog.subscription_table is not None
            assert dialog.add_subscription_button is not None
            assert dialog.delete_subscription_button is not None
            assert dialog.routing_mode_combo.findData("global") >= 0
            assert dialog.routing_mode_combo.findData("rule") >= 0
            assert dialog.routing_mode_combo.findData("direct") >= 0
            assert dialog.update_check_enabled is not None
            assert dialog.update_check_url_edit is not None
        finally:
            dialog.close()
    finally:
        window.force_quit = True
        window.close()
        app.processEvents()
