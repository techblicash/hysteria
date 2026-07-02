from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests

from proxy_gui_client.core.paths import version_file


RequestGet = Callable[..., Any]


@dataclass
class UpdateCheckResult:
    current_version: str
    latest_version: str
    update_available: bool = False
    release_url: str = ""
    error: str = ""


def get_current_version(path: Path | None = None) -> str:
    file_path = path or version_file()
    try:
        return file_path.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    max_len = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (max_len - len(left_parts)))
    right_parts.extend([0] * (max_len - len(right_parts)))
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def is_newer_version(current: str, latest: str) -> bool:
    return compare_versions(current, latest) < 0


def check_update_from_url(
    url: str,
    current_version: str | None = None,
    request_get: RequestGet = requests.get,
    timeout: float = 5,
) -> UpdateCheckResult:
    current = current_version or get_current_version()
    if not url.strip():
        return UpdateCheckResult(current, current, False)
    try:
        response = request_get(url, timeout=timeout)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        latest, release_url = _extract_release(response)
        return UpdateCheckResult(current, latest, is_newer_version(current, latest), release_url)
    except Exception as exc:
        return UpdateCheckResult(current, current, False, error=str(exc))


def should_prompt_update(result: UpdateCheckResult) -> bool:
    return result.update_available and not result.error


def _extract_release(response) -> tuple[str, str]:
    try:
        data = response.json()
    except Exception:
        text = str(getattr(response, "text", "") or "").strip()
        return text, ""
    if isinstance(data, dict):
        version = str(data.get("tag_name") or data.get("version") or "").strip()
        release_url = str(data.get("html_url") or data.get("url") or "").strip()
        if version:
            return version, release_url
    raise ValueError("update response does not contain a version")


def _version_parts(value: str) -> list[int]:
    cleaned = value.strip().lower().lstrip("v")
    parts: list[int] = []
    for item in cleaned.replace("-", ".").split("."):
        digits = "".join(char for char in item if char.isdigit())
        if digits:
            parts.append(int(digits))
    return parts or [0]
