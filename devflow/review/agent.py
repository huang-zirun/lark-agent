from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devflow.config import LlmConfig
from devflow.llm import LlmError, UrlOpen, base_url_host, chat_completion, parse_llm_json
from devflow.review.models import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION
from devflow.review.prompt import CODE_REVIEW_SYSTEM_PROMPT, build_code_review_user_prompt
from devflow.review.tools import ReviewToolExecutor
from devflow.solution.models import SCHEMA_VERSION as SOLUTION_SCHEMA_VERSION

if TYPE_CHECKING:
    from devflow.trace import StageTrace


def _load_reference_docs_for_review() -> list[dict[str, Any]]:
    try:
        from devflow.config import load_config
        from devflow.references.registry import ReferenceRegistry
        config = load_config()
        if not config.reference.enabled:
            return []
        registry = ReferenceRegistry()
        return registry.get_documents_for_stage(
            "code_review",
            max_total_chars=config.reference.max_chars_per_stage,
        )
    except Exception:
        return []


REQUIREMENT_SCHEMA_VERSION = "devflow.requirement.v1"
CODE_GENERATION_SCHEMA_VERSION = "devflow.code_generation.v1"
TEST_GENERATION_SCHEMA_VERSION = "devflow.test_generation.v1"


def build_code_review_artifact(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    test_generation: dict[str, Any],
    llm_config: LlmConfig,
    *,
    requirement_path: Path | str | None = None,
    solution_path: Path | str | None = None,
    code_generation_path: Path | str | None = None,
    test_generation_path: Path | str | None = None,
    stage_trace: "StageTrace | None" = None,
    opener: UrlOpen | None = None,
    max_turns: int = 6,
) -> dict[str, Any]:
    validate_code_review_inputs(requirement, solution, code_generation, test_generation)
    workspace = code_generation["workspace"]
    workspace_root = Path(workspace["path"]).expanduser().resolve()
    executor = ReviewToolExecutor(workspace_root)
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": CODE_REVIEW_SYSTEM_PROMPT
            + "\n只返回一个合法 JSON object，不要包含 markdown 代码块。",
        }
    ]
    finish: dict[str, Any] | None = None
    completions: list[dict[str, Any]] = []

    for turn in range(1, max_turns + 1):
        messages.append(
            {
                "role": "user",
                "content": build_code_review_user_prompt(
                    requirement,
                    solution,
                    code_generation,
                    test_generation,
                    executor.events,
                    reference_documents=_load_reference_docs_for_review(),
                ),
            }
        )
        if stage_trace is not None:
            stage_trace.event("review_llm_started", status="running", payload={"turn": turn, "model": llm_config.model})
        completion = chat_completion(llm_config, messages, opener=opener)
        completions.append(completion.to_audit_payload())
        if stage_trace is not None:
            stage_trace.write_json_artifact(f"review-llm-response-turn{turn}.json", completion.to_audit_payload())
            stage_trace.event(
                "review_llm_completed",
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
            stage_trace.event("review_tool_completed", status="success", payload=executor.events[-1])

    if finish is None:
        raise LlmError("代码评审 agent 达到最大轮数但没有返回 finish。")

    findings = normalize_findings(finish.get("findings"))
    test_summary = summarize_tests(test_generation)
    findings.extend(test_failure_findings(test_summary))
    blocking_count = sum(1 for finding in findings if finding.get("blocking"))
    quality_gate = normalize_quality_gate(finish.get("quality_gate"), blocking_count)
    review_status = normalize_review_status(finish.get("review_status"), quality_gate)
    if test_summary["failed_commands"] > 0 and review_status == "passed":
        review_status = "needs_changes"
    if review_status != "passed":
        quality_gate["passed"] = False
    quality_gate["blocking_findings"] = blocking_count

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
            "test_generation_artifact": str(test_generation_path) if test_generation_path is not None else "",
        },
        "review_status": review_status,
        "quality_gate": quality_gate,
        "findings": findings,
        "test_summary": test_summary,
        "diff_summary": {
            "changed_files": _text_list(code_generation.get("changed_files")),
            "code_diff_bytes": len(str(code_generation.get("diff") or "").encode("utf-8")),
            "test_diff_bytes": len(str(test_generation.get("diff") or "").encode("utf-8")),
        },
        "repair_recommendations": _text_list(finish.get("repair_recommendations")),
        "summary": str(finish.get("summary") or "").strip(),
        "warnings": _text_list(finish.get("warnings")),
        "tool_events": executor.events,
        "reference_documents_used": [
            {"name": doc.get("name"), "title": doc.get("title"), "chars_injected": len(doc.get("content", ""))}
            for doc in _load_reference_docs_for_review()
        ],
        "prompt": {
            "system_prompt": CODE_REVIEW_SYSTEM_PROMPT,
            "turn_count": len(completions),
        },
    }


def validate_code_review_inputs(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    test_generation: dict[str, Any],
) -> None:
    if not isinstance(requirement, dict) or requirement.get("schema_version") != REQUIREMENT_SCHEMA_VERSION:
        raise ValueError("需求产物 schema_version 必须是 devflow.requirement.v1。")
    if not isinstance(solution, dict) or solution.get("schema_version") != SOLUTION_SCHEMA_VERSION:
        raise ValueError("技术方案 schema_version 必须是 devflow.solution_design.v1。")
    if not isinstance(code_generation, dict) or code_generation.get("schema_version") != CODE_GENERATION_SCHEMA_VERSION:
        raise ValueError("代码生成产物 schema_version 必须是 devflow.code_generation.v1。")
    if code_generation.get("status") != "success":
        raise ValueError("代码生成产物必须是 success 状态才能评审。")
    if not isinstance(test_generation, dict) or test_generation.get("schema_version") != TEST_GENERATION_SCHEMA_VERSION:
        raise ValueError("测试生成产物 schema_version 必须是 devflow.test_generation.v1。")
    if test_generation.get("status") != "success":
        raise ValueError("测试生成产物必须是 success 状态才能评审。")
    workspace = code_generation.get("workspace")
    if not isinstance(workspace, dict) or not workspace.get("path"):
        raise ValueError("代码生成产物缺少 workspace.path。")


def normalize_agent_action(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip().lower()
    if action == "finish":
        return {
            "action": "finish",
            "review_status": str(payload.get("review_status") or "needs_changes").strip(),
            "quality_gate": payload.get("quality_gate") if isinstance(payload.get("quality_gate"), dict) else {},
            "findings": payload.get("findings") if isinstance(payload.get("findings"), list) else [],
            "repair_recommendations": _text_list(payload.get("repair_recommendations")),
            "summary": str(payload.get("summary") or "").strip(),
            "warnings": _text_list(payload.get("warnings")),
        }
    if action == "tool":
        tool = str(payload.get("tool") or "").strip()
        tool_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        if not tool:
            raise LlmError("代码评审 agent tool action 缺少 tool。")
        return {"action": "tool", "tool": tool, "input": tool_input}
    raise LlmError("代码评审 agent 响应 action 必须是 tool 或 finish。")


def write_code_review_artifact(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def load_code_review_artifact(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("代码评审产物 schema_version 必须是 devflow.code_review.v1。")
    return payload


def load_requirement_artifact(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != REQUIREMENT_SCHEMA_VERSION:
        raise ValueError("需求产物 schema_version 必须是 devflow.requirement.v1。")
    return payload


def summarize_tests(test_generation: dict[str, Any]) -> dict[str, Any]:
    commands = test_generation.get("test_commands") if isinstance(test_generation.get("test_commands"), list) else []
    failed = 0
    executed = 0
    failed_commands: list[dict[str, Any]] = []
    for command in commands:
        if not isinstance(command, dict):
            continue
        executed += 1
        if int(command.get("returncode") or 0) != 0 or command.get("status") == "failed":
            failed += 1
            failed_commands.append(command)
    return {
        "generated_tests": _text_list(test_generation.get("generated_tests")),
        "command_count": executed,
        "failed_commands": failed,
        "failed_command_details": failed_commands,
    }


def test_failure_findings(test_summary: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for index, command in enumerate(test_summary.get("failed_command_details") or [], start=1):
        findings.append(
            {
                "id": f"CR-TEST-{index:03d}",
                "severity": "P1",
                "category": "tests",
                "path": "",
                "line": None,
                "title": "测试命令执行失败",
                "description": f"测试命令 `{command.get('command', '')}` 返回失败，代码评审不能放行。",
                "evidence": str(command.get("stderr") or command.get("stdout") or command.get("returncode") or ""),
                "fix_suggestion": "先修复失败测试或补充可重复的验证命令，再重新评审。",
                "blocking": True,
            }
        )
    return findings


def normalize_findings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    findings: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        blocking = bool(item.get("blocking"))
        severity = str(item.get("severity") or "P2").upper()
        if severity in {"P0", "P1"}:
            blocking = True
        findings.append(
            {
                "id": str(item.get("id") or f"CR-{index:03d}"),
                "severity": severity,
                "category": str(item.get("category") or "maintainability"),
                "path": str(item.get("path") or ""),
                "line": item.get("line"),
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
                "evidence": str(item.get("evidence") or ""),
                "fix_suggestion": str(item.get("fix_suggestion") or ""),
                "blocking": blocking,
            }
        )
    return findings


def normalize_quality_gate(value: Any, blocking_count: int) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    passed = bool(payload.get("passed")) and blocking_count == 0
    return {
        "passed": passed,
        "blocking_findings": blocking_count,
        "risk_level": str(payload.get("risk_level") or ("low" if passed else "medium")),
    }


def normalize_review_status(value: Any, quality_gate: dict[str, Any]) -> str:
    status = str(value or "").strip().lower()
    if status not in {"passed", "needs_changes", "blocked"}:
        status = "passed" if quality_gate.get("passed") else "needs_changes"
    if quality_gate.get("passed") is False and status == "passed":
        status = "needs_changes"
    return status


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
