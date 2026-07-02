from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from proxy_gui_client.core.models import ProxyNode
from proxy_gui_client.core.node_dedup import node_identity
from proxy_gui_client.core.node_exporter import export_nodes_project_json


RestoreMode = Literal["merge", "replace"]


@dataclass
class BackupResult:
    path: str
    count: int


@dataclass
class RestoreResult:
    nodes: list[ProxyNode] = field(default_factory=list)
    restored_count: int = 0
    skipped_count: int = 0
    overwritten_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def backup_nodes(nodes: list[ProxyNode], path: str) -> BackupResult:
    export_nodes_project_json(nodes, path)
    return BackupResult(path=str(path), count=len(nodes))


def load_backup_nodes(path: str) -> RestoreResult:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        return RestoreResult(errors=[f"Failed to read backup file: {exc}"])

    if isinstance(data, dict):
        raw_nodes = data.get("nodes")
    else:
        raw_nodes = data
    if not isinstance(raw_nodes, list):
        return RestoreResult(errors=["Invalid backup file: expected a node list or an object with nodes list"])

    nodes: list[ProxyNode] = []
    warnings: list[str] = []
    for index, item in enumerate(raw_nodes):
        if not isinstance(item, dict):
            warnings.append(f"Backup node #{index + 1} skipped: item is not an object")
            continue
        try:
            nodes.append(ProxyNode.from_dict(item))
        except Exception as exc:
            warnings.append(f"Backup node #{index + 1} skipped: {exc}")
    return RestoreResult(nodes=nodes, restored_count=len(nodes), skipped_count=len(raw_nodes) - len(nodes), warnings=warnings)


def restore_nodes_from_backup(existing_nodes: list[ProxyNode], path: str, mode: RestoreMode) -> RestoreResult:
    loaded = load_backup_nodes(path)
    if loaded.errors:
        return loaded
    if mode == "replace":
        return RestoreResult(nodes=loaded.nodes, restored_count=len(loaded.nodes), overwritten_count=len(existing_nodes), warnings=loaded.warnings)
    if mode != "merge":
        return RestoreResult(nodes=list(existing_nodes), errors=[f"Unknown restore mode: {mode}"])

    nodes = list(existing_nodes)
    existing_identities = {node_identity(node) for node in nodes}
    restored_count = 0
    skipped_count = loaded.skipped_count
    for node in loaded.nodes:
        identity = node_identity(node)
        if identity in existing_identities:
            skipped_count += 1
            continue
        nodes.append(node)
        existing_identities.add(identity)
        restored_count += 1
    return RestoreResult(nodes=nodes, restored_count=restored_count, skipped_count=skipped_count, overwritten_count=0, warnings=loaded.warnings)
