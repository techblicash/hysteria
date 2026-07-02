from __future__ import annotations

import json

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_backup import backup_nodes, load_backup_nodes, restore_nodes_from_backup


def trojan(name: str, server: str = "example.com", password: str = "p") -> ProxyNode:
    return ProxyNode(name=name, type="trojan", server=server, port=443, password=password)


def test_backup_all_nodes(tmp_path) -> None:
    path = tmp_path / "backup.json"

    result = backup_nodes([trojan("a"), trojan("b", server="b.example.com")], str(path))

    assert result.count == 2
    assert path.exists()
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 2


def test_restore_backup_merge(tmp_path) -> None:
    path = tmp_path / "backup.json"
    backup_nodes([trojan("new", server="new.example.com")], str(path))

    result = restore_nodes_from_backup([trojan("existing")], str(path), "merge")

    assert [node.name for node in result.nodes] == ["existing", "new"]
    assert result.restored_count == 1


def test_restore_backup_replace(tmp_path) -> None:
    path = tmp_path / "backup.json"
    backup_nodes([trojan("replacement")], str(path))

    result = restore_nodes_from_backup([trojan("existing")], str(path), "replace")

    assert [node.name for node in result.nodes] == ["replacement"]
    assert result.overwritten_count == 1


def test_merge_restore_skips_duplicate_nodes(tmp_path) -> None:
    path = tmp_path / "backup.json"
    duplicate = trojan("duplicate")
    backup_nodes([duplicate], str(path))

    result = restore_nodes_from_backup([trojan("existing")], str(path), "merge")

    assert [node.name for node in result.nodes] == ["existing"]
    assert result.restored_count == 0
    assert result.skipped_count == 1


def test_invalid_backup_file_returns_error(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")

    result = load_backup_nodes(str(path))

    assert result.errors


def test_old_format_backup_object_with_nodes_is_supported(tmp_path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"nodes": [trojan("old").to_dict()]}), encoding="utf-8")

    result = load_backup_nodes(str(path))

    assert not result.errors
    assert result.nodes[0].name == "old"
