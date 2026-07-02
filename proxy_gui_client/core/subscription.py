from __future__ import annotations

from urllib.request import Request, urlopen

from .models import ProxyNode
from .node_parser import parse_subscription_payload


def fetch_subscription(url: str, timeout_seconds: int = 15) -> list[ProxyNode]:
    if not url.strip():
        raise ValueError("订阅链接为空")
    request = Request(url.strip(), headers={"User-Agent": "ProxyGuiClient/0.1"})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8", errors="replace")
    errors: list[str] = []
    nodes = parse_subscription_payload(payload, source=url.strip(), errors=errors)
    if not nodes:
        details = "; ".join(errors[:3])
        suffix = f"，解析错误: {details}" if details else ""
        raise ValueError(f"订阅内容中未解析到支持的节点{suffix}")
    return nodes
