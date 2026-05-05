from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devflow.config import LlmConfig, ReferenceConfig
from devflow.llm import LlmError, UrlOpen, base_url_host, chat_completion, parse_llm_json
from devflow.solution.models import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION
from devflow.solution.prompt import SOLUTION_DESIGN_ARCHITECT_PROMPT
from devflow.solution.workspace import build_codebase_context

if TYPE_CHECKING:
    from devflow.trace import StageTrace


REQUIREMENT_SCHEMA_VERSION = "devflow.requirement.v1"


SOLUTION_RESPONSE_SHAPE = {
    "schema_version": SCHEMA_VERSION,
    "architecture_analysis": {
        "current_architecture": ["..."],
        "related_modules": ["..."],
        "constraints": ["..."],
        "reusable_patterns": ["..."],
    },
    "proposed_solution": {
        "summary": "...",
        "data_flow": ["..."],
        "implementation_steps": ["..."],
    },
    "change_plan": [
        {
            "path": "relative/path.ext",
            "action": "add|modify|delete",
            "responsibility": "...",
        }
    ],
    "api_design": {
        "cli": ["..."],
        "python": ["..."],
        "json_contracts": ["..."],
        "external": ["..."],
    },
    "testing_strategy": {
        "unit_tests": ["..."],
        "integration_tests": ["..."],
        "acceptance_mapping": ["..."],
        "regression_tests": ["..."],
    },
    "risks_and_assumptions": {
        "risks": ["..."],
        "assumptions": ["..."],
        "open_questions": ["..."],
    },
    "human_review": {
        "status": "pending",
        "checklist": ["..."],
    },
    "quality": {
        "completeness_score": 0.8,
        "risk_level": "low|medium|high",
        "ready_for_code_generation": True,
        "warnings": ["..."],
    },
}


def load_requirement_artifact(path: Path | str) -> dict[str, Any]:
    requirement_path = Path(path)
    try:
        payload = json.loads(requirement_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"需求文件不是有效 JSON：{requirement_path}。") from exc
    except OSError as exc:
        raise ValueError(f"无法读取需求文件：{requirement_path}。") from exc
    validate_requirement_artifact(payload)
    return payload


def validate_requirement_artifact(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("需求产物必须是 JSON object。")
    if payload.get("schema_version") != REQUIREMENT_SCHEMA_VERSION:
        raise ValueError("需求产物 schema_version 必须是 devflow.requirement.v1。")
    if not isinstance(payload.get("normalized_requirement"), dict):
        raise ValueError("需求产物缺少 normalized_requirement。")


def build_solution_design_artifact(
    requirement: dict[str, Any],
    workspace: dict[str, Any],
    llm_config: LlmConfig,
    *,
    requirement_path: Path | str | None = None,
    stage_trace: "StageTrace | None" = None,
    opener: UrlOpen | None = None,
    reference_config: "ReferenceConfig | None" = None,
) -> dict[str, Any]:
    validate_requirement_artifact(requirement)
    codebase_context = build_codebase_context(Path(workspace["path"]), reference_config=reference_config)
    if stage_trace is not None:
        stage_trace.event(
            "codebase_context_built",
            status="success",
            payload={
                "root": codebase_context["root"],
                "included_file_count": codebase_context["included_file_count"],
                "context_character_count": codebase_context["context_character_count"],
            },
        )

    messages = [
        {
            "role": "system",
            "content": SOLUTION_DESIGN_ARCHITECT_PROMPT
            + "\n只返回一个合法 JSON object，不要包含 markdown 代码块。",
        },
        {
            "role": "user",
            "content": build_solution_design_user_prompt(requirement, workspace, codebase_context),
        },
    ]
    if stage_trace is not None:
        stage_trace.event(
            "solution_llm_started",
            status="running",
            payload={
                "provider": llm_config.provider,
                "model": llm_config.model,
                "temperature": llm_config.temperature,
                "max_tokens": llm_config.max_tokens,
            },
        )
    try:
        completion = chat_completion(llm_config, messages, opener=opener)
    except LlmError:
        if stage_trace is not None:
            stage_trace.event("solution_llm_failed", status="failed")
        raise

    if stage_trace is not None:
        request_path = stage_trace.write_json_artifact(
            "solution-llm-request.json",
            completion.request_body,
        )
        response_path = stage_trace.write_json_artifact(
            "solution-llm-response.json",
            completion.to_audit_payload(),
        )
        stage_trace.event(
            "solution_llm_completed",
            status="success",
            duration_ms=completion.duration_ms,
            payload={
                "request_path": str(request_path),
                "response_path": str(response_path),
                "token_usage": completion.usage,
                "usage_source": completion.usage_source,
            },
        )

    solution = normalize_solution_design(parse_llm_json(completion.content))
    return build_solution_payload(
        requirement=requirement,
        workspace=workspace,
        codebase_context=codebase_context,
        solution=solution,
        llm_config=llm_config,
        requirement_path=requirement_path,
    )


def build_solution_design_user_prompt(
    requirement: dict[str, Any],
    workspace: dict[str, Any],
    codebase_context: dict[str, Any],
) -> str:
    requirement_summary = build_requirement_summary(requirement)
    prompt_payload = {
        "schema_version": SCHEMA_VERSION,
        "requirement_summary": requirement_summary,
        "workspace": workspace,
        "codebase_context": {
            "root": codebase_context.get("root"),
            "excluded_directories": codebase_context.get("excluded_directories"),
            "tree": codebase_context.get("tree", [])[:120],
            "files": [
                {
                    "path": item.get("path"),
                    "summary": item.get("summary"),
                    "content": item.get("content"),
                }
                for item in codebase_context.get("files", [])[:40]
            ],
        },
        "reference_documents": codebase_context.get("reference_documents", []),
    }
    return (
        "请基于下面 JSON 输出技术方案，只返回一个 JSON object。\n"
        "字段名必须保持英文；所有人类可读字段值必须使用简体中文。\n"
        "必须包含字段：architecture_analysis, proposed_solution, change_plan, "
        "api_design, testing_strategy, risks_and_assumptions, human_review, quality。\n"
        "quality.risk_level 使用 low/medium/high，human_review.status 固定为 pending。\n\n"
        "architecture_analysis, proposed_solution, api_design, testing_strategy "
        "must be JSON objects, not strings.\n\n"
        "Expected response shape:\n"
        f"{json.dumps(SOLUTION_RESPONSE_SHAPE, ensure_ascii=False, indent=2)}\n\n"
        "Input context:\n"
        f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
    )


def normalize_solution_design(payload: dict[str, Any]) -> dict[str, Any]:
    required = [
        "architecture_analysis",
        "proposed_solution",
        "change_plan",
        "api_design",
        "testing_strategy",
        "risks_and_assumptions",
        "human_review",
        "quality",
    ]
    for key in required:
        if key not in payload:
            raise LlmError(f"LLM 方案响应缺少必填字段：{key}。")

    architecture = _section_payload(payload["architecture_analysis"], "architecture_analysis", "current_architecture")
    proposed = _section_payload(payload["proposed_solution"], "proposed_solution", "summary")
    api_design = _section_payload(payload["api_design"], "api_design", "external")
    testing = _section_payload(payload["testing_strategy"], "testing_strategy", "unit_tests")
    risks = _section_payload(payload["risks_and_assumptions"], "risks_and_assumptions", "risks")
    human_review = _section_payload(payload["human_review"], "human_review", "checklist")
    quality = _dict_payload(payload["quality"], "quality")

    return {
        "architecture_analysis": {
            "current_architecture": _text_list(architecture.get("current_architecture")),
            "related_modules": _text_list(architecture.get("related_modules")),
            "constraints": _text_list(architecture.get("constraints")),
            "reusable_patterns": _text_list(architecture.get("reusable_patterns")),
        },
        "proposed_solution": {
            "summary": _text(proposed.get("summary")) or "暂无方案摘要。",
            "data_flow": _text_list(proposed.get("data_flow")),
            "implementation_steps": _text_list(proposed.get("implementation_steps")),
        },
        "change_plan": _change_plan(payload["change_plan"]),
        "api_design": {
            "cli": _text_list(api_design.get("cli")),
            "python": _text_list(api_design.get("python")),
            "json_contracts": _text_list(api_design.get("json_contracts")),
            "external": _text_list(api_design.get("external")),
        },
        "testing_strategy": {
            "unit_tests": _text_list(testing.get("unit_tests")),
            "integration_tests": _text_list(testing.get("integration_tests")),
            "acceptance_mapping": _text_list(testing.get("acceptance_mapping")),
            "regression_tests": _text_list(testing.get("regression_tests")),
        },
        "risks_and_assumptions": {
            "risks": _text_list(risks.get("risks")),
            "assumptions": _text_list(risks.get("assumptions")),
            "open_questions": _text_list(risks.get("open_questions")),
        },
        "human_review": {
            "status": "pending",
            "checklist": _text_list(human_review.get("checklist") or human_review.get("review_items")),
        },
        "quality": {
            "completeness_score": _score(quality.get("completeness_score")),
            "risk_level": _risk_level(quality.get("risk_level")),
            "ready_for_code_generation": _ready_for_code_generation(quality),
            "warnings": _quality_warnings(quality),
        },
    }


def build_solution_payload(
    *,
    requirement: dict[str, Any],
    workspace: dict[str, Any],
    codebase_context: dict[str, Any],
    solution: dict[str, Any],
    llm_config: LlmConfig,
    requirement_path: Path | str | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "agent": AGENT_NAME,
            "agent_version": AGENT_VERSION,
            "created_at": utc_now(),
            "system_prompt_id": "SolutionDesignArchitect.v1",
            "model": llm_config.model,
            "llm_provider": llm_config.provider,
            "llm_base_url_host": base_url_host(llm_config),
            "requirement_path": str(requirement_path) if requirement_path is not None else None,
        },
        "workspace": workspace,
        "requirement_summary": build_requirement_summary(requirement),
        "codebase_context": codebase_context,
        "architecture_analysis": solution["architecture_analysis"],
        "proposed_solution": solution["proposed_solution"],
        "change_plan": solution["change_plan"],
        "api_design": solution["api_design"],
        "testing_strategy": solution["testing_strategy"],
        "risks_and_assumptions": solution["risks_and_assumptions"],
        "human_review": solution["human_review"],
        "quality": solution["quality"],
        "prompt": {
            "system_prompt": SOLUTION_DESIGN_ARCHITECT_PROMPT,
            "distilled_from": [
                "DevFlow Engine 功能一",
                "claw-code-main PROJECT_ANALYSIS.md design principles",
            ],
        },
        "reference_documents_used": [
            {"name": doc.get("name"), "title": doc.get("title"), "chars_injected": len(doc.get("content", ""))}
            for doc in codebase_context.get("reference_documents", [])
        ],
    }


def build_requirement_summary(requirement: dict[str, Any]) -> dict[str, Any]:
    normalized = _dict_payload(requirement.get("normalized_requirement"), "normalized_requirement")
    return {
        "title": _text(normalized.get("title")) or "未命名需求",
        "goals": _text_list(normalized.get("goals")),
        "scope": _text_list(normalized.get("scope")),
        "acceptance_criteria": [
            {
                "id": _text(item.get("id")) or f"AC-{index:03d}",
                "criterion": _text(item.get("criterion")) or "",
            }
            for index, item in enumerate(requirement.get("acceptance_criteria") or [], start=1)
            if isinstance(item, dict)
        ],
        "open_questions": requirement.get("open_questions") if isinstance(requirement.get("open_questions"), list) else [],
        "ready_for_next_stage": bool(_dict_payload(requirement.get("quality") or {}, "quality").get("ready_for_next_stage")),
    }


def write_solution_artifact(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def _change_plan(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise LlmError("LLM 方案响应字段必须是数组：change_plan。")
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        path = _text(item.get("path") or item.get("file_path")).lstrip("/\\")
        if not path:
            continue
        result.append(
            {
                "path": path,
                "action": _text(item.get("action") or item.get("change_type")) or "modify",
                "responsibility": _text(item.get("responsibility") or item.get("description")) or "待细化。",
            }
        )
    return result


def _section_payload(value: Any, field: str, text_key: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = _text(value)
    if text:
        return {text_key: text}
    raise LlmError(f"LLM 方案响应字段必须是对象：{field}。")


def _dict_payload(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LlmError(f"LLM 方案响应字段必须是对象：{field}。")
    return value


def _ready_for_code_generation(quality: dict[str, Any]) -> bool:
    if "ready_for_code_generation" in quality:
        return bool(quality.get("ready_for_code_generation"))
    return True


def _quality_warnings(quality: dict[str, Any]) -> list[str]:
    warnings = _text_list(quality.get("warnings"))
    for key in ("test_coverage", "maintainability"):
        text = _text(quality.get(key))
        if text:
            warnings.append(text)
    return warnings


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [text for item in value if (text := _text(item))]
    text = _text(value)
    return [text] if text else []


def _score(value: Any) -> float:
    if isinstance(value, int | float):
        return round(max(0.0, min(1.0, float(value))), 2)
    if isinstance(value, str):
        try:
            return round(max(0.0, min(1.0, float(value.strip()))), 2)
        except ValueError:
            return 0.0
    return 0.0


def _risk_level(value: Any) -> str:
    text = _text(value).lower()
    if text in {"low", "medium", "high"}:
        return text
    return "medium"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
