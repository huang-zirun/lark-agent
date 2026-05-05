from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class RunTrace:
    def __init__(self, run_id: str, run_dir: Path) -> None:
        self.run_id = run_id
        self.run_dir = run_dir
        self.trace_path = run_dir / "trace.jsonl"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def stage(self, name: str) -> StageTrace:
        return StageTrace(self, name)

    def event(
        self,
        event_type: str,
        *,
        stage: str | None = None,
        status: str | None = None,
        payload: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        event = {
            "timestamp": utc_now(),
            "run_id": self.run_id,
            "type": event_type,
        }
        if stage is not None:
            event["stage"] = stage
        if status is not None:
            event["status"] = status
        if duration_ms is not None:
            event["duration_ms"] = duration_ms
        if payload is not None:
            event["payload"] = payload
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


class StageTrace:
    def __init__(self, run_trace: RunTrace, stage: str) -> None:
        self.run_trace = run_trace
        self.stage = stage

    def event(
        self,
        event_type: str,
        *,
        status: str | None = None,
        payload: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        return self.run_trace.event(
            event_type,
            stage=self.stage,
            status=status,
            payload=payload,
            duration_ms=duration_ms,
        )

    def write_json_artifact(self, name: str, payload: dict[str, Any]) -> Path:
        path = self.run_trace.run_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
