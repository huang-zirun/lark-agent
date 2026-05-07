from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from devflow.config import LlmConfig
from devflow.cli import main
from devflow.code.agent import build_code_generation_artifact
from devflow.code.permissions import PermissionDenied, resolve_workspace_path, validate_powershell_command
from devflow.code.tools import CodeToolExecutor, capture_workspace_changes
from devflow.trace import RunTrace


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "code-generation"


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


def solution_payload(workspace: Path) -> dict:
    return {
        "schema_version": "devflow.solution_design.v1",
        "metadata": {"agent": "SolutionDesignArchitect"},
        "workspace": {
            "mode": "existing_path",
            "path": str(workspace),
            "project_name": workspace.name,
            "repo_url": "",
            "base_branch": "main",
            "writable": True,
        },
        "requirement_summary": {
            "title": "写入欢迎文案",
            "goals": ["创建一个欢迎文件"],
            "acceptance_criteria": [{"id": "AC-001", "criterion": "hello.txt 包含中文欢迎语"}],
        },
        "proposed_solution": {
            "summary": "创建 hello.txt",
            "data_flow": ["solution.json -> code-generation.json"],
            "implementation_steps": ["写入 hello.txt"],
        },
        "change_plan": [
            {"path": "hello.txt", "action": "create", "responsibility": "欢迎文案"}
        ],
        "quality": {"ready_for_code_generation": True},
    }


class CodeGenerationTests(unittest.TestCase):
    def test_workspace_path_rejects_escape(self) -> None:
        with temp_workspace() as temp_dir:
            root = temp_dir / "repo"
            root.mkdir()

            with self.assertRaises(PermissionDenied):
                resolve_workspace_path(root, "..\\outside.txt", must_exist=False)

    def test_powershell_validation_rejects_destructive_commands(self) -> None:
        with self.assertRaises(PermissionDenied):
            validate_powershell_command("Remove-Item -Recurse C:\\important")

    def test_file_tools_write_read_edit_and_record_events(self) -> None:
        with temp_workspace() as root:
            executor = CodeToolExecutor(root)

            write_result = executor.execute("write_file", {"path": "hello.txt", "content": "hello\n"})
            read_result = executor.execute("read_file", {"path": "hello.txt"})
            edit_result = executor.execute(
                "edit_file",
                {"path": "hello.txt", "old_string": "hello", "new_string": "你好"},
            )

            self.assertEqual(write_result["status"], "success")
            self.assertEqual(read_result["content"], "hello\n")
            self.assertEqual(edit_result["status"], "success")
            self.assertEqual((root / "hello.txt").read_text(encoding="utf-8"), "你好\n")
            self.assertEqual([event["tool"] for event in executor.events], ["write_file", "read_file", "edit_file"])

    def test_code_generation_agent_runs_tool_loop_and_writes_artifact(self) -> None:
        responses = [
            FakeLlmResponse({"action": "tool", "tool": "write_file", "input": {"path": "hello.txt", "content": "欢迎使用 DevFlow\n"}}),
            FakeLlmResponse({"action": "finish", "summary": "已创建欢迎文件", "changed_files": ["hello.txt"]}),
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            artifact = build_code_generation_artifact(
                solution_payload(workspace),
                LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                opener=opener,
                stage_trace=RunTrace("run_code", workspace).stage("code_generation"),
            )

            self.assertEqual(artifact["schema_version"], "devflow.code_generation.v1")
            self.assertEqual(artifact["status"], "success")
            self.assertEqual(artifact["changed_files"], ["hello.txt"])
            self.assertTrue((workspace / "hello.txt").exists())
            self.assertEqual(artifact["tool_events"][0]["tool"], "write_file")
            self.assertTrue((workspace / "code-llm-request-turn1.json").exists())
            self.assertTrue((workspace / "code-llm-response-turn1.json").exists())
            self.assertTrue((workspace / "code-llm-request-turn2.json").exists())
            self.assertTrue((workspace / "code-llm-response-turn2.json").exists())
            self.assertIn("workspace_changes", artifact)
            self.assertIn("hello.txt", artifact["workspace_changes"]["changed_files"])

    def test_workspace_change_capture_includes_untracked_text_and_excludes_runtime_dirs(self) -> None:
        with temp_workspace() as workspace:
            subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True, text=True)
            (workspace / "index.html").write_text("<canvas></canvas>\n", encoding="utf-8")
            (workspace / ".devflow-index").mkdir()
            (workspace / ".devflow-index" / "summary.json").write_text("{}", encoding="utf-8")

            changes = capture_workspace_changes(workspace)

        self.assertIn("index.html", changes["changed_files"])
        self.assertIn("index.html", changes["untracked_files"])
        self.assertNotIn(".devflow-index/summary.json", changes["changed_files"])
        self.assertIn("diff --git a/index.html b/index.html", changes["diff"])
        self.assertIn("+<canvas></canvas>", changes["diff"])

    def test_code_generation_compacts_tool_results_in_next_llm_turn(self) -> None:
        big_content = "A" * 5000
        responses = [
            FakeLlmResponse({"action": "tool", "tool": "write_file", "input": {"path": "big.txt", "content": big_content}}),
            FakeLlmResponse({"action": "finish", "summary": "已创建大文件", "changed_files": ["big.txt"]}),
        ]
        request_bodies: list[dict] = []

        def opener(request, timeout: int):
            request_bodies.append(json.loads(request.data.decode("utf-8")))
            return responses.pop(0)

        with temp_workspace() as workspace:
            artifact = build_code_generation_artifact(
                solution_payload(workspace),
                LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                opener=opener,
            )

        second_request = json.dumps(request_bodies[1], ensure_ascii=False)
        self.assertEqual(artifact["changed_files"], ["big.txt"])
        self.assertNotIn(big_content, second_request)
        self.assertIn("truncated", second_request)

    def test_cli_generates_code_from_solution_file(self) -> None:
        responses = [
            FakeLlmResponse({"action": "tool", "tool": "write_file", "input": {"path": "hello.txt", "content": "hello\n"}}),
            FakeLlmResponse({"action": "finish", "summary": "已创建欢迎文件", "changed_files": ["hello.txt"]}),
        ]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_workspace() as workspace:
            solution_path = workspace / "solution.json"
            out_path = workspace / "code-generation.json"
            solution_path.write_text(json.dumps(solution_payload(workspace), ensure_ascii=False), encoding="utf-8")
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
                        exit_code = main(["code", "generate", "--solution", str(solution_path), "--out", str(out_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(out_path.exists())
            self.assertIn(str(out_path), stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
