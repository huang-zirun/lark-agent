from __future__ import annotations

from typing import Any


def render_prd_markdown(artifact: dict[str, Any], *, run_id: str | None = None) -> str:
    normalized = _dict(artifact.get("normalized_requirement"))
    analysis = _dict(artifact.get("product_analysis"))
    quality = _dict(artifact.get("quality"))
    title = _text(normalized.get("title")) or "未命名需求"

    lines: list[str] = [f"# {title}", ""]
    if run_id:
        lines.extend(["## 运行信息", "", f"- 运行 ID：{run_id}", ""])

    _append_input_history(lines, artifact.get("input_history"))
    _append_list_section(lines, "背景", _list(normalized.get("background")))
    _append_list_section(lines, "目标用户", _list(normalized.get("target_users")))
    _append_list_section(lines, "核心问题", _list(normalized.get("problem")))
    _append_list_section(lines, "目标", _list(normalized.get("goals")))
    _append_list_section(lines, "范围", _list(normalized.get("scope")))
    _append_list_section(lines, "非目标", _list(normalized.get("non_goals")))
    _append_user_stories(lines, analysis.get("user_stories"))
    _append_list_section(lines, "用户场景", _list(analysis.get("user_scenarios")))
    _append_list_section(lines, "业务价值", _list(analysis.get("business_value")))
    _append_list_section(lines, "证据", _list(analysis.get("evidence")))
    _append_list_section(lines, "假设", _list(analysis.get("assumptions")))
    _append_list_section(lines, "风险", _list(analysis.get("risks")))
    _append_list_section(lines, "依赖", _list(analysis.get("dependencies")))
    _append_acceptance_criteria(lines, artifact.get("acceptance_criteria"))
    _append_open_questions(lines, artifact.get("open_questions"))
    _append_quality(lines, quality)

    return "\n".join(lines).rstrip() + "\n"


def build_prd_preview_card(
    artifact: dict[str, Any],
    *,
    run_id: str,
    detected_input: dict[str, Any],
    prd_url: str,
) -> dict[str, Any]:
    normalized = _dict(artifact.get("normalized_requirement"))
    quality = _dict(artifact.get("quality"))
    title = _text(normalized.get("title")) or "未命名需求"
    ready = "是" if quality.get("ready_for_next_stage") else "否"
    input_kind = _text(detected_input.get("kind")) or "unknown"

    doc_link_text = (
        f"[查看完整 PRD 文档]({prd_url})"
        if prd_url
        else "**PRD 文档**：已创建，暂未返回链接"
    )
    summary_lines = [
        f"**运行 ID**：{run_id}",
        f"**输入类型**：{input_kind}",
        f"**可进入下一阶段**：{ready}",
    ]

    body = "\n".join(summary_lines)
    problem = _preview_list("核心问题", _list(normalized.get("problem")))
    goals = _preview_list("目标", _list(normalized.get("goals")))
    acceptance = _preview_acceptance(artifact.get("acceptance_criteria"))
    questions = _preview_open_questions(artifact.get("open_questions"))

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green" if quality.get("ready_for_next_stage") else "orange",
            "title": {"tag": "plain_text", "content": f"DevFlow PRD：{title}"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": doc_link_text}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": problem}},
            {"tag": "div", "text": {"tag": "lark_md", "content": goals}},
            {"tag": "div", "text": {"tag": "lark_md", "content": acceptance}},
            {"tag": "div", "text": {"tag": "lark_md", "content": questions}},
        ],
    }


def _append_input_history(lines: list[str], value: Any) -> None:
    lines.extend(["## 输入历史", ""])
    entries = value if isinstance(value, list) else []
    if not entries:
        lines.extend(["- 暂无记录。", ""])
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        timestamp = _text(entry.get("timestamp")) or ""
        mode = _text(entry.get("mode")) or "unknown"
        trigger = _text(entry.get("trigger")) or ""
        raw_input = _text(entry.get("raw_input")) or ""
        lines.append(f"### {timestamp} · {mode.capitalize()} · {trigger}")
        lines.append("")
        if raw_input:
            for raw_line in raw_input.splitlines():
                lines.append(f"> {raw_line}")
        lines.append("")


def _append_user_stories(lines: list[str], value: Any) -> None:
    lines.extend(["## 用户故事", ""])
    stories = value if isinstance(value, list) else []
    if not stories:
        lines.extend(["- 暂无明确内容。", ""])
        return
    for item in stories:
        if not isinstance(item, dict):
            lines.append(f"- {_text(item) or '暂无明确内容。'}")
            continue
        story_id = _text(item.get("id")) or "US-???"
        title = _text(item.get("title")) or ""
        priority = _text(item.get("priority")) or "P2"
        description = _text(item.get("description")) or ""
        priority_reason = _text(item.get("priority_reason")) or ""
        independent_test = _text(item.get("independent_test")) or ""
        scenarios = item.get("acceptance_scenarios")

        header = f"### {story_id} - {title} (优先级: {priority})" if title else f"### {story_id} (优先级: {priority})"
        lines.append(header)
        lines.append("")
        if description:
            lines.append(description)
        if priority_reason:
            lines.append(f"**优先级原因**：{priority_reason}")
        if independent_test:
            lines.append(f"**独立测试**：{independent_test}")
        lines.append("")

        if isinstance(scenarios, list) and scenarios:
            lines.append("**验收场景**：")
            for sc in scenarios:
                if isinstance(sc, dict):
                    given = _text(sc.get("given")) or ""
                    when = _text(sc.get("when")) or ""
                    then = _text(sc.get("then")) or ""
                    lines.append(f"1. **给定** {given}，**当** {when}，**那么** {then}")
            lines.append("")


def _append_open_questions(lines: list[str], value: Any) -> None:
    lines.extend(["## 待澄清问题", ""])
    questions = value if isinstance(value, list) else []
    if not questions:
        lines.extend(["- 暂无待澄清问题。", ""])
        return
    for item in questions:
        if isinstance(item, dict):
            field = _text(item.get("field")) or "general"
            question = _text(item.get("question")) or ""
            suggested = _text(item.get("suggested_answer"))
            reasoning = _text(item.get("reasoning"))
            parts = [f"**[{field}]** {question}"]
            if suggested:
                parts.append(f"  建议答案：{suggested}")
            if reasoning:
                parts.append(f"  推理依据：{reasoning}")
            lines.append(f"- {' | '.join(parts)}")
        else:
            lines.append(f"- {_text(item) or '暂无'}")
    lines.append("")


def _append_list_section(
    lines: list[str],
    heading: str,
    values: list[str],
    *,
    empty: str = "暂无明确内容。",
) -> None:
    lines.extend([f"## {heading}", ""])
    items = values or [empty]
    lines.extend(f"- {item}" for item in items)
    lines.append("")


def _append_acceptance_criteria(lines: list[str], value: Any) -> None:
    lines.extend(["## 验收标准", ""])
    criteria = value if isinstance(value, list) else []
    if not criteria:
        lines.extend(["- 暂无明确内容。", ""])
        return
    for index, item in enumerate(criteria, start=1):
        if isinstance(item, dict):
            criterion = _text(item.get("criterion")) or "暂无明确内容。"
            criterion_id = _text(item.get("id")) or f"AC-{index:03d}"
            lines.append(f"- **{criterion_id}**：{criterion}")
        else:
            lines.append(f"- **AC-{index:03d}**：{_text(item) or '暂无明确内容。'}")
    lines.append("")


def _append_quality(lines: list[str], quality: dict[str, Any]) -> None:
    lines.extend(["## 质量信号", ""])
    completeness = quality.get("completeness_score")
    ambiguity = quality.get("ambiguity_score")
    ready = "是" if quality.get("ready_for_next_stage") else "否"
    lines.append(f"- 可进入下一阶段：{ready}")
    if isinstance(completeness, int | float):
        lines.append(f"- 完整度评分：{completeness}")
    if isinstance(ambiguity, int | float):
        lines.append(f"- 歧义评分：{ambiguity}")
    dimensions = quality.get("dimensions")
    if isinstance(dimensions, dict):
        cq = _text(dimensions.get("content_quality")) or ""
        rc = _text(dimensions.get("requirement_completeness")) or ""
        fr = _text(dimensions.get("functional_readiness")) or ""
        if cq or rc or fr:
            lines.append(f"- 内容质量：{cq or '未评估'} | 需求完整性：{rc or '未评估'} | 功能就绪度：{fr or '未评估'}")
    warnings = _list(quality.get("warnings"))
    if warnings:
        lines.extend(f"- 预警：{warning}" for warning in warnings)
    lines.append("")


def _preview_list(heading: str, values: list[str], *, empty: str = "暂无") -> str:
    items = values[:3] or [empty]
    return f"**{heading}**\n" + "\n".join(f"• {item}" for item in items)


def _preview_open_questions(value: Any) -> str:
    questions = value if isinstance(value, list) else []
    if not questions:
        return "**待澄清问题**\n• 暂无"
    lines = ["**待澄清问题**"]
    for item in questions[:3]:
        if isinstance(item, dict):
            question = _text(item.get("question")) or ""
            suggested = _text(item.get("suggested_answer"))
            if suggested:
                lines.append(f"• {question} → 建议：{suggested}")
            else:
                lines.append(f"• {question}")
        else:
            lines.append(f"• {_text(item) or '暂无'}")
    return "\n".join(lines)


def _preview_acceptance(value: Any) -> str:
    criteria = value if isinstance(value, list) else []
    if not criteria:
        return "**验收标准**\n• 暂无"
    lines = ["**验收标准**"]
    for index, item in enumerate(criteria[:3], start=1):
        if isinstance(item, dict):
            criterion_id = _text(item.get("id")) or f"AC-{index:03d}"
            criterion = _text(item.get("criterion")) or "暂无"
            lines.append(f"• {criterion_id}：{criterion}")
        else:
            lines.append(f"• AC-{index:03d}：{_text(item) or '暂无'}")
    return "\n".join(lines)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if value is None:
        return None
    return str(value)
