from __future__ import annotations

import socket


class PortAllocationError(RuntimeError):
    pass


def find_free_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for a currently free TCP port."""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, 0))
            return int(sock.getsockname()[1])
    except OSError as exc:
        raise PortAllocationError(f"Unable to allocate a free port on {host}: {exc}") from exc


def find_free_port_pair(host: str = "127.0.0.1") -> tuple[int, int]:
    """Return two different currently free TCP ports."""

    first = find_free_port(host)
    for _ in range(20):
        second = find_free_port(host)
        if second != first:
            return first, second
    raise PortAllocationError(f"Unable to allocate two different free ports on {host}")


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Return whether a local TCP port can be bound right now."""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, int(port)))
            return True
    except (OSError, ValueError):
        return False

