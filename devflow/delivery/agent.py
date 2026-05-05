from __future__ import annotations

import difflib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devflow.delivery.models import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION


REQUIREMENT_SCHEMA_VERSION = "devflow.requirement.v1"
SOLUTION_SCHEMA_VERSION = "devflow.solution_design.v1"
CODE_GENERATION_SCHEMA_VERSION = "devflow.code_generation.v1"
TEST_GENERATION_SCHEMA_VERSION = "devflow.test_generation.v1"
CODE_REVIEW_SCHEMA_VERSION = "devflow.code_review.v1"
CHECKPOINT_SCHEMA_VERSION = "devflow.checkpoint.v1"
MAX_UNTRACKED_PATCH_BYTES = 1024 * 1024


def build_delivery_artifact(
    run_payload: dict[str, Any],
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    test_generation: dict[str, Any],
    code_review: dict[str, Any],
    checkpoint: dict[str, Any],
    *,
    requirement_path: Path | str | None = None,
    solution_path: Path | str | None = None,
    code_generation_path: Path | str | None = None,
    test_generation_path: Path | str | None = None,
    code_review_path: Path | str | None = None,
    checkpoint_path: Path | str | None = None,
) -> dict[str, Any]:
    validate_delivery_inputs(requirement, solution, code_generation, test_generation, code_review, checkpoint)
    workspace = code_generation.get("workspace") if isinstance(code_generation.get("workspace"), dict) else solution.get("workspace")
    if not isinstance(workspace, dict) or not workspace.get("path"):
        raise ValueError("交付节点缺少 workspace.path。")
    workspace_root = Path(str(workspace["path"])).expanduser().resolve()
    git = collect_git_state(workspace_root)
    verification = build_verification(test_generation, code_review)
    change_summary = build_change_summary(requirement, solution, code_generation, test_generation, code_review)
    readiness = build_readiness(git, verification, code_review)

    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "agent": AGENT_NAME,
            "agent_version": AGENT_VERSION,
            "created_at": utc_now(),
            "run_id": str(run_payload.get("run_id") or checkpoint.get("run_id") or ""),
            "workspace": workspace,
        },
        "status": "success",
        "inputs": {
            "requirement_artifact": str(requirement_path or run_payload.get("requirement_artifact") or ""),
            "solution_artifact": str(solution_path or run_payload.get("solution_artifact") or ""),
            "code_generation_artifact": str(code_generation_path or run_payload.get("code_generation_artifact") or ""),
            "test_generation_artifact": str(test_generation_path or run_payload.get("test_generation_artifact") or ""),
            "code_review_artifact": str(code_review_path or run_payload.get("code_review_artifact") or ""),
            "checkpoint_artifact": str(checkpoint_path or run_payload.get("checkpoint_artifact") or ""),
        },
        "approval": {
            "stage": checkpoint.get("stage"),
            "status": checkpoint.get("status"),
            "decision": checkpoint.get("decision"),
            "reviewer": checkpoint.get("reviewer"),
            "approved_at": checkpoint.get("updated_at"),
        },
        "change_summary": change_summary,
        "verification": verification,
        "git": git,
        "readiness": readiness,
    }


def validate_delivery_inputs(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    test_generation: dict[str, Any],
    code_review: dict[str, Any],
    checkpoint: dict[str, Any],
) -> None:
    if not isinstance(requirement, dict) or requirement.get("schema_version") != REQUIREMENT_SCHEMA_VERSION:
        raise ValueError("需求产物 schema_version 必须是 devflow.requirement.v1。")
    if not isinstance(solution, dict) or solution.get("schema_version") != SOLUTION_SCHEMA_VERSION:
        raise ValueError("技术方案产物 schema_version 必须是 devflow.solution_design.v1。")
    if not isinstance(code_generation, dict) or code_generation.get("schema_version") != CODE_GENERATION_SCHEMA_VERSION:
        raise ValueError("代码生成产物 schema_version 必须是 devflow.code_generation.v1。")
    if code_generation.get("status") != "success":
        raise ValueError("代码生成产物必须是 success 状态。")
    if not isinstance(test_generation, dict) or test_generation.get("schema_version") != TEST_GENERATION_SCHEMA_VERSION:
        raise ValueError("测试生成产物 schema_version 必须是 devflow.test_generation.v1。")
    if test_generation.get("status") != "success":
        raise ValueError("测试生成产物必须是 success 状态。")
    if not isinstance(code_review, dict) or code_review.get("schema_version") != CODE_REVIEW_SCHEMA_VERSION:
        raise ValueError("代码评审产物 schema_version 必须是 devflow.code_review.v1。")
    if code_review.get("status") != "success":
        raise ValueError("代码评审产物必须是 success 状态。")
    if not isinstance(checkpoint, dict) or checkpoint.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("检查点产物 schema_version 必须是 devflow.checkpoint.v1。")
    if checkpoint.get("stage") != "code_review" or checkpoint.get("status") != "approved":
        raise ValueError("交付节点只能在 code_review 检查点 approved 后运行。")


def build_change_summary(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    test_generation: dict[str, Any],
    code_review: dict[str, Any],
) -> dict[str, Any]:
    normalized = requirement.get("normalized_requirement") if isinstance(requirement.get("normalized_requirement"), dict) else {}
    proposed = solution.get("proposed_solution") if isinstance(solution.get("proposed_solution"), dict) else {}
    diff_summary = code_review.get("diff_summary") if isinstance(code_review.get("diff_summary"), dict) else {}
    changed_files = _unique_texts(code_generation.get("changed_files"), diff_summary.get("changed_files"))
    return {
        "title": str(normalized.get("title") or "未命名需求"),
        "purpose": str(proposed.get("summary") or code_generation.get("summary") or ""),
        "major_changes": _text_list(code_generation.get("summary"))
        + _text_list(test_generation.get("summary"))
        + _text_list(code_review.get("summary")),
        "changed_files": changed_files,
        "reviewer_guide": changed_files[:10],
    }


def build_verification(test_generation: dict[str, Any], code_review: dict[str, Any]) -> dict[str, Any]:
    commands = test_generation.get("test_commands") if isinstance(test_generation.get("test_commands"), list) else []
    command_summaries: list[dict[str, Any]] = []
    failed = 0
    for command in commands:
        if not isinstance(command, dict):
            continue
        returncode = int(command.get("returncode") or 0)
        status = str(command.get("status") or "")
        if returncode != 0 or status == "failed":
            failed += 1
        command_summaries.append(
            {
                "command": str(command.get("command") or ""),
                "status": status,
                "returncode": returncode,
            }
        )
    gate = code_review.get("quality_gate") if isinstance(code_review.get("quality_gate"), dict) else {}
    return {
        "test_commands": command_summaries,
        "test_command_count": len(command_summaries),
        "failed_test_commands": failed,
        "generated_tests": _text_list(test_generation.get("generated_tests")),
        "code_review_status": str(code_review.get("review_status") or ""),
        "quality_gate_passed": bool(gate.get("passed")),
        "blocking_findings": int(gate.get("blocking_findings") or 0),
        "review_summary": str(code_review.get("summary") or ""),
    }


def collect_git_state(workspace_root: Path) -> dict[str, Any]:
    warnings: list[str] = []
    if not is_git_repo(workspace_root):
        return {
            "is_repo": False,
            "branch": "",
            "head": "",
            "status": [],
            "tracked_diff": "",
            "untracked_files": [],
            "untracked_patches": [],
            "diff_stat": {"files_changed": 0, "insertions": 0, "deletions": 0},
            "warnings": ["工作区不是 Git 仓库，交付包无法标记为可合并。"],
        }

    tracked_diff = git_output(workspace_root, "diff", "--no-ext-diff")
    status_output = git_output(workspace_root, "status", "--porcelain=v1")
    untracked_files = [line for line in git_output(workspace_root, "ls-files", "--others", "--exclude-standard").splitlines() if line.strip()]
    untracked_patches = build_untracked_patches(workspace_root, untracked_files, warnings)
    tracked_stat = git_numstat(workspace_root)
    untracked_insertions = sum(int(item.get("insertions") or 0) for item in untracked_patches)
    return {
        "is_repo": True,
        "branch": git_output(workspace_root, "rev-parse", "--abbrev-ref", "HEAD").strip(),
        "head": git_output(workspace_root, "rev-parse", "--verify", "HEAD").strip(),
        "status": parse_status(status_output),
        "tracked_diff": tracked_diff,
        "untracked_files": untracked_files,
        "untracked_patches": untracked_patches,
        "diff_stat": {
            "files_changed": tracked_stat["files_changed"] + len(untracked_patches),
            "insertions": tracked_stat["insertions"] + untracked_insertions,
            "deletions": tracked_stat["deletions"],
        },
        "warnings": warnings,
    }


def is_git_repo(workspace_root: Path) -> bool:
    if not (workspace_root / ".git").exists():
        return False
    completed = run_git(workspace_root, "rev-parse", "--is-inside-work-tree")
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def git_output(workspace_root: Path, *args: str) -> str:
    completed = run_git(workspace_root, *args)
    return completed.stdout if completed.returncode == 0 else ""


def run_git(workspace_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=workspace_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )


def git_numstat(workspace_root: Path) -> dict[str, int]:
    output = git_output(workspace_root, "diff", "--numstat")
    files_changed = 0
    insertions = 0
    deletions = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        files_changed += 1
        if parts[0].isdigit():
            insertions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])
    return {"files_changed": files_changed, "insertions": insertions, "deletions": deletions}


def parse_status(output: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        entries.append({"status": line[:2].strip(), "path": line[3:].strip()})
    return entries


def build_untracked_patches(workspace_root: Path, files: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    patches: list[dict[str, Any]] = []
    for rel in files:
        path = (workspace_root / rel).resolve()
        try:
            if not path.is_file():
                continue
            data = path.read_bytes()
        except OSError as exc:
            warnings.append(f"未能读取未跟踪文件 {rel}：{exc}")
            continue
        if len(data) > MAX_UNTRACKED_PATCH_BYTES:
            warnings.append(f"未跟踪文件过大，未嵌入 patch：{rel}")
            continue
        if b"\0" in data[:8192]:
            warnings.append(f"未跟踪文件疑似二进制，未嵌入 patch：{rel}")
            continue
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            warnings.append(f"未跟踪文件不是 UTF-8 文本，未嵌入 patch：{rel}")
            continue
        patch = "".join(
            difflib.unified_diff(
                [],
                content.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
        patches.append(
            {
                "path": rel.replace("\\", "/"),
                "insertions": len(content.splitlines()),
                "patch": patch,
            }
        )
    return patches


def build_readiness(git: dict[str, Any], verification: dict[str, Any], code_review: dict[str, Any]) -> dict[str, Any]:
    warnings = list(git.get("warnings") if isinstance(git.get("warnings"), list) else [])
    gate = code_review.get("quality_gate") if isinstance(code_review.get("quality_gate"), dict) else {}
    if int(verification.get("failed_test_commands") or 0) > 0:
        warnings.append("存在失败的测试命令，建议修复后再合并。")
    if int(verification.get("blocking_findings") or 0) > 0:
        warnings.append("代码评审仍有阻塞问题，建议修复后再合并。")
    if code_review.get("review_status") != "passed" or gate.get("passed") is not True:
        warnings.append("代码评审未完全通过。")
    ready = (
        bool(git.get("is_repo"))
        and int(verification.get("failed_test_commands") or 0) == 0
        and int(verification.get("blocking_findings") or 0) == 0
        and code_review.get("review_status") == "passed"
        and gate.get("passed") is True
    )
    return {
        "ready_to_merge": ready,
        "risk_level": str(gate.get("risk_level") or ("low" if ready else "medium")),
        "warnings": _unique_texts(warnings),
    }


def delivery_diff(artifact: dict[str, Any]) -> str:
    git = artifact.get("git") if isinstance(artifact.get("git"), dict) else {}
    parts = []
    tracked = str(git.get("tracked_diff") or "")
    if tracked:
        parts.append(tracked.rstrip() + "\n")
    for item in git.get("untracked_patches") if isinstance(git.get("untracked_patches"), list) else []:
        if isinstance(item, dict) and item.get("patch"):
            parts.append(str(item["patch"]).rstrip() + "\n")
    return "\n".join(parts)


def write_delivery_artifact(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def write_delivery_diff(artifact: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(delivery_diff(artifact), encoding="utf-8")
    return out_path


def load_delivery_artifact(path: Path | str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("交付产物 schema_version 必须是 devflow.delivery.v1。")
    return payload


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def _unique_texts(*values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        for item in _text_list(value):
            if item not in result:
                result.append(item)
    return result
