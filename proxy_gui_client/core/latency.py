from __future__ import annotations

import socket
import time

from .models import ProxyNode


def tcp_latency_ms(node: ProxyNode, timeout_seconds: float = 5.0) -> int:
    """Return TCP connect latency in milliseconds, or raise the socket error."""

    start = time.perf_counter()
    with socket.create_connection((node.server, int(node.port)), timeout=timeout_seconds):
        pass
    return max(1, int((time.perf_counter() - start) * 1000))


def try_tcp_latency_ms(node: ProxyNode, timeout_seconds: float = 5.0) -> tuple[bool, int | None, str | None]:
    """Return a non-throwing latency result for callers that need stable UI/test flow."""

    try:
        return True, tcp_latency_ms(node, timeout_seconds), None
    except Exception as exc:
        return False, None, str(exc)
