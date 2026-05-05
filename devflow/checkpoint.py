from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "devflow.checkpoint.v1"
CHECKPOINT_FILE = "checkpoint.json"
APPROVE_ALIASES = {"approve", "approved", "同意", "通过", "继续", "确认"}
REJECT_ALIASES = {"reject", "rejected", "拒绝", "驳回", "退回", "不同意"}
FORCE_OVERRIDE_ALIASES = {"--force", "强制通过", "强制同意", "override"}


HELP_ALIASES = {"help", "帮助"}
STATUS_ALIASES = {"status", "状态"}


SKIP_ALIASES = {"继续", "skip", "跳过"}


class PrefixMatchError(Exception):
    def __init__(self, partial: str, matches: list[str]) -> None:
        self.partial = partial
        self.matches = matches
        super().__init__(f"前缀 '{partial}' 匹配到多个运行：{', '.join(matches)}")


def resolve_run_id_prefix(partial: str, out_dir: Path) -> str:
    if not partial:
        raise PrefixMatchError(partial, [])
    runs_dir = out_dir
    if not runs_dir.exists():
        raise PrefixMatchError(partial, [])
    matches = sorted(
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and d.name.startswith(partial)
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise PrefixMatchError(partial, matches)
    raise PrefixMatchError(partial, [])


@dataclass(frozen=True, slots=True)
class SystemCommand:
    command: str


@dataclass(frozen=True, slots=True)
class CheckpointCommand:
    decision: str
    run_id: str
    reason: str | None = None
    force_override: bool = False


@dataclass(frozen=True, slots=True)
class ClarificationReply:
    action: str
    text: str | None = None


def parse_clarification_reply(text: str) -> ClarificationReply:
    stripped = text.strip()
    if stripped.lower() in SKIP_ALIASES:
        return ClarificationReply(action="skip")
    return ClarificationReply(action="answer", text=stripped)


def parse_system_command(text: str) -> SystemCommand | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped[1:].split(None, 1)
    if not parts:
        return None
    verb = parts[0].lower()
    if verb in HELP_ALIASES:
        return SystemCommand("help")
    if verb in STATUS_ALIASES:
        return SystemCommand("status")
    return None


def parse_checkpoint_command(text: str, *, out_dir: Path | None = None) -> CheckpointCommand | PrefixMatchError | None:
    stripped = text.strip()
    if not stripped:
        return None
    colon_match = re.match(r"^(\S+)\s+([A-Za-z0-9_.-]+)\s*[:：]\s*(.+)$", stripped, re.S)
    if colon_match is not None:
        verb = colon_match.group(1).strip().lower()
        run_id = colon_match.group(2).strip()
        tail = colon_match.group(3).strip()
        force = any(alias in tail for alias in FORCE_OVERRIDE_ALIASES)
        if force:
            for alias in FORCE_OVERRIDE_ALIASES:
                tail = tail.replace(alias, "")
            tail = tail.strip()
        reason = tail or None
        if verb in APPROVE_ALIASES:
            resolved = _resolve_if_needed(run_id, out_dir)
            if isinstance(resolved, PrefixMatchError):
                return resolved
            return CheckpointCommand("approve", resolved, None, force_override=force)
        if verb in REJECT_ALIASES:
            resolved = _resolve_if_needed(run_id, out_dir)
            if isinstance(resolved, PrefixMatchError):
                return resolved
            return CheckpointCommand("reject", resolved, reason)
    match = re.match(r"^(\S+)\s+([A-Za-z0-9_.:-]+)(?:\s*[:：]\s*(.+)|\s+(.+))?$", stripped, re.S)
    if match is None:
        return None
    verb = match.group(1).strip().lower()
    run_id = match.group(2).strip()
    tail = (match.group(3) or match.group(4) or "").strip()
    force = any(alias in tail for alias in FORCE_OVERRIDE_ALIASES)
    if force:
        for alias in FORCE_OVERRIDE_ALIASES:
            tail = tail.replace(alias, "")
        tail = tail.strip()
    reason = tail or None
    if verb in APPROVE_ALIASES:
        resolved = _resolve_if_needed(run_id, out_dir)
        if isinstance(resolved, PrefixMatchError):
            return resolved
        return CheckpointCommand("approve", resolved, None, force_override=force)
    if verb in REJECT_ALIASES:
        resolved = _resolve_if_needed(run_id, out_dir)
        if isinstance(resolved, PrefixMatchError):
            return resolved
        return CheckpointCommand("reject", resolved, reason)
    return None


def _resolve_if_needed(run_id: str, out_dir: Path | None) -> str | PrefixMatchError:
    if out_dir is None:
        return run_id
    full_dir = out_dir / run_id
    if full_dir.exists():
        return run_id
    try:
        return resolve_run_id_prefix(run_id, out_dir)
    except PrefixMatchError as exc:
        return exc


def build_solution_review_checkpoint(
    run_payload: dict[str, Any],
    solution_path: Path | str | None,
    solution_markdown_path: Path | str | None,
    *,
    attempt: int = 1,
    status: str = "waiting_approval",
    previous_artifacts: list[dict[str, Any]] | None = None,
    reject_reason: str | None = None,
    blocked_reason: str | None = None,
    approval_instance_code: str | None = None,
    solution_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_history = list(previous_artifacts or [])
    if solution_path is not None or solution_markdown_path is not None:
        artifact_history.append(
            {
                "attempt": attempt,
                "solution_path": str(solution_path) if solution_path is not None else None,
                "solution_markdown_path": str(solution_markdown_path) if solution_markdown_path is not None else None,
                "created_at": utc_now(),
            }
        )
    quality_snapshot = None
    if solution_artifact is not None:
        quality = _dict(solution_artifact.get("quality"))
        if quality:
            quality_snapshot = {
                "ready_for_code_generation": bool(quality.get("ready_for_code_generation")),
                "completeness_score": quality.get("completeness_score"),
                "risk_level": _text(quality.get("risk_level")) or None,
                "warnings": quality.get("warnings") if isinstance(quality.get("warnings"), list) else [],
            }
    effective_status = status
    if quality_snapshot is not None and not quality_snapshot["ready_for_code_generation"] and status == "waiting_approval":
        effective_status = "waiting_approval_with_warnings"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_payload["run_id"],
        "stage": "solution_design",
        "status": effective_status,
        "attempt": attempt,
        "reviewer": None,
        "decision": None,
        "reject_reason": reject_reason,
        "blocked_reason": blocked_reason,
        "continue_requested": False,
        "artifact_history": artifact_history,
        "approval_instance_code": approval_instance_code,
        "quality_snapshot": quality_snapshot,
        "updated_at": utc_now(),
    }


def build_code_review_checkpoint(
    run_payload: dict[str, Any],
    review_path: Path | str,
    review_markdown_path: Path | str,
    *,
    attempt: int = 1,
    status: str = "waiting_approval",
    reject_reason: str | None = None,
    approval_instance_code: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_payload["run_id"],
        "stage": "code_review",
        "status": status,
        "attempt": attempt,
        "reviewer": None,
        "decision": None,
        "reject_reason": reject_reason,
        "blocked_reason": None,
        "continue_requested": False,
        "artifact_history": [
            {
                "attempt": attempt,
                "code_review_path": str(review_path),
                "code_review_markdown_path": str(review_markdown_path),
                "created_at": utc_now(),
            }
        ],
        "approval_instance_code": approval_instance_code,
        "updated_at": utc_now(),
    }


def write_checkpoint(run_dir: Path | str, checkpoint: dict[str, Any]) -> Path:
    path = Path(run_dir) / CHECKPOINT_FILE
    path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_checkpoint(run_dir: Path | str) -> dict[str, Any]:
    path = Path(run_dir) / CHECKPOINT_FILE
    return json.loads(path.read_text(encoding="utf-8-sig"))


def apply_checkpoint_decision(
    run_dir: Path | str,
    decision: str,
    *,
    reason: str | None = None,
    reviewer: dict[str, Any] | None = None,
    force_override: bool = False,
) -> dict[str, Any]:
    checkpoint = load_checkpoint(run_dir)
    normalized = decision.strip().lower()
    if normalized not in {"approve", "reject"}:
        raise ValueError(f"未知检查点决策：{decision}")

    checkpoint["reviewer"] = reviewer or checkpoint.get("reviewer")
    checkpoint["decision"] = normalized
    checkpoint["updated_at"] = utc_now()
    if normalized == "approve":
        quality_snapshot = checkpoint.get("quality_snapshot")
        not_ready = (
            quality_snapshot is not None
            and isinstance(quality_snapshot, dict)
            and quality_snapshot.get("ready_for_code_generation") is False
        )
        if not_ready and not force_override:
            checkpoint["status"] = "waiting_approval_with_warnings"
            checkpoint["approval_blocked_reason"] = "方案未就绪，无法批准。如需强制通过请使用 --force"
            write_checkpoint(run_dir, checkpoint)
            return checkpoint
        if not_ready and force_override:
            checkpoint["status"] = "approved_with_override"
            checkpoint["continue_requested"] = True
            checkpoint["override_reason"] = "human_override_quality_gate_failed"
            checkpoint["quality_at_approval"] = checkpoint.get("quality_snapshot")
            checkpoint["reject_reason"] = None
        else:
            checkpoint["status"] = "approved"
            checkpoint["continue_requested"] = True
            checkpoint["reject_reason"] = None
    elif reason:
        checkpoint["status"] = "rejected"
        checkpoint["continue_requested"] = False
        checkpoint["reject_reason"] = reason.strip()
    else:
        checkpoint["status"] = "awaiting_reject_reason"
        checkpoint["continue_requested"] = False
    write_checkpoint(run_dir, checkpoint)
    return checkpoint


def build_solution_review_card(
    run_payload: dict[str, Any],
    solution_artifact: dict[str, Any],
    *,
    solution_path: Path | str,
    solution_markdown_path: Path | str,
    solution_doc_url: str | None = None,
) -> dict[str, Any]:
    run_id = run_payload["run_id"]
    proposed = _dict(solution_artifact.get("proposed_solution"))
    quality = _dict(solution_artifact.get("quality"))
    change_plan = solution_artifact.get("change_plan") if isinstance(solution_artifact.get("change_plan"), list) else []
    summary = _text(proposed.get("summary")) or "技术方案已生成"
    risk = _text(quality.get("risk_level")) or "medium"
    solution_path_text = _path_text(solution_path)
    solution_markdown_path_text = _path_text(solution_markdown_path)
    files = [f"• `{_text(item.get('path'))}`：{_text(item.get('responsibility'))}" for item in change_plan[:10] if isinstance(item, dict)]
    if not files:
        files = ["• 暂无文件变更清单"]
    has_warnings = quality.get("ready_for_code_generation") is False
    warnings = quality.get("warnings", []) if has_warnings else []
    warning_lines = []
    if has_warnings:
        warning_lines.append("")
        warning_lines.append("⚠️ **质量警告**")
        for w in warnings:
            warning_lines.append(f"• {_text(w)}")
        warning_lines.append(f"方案存在未决问题，建议确认后再批准。如需强制通过，请回复：`Approve {run_id} --force`")
    doc_link_line = (
        f"[查看完整方案]({solution_doc_url})"
        if solution_doc_url
        else f"完整方案文档发布失败，请查看本地产物：`{solution_markdown_path_text}`"
    )
    body = "\n".join(
        [
            f"**运行 ID**：`{run_id}`",
            f"**风险等级**：{risk}",
            f"**方案 JSON**：`{solution_path_text}`",
            "",
            "**文件变更预览**",
            *files,
            *warning_lines,
            "",
            f"同意：`Approve {run_id}`",
            f"拒绝：`Reject {run_id}`",
        ]
    )
    header_template = "orange" if has_warnings else "blue"
    header_title = "DevFlow 技术方案评审（有质量警告）" if has_warnings else "DevFlow 技术方案评审"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": header_template,
            "title": {"tag": "plain_text", "content": header_title},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": doc_link_line}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**方案摘要**：{summary}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
        ],
    }


def build_code_review_card(
    run_payload: dict[str, Any],
    review_artifact: dict[str, Any],
    *,
    review_path: Path | str,
    review_markdown_path: Path | str,
    review_doc_url: str | None = None,
    has_approval_instance: bool = False,
) -> dict[str, Any]:
    run_id = run_payload["run_id"]
    gate = _dict(review_artifact.get("quality_gate"))
    findings = review_artifact.get("findings") if isinstance(review_artifact.get("findings"), list) else []
    status = _text(review_artifact.get("review_status")) or "unknown"
    risk = _text(gate.get("risk_level")) or "medium"
    blocking_count = gate.get("blocking_findings", 0)
    review_path_text = _path_text(review_path)
    review_markdown_path_text = _path_text(review_markdown_path)
    issue_lines = []
    for item in findings[:10]:
        if not isinstance(item, dict):
            continue
        severity = _text(item.get("severity")) or "P2"
        path = _text(item.get("path")) or "未指定文件"
        title = _text(item.get("title")) or "未命名问题"
        issue_lines.append(
            f"• {severity} `{path}`：{title}"
        )
    if not issue_lines:
        issue_lines = ["• 暂无阻塞问题"]
    doc_link_line = (
        f"[查看完整评审报告]({review_doc_url})"
        if review_doc_url
        else f"完整评审报告发布失败，请查看本地产物：`{review_markdown_path_text}`"
    )
    approval_hint = "\n也可在飞书「审批」应用中处理。" if has_approval_instance else ""
    body = "\n".join(
        [
            f"**运行 ID**：`{run_id}`",
            f"**评审状态**：{status}",
            f"**风险等级**：{risk}",
            f"**阻塞问题数**：{blocking_count}",
            f"**评审 JSON**：`{review_path_text}`",
            "",
            "**问题预览**",
            *issue_lines,
            "",
            f"同意：`Approve {run_id}`",
            f"拒绝：`Reject {run_id}`",
            approval_hint,
        ]
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green" if gate.get("passed") else "red",
            "title": {"tag": "plain_text", "content": "DevFlow 代码评审"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": doc_link_line}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**评审摘要**：{_text(review_artifact.get('summary')) or '代码评审已生成'}"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
        ],
    }


def build_clarification_checkpoint(
    run_payload: dict[str, Any],
    open_questions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_payload["run_id"],
        "stage": "clarification",
        "status": "waiting_clarification",
        "attempt": 1,
        "reviewer": None,
        "decision": None,
        "reject_reason": None,
        "blocked_reason": None,
        "continue_requested": False,
        "artifact_history": [],
        "open_questions": open_questions,
        "updated_at": utc_now(),
    }


def build_clarification_card(
    run_payload: dict[str, Any],
    open_questions: list[dict[str, Any]],
) -> dict[str, Any]:
    run_id = run_payload["run_id"]
    question_lines = []
    for i, q in enumerate(open_questions, start=1):
        question_text = _text(q.get("question"))
        question_lines.append(f"• Q{i}：{question_text}")
    if not question_lines:
        question_lines = ["• 暂无待澄清问题"]
    body = "\n".join(
        [
            f"**运行 ID**：`{run_id}`",
            "",
            "**待澄清问题**",
            *question_lines,
            "",
            "请回复问题的答案，或回复 `继续` 跳过澄清直接进入方案设计",
        ]
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": "🔍 需求待澄清"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
        ],
    }


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _path_text(value: Path | str) -> str:
    if isinstance(value, Path):
        return value.as_posix()
    return str(value).replace("\\", "/")
