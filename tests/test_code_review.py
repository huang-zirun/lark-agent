from __future__ import annotations

import json
import shutil
import unittest
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from devflow.cli import main
from devflow.config import LlmConfig
from devflow.review.agent import build_code_review_artifact, write_code_review_artifact
from devflow.review.render import render_code_review_markdown
from devflow.review.tools import ReviewToolExecutor
from devflow.trace import RunTrace


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "code-review"


@contextmanager
def temp_workspace():
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / f"workspace-{len(list(TEST_TMP_ROOT.glob('workspace-*'))) + 1}"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir()
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


class FakeLlmResponse:
    def __init__(self, content: dict) -> None:
        self.payload = {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def requirement_payload() -> dict:
    return {
        "schema_version": "devflow.requirement.v1",
        "normalized_requirement": {"title": "Add calculator", "goals": ["Support addition"]},
        "acceptance_criteria": [{"id": "AC-001", "criterion": "add(1, 2) returns 3"}],
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
        "requirement_summary": {"title": "Add calculator"},
        "proposed_solution": {"summary": "Create calculator.py with add()."},
        "change_plan": [{"path": "calculator.py", "action": "create", "responsibility": "addition"}],
        "testing_strategy": {"unit_tests": ["test add()"]},
        "quality": {"ready_for_code_generation": True},
    }


def code_generation_payload(workspace: Path) -> dict:
    return {
        "schema_version": "devflow.code_generation.v1",
        "status": "success",
        "workspace": solution_payload(workspace)["workspace"],
        "solution_summary": {"title": "Add calculator", "summary": "Create calculator.py"},
        "changed_files": ["calculator.py"],
        "summary": "已生成 calculator.py。",
        "warnings": [],
        "tool_events": [],
        "diff": "diff --git a/calculator.py b/calculator.py\n+def add(a, b):\n+    return a + b\n",
    }


def review_test_artifact_payload(workspace: Path, *, returncode: int = 0) -> dict:
    return {
        "schema_version": "devflow.test_generation.v1",
        "status": "success",
        "workspace": solution_payload(workspace)["workspace"],
        "inputs": {},
        "detected_stack": {"language": "python", "framework": "pytest", "commands": []},
        "generated_tests": ["tests/test_calculator.py"],
        "test_commands": [
            {
                "command": "uv run pytest",
                "status": "success" if returncode == 0 else "failed",
                "returncode": returncode,
                "stdout": "passed" if returncode == 0 else "",
                "stderr": "" if returncode == 0 else "failed",
            }
        ],
        "summary": "已生成并执行测试。",
        "warnings": [],
        "tool_events": [],
        "diff": "diff --git a/tests/test_calculator.py b/tests/test_calculator.py\n",
        "test_validity": {
            "proves_production_code": True,
            "reasons": [],
            "production_paths": ["calculator.py"],
            "generated_tests": ["tests/test_calculator.py"],
        },
    }


class CodeReviewTests(unittest.TestCase):
    def test_review_tools_are_read_only(self) -> None:
        with temp_workspace() as workspace:
            (workspace / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            executor = ReviewToolExecutor(workspace)

            read = executor.execute("read_file", {"path": "calculator.py"})

            self.assertIn("return a + b", read["content"])
            with self.assertRaises(ValueError):
                executor.execute("write_file", {"path": "bad.py", "content": "x = 1\n"})

    def test_code_review_agent_returns_passed_artifact(self) -> None:
        responses = [
            FakeLlmResponse(
                {
                    "action": "finish",
                    "review_status": "passed",
                    "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"},
                    "findings": [],
                    "repair_recommendations": [],
                    "summary": "变更与需求一致，测试已覆盖核心路径。",
                    "warnings": [],
                }
            )
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            (workspace / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            artifact = build_code_review_artifact(
                requirement_payload(),
                solution_payload(workspace),
                code_generation_payload(workspace),
                review_test_artifact_payload(workspace),
                LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                opener=opener,
                stage_trace=RunTrace("run_review", workspace).stage("code_review"),
            )

            self.assertEqual(artifact["schema_version"], "devflow.code_review.v1")
            self.assertEqual(artifact["review_status"], "passed")
            self.assertTrue(artifact["quality_gate"]["passed"])
            self.assertEqual(artifact["test_summary"]["failed_commands"], 0)
            self.assertTrue((workspace / "review-llm-request-turn1.json").exists())
            self.assertTrue((workspace / "review-llm-response-turn1.json").exists())

    def test_failed_test_command_becomes_blocking_review_evidence(self) -> None:
        responses = [
            FakeLlmResponse(
                {
                    "action": "finish",
                    "review_status": "passed",
                    "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"},
                    "findings": [],
                    "repair_recommendations": [],
                    "summary": "模型未发现问题。",
                    "warnings": [],
                }
            )
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            artifact = build_code_review_artifact(
                requirement_payload(),
                solution_payload(workspace),
                code_generation_payload(workspace),
                review_test_artifact_payload(workspace, returncode=1),
                LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                opener=opener,
            )

        self.assertEqual(artifact["review_status"], "needs_changes")
        self.assertFalse(artifact["quality_gate"]["passed"])
        self.assertEqual(artifact["test_summary"]["failed_commands"], 1)
        self.assertTrue(any(finding["category"] == "tests" for finding in artifact["findings"]))

    def test_invalid_test_validity_blocks_review_even_if_commands_pass(self) -> None:
        responses = [
            FakeLlmResponse(
                {
                    "action": "finish",
                    "review_status": "passed",
                    "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"},
                    "findings": [],
                    "repair_recommendations": [],
                    "summary": "模型未发现问题。",
                    "warnings": [],
                }
            )
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            test_artifact = review_test_artifact_payload(workspace)
            test_artifact["test_validity"] = {
                "proves_production_code": False,
                "reasons": ["test/game.test.js 复制了生产函数，没有引用生产文件。"],
                "production_paths": ["index.html"],
                "generated_tests": ["test/game.test.js"],
            }
            artifact = build_code_review_artifact(
                requirement_payload(),
                solution_payload(workspace),
                code_generation_payload(workspace),
                test_artifact,
                LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                opener=opener,
            )

        self.assertEqual(artifact["review_status"], "needs_changes")
        self.assertFalse(artifact["quality_gate"]["passed"])
        self.assertTrue(any(finding["category"] == "tests" and finding["blocking"] for finding in artifact["findings"]))

    def test_render_markdown_and_cli_generate_review(self) -> None:
        responses = [
            FakeLlmResponse(
                {
                    "action": "finish",
                    "review_status": "passed",
                    "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"},
                    "findings": [],
                    "repair_recommendations": [],
                    "summary": "可以进入人工确认。",
                    "warnings": [],
                }
            )
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            requirement_path = workspace / "requirement.json"
            solution_path = workspace / "solution.json"
            code_path = workspace / "code-generation.json"
            test_path = workspace / "test-generation.json"
            out_path = workspace / "code-review.json"
            requirement_path.write_text(json.dumps(requirement_payload(), ensure_ascii=False), encoding="utf-8")
            solution_path.write_text(json.dumps(solution_payload(workspace), ensure_ascii=False), encoding="utf-8")
            code_path.write_text(json.dumps(code_generation_payload(workspace), ensure_ascii=False), encoding="utf-8")
            test_path.write_text(json.dumps(review_test_artifact_payload(workspace), ensure_ascii=False), encoding="utf-8")
            fake_config = type(
                "FakeConfig",
                (),
                {
                    "llm": LlmConfig(
                        provider="custom",
                        api_key="SECRET_VALUE",
                        model="test-model",
                        base_url="https://example.test/v1",
                    )
                },
            )()
            stdout = StringIO()

            with patch("devflow.cli.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=opener):
                    with patch("sys.stdout", stdout):
                        exit_code = main(
                            [
                                "review",
                                "generate",
                                "--requirement",
                                str(requirement_path),
                                "--solution",
                                str(solution_path),
                                "--code-generation",
                                str(code_path),
                                "--test-generation",
                                str(test_path),
                                "--out",
                                str(out_path),
                            ]
                        )

            artifact = json.loads(out_path.read_text(encoding="utf-8"))
            markdown = render_code_review_markdown(artifact, run_id="run_123")
            written = write_code_review_artifact(artifact, workspace / "copy.json")
            out_exists = out_path.exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(out_exists)
        self.assertEqual(written, workspace / "copy.json")
        self.assertIn(str(out_path), stdout.getvalue())
        self.assertIn("# 代码评审：run_123", markdown)
        self.assertIn("Approve run_123", markdown)
        self.assertIn("Reject run_123", markdown)


if __name__ == "__main__":
    unittest.main()
