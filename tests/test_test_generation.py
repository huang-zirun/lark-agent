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
from devflow.test.agent import assess_test_validity, build_test_generation_artifact, write_test_diff, write_test_generation_artifact
from devflow.test.runners import detect_test_stack
from devflow.trace import RunTrace


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "test-generation"


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
        "testing_strategy": {
            "unit_tests": ["test add()"],
            "integration_tests": ["run unittest discovery"],
            "regression_tests": ["python -m unittest"],
        },
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
        "diff": "diff --git a/calculator.py b/calculator.py\n",
    }


class TestGenerationTests(unittest.TestCase):
    def test_detects_python_pytest_and_unittest_fallback(self) -> None:
        with temp_workspace() as workspace:
            (workspace / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
            (workspace / "tests").mkdir()

            stack = detect_test_stack(workspace)

            self.assertEqual(stack["language"], "python")
            self.assertEqual(stack["framework"], "pytest")
            self.assertEqual(stack["commands"][0]["command"], "uv run pytest")

        with temp_workspace() as workspace:
            (workspace / "tests").mkdir()

            stack = detect_test_stack(workspace)

            self.assertEqual(stack["language"], "python")
            self.assertEqual(stack["framework"], "unittest")
            self.assertEqual(stack["commands"][0]["command"], "uv run python -m unittest discover -s tests")

    def test_detects_js_and_java_test_commands_without_installing_dependencies(self) -> None:
        with temp_workspace() as workspace:
            (workspace / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "^1.0.0"}}),
                encoding="utf-8",
            )

            stack = detect_test_stack(workspace)

            self.assertEqual(stack["language"], "javascript")
            self.assertEqual(stack["framework"], "vitest")
            self.assertEqual(stack["commands"][0]["command"], "npm.cmd test")

        with temp_workspace() as workspace:
            (workspace / "pom.xml").write_text("<project></project>", encoding="utf-8")

            stack = detect_test_stack(workspace)

            self.assertEqual(stack["language"], "java")
            self.assertEqual(stack["framework"], "maven")
            self.assertEqual(stack["commands"][0]["command"], "mvn test")

    def test_detects_plain_html_workspace_as_javascript(self) -> None:
        with temp_workspace() as workspace:
            (workspace / "index.html").write_text("<script src=\"game.js\"></script>\n", encoding="utf-8")

            stack = detect_test_stack(workspace)

        self.assertEqual(stack["language"], "javascript")
        self.assertEqual(stack["framework"], "html-js")
        self.assertIn("commands", stack)

    def test_test_validity_rejects_copied_logic_without_production_reference(self) -> None:
        with temp_workspace() as workspace:
            (workspace / "index.html").write_text("<script>function moveSnake() { return true; }</script>\n", encoding="utf-8")
            test_path = workspace / "test" / "game.test.js"
            test_path.parent.mkdir()
            test_path.write_text(
                "// 从 index.html 提取的核心函数（为测试目的复制）\n"
                "function moveSnake() { return true; }\n"
                "require('assert').equal(moveSnake(), true);\n",
                encoding="utf-8",
            )

            validity = assess_test_validity(
                workspace,
                generated_tests=["test/game.test.js"],
                production_paths=["index.html"],
            )

        self.assertFalse(validity["proves_production_code"])
        self.assertIn("test/game.test.js", validity["generated_tests"])
        self.assertTrue(any("复制" in reason or "copy" in reason.lower() for reason in validity["reasons"]))

    def test_test_validity_accepts_import_or_html_execution_reference(self) -> None:
        with temp_workspace() as workspace:
            (workspace / "game.js").write_text("export function moveSnake() { return true; }\n", encoding="utf-8")
            test_path = workspace / "test" / "game.test.js"
            test_path.parent.mkdir()
            test_path.write_text(
                "const { moveSnake } = require('../game.js');\n"
                "require('assert').equal(moveSnake(), true);\n",
                encoding="utf-8",
            )

            validity = assess_test_validity(
                workspace,
                generated_tests=["test/game.test.js"],
                production_paths=["game.js"],
            )

        self.assertTrue(validity["proves_production_code"])
        self.assertEqual(validity["production_paths"], ["game.js"])

    def test_test_generation_agent_writes_tests_runs_command_and_returns_artifact(self) -> None:
        responses = [
            FakeLlmResponse(
                {
                    "action": "tool",
                    "tool": "write_file",
                    "input": {
                        "path": "tests/test_calculator.py",
                        "content": "import unittest\nfrom calculator import add\n\nclass CalculatorTests(unittest.TestCase):\n    def test_adds_numbers(self):\n        self.assertEqual(add(1, 2), 3)\n",
                    },
                }
            ),
            FakeLlmResponse(
                {
                    "action": "tool",
                    "tool": "powershell",
                    "input": {"command": "python -m unittest discover -s tests", "timeout_seconds": 30},
                }
            ),
            FakeLlmResponse(
                {
                    "action": "finish",
                    "summary": "已生成并执行单元测试。",
                    "generated_tests": ["tests/test_calculator.py"],
                    "warnings": [],
                }
            ),
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            (workspace / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            artifact = build_test_generation_artifact(
                requirement_payload(),
                solution_payload(workspace),
                code_generation_payload(workspace),
                LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                requirement_path=workspace / "requirement.json",
                solution_path=workspace / "solution.json",
                code_generation_path=workspace / "code-generation.json",
                opener=opener,
                stage_trace=RunTrace("run_test", workspace).stage("test_generation"),
            )

            self.assertEqual(artifact["schema_version"], "devflow.test_generation.v1")
            self.assertEqual(artifact["status"], "success")
            self.assertEqual(artifact["generated_tests"], ["tests/test_calculator.py"])
            self.assertEqual(artifact["test_commands"][0]["returncode"], 0)
            self.assertTrue(artifact["test_validity"]["proves_production_code"])
            self.assertTrue((workspace / "tests" / "test_calculator.py").exists())
            self.assertTrue((workspace / "test-llm-request-turn1.json").exists())
            self.assertTrue((workspace / "test-llm-response-turn1.json").exists())
            self.assertTrue((workspace / "test-llm-request-turn2.json").exists())
            self.assertTrue((workspace / "test-llm-response-turn2.json").exists())
            self.assertTrue((workspace / "test-llm-request-turn3.json").exists())
            self.assertTrue((workspace / "test-llm-response-turn3.json").exists())

    def test_cli_generates_tests_from_explicit_artifacts(self) -> None:
        responses = [
            FakeLlmResponse(
                {
                    "action": "finish",
                    "summary": "无需新增测试。",
                    "generated_tests": [],
                    "warnings": ["当前变更已有测试覆盖。"],
                }
            )
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            requirement_path = workspace / "requirement.json"
            solution_path = workspace / "solution.json"
            code_path = workspace / "code-generation.json"
            out_path = workspace / "test-generation.json"
            requirement_path.write_text(json.dumps(requirement_payload(), ensure_ascii=False), encoding="utf-8")
            solution_path.write_text(json.dumps(solution_payload(workspace), ensure_ascii=False), encoding="utf-8")
            code_path.write_text(json.dumps(code_generation_payload(workspace), ensure_ascii=False), encoding="utf-8")
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
                                "test",
                                "generate",
                                "--requirement",
                                str(requirement_path),
                                "--solution",
                                str(solution_path),
                                "--code-generation",
                                str(code_path),
                                "--out",
                                str(out_path),
                            ]
                        )

            self.assertEqual(exit_code, 0)
            self.assertTrue(out_path.exists())
            self.assertTrue(out_path.with_suffix(".diff").exists())
            self.assertIn(str(out_path), stdout.getvalue())

    def test_writes_artifact_and_diff_helpers(self) -> None:
        with temp_workspace() as workspace:
            artifact = {
                "schema_version": "devflow.test_generation.v1",
                "status": "success",
                "diff": "diff --git a/tests/test_sample.py b/tests/test_sample.py\n",
            }

            written = write_test_generation_artifact(artifact, workspace / "test-generation.json")
            diff_path = write_test_diff(artifact, workspace / "test.diff")

            self.assertEqual(written, workspace / "test-generation.json")
            self.assertEqual(diff_path.read_text(encoding="utf-8"), artifact["diff"])


if __name__ == "__main__":
    unittest.main()
