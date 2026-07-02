from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ConnectionStatus = Literal["disconnected", "starting", "running", "stopping", "error"]


@dataclass
class ConnectionState:
    status: ConnectionStatus = "disconnected"
    node_name: str = ""
    error: str = ""

    def set_starting(self, node_name: str = "") -> None:
        self.status = "starting"
        self.node_name = node_name
        self.error = ""

    def set_running(self, node_name: str) -> None:
        self.status = "running"
        self.node_name = node_name
        self.error = ""

    def set_stopping(self) -> None:
        self.status = "stopping"
        self.error = ""

    def set_disconnected(self) -> None:
        self.status = "disconnected"
        self.node_name = ""
        self.error = ""

    def set_error(self, message: str) -> None:
        self.status = "error"
        self.error = message

    def display_text(self) -> str:
        if self.status == "starting":
            return f"正在连接：{self.node_name}" if self.node_name else "正在连接"
        if self.status == "running":
            return f"已连接：{self.node_name}" if self.node_name else "已连接"
        if self.status == "stopping":
            return "正在停止"
        if self.status == "error":
            return f"启动失败：{self.error}" if self.error else "启动失败"
        return "未连接"

    @property
    def is_running(self) -> bool:
        return self.status == "running"
