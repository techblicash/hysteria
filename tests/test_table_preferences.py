from __future__ import annotations

from proxy_gui_client.core.storage import load_settings, save_settings
from proxy_gui_client.core.table_preferences import (
    DEFAULT_NODE_FILTER_PREFERENCES,
    DEFAULT_TABLE_COLUMN_WIDTHS,
    normalize_filter_preferences,
    normalize_table_column_widths,
    update_filter_preference,
    update_table_column_width,
)


def test_old_settings_get_default_table_column_widths() -> None:
    widths = normalize_table_column_widths({})

    assert widths == DEFAULT_TABLE_COLUMN_WIDTHS


def test_old_settings_get_default_filter_preferences() -> None:
    preferences = normalize_filter_preferences({})

    assert preferences == DEFAULT_NODE_FILTER_PREFERENCES


def test_saved_column_width_can_be_loaded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))

    settings = update_table_column_width({}, "name", 260)
    save_settings(settings)

    loaded = load_settings()
    assert loaded["table_column_widths"]["name"] == 260


def test_saved_filter_preferences_can_be_loaded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROXY_GUI_CLIENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PROXY_GUI_CLIENT_LOG_DIR", str(tmp_path / "logs"))

    settings = update_filter_preference({}, "sort_by", "tcp_latency")
    settings = update_filter_preference(settings, "batch_scope", "selected")
    save_settings(settings)

    loaded = load_settings()
    assert loaded["node_filter_preferences"]["sort_by"] == "tcp_latency"
    assert loaded["node_filter_preferences"]["batch_scope"] == "selected"


def test_invalid_table_preference_fields_fall_back_to_defaults() -> None:
    widths = normalize_table_column_widths({"table_column_widths": {"name": "bad", "port": 5}})

    assert widths["name"] == DEFAULT_TABLE_COLUMN_WIDTHS["name"]
    assert widths["port"] == DEFAULT_TABLE_COLUMN_WIDTHS["port"]


def test_invalid_filter_preference_fields_fall_back_to_defaults() -> None:
    preferences = normalize_filter_preferences(
        {
            "node_filter_preferences": {
                "node_type": "bad",
                "source": "bad",
                "availability": "bad",
                "sort_by": "bad",
                "batch_scope": "bad",
            }
        }
    )

    assert preferences["node_type"] == "all"
    assert preferences["source"] == "all"
    assert preferences["availability"] == "all"
    assert preferences["sort_by"] == "default"
    assert preferences["batch_scope"] == "filtered"
