from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable, Iterable

from proxy_gui_client.core.latency import tcp_latency_ms
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.proxy_latency import UrlLatencyResult, url_proxy_latency_ms


@dataclass
class BatchLatencyUpdate:
    node_index: int
    ok: bool
    kind: str
    latency_ms: int | None = None
    error: str = ""


@dataclass
class BatchLatencySummary:
    total: int
    success_count: int
    failure_count: int
    average_latency_ms: int | None = None
    fastest_node_index: int | None = None
    fastest_latency_ms: int | None = None
    cancelled: bool = False


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


ResultCallback = Callable[[BatchLatencyUpdate], None]


def run_batch_tcp_tests(
    indexed_nodes: Iterable[tuple[int, ProxyNode]],
    timeout_seconds: float = 5.0,
    max_workers: int = 8,
    on_result: ResultCallback | None = None,
    cancel_token: CancellationToken | None = None,
    tcp_func: Callable[[ProxyNode, float], int] = tcp_latency_ms,
) -> BatchLatencySummary:
    token = cancel_token or CancellationToken()
    tasks = list(indexed_nodes)

    def run_one(node: ProxyNode) -> int:
        return tcp_func(node, timeout_seconds)

    return _run_batch(tasks, "tcp", max_workers, token, on_result, run_one)


def run_batch_url_tests(
    indexed_nodes: Iterable[tuple[int, ProxyNode]],
    settings: dict,
    max_workers: int = 2,
    on_result: ResultCallback | None = None,
    cancel_token: CancellationToken | None = None,
    url_func: Callable[[ProxyNode, dict], UrlLatencyResult] = url_proxy_latency_ms,
) -> BatchLatencySummary:
    token = cancel_token or CancellationToken()
    tasks = list(indexed_nodes)

    def run_one(node: ProxyNode) -> int:
        result = url_func(node, settings)
        if result.ok and result.latency_ms is not None:
            return result.latency_ms
        raise RuntimeError(result.error or "URL latency test failed")

    return _run_batch(tasks, "url", max_workers, token, on_result, run_one)


def _run_batch(
    tasks: list[tuple[int, ProxyNode]],
    kind: str,
    max_workers: int,
    token: CancellationToken,
    on_result: ResultCallback | None,
    run_one: Callable[[ProxyNode], int],
) -> BatchLatencySummary:
    work: queue.Queue[tuple[int, ProxyNode]] = queue.Queue()
    for task in tasks:
        work.put(task)

    lock = threading.Lock()
    latencies: list[tuple[int, int]] = []
    failures = 0
    started = 0

    def worker() -> None:
        nonlocal failures, started
        while not token.is_cancelled():
            try:
                node_index, node = work.get_nowait()
            except queue.Empty:
                return
            with lock:
                started += 1
            try:
                latency = run_one(node)
                update = BatchLatencyUpdate(node_index=node_index, ok=True, kind=kind, latency_ms=latency)
                with lock:
                    latencies.append((node_index, latency))
            except Exception as exc:
                update = BatchLatencyUpdate(node_index=node_index, ok=False, kind=kind, error=str(exc))
                with lock:
                    failures += 1
            if on_result:
                on_result(update)
            work.task_done()

    workers = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, min(max_workers, len(tasks) or 1)))]
    for thread in workers:
        thread.start()
    for thread in workers:
        thread.join()

    success_count = len(latencies)
    failure_count = failures
    if token.is_cancelled():
        failure_count += max(0, len(tasks) - started)
    fastest = min(latencies, key=lambda item: item[1], default=None)
    average = int(sum(latency for _, latency in latencies) / success_count) if success_count else None
    return BatchLatencySummary(
        total=len(tasks),
        success_count=success_count,
        failure_count=failure_count,
        average_latency_ms=average,
        fastest_node_index=fastest[0] if fastest else None,
        fastest_latency_ms=fastest[1] if fastest else None,
        cancelled=token.is_cancelled(),
    )

