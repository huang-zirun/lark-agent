from __future__ import annotations

from typing import Any


def render_code_review_markdown(artifact: dict[str, Any], *, run_id: str) -> str:
    gate = artifact.get("quality_gate") if isinstance(artifact.get("quality_gate"), dict) else {}
    findings = artifact.get("findings") if isinstance(artifact.get("findings"), list) else []
    lines = [
        f"# 代码评审：{run_id}",
        "",
        f"- 评审状态：{artifact.get('review_status', 'unknown')}",
        f"- 质量门禁：{'通过' if gate.get('passed') else '未通过'}",
        f"- 阻塞问题数：{gate.get('blocking_findings', 0)}",
        f"- 风险等级：{gate.get('risk_level', 'medium')}",
        "",
        "## 摘要",
        "",
        str(artifact.get("summary") or "暂无摘要"),
        "",
        "## 问题列表",
        "",
    ]
    if findings:
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            location = str(finding.get("path") or "")
            if finding.get("line"):
                location = f"{location}:{finding['line']}" if location else f"line {finding['line']}"
            blocking = "阻塞" if finding.get("blocking") else "建议"
            lines.extend(
                [
                    f"### {finding.get('id', 'CR')} · {finding.get('severity', 'P2')} · {blocking}",
                    "",
                    f"- 标题：{finding.get('title', '')}",
                    f"- 分类：{finding.get('category', '')}",
                    f"- 位置：{location or '未指定'}",
                    f"- 证据：{finding.get('evidence', '')}",
                    f"- 建议：{finding.get('fix_suggestion', '')}",
                    "",
                    str(finding.get("description") or ""),
                    "",
                ]
            )
    else:
        lines.extend(["暂无问题。", ""])

    recommendations = artifact.get("repair_recommendations") if isinstance(artifact.get("repair_recommendations"), list) else []
    lines.extend(["## 修复建议", ""])
    if recommendations:
        lines.extend(f"- {item}" for item in recommendations)
    else:
        lines.append("暂无额外修复建议。")
    lines.extend(
        [
            "",
            "## 人工决策",
            "",
            f"- 同意：`Approve {run_id}`",
            f"- 拒绝：`Reject {run_id}: <原因>`",
            "",
        ]
    )
    return "\n".join(lines)
