from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devflow.code.tools import CodeToolExecutor


READ_ONLY_TOOLS = {"read_file", "glob_search", "grep_search", "powershell", "semantic_search"}


@dataclass(slots=True)
class ReviewToolExecutor:
    workspace_root: Path | str
    events: list[dict[str, Any]] = field(default_factory=list)
    _delegate: CodeToolExecutor = field(init=False)

    def __post_init__(self) -> None:
        self._delegate = CodeToolExecutor(self.workspace_root)
        self.events = self._delegate.events

    def execute(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool not in READ_ONLY_TOOLS:
            raise ValueError(f"代码评审工具只允许只读操作，拒绝：{tool}")
        return self._delegate.execute(tool, payload)
