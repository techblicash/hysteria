from __future__ import annotations

import socket

from proxy_gui_client.core.port_utils import find_free_port, find_free_port_pair, is_port_available


def test_find_free_port_returns_bindable_port() -> None:
    port = find_free_port()

    assert isinstance(port, int)
    assert is_port_available(port) is True


def test_find_free_port_pair_returns_two_different_ports() -> None:
    first, second = find_free_port_pair()

    assert first != second
    assert is_port_available(first) is True
    assert is_port_available(second) is True


def test_is_port_available_returns_false_for_bound_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])

        assert is_port_available(port) is False


def test_port_utils_do_not_raise_unhandled_exception() -> None:
    port = find_free_port("127.0.0.1")

    assert 1 <= port <= 65535

