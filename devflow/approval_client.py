from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devflow.config import ConfigError, load_config
from devflow.intake.lark_cli import LarkCliError, run_lark_cli_text


class ApprovalError(RuntimeError):
    """Raised when approval operations fail."""


@dataclass(frozen=True, slots=True)
class ApprovalInstanceResult:
    instance_code: str
    status: str
    decision: str | None = None
    reject_reason: str | None = None


def _run_lark_api(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a lark-cli api bare call and return the parsed JSON response."""
    args = ["api", method, path]
    if payload is not None:
        args.extend(["--data", json.dumps(payload, ensure_ascii=False)])
    try:
        stdout = run_lark_cli_text(args, timeout_seconds=120)
    except LarkCliError as exc:
        raise ApprovalError(f"API 调用失败：{exc}") from exc

    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ApprovalError(f"响应解析失败：{exc}") from exc

    if response.get("code") != 0:
        msg = response.get("msg", "未知错误")
        raise ApprovalError(f"API 错误：{msg} (code={response.get('code')})")

    return response.get("data") or {}


def ensure_approval_definition(
    approval_code_hint: str | None = None,
    user_open_id: str | None = None,
) -> str:
    """Ensure a Lark approval definition exists for DevFlow solution review.

    If approval_code_hint is provided and valid, return it directly.
    Otherwise, create a new external (third-party) approval definition
    via native OpenAPI and return its approval_code.

    The external approval definition does NOT require admin console setup.
    It is created programmatically and shows up in the user's approval app.
    """
    if approval_code_hint:
        # Validate the existing definition by querying it
        try:
            _run_lark_api("GET", f"/open-apis/approval/v4/approvals/{approval_code_hint}")
            return approval_code_hint
        except ApprovalError:
            pass  # Invalid or inaccessible, create a new one

    # Generate a stable custom approval code for DevFlow
    custom_code = approval_code_hint or "devflow-solution-review"

    i18n_key_name = f"@i18n@{uuid.uuid4().hex[:8]}"
    i18n_key_group = f"@i18n@{uuid.uuid4().hex[:8]}"

    payload: dict[str, Any] = {
        "approval_name": i18n_key_name,
        "approval_code": custom_code,
        "group_code": "devflow",
        "group_name": i18n_key_group,
        "external": {
            "support_pc": True,
            "support_mobile": True,
            "support_batch_read": False,
            "allow_batch_operate": False,
        },
        "viewers": [
            {
                "viewer_type": "TENANT",
            }
        ],
        "i18n_resources": [
            {
                "locale": "zh-CN",
                "is_default": True,
                "texts": [
                    {
                        "key": i18n_key_name,
                        "value": "DevFlow 技术方案评审",
                    },
                    {
                        "key": i18n_key_group,
                        "value": "DevFlow",
                    },
                ],
            }
        ],
    }

    data = _run_lark_api("POST", "/open-apis/approval/v4/external_approvals", payload)
    approval_code = data.get("approval_code")
    if not approval_code:
        raise ApprovalError("创建三方审批定义成功但未返回 approval_code。")
    return approval_code


def create_external_approval_instance(
    approval_code: str,
    user_open_id: str,
    run_id: str,
    summary: str,
    risk_level: str,
    solution_markdown_path: str,
) -> str:
    """Create a third-party approval instance and return its instance_id.

    Uses lark-cli api bare call for POST /open-apis/approval/v4/external_instances.
    """
    import time

    i18n_key_title = f"@i18n@{uuid.uuid4().hex[:8]}"
    i18n_key_summary = f"@i18n@{uuid.uuid4().hex[:8]}"
    i18n_key_risk = f"@i18n@{uuid.uuid4().hex[:8]}"
    i18n_key_doc = f"@i18n@{uuid.uuid4().hex[:8]}"
    i18n_key_task = f"@i18n@{uuid.uuid4().hex[:8]}"
    i18n_key_approve = f"@i18n@{uuid.uuid4().hex[:8]}"
    i18n_key_reject = f"@i18n@{uuid.uuid4().hex[:8]}"

    now_ms = str(int(time.time() * 1000))
    instance_id = f"devflow-{run_id}"

    payload: dict[str, Any] = {
        "approval_code": approval_code,
        "status": "PENDING",
        "instance_id": instance_id,
        "open_id": user_open_id,
        "start_time": now_ms,
        "end_time": "0",
        "update_time": now_ms,
        "display_method": "SIDEBAR",
        "update_mode": "REPLACE",
        "title": i18n_key_title,
        "form": [
            {"name": i18n_key_summary, "value": summary},
            {"name": i18n_key_risk, "value": f"风险等级：{risk_level}"},
            {"name": i18n_key_doc, "value": solution_markdown_path},
        ],
        "task_list": [
            {
                "task_id": f"task-{run_id}",
                "open_id": user_open_id,
                "title": i18n_key_task,
                "status": "PENDING",
                "create_time": now_ms,
                "end_time": "0",
                "update_time": now_ms,
                "links": {
                    "pc_link": "",
                    "mobile_link": "",
                },
                "action_configs": [
                    {
                        "action_type": "APPROVE",
                        "action_name": i18n_key_approve,
                        "is_need_reason": False,
                        "is_reason_required": False,
                    },
                    {
                        "action_type": "REJECT",
                        "action_name": i18n_key_reject,
                        "is_need_reason": True,
                        "is_reason_required": True,
                    },
                ],
                "display_method": "SIDEBAR",
            }
        ],
        "i18n_resources": [
            {
                "locale": "zh-CN",
                "is_default": True,
                "texts": [
                    {"key": i18n_key_title, "value": f"技术方案评审 - {run_id}"},
                    {"key": i18n_key_summary, "value": "方案摘要"},
                    {"key": i18n_key_risk, "value": "风险等级"},
                    {"key": i18n_key_doc, "value": "方案文档"},
                    {"key": i18n_key_task, "value": "请审批技术方案"},
                    {"key": i18n_key_approve, "value": "同意"},
                    {"key": i18n_key_reject, "value": "拒绝"},
                ],
            }
        ],
    }

    data = _run_lark_api("POST", "/open-apis/approval/v4/external_instances", payload)
    result = data.get("data") or {}
    returned_instance_id = result.get("instance_id")
    if not returned_instance_id:
        raise ApprovalError("同步三方审批实例成功但未返回 instance_id。")
    return returned_instance_id


def get_external_approval_instance(approval_code: str, instance_id: str) -> dict[str, Any]:
    """Fetch third-party approval instance detail.

    Uses lark-cli api bare call for GET /open-apis/approval/v4/external_instances/:instance_id
    with approval_code as query param.
    """
    return _run_lark_api(
        "GET",
        f"/open-apis/approval/v4/external_instances/{instance_id}?approval_code={approval_code}",
    )


def parse_external_approval_result(instance_detail: dict[str, Any]) -> ApprovalInstanceResult:
    """Parse external instance detail into a structured result."""
    instance_id = instance_detail.get("instance_id") or ""
    status = instance_detail.get("status") or "UNKNOWN"

    decision = None
    reject_reason = None

    if status == "APPROVED":
        decision = "approve"
    elif status == "REJECTED":
        decision = "reject"
        # Try to extract reason from task extra
        task_list = instance_detail.get("task_list") or []
        for task in task_list:
            if task.get("status") == "REJECTED":
                extra_str = task.get("extra") or "{}"
                try:
                    extra = json.loads(extra_str)
                except json.JSONDecodeError:
                    extra = {}
                reason = extra.get("complete_reason") or extra.get("reason") or ""
                if reason and reason != "rejected":
                    reject_reason = reason
                break

    return ApprovalInstanceResult(
        instance_code=instance_id,
        status=status,
        decision=decision,
        reject_reason=reject_reason,
    )


def update_external_approval_instance(
    approval_code: str,
    instance_id: str,
    status: str,
    reject_reason: str | None = None,
) -> None:
    """Update a third-party approval instance status.

    Called when the user has approved/rejected via IM command fallback
    to keep the external approval instance in sync.
    """
    import time

    now_ms = str(int(time.time() * 1000))
    payload: dict[str, Any] = {
        "approval_code": approval_code,
        "status": status,
        "instance_id": instance_id,
        "end_time": now_ms,
        "update_time": now_ms,
        "update_mode": "UPDATE",
        "task_list": [
            {
                "task_id": f"task-{instance_id}",
                "status": status,
                "end_time": now_ms,
                "update_time": now_ms,
            }
        ],
    }
    if reject_reason:
        payload["task_list"][0]["extra"] = json.dumps(
            {"complete_reason": "rejected", "reason": reject_reason},
            ensure_ascii=False,
        )

    _run_lark_api("POST", "/open-apis/approval/v4/external_instances", payload)


# Legacy native-approval helpers (kept for backward compatibility)

def create_approval_instance(
    approval_code: str,
    user_open_id: str,
    form: list[dict[str, Any]],
    *,
    title: str | None = None,
    uuid: str | None = None,
) -> str:
    """Create a Lark native approval instance and return its instance_code."""
    payload: dict[str, Any] = {
        "approval_code": approval_code,
        "open_id": user_open_id,
        "form": json.dumps(form, ensure_ascii=False),
        "locale": "zh-CN",
    }
    if title:
        payload["title"] = title
    if uuid:
        payload["uuid"] = uuid

    data = _run_lark_api("POST", "/open-apis/approval/v4/instances", payload)
    instance_code = data.get("instance_code")
    if not instance_code:
        raise ApprovalError("审批创建成功但未返回 instance_code。")
    return instance_code


def get_approval_instance(instance_code: str) -> dict[str, Any]:
    """Fetch native approval instance detail."""
    return _run_lark_api("GET", f"/open-apis/approval/v4/instances/{instance_code}")


def parse_approval_result(instance_detail: dict[str, Any]) -> ApprovalInstanceResult:
    """Parse native instance detail into a structured result."""
    instance_code = instance_detail.get("instance_code") or ""
    status = instance_detail.get("status") or "UNKNOWN"

    decision = None
    reject_reason = None

    if status == "APPROVED":
        decision = "approve"
    elif status == "REJECTED":
        decision = "reject"
        timeline = instance_detail.get("timeline") or []
        for record in reversed(timeline):
            if record.get("type") == "REJECT":
                comment = record.get("comment") or ""
                if comment:
                    reject_reason = comment
                break

    return ApprovalInstanceResult(
        instance_code=instance_code,
        status=status,
        decision=decision,
        reject_reason=reject_reason,
    )


def build_solution_review_form(
    run_id: str,
    summary: str,
    risk_level: str,
    solution_markdown_path: str,
) -> list[dict[str, Any]]:
    """Build approval form controls for a solution review."""
    return [
        {"id": "run_id", "type": "input", "value": run_id},
        {"id": "summary", "type": "textarea", "value": summary},
        {"id": "risk_level", "type": "input", "value": risk_level},
        {"id": "solution_doc", "type": "textarea", "value": solution_markdown_path},
    ]


def load_approval_config() -> dict[str, Any]:
    """Load approval-related config from config.json."""
    config = load_config()
    raw = json.loads(Path("config.json").read_text(encoding="utf-8-sig"))
    return raw.get("approval") or {}
