from __future__ import annotations

from typing import Any


def render_solution_markdown(artifact: dict[str, Any], *, run_id: str | None = None) -> str:
    proposed = _dict(artifact.get("proposed_solution"))
    quality = _dict(artifact.get("quality"))
    summary = _text(proposed.get("summary")) or "未命名技术方案"
    lines = [f"# 技术方案：{summary}", ""]
    if run_id:
        lines.extend(["## 运行信息", "", f"- 运行 ID：{run_id}", ""])

    _append_list(lines, "数据流", _list(proposed.get("data_flow")))
    _append_list(lines, "实施步骤", _list(proposed.get("implementation_steps")))
    _append_change_plan(lines, artifact.get("change_plan"))
    _append_api_design(lines, _dict(artifact.get("api_design")))
    _append_testing(lines, _dict(artifact.get("testing_strategy")))
    risks = _dict(artifact.get("risks_and_assumptions"))
    _append_list(lines, "风险", _list(risks.get("risks")))
    _append_list(lines, "假设", _list(risks.get("assumptions")))
    _append_list(lines, "开放问题", _list(risks.get("open_questions")), empty="暂无开放问题。")
    review = _dict(artifact.get("human_review"))
    _append_list(lines, "人工评审清单", _list(review.get("checklist")), empty="暂无评审项。")
    lines.extend(["## 质量信号", ""])
    lines.append(f"- 风险等级：{_text(quality.get('risk_level')) or 'medium'}")
    lines.append(f"- 可进入代码生成：{'是' if quality.get('ready_for_code_generation') else '否'}")
    score = quality.get("completeness_score")
    if isinstance(score, int | float):
        lines.append(f"- 完整度：{score}")
    for warning in _list(quality.get("warnings")):
        lines.append(f"- 预警：{warning}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _append_change_plan(lines: list[str], value: Any) -> None:
    lines.extend(["## 文件变更清单", ""])
    items = value if isinstance(value, list) else []
    if not items:
        lines.extend(["- 暂无文件变更清单。", ""])
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        path = _text(item.get("path")) or "未命名路径"
        action = _text(item.get("action")) or "modify"
        responsibility = _text(item.get("responsibility")) or "待细化"
        lines.append(f"- `{path}`（{action}）：{responsibility}")
    lines.append("")


def _append_api_design(lines: list[str], api: dict[str, Any]) -> None:
    lines.extend(["## API 设计", ""])
    for heading, key in (("CLI", "cli"), ("Python", "python"), ("JSON Contract", "json_contracts"), ("外部接口", "external")):
        values = _list(api.get(key))
        if values:
            lines.append(f"### {heading}")
            lines.extend(f"- {item}" for item in values)
            lines.append("")
    if lines[-1] == "## API 设计":
        lines.extend(["- 暂无 API 变更。", ""])


def _append_testing(lines: list[str], testing: dict[str, Any]) -> None:
    lines.extend(["## 测试策略", ""])
    mapping = (
        ("单元测试", "unit_tests"),
        ("集成测试", "integration_tests"),
        ("验收映射", "acceptance_mapping"),
        ("回归测试", "regression_tests"),
    )
    wrote = False
    for heading, key in mapping:
        values = _list(testing.get(key))
        if not values:
            continue
        wrote = True
        lines.append(f"### {heading}")
        lines.extend(f"- {item}" for item in values)
        lines.append("")
    if not wrote:
        lines.extend(["- 暂无测试策略。", ""])


def _append_list(lines: list[str], heading: str, values: list[str], *, empty: str = "暂无明确内容。") -> None:
    lines.extend([f"## {heading}", ""])
    lines.extend(f"- {item}" for item in (values or [empty]))
    lines.append("")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [text for item in value if (text := _text(item))]
    text = _text(value)
    return [text] if text else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()
