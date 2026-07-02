from __future__ import annotations

from typing import Any


TABLE_COLUMN_KEYS = [
    "name",
    "type",
    "server",
    "port",
    "source",
    "tcp_latency",
    "url_latency",
    "status",
]

DEFAULT_TABLE_COLUMN_WIDTHS: dict[str, int] = {
    "name": 180,
    "type": 80,
    "server": 220,
    "port": 80,
    "source": 100,
    "tcp_latency": 100,
    "url_latency": 100,
    "status": 160,
}

DEFAULT_NODE_FILTER_PREFERENCES: dict[str, str] = {
    "keyword": "",
    "node_type": "all",
    "source": "all",
    "availability": "all",
    "sort_by": "default",
    "batch_scope": "filtered",
}

VALID_NODE_TYPES = {"all", "vmess", "vless", "trojan", "shadowsocks"}
VALID_SOURCES = {"all", "manual", "subscription", "config_file", "unknown"}
VALID_AVAILABILITY = {"all", "tcp_available", "url_available", "failed", "untested"}
VALID_SORT_BY = {"default", "name", "type", "tcp_latency", "url_latency", "source", "imported_at"}
VALID_BATCH_SCOPE = {"filtered", "selected"}


def ensure_table_preferences(settings: dict[str, Any]) -> dict[str, Any]:
    updated = dict(settings)
    updated["table_column_widths"] = normalize_table_column_widths(updated)
    updated["node_filter_preferences"] = normalize_filter_preferences(updated)
    return updated


def normalize_table_column_widths(settings: dict[str, Any]) -> dict[str, int]:
    raw = settings.get("table_column_widths")
    if not isinstance(raw, dict):
        raw = {}

    widths: dict[str, int] = {}
    for key, default in DEFAULT_TABLE_COLUMN_WIDTHS.items():
        value = raw.get(key, default)
        try:
            width = int(value)
        except (TypeError, ValueError):
            width = default
        widths[key] = width if width >= 40 else default
    return widths


def normalize_filter_preferences(settings: dict[str, Any]) -> dict[str, str]:
    raw = settings.get("node_filter_preferences")
    if not isinstance(raw, dict):
        raw = {}

    preferences = dict(DEFAULT_NODE_FILTER_PREFERENCES)
    preferences["keyword"] = str(raw.get("keyword", "") or "")
    preferences["node_type"] = _valid_or_default(raw.get("node_type"), VALID_NODE_TYPES, "all")
    preferences["source"] = _valid_or_default(raw.get("source"), VALID_SOURCES, "all")
    preferences["availability"] = _valid_or_default(raw.get("availability"), VALID_AVAILABILITY, "all")
    preferences["sort_by"] = _valid_or_default(raw.get("sort_by"), VALID_SORT_BY, "default")
    preferences["batch_scope"] = _valid_or_default(raw.get("batch_scope"), VALID_BATCH_SCOPE, "filtered")
    return preferences


def update_table_column_width(settings: dict[str, Any], key: str, width: int) -> dict[str, Any]:
    updated = ensure_table_preferences(settings)
    if key in DEFAULT_TABLE_COLUMN_WIDTHS:
        try:
            parsed = int(width)
        except (TypeError, ValueError):
            parsed = DEFAULT_TABLE_COLUMN_WIDTHS[key]
        updated["table_column_widths"][key] = parsed if parsed >= 40 else DEFAULT_TABLE_COLUMN_WIDTHS[key]
    return updated


def update_filter_preference(settings: dict[str, Any], key: str, value: str) -> dict[str, Any]:
    updated = ensure_table_preferences(settings)
    if key in DEFAULT_NODE_FILTER_PREFERENCES:
        raw = dict(updated["node_filter_preferences"])
        raw[key] = value
        updated["node_filter_preferences"] = normalize_filter_preferences({"node_filter_preferences": raw})
    return updated


def _valid_or_default(value: Any, valid_values: set[str], default: str) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in valid_values else default
