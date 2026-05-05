from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devflow.code.models import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION
from devflow.code.prompt import CODE_GENERATION_SYSTEM_PROMPT, build_code_generation_user_prompt
from devflow.code.tools import CodeToolExecutor, capture_git_diff
from devflow.config import LlmConfig
from devflow.llm import LlmError, UrlOpen, base_url_host, chat_completion, parse_llm_json
from devflow.solution.models import SCHEMA_VERSION as SOLUTION_SCHEMA_VERSION

if TYPE_CHECKING:
    from devflow.trace import StageTrace


class QualityGateError(Exception):
    def __init__(self, stage: str, reasons: list[str], quality_snapshot: dict | None = None) -> None:
        self.stage = stage
        self.reasons = reasons
        self.quality_snapshot = quality_snapshot
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        parts = [f"Quality gate failed at stage '{self.stage}':"]
        for r in self.reasons:
            parts.append(f"  - {r}")
        if self.quality_snapshot:
            parts.append(f"  snapshot: {self.quality_snapshot}")
        return "\n".join(parts)

    def __str__(self) -> str:
        return self._build_message()


def build_code_generation_artifact(
    solution: dict[str, Any],
    llm_config: LlmConfig,
    *,
    stage_trace: "StageTrace | None" = None,
    opener: UrlOpen | None = None,
    max_turns: int = 8,
) -> dict[str, Any]:
    validate_solution_artifact(solution)
    workspace = solution["workspace"]
    workspace_root = Path(workspace["path"]).expanduser().resolve()
    executor = CodeToolExecutor(workspace_root)
    messages: list[dict[str, str]] = [{"role": "system", "content": CODE_GENERATION_SYSTEM_PROMPT}]
    finish: dict[str, Any] | None = None
    completions: list[dict[str, Any]] = []

    for turn in range(1, max_turns + 1):
        messages.append({"role": "user", "content": build_code_generation_user_prompt(solution, executor.events)})
        if stage_trace is not None:
            stage_trace.event("code_llm_started", status="running", payload={"turn": turn, "model": llm_config.model})
        completion = chat_completion(llm_config, messages, opener=opener)
        completions.append(completion.to_audit_payload())
        if stage_trace is not None:
            stage_trace.write_json_artifact(f"code-llm-response-turn{turn}.json", completion.to_audit_payload())
            stage_trace.event(
                "code_llm_completed",
                status="success",
                duration_ms=completion.duration_ms,
                payload={"turn": turn, "token_usage": completion.usage, "usage_source": completion.usage_source},
            )
        action = normalize_agent_action(parse_llm_json(completion.content))
        messages.append({"role": "assistant", "content": json.dumps(action, ensure_ascii=False)})
        if action["action"] == "finish":
            finish = action
            break
        result = executor.execute(action["tool"], action["input"])
        messages.append({"role": "user", "content": json.dumps({"tool_result": result}, ensure_ascii=False)})
        if stage_trace is not None:
            stage_trace.event("code_tool_completed", status="success", payload=executor.events[-1])

    if finish is None:
        raise LlmError("代码生成 agent 达到最大轮数但没有返回 finish。")

    diff_text = capture_git_diff(workspace_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "agent": AGENT_NAME,
            "agent_version": AGENT_VERSION,
            "created_at": utc_now(),
            "model": llm_config.model,
            "llm_provider": llm_config.provider,
            "llm_base_url_host": base_url_host(llm_config),
        },
        "status": "success",
        "workspace": workspace,
        "solution_summary": {
            "title": (solution.get("requirement_summary") or {}).get("title", ""),
            "summary": (solution.get("proposed_solution") or {}).get("summary", ""),
        },
        "changed_files": _text_list(finish.get("changed_files")),
        "summary": str(finish.get("summary") or "").strip(),
        "warnings": _text_list(finish.get("warnings")),
        "tool_events": executor.events,
        "diff": diff_text,
        "prompt": {
            "system_prompt": CODE_GENERATION_SYSTEM_PROMPT,
            "turn_count": len(completions),
        },
    }


def validate_solution_artifact(solution: dict[str, Any]) -> None:
    if not isinstance(solution, dict):
        raise ValueError("技术方案必须是 JSON object。")
    if solution.get("schema_version") != SOLUTION_SCHEMA_VERSION:
        raise ValueError("技术方案 schema_version 必须是 devflow.solution_design.v1。")
    workspace = solution.get("workspace")
    if not isinstance(workspace, dict) or not workspace.get("path"):
        raise ValueError("技术方案缺少 workspace.path。")
    quality = solution.get("quality") if isinstance(solution.get("quality"), dict) else {}
    if quality.get("ready_for_code_generation") is False:
        raise QualityGateError(
            stage="solution_design",
            reasons=["技术方案未标记为 ready_for_code_generation。"] + [str(w) for w in quality.get("warnings", []) if w],
            quality_snapshot={"ready_for_code_generation": quality.get("ready_for_code_generation"), "completeness_score": quality.get("completeness_score"), "risk_level": quality.get("risk_level"), "warnings": quality.get("warnings", [])},
        )


def normalize_agent_action(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip().lower()
    if action == "finish":
        return {
            "action": "finish",
            "summary": str(payload.get("summary") or "").strip(),
            "changed_files": _text_list(payload.get("changed_files")),
            "warnings": _text_list(payload.get("warnings")),
        }
    if action == "tool":
        tool = str(payload.get("tool") or "").strip()
        tool_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        if not tool:
            raise LlmError("代码生成 agent tool action 缺少 tool。")
        return {"action": "tool", "tool": tool, "input": tool_input}
    raise LlmError("代码生成 agent 响应 action 必须是 tool 或 finish。")


def write_code_generation_artifact(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def write_code_diff(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(str(artifact.get("diff") or ""), encoding="utf-8")
    return out_path


def load_solution_artifact(path: Path | str) -> dict[str, Any]:
    solution_path = Path(path)
    payload = json.loads(solution_path.read_text(encoding="utf-8-sig"))
    validate_solution_artifact(payload)
    return payload


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
