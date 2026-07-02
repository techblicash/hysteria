from __future__ import annotations

import threading
from collections import deque
from typing import TextIO


class ProcessOutputBuffer:
    """Thread-safe bounded stdout/stderr collector for short diagnostics."""

    def __init__(self, max_lines: int = 200, tail_lines: int = 20, tail_chars: int = 4000):
        self.max_lines = max_lines
        self.tail_lines = tail_lines
        self.tail_chars = tail_chars
        self._stdout: deque[str] = deque(maxlen=max_lines)
        self._stderr: deque[str] = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def append_stdout(self, text: str) -> None:
        self._append(self._stdout, text)

    def append_stderr(self, text: str) -> None:
        self._append(self._stderr, text)

    def stdout_tail(self) -> str:
        return self._tail(self._stdout)

    def stderr_tail(self) -> str:
        return self._tail(self._stderr)

    def start_reader_threads(self, stdout: TextIO | None, stderr: TextIO | None) -> None:
        if stdout is not None:
            self._start_reader(stdout, self.append_stdout)
        if stderr is not None:
            self._start_reader(stderr, self.append_stderr)

    def drain_remaining(self, stdout: TextIO | None, stderr: TextIO | None) -> None:
        for pipe, append in [(stdout, self.append_stdout), (stderr, self.append_stderr)]:
            if pipe is None:
                continue
            try:
                remaining = pipe.read()
            except Exception:
                remaining = ""
            if remaining:
                append(remaining)

    def _start_reader(self, pipe: TextIO, append) -> None:
        def read_loop() -> None:
            try:
                for line in iter(pipe.readline, ""):
                    append(line)
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        thread = threading.Thread(target=read_loop, daemon=True)
        self._threads.append(thread)
        thread.start()

    def _append(self, target: deque[str], text: str) -> None:
        lines = text.splitlines()
        if text.endswith(("\n", "\r")):
            pass
        elif lines:
            lines[-1] = lines[-1]
        else:
            lines = [text]
        with self._lock:
            for line in lines:
                target.append(line)

    def _tail(self, source: deque[str]) -> str:
        with self._lock:
            lines = list(source)[-self.tail_lines :]
        text = "\n".join(lines)
        if len(text) > self.tail_chars:
            return text[-self.tail_chars :]
        return text

