from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from proxy_gui_client.core.models import ProxyNode


SourceFileAction = Literal["keep", "clear", "set"]


@dataclass
class BatchEditOptions:
    source: str | None = None
    source_file_action: SourceFileAction = "keep"
    source_file_value: str = ""
    name_prefix: str = ""
    name_suffix: str = ""
    clear_test_results: bool = False


@dataclass
class BatchEditResult:
    nodes: list[ProxyNode]
    updated_count: int = 0


def apply_batch_edit(nodes: list[ProxyNode], indexes: list[int], options: BatchEditOptions) -> BatchEditResult:
    if not indexes:
        return BatchEditResult(nodes=list(nodes), updated_count=0)

    updated_nodes = [ProxyNode.from_dict(node.to_dict()) for node in nodes]
    changed_count = 0
    valid_indexes = sorted({index for index in indexes if 0 <= index < len(updated_nodes)})
    has_operation = _has_operation(options)
    if not has_operation:
        return BatchEditResult(nodes=updated_nodes, updated_count=0)

    for index in valid_indexes:
        node = updated_nodes[index]
        before = node.to_dict()
        if options.source is not None:
            node.source = options.source
        if options.source_file_action == "clear":
            node.source_file = ""
        elif options.source_file_action == "set":
            node.source_file = options.source_file_value
        if options.name_prefix:
            node.name = f"{options.name_prefix}{node.name}"
        if options.name_suffix:
            node.name = f"{node.name}{options.name_suffix}"
        if options.clear_test_results:
            node.tcp_latency_ms = None
            node.url_latency_ms = None
            node.latency_ms = None
            node.test_status = ""
            node.last_tested_at = ""
        if node.to_dict() != before:
            changed_count += 1
    return BatchEditResult(nodes=updated_nodes, updated_count=changed_count)


def _has_operation(options: BatchEditOptions) -> bool:
    return (
        options.source is not None
        or options.source_file_action != "keep"
        or bool(options.name_prefix)
        or bool(options.name_suffix)
        or options.clear_test_results
    )
