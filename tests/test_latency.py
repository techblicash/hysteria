from __future__ import annotations

import socket

from proxy_gui_client.core.latency import try_tcp_latency_ms
from proxy_gui_client.core.models import ProxyNode


def unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_unreachable_port_returns_failure_result() -> None:
    node = ProxyNode(name="closed", type="trojan", server="127.0.0.1", port=unused_local_port(), password="p")

    ok, latency, error = try_tcp_latency_ms(node, timeout_seconds=0.2)

    assert ok is False
    assert latency is None
    assert error


def test_latency_wrapper_does_not_raise_unhandled_exception() -> None:
    node = ProxyNode(name="invalid", type="trojan", server="256.256.256.256", port=443, password="p")

    ok, latency, error = try_tcp_latency_ms(node, timeout_seconds=0.2)

    assert ok is False
    assert latency is None
    assert isinstance(error, str)

