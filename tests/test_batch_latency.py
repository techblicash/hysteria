from __future__ import annotations

import threading
import time

from proxy_gui_client.core.batch_latency import CancellationToken, run_batch_tcp_tests, run_batch_url_tests
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.proxy_latency import UrlLatencyResult


def node(name: str) -> ProxyNode:
    return ProxyNode(name=name, type="trojan", server="example.com", port=443, password="p")


def test_batch_tcp_processes_multiple_nodes() -> None:
    updates = []

    summary = run_batch_tcp_tests(
        [(0, node("a")), (1, node("b"))],
        tcp_func=lambda n, timeout: 10 if n.name == "a" else 20,
        on_result=updates.append,
    )

    assert summary.total == 2
    assert summary.success_count == 2
    assert summary.failure_count == 0
    assert summary.average_latency_ms == 15
    assert len(updates) == 2


def test_single_node_failure_does_not_stop_batch() -> None:
    def fake_tcp(n, timeout):
        if n.name == "bad":
            raise OSError("closed")
        return 12

    summary = run_batch_tcp_tests([(0, node("bad")), (1, node("ok"))], tcp_func=fake_tcp)

    assert summary.success_count == 1
    assert summary.failure_count == 1


def test_cancel_token_prevents_unstarted_tasks() -> None:
    token = CancellationToken()
    token.cancel()

    summary = run_batch_tcp_tests([(0, node("a")), (1, node("b"))], cancel_token=token, tcp_func=lambda n, timeout: 1)

    assert summary.cancelled is True
    assert summary.success_count == 0
    assert summary.failure_count == 2


def test_batch_summary_contains_counts() -> None:
    summary = run_batch_tcp_tests([(0, node("a"))], tcp_func=lambda n, timeout: 7)

    assert summary.total == 1
    assert summary.success_count == 1
    assert summary.failure_count == 0
    assert summary.fastest_node_index == 0
    assert summary.fastest_latency_ms == 7


def test_url_batch_respects_max_concurrency() -> None:
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_url(n, settings):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return UrlLatencyResult(True, latency_ms=10)

    summary = run_batch_url_tests([(i, node(str(i))) for i in range(6)], {}, max_workers=2, url_func=fake_url)

    assert summary.success_count == 6
    assert max_active <= 2


def test_batch_calls_result_callback() -> None:
    updates = []

    run_batch_tcp_tests([(0, node("a"))], tcp_func=lambda n, timeout: 5, on_result=updates.append)

    assert len(updates) == 1
    assert updates[0].node_index == 0
    assert updates[0].latency_ms == 5

