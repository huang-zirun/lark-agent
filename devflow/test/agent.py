from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devflow.code.tools import CodeToolExecutor, capture_git_diff
from devflow.config import LlmConfig
from devflow.llm import LlmError, UrlOpen, base_url_host, chat_completion, parse_llm_json
from devflow.solution.models import SCHEMA_VERSION as SOLUTION_SCHEMA_VERSION
from devflow.test.models import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION
from devflow.test.prompt import TEST_GENERATION_SYSTEM_PROMPT, build_test_generation_user_prompt
from devflow.test.runners import detect_test_stack

if TYPE_CHECKING:
    from devflow.trace import StageTrace


REQUIREMENT_SCHEMA_VERSION = "devflow.requirement.v1"
CODE_GENERATION_SCHEMA_VERSION = "devflow.code_generation.v1"


def build_test_generation_artifact(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    llm_config: LlmConfig,
    *,
    requirement_path: Path | str | None = None,
    solution_path: Path | str | None = None,
    code_generation_path: Path | str | None = None,
    stage_trace: "StageTrace | None" = None,
    opener: UrlOpen | None = None,
    max_turns: int = 8,
) -> dict[str, Any]:
    validate_test_generation_inputs(requirement, solution, code_generation)
    workspace = code_generation["workspace"]
    workspace_root = Path(workspace["path"]).expanduser().resolve()
    detected_stack = detect_test_stack(workspace_root)
    executor = CodeToolExecutor(workspace_root)
    messages: list[dict[str, str]] = [{"role": "system", "content": TEST_GENERATION_SYSTEM_PROMPT}]
    finish: dict[str, Any] | None = None
    completions: list[dict[str, Any]] = []

    for turn in range(1, max_turns + 1):
        messages.append(
            {
                "role": "user",
                "content": build_test_generation_user_prompt(
                    requirement,
                    solution,
                    code_generation,
                    detected_stack,
                    executor.events,
                ),
            }
        )
        if stage_trace is not None:
            stage_trace.event("test_llm_started", status="running", payload={"turn": turn, "model": llm_config.model})
        completion = chat_completion(llm_config, messages, opener=opener)
        completions.append(completion.to_audit_payload())
        if stage_trace is not None:
            stage_trace.write_json_artifact(f"test-llm-response-turn{turn}.json", completion.to_audit_payload())
            stage_trace.event(
                "test_llm_completed",
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
            stage_trace.event("test_tool_completed", status="success", payload=executor.events[-1])

    if finish is None:
        raise LlmError("测试生成 agent 达到最大轮数但没有返回 finish。")

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
        "inputs": {
            "requirement_artifact": str(requirement_path) if requirement_path is not None else "",
            "solution_artifact": str(solution_path) if solution_path is not None else "",
            "code_generation_artifact": str(code_generation_path) if code_generation_path is not None else "",
        },
        "detected_stack": detected_stack,
        "generated_tests": _text_list(finish.get("generated_tests")),
        "test_commands": _test_commands(executor.events),
        "summary": str(finish.get("summary") or "").strip(),
        "warnings": _text_list(finish.get("warnings")),
        "tool_events": executor.events,
        "diff": diff_text,
        "prompt": {
            "system_prompt": TEST_GENERATION_SYSTEM_PROMPT,
            "turn_count": len(completions),
        },
    }


def validate_test_generation_inputs(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
) -> None:
    if not isinstance(requirement, dict) or requirement.get("schema_version") != REQUIREMENT_SCHEMA_VERSION:
        raise ValueError("需求产物 schema_version 必须是 devflow.requirement.v1。")
    if not isinstance(solution, dict) or solution.get("schema_version") != SOLUTION_SCHEMA_VERSION:
        raise ValueError("技术方案 schema_version 必须是 devflow.solution_design.v1。")
    if not isinstance(code_generation, dict) or code_generation.get("schema_version") != CODE_GENERATION_SCHEMA_VERSION:
        raise ValueError("代码生成产物 schema_version 必须是 devflow.code_generation.v1。")
    if code_generation.get("status") != "success":
        raise ValueError("代码生成产物必须是 success 状态才能生成测试。")
    workspace = code_generation.get("workspace")
    if not isinstance(workspace, dict) or not workspace.get("path"):
        raise ValueError("代码生成产物缺少 workspace.path。")


def normalize_agent_action(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip().lower()
    if action == "finish":
        return {
            "action": "finish",
            "summary": str(payload.get("summary") or "").strip(),
            "generated_tests": _text_list(payload.get("generated_tests")),
            "warnings": _text_list(payload.get("warnings")),
        }
    if action == "tool":
        tool = str(payload.get("tool") or "").strip()
        tool_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        if not tool:
            raise LlmError("测试生成 agent tool action 缺少 tool。")
        return {"action": "tool", "tool": tool, "input": tool_input}
    raise LlmError("测试生成 agent 响应 action 必须是 tool 或 finish。")


def write_test_generation_artifact(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def write_test_diff(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(str(artifact.get("diff") or ""), encoding="utf-8")
    return out_path


def load_requirement_artifact(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != REQUIREMENT_SCHEMA_VERSION:
        raise ValueError("需求产物 schema_version 必须是 devflow.requirement.v1。")
    return payload


def load_code_generation_artifact(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != CODE_GENERATION_SCHEMA_VERSION:
        raise ValueError("代码生成产物 schema_version 必须是 devflow.code_generation.v1。")
    return payload


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _test_commands(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for event in events:
        if event.get("tool") != "powershell":
            continue
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        payload = event.get("input") if isinstance(event.get("input"), dict) else {}
        commands.append(
            {
                "command": str(payload.get("command") or ""),
                "status": result.get("status"),
                "returncode": result.get("returncode"),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
            }
        )
    return commands


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
