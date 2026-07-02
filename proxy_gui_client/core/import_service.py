from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from proxy_gui_client.core.config_importer import ImportResult
from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_dedup import find_duplicate_nodes, find_duplicate_nodes_inside


ImportStatus = Literal["new", "duplicate_existing", "duplicate_inside_file", "invalid"]
ImportStrategy = Literal["import_new_only", "overwrite_existing", "import_all_rename", "import_selected", "cancel"]


@dataclass
class ImportPreviewItem:
    node: ProxyNode
    status: ImportStatus
    duplicate_existing_index: int | None = None
    duplicate_import_index: int | None = None
    message: str = ""


@dataclass
class ImportPreview:
    items: list[ImportPreviewItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_nodes: int = 0
    new_count: int = 0
    duplicate_existing_count: int = 0
    duplicate_inside_file_count: int = 0
    source_file: str = ""


@dataclass
class ImportApplyResult:
    nodes: list[ProxyNode]
    imported_count: int = 0
    overwritten_count: int = 0
    skipped_count: int = 0
    renamed_count: int = 0
    cancelled: bool = False
    warnings: list[str] = field(default_factory=list)


def build_import_preview(import_result: ImportResult, existing_nodes: list[ProxyNode], source_path: str) -> ImportPreview:
    source_file = Path(source_path).name
    duplicate_existing = find_duplicate_nodes(import_result.nodes, existing_nodes)
    duplicate_inside = find_duplicate_nodes_inside(import_result.nodes)
    items: list[ImportPreviewItem] = []

    for index, node in enumerate(import_result.nodes):
        if index in duplicate_inside:
            first_index = duplicate_inside[index]
            items.append(
                ImportPreviewItem(
                    node=node,
                    status="duplicate_inside_file",
                    duplicate_import_index=first_index,
                    message=f"Duplicate inside file; first occurrence is #{first_index + 1}",
                )
            )
        elif index in duplicate_existing:
            existing_index = duplicate_existing[index]
            items.append(
                ImportPreviewItem(
                    node=node,
                    status="duplicate_existing",
                    duplicate_existing_index=existing_index,
                    message=f"Duplicates existing node #{existing_index + 1}",
                )
            )
        else:
            items.append(ImportPreviewItem(node=node, status="new", message="New node"))

    return ImportPreview(
        items=items,
        warnings=list(import_result.warnings),
        errors=list(import_result.errors),
        total_nodes=len(import_result.nodes),
        new_count=sum(1 for item in items if item.status == "new"),
        duplicate_existing_count=sum(1 for item in items if item.status == "duplicate_existing"),
        duplicate_inside_file_count=sum(1 for item in items if item.status == "duplicate_inside_file"),
        source_file=source_file,
    )


def apply_import_strategy(existing_nodes: list[ProxyNode], preview: ImportPreview, strategy: ImportStrategy) -> ImportApplyResult:
    if strategy == "cancel":
        return ImportApplyResult(nodes=list(existing_nodes), cancelled=True)
    if strategy == "import_selected":
        return apply_selected_import(existing_nodes, preview, set())

    nodes = list(existing_nodes)
    imported_count = 0
    overwritten_count = 0
    skipped_count = 0
    renamed_count = 0
    used_names = {node.name for node in nodes}

    for item in preview.items:
        node = _stamp_import_metadata(item.node, preview.source_file)
        if strategy == "import_new_only":
            if item.status == "new":
                nodes.append(node)
                used_names.add(node.name)
                imported_count += 1
            else:
                skipped_count += 1
        elif strategy == "overwrite_existing":
            if item.status == "new":
                nodes.append(node)
                used_names.add(node.name)
                imported_count += 1
            elif item.status == "duplicate_existing" and item.duplicate_existing_index is not None:
                nodes[item.duplicate_existing_index] = node
                used_names.add(node.name)
                imported_count += 1
                overwritten_count += 1
            else:
                skipped_count += 1
        elif strategy == "import_all_rename":
            original_name = node.name
            node.name = _unique_name(node.name, used_names)
            if node.name != original_name:
                renamed_count += 1
            used_names.add(node.name)
            nodes.append(node)
            imported_count += 1
        else:
            raise ValueError(f"Unknown import strategy: {strategy}")

    return ImportApplyResult(
        nodes=nodes,
        imported_count=imported_count,
        overwritten_count=overwritten_count,
        skipped_count=skipped_count,
        renamed_count=renamed_count,
    )


def apply_selected_import(existing_nodes: list[ProxyNode], preview: ImportPreview, selected_indexes: set[int]) -> ImportApplyResult:
    nodes = list(existing_nodes)
    imported_count = 0
    overwritten_count = 0
    skipped_count = 0
    renamed_count = 0
    warnings: list[str] = []
    used_names = {node.name for node in nodes}

    for index, item in enumerate(preview.items):
        if index not in selected_indexes:
            skipped_count += 1
            continue
        if item.status == "invalid":
            skipped_count += 1
            warnings.append(f"Skipped invalid node #{index + 1}: {item.node.name or '-'}")
            continue

        node = _stamp_import_metadata(item.node, preview.source_file)
        if item.status == "duplicate_existing":
            if item.duplicate_existing_index is None or item.duplicate_existing_index >= len(nodes):
                skipped_count += 1
                warnings.append(f"Skipped duplicate node #{index + 1}: missing existing target")
                continue
            nodes[item.duplicate_existing_index] = node
            used_names.add(node.name)
            imported_count += 1
            overwritten_count += 1
        elif item.status == "duplicate_inside_file":
            original_name = node.name
            if item.duplicate_import_index is not None and 0 <= item.duplicate_import_index < len(preview.items):
                used_names.add(preview.items[item.duplicate_import_index].node.name)
            node.name = _unique_name(node.name, used_names)
            if node.name != original_name:
                renamed_count += 1
            used_names.add(node.name)
            nodes.append(node)
            imported_count += 1
            warnings.append(f"Imported duplicate-inside-file node #{index + 1} as {node.name}")
        else:
            used_names.add(node.name)
            nodes.append(node)
            imported_count += 1

    return ImportApplyResult(
        nodes=nodes,
        imported_count=imported_count,
        overwritten_count=overwritten_count,
        skipped_count=skipped_count,
        renamed_count=renamed_count,
        warnings=warnings,
    )


def _stamp_import_metadata(node: ProxyNode, source_file: str) -> ProxyNode:
    data = node.to_dict()
    data.update(
        {
            "source": "config_file",
            "source_file": source_file,
            "imported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "latency_ms": None,
            "tcp_latency_ms": None,
            "url_latency_ms": None,
            "test_status": "",
        }
    )
    return ProxyNode.from_dict(data)


def _unique_name(name: str, used_names: set[str]) -> str:
    base = name or "Imported Node"
    if base not in used_names:
        return base
    suffix = 2
    while True:
        candidate = f"{base} ({suffix})"
        if candidate not in used_names:
            return candidate
        suffix += 1
