from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from devflow.config import LlmConfig
from devflow.intake.models import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION, RequirementSource
from devflow.intake.prompt import PRODUCT_REQUIREMENT_ANALYST_PROMPT
from devflow.llm import LlmError, base_url_host, chat_completion, chat_completion_content, parse_llm_json

if TYPE_CHECKING:
    from devflow.trace import StageTrace


MAX_TOP_LEVEL_SUMMARY_CHARS = 600
SECTION_CHUNK_CHARS = 2800


def _load_reference_docs_for_intake() -> list[dict[str, Any]]:
    try:
        from devflow.config import load_config, ReferenceConfig
        from devflow.references.registry import ReferenceRegistry
        config = load_config()
        if not config.reference.enabled:
            return []
        registry = ReferenceRegistry()
        return registry.get_documents_for_stage(
            "requirement_intake",
            max_total_chars=config.reference.max_chars_per_stage,
        )
    except Exception:
        return []


def build_requirement_artifact(
    source: RequirementSource,
    model: str = "heuristic-local-v1",
    analyzer: str = "heuristic",
    llm_config: LlmConfig | None = None,
    stage_trace: "StageTrace | None" = None,
) -> dict[str, Any]:
    if analyzer == "llm":
        if llm_config is None:
            raise LlmError("LLM 分析器需要已加载的 llm 配置。")
        return build_llm_requirement_artifact(source, llm_config, stage_trace=stage_trace)
    if analyzer != "heuristic":
        raise ValueError(f"不支持的 analyzer：{analyzer}。")

    source.ensure_content()
    content = normalize_text(source.content)
    title = source.title or infer_title(content)
    sections = build_sections(content)
    extracted = extract_product_fields(content)
    open_questions = build_open_questions(extracted, content=content)
    acceptance_criteria = build_acceptance_criteria(content, extracted)
    quality = build_quality(extracted, acceptance_criteria, open_questions, content=content)
    analysis = {
        "normalized_requirement": {
            "title": title,
            "background": extracted["background"],
            "target_users": extracted["target_users"],
            "problem": extracted["problem"],
            "goals": extracted["goals"],
            "non_goals": extracted["non_goals"],
            "scope": extracted["scope"],
        },
        "product_analysis": {
            "user_scenarios": extracted["user_scenarios"],
            "business_value": extracted["business_value"],
            "evidence": extracted["evidence"],
            "assumptions": extracted["assumptions"],
            "risks": extracted["risks"],
            "dependencies": extracted["dependencies"],
        },
        "acceptance_criteria": acceptance_criteria,
        "open_questions": open_questions,
        "quality": quality,
    }
    return build_artifact_payload(
        source=source,
        content=content,
        title=title,
        sections=sections,
        analysis=analysis,
        implementation_hints=build_implementation_hints(source, sections, extracted),
        metadata_extra={"model": model, "analyzer": "heuristic"},
    )


def build_llm_requirement_artifact(
    source: RequirementSource,
    llm_config: LlmConfig,
    *,
    stage_trace: "StageTrace | None" = None,
) -> dict[str, Any]:
    source.ensure_content()
    content = normalize_text(source.content)
    title = source.title or infer_title(content)
    sections = build_sections(content)
    analysis = analyze_with_llm(source, content, sections, llm_config, stage_trace=stage_trace)
    extracted = {
        **analysis["normalized_requirement"],
        **analysis["product_analysis"],
    }
    return build_artifact_payload(
        source=source,
        content=content,
        title=title,
        sections=sections,
        analysis=analysis,
        implementation_hints=build_implementation_hints(source, sections, extracted),
        metadata_extra={
            "model": llm_config.model,
            "analyzer": "llm",
            "llm_provider": llm_config.provider,
            "llm_base_url_host": base_url_host(llm_config),
        },
    )


def build_artifact_payload(
    *,
    source: RequirementSource,
    content: str,
    title: str,
    sections: list[dict[str, Any]],
    analysis: dict[str, Any],
    implementation_hints: dict[str, Any],
    metadata_extra: dict[str, Any],
) -> dict[str, Any]:
    metadata = {
        "agent": AGENT_NAME,
        "agent_version": AGENT_VERSION,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "system_prompt_id": "ProductRequirementAnalyst.v1",
        "source_type": source.source_type,
        "source_id": source.source_id,
        "lark_identity": source.identity,
    }
    metadata.update(metadata_extra)

    input_history_entry = {
        "timestamp": metadata["created_at"],
        "mode": "generate",
        "trigger": "首次创建需求",
        "raw_input": content,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "source": {
            "reference": source.reference,
            "title": title,
            "safe_summary": summarize(content, MAX_TOP_LEVEL_SUMMARY_CHARS),
            "raw_character_count": len(content),
            "attachments": source.attachments,
            "embedded_resources": source.embedded_resources,
            "metadata": source.metadata,
        },
        "input_history": [input_history_entry],
        "normalized_requirement": analysis["normalized_requirement"],
        "product_analysis": analysis["product_analysis"],
        "acceptance_criteria": analysis["acceptance_criteria"],
        "implementation_hints": implementation_hints,
        "open_questions": analysis["open_questions"],
        "sections": sections,
        "quality": analysis["quality"],
        "prompt": {
            "distilled_from": [
                "Product-Manager-Skills/write-prd",
                "Product-Manager-Skills/prd-development",
                "Product-Manager-Skills/problem-statement",
                "Product-Manager-Skills/user-story",
            ],
            "system_prompt": PRODUCT_REQUIREMENT_ANALYST_PROMPT,
        },
    }


def analyze_with_llm(
    source: RequirementSource,
    content: str,
    sections: list[dict[str, Any]],
    llm_config: LlmConfig,
    *,
    stage_trace: "StageTrace | None" = None,
) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": PRODUCT_REQUIREMENT_ANALYST_PROMPT
            + "\n只返回一个合法 JSON object，不要包含 markdown 代码块。",
        },
        {
            "role": "user",
            "content": build_llm_user_prompt(source, content, sections, reference_documents=_load_reference_docs_for_intake()),
        },
    ]
    if stage_trace is not None:
        return analyze_with_traced_llm(llm_config, messages, stage_trace)
    response = chat_completion_content(llm_config, messages)
    return normalize_llm_analysis(parse_llm_json(response))


def analyze_with_traced_llm(
    llm_config: LlmConfig,
    messages: list[dict[str, str]],
    stage_trace: "StageTrace",
) -> dict[str, Any]:
    stage_trace.event(
        "llm_started",
        status="running",
        payload={
            "provider": llm_config.provider,
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
        },
    )
    try:
        completion = chat_completion(llm_config, messages)
        request_path = stage_trace.write_json_artifact("llm-request.json", completion.request_body)
        response_path = stage_trace.write_json_artifact(
            "llm-response.json",
            completion.to_audit_payload(),
        )
        stage_trace.event(
            "llm_completed",
            status="success",
            duration_ms=completion.duration_ms,
            payload={
                "request_path": str(request_path),
                "response_path": str(response_path),
                "token_usage": completion.usage,
                "usage_source": completion.usage_source,
            },
        )
        return normalize_llm_analysis(parse_llm_json(completion.content))
    except LlmError as exc:
        stage_trace.event("llm_failed", status="failed", payload={"error": str(exc)})
        raise


def build_llm_user_prompt(
    source: RequirementSource,
    content: str,
    sections: list[dict[str, Any]],
    reference_documents: list[dict[str, Any]] | None = None,
) -> str:
    section_index = [
        {
            "id": section["id"],
            "title": section["title"],
            "kind": section["kind"],
            "summary": section["summary"],
            "character_count": section["character_count"],
        }
        for section in sections
    ]
    return (
        "请分析下面的需求来源，并只返回包含这些顶层字段的 JSON："
        "normalized_requirement, product_analysis, acceptance_criteria, open_questions, quality。\n\n"
        "字段名必须保持英文，schema/枚举/机器消费值不要翻译；所有字段值、问题、告警、验收标准等人可读内容必须使用简体中文。\n\n"
        "结构要求：\n"
        "- normalized_requirement: title 字符串，background/target_users/problem/goals/non_goals/scope 为字符串数组。\n"
        "- product_analysis: user_stories 为对象数组（见下方详细结构），business_value/evidence/assumptions/risks/dependencies 为字符串数组。\n"
        "- acceptance_criteria: 对象数组，每个对象包含 id, source, criterion。验收标准必须使用 EARS 语法模式，可测试无歧义。\n"
        "- open_questions: 对象数组，每个对象包含 field, question, suggested_answer（建议答案，可选）, reasoning（推理依据，可选）。最多 3 个，按优先级排序：范围 > 安全/隐私 > 用户体验 > 技术细节。\n"
        "- quality: 对象，包含 completeness_score 数字、ambiguity_score 数字、ready_for_next_stage 布尔值、warnings 字符串数组、dimensions 对象（可选，包含 content_quality/requirement_completeness/functional_readiness，值为 clear/partial/missing）。\n\n"
        "user_stories 详细结构（product_analysis.user_stories）：\n"
        "每个用户故事是一个对象，包含：\n"
        "- id: 字符串，如 US-001、US-002\n"
        "- title: 简要标题\n"
        "- priority: P1（核心，必须实现）/P2（重要，应当实现）/P3（锦上添花，可以实现）\n"
        "- description: 使用中文表达'作为某类角色，我希望完成某个动作，以便获得某个收益'\n"
        "- priority_reason: 为什么是这个优先级\n"
        "- independent_test: 如何独立验证这个故事的价值\n"
        "- acceptance_scenarios: 对象数组，每个包含 given（初始状态）、when（用户操作）、then（预期结果）\n\n"
        f"来源类型: {source.source_type}\n"
        f"来源 ID: {source.source_id}\n"
        f"来源标题: {source.title or ''}\n"
        f"Section 索引 JSON: {section_index}\n\n"
        + _ref_docs_json(reference_documents) + "\n\n"
        + "来源 Markdown:\n"
        f"{content}"
    )


def normalize_llm_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    required = [
        "normalized_requirement",
        "product_analysis",
        "acceptance_criteria",
        "open_questions",
        "quality",
    ]
    for key in required:
        if key not in payload:
            raise LlmError(f"LLM 响应缺少必填字段：{key}。")

    normalized = _dict_payload(payload["normalized_requirement"], "normalized_requirement")
    product = _dict_payload(payload["product_analysis"], "product_analysis")
    quality = _dict_payload(payload["quality"], "quality")

    user_stories_raw = product.get("user_stories")
    user_stories = _user_stories_list(user_stories_raw) if isinstance(user_stories_raw, list) else []
    user_scenarios_from_stories = [us["description"] for us in user_stories if us.get("description")]
    user_scenarios_legacy = _text_list(product.get("user_scenarios"))
    user_scenarios = user_scenarios_from_stories if user_scenarios_from_stories else user_scenarios_legacy

    quality_dimensions = quality.get("dimensions")
    dimensions = None
    if isinstance(quality_dimensions, dict):
        dimensions = {
            "content_quality": _text(quality_dimensions.get("content_quality")) or "clear",
            "requirement_completeness": _text(quality_dimensions.get("requirement_completeness")) or "clear",
            "functional_readiness": _text(quality_dimensions.get("functional_readiness")) or "clear",
        }

    return {
        "normalized_requirement": {
            "title": _text(normalized.get("title")) or "未命名需求",
            "background": _text_list(normalized.get("background")),
            "target_users": _text_list(normalized.get("target_users")),
            "problem": _text_list(normalized.get("problem")),
            "goals": _text_list(normalized.get("goals")),
            "non_goals": _text_list(normalized.get("non_goals")),
            "scope": _text_list(normalized.get("scope")),
        },
        "product_analysis": {
            "user_stories": user_stories,
            "user_scenarios": user_scenarios,
            "business_value": _text_list(product.get("business_value")),
            "evidence": _text_list(product.get("evidence")),
            "assumptions": _text_list(product.get("assumptions")),
            "risks": _text_list(product.get("risks")),
            "dependencies": _text_list(product.get("dependencies")),
        },
        "acceptance_criteria": _criteria_list(payload["acceptance_criteria"]),
        "open_questions": _question_list(payload["open_questions"]),
        "quality": {
            "completeness_score": _score(quality.get("completeness_score")),
            "ambiguity_score": _score(quality.get("ambiguity_score")),
            "ready_for_next_stage": bool(quality.get("ready_for_next_stage")),
            "warnings": _text_list(quality.get("warnings")),
            **({"dimensions": dimensions} if dimensions else {}),
        },
    }


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def infer_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        return stripped[:120]
    return "未命名需求"


def extract_product_fields(content: str) -> dict[str, list[str]]:
    lines = meaningful_lines(content)
    field_specs = {
        "background": ["背景", "现状", "上下文", "context", "background", "痛点"],
        "target_users": ["用户", "角色", "persona", "使用者", "客户", "产品经理", "开发者"],
        "problem": ["问题", "痛点", "阻碍", "困难", "bug", "issue", "problem", "失败"],
        "goals": ["目标", "希望", "需要", "实现", "支持", "能够", "提升", "减少", "goal"],
        "non_goals": ["不做", "不包含", "非目标", "out of scope", "not included"],
        "scope": ["范围", "本期", "首版", "mvp", "scope", "阶段"],
        "user_scenarios": ["场景", "流程", "当用户", "作为", "scenario", "journey"],
        "business_value": ["价值", "收益", "指标", "提升", "减少", "转化", "效率", "metric"],
        "evidence": ["证据", "数据", "调研", "反馈", "用户说", "quote", "analytics"],
        "assumptions": ["假设", "前提", "预计", "可能", "assumption"],
        "risks": ["风险", "限制", "失败", "依赖不足", "risk"],
        "dependencies": ["依赖", "前置", "集成", "权限", "api", "接口", "dependency"],
    }
    extracted = {field: pick_lines(lines, keywords, limit=6) for field, keywords in field_specs.items()}
    if not extracted["goals"]:
        extracted["goals"] = infer_goal_lines(lines)
    if not extracted["problem"]:
        extracted["problem"] = infer_problem_lines(lines)
    return extracted


def meaningful_lines(content: str) -> list[str]:
    result: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = line.strip()
        if line:
            result.append(line)
    return result


def pick_lines(lines: list[str], keywords: list[str], limit: int) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            cleaned = clean_line(line)
            if cleaned not in seen:
                seen.add(cleaned)
                matches.append(cleaned)
        if len(matches) >= limit:
            break
    return matches


def infer_goal_lines(lines: list[str]) -> list[str]:
    return [
        clean_line(line)
        for line in lines
        if re.search(r"(需要|希望|实现|支持|能够|should|must|need)", line, re.IGNORECASE)
    ][:6]


def infer_problem_lines(lines: list[str]) -> list[str]:
    return [
        clean_line(line)
        for line in lines
        if re.search(r"(无法|不能|缺少|慢|复杂|confusing|slow|missing)", line, re.IGNORECASE)
    ][:6]


def build_acceptance_criteria(
    content: str,
    extracted: dict[str, list[str]],
) -> list[dict[str, str]]:
    explicit = []
    for line in meaningful_lines(content):
        if re.search(r"(验收|acceptance|given|when|then|场景|criteria)", line, re.IGNORECASE):
            explicit.append(clean_line(line))
        if re.match(r"^\[[ xX]\]", line):
            explicit.append(clean_line(line))

    criteria = []
    for index, line in enumerate(explicit[:8], start=1):
        criteria.append(
            {
                "id": f"AC-{index:03d}",
                "source": "explicit",
                "criterion": line,
            }
        )

    if criteria:
        return criteria

    goals = extracted.get("goals", [])
    for index, goal in enumerate(goals[:5], start=1):
        criteria.append(
            {
                "id": f"AC-{index:03d}",
                "source": "inferred",
                "criterion": f"给定目标用户场景，当该需求完成交付时，应能够验证：{goal}",
            }
        )
    return criteria


def build_open_questions(
    extracted: dict[str, list[str]],
    content: str | None = None,
) -> list[dict[str, str]]:
    question_specs = [
        ("target_users", "这个需求的主要目标用户或角色是谁？"),
        ("problem", "在决定方案前，需要先解决的具体用户问题是什么？"),
        ("goals", "哪些可衡量的产品或业务结果代表成功？"),
        ("scope", "首版范围具体包含哪些内容？"),
        ("non_goals", "本期需要明确排除哪些内容？"),
    ]
    questions: list[dict[str, str]] = []
    for field, question in question_specs:
        if not extracted.get(field):
            questions.append({"field": field, "question": question})

    if content:
        vague_questions = _detect_vague_expressions(content)
        questions.extend(vague_questions)

    return questions[:8]


_VAGUE_PATTERNS: list[tuple[str, str, str]] = [
    (r"(快速|高效|稳定|高性能|robust|fast|reliable|performant)", "性能需求未量化", "请明确具体的性能指标（如响应时间、吞吐量、可用性百分比）"),
    (r"(友好|直观|易用|intuitive|user-friendly|easy\s+to\s+use)", "用户体验描述主观", "请用可测试的交互标准替代主观评价（如'3次点击内完成任务'）"),
    (r"(等|等等|etc\.|and\s+so\s+on|\.\.\.)", "范围边界模糊", "请明确列举完整的范围项，避免使用'等'导致的范围歧义"),
]


def _detect_vague_expressions(content: str) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    seen_fields: set[str] = set()
    for pattern, field_label, suggestion in _VAGUE_PATTERNS:
        if field_label in seen_fields:
            continue
        if re.search(pattern, content, re.IGNORECASE):
            seen_fields.add(field_label)
            questions.append({
                "field": "vague_expression",
                "question": f"需求中包含模糊表述（{field_label}），{suggestion}",
                "suggested_answer": suggestion.split("（")[1].rstrip("）") if "（" in suggestion else suggestion,
                "reasoning": "模糊表述会导致下游实现理解不一致，需量化为可测试的标准",
            })
    return questions


def _dict_payload(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LlmError(f"LLM 响应字段必须是对象：{field}。")
    return value


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


def _criteria_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise LlmError("LLM 响应字段必须是数组：acceptance_criteria。")
    criteria: list[dict[str, str]] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            criterion = _text(item.get("criterion"))
            if criterion:
                criteria.append(
                    {
                        "id": _text(item.get("id")) or f"AC-{index:03d}",
                        "source": _text(item.get("source")) or "llm",
                        "criterion": criterion,
                    }
                )
        else:
            criterion = _text(item)
            if criterion:
                criteria.append(
                    {"id": f"AC-{index:03d}", "source": "llm", "criterion": criterion}
                )
    return criteria


def _question_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise LlmError("LLM 响应字段必须是数组：open_questions。")
    questions: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            question = _text(item.get("question"))
            if question:
                entry: dict[str, str] = {"field": _text(item.get("field")) or "general", "question": question}
                suggested = _text(item.get("suggested_answer"))
                if suggested:
                    entry["suggested_answer"] = suggested
                reasoning = _text(item.get("reasoning"))
                if reasoning:
                    entry["reasoning"] = reasoning
                questions.append(entry)
        else:
            question = _text(item)
            if question:
                questions.append({"field": "general", "question": question})
    return questions


def _user_stories_list(value: list[Any]) -> list[dict[str, Any]]:
    stories: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            desc = _text(item)
            if desc:
                stories.append({
                    "id": f"US-{index:03d}",
                    "title": "",
                    "priority": "P2",
                    "description": desc,
                    "priority_reason": "",
                    "independent_test": "",
                    "acceptance_scenarios": [],
                })
            continue
        story_id = _text(item.get("id")) or f"US-{index:03d}"
        description = _text(item.get("description"))
        if not description:
            continue
        scenarios_raw = item.get("acceptance_scenarios")
        scenarios = []
        if isinstance(scenarios_raw, list):
            for sc in scenarios_raw:
                if isinstance(sc, dict):
                    scenarios.append({
                        "given": _text(sc.get("given")) or "",
                        "when": _text(sc.get("when")) or "",
                        "then": _text(sc.get("then")) or "",
                    })
        stories.append({
            "id": story_id,
            "title": _text(item.get("title")) or "",
            "priority": _text(item.get("priority")) or "P2",
            "description": description,
            "priority_reason": _text(item.get("priority_reason")) or "",
            "independent_test": _text(item.get("independent_test")) or "",
            "acceptance_scenarios": scenarios,
        })
    return stories


def _score(value: Any) -> float:
    if isinstance(value, int | float):
        return round(max(0.0, min(1.0, float(value))), 2)
    if isinstance(value, str):
        try:
            return round(max(0.0, min(1.0, float(value.strip()))), 2)
        except ValueError:
            return 0.0
    return 0.0


def build_quality(
    extracted: dict[str, list[str]],
    acceptance_criteria: list[dict[str, str]],
    open_questions: list[dict[str, str]],
    content: str | None = None,
) -> dict[str, Any]:
    required = ["target_users", "problem", "goals", "scope"]
    present = sum(1 for field in required if extracted.get(field))
    if acceptance_criteria:
        present += 1
    completeness = round(present / 5, 2)

    vague_count = sum(1 for q in open_questions if q.get("field") == "vague_expression")
    ambiguity = round(min(1.0, (len(open_questions) + vague_count * 0.5) / 5), 2)

    content_quality = "clear"
    requirement_completeness = "clear" if completeness >= 0.6 else ("partial" if completeness >= 0.4 else "missing")
    functional_readiness = "clear" if acceptance_criteria else "partial"

    if content and vague_count > 0:
        content_quality = "partial"

    return {
        "completeness_score": completeness,
        "ambiguity_score": ambiguity,
        "ready_for_next_stage": completeness >= 0.6 and ambiguity <= 0.6,
        "warnings": build_quality_warnings(completeness, ambiguity, acceptance_criteria, vague_count),
        "dimensions": {
            "content_quality": content_quality,
            "requirement_completeness": requirement_completeness,
            "functional_readiness": functional_readiness,
        },
    }


def build_quality_warnings(
    completeness: float,
    ambiguity: float,
    acceptance_criteria: list[dict[str, str]],
    vague_count: int = 0,
) -> list[str]:
    warnings: list[str] = []
    if completeness < 0.6:
        warnings.append("需求缺少关键产品上下文。")
    if ambiguity > 0.6:
        warnings.append("进入方案设计前仍有较多开放问题。")
    if not acceptance_criteria:
        warnings.append("未能推断出可测试的验收标准。")
    if vague_count > 0:
        warnings.append(f"需求中包含 {vague_count} 处模糊表述，建议量化为可测试标准。")
    return warnings


def build_implementation_hints(
    source: RequirementSource,
    sections: list[dict[str, Any]],
    extracted: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "handoff_note": (
            "优先阅读 normalized_requirement 和 acceptance_criteria。"
            "只有需要更多来源上下文时，再按 id 读取 sections。"
        ),
        "source_type": source.source_type,
        "recommended_next_agent": "solution-design-agent",
        "relevant_section_ids": [section["id"] for section in sections[:5]],
        "avoid_premature_decisions": [
            "在完成仓库上下文索引前，不要选择具体实现文件。",
            "不要把推断出的验收标准当作已经确认的产品决策。",
        ],
        "possible_dependency_topics": extracted.get("dependencies", []),
    }


def build_sections(content: str, chunk_chars: int = SECTION_CHUNK_CHARS) -> list[dict[str, Any]]:
    heading_sections = split_by_markdown_headings(content)
    if len(heading_sections) <= 1:
        chunks = split_by_size(content, chunk_chars)
        return [
            section_payload(index, f"片段 {index}", "chunk", chunk)
            for index, chunk in enumerate(chunks, start=1)
        ]

    sections: list[dict[str, Any]] = []
    for title, body in heading_sections:
        chunks = split_by_size(body, chunk_chars)
        for chunk in chunks:
            sections.append(section_payload(len(sections) + 1, title, "heading", chunk))
    return sections


def split_by_markdown_headings(content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "概览"
    current_lines: list[str] = []
    saw_heading = False
    for line in content.splitlines():
        if re.match(r"^#{1,6}\s+\S", line):
            if current_lines:
                sections.append((current_title, current_lines))
                current_lines = []
            current_title = line.lstrip("#").strip()[:120]
            saw_heading = True
        current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))
    if not saw_heading:
        return [("全文", content)]
    return [(title, "\n".join(lines).strip()) for title, lines in sections if "\n".join(lines).strip()]


def split_by_size(content: str, chunk_chars: int) -> list[str]:
    if len(content) <= chunk_chars:
        return [content]
    paragraphs = re.split(r"\n\s*\n", content)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > chunk_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(paragraph[i : i + chunk_chars] for i in range(0, len(paragraph), chunk_chars))
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) > chunk_chars:
            chunks.append(current.strip())
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks


def section_payload(index: int, title: str, kind: str, content: str) -> dict[str, Any]:
    return {
        "id": f"sec-{index:03d}",
        "title": title or f"章节 {index}",
        "kind": kind,
        "summary": summarize(content, 240),
        "content_ref": f"$.sections[{index - 1}].content",
        "content": content,
        "character_count": len(content),
    }


def summarize(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def _ref_docs_json(docs: list[dict[str, Any]] | None) -> str:
    if not docs:
        return "参考文档: []"
    import json
    return f"参考文档: {json.dumps(docs, ensure_ascii=False, indent=2)}"


def clean_line(line: str) -> str:
    line = re.sub(r"^#+\s*", "", line.strip())
    line = re.sub(r"^\[[ xX]\]\s*", "", line)
    return line[:500]
