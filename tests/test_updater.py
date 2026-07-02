from __future__ import annotations

from proxy_gui_client.core.updater import check_update_from_url, compare_versions, get_current_version, should_prompt_update


class FakeResponse:
    def __init__(self, payload=None, text: str = ""):
        self.payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self):
        if self.payload is None:
            raise ValueError("no json")
        return self.payload


def test_version_compare_logic() -> None:
    assert compare_versions("0.1.0", "0.1.1") < 0
    assert compare_versions("v1.2.0", "1.2.0") == 0
    assert compare_versions("1.3.0", "1.2.9") > 0


def test_get_current_version_reads_file(tmp_path) -> None:
    version_file = tmp_path / "version.txt"
    version_file.write_text("1.2.3", encoding="utf-8")

    assert get_current_version(version_file) == "1.2.3"


def test_update_prompt_when_latest_is_newer() -> None:
    result = check_update_from_url(
        "https://example.test/latest",
        current_version="1.0.0",
        request_get=lambda url, timeout: FakeResponse({"tag_name": "v1.1.0", "html_url": "https://example.test/release"}),
    )

    assert result.update_available is True
    assert result.latest_version == "v1.1.0"
    assert should_prompt_update(result) is True


def test_no_prompt_when_same_version() -> None:
    result = check_update_from_url(
        "https://example.test/latest",
        current_version="1.0.0",
        request_get=lambda url, timeout: FakeResponse({"tag_name": "1.0.0"}),
    )

    assert result.update_available is False
    assert should_prompt_update(result) is False


def test_update_check_error_does_not_raise() -> None:
    result = check_update_from_url(
        "https://example.test/latest",
        current_version="1.0.0",
        request_get=lambda url, timeout: (_ for _ in ()).throw(OSError("offline")),
    )

    assert result.error == "offline"
    assert should_prompt_update(result) is False


def test_plain_text_version_response() -> None:
    result = check_update_from_url(
        "https://example.test/version.txt",
        current_version="1.0.0",
        request_get=lambda url, timeout: FakeResponse(None, "1.0.1"),
    )

    assert result.update_available is True
    assert result.latest_version == "1.0.1"
