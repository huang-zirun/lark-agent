from __future__ import annotations

import json
import os
import re
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4

from devflow.approval_client import (
    ApprovalError,
    build_solution_review_form,
    create_approval_instance,
    get_approval_instance,
    parse_approval_result,
)
from devflow.code.agent import (
    QualityGateError,
    build_code_generation_artifact,
    load_solution_artifact,
    write_code_diff,
    write_code_generation_artifact,
)
from devflow.checkpoint import (
    apply_checkpoint_decision,
    build_clarification_card,
    build_clarification_checkpoint,
    build_code_review_card,
    build_code_review_checkpoint,
    build_solution_review_card,
    build_solution_review_checkpoint,
    ClarificationReply,
    load_checkpoint,
    parse_checkpoint_command,
    parse_clarification_reply,
    parse_system_command,
    write_checkpoint,
    PrefixMatchError,
    SystemCommand,
)
from devflow.config import DEFAULT_CONFIG_PATH, ConfigError, load_config
from devflow.delivery.agent import build_delivery_artifact, write_delivery_artifact, write_delivery_diff
from devflow.delivery.render import render_delivery_markdown
from devflow.intake.analyzer import build_requirement_artifact
from devflow.intake.lark_cli import (
    LarkCliError,
    create_prd_document,
    event_to_source,
    fetch_doc_source,
    fetch_message_source,
    listen_bot_events,
    publish_document,
    send_bot_card_reply,
    send_bot_message,
    send_bot_reply,
    send_bot_text,
)
from devflow.intake.models import RequirementSource
from devflow.intake.output import slugify, write_artifact
from devflow.llm import LlmError
from devflow.prd import build_prd_preview_card, render_prd_markdown
from devflow.pipeline_config import resolve_pipeline_config
from devflow.review.agent import (
    build_code_review_artifact,
    load_requirement_artifact as load_review_requirement_artifact,
    write_code_review_artifact,
)
from devflow.review.render import render_code_review_markdown
from devflow.solution.designer import build_solution_design_artifact, load_requirement_artifact, write_solution_artifact
from devflow.solution.render import render_solution_markdown
from devflow.solution.workspace import WorkspaceError, parse_workspace_directive, resolve_workspace
from devflow.test.agent import (
    build_test_generation_artifact,
    load_code_generation_artifact,
    load_requirement_artifact as load_test_requirement_artifact,
    write_test_diff,
    write_test_generation_artifact,
)
from devflow.trace import RunTrace, StageTrace


def _idempotency_key(run_id: str, suffix: str) -> str:
    """Generate a short idempotency key within Lark API limits (~64 chars)."""
    # run_id format: 20260503T123303Z-om_x100b5040493c3938b21603e79c5587f-c58e7ef9
    # Use last 8 chars (UUID fragment) + suffix to stay under limit
    short_id = run_id.split("-")[-1] if "-" in run_id else run_id[-8:]
    key = f"df-{short_id}-{suffix}"
    # Hard cap at 64 chars to be safe
    return key[:64]


STAGE_DISPLAY_NAMES = {
    "requirement_intake": "需求分析",
    "clarification": "需求澄清",
    "solution_design": "方案设计",
    "code_generation": "代码生成",
    "test_generation": "测试生成",
    "code_review": "代码评审",
    "delivery": "交付",
}


def send_stage_notification(
    message_id: str,
    run_id: str,
    stage_name: str,
    event_type: str,
    stages: list[dict[str, Any]],
    error_summary: str | None = None,
) -> None:
    try:
        config = load_config()
    except ConfigError:
        return
    if not config.interaction.progress_notifications_enabled:
        return
    display_name = STAGE_DISPLAY_NAMES.get(stage_name, stage_name)
    completed = sum(1 for s in stages if isinstance(s, dict) and s.get("status") == "success")
    total = len(stages)
    if event_type == "started":
        text = f"📋 {display_name} 进行中… （{completed}/{total}）"
    elif event_type == "completed":
        text = f"✅ {display_name} 已完成"
    elif event_type == "failed":
        suggestion = _stage_failure_suggestion(stage_name, error_summary or "")
        text = f"❌ {display_name} 失败：{error_summary or '未知错误'}\n💡 {suggestion}"
    else:
        return
    try:
        send_bot_reply(
            message_id,
            text,
            _idempotency_key(run_id, f"stage-{stage_name}-{event_type}"),
        )
    except LarkCliError:
        pass


def send_thinking_notification(
    message_id: str,
    run_id: str,
    stage_name: str,
) -> None:
    try:
        config = load_config()
    except ConfigError:
        return
    if not config.interaction.progress_notifications_enabled:
        return
    display_name = STAGE_DISPLAY_NAMES.get(stage_name, stage_name)
    text = f"🤔 {display_name}：正在思考…"
    try:
        send_bot_reply(
            message_id,
            text,
            _idempotency_key(run_id, f"thinking-{stage_name}"),
        )
    except LarkCliError:
        pass


_THINKING_TIMEOUT_SECONDS = 30
_THINKING_TIMEOUT_TEXT = "⏳ 仍在处理中，请稍候…"
_FIRST_INTERACTION_GUIDE = "收到！我是 DevFlow 机器人，发送需求描述即可启动开发流水线。发送 /help 查看完整指引。"
_seen_senders: set[str] = set()


class ThinkingTimer:
    def __init__(
        self,
        message_id: str,
        run_id: str,
        stage_name: str,
        *,
        timeout_seconds: float = _THINKING_TIMEOUT_SECONDS,
    ) -> None:
        self._message_id = message_id
        self._run_id = run_id
        self._stage_name = stage_name
        self._timeout_seconds = timeout_seconds
        self._fired = False
        self._cancelled = False
        self._timer: threading.Timer | None = None

    def start(self) -> None:
        self._timer = threading.Timer(self._timeout_seconds, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def cancel(self) -> None:
        self._cancelled = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _on_timeout(self) -> None:
        if self._cancelled:
            return
        self._fired = True
        try:
            config = load_config()
        except ConfigError:
            return
        if not config.interaction.progress_notifications_enabled:
            return
        try:
            send_bot_reply(
                self._message_id,
                _THINKING_TIMEOUT_TEXT,
                _idempotency_key(self._run_id, f"timeout-{self._stage_name}"),
            )
        except LarkCliError:
            pass


def _trigger_message_id(run_payload: dict[str, Any]) -> str:
    trigger = run_payload.get("trigger") if isinstance(run_payload.get("trigger"), dict) else {}
    return str(trigger.get("message_id") or "")


PIPELINE_SCHEMA_VERSION = "devflow.pipeline_run.v1"
DEFAULT_STAGE_NAMES = [
    "requirement_intake",
    "solution_design",
    "code_generation",
    "test_generation",
    "code_review",
    "delivery",
]
STAGE_NAMES = list(DEFAULT_STAGE_NAMES)
DOC_URL_PATTERN = re.compile(r"https?://[^\s<>'\"]*(?:feishu|larksuite)\.[^\s<>'\"]+", re.IGNORECASE)
DOC_TOKEN_PATTERN = re.compile(
    r"\b(?:(?:doc|docx|wiki)_[A-Za-z0-9_-]{3,}|(?:doxcn|doccn)[A-Za-z0-9_-]{6,})\b",
    re.IGNORECASE,
)
MESSAGE_ID_PATTERN = re.compile(r"\bom_[A-Za-z0-9_-]+\b")


@dataclass(frozen=True, slots=True)
class DetectedInput:
    kind: str
    value: str


@dataclass(frozen=True, slots=True)
class PipelineResult:
    run_id: str
    status: str
    run_dir: Path
    run_path: Path
    requirement_path: Path | None
    solution_path: Path | None = None
    reply_error: str | None = None


FetchSource = Callable[[str], RequirementSource]
ReplySender = Callable[[str, str, str], Any]
ArtifactBuilder = Callable[[RequirementSource, str, str], dict[str, Any]]
PrdCreator = Callable[[str, str], dict[str, Any]]
CardReplySender = Callable[[str, dict[str, Any], str], Any]


def detect_requirement_input(text: str) -> DetectedInput:
    content = text.strip()
    doc_url = DOC_URL_PATTERN.search(content)
    if doc_url is not None:
        return DetectedInput(kind="lark_doc", value=doc_url.group(0).rstrip(".,;"))

    doc_token = DOC_TOKEN_PATTERN.search(content)
    if doc_token is not None:
        return DetectedInput(kind="lark_doc", value=doc_token.group(0))

    message_id = MESSAGE_ID_PATTERN.search(content)
    if message_id is not None:
        return DetectedInput(kind="lark_message", value=message_id.group(0))

    return DetectedInput(kind="inline_text", value=content)


def process_bot_event(
    event: dict[str, Any],
    *,
    out_dir: Path,
    analyzer: str,
    model: str,
    fetch_doc: FetchSource = fetch_doc_source,
    fetch_message: FetchSource = fetch_message_source,
    build_artifact: ArtifactBuilder | None = None,
    reply_sender: ReplySender | None = None,
    prd_creator: PrdCreator | None = None,
    card_reply_sender: CardReplySender | None = None,
) -> PipelineResult:
    event_source = event_to_source(event)
    checkpoint_result = maybe_process_checkpoint_event(
        event_source,
        out_dir=out_dir,
        reply_sender=reply_sender,
        card_reply_sender=card_reply_sender,
    )
    if checkpoint_result is not None:
        return checkpoint_result

    detected = detect_requirement_input(event_source.content)
    run_id = new_run_id(event_source.source_id)
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / "run.json"
    requirement_path = run_dir / "requirement.json"
    trace = RunTrace(run_id, run_dir)
    stage_trace = trace.stage("requirement_intake")
    started_at = utc_now()
    stages = initial_stages()
    set_stage_status(stages, "requirement_intake", "running", started_at=started_at)
    send_stage_notification(
        event_source.source_id, run_id, "requirement_intake", "started", stages,
    )

    run_payload = base_run_payload(
        run_id=run_id,
        run_dir=run_dir,
        event_source=event_source,
        detected=detected,
        started_at=started_at,
        stages=stages,
    )
    run_payload["audit"] = build_audit_payload(trace, run_dir)
    stage_trace.event("run_started", status="running", payload={"run_path": str(run_path)})
    stage_trace.event(
        "input_detected",
        payload={"kind": detected.kind, "value": detected.value},
    )
    write_json(run_path, run_payload)

    sender = send_bot_reply if reply_sender is None else reply_sender
    if sender is not None:
        confirm_text = f"收到需求，正在分析中… 运行 ID：{run_id}"
        sender_id = event_source.metadata.get("sender_id", "")
        if sender_id:
            is_first = sender_id not in _seen_senders
            _seen_senders.add(sender_id)
            if is_first:
                try:
                    config = load_config()
                    has_default_chat = bool(config.interaction.default_chat_id)
                except ConfigError:
                    has_default_chat = False
                if not has_default_chat:
                    confirm_text = f"收到需求，正在分析中… 运行 ID：{run_id}\n\n{_FIRST_INTERACTION_GUIDE}"
        try:
            sender(
                event_source.source_id,
                confirm_text,
                _idempotency_key(run_id, "confirm"),
            )
        except LarkCliError:
            pass

    reply_error = None
    try:
        stage_trace.event("source_resolution_started", status="running")
        try:
            requirement_source = resolve_detected_source(
                detected,
                event_source,
                fetch_doc=fetch_doc,
                fetch_message=fetch_message,
            )
        except (LarkCliError, ValueError) as exc:
            stage_trace.event(
                "source_resolution_failed",
                status="failed",
                payload={"error": str(exc), "input_kind": detected.kind},
            )
            raise
        stage_trace.event(
            "source_resolved",
            status="success",
            payload={
                "source_type": requirement_source.source_type,
                "source_id": requirement_source.source_id,
                "reference": requirement_source.reference,
            },
        )
        artifact_builder = build_artifact or build_requirement_artifact_for_pipeline
        stage_trace.event(
            "analysis_started",
            status="running",
            payload={"analyzer": analyzer, "model": model},
        )
        send_thinking_notification(
            event_source.source_id, run_id, "requirement_intake",
        )
        thinking_timer = ThinkingTimer(event_source.source_id, run_id, "requirement_intake")
        thinking_timer.start()
        try:
            if build_artifact is None:
                artifact = build_requirement_artifact_for_pipeline(
                    requirement_source,
                    analyzer,
                    model,
                    stage_trace=stage_trace,
                )
            else:
                artifact = artifact_builder(requirement_source, analyzer, model)
        except (ConfigError, LlmError, ValueError) as exc:
            stage_trace.event(
                "analysis_failed",
                status="failed",
                payload={"error": str(exc), "analyzer": analyzer},
            )
            raise
        finally:
            thinking_timer.cancel()
        stage_trace.event("analysis_completed", status="success", payload={"analyzer": analyzer})
        write_artifact(artifact, requirement_path)
        stage_trace.event(
            "artifact_written",
            status="success",
            payload={"path": str(requirement_path), "schema_version": artifact.get("schema_version")},
        )

        ended_at = utc_now()
        set_stage_status(
            stages,
            "requirement_intake",
            "success",
            ended_at=ended_at,
            artifact=str(requirement_path),
        )
        send_stage_notification(
            event_source.source_id, run_id, "requirement_intake", "completed", stages,
        )
        run_payload.update(
            {
                "status": "success",
                "ended_at": ended_at,
                "requirement_artifact": str(requirement_path),
                "requirement_title": artifact["normalized_requirement"]["title"],
                "ready_for_next_stage": artifact["quality"]["ready_for_next_stage"],
                "stages": stages,
                "audit": build_audit_payload(trace, run_dir),
            }
        )
        quality = artifact.get("quality") if isinstance(artifact.get("quality"), dict) else {}
        open_questions = artifact.get("open_questions") if isinstance(artifact.get("open_questions"), list) else []
        if not quality.get("ready_for_next_stage") and open_questions:
            run_payload["status"] = "waiting_clarification"
            checkpoint = build_clarification_checkpoint(run_payload, open_questions)
            write_checkpoint(run_dir, checkpoint)
            run_payload["checkpoint_artifact"] = str(run_dir / "checkpoint.json")
            run_payload["checkpoint_status"] = checkpoint["status"]
            card_sender = send_bot_card_reply if card_reply_sender is None else card_reply_sender
            try:
                card = build_clarification_card(run_payload, open_questions)
                card_sender(
                    event_source.source_id,
                    card,
                    _idempotency_key(run_id, "clarification"),
                )
            except LarkCliError:
                pass
            write_json(run_path, run_payload)
            return PipelineResult(
                run_id=run_id,
                status="waiting_clarification",
                run_dir=run_dir,
                run_path=run_path,
                requirement_path=requirement_path,
            )
        solution_path = maybe_run_solution_design(
            artifact,
            requirement_path,
            requirement_source,
            analyzer=analyzer,
            run_dir=run_dir,
            stages=stages,
            trace=trace,
            run_payload=run_payload,
            message_id=event_source.source_id,
            card_reply_sender=card_reply_sender,
        )
        if solution_path is not None:
            run_payload["solution_artifact"] = str(solution_path)
            run_payload["audit"] = build_audit_payload(trace, run_dir)
        if run_payload.get("status") == "blocked":
            stage_trace.event("run_blocked", status="blocked")
            reply_text = build_workspace_blocked_reply(run_payload)
        else:
            publish_requirement_prd(
                run_payload,
                artifact,
                event_source.source_id,
                prd_creator=prd_creator,
                card_reply_sender=card_reply_sender,
                stage_trace=stage_trace,
            )
            stage_trace.event("run_completed", status="success")
            reply_text = build_success_reply(run_payload)
    except (ConfigError, LarkCliError, LlmError, WorkspaceError, ValueError) as exc:
        ended_at = utc_now()
        failed_stage = (
            "solution_design"
            if stage_status(stages, "solution_design") in {"running", "failed"}
            else "requirement_intake"
        )
        if stage_status(stages, failed_stage) != "failed":
            set_stage_status(
                stages,
                failed_stage,
                "failed",
                ended_at=ended_at,
                error=str(exc),
            )
        send_stage_notification(
            event_source.source_id, run_id, failed_stage, "failed", stages, error_summary=str(exc),
        )
        run_payload.update(
            {
                "status": "failed",
                "ended_at": ended_at,
                "error": {
                    "stage": failed_stage,
                    "message": str(exc),
                    "hint": failure_hint(detected),
                },
                "stages": stages,
                "audit": build_audit_payload(trace, run_dir),
            }
        )
        trace.stage(failed_stage).event(
            "run_failed",
            status="failed",
            payload={"stage": failed_stage, "error": str(exc)},
        )
        reply_text = build_failure_reply(run_payload)

    write_json(run_path, run_payload)

    sender = send_bot_reply if reply_sender is None else reply_sender
    should_send_text_reply = run_payload["status"] != "success" or run_payload.get("reply_error") is not None
    if sender is not None and should_send_text_reply:
        try:
            stage_trace.event("reply_attempted", status="running")
            sender(
                event_source.source_id,
                reply_text,
                _idempotency_key(run_id, f"{run_payload['status']}-fallback"),
            )
            stage_trace.event("reply_completed", status="success")
        except LarkCliError as exc:
            reply_error = str(exc)
            run_payload["reply_error"] = reply_error
            stage_trace.event("reply_failed", status="failed", payload={"error": reply_error})
            write_json(run_path, run_payload)

    return PipelineResult(
        run_id=run_id,
        status=run_payload["status"],
        run_dir=run_dir,
        run_path=run_path,
        requirement_path=requirement_path if run_payload["status"] == "success" else None,
        solution_path=Path(run_payload["solution_artifact"]) if run_payload.get("solution_artifact") else None,
        reply_error=reply_error or run_payload.get("reply_error"),
    )


def maybe_run_solution_design(
    requirement_artifact: dict[str, Any],
    requirement_path: Path,
    requirement_source: RequirementSource,
    *,
    analyzer: str,
    run_dir: Path,
    stages: list[dict[str, Any]],
    trace: RunTrace,
    run_payload: dict[str, Any],
    message_id: str,
    card_reply_sender: CardReplySender | None,
) -> Path | None:
    if analyzer != "llm":
        return None

    config = load_config(require_llm_api_key=True, require_llm_model=True)
    solution_trace = trace.stage("solution_design")
    try:
        workspace = resolve_workspace(
            message_text=requirement_source.content,
            config=config.workspace,
        )
    except WorkspaceError as exc:
        ended_at = utc_now()
        set_stage_status(
            stages,
            "solution_design",
            "blocked",
            ended_at=ended_at,
            error=str(exc),
        )
        checkpoint = build_solution_review_checkpoint(
            run_payload,
            None,
            None,
            status="blocked",
            blocked_reason=str(exc),
        )
        checkpoint_path = write_checkpoint(run_dir, checkpoint)
        run_payload.update(
            {
                "status": "blocked",
                "ended_at": ended_at,
                "stages": stages,
                "checkpoint_artifact": str(checkpoint_path),
                "checkpoint_status": checkpoint["status"],
                "checkpoint_blocked_reason": str(exc),
            }
        )
        solution_trace.event(
            "workspace_resolution_blocked",
            status="blocked",
            payload={"reason": str(exc)},
        )
        return None

    started_at = utc_now()
    set_stage_status(stages, "solution_design", "running", started_at=started_at)
    send_stage_notification(
        message_id, run_payload["run_id"], "solution_design", "started", stages,
    )
    run_payload["stages"] = stages
    solution_trace.event("workspace_resolved", status="success", payload=workspace)
    solution_path = run_dir / "solution.json"
    try:
        send_thinking_notification(
            message_id, run_payload["run_id"], "solution_design",
        )
        thinking_timer = ThinkingTimer(message_id, run_payload["run_id"], "solution_design")
        thinking_timer.start()
        try:
            artifact = build_solution_design_artifact(
                requirement_artifact,
                workspace,
                config.llm,
                requirement_path=requirement_path,
                stage_trace=solution_trace,
            )
        finally:
            thinking_timer.cancel()
        write_solution_artifact(artifact, solution_path)
        solution_markdown_path = run_dir / "solution.md"
        solution_markdown_path.write_text(
            render_solution_markdown(artifact, run_id=run_payload["run_id"]),
            encoding="utf-8",
        )
        checkpoint = build_solution_review_checkpoint(
            run_payload,
            solution_path,
            solution_markdown_path,
        )
        checkpoint_path = write_checkpoint(run_dir, checkpoint)
        solution_trace.event(
            "solution_artifact_written",
            status="success",
            payload={"path": str(solution_path), "schema_version": artifact.get("schema_version")},
        )
        ended_at = utc_now()
        set_stage_status(
            stages,
            "solution_design",
            "success",
            ended_at=ended_at,
            artifact=str(solution_path),
        )
        send_stage_notification(
            message_id, run_payload["run_id"], "solution_design", "completed", stages,
        )
        run_payload["solution_title"] = artifact["proposed_solution"]["summary"]
        run_payload["solution_markdown"] = str(solution_markdown_path)
        run_payload["checkpoint_artifact"] = str(checkpoint_path)
        run_payload["checkpoint_status"] = checkpoint["status"]
        run_payload["stages"] = stages
        publish_solution_review_checkpoint(
            run_payload,
            artifact,
            solution_path=solution_path,
            solution_markdown_path=solution_markdown_path,
            message_id=message_id,
            card_reply_sender=card_reply_sender,
            stage_trace=solution_trace,
            event_source=requirement_source,
        )
        return solution_path
    except (LlmError, ValueError) as exc:
        ended_at = utc_now()
        set_stage_status(
            stages,
            "solution_design",
            "failed",
            ended_at=ended_at,
            error=str(exc),
        )
        send_stage_notification(
            message_id, run_payload["run_id"], "solution_design", "failed", stages, error_summary=str(exc),
        )
        solution_trace.event("solution_design_failed", status="failed", payload={"error": str(exc)})
        raise


def publish_solution_review_checkpoint(
    run_payload: dict[str, Any],
    solution_artifact: dict[str, Any],
    *,
    solution_path: Path,
    solution_markdown_path: Path,
    message_id: str,
    card_reply_sender: CardReplySender | None,
    stage_trace: StageTrace,
    event_source: RequirementSource | None = None,
) -> None:
    config = load_config()
    approval_cfg = config.approval

    # Try Lark approval flow first if enabled and we have user identity
    if (
        approval_cfg.enabled
        and event_source is not None
        and event_source.metadata.get("sender_id")
    ):
        try:
            stage_trace.event("approval_creation_attempted", status="running")
            _publish_via_external_approval(
                run_payload,
                solution_artifact,
                solution_path=solution_path,
                solution_markdown_path=solution_markdown_path,
                message_id=message_id,
                event_source=event_source,
                stage_trace=stage_trace,
            )
            return
        except (ApprovalError, ConfigError, LarkCliError) as exc:
            stage_trace.event("approval_creation_failed", status="failed", payload={"error": str(exc)})
            # Fall through to card-based fallback

    # Fallback: interactive card with text commands
    solution_doc_url: str | None = None
    try:
        config = load_config()
        folder_token = config.lark.prd_folder_token or None
        solution_markdown_content = Path(solution_markdown_path).read_text(encoding="utf-8")
        doc_result = publish_document(
            title=f"技术方案 - {run_payload['run_id']}",
            markdown=solution_markdown_content,
            folder_token=folder_token,
        )
        solution_doc_url = doc_result.get("url") or None
        stage_trace.event("solution_doc_published", status="success", payload={"url": solution_doc_url})
    except Exception as exc:
        solution_doc_url = None
        run_payload["solution_doc_publish_error"] = str(exc)
        stage_trace.event("solution_doc_publish_failed", status="failed", payload={"error": str(exc)})

    card_sender = send_bot_card_reply if card_reply_sender is None else card_reply_sender
    try:
        card = build_solution_review_card(
            run_payload,
            solution_artifact,
            solution_path=solution_path,
            solution_markdown_path=solution_markdown_path,
            solution_doc_url=solution_doc_url,
        )
        stage_trace.event("solution_review_card_attempted", status="running")
        card_sender(
            message_id,
            card,
            _idempotency_key(run_payload['run_id'], "solution-review"),
        )
        run_payload["checkpoint_publication"] = {"status": "success", "channel": "card"}
        stage_trace.event("solution_review_card_completed", status="success")
    except Exception as exc:
        run_payload["checkpoint_publication"] = {"status": "failed", "error": str(exc), "channel": "card"}
        run_payload["reply_error"] = str(exc)
        stage_trace.event("solution_review_card_failed", status="failed", payload={"error": str(exc)})


def _publish_via_external_approval(
    run_payload: dict[str, Any],
    solution_artifact: dict[str, Any],
    *,
    solution_path: Path,
    solution_markdown_path: Path,
    message_id: str,
    event_source: RequirementSource,
    stage_trace: StageTrace,
) -> None:
    """Create a Lark third-party approval instance and notify the user via IM.

    Uses external approval (三方审批) which does NOT require a pre-configured
    admin console template. The approval definition is created programmatically.
    """
    from devflow.approval_client import (
        create_external_approval_instance,
        ensure_approval_definition,
    )

    config = load_config()
    approval_cfg = config.approval
    run_id = run_payload["run_id"]
    sender_id = event_source.metadata.get("sender_id")
    if not sender_id:
        raise ApprovalError("无法获取审批人 open_id。")

    # Ensure the external approval definition exists (auto-create if needed)
    approval_code = ensure_approval_definition(
        approval_code_hint=approval_cfg.definition_code or None,
        user_open_id=sender_id,
    )

    proposed = solution_artifact.get("proposed_solution") or {}
    quality = solution_artifact.get("quality") or {}
    summary = proposed.get("summary") or "技术方案已生成"
    risk = quality.get("risk_level") or "medium"

    instance_id = create_external_approval_instance(
        approval_code=approval_code,
        user_open_id=sender_id,
        run_id=run_id,
        summary=summary,
        risk_level=risk,
        solution_markdown_path=str(solution_markdown_path),
    )

    # Update checkpoint with approval instance info
    run_dir = Path(run_payload["run_dir"])
    checkpoint_path = run_dir / "checkpoint.json"
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
        checkpoint["approval_instance_code"] = instance_id
        checkpoint["approval_code"] = approval_code
        checkpoint["status"] = "waiting_approval"
        write_checkpoint(run_dir, checkpoint)
        run_payload["checkpoint_artifact"] = str(checkpoint_path)
        run_payload["checkpoint_status"] = checkpoint["status"]

    run_payload["approval_instance_code"] = instance_id
    run_payload["approval_code"] = approval_code
    run_payload["checkpoint_publication"] = {"status": "success", "channel": "external_approval"}
    stage_trace.event("approval_creation_completed", status="success", payload={"instance_id": instance_id, "approval_code": approval_code})

    # Notify user via IM
    sender = send_bot_reply
    approval_msg = (
        f"技术方案已生成，已为你发起审批「技术方案评审 - {run_id}」。\n"
        f"请在飞书「审批」应用中查看并处理。\n"
        f"运行 ID：{run_id}\n"
        f"方案文档：{solution_markdown_path}"
    )
    try:
        sender(
            message_id,
            approval_msg,
            _idempotency_key(run_id, "approval-notify"),
        )
        stage_trace.event("approval_notification_sent", status="success")
    except LarkCliError as exc:
        stage_trace.event("approval_notification_failed", status="failed", payload={"error": str(exc)})


def handle_system_command(
    cmd: SystemCommand,
    event_source: RequirementSource,
    *,
    out_dir: Path,
    reply_sender: ReplySender | None,
    card_reply_sender: CardReplySender | None,
) -> PipelineResult:
    if cmd.command == "help":
        card = _build_help_card()
    else:
        card = _build_status_card(event_source, out_dir=out_dir)
    sender = send_bot_card_reply if card_reply_sender is None else card_reply_sender
    dummy_run_id = f"sys-{cmd.command}-{uuid4().hex[:8]}"
    reply_error = None
    try:
        sender(
            event_source.source_id,
            card,
            _idempotency_key(dummy_run_id, cmd.command),
        )
    except LarkCliError as exc:
        reply_error = str(exc)
        fallback = send_bot_reply if reply_sender is None else reply_sender
        if fallback is not None:
            try:
                fallback(
                    event_source.source_id,
                    _card_fallback_text(card),
                    _idempotency_key(dummy_run_id, f"{cmd.command}-fallback"),
                )
            except LarkCliError:
                pass
    return PipelineResult(
        run_id=dummy_run_id,
        status="system_command",
        run_dir=out_dir,
        run_path=out_dir / "_system_command_",
        requirement_path=None,
        reply_error=reply_error,
    )


def _build_help_card() -> dict[str, Any]:
    body = "\n".join(
        [
            "**输入格式**",
            "• 直接发送需求描述即可启动流水线",
            "• 发送飞书文档链接可自动解析文档内容",
            "• 发送消息 ID（om_ 开头）可引用历史消息",
            "",
            "**系统命令**",
            "• `/help` 或 `/帮助`：查看使用指引",
            "• `/status` 或 `/状态`：查看当前任务状态",
            "",
            "**检查点命令**",
            "• `Approve <run_id>`：批准技术方案或代码评审",
            "• `Reject <run_id>`：拒绝并重做",
            "• `Reject <run_id>：理由`：拒绝并说明理由",
            "• `Approve <run_id> --force`：强制通过（含质量警告时）",
        ]
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "📖 DevFlow 使用指引"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
        ],
    }


def _build_status_card(
    event_source: RequirementSource,
    *,
    out_dir: Path,
) -> dict[str, Any]:
    active_runs = _find_active_runs(out_dir, event_source)
    if not active_runs:
        body = "当前没有进行中的任务。发送需求描述即可开始。"
    else:
        lines = ["**进行中的任务**", ""]
        for run in active_runs:
            run_id = run.get("run_id", "unknown")
            stage = _current_stage(run)
            started_at = run.get("started_at", "unknown")
            lines.append(f"• `{run_id}`：{stage}（启动于 {started_at}）")
        body = "\n".join(lines)
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green",
            "title": {"tag": "plain_text", "content": "📊 DevFlow 任务状态"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
        ],
    }


ACTIVE_STATUSES = frozenset({
    "running",
    "blocked",
    "waiting_approval",
    "waiting_approval_with_warnings",
    "waiting_clarification",
})


def _find_active_runs(
    out_dir: Path,
    event_source: RequirementSource,
) -> list[dict[str, Any]]:
    if not out_dir.exists():
        return []
    chat_id = event_source.metadata.get("chat_id")
    sender_id = event_source.metadata.get("sender_id")
    results: list[dict[str, Any]] = []
    for run_path in sorted(out_dir.glob("*/run.json")):
        try:
            payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
        if trigger.get("chat_id") != chat_id or trigger.get("sender_id") != sender_id:
            continue
        status = payload.get("status") or payload.get("lifecycle_status") or ""
        if status not in ACTIVE_STATUSES:
            continue
        results.append(payload)
    return results


def _current_stage(run_payload: dict[str, Any]) -> str:
    stages = run_payload.get("stages")
    if not isinstance(stages, list):
        return "unknown"
    stage_names = {
        "requirement_intake": "需求分析",
        "clarification": "需求澄清",
        "solution_design": "方案设计",
        "code_generation": "代码生成",
        "test_generation": "测试生成",
        "code_review": "代码评审",
        "delivery": "交付",
    }
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        if stage.get("status") == "running":
            name = stage.get("name", "unknown")
            return stage_names.get(name, name)
    for stage in reversed(stages):
        if not isinstance(stage, dict):
            continue
        if stage.get("status") in {"success", "failed", "blocked"}:
            name = stage.get("name", "unknown")
            return stage_names.get(name, name)
    return "unknown"


def _card_fallback_text(card: dict[str, Any]) -> str:
    parts: list[str] = []
    header = card.get("header") if isinstance(card.get("header"), dict) else {}
    title_obj = header.get("title") if isinstance(header.get("title"), dict) else {}
    title = title_obj.get("content", "")
    if title:
        parts.append(title)
    for element in card.get("elements", []):
        if isinstance(element, dict) and element.get("tag") == "div":
            text_obj = element.get("text") if isinstance(element.get("text"), dict) else {}
            if text_obj.get("tag") == "lark_md" and text_obj.get("content"):
                parts.append(text_obj["content"])
    return "\n".join(parts)


def maybe_process_checkpoint_event(
    event_source: RequirementSource,
    *,
    out_dir: Path,
    reply_sender: ReplySender | None,
    card_reply_sender: CardReplySender | None,
) -> PipelineResult | None:
    sys_cmd = parse_system_command(event_source.content)
    if sys_cmd is not None:
        return handle_system_command(
            sys_cmd,
            event_source,
            out_dir=out_dir,
            reply_sender=reply_sender,
            card_reply_sender=card_reply_sender,
        )

    command = parse_checkpoint_command(event_source.content, out_dir=out_dir)
    if command is not None:
        if isinstance(command, PrefixMatchError):
            sender = send_bot_reply if reply_sender is None else reply_sender
            if sender is not None:
                if command.matches:
                    sender(
                        event_source.source_id,
                        f"前缀 '{command.partial}' 匹配到多个运行：{', '.join(command.matches)}，请提供更完整的 ID",
                        _idempotency_key(command.partial, "prefix-ambiguous"),
                    )
                else:
                    sender(
                        event_source.source_id,
                        f"未找到以 '{command.partial}' 开头的运行",
                        _idempotency_key(command.partial, "prefix-no-match"),
                    )
            return None
        cmd_sender = send_bot_reply if reply_sender is None else reply_sender
        if cmd_sender is not None:
            confirm_text = (
                f"✅ 已收到同意指令，正在继续… 运行 ID：{command.run_id}"
                if command.decision == "approve"
                else f"🔄 已收到拒绝指令，正在处理… 运行 ID：{command.run_id}"
            )
            try:
                cmd_sender(
                    event_source.source_id,
                    confirm_text,
                    _idempotency_key(command.run_id, "cmd-confirm"),
                )
            except LarkCliError:
                pass
        run_dir = out_dir / command.run_id
        if not run_dir.exists():
            sender = send_bot_reply if reply_sender is None else reply_sender
            if sender is not None:
                sender(event_source.source_id, f"未找到运行：{command.run_id}", _idempotency_key(command.run_id, "missing"))
            return PipelineResult(command.run_id, "failed", run_dir, run_dir / "run.json", None)
        if command.decision == "approve":
            return approve_checkpoint_run(event_source, run_dir, reply_sender=reply_sender, force_override=command.force_override)
        return reject_checkpoint_run(
            event_source,
            run_dir,
            reason=command.reason,
            reply_sender=reply_sender,
            card_reply_sender=card_reply_sender,
        )

    pending_run_dir = find_awaiting_reject_reason_run(out_dir, event_source)
    if pending_run_dir is not None:
        return reject_checkpoint_run(
            event_source,
            pending_run_dir,
            reason=event_source.content.strip(),
            reply_sender=reply_sender,
            card_reply_sender=card_reply_sender,
        )

    clarification_run_dir = find_waiting_clarification_run(out_dir, event_source)
    if clarification_run_dir is not None:
        reply = parse_clarification_reply(event_source.content)
        return resume_from_clarification(
            event_source,
            clarification_run_dir,
            reply,
            reply_sender=reply_sender,
            card_reply_sender=card_reply_sender,
        )

    blocked_run_dir = find_blocked_workspace_run(out_dir, event_source)
    if blocked_run_dir is None:
        return None
    return resume_blocked_solution_design(
        event_source,
        blocked_run_dir,
        reply_sender=reply_sender,
        card_reply_sender=card_reply_sender,
    )


def resume_blocked_solution_design(
    event_source: RequirementSource,
    run_dir: Path,
    *,
    reply_sender: ReplySender | None,
    card_reply_sender: CardReplySender | None,
) -> PipelineResult:
    run_payload = load_run_payload(run_dir)
    requirement_path = Path(run_payload["requirement_artifact"])
    requirement = load_requirement_artifact(requirement_path)
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    workspace = resolve_workspace(message_text=event_source.content, config=config.workspace)
    trace = RunTrace(run_payload["run_id"], run_dir)
    solution_trace = trace.stage("solution_design")
    started_at = utc_now()
    set_stage_status(run_payload["stages"], "solution_design", "running", started_at=started_at)
    solution_path = run_dir / "solution.json"
    solution_markdown_path = run_dir / "solution.md"
    artifact = build_solution_design_artifact(
        requirement,
        workspace,
        config.llm,
        requirement_path=requirement_path,
        stage_trace=solution_trace,
    )
    write_solution_artifact(artifact, solution_path)
    solution_markdown_path.write_text(
        render_solution_markdown(artifact, run_id=run_payload["run_id"]),
        encoding="utf-8",
    )
    checkpoint = build_solution_review_checkpoint(run_payload, solution_path, solution_markdown_path)
    checkpoint_path = write_checkpoint(run_dir, checkpoint)
    set_stage_status(
        run_payload["stages"],
        "solution_design",
        "success",
        ended_at=utc_now(),
        artifact=str(solution_path),
    )
    run_payload["status"] = "success"
    run_payload["solution_artifact"] = str(solution_path)
    run_payload["solution_markdown"] = str(solution_markdown_path)
    run_payload["solution_title"] = artifact["proposed_solution"]["summary"]
    run_payload["checkpoint_artifact"] = str(checkpoint_path)
    run_payload["checkpoint_status"] = checkpoint["status"]
    write_json(run_dir / "run.json", run_payload)
    publish_solution_review_checkpoint(
        run_payload,
        artifact,
        solution_path=solution_path,
        solution_markdown_path=solution_markdown_path,
        message_id=event_source.source_id,
        card_reply_sender=card_reply_sender,
        stage_trace=solution_trace,
    )
    write_json(run_dir / "run.json", run_payload)
    sender = send_bot_reply if reply_sender is None else reply_sender
    if sender is not None:
        card_note = "（卡片发送失败，请查看 artifacts 获取详情）" if run_payload.get("reply_error") else ""
        try:
            sender(
                event_source.source_id,
                f"已补充仓库上下文并生成技术方案：{solution_markdown_path}{card_note}",
                _idempotency_key(run_payload['run_id'], "checkpoint-resume"),
            )
        except LarkCliError as exc:
            run_payload["reply_error"] = str(exc)
            write_json(run_dir / "run.json", run_payload)
    return PipelineResult(
        run_payload["run_id"],
        "waiting_approval",
        run_dir,
        run_dir / "run.json",
        requirement_path,
        solution_path,
    )


def approve_checkpoint_run(
    event_source: RequirementSource,
    run_dir: Path,
    *,
    reply_sender: ReplySender | None,
    force_override: bool = False,
) -> PipelineResult:
    current_checkpoint = load_checkpoint(run_dir)
    existing_payload = load_run_payload(run_dir)
    lifecycle_status = existing_payload.get("lifecycle_status") or existing_payload.get("status")
    if lifecycle_status in {"paused", "terminated"}:
        sender = send_bot_reply if reply_sender is None else reply_sender
        if sender is not None:
            sender(
                event_source.source_id,
                f"当前运行 {existing_payload['run_id']} 状态为 {lifecycle_status}，不能继续检查点。",
                _idempotency_key(existing_payload["run_id"], "checkpoint-blocked"),
            )
        return PipelineResult(
            existing_payload["run_id"],
            str(lifecycle_status),
            run_dir,
            run_dir / "run.json",
            Path(existing_payload["requirement_artifact"]) if existing_payload.get("requirement_artifact") else None,
            Path(existing_payload["solution_artifact"]) if existing_payload.get("solution_artifact") else None,
        )
    checkpoint = apply_checkpoint_decision(
        run_dir,
        "approve",
        reviewer=reviewer_from_event(event_source),
        force_override=force_override,
    )
    if checkpoint["status"] == "waiting_approval_with_warnings":
        sender = send_bot_reply if reply_sender is None else reply_sender
        if sender is not None:
            blocked_reason = checkpoint.get("approval_blocked_reason", "方案未就绪，无法批准。如需强制通过请使用 --force")
            sender(
                event_source.source_id,
                blocked_reason,
                _idempotency_key(existing_payload["run_id"], "approval-blocked"),
            )
        return PipelineResult(
            existing_payload["run_id"],
            "waiting_approval_with_warnings",
            run_dir,
            run_dir / "run.json",
            Path(existing_payload["requirement_artifact"]) if existing_payload.get("requirement_artifact") else None,
            Path(existing_payload["solution_artifact"]) if existing_payload.get("solution_artifact") else None,
        )
    run_payload = load_run_payload(run_dir)
    run_payload["checkpoint_status"] = checkpoint["status"]
    run_payload["checkpoint_artifact"] = str(run_dir / "checkpoint.json")
    write_json(run_dir / "run.json", run_payload)
    if current_checkpoint.get("stage") == "code_review":
        from devflow.graph_runner import run_pipeline_graph

        run_payload = run_pipeline_graph(run_dir, entrypoint="code_review_approved", checkpoint=checkpoint)
        delivery_path = Path(run_payload["delivery_artifact"])
        sender = send_bot_reply if reply_sender is None else reply_sender
        if sender is not None:
            sender(
                event_source.source_id,
                f"已确认代码评审并生成交付包：{run_payload['run_id']}。产物：{delivery_path}",
                _idempotency_key(run_payload['run_id'], "code-review-approved"),
            )
        return PipelineResult(
            run_payload["run_id"],
            "delivered",
            run_dir,
            run_dir / "run.json",
            Path(run_payload["requirement_artifact"]) if run_payload.get("requirement_artifact") else None,
            Path(run_payload["solution_artifact"]) if run_payload.get("solution_artifact") else None,
        )
    from devflow.graph_runner import run_pipeline_graph

    run_payload = run_pipeline_graph(run_dir, entrypoint="solution_approved", checkpoint=checkpoint)
    final_artifact_path = Path(run_payload["code_review_artifact"]) if run_payload.get("code_review_artifact") else None
    sender = send_bot_reply if reply_sender is None else reply_sender
    if sender is not None:
        if final_artifact_path is None:
            sender(
                event_source.source_id,
                f"已确认技术方案：{run_payload['run_id']}。缺少 solution_artifact，已记录 code_generation 继续请求。",
                _idempotency_key(run_payload['run_id'], "checkpoint-approved"),
            )
        else:
            sender(
                event_source.source_id,
                f"已确认技术方案并完成代码生成、测试生成和代码评审：{run_payload['run_id']}。产物：{final_artifact_path}",
                _idempotency_key(run_payload['run_id'], "code-review-generated"),
            )
    return PipelineResult(
        run_payload["run_id"],
        "waiting_code_review" if run_payload.get("code_review_artifact") else ("test_generated" if run_payload.get("test_generation_artifact") else ("code_generated" if final_artifact_path is not None else "approved")),
        run_dir,
        run_dir / "run.json",
        Path(run_payload["requirement_artifact"]) if run_payload.get("requirement_artifact") else None,
        Path(run_payload["solution_artifact"]) if run_payload.get("solution_artifact") else None,
    )


def run_code_generation_after_approval(run_dir: Path, run_payload: dict[str, Any]) -> Path | None:
    solution_artifact = run_payload.get("solution_artifact")
    if not solution_artifact:
        run_payload["continuation"] = {
            "requested": True,
            "stage": "code_generation",
            "requested_at": utc_now(),
            "note": "缺少 solution_artifact，当前仅记录继续请求。",
        }
        return None

    trace = RunTrace(run_payload["run_id"], run_dir)
    stage_trace = trace.stage("code_generation")
    started_at = utc_now()
    set_stage_status(run_payload["stages"], "code_generation", "running", started_at=started_at)
    send_stage_notification(
        _trigger_message_id(run_payload), run_payload["run_id"], "code_generation", "started", run_payload["stages"],
    )
    try:
        config = load_config(require_llm_api_key=True, require_llm_model=True)
        solution = load_solution_artifact(solution_artifact)
        send_thinking_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "code_generation",
        )
        thinking_timer = ThinkingTimer(_trigger_message_id(run_payload), run_payload["run_id"], "code_generation")
        thinking_timer.start()
        try:
            artifact = build_code_generation_artifact(solution, config.llm, stage_trace=stage_trace)
        finally:
            thinking_timer.cancel()
        code_path = write_code_generation_artifact(artifact, run_dir / "code-generation.json")
        diff_path = write_code_diff(artifact, run_dir / "code.diff")
        ended_at = utc_now()
        set_stage_status(
            run_payload["stages"],
            "code_generation",
            "success",
            ended_at=ended_at,
            artifact=str(code_path),
        )
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "code_generation", "completed", run_payload["stages"],
        )
        run_payload["status"] = "success"
        run_payload["code_generation_artifact"] = str(code_path)
        run_payload["code_diff"] = str(diff_path)
        run_payload["code_generation_summary"] = artifact.get("summary")
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event(
            "code_generation_artifact_written",
            status="success",
            payload={"path": str(code_path), "schema_version": artifact.get("schema_version")},
        )
        return run_test_generation_after_code_generation(run_dir, run_payload)
    except QualityGateError as exc:
        ended_at = utc_now()
        set_stage_status(
            run_payload["stages"],
            "code_generation",
            "failed",
            ended_at=ended_at,
            error=str(exc),
        )
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "code_generation", "failed", run_payload["stages"], error_summary=str(exc),
        )
        run_payload["status"] = "failed"
        run_payload["lifecycle_status"] = "failed"
        run_payload["ended_at"] = ended_at
        run_payload["error"] = {
            "stage": "code_generation",
            "message": str(exc),
            "reasons": exc.reasons,
            "quality_snapshot": exc.quality_snapshot,
        }
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event("code_generation_failed", status="failed", payload={"error": str(exc), "reasons": exc.reasons})
        return None
    except (ConfigError, LlmError, ValueError) as exc:
        ended_at = utc_now()
        set_stage_status(
            run_payload["stages"],
            "code_generation",
            "failed",
            ended_at=ended_at,
            error=str(exc),
        )
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "code_generation", "failed", run_payload["stages"], error_summary=str(exc),
        )
        run_payload["status"] = "failed"
        run_payload["error"] = {"stage": "code_generation", "message": str(exc)}
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event("code_generation_failed", status="failed", payload={"error": str(exc)})
        raise


def run_test_generation_after_code_generation(run_dir: Path, run_payload: dict[str, Any]) -> Path | None:
    requirement_artifact = run_payload.get("requirement_artifact")
    solution_artifact = run_payload.get("solution_artifact")
    code_generation_artifact = run_payload.get("code_generation_artifact")
    if not requirement_artifact or not solution_artifact or not code_generation_artifact:
        run_payload["continuation"] = {
            "requested": True,
            "stage": "test_generation",
            "requested_at": utc_now(),
            "note": "缺少测试生成所需的上游产物，当前仅记录继续请求。",
        }
        write_json(run_dir / "run.json", run_payload)
        return None

    trace = RunTrace(run_payload["run_id"], run_dir)
    stage_trace = trace.stage("test_generation")
    started_at = utc_now()
    set_stage_status(run_payload["stages"], "test_generation", "running", started_at=started_at)
    send_stage_notification(
        _trigger_message_id(run_payload), run_payload["run_id"], "test_generation", "started", run_payload["stages"],
    )
    try:
        config = load_config(require_llm_api_key=True, require_llm_model=True)
        requirement = load_test_requirement_artifact(requirement_artifact)
        solution = load_solution_artifact(solution_artifact)
        code_generation = load_code_generation_artifact(code_generation_artifact)
        send_thinking_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "test_generation",
        )
        thinking_timer = ThinkingTimer(_trigger_message_id(run_payload), run_payload["run_id"], "test_generation")
        thinking_timer.start()
        try:
            artifact = build_test_generation_artifact(
                requirement,
                solution,
                code_generation,
                config.llm,
                requirement_path=requirement_artifact,
                solution_path=solution_artifact,
                code_generation_path=code_generation_artifact,
                stage_trace=stage_trace,
            )
        finally:
            thinking_timer.cancel()
        test_path = write_test_generation_artifact(artifact, run_dir / "test-generation.json")
        diff_path = write_test_diff(artifact, run_dir / "test.diff")
        ended_at = utc_now()
        set_stage_status(
            run_payload["stages"],
            "test_generation",
            "success",
            ended_at=ended_at,
            artifact=str(test_path),
        )
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "test_generation", "completed", run_payload["stages"],
        )
        run_payload["status"] = "success"
        run_payload["test_generation_artifact"] = str(test_path)
        run_payload["test_diff"] = str(diff_path)
        run_payload["test_generation_summary"] = artifact.get("summary")
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event(
            "test_generation_artifact_written",
            status="success",
            payload={"path": str(test_path), "schema_version": artifact.get("schema_version")},
        )
        write_json(run_dir / "run.json", run_payload)
        return run_code_review_after_test_generation(run_dir, run_payload)
    except (ConfigError, LlmError, ValueError) as exc:
        ended_at = utc_now()
        set_stage_status(
            run_payload["stages"],
            "test_generation",
            "failed",
            ended_at=ended_at,
            error=str(exc),
        )
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "test_generation", "failed", run_payload["stages"], error_summary=str(exc),
        )
        run_payload["status"] = "failed"
        run_payload["error"] = {"stage": "test_generation", "message": str(exc)}
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event("test_generation_failed", status="failed", payload={"error": str(exc)})
        write_json(run_dir / "run.json", run_payload)
        raise


def run_code_review_after_test_generation(
    run_dir: Path,
    run_payload: dict[str, Any],
    *,
    attempt: int | None = None,
    allow_auto_repair: bool = True,
) -> Path | None:
    requirement_artifact = run_payload.get("requirement_artifact")
    solution_artifact = run_payload.get("solution_artifact")
    code_generation_artifact = run_payload.get("code_generation_artifact")
    test_generation_artifact = run_payload.get("test_generation_artifact")
    if not requirement_artifact or not solution_artifact or not code_generation_artifact or not test_generation_artifact:
        run_payload["continuation"] = {
            "requested": True,
            "stage": "code_review",
            "requested_at": utc_now(),
            "note": "缺少代码评审所需的上游产物，当前仅记录继续请求。",
        }
        write_json(run_dir / "run.json", run_payload)
        return None

    review_attempt = attempt or int(run_payload.get("repair_attempts") or 0) + 1
    suffix = "" if review_attempt == 1 else f"-attempt-{review_attempt}"
    trace = RunTrace(run_payload["run_id"], run_dir)
    stage_trace = trace.stage("code_review")
    started_at = utc_now()
    set_stage_status(run_payload["stages"], "code_review", "running", started_at=started_at)
    send_stage_notification(
        _trigger_message_id(run_payload), run_payload["run_id"], "code_review", "started", run_payload["stages"],
    )
    try:
        config = load_config(require_llm_api_key=True, require_llm_model=True)
        requirement = load_review_requirement_artifact(requirement_artifact)
        solution = load_solution_artifact(solution_artifact)
        code_generation = load_code_generation_artifact(code_generation_artifact)
        test_generation = json.loads(Path(test_generation_artifact).read_text(encoding="utf-8-sig"))
        send_thinking_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "code_review",
        )
        thinking_timer = ThinkingTimer(_trigger_message_id(run_payload), run_payload["run_id"], "code_review")
        thinking_timer.start()
        try:
            artifact = build_code_review_artifact(
                requirement,
                solution,
                code_generation,
                test_generation,
                config.llm,
                requirement_path=requirement_artifact,
                solution_path=solution_artifact,
                code_generation_path=code_generation_artifact,
                test_generation_path=test_generation_artifact,
                stage_trace=stage_trace,
            )
        finally:
            thinking_timer.cancel()
        review_path = write_code_review_artifact(artifact, run_dir / f"code-review{suffix}.json")
        review_markdown_path = run_dir / f"code-review{suffix}.md"
        review_markdown_path.write_text(
            render_code_review_markdown(artifact, run_id=run_payload["run_id"]),
            encoding="utf-8",
        )
        ended_at = utc_now()
        set_stage_status(
            run_payload["stages"],
            "code_review",
            "success",
            ended_at=ended_at,
            artifact=str(review_path),
        )
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "code_review", "completed", run_payload["stages"],
        )
        run_payload["status"] = "success"
        run_payload["code_review_artifact"] = str(review_path)
        run_payload["code_review_markdown"] = str(review_markdown_path)
        run_payload["code_review_summary"] = artifact.get("summary")
        run_payload["code_review_status"] = artifact.get("review_status")
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event(
            "code_review_artifact_written",
            status="success",
            payload={"path": str(review_path), "schema_version": artifact.get("schema_version")},
        )
        write_json(run_dir / "run.json", run_payload)

        if should_auto_repair_review(artifact, run_payload, allow_auto_repair=allow_auto_repair):
            return run_repair_after_code_review(run_dir, run_payload, artifact)

        publish_code_review_checkpoint(
            run_payload,
            artifact,
            review_path=review_path,
            review_markdown_path=review_markdown_path,
            stage_trace=stage_trace,
        )
        write_json(run_dir / "run.json", run_payload)
        return review_path
    except (ConfigError, LlmError, ValueError) as exc:
        ended_at = utc_now()
        set_stage_status(
            run_payload["stages"],
            "code_review",
            "failed",
            ended_at=ended_at,
            error=str(exc),
        )
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "code_review", "failed", run_payload["stages"], error_summary=str(exc),
        )
        run_payload["status"] = "failed"
        run_payload["error"] = {"stage": "code_review", "message": str(exc)}
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event("code_review_failed", status="failed", payload={"error": str(exc)})
        write_json(run_dir / "run.json", run_payload)
        raise


def should_auto_repair_review(
    artifact: dict[str, Any],
    run_payload: dict[str, Any],
    *,
    allow_auto_repair: bool,
) -> bool:
    if not allow_auto_repair:
        return False
    if int(run_payload.get("repair_attempts") or 0) >= 1:
        return False
    gate = artifact.get("quality_gate") if isinstance(artifact.get("quality_gate"), dict) else {}
    return artifact.get("review_status") != "passed" or gate.get("passed") is False


def run_repair_after_code_review(
    run_dir: Path,
    run_payload: dict[str, Any],
    review_artifact: dict[str, Any],
) -> Path | None:
    run_payload["repair_attempts"] = int(run_payload.get("repair_attempts") or 0) + 1
    attempt = int(run_payload["repair_attempts"]) + 1
    trace = RunTrace(run_payload["run_id"], run_dir)
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    solution = load_solution_artifact(run_payload["solution_artifact"])
    solution["code_review_feedback"] = {
        "review_status": review_artifact.get("review_status"),
        "findings": review_artifact.get("findings"),
        "repair_recommendations": review_artifact.get("repair_recommendations"),
        "summary": review_artifact.get("summary"),
    }

    code_trace = trace.stage("code_generation")
    set_stage_status(run_payload["stages"], "code_generation", "running", started_at=utc_now())
    code_artifact = build_code_generation_artifact(solution, config.llm, stage_trace=code_trace)
    code_path = write_code_generation_artifact(code_artifact, run_dir / f"code-generation-attempt-{attempt}.json")
    diff_path = write_code_diff(code_artifact, run_dir / f"code-attempt-{attempt}.diff")
    set_stage_status(run_payload["stages"], "code_generation", "success", ended_at=utc_now(), artifact=str(code_path))
    run_payload["code_generation_artifact"] = str(code_path)
    run_payload["code_diff"] = str(diff_path)
    run_payload["code_generation_summary"] = code_artifact.get("summary")

    test_trace = trace.stage("test_generation")
    set_stage_status(run_payload["stages"], "test_generation", "running", started_at=utc_now())
    requirement = load_test_requirement_artifact(run_payload["requirement_artifact"])
    fresh_solution = load_solution_artifact(run_payload["solution_artifact"])
    test_artifact = build_test_generation_artifact(
        requirement,
        fresh_solution,
        code_artifact,
        config.llm,
        requirement_path=run_payload["requirement_artifact"],
        solution_path=run_payload["solution_artifact"],
        code_generation_path=code_path,
        stage_trace=test_trace,
    )
    test_path = write_test_generation_artifact(test_artifact, run_dir / f"test-generation-attempt-{attempt}.json")
    test_diff_path = write_test_diff(test_artifact, run_dir / f"test-attempt-{attempt}.diff")
    set_stage_status(run_payload["stages"], "test_generation", "success", ended_at=utc_now(), artifact=str(test_path))
    run_payload["test_generation_artifact"] = str(test_path)
    run_payload["test_diff"] = str(test_diff_path)
    run_payload["test_generation_summary"] = test_artifact.get("summary")
    run_payload["audit"] = build_audit_payload(trace, run_dir)
    write_json(run_dir / "run.json", run_payload)
    return run_code_review_after_test_generation(run_dir, run_payload, attempt=attempt, allow_auto_repair=False)


def run_delivery_after_code_review_approval(
    run_dir: Path,
    run_payload: dict[str, Any],
    checkpoint: dict[str, Any] | None = None,
) -> Path:
    checkpoint_payload = checkpoint or load_checkpoint(run_dir)
    trace = RunTrace(run_payload["run_id"], run_dir)
    stage_trace = trace.stage("delivery")
    started_at = utc_now()
    set_stage_status(run_payload["stages"], "delivery", "running", started_at=started_at)
    send_stage_notification(
        _trigger_message_id(run_payload), run_payload["run_id"], "delivery", "started", run_payload["stages"],
    )
    try:
        requirement_path = Path(run_payload.get("requirement_artifact") or run_dir / "requirement.json")
        solution_path = Path(run_payload.get("solution_artifact") or run_dir / "solution.json")
        code_generation_path = Path(run_payload.get("code_generation_artifact") or run_dir / "code-generation.json")
        test_generation_path = Path(run_payload.get("test_generation_artifact") or run_dir / "test-generation.json")
        code_review_path = Path(run_payload.get("code_review_artifact") or run_dir / "code-review.json")
        checkpoint_path = run_dir / "checkpoint.json"
        artifact = build_delivery_artifact(
            run_payload,
            json.loads(requirement_path.read_text(encoding="utf-8-sig")),
            json.loads(solution_path.read_text(encoding="utf-8-sig")),
            json.loads(code_generation_path.read_text(encoding="utf-8-sig")),
            json.loads(test_generation_path.read_text(encoding="utf-8-sig")),
            json.loads(code_review_path.read_text(encoding="utf-8-sig")),
            checkpoint_payload,
            requirement_path=requirement_path,
            solution_path=solution_path,
            code_generation_path=code_generation_path,
            test_generation_path=test_generation_path,
            code_review_path=code_review_path,
            checkpoint_path=checkpoint_path,
        )
        delivery_path = write_delivery_artifact(artifact, run_dir / "delivery.json")
        delivery_markdown_path = run_dir / "delivery.md"
        delivery_markdown_path.write_text(render_delivery_markdown(artifact), encoding="utf-8")
        delivery_diff_path = write_delivery_diff(artifact, run_dir / "delivery.diff")
        ended_at = utc_now()
        set_stage_status(run_payload["stages"], "delivery", "success", ended_at=ended_at, artifact=str(delivery_path))
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "delivery", "completed", run_payload["stages"],
        )
        run_payload["status"] = "delivered"
        run_payload["delivery_artifact"] = str(delivery_path)
        run_payload["delivery_markdown"] = str(delivery_markdown_path)
        run_payload["delivery_diff"] = str(delivery_diff_path)
        run_payload["delivery_ready_to_merge"] = artifact["readiness"]["ready_to_merge"]
        run_payload["delivery_summary"] = artifact["change_summary"]
        run_payload["checkpoint_stage"] = "code_review"
        run_payload["checkpoint_status"] = checkpoint_payload.get("status")
        run_payload["checkpoint_artifact"] = str(checkpoint_path)
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event(
            "delivery_artifact_written",
            status="success",
            payload={"path": str(delivery_path), "schema_version": artifact.get("schema_version")},
        )
        write_json(run_dir / "run.json", run_payload)
        return delivery_path
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        ended_at = utc_now()
        set_stage_status(run_payload["stages"], "delivery", "failed", ended_at=ended_at, error=str(exc))
        send_stage_notification(
            _trigger_message_id(run_payload), run_payload["run_id"], "delivery", "failed", run_payload["stages"], error_summary=str(exc),
        )
        run_payload["status"] = "failed"
        run_payload["error"] = {"stage": "delivery", "message": str(exc)}
        run_payload["audit"] = build_audit_payload(trace, run_dir)
        stage_trace.event("delivery_failed", status="failed", payload={"error": str(exc)})
        write_json(run_dir / "run.json", run_payload)
        raise


def publish_code_review_checkpoint(
    run_payload: dict[str, Any],
    review_artifact: dict[str, Any],
    *,
    review_path: Path,
    review_markdown_path: Path,
    stage_trace: StageTrace,
    card_reply_sender: CardReplySender | None = None,
) -> None:
    run_dir = Path(run_payload["run_dir"])
    checkpoint_path = run_dir / "checkpoint.json"
    if checkpoint_path.exists():
        try:
            previous = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            previous = None
        if previous is not None:
            history = run_payload.get("checkpoint_history") if isinstance(run_payload.get("checkpoint_history"), list) else []
            history.append(previous)
            run_payload["checkpoint_history"] = history

    checkpoint = build_code_review_checkpoint(
        run_payload,
        review_path,
        review_markdown_path,
        attempt=int(run_payload.get("repair_attempts") or 0) + 1,
    )
    written = write_checkpoint(run_dir, checkpoint)
    run_payload["checkpoint_artifact"] = str(written)
    run_payload["checkpoint_status"] = checkpoint["status"]
    run_payload["checkpoint_stage"] = checkpoint["stage"]
    run_payload["checkpoint_publication"] = {"status": "local", "channel": "artifact"}

    if card_reply_sender is not None:
        review_doc_url: str | None = None
        try:
            config = load_config()
            folder_token = config.lark.prd_folder_token or None
            review_markdown_content = Path(review_markdown_path).read_text(encoding="utf-8")
            doc_result = publish_document(
                title=f"代码评审 - {run_payload['run_id']}",
                markdown=review_markdown_content,
                folder_token=folder_token,
            )
            review_doc_url = doc_result.get("url") or None
            stage_trace.event("review_doc_published", status="success", payload={"url": review_doc_url})
        except Exception as exc:
            review_doc_url = None
            run_payload["review_doc_publish_error"] = str(exc)
            stage_trace.event("review_doc_publish_failed", status="failed", payload={"error": str(exc)})

        try:
            message_id = str((run_payload.get("trigger") or {}).get("message_id") or "")
            if message_id:
                card = build_code_review_card(
                    run_payload,
                    review_artifact,
                    review_path=review_path,
                    review_markdown_path=review_markdown_path,
                    review_doc_url=review_doc_url,
                )
                stage_trace.event("code_review_card_attempted", status="running")
                card_reply_sender(message_id, card, _idempotency_key(run_payload["run_id"], "code-review"))
                run_payload["checkpoint_publication"] = {"status": "success", "channel": "card"}
                stage_trace.event("code_review_card_completed", status="success")
        except Exception as exc:
            run_payload["checkpoint_publication"] = {"status": "failed", "error": str(exc), "channel": "card"}
            run_payload["reply_error"] = str(exc)
            stage_trace.event("code_review_card_failed", status="failed", payload={"error": str(exc)})


def reject_checkpoint_run(
    event_source: RequirementSource,
    run_dir: Path,
    *,
    reason: str | None,
    reply_sender: ReplySender | None,
    card_reply_sender: CardReplySender | None,
) -> PipelineResult:
    current_checkpoint = load_checkpoint(run_dir)
    if not reason:
        checkpoint = apply_checkpoint_decision(
            run_dir,
            "reject",
            reviewer=reviewer_from_event(event_source),
        )
        run_payload = load_run_payload(run_dir)
        run_payload["checkpoint_status"] = checkpoint["status"]
        run_payload["checkpoint_artifact"] = str(run_dir / "checkpoint.json")
        write_json(run_dir / "run.json", run_payload)
        sender = send_bot_reply if reply_sender is None else reply_sender
        if sender is not None:
            stage_label = "代码和测试" if current_checkpoint.get("stage") == "code_review" else "技术方案"
            sender(
                event_source.source_id,
                f"请补充 Reject 理由：{run_payload['run_id']}。我会根据你的意见重做{stage_label}。",
                _idempotency_key(run_payload['run_id'], "reject-reason"),
            )
        return PipelineResult(run_payload["run_id"], "awaiting_reject_reason", run_dir, run_dir / "run.json", None)

    rejected = apply_checkpoint_decision(
        run_dir,
        "reject",
        reason=reason,
        reviewer=reviewer_from_event(event_source),
    )
    if current_checkpoint.get("stage") == "code_review":
        run_payload = load_run_payload(run_dir)
        if int(run_payload.get("repair_attempts") or 0) >= 1:
            run_payload["checkpoint_status"] = rejected["status"]
            run_payload["checkpoint_artifact"] = str(run_dir / "checkpoint.json")
            run_payload["status"] = "blocked"
            run_payload["error"] = {"stage": "code_review", "message": reason}
            write_json(run_dir / "run.json", run_payload)
            return PipelineResult(run_payload["run_id"], "rejected", run_dir, run_dir / "run.json", None)
        feedback = {
            "review_status": "needs_changes",
            "findings": [
                {
                    "id": "CR-HUMAN-001",
                    "severity": "P1",
                    "category": "requirements",
                    "title": "人工代码评审拒绝",
                    "description": reason,
                    "fix_suggestion": reason,
                    "blocking": True,
                }
            ],
            "repair_recommendations": [reason],
            "summary": reason,
        }
        final_path = run_repair_after_code_review(run_dir, run_payload, feedback)
        return PipelineResult(
            run_payload["run_id"],
            "waiting_code_review",
            run_dir,
            run_dir / "run.json",
            Path(run_payload["requirement_artifact"]) if run_payload.get("requirement_artifact") else None,
            Path(run_payload["solution_artifact"]) if run_payload.get("solution_artifact") else None,
        )
    return rerun_solution_design_after_reject(
        event_source,
        run_dir,
        rejected,
        reason=reason,
        reply_sender=reply_sender,
        card_reply_sender=card_reply_sender,
    )


def rerun_solution_design_after_reject(
    event_source: RequirementSource,
    run_dir: Path,
    checkpoint: dict[str, Any],
    *,
    reason: str,
    reply_sender: ReplySender | None,
    card_reply_sender: CardReplySender | None,
) -> PipelineResult:
    run_payload = load_run_payload(run_dir)
    requirement_path = Path(run_payload["requirement_artifact"])
    requirement = load_requirement_artifact(requirement_path)
    requirement = requirement_with_review_feedback(requirement, reason)
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    workspace = workspace_from_previous_solution(checkpoint) or resolve_workspace(
        message_text=run_payload.get("detected_input", {}).get("value", ""),
        config=config.workspace,
    )
    trace = RunTrace(run_payload["run_id"], run_dir)
    solution_trace = trace.stage("solution_design")
    attempt = int(checkpoint.get("attempt") or 1) + 1
    solution_path = run_dir / f"solution-attempt-{attempt}.json"
    solution_markdown_path = run_dir / f"solution-attempt-{attempt}.md"
    artifact = build_solution_design_artifact(
        requirement,
        workspace,
        config.llm,
        requirement_path=requirement_path,
        stage_trace=solution_trace,
    )
    write_solution_artifact(artifact, solution_path)
    solution_markdown_path.write_text(
        render_solution_markdown(artifact, run_id=run_payload["run_id"]),
        encoding="utf-8",
    )
    next_checkpoint = build_solution_review_checkpoint(
        run_payload,
        solution_path,
        solution_markdown_path,
        attempt=attempt,
        previous_artifacts=checkpoint.get("artifact_history") if isinstance(checkpoint.get("artifact_history"), list) else [],
        reject_reason=reason,
    )
    checkpoint_path = write_checkpoint(run_dir, next_checkpoint)
    set_stage_status(
        run_payload["stages"],
        "solution_design",
        "success",
        ended_at=utc_now(),
        artifact=str(solution_path),
    )
    run_payload["status"] = "success"
    run_payload["solution_artifact"] = str(solution_path)
    run_payload["solution_markdown"] = str(solution_markdown_path)
    run_payload["solution_title"] = artifact["proposed_solution"]["summary"]
    run_payload["checkpoint_artifact"] = str(checkpoint_path)
    run_payload["checkpoint_status"] = next_checkpoint["status"]
    write_json(run_dir / "run.json", run_payload)
    publish_solution_review_checkpoint(
        run_payload,
        artifact,
        solution_path=solution_path,
        solution_markdown_path=solution_markdown_path,
        message_id=event_source.source_id,
        card_reply_sender=card_reply_sender,
        stage_trace=solution_trace,
    )
    write_json(run_dir / "run.json", run_payload)
    sender = send_bot_reply if reply_sender is None else reply_sender
    if sender is not None:
        card_note = "（卡片发送失败，请查看 artifacts 获取详情）" if run_payload.get("reply_error") else ""
        try:
            sender(
                event_source.source_id,
                f"已根据 Reject 理由重做技术方案：{solution_markdown_path}{card_note}",
                _idempotency_key(run_payload['run_id'], f"rerun-{attempt}"),
            )
        except LarkCliError as exc:
            run_payload["reply_error"] = str(exc)
            write_json(run_dir / "run.json", run_payload)
    return PipelineResult(
        run_payload["run_id"],
        "waiting_approval",
        run_dir,
        run_dir / "run.json",
        requirement_path,
        solution_path,
    )


def publish_requirement_prd(
    run_payload: dict[str, Any],
    artifact: dict[str, Any],
    message_id: str,
    *,
    prd_creator: PrdCreator | None,
    card_reply_sender: CardReplySender | None,
    stage_trace: StageTrace,
) -> None:
    publication = {
        "status": "running",
        "prd": None,
        "card_reply": None,
        "error": None,
    }
    run_payload["publication"] = publication
    title = artifact["normalized_requirement"]["title"]
    markdown = render_prd_markdown(artifact, run_id=run_payload["run_id"])
    creator = create_prd_document_for_pipeline if prd_creator is None else prd_creator
    card_sender = send_bot_card_reply if card_reply_sender is None else card_reply_sender
    try:
        stage_trace.event("prd_creation_started", status="running")
        prd = creator(title, markdown)
        publication["prd"] = prd
        stage_trace.event("prd_created", status="success", payload=prd)
        prd_url = prd.get("url") or ""
        card = build_prd_preview_card(
            artifact,
            run_id=run_payload["run_id"],
            detected_input=run_payload["detected_input"],
            prd_url=prd_url,
        )
        stage_trace.event("card_reply_attempted", status="running")
        card_sender(
            message_id,
            card,
            _idempotency_key(run_payload['run_id'], "prd-card"),
        )
        publication["card_reply"] = {"status": "success"}
        publication["status"] = "success"
        stage_trace.event("card_reply_completed", status="success")
    except Exception as exc:
        publication["status"] = "failed"
        publication["error"] = str(exc)
        if publication["prd"] is not None:
            run_payload["reply_error"] = str(exc)
        if publication["card_reply"] is None:
            publication["card_reply"] = {"status": "failed"}
        stage_trace.event("publication_failed", status="failed", payload={"error": str(exc)})


def _print_no_default_chat_guidance() -> None:
    lines = [
        "",
        "===================================================",
        "  DevFlow 机器人已就绪",
        "",
        "  用户可以在飞书中向机器人发送消息",
        "  启动开发流水线。",
        "",
        "  如需启动时发送欢迎消息，请在配置中设置：",
        '    interaction.default_chat_id = "oc_xxxxxxx"',
        "===================================================",
        "",
    ]
    for line in lines:
        print(line, file=sys.stderr)


def _send_welcome_message() -> None:
    try:
        config = load_config()
    except ConfigError:
        _print_no_default_chat_guidance()
        return
    chat_id = config.interaction.default_chat_id
    if not chat_id:
        _print_no_default_chat_guidance()
        return
    # Use text message instead of interactive card on Windows to avoid
    # command line length limitations with JSON content
    welcome_text = build_welcome_text(
        workspace_root=config.workspace.root,
        default_repo=config.workspace.default_repo,
    )
    try:
        # Use a high-resolution timestamp so quick restarts do not collide.
        import time
        idempotency_key = f"df-welcome-{time.time_ns()}"
        send_bot_text(
            chat_id,
            welcome_text,
            idempotency_key,
        )
    except LarkCliError as exc:
        print(f"欢迎消息发送失败：{exc}", file=sys.stderr)


def run_start_loop(
    *,
    out_dir: Path,
    once: bool,
    timeout_seconds: int | None,
    analyzer: str,
    model: str,
) -> int:
    _send_welcome_message()
    config = load_config()
    merge_window = config.interaction.message_merge_window_seconds
    max_queue_size = config.interaction.max_queue_size
    max_events = 1 if once else None

    def on_append(event: dict[str, Any]) -> None:
        source = event_to_source(event)
        message_id = source.source_id
        try:
            send_bot_reply(
                message_id,
                "已追加到当前需求中",
                _idempotency_key(message_id, "append"),
            )
        except LarkCliError:
            pass

    def on_queue_overflow(dropped_event: dict[str, Any]) -> None:
        source = event_to_source(dropped_event)
        message_id = source.source_id
        try:
            send_bot_reply(
                message_id,
                "消息队列已满，请等待当前任务完成",
                _idempotency_key(message_id, "queue-overflow"),
            )
        except LarkCliError:
            pass

    from devflow.message_buffer import MessageBuffer
    from devflow.message_queue import UserMessageQueue

    processed = 0
    raw_events = listen_bot_events(
        max_events=max_events,
        timeout_seconds=timeout_seconds,
    )
    buffered_events = MessageBuffer(
        raw_events,
        merge_window_seconds=merge_window,
        on_append=on_append,
    )

    def processor(event: dict[str, Any]) -> Any:
        return process_bot_event(
            event,
            out_dir=out_dir,
            analyzer=analyzer,
            model=model,
        )

    for result in UserMessageQueue(
        buffered_events,
        max_queue_size=max_queue_size,
        processor=processor,
        on_queue_overflow=on_queue_overflow,
    ):
        print(f"{result.run_id} {result.status} {result.run_dir}")
        processed += 1
        if once:
            break

    if once and processed == 0:
        raise LarkCliError("命令结束前没有收到机器人消息事件。")
    return processed


def create_prd_document_for_pipeline(title: str, markdown: str) -> dict[str, Any]:
    folder_token = None
    if DEFAULT_CONFIG_PATH.exists():
        config = load_config()
        folder_token = config.lark.prd_folder_token or None
    return create_prd_document(title, markdown, folder_token=folder_token)


def resolve_detected_source(
    detected: DetectedInput,
    event_source: RequirementSource,
    *,
    fetch_doc: FetchSource,
    fetch_message: FetchSource,
) -> RequirementSource:
    if detected.kind == "lark_doc":
        return fetch_doc(detected.value)
    if detected.kind == "lark_message":
        return fetch_message(detected.value)
    return RequirementSource(
        source_type="lark_bot_text",
        source_id=event_source.source_id,
        reference=event_source.reference,
        title=event_source.title,
        content=detected.value,
        identity=event_source.identity,
        metadata={
            **event_source.metadata,
            "detected_input_kind": detected.kind,
            "original_source_type": event_source.source_type,
        },
        attachments=event_source.attachments,
        embedded_resources=event_source.embedded_resources,
    )


def build_requirement_artifact_for_pipeline(
    source: RequirementSource,
    analyzer: str,
    model: str,
    *,
    stage_trace: StageTrace | None = None,
) -> dict[str, Any]:
    if analyzer == "heuristic":
        return build_requirement_artifact(source, model=model, analyzer="heuristic")
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    return build_requirement_artifact(
        source,
        analyzer="llm",
        llm_config=config.llm,
        stage_trace=stage_trace,
    )


def build_audit_payload(trace: RunTrace, run_dir: Path) -> dict[str, Any]:
    audit: dict[str, Any] = {
        "trace_path": str(trace.trace_path),
        "llm": None,
    }
    response_path = run_dir / "llm-response.json"
    request_path = run_dir / "llm-request.json"
    if not response_path.exists():
        return _with_solution_audit(audit, run_dir)
    try:
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return audit
    audit["llm"] = {
        "request_path": str(request_path),
        "response_path": str(response_path),
        "token_usage": response_payload.get("usage"),
        "usage_source": response_payload.get("usage_source", "missing"),
        "duration_ms": response_payload.get("duration_ms"),
    }
    return _with_solution_audit(audit, run_dir)


def load_run_payload(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))


def reviewer_from_event(event_source: RequirementSource) -> dict[str, Any]:
    return {
        "chat_id": event_source.metadata.get("chat_id"),
        "sender_id": event_source.metadata.get("sender_id"),
        "message_id": event_source.source_id,
        "reviewed_at": utc_now(),
    }


def find_awaiting_reject_reason_run(out_dir: Path, event_source: RequirementSource) -> Path | None:
    if not out_dir.exists():
        return None
    chat_id = event_source.metadata.get("chat_id")
    sender_id = event_source.metadata.get("sender_id")
    for checkpoint_path in sorted(out_dir.glob("*/checkpoint.json")):
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if checkpoint.get("status") != "awaiting_reject_reason":
            continue
        reviewer = checkpoint.get("reviewer") if isinstance(checkpoint.get("reviewer"), dict) else {}
        if reviewer.get("chat_id") == chat_id and reviewer.get("sender_id") == sender_id:
            return checkpoint_path.parent
    return None


def find_waiting_clarification_run(out_dir: Path, event_source: RequirementSource) -> Path | None:
    if not out_dir.exists():
        return None
    chat_id = event_source.metadata.get("chat_id")
    sender_id = event_source.metadata.get("sender_id")
    candidates: list[Path] = []
    for checkpoint_path in sorted(out_dir.glob("*/checkpoint.json")):
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if checkpoint.get("status") != "waiting_clarification":
            continue
        run_payload = load_run_payload(checkpoint_path.parent)
        trigger = run_payload.get("trigger") if isinstance(run_payload.get("trigger"), dict) else {}
        if trigger.get("chat_id") == chat_id and trigger.get("sender_id") == sender_id:
            candidates.append(checkpoint_path.parent)
    return candidates[-1] if candidates else None


def resume_from_clarification(
    event_source: RequirementSource,
    run_dir: Path,
    reply: ClarificationReply,
    *,
    reply_sender: ReplySender | None,
    card_reply_sender: CardReplySender | None,
) -> PipelineResult:
    run_payload = load_run_payload(run_dir)
    requirement_path = Path(run_payload["requirement_artifact"])
    requirement = load_requirement_artifact(requirement_path)
    open_questions = requirement.get("open_questions") if isinstance(requirement.get("open_questions"), list) else []

    if reply.action == "skip":
        for q in open_questions:
            if isinstance(q, dict) and "answer" not in q:
                q["answer"] = "__skipped__"
        requirement["quality"]["ready_for_next_stage"] = True
        if "warnings" not in requirement["quality"]:
            requirement["quality"]["warnings"] = []
        requirement["quality"]["warnings"].append("用户跳过了需求澄清，部分问题未解答。")
    else:
        answered = False
        for q in open_questions:
            if isinstance(q, dict) and "answer" not in q:
                q["answer"] = reply.text or ""
                answered = True
                break
        if not answered:
            open_questions.append({"field": "user_supplement", "question": "用户补充说明", "answer": reply.text or ""})
            requirement["open_questions"] = open_questions
        quality = requirement.get("quality") if isinstance(requirement.get("quality"), dict) else {}
        all_answered = all(
            isinstance(q, dict) and q.get("answer")
            for q in open_questions
            if isinstance(q, dict)
        )
        if all_answered:
            quality["ready_for_next_stage"] = True
            quality["ambiguity_score"] = 0.0
        else:
            quality["ready_for_next_stage"] = True
            quality["ambiguity_score"] = round(min(1.0, sum(1 for q in open_questions if isinstance(q, dict) and not q.get("answer")) / max(len(open_questions), 1)), 2)

    requirement_path.write_text(
        json.dumps(requirement, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checkpoint = load_checkpoint(run_dir)
    checkpoint["status"] = "clarification_resolved"
    checkpoint["clarification_reply"] = {"action": reply.action, "text": reply.text}
    checkpoint["updated_at"] = utc_now()
    write_checkpoint(run_dir, checkpoint)

    run_payload["status"] = "success"
    run_payload["checkpoint_artifact"] = str(run_dir / "checkpoint.json")
    run_payload["checkpoint_status"] = checkpoint["status"]
    run_payload["ready_for_next_stage"] = True

    sender = send_bot_reply if reply_sender is None else reply_sender
    if sender is not None:
        try:
            if reply.action == "skip":
                sender(
                    event_source.source_id,
                    f"已跳过需求澄清，继续进入方案设计… 运行 ID：{run_payload['run_id']}",
                    _idempotency_key(run_payload["run_id"], "clarification-skip"),
                )
            else:
                sender(
                    event_source.source_id,
                    f"已收到澄清回复，继续进入方案设计… 运行 ID：{run_payload['run_id']}",
                    _idempotency_key(run_payload["run_id"], "clarification-answer"),
                )
        except LarkCliError:
            pass

    requirement_source = RequirementSource(
        source_type=event_source.source_type,
        source_id=event_source.source_id,
        reference=event_source.reference,
        title=event_source.title,
        content=event_source.content,
        identity=event_source.identity,
        metadata=event_source.metadata,
        attachments=event_source.attachments,
        embedded_resources=event_source.embedded_resources,
    )
    trace = RunTrace(run_payload["run_id"], run_dir)
    solution_path = maybe_run_solution_design(
        requirement,
        requirement_path,
        requirement_source,
        analyzer="llm",
        run_dir=run_dir,
        stages=run_payload["stages"],
        trace=trace,
        run_payload=run_payload,
        message_id=event_source.source_id,
        card_reply_sender=card_reply_sender,
    )
    if solution_path is not None:
        run_payload["solution_artifact"] = str(solution_path)
    write_json(run_dir / "run.json", run_payload)

    return PipelineResult(
        run_id=run_payload["run_id"],
        status=run_payload.get("status", "success"),
        run_dir=run_dir,
        run_path=run_dir / "run.json",
        requirement_path=requirement_path,
        solution_path=Path(run_payload["solution_artifact"]) if run_payload.get("solution_artifact") else None,
    )


def find_blocked_workspace_run(out_dir: Path, event_source: RequirementSource) -> Path | None:
    if not is_workspace_resume_reply(event_source.content):
        return None
    chat_id = event_source.metadata.get("chat_id")
    sender_id = event_source.metadata.get("sender_id")
    candidates: list[Path] = []
    for checkpoint_path in sorted(out_dir.glob("*/checkpoint.json")):
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
            run_payload = load_run_payload(checkpoint_path.parent)
        except (OSError, json.JSONDecodeError):
            continue
        if checkpoint.get("status") != "blocked":
            continue
        trigger = run_payload.get("trigger") if isinstance(run_payload.get("trigger"), dict) else {}
        if trigger.get("chat_id") == chat_id and trigger.get("sender_id") == sender_id:
            candidates.append(checkpoint_path.parent)
    return candidates[-1] if candidates else None


def is_workspace_resume_reply(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return len(lines) == 1 and parse_workspace_directive(lines[0]) is not None


def workspace_from_previous_solution(checkpoint: dict[str, Any]) -> dict[str, Any] | None:
    history = checkpoint.get("artifact_history")
    if not isinstance(history, list):
        return None
    for item in reversed(history):
        if not isinstance(item, dict) or not item.get("solution_path"):
            continue
        try:
            payload = json.loads(Path(item["solution_path"]).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        workspace = payload.get("workspace")
        if isinstance(workspace, dict) and workspace.get("path"):
            return workspace
    return None


def requirement_with_review_feedback(requirement: dict[str, Any], reason: str) -> dict[str, Any]:
    payload = json.loads(json.dumps(requirement, ensure_ascii=False))
    open_questions = payload.get("open_questions")
    if not isinstance(open_questions, list):
        open_questions = []
    open_questions.append(
        {
            "field": "solution_review_reject_reason",
            "question": f"请根据上一版技术方案的 Reject 理由重做方案：{reason}",
        }
    )
    payload["open_questions"] = open_questions
    return payload


def _with_solution_audit(audit: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    response_path = run_dir / "solution-llm-response.json"
    request_path = run_dir / "solution-llm-request.json"
    if not response_path.exists():
        return audit
    try:
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return audit
    audit["solution_llm"] = {
        "request_path": str(request_path),
        "response_path": str(response_path),
        "token_usage": response_payload.get("usage"),
        "usage_source": response_payload.get("usage_source", "missing"),
        "duration_ms": response_payload.get("duration_ms"),
    }
    return audit


def build_welcome_card(*, workspace_root: str = "", default_repo: str = "") -> dict[str, Any]:
    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "**简介**：DevFlow 是一个 AI 驱动的开发流水线引擎。发送需求描述，即可自动完成需求分析、方案设计、代码生成、测试、评审和交付。",
            },
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    "**输入示例**\n"
                    "• 直接描述需求：`创建一个俄罗斯方块小游戏`\n"
                    "• 发送飞书文档链接\n"
                    "• 指定仓库：`仓库：D:\\path\\to\\repo`\n"
                    "• 新建项目：`新项目：snake-game`"
                ),
            },
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    "**可用命令**\n"
                    "• `/help` — 查看使用指引\n"
                    "• `/status` — 查询当前运行状态\n"
                    "• `Approve <运行ID>` — 同意技术方案\n"
                    "• `Reject <运行ID>` — 拒绝技术方案"
                ),
            },
        },
    ]
    if workspace_root or default_repo:
        config_lines: list[str] = []
        if workspace_root:
            config_lines.append(f"• 工作区根目录：`{workspace_root}`")
        if default_repo:
            config_lines.append(f"• 默认仓库：`{default_repo}`")
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**工作区配置**\n" + "\n".join(config_lines),
                },
            }
        )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "🤖 DevFlow 已就绪"},
        },
        "elements": elements,
    }


def build_welcome_text(*, workspace_root: str = "", default_repo: str = "") -> str:
    """Build a plain text welcome message for Windows compatibility.

    Windows has command line length limitations that prevent sending long JSON
    content via --content parameter. This function creates a shorter text-only
    message that can be sent via --text parameter instead.
    """
    lines = [
        "🤖 DevFlow 已就绪",
        "",
        "【简介】",
        "DevFlow 是一个 AI 驱动的开发流水线引擎，让软件开发更高效、更智能。",
        "",
        "【核心能力】",
        "📋 需求分析 — 智能解析需求，生成结构化 PRD 文档",
        "🎨 方案设计 — 自动设计技术方案，包含架构和实现计划",
        "💻 代码生成 — 基于方案自动生成代码，支持多种语言",
        "🧪 测试生成 — 自动创建测试用例，确保代码质量",
        "🔍 代码评审 — AI 自动评审，发现潜在问题",
        "📦 交付打包 — 生成完整的交付物，包含变更记录",
        "",
        "【使用方法】",
        "直接发送需求描述，例如：",
        "• 创建一个俄罗斯方块小游戏，使用 HTML5 Canvas 实现",
        "• 帮我写一个 Python 爬虫，抓取豆瓣电影 Top250 信息",
        "• 设计一个用户登录系统，包含注册、登录、找回密码功能",
        "",
        "【支持的输入方式】",
        "📝 文字描述 — 直接输入需求文字",
        "🔗 飞书文档 — 发送飞书文档链接",
        "📁 本地仓库 — 指定已有项目：仓库：D:\\path\\to\\repo",
        "🆕 新建项目 — 创建新项目：新项目：snake-game",
        "",
        "【常用命令】",
        "• /help — 查看详细使用帮助",
        "• /status — 查询当前运行状态",
        "• Approve <运行ID> — 同意技术方案，进入代码生成",
        "• Reject <运行ID> — 拒绝技术方案，提供修改意见",
        "• 继续 / skip — 跳过需求澄清，继续下一步",
        "",
        "【工作流程】",
        "1️⃣ 发送需求 → 2️⃣ AI 分析 → 3️⃣ 方案确认 → 4️⃣ 代码生成 → 5️⃣ 测试验证 → 6️⃣ 交付完成",
        "",
        "💡 提示：需求描述越详细，生成的方案和质量就越好！",
    ]

    if workspace_root or default_repo:
        lines.append("")
        lines.append("【当前工作区配置】")
        if workspace_root:
            lines.append(f"📂 工作区根目录：{workspace_root}")
        if default_repo:
            lines.append(f"📁 默认仓库：{default_repo}")

    return "\n".join(lines)


def build_workspace_blocked_reply(run_payload: dict[str, Any]) -> str:
    blocked_reason = str(run_payload.get("checkpoint_blocked_reason") or "缺少仓库上下文。").strip()
    return "\n".join(
        [
            f"DevFlow 已完成需求分析，但技术方案已暂停：{blocked_reason} 请只回复一行继续：仓库：D:\\path\\to\\repo 或 新项目：snake-game。",
            "技术方案需要读取本机可访问的代码库上下文。",
            f"运行 ID：{run_payload['run_id']}",
            f"需求产物：{run_payload.get('requirement_artifact')}",
            "只回复一行即可继续，请复制其中一种格式：",
            "仓库：D:\\path\\to\\repo",
            "新项目：snake-game",
            "如果这是全新的网页、小游戏或工具，优先回复 `新项目：snake-game` 这类项目名。",
            "收到后我会继续生成技术方案和评审卡片。",
        ]
    )


def build_success_reply(run_payload: dict[str, Any]) -> str:
    ready = "是" if run_payload.get("ready_for_next_stage") else "否"
    lines = [
        "DevFlow 流水线已完成。",
        f"运行 ID：{run_payload['run_id']}",
        f"输入：{run_payload['detected_input']['kind']} ({run_payload['detected_input']['value']})",
        f"标题：{run_payload.get('requirement_title', '未命名需求')}",
        f"是否可进入下一阶段：{ready}",
        f"产物：{run_payload['requirement_artifact']}",
    ]
    publication = run_payload.get("publication")
    if isinstance(publication, dict) and publication.get("status") == "failed":
        lines.append("PRD 发布：失败，已记录到 run.json。")
        prd = publication.get("prd")
        if isinstance(prd, dict) and prd.get("document_id"):
            lines.append(f"PRD 文档 ID：{prd['document_id']}")
    if run_payload.get("solution_artifact"):
        lines.append(f"技术方案：{run_payload['solution_artifact']}")
    return "\n".join(lines)


_LLM_ERROR_KEYWORDS = ("LlmError", "api_key", "timeout")

_STAGE_RETRY_HINT = {
    "requirement_intake": "请修改后重新发送需求描述。",
    "solution_design": "请修改后重新发送需求描述。",
    "code_generation": "请修改后重新发送需求描述。",
    "test_generation": "请修改后重新发送需求描述。",
    "code_review": "请修改后重新发送需求描述。",
    "delivery": "请修改后重新发送需求描述。",
}


def _stage_failure_suggestion(stage_name: str, error_message: str) -> str:
    if stage_name == "requirement_intake":
        return "补充更具体的需求上下文后重新发送消息。"
    if stage_name == "solution_design":
        if any(kw in error_message for kw in _LLM_ERROR_KEYWORDS):
            return "检查 LLM 配置和 API Key 是否有效。"
        return "检查需求描述是否足够清晰，或尝试简化需求范围。"
    if stage_name == "code_generation":
        if "QualityGateError" in error_message:
            return "方案质量未通过门禁，可尝试 Reject 后重新设计方案。"
        return "检查需求描述是否足够清晰，或尝试简化需求范围。"
    if stage_name == "test_generation":
        return "检查项目测试框架配置是否正确。"
    if stage_name == "code_review":
        return "检查代码变更是否符合需求描述。"
    if stage_name == "delivery":
        return "检查工作区 Git 状态是否正常。"
    return "请检查错误信息后重试。"


def build_failure_reply(run_payload: dict[str, Any]) -> str:
    error = run_payload["error"]
    stage_name = error["stage"]
    display_name = STAGE_DISPLAY_NAMES.get(stage_name, stage_name)
    suggestion = _stage_failure_suggestion(stage_name, error["message"])
    retry_hint = _STAGE_RETRY_HINT.get(stage_name, "请修改后重新发送需求描述。")
    return (
        f"❌ {display_name} 失败：{error['message']}\n"
        f"💡 建议：{suggestion}\n"
        f"🔄 {retry_hint}\n"
        f"运行 ID：{run_payload['run_id']}\n"
        f"运行记录：{run_payload['run_path']}"
    )


def failure_hint(detected: DetectedInput) -> str:
    if detected.kind == "lark_doc":
        return "检查文档权限，并确认机器人可以访问该文档。"
    if detected.kind == "lark_message":
        return "检查 message id 是否正确，并确认机器人可以看到该消息。"
    return "补充更具体的需求上下文后，再重新发送消息。"


def new_run_id(source_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{slugify(source_id)}-{uuid4().hex[:8]}"


def initial_stages(stage_names: list[str] | None = None) -> list[dict[str, Any]]:
    names = stage_names or STAGE_NAMES
    return [{"name": name, "status": "pending"} for name in names]


def set_stage_status(
    stages: list[dict[str, Any]],
    name: str,
    status: str,
    *,
    started_at: str | None = None,
    ended_at: str | None = None,
    artifact: str | None = None,
    error: str | None = None,
) -> None:
    for stage in stages:
        if stage["name"] != name:
            continue
        stage["status"] = status
        if started_at is not None:
            stage["started_at"] = started_at
        if ended_at is not None:
            stage["ended_at"] = ended_at
        if artifact is not None:
            stage["artifact"] = artifact
        if error is not None:
            stage["error"] = error
        return
    raise ValueError(f"未知的流水线阶段：{name}。")


def stage_status(stages: list[dict[str, Any]], name: str) -> str | None:
    for stage in stages:
        if stage["name"] == name:
            return stage.get("status")
    return None


def base_run_payload(
    *,
    run_id: str,
    run_dir: Path,
    event_source: RequirementSource,
    detected: DetectedInput,
    started_at: str,
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    provider_override = os.environ.get("DEVFLOW_PROVIDER_OVERRIDE", "").strip()
    payload = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "running",
        "lifecycle_status": "running",
        "run_dir": str(run_dir),
        "run_path": str(run_dir / "run.json"),
        "started_at": started_at,
        "ended_at": None,
        "trigger": {
            "source_type": event_source.source_type,
            "message_id": event_source.source_id,
            "chat_id": event_source.metadata.get("chat_id"),
            "sender_id": event_source.metadata.get("sender_id"),
            "create_time": event_source.metadata.get("create_time"),
        },
        "detected_input": {
            "kind": detected.kind,
            "value": detected.value,
        },
        "stages": stages,
        "pipeline_config": resolve_pipeline_config(None),
        "graph_state": {"engine": "langgraph", "status": "running", "updated_at": started_at},
        "error": None,
        "publication": {
            "status": "pending",
            "prd": None,
            "card_reply": None,
            "error": None,
        },
    }
    if provider_override:
        payload["provider_override"] = provider_override
    return payload


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
