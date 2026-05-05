from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from uuid import uuid4

from devflow.cli import main
from devflow.delivery.agent import build_delivery_artifact, write_delivery_artifact, write_delivery_diff
from devflow.delivery.render import render_delivery_markdown


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "delivery"


def temp_dir(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / f"{name}-{uuid4().hex}"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def run_git(workspace: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=workspace, text=True, capture_output=True, check=True)


def init_git_workspace() -> Path:
    workspace = temp_dir("git-workspace")
    run_git(workspace, "init")
    run_git(workspace, "config", "user.email", "devflow@example.test")
    run_git(workspace, "config", "user.name", "DevFlow Test")
    (workspace / "app.py").write_text("def hello():\n    return 'old'\n", encoding="utf-8")
    run_git(workspace, "add", "app.py")
    run_git(workspace, "commit", "-m", "test: seed workspace")
    (workspace / "app.py").write_text("def hello():\n    return 'new'\n", encoding="utf-8")
    (workspace / "new_file.py").write_text("VALUE = 'created'\n", encoding="utf-8")
    return workspace


def requirement_payload() -> dict:
    return {
        "schema_version": "devflow.requirement.v1",
        "normalized_requirement": {"title": "Add delivery package", "goals": ["Produce a merge-ready package"]},
        "quality": {"ready_for_next_stage": True},
    }


def solution_payload(workspace: Path) -> dict:
    return {
        "schema_version": "devflow.solution_design.v1",
        "workspace": {
            "mode": "existing_path",
            "path": str(workspace),
            "project_name": workspace.name,
            "repo_url": "",
            "base_branch": "main",
            "writable": True,
        },
        "requirement_summary": {"title": "Add delivery package"},
        "proposed_solution": {"summary": "Generate final delivery artifacts."},
        "change_plan": [{"path": "app.py", "action": "modify", "responsibility": "delivery demo"}],
        "quality": {"ready_for_code_generation": True},
    }


def code_generation_payload(workspace: Path) -> dict:
    return {
        "schema_version": "devflow.code_generation.v1",
        "status": "success",
        "workspace": solution_payload(workspace)["workspace"],
        "solution_summary": {"title": "Add delivery package", "summary": "Generate final delivery artifacts."},
        "changed_files": ["app.py", "new_file.py"],
        "summary": "已生成代码变更。",
        "warnings": [],
        "tool_events": [],
        "diff": "diff --git a/app.py b/app.py\n",
    }


def generation_artifact_payload(workspace: Path, *, returncode: int = 0) -> dict:
    return {
        "schema_version": "devflow.test_generation.v1",
        "status": "success",
        "workspace": solution_payload(workspace)["workspace"],
        "inputs": {},
        "detected_stack": {"language": "python", "framework": "pytest", "commands": ["uv run pytest"]},
        "generated_tests": ["tests/test_app.py"],
        "test_commands": [
            {
                "command": "uv run pytest",
                "status": "success" if returncode == 0 else "failed",
                "returncode": returncode,
                "stdout": "1 passed" if returncode == 0 else "",
                "stderr": "" if returncode == 0 else "1 failed",
            }
        ],
        "summary": "已执行测试。",
        "warnings": [],
        "tool_events": [],
        "diff": "diff --git a/tests/test_app.py b/tests/test_app.py\n",
    }


def code_review_payload(workspace: Path, *, blocking: int = 0) -> dict:
    return {
        "schema_version": "devflow.code_review.v1",
        "status": "success",
        "workspace": solution_payload(workspace)["workspace"],
        "inputs": {},
        "review_status": "passed" if blocking == 0 else "needs_changes",
        "quality_gate": {"passed": blocking == 0, "blocking_findings": blocking, "risk_level": "low" if blocking == 0 else "high"},
        "findings": [],
        "test_summary": {"command_count": 1, "failed_commands": 0, "generated_tests": ["tests/test_app.py"]},
        "diff_summary": {"changed_files": ["app.py", "new_file.py"]},
        "repair_recommendations": [],
        "summary": "代码评审通过。" if blocking == 0 else "代码评审仍有阻塞问题。",
        "warnings": [],
        "tool_events": [],
        "prompt": {},
    }


def approved_checkpoint() -> dict:
    return {
        "schema_version": "devflow.checkpoint.v1",
        "run_id": "run_delivery",
        "stage": "code_review",
        "status": "approved",
        "attempt": 1,
        "reviewer": {"source": "test"},
        "decision": "approve",
        "reject_reason": None,
        "blocked_reason": None,
        "continue_requested": True,
        "artifact_history": [],
        "approval_instance_code": None,
        "updated_at": "2026-05-04T00:00:00Z",
    }


def run_payload(workspace: Path) -> dict:
    return {
        "schema_version": "devflow.pipeline_run.v1",
        "run_id": "run_delivery",
        "run_dir": str(workspace.parent),
        "stages": [{"name": name, "status": "success" if name != "delivery" else "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
    }


class DeliveryTests(unittest.TestCase):
    def test_delivery_collects_git_diff_status_and_untracked_text_patches(self) -> None:
        workspace = init_git_workspace()

        artifact = build_delivery_artifact(
            run_payload(workspace),
            requirement_payload(),
            solution_payload(workspace),
            code_generation_payload(workspace),
            generation_artifact_payload(workspace),
            code_review_payload(workspace),
            approved_checkpoint(),
        )

        self.assertEqual(artifact["schema_version"], "devflow.delivery.v1")
        self.assertTrue(artifact["readiness"]["ready_to_merge"])
        self.assertTrue(artifact["git"]["is_repo"])
        self.assertIn("app.py", artifact["git"]["tracked_diff"])
        self.assertIn("new_file.py", artifact["git"]["untracked_files"])
        self.assertIn("+VALUE = 'created'", artifact["git"]["untracked_patches"][0]["patch"])
        self.assertGreaterEqual(artifact["git"]["diff_stat"]["files_changed"], 2)

    def test_non_git_workspace_still_writes_package_but_not_ready_to_merge(self) -> None:
        workspace = temp_dir("plain-workspace")
        (workspace / "app.py").write_text("print('hello')\n", encoding="utf-8")

        artifact = build_delivery_artifact(
            run_payload(workspace),
            requirement_payload(),
            solution_payload(workspace),
            code_generation_payload(workspace),
            generation_artifact_payload(workspace),
            code_review_payload(workspace),
            approved_checkpoint(),
        )

        self.assertFalse(artifact["git"]["is_repo"])
        self.assertFalse(artifact["readiness"]["ready_to_merge"])
        self.assertTrue(any("Git" in warning for warning in artifact["readiness"]["warnings"]))

    def test_failed_verification_or_blocking_review_marks_delivery_not_ready(self) -> None:
        workspace = init_git_workspace()

        artifact = build_delivery_artifact(
            run_payload(workspace),
            requirement_payload(),
            solution_payload(workspace),
            code_generation_payload(workspace),
            generation_artifact_payload(workspace, returncode=1),
            code_review_payload(workspace, blocking=1),
            approved_checkpoint(),
        )

        self.assertFalse(artifact["readiness"]["ready_to_merge"])
        self.assertEqual(artifact["verification"]["failed_test_commands"], 1)
        self.assertEqual(artifact["verification"]["blocking_findings"], 1)

    def test_delivery_requires_approved_code_review_checkpoint(self) -> None:
        workspace = temp_dir("unapproved-workspace")
        checkpoint = approved_checkpoint()
        checkpoint["status"] = "waiting_approval"

        with self.assertRaises(ValueError):
            build_delivery_artifact(
                run_payload(workspace),
                requirement_payload(),
                solution_payload(workspace),
                code_generation_payload(workspace),
                generation_artifact_payload(workspace),
                code_review_payload(workspace),
                checkpoint,
            )

    def test_writes_delivery_artifacts_and_markdown(self) -> None:
        workspace = init_git_workspace()
        artifact = build_delivery_artifact(
            run_payload(workspace),
            requirement_payload(),
            solution_payload(workspace),
            code_generation_payload(workspace),
            generation_artifact_payload(workspace),
            code_review_payload(workspace),
            approved_checkpoint(),
        )
        out_dir = temp_dir("out")

        json_path = write_delivery_artifact(artifact, out_dir / "delivery.json")
        diff_path = write_delivery_diff(artifact, out_dir / "delivery.diff")
        markdown = render_delivery_markdown(artifact)

        self.assertTrue(json_path.exists())
        self.assertTrue(diff_path.exists())
        self.assertIn("# DevFlow 交付包", markdown)
        self.assertIn("Add delivery package", markdown)
        self.assertIn("app.py", diff_path.read_text(encoding="utf-8"))

    def test_cli_generates_delivery_from_run(self) -> None:
        workspace = init_git_workspace()
        out_dir = temp_dir("runs")
        run_id = "run_cli_delivery"
        run_dir = out_dir / run_id
        run_dir.mkdir()
        paths = {
            "requirement_artifact": run_dir / "requirement.json",
            "solution_artifact": run_dir / "solution.json",
            "code_generation_artifact": run_dir / "code-generation.json",
            "test_generation_artifact": run_dir / "test-generation.json",
            "code_review_artifact": run_dir / "code-review.json",
            "checkpoint_artifact": run_dir / "checkpoint.json",
        }
        payloads = [
            requirement_payload(),
            solution_payload(workspace),
            code_generation_payload(workspace),
            generation_artifact_payload(workspace),
            code_review_payload(workspace),
            approved_checkpoint(),
        ]
        for path, payload in zip(paths.values(), payloads, strict=True):
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        run_data = {
            "schema_version": "devflow.pipeline_run.v1",
            "run_id": run_id,
            "run_dir": str(run_dir),
            "stages": [{"name": name, "status": "success" if name != "delivery" else "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            **{key: str(value) for key, value in paths.items()},
        }
        (run_dir / "run.json").write_text(json.dumps(run_data, ensure_ascii=False), encoding="utf-8")

        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["delivery", "generate", "--run", run_id, "--out-dir", str(out_dir)])

        self.assertEqual(exit_code, 0)
        self.assertIn("delivery.json", stdout.getvalue())
        self.assertTrue((run_dir / "delivery.json").exists())
        self.assertTrue((run_dir / "delivery.md").exists())
        self.assertTrue((run_dir / "delivery.diff").exists())
