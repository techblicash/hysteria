from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from .adapters import get_core_adapter
from .models import ProxyNode
from .storage import resolve_app_path


LogCallback = Callable[[str], None]
ExitCallback = Callable[[int], None]


class CoreManager:
    """Owns the external proxy core process and streams stdout/stderr."""

    def __init__(self, log_callback: LogCallback | None = None, exit_callback: ExitCallback | None = None):
        self.log_callback = log_callback
        self.exit_callback = exit_callback
        self.process: subprocess.Popen[str] | None = None
        self._reader_threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, node: ProxyNode, settings: dict) -> Path:
        with self._lock:
            if self.is_running:
                raise RuntimeError("代理核心已在运行，请先停止当前进程")
            adapter = get_core_adapter(settings.get("core_type", "sing-box"))
            core_path = str(settings.get("core_path") or "").strip()
            executable = resolve_app_path(core_path)
            adapter.validate_core_path(str(executable))
            config_path = resolve_app_path(str(settings.get("config_path") or "proxy_gui_client/data/generated_config.json"))
            config_path = adapter.generate_config(node, settings, config_path)
            if not config_path.exists():
                raise RuntimeError(f"配置文件生成失败: {config_path}")

            command = adapter.build_start_command(str(executable), str(config_path))
            self._log(f"启动核心 ({adapter.name}): {' '.join(command)}")
            try:
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(executable.parent),
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
            except OSError as exc:
                self.process = None
                raise RuntimeError(f"启动代理核心失败: {exc}") from exc
            self._start_reader("stdout", self.process.stdout)
            self._start_reader("stderr", self.process.stderr)
            threading.Thread(target=self._watch_exit, daemon=True).start()
            time.sleep(0.2)
            if self.process and self.process.poll() is not None:
                code = self.process.returncode
                self.process = None
                raise RuntimeError(f"代理核心启动后立即退出，退出码: {code}。请检查核心路径、配置内容或端口占用。")
            return config_path

    def stop(self) -> None:
        with self._lock:
            if not self.process:
                return
            if self.process.poll() is None:
                self._log("正在停止代理核心...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._log("核心未及时退出，强制结束进程")
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None

    def _start_reader(self, name: str, pipe) -> None:
        if pipe is None:
            return

        def read_loop() -> None:
            for line in iter(pipe.readline, ""):
                self._log(f"[{name}] {line.rstrip()}")
            pipe.close()

        thread = threading.Thread(target=read_loop, daemon=True)
        self._reader_threads.append(thread)
        thread.start()

    def _watch_exit(self) -> None:
        process = self.process
        if not process:
            return
        code = process.wait()
        self._log(f"代理核心已退出，退出码: {code}")
        if self.exit_callback:
            self.exit_callback(code)

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)
