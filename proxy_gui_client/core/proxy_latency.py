from __future__ import annotations

import subprocess
import time
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests

from proxy_gui_client.core.adapters.base import CoreConfigError, CorePathError
from proxy_gui_client.core.adapters import get_core_adapter
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.port_utils import find_free_port_pair
from proxy_gui_client.core.process_utils import ProcessOutputBuffer
from proxy_gui_client.core.storage import data_dir, resolve_app_path


logger = logging.getLogger(__name__)


@dataclass
class UrlLatencyResult:
    success: bool
    latency_ms: int | None = None
    error: str | None = None
    error_category: str | None = None
    http_port: int | None = None
    socks_port: int | None = None
    test_url: str | None = None
    core_stdout_tail: str | None = None
    core_stderr_tail: str | None = None
    config_path: str | None = None

    @property
    def ok(self) -> bool:
        return self.success


PopenFactory = Callable[..., subprocess.Popen]
RequestGet = Callable[..., Any]


def url_proxy_latency_ms(
    node: ProxyNode,
    settings: dict[str, Any],
    popen_factory: PopenFactory = subprocess.Popen,
    request_get: RequestGet = requests.get,
    startup_wait_seconds: float = 0.3,
) -> UrlLatencyResult:
    """Measure URL latency through a temporary local proxy core process."""

    process: subprocess.Popen | None = None
    config_path: Path | None = None
    temp_http_port: int | None = None
    temp_socks_port: int | None = None
    test_url: str | None = None
    output = ProcessOutputBuffer()
    try:
        adapter = get_core_adapter(settings.get("core_type", "sing-box"))
        core_path = str(settings.get("core_path") or "").strip()
        core_path = str(resolve_app_path(core_path))
        try:
            adapter.validate_core_path(core_path)
        except CorePathError as exc:
            return UrlLatencyResult(False, error=f"core_path_missing: {exc}", error_category="core_path_missing")

        timeout = float(settings.get("latency_timeout") or settings.get("test_timeout_seconds") or 5)
        test_url = str(settings.get("latency_test_url") or "https://www.gstatic.com/generate_204").strip()
        if not test_url:
            return UrlLatencyResult(False, error="request_failed: latency test URL is empty", error_category="request_failed")

        temp_http_port, temp_socks_port = find_free_port_pair()
        temp_settings = dict(settings)
        temp_settings["http_port"] = temp_http_port
        temp_settings["socks_port"] = temp_socks_port
        temp_settings["routing_mode"] = "global"

        tmp_dir = data_dir() / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_path = tmp_dir / f"latency_test_{timestamp}_{uuid.uuid4().hex[:8]}.json"

        try:
            adapter.generate_config(node, temp_settings, config_path)
        except CoreConfigError as exc:
            return UrlLatencyResult(
                False,
                error=f"config_generation_failed: {exc}",
                error_category="config_generation_failed",
                http_port=temp_http_port,
                socks_port=temp_socks_port,
                test_url=test_url,
                config_path=str(config_path),
            )
        command = adapter.build_start_command(core_path, str(config_path))
        try:
            process = popen_factory(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(Path(core_path).expanduser().parent),
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except OSError as exc:
            return UrlLatencyResult(
                False,
                error=f"core_start_failed: failed to start temporary core: {exc}",
                error_category="core_start_failed",
                http_port=temp_http_port,
                socks_port=temp_socks_port,
                test_url=test_url,
                config_path=str(config_path),
            )
        output.start_reader_threads(process.stdout, process.stderr)

        time.sleep(startup_wait_seconds)
        if process.poll() is not None:
            output.drain_remaining(process.stdout, process.stderr)
            stdout_tail = output.stdout_tail()
            stderr_tail = output.stderr_tail()
            category = _classify_core_start_failure(stdout_tail, stderr_tail)
            return UrlLatencyResult(
                False,
                error=(
                    f"{category}: temporary core exited immediately with code {process.returncode}. "
                    f"Check config or temporary port usage (HTTP {temp_http_port}, SOCKS {temp_socks_port})."
                ),
                error_category=category,
                http_port=temp_http_port,
                socks_port=temp_socks_port,
                test_url=test_url,
                core_stdout_tail=stdout_tail,
                core_stderr_tail=stderr_tail,
                config_path=str(config_path),
            )

        proxies = {
            "http": f"http://127.0.0.1:{temp_http_port}",
            "https": f"http://127.0.0.1:{temp_http_port}",
        }
        start = time.perf_counter()
        try:
            response = request_get(test_url, proxies=proxies, timeout=timeout)
        except requests.exceptions.Timeout as exc:
            return _failure_result(
                "timeout",
                f"timeout: request to {test_url} timed out after {timeout} seconds: {exc}",
                temp_http_port,
                temp_socks_port,
                test_url,
                config_path,
                output,
            )
        except requests.exceptions.RequestException as exc:
            return _failure_result(
                "request_failed",
                f"request_failed: failed to request {test_url}: {exc}",
                temp_http_port,
                temp_socks_port,
                test_url,
                config_path,
                output,
            )
        elapsed = max(1, int((time.perf_counter() - start) * 1000))
        try:
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            return _failure_result(
                "request_failed",
                f"request_failed: test URL returned an error: {exc}",
                temp_http_port,
                temp_socks_port,
                test_url,
                config_path,
                output,
            )
        return UrlLatencyResult(
            True,
            latency_ms=elapsed,
            http_port=temp_http_port,
            socks_port=temp_socks_port,
            test_url=test_url,
            core_stdout_tail=output.stdout_tail(),
            core_stderr_tail=output.stderr_tail(),
            config_path=str(config_path),
        )
    except Exception as exc:
        return UrlLatencyResult(
            False,
            error=f"request_failed: {exc}",
            error_category="request_failed",
            http_port=temp_http_port,
            socks_port=temp_socks_port,
            test_url=test_url,
            core_stdout_tail=output.stdout_tail(),
            core_stderr_tail=output.stderr_tail(),
            config_path=str(config_path) if config_path else None,
        )
    finally:
        if process is not None:
            _stop_process(process)
        if config_path is not None:
            _cleanup_config(config_path)


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _cleanup_config(config_path: Path) -> None:
    try:
        if config_path.exists():
            config_path.unlink()
    except OSError as exc:
        logger.warning("Failed to clean temporary latency config %s: %s", config_path, exc)


def _failure_result(
    category: str,
    error: str,
    http_port: int | None,
    socks_port: int | None,
    test_url: str | None,
    config_path: Path | None,
    output: ProcessOutputBuffer,
) -> UrlLatencyResult:
    return UrlLatencyResult(
        False,
        error=error,
        error_category=category,
        http_port=http_port,
        socks_port=socks_port,
        test_url=test_url,
        core_stdout_tail=output.stdout_tail(),
        core_stderr_tail=output.stderr_tail(),
        config_path=str(config_path) if config_path else None,
    )


def _classify_core_start_failure(stdout_tail: str, stderr_tail: str) -> str:
    text = f"{stdout_tail}\n{stderr_tail}".lower()
    port_markers = [
        "address already in use",
        "only one usage of each socket address",
        "bind:",
        "listen tcp",
        "cannot assign requested address",
    ]
    if any(marker in text for marker in port_markers):
        return "port_conflict"
    config_markers = ["parse", "decode", "config", "invalid", "missing", "unknown"]
    if any(marker in text for marker in config_markers):
        return "config_generation_failed"
    return "core_start_failed"
