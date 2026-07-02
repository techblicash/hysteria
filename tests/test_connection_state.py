from __future__ import annotations

from proxy_gui_client.core.connection_state import ConnectionState


def test_initial_state_is_disconnected() -> None:
    state = ConnectionState()

    assert state.status == "disconnected"
    assert state.display_text() == "未连接"


def test_starting_to_running() -> None:
    state = ConnectionState()
    state.set_starting("A")
    state.set_running("A")

    assert state.status == "running"
    assert state.display_text() == "已连接：A"


def test_starting_to_error() -> None:
    state = ConnectionState()
    state.set_starting("A")
    state.set_error("bad config")

    assert state.status == "error"
    assert "bad config" in state.display_text()


def test_running_to_stopping_to_disconnected() -> None:
    state = ConnectionState()
    state.set_running("A")
    state.set_stopping()
    assert state.display_text() == "正在停止"
    state.set_disconnected()

    assert state.status == "disconnected"


def test_display_text_for_gui() -> None:
    state = ConnectionState(status="running", node_name="Node")

    assert state.display_text() == "已连接：Node"
