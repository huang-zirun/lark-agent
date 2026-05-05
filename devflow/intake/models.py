from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "devflow.requirement.v1"
AGENT_NAME = "ProductRequirementAnalyst"
AGENT_VERSION = "0.1.0"


@dataclass(slots=True)
class RequirementSource:
    source_type: str
    source_id: str
    reference: str
    content: str
    title: str | None = None
    identity: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    embedded_resources: list[dict[str, Any]] = field(default_factory=list)

    def ensure_content(self) -> None:
        if not self.content or not self.content.strip():
            raise ValueError("需求来源内容为空。")
