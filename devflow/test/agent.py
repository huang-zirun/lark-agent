from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devflow.code.tools import (
    CodeToolExecutor,
    capture_workspace_changes,
    compact_agent_action,
    compact_tool_events,
    compact_tool_result,
)
from devflow.config import LlmConfig
from devflow.llm import LlmError, UrlOpen, base_url_host, chat_completion, parse_llm_json
from devflow.solution.models import SCHEMA_VERSION as SOLUTION_SCHEMA_VERSION
from devflow.test.models import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION
from devflow.test.prompt import TEST_GENERATION_SYSTEM_PROMPT, build_test_generation_user_prompt
from devflow.test.runners import detect_test_stack

if TYPE_CHECKING:
    from devflow.trace import StageTrace


def _load_reference_docs_for_test() -> list[dict[str, Any]]:
    try:
        from devflow.config import load_config
        from devflow.references.registry import ReferenceRegistry
        config = load_config()
        if not config.reference.enabled:
            return []
        registry = ReferenceRegistry()
        return registry.get_documents_for_stage(
            "test_generation",
            max_total_chars=config.reference.max_chars_per_stage,
        )
    except Exception:
        return []


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
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": TEST_GENERATION_SYSTEM_PROMPT
            + "\n只返回一个合法 JSON object，不要包含 markdown 代码块。",
        }
    ]
    finish: dict[str, Any] | None = None
    completions: list[dict[str, Any]] = []
    reference_documents = _load_reference_docs_for_test()

    for turn in range(1, max_turns + 1):
        prompt_reference_docs = reference_documents if turn == 1 else _reference_doc_summaries(reference_documents)
        messages.append(
            {
                "role": "user",
                "content": build_test_generation_user_prompt(
                    requirement,
                    solution,
                    code_generation,
                    detected_stack,
                    compact_tool_events(executor.events),
                    reference_documents=prompt_reference_docs,
                ),
            }
        )
        if stage_trace is not None:
            stage_trace.event("test_llm_started", status="running", payload={"turn": turn, "model": llm_config.model})
        completion = chat_completion(llm_config, messages, opener=opener)
        completions.append(completion.to_audit_payload())
        if stage_trace is not None:
            request_path = stage_trace.write_json_artifact(
                f"test-llm-request-turn{turn}.json",
                completion.request_body,
            )
            response_path = stage_trace.write_json_artifact(
                f"test-llm-response-turn{turn}.json",
                completion.to_audit_payload(),
            )
            stage_trace.event(
                "test_llm_completed",
                status="success",
                duration_ms=completion.duration_ms,
                payload={
                    "turn": turn,
                    "request_path": str(request_path),
                    "response_path": str(response_path),
                    "token_usage": completion.usage,
                    "usage_source": completion.usage_source,
                },
            )
        action = normalize_agent_action(parse_llm_json(completion.content))
        messages.append({"role": "assistant", "content": json.dumps(compact_agent_action(action), ensure_ascii=False)})
        if action["action"] == "finish":
            finish = action
            break
        result = executor.execute(action["tool"], action["input"])
        messages.append({"role": "user", "content": json.dumps({"tool_result": compact_tool_result(result)}, ensure_ascii=False)})
        if stage_trace is not None:
            stage_trace.event("test_tool_completed", status="success", payload=executor.events[-1])

    if finish is None:
        raise LlmError("测试生成 agent 达到最大轮数但没有返回 finish。")

    workspace_changes = capture_workspace_changes(workspace_root)
    generated_tests = _text_list(finish.get("generated_tests"))
    production_paths = _production_paths(code_generation, solution)
    test_validity = assess_test_validity(
        workspace_root,
        generated_tests=generated_tests,
        production_paths=production_paths,
    )
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
        "generated_tests": generated_tests,
        "test_commands": _test_commands(executor.events),
        "test_validity": test_validity,
        "summary": str(finish.get("summary") or "").strip(),
        "warnings": _text_list(finish.get("warnings")),
        "tool_events": executor.events,
        "workspace_changes": workspace_changes,
        "diff": workspace_changes.get("diff", ""),
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


def assess_test_validity(
    workspace_root: Path | str,
    *,
    generated_tests: list[str],
    production_paths: list[str],
) -> dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve()
    normalized_tests = [path.replace("\\", "/") for path in generated_tests if path]
    normalized_production = [path.replace("\\", "/") for path in production_paths if path]
    reasons: list[str] = []
    if not normalized_tests:
        return {
            "proves_production_code": True,
            "reasons": ["未生成新测试，沿用已有验证结果。"],
            "production_paths": normalized_production,
            "generated_tests": normalized_tests,
        }
    if not normalized_production:
        return {
            "proves_production_code": False,
            "reasons": ["缺少可验证的生产代码路径。"],
            "production_paths": normalized_production,
            "generated_tests": normalized_tests,
        }

    any_reference = False
    copied_without_reference: list[str] = []
    for test_rel in normalized_tests:
        test_path = (root / test_rel).resolve()
        try:
            content = test_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            reasons.append(f"{test_rel} 无法读取，不能证明生产代码。")
            continue
        if _looks_like_copied_logic(content):
            copied_without_reference.append(test_rel)
        elif any(_references_production_path(content, prod) for prod in normalized_production):
            any_reference = True
        else:
            reasons.append(f"{test_rel} 未引用或执行生产代码文件。")

    for path in copied_without_reference:
        reasons.append(f"{path} 复制了生产逻辑但未引用生产代码。")
    proves = any_reference and not copied_without_reference
    return {
        "proves_production_code": proves,
        "reasons": [] if proves else reasons,
        "production_paths": normalized_production,
        "generated_tests": normalized_tests,
    }


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


def _production_paths(code_generation: dict[str, Any], solution: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    changes = code_generation.get("workspace_changes")
    if isinstance(changes, dict):
        candidates.extend(_text_list(changes.get("changed_files")))
    candidates.extend(_text_list(code_generation.get("changed_files")))
    for item in solution.get("change_plan") if isinstance(solution.get("change_plan"), list) else []:
        if isinstance(item, dict):
            candidates.extend(_text_list(item.get("path")))
    result: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        rel = path.replace("\\", "/")
        parts = Path(rel).parts
        if any(part in {"test", "tests", "__tests__"} for part in parts):
            continue
        if rel.endswith((".test.js", ".spec.js", "_test.py")):
            continue
        if rel and rel not in seen:
            seen.add(rel)
            result.append(rel)
    return result


def _references_production_path(content: str, production_path: str) -> bool:
    normalized = content.replace("\\", "/")
    path = production_path.replace("\\", "/")
    stem = Path(path).stem
    basename = Path(path).name
    if path in normalized or basename in normalized:
        return True
    if re.search(rf"\bfrom\s+{re.escape(stem)}\s+import\b", normalized):
        return True
    if re.search(rf"\bimport\s+{re.escape(stem)}\b", normalized):
        return True
    if re.search(rf"require\(['\"].*{re.escape(stem)}(?:\.[A-Za-z0-9]+)?['\"]\)", normalized):
        return True
    if re.search(rf"from\s+['\"].*{re.escape(stem)}(?:\.[A-Za-z0-9]+)?['\"]", normalized):
        return True
    return False


def _looks_like_copied_logic(content: str) -> bool:
    lowered = content.lower()
    markers = ("复制", "提取", "copy", "copied", "mocked game constants", "模拟游戏常量")
    return any(marker in lowered for marker in markers)


def _reference_doc_summaries(reference_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": doc.get("name"),
            "title": doc.get("title"),
            "loaded": True,
            "content_chars": len(str(doc.get("content") or "")),
        }
        for doc in reference_documents
    ]


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
