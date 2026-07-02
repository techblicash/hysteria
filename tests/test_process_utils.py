from __future__ import annotations

from proxy_gui_client.core.process_utils import ProcessOutputBuffer


def test_empty_log_tail_returns_empty_string() -> None:
    buffer = ProcessOutputBuffer()

    assert buffer.stdout_tail() == ""
    assert buffer.stderr_tail() == ""


def test_stdout_stderr_tail_truncates_by_lines() -> None:
    buffer = ProcessOutputBuffer(max_lines=10, tail_lines=3, tail_chars=1000)

    for index in range(8):
        buffer.append_stdout(f"stdout-{index}\n")
        buffer.append_stderr(f"stderr-{index}\n")

    assert buffer.stdout_tail() == "stdout-5\nstdout-6\nstdout-7"
    assert buffer.stderr_tail() == "stderr-5\nstderr-6\nstderr-7"


def test_long_log_tail_truncates_by_chars() -> None:
    buffer = ProcessOutputBuffer(max_lines=100, tail_lines=100, tail_chars=50)
    buffer.append_stderr("x" * 200)

    tail = buffer.stderr_tail()

    assert len(tail) == 50
    assert tail == "x" * 50


def test_buffer_does_not_grow_without_bound() -> None:
    buffer = ProcessOutputBuffer(max_lines=5, tail_lines=10, tail_chars=1000)

    for index in range(50):
        buffer.append_stdout(f"line-{index}")

    assert buffer.stdout_tail().splitlines() == ["line-45", "line-46", "line-47", "line-48", "line-49"]

