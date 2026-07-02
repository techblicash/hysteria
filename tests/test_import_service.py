from __future__ import annotations

from proxy_gui_client.core.config_importer import ImportResult
from proxy_gui_client.core.import_service import (
    ImportPreview,
    ImportPreviewItem,
    apply_import_strategy,
    apply_selected_import,
    build_import_preview,
)
from proxy_gui_client.core.models import ProxyNode


def vless(name: str, server: str = "example.com", uuid: str = "u") -> ProxyNode:
    return ProxyNode(name=name, type="vless", server=server, port=443, uuid=uuid, network="tcp", tls=True, sni="example.com")


def trojan(name: str, server: str = "trojan.example.com", password: str = "p") -> ProxyNode:
    return ProxyNode(name=name, type="trojan", server=server, port=443, password=password, network="tcp", tls=True, sni="example.com")


def test_preview_distinguishes_new_and_duplicate_existing() -> None:
    existing = [vless("existing")]
    result = ImportResult(nodes=[vless("imported"), trojan("new")])

    preview = build_import_preview(result, existing, r"C:\configs\demo.yaml")

    assert [item.status for item in preview.items] == ["duplicate_existing", "new"]
    assert preview.duplicate_existing_count == 1
    assert preview.new_count == 1


def test_preview_detects_duplicate_inside_file() -> None:
    result = ImportResult(nodes=[vless("first"), vless("second")])

    preview = build_import_preview(result, [], "demo.yaml")

    assert preview.items[0].status == "new"
    assert preview.items[1].status == "duplicate_inside_file"
    assert preview.items[1].duplicate_import_index == 0


def test_import_new_only_imports_only_new_nodes() -> None:
    existing = [vless("existing")]
    preview = build_import_preview(ImportResult(nodes=[vless("dupe"), trojan("new")]), existing, "demo.yaml")

    applied = apply_import_strategy(existing, preview, "import_new_only")

    assert [node.name for node in applied.nodes] == ["existing", "new"]
    assert applied.imported_count == 1
    assert applied.skipped_count == 1


def test_overwrite_existing_replaces_duplicate() -> None:
    existing = [vless("old")]
    imported = vless("replacement")
    preview = build_import_preview(ImportResult(nodes=[imported]), existing, "demo.yaml")

    applied = apply_import_strategy(existing, preview, "overwrite_existing")

    assert len(applied.nodes) == 1
    assert applied.nodes[0].name == "replacement"
    assert applied.overwritten_count == 1


def test_import_all_rename_imports_all_and_handles_duplicate_names() -> None:
    existing = [vless("Node", server="a.example.com")]
    imported = [vless("Node", server="b.example.com"), vless("Node", server="c.example.com")]
    preview = build_import_preview(ImportResult(nodes=imported), existing, "demo.yaml")

    applied = apply_import_strategy(existing, preview, "import_all_rename")

    assert [node.name for node in applied.nodes] == ["Node", "Node (2)", "Node (3)"]
    assert applied.imported_count == 2
    assert applied.renamed_count == 2


def test_cancel_import_does_not_modify_nodes() -> None:
    existing = [vless("existing")]
    preview = build_import_preview(ImportResult(nodes=[trojan("new")]), existing, "demo.yaml")

    applied = apply_import_strategy(existing, preview, "cancel")

    assert applied.cancelled is True
    assert applied.nodes == existing


def test_imported_nodes_get_source_metadata() -> None:
    preview = build_import_preview(ImportResult(nodes=[trojan("new")]), [], r"C:\configs\demo.yaml")

    applied = apply_import_strategy([], preview, "import_new_only")
    node = applied.nodes[0]

    assert node.source == "config_file"
    assert node.source_file == "demo.yaml"
    assert node.imported_at


def test_old_node_without_source_fields_can_deduplicate() -> None:
    old = ProxyNode.from_dict({"name": "old", "type": "trojan", "server": "example.com", "port": 443, "password": "p"})
    imported = ProxyNode(name="new", type="trojan", server="example.com", port=443, password="p")

    preview = build_import_preview(ImportResult(nodes=[imported]), [old], "demo.yaml")

    assert preview.items[0].status == "duplicate_existing"


def test_import_selected_imports_only_checked_new_nodes() -> None:
    preview = build_import_preview(ImportResult(nodes=[trojan("a"), trojan("b", server="b.example.com")]), [], "demo.yaml")

    applied = apply_selected_import([], preview, {1})

    assert [node.name for node in applied.nodes] == ["b"]
    assert applied.imported_count == 1
    assert applied.skipped_count == 1


def test_import_selected_can_overwrite_checked_duplicate_existing() -> None:
    existing = [vless("old")]
    preview = build_import_preview(ImportResult(nodes=[vless("replacement")]), existing, "demo.yaml")

    applied = apply_selected_import(existing, preview, {0})

    assert [node.name for node in applied.nodes] == ["replacement"]
    assert applied.overwritten_count == 1


def test_import_selected_does_not_import_unchecked_nodes() -> None:
    preview = build_import_preview(ImportResult(nodes=[trojan("a"), trojan("b", server="b.example.com")]), [], "demo.yaml")

    applied = apply_selected_import([], preview, {0})

    assert [node.name for node in applied.nodes] == ["a"]


def test_import_selected_does_not_import_invalid_nodes() -> None:
    preview = ImportPreview(
        items=[ImportPreviewItem(node=trojan("invalid"), status="invalid", message="bad")],
        total_nodes=1,
        source_file="demo.yaml",
    )

    applied = apply_selected_import([], preview, {0})

    assert applied.nodes == []
    assert applied.imported_count == 0
    assert applied.skipped_count == 1
    assert applied.warnings


def test_import_selected_sets_source_metadata() -> None:
    preview = build_import_preview(ImportResult(nodes=[trojan("new")]), [], r"C:\configs\demo.yaml")

    applied = apply_selected_import([], preview, {0})
    node = applied.nodes[0]

    assert node.source == "config_file"
    assert node.source_file == "demo.yaml"
    assert node.imported_at


def test_import_selected_renames_checked_duplicate_inside_file() -> None:
    first = vless("Node")
    second = vless("Node")
    preview = build_import_preview(ImportResult(nodes=[first, second]), [], "demo.yaml")

    applied = apply_selected_import([], preview, {1})

    assert [node.name for node in applied.nodes] == ["Node (2)"]
    assert applied.renamed_count == 1
    assert applied.warnings


def test_import_selected_empty_selection_does_not_modify_existing_nodes() -> None:
    existing = [vless("existing")]
    preview = build_import_preview(ImportResult(nodes=[trojan("new")]), existing, "demo.yaml")

    applied = apply_selected_import(existing, preview, set())

    assert applied.nodes == existing
    assert applied.imported_count == 0
