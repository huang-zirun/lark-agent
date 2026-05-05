from __future__ import annotations

from typing import Any


def render_delivery_markdown(artifact: dict[str, Any]) -> str:
    metadata = _dict(artifact.get("metadata"))
    summary = _dict(artifact.get("change_summary"))
    verification = _dict(artifact.get("verification"))
    readiness = _dict(artifact.get("readiness"))
    git = _dict(artifact.get("git"))
    lines = [
        "# DevFlow 交付包",
        "",
        f"- 运行 ID：`{metadata.get('run_id', '')}`",
        f"- 需求标题：{summary.get('title', '未命名需求')}",
        f"- 合并建议：{'可以合并' if readiness.get('ready_to_merge') else '暂不建议合并'}",
        f"- 风险等级：{readiness.get('risk_level', 'medium')}",
        "",
        "## 变更摘要",
        "",
        str(summary.get("purpose") or "未提供变更目的。"),
        "",
        "## 主要变更",
        "",
    ]
    lines.extend(_bullet_list(summary.get("major_changes"), empty="暂无变更摘要。"))
    lines.extend(["", "## 文件清单", ""])
    lines.extend(_bullet_list(summary.get("changed_files"), empty="暂无文件清单。", code=True))
    lines.extend(["", "## 验证结果", ""])
    lines.append(f"- 测试命令数：{verification.get('test_command_count', 0)}")
    lines.append(f"- 失败命令数：{verification.get('failed_test_commands', 0)}")
    lines.append(f"- 代码评审状态：{verification.get('code_review_status', '')}")
    lines.append(f"- 阻塞问题数：{verification.get('blocking_findings', 0)}")
    commands = verification.get("test_commands") if isinstance(verification.get("test_commands"), list) else []
    if commands:
        lines.extend(["", "### 测试命令", ""])
        for item in commands:
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('command', '')}`：{item.get('status', '')} ({item.get('returncode', '')})")
    lines.extend(["", "## Git 状态", ""])
    if git.get("is_repo"):
        lines.append(f"- 分支：`{git.get('branch', '')}`")
        lines.append(f"- HEAD：`{git.get('head', '')}`")
        stat = _dict(git.get("diff_stat"))
        lines.append(
            f"- Diff 统计：{stat.get('files_changed', 0)} files, +{stat.get('insertions', 0)}, -{stat.get('deletions', 0)}"
        )
    else:
        lines.append("- 当前工作区不是 Git 仓库。")
    lines.extend(["", "## 待人工处理", ""])
    lines.extend(_bullet_list(readiness.get("warnings"), empty="暂无阻塞项。"))
    lines.append("")
    return "\n".join(lines)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bullet_list(value: Any, *, empty: str, code: bool = False) -> list[str]:
    items = value if isinstance(value, list) else []
    texts = [str(item).strip() for item in items if str(item).strip()]
    if not texts:
        return [f"- {empty}"]
    if code:
        return [f"- `{item}`" for item in texts]
    return [f"- {item}" for item in texts]
