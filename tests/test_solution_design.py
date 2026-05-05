from __future__ import annotations

import json
import unittest
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from devflow.cli import main
from devflow.config import DevflowConfig, LarkConfig, LlmConfig, WorkspaceConfig
from devflow.llm import LlmError
from devflow.solution.designer import (
    build_solution_design_artifact,
    build_solution_design_user_prompt,
    normalize_solution_design,
)
from devflow.solution.models import SCHEMA_VERSION


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


@contextmanager
def temp_dir():
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / f"solution-design-{uuid4().hex}"
    path.mkdir()
    yield str(path)


def requirement_artifact() -> dict:
    return {
        "schema_version": "devflow.requirement.v1",
        "metadata": {"agent": "ProductRequirementAnalyst"},
        "normalized_requirement": {
            "title": "方案设计节点",
            "goals": ["输出技术方案 JSON"],
            "scope": ["支持 CLI 和 start 流程"],
        },
        "acceptance_criteria": [
            {"id": "AC-001", "criterion": "能生成 devflow.solution_design.v1 JSON"}
        ],
        "open_questions": [{"field": "repo", "question": "目标仓库在哪里？"}],
        "quality": {"ready_for_next_stage": True},
    }


def llm_solution_payload() -> dict:
    return {
        "architecture_analysis": {
            "current_architecture": ["Python CLI 包含 pipeline 和 intake 模块。"],
            "related_modules": ["devflow.pipeline", "devflow.cli"],
            "constraints": ["保持标准库依赖。"],
            "reusable_patterns": ["RunTrace JSONL 审计。"],
        },
        "proposed_solution": {
            "summary": "新增 solution agent 并接入 start。",
            "data_flow": ["requirement.json -> solution.json"],
            "implementation_steps": ["新增 devflow.solution 包", "扩展 pipeline"],
        },
        "change_plan": [
            {"path": "devflow/solution/designer.py", "action": "create", "responsibility": "生成方案产物"}
        ],
        "api_design": {
            "cli": ["devflow design from-requirement --requirement ... --repo ... --out ..."],
            "python": ["build_solution_design_artifact(requirement, workspace, llm_config)"],
            "json_contracts": ["devflow.solution_design.v1"],
            "external": [],
        },
        "testing_strategy": {
            "unit_tests": ["workspace 解析和 LLM JSON 规范化"],
            "integration_tests": ["devflow start 写出 solution.json"],
            "acceptance_mapping": ["AC-001"],
            "regression_tests": ["完整 unittest"],
        },
        "risks_and_assumptions": {
            "risks": ["LLM 输出缺字段"],
            "assumptions": ["目标路径对运行机器可见"],
            "open_questions": ["是否需要审批 API"],
        },
        "human_review": {
            "status": "pending",
            "checklist": ["确认文件变更清单", "确认 API 合同"],
        },
        "quality": {
            "completeness_score": 0.86,
            "risk_level": "medium",
            "ready_for_code_generation": True,
            "warnings": [],
        },
    }


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class SolutionDesignTests(unittest.TestCase):
    def test_prompt_includes_requirement_and_codebase_context(self) -> None:
        prompt = build_solution_design_user_prompt(
            requirement_artifact(),
            {
                "mode": "existing_path",
                "path": "D:\\lark",
                "project_name": "",
                "repo_url": "",
                "base_branch": "main",
                "writable": True,
            },
            {
                "root": "D:\\lark",
                "files": [{"path": "devflow/pipeline.py", "summary": "pipeline stages"}],
                "tree": ["devflow/pipeline.py"],
            },
        )

        self.assertIn("方案设计节点", prompt)
        self.assertIn("devflow/pipeline.py", prompt)
        self.assertIn("devflow.solution_design.v1", prompt)
        self.assertIn("字段名必须保持英文", prompt)

    def test_build_solution_design_artifact_with_mocked_llm(self) -> None:
        seen = {}

        def opener(request, timeout: int):
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(
                {
                    "choices": [
                        {"message": {"content": json.dumps(llm_solution_payload(), ensure_ascii=False)}}
                    ],
                    "usage": {"total_tokens": 42},
                }
            )

        with temp_dir() as directory:
            root = Path(directory)
            (root / "devflow").mkdir()
            (root / "devflow" / "cli.py").write_text("def main(): pass\n", encoding="utf-8")
            artifact = build_solution_design_artifact(
                requirement_artifact(),
                {
                    "mode": "existing_path",
                    "path": str(root),
                    "project_name": "",
                    "repo_url": "",
                    "base_branch": "main",
                    "writable": True,
                },
                LlmConfig(
                    provider="custom",
                    api_key="SECRET_VALUE",
                    model="test-model",
                    base_url="https://example.test/v1",
                ),
                opener=opener,
            )

        self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)
        self.assertEqual(artifact["metadata"]["agent"], "SolutionDesignArchitect")
        self.assertEqual(artifact["workspace"]["mode"], "existing_path")
        self.assertEqual(artifact["change_plan"][0]["path"], "devflow/solution/designer.py")
        self.assertEqual(artifact["quality"]["risk_level"], "medium")
        self.assertIn("devflow.solution_design.v1", seen["body"]["messages"][0]["content"])

    def test_invalid_llm_solution_response_raises_chinese_error(self) -> None:
        def opener(request, timeout: int):
            return FakeResponse({"choices": [{"message": {"content": "{\"quality\":{}}"}}]})

        with temp_dir() as directory:
            root = Path(directory)
            with self.assertRaises(LlmError) as raised:
                build_solution_design_artifact(
                    requirement_artifact(),
                    {
                        "mode": "existing_path",
                        "path": str(root),
                        "project_name": "",
                        "repo_url": "",
                        "base_branch": "main",
                        "writable": True,
                    },
                    LlmConfig(
                        provider="custom",
                        api_key="SECRET_VALUE",
                        model="test-model",
                        base_url="https://example.test/v1",
                    ),
                    opener=opener,
                )

        self.assertIn("缺少必填字段", str(raised.exception))

    def test_normalizes_loose_llm_solution_sections_from_provider_response(self) -> None:
        payload = {
            "architecture_analysis": "Single-file HTML Canvas architecture with no external dependencies.",
            "proposed_solution": "Implement CSS and JavaScript inside index.html.",
            "change_plan": [
                {
                    "file_path": "/index.html",
                    "change_type": "add",
                    "description": "Add the standalone snake game file.",
                }
            ],
            "api_design": "No external API; only keyboard and button events.",
            "testing_strategy": "Verify offline loading, direction controls, collisions, and restart.",
            "risks_and_assumptions": {
                "assumptions": ["Classic snake rules are acceptable."],
                "risks": ["Older browser compatibility may need follow-up."],
            },
            "human_review": {
                "status": "pending",
                "review_items": ["Confirm UI style."],
            },
            "quality": {
                "risk_level": "low",
                "test_coverage": "Cover core gameplay.",
                "maintainability": "Keep script functions separated.",
            },
        }

        solution = normalize_solution_design(payload)

        self.assertEqual(solution["architecture_analysis"]["current_architecture"][0], payload["architecture_analysis"])
        self.assertEqual(solution["proposed_solution"]["summary"], payload["proposed_solution"])
        self.assertEqual(solution["change_plan"][0]["path"], "index.html")
        self.assertEqual(solution["change_plan"][0]["action"], "add")
        self.assertEqual(solution["api_design"]["external"][0], payload["api_design"])
        self.assertEqual(solution["testing_strategy"]["unit_tests"][0], payload["testing_strategy"])
        self.assertEqual(solution["human_review"]["checklist"], ["Confirm UI style."])
        self.assertEqual(solution["quality"]["risk_level"], "low")
        self.assertIn("Cover core gameplay.", solution["quality"]["warnings"])
        self.assertTrue(solution["quality"]["ready_for_code_generation"])

    def test_cli_design_from_requirement_writes_solution_json(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            workspace=WorkspaceConfig(root="", default_repo=""),
        )

        with temp_dir() as directory:
            root = Path(directory)
            requirement_path = root / "requirement.json"
            out_path = root / "solution.json"
            repo = root / "repo"
            repo.mkdir()
            requirement_path.write_text(json.dumps(requirement_artifact()), encoding="utf-8")
            with patch("devflow.cli.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", return_value=FakeResponse({"choices": [{"message": {"content": json.dumps(llm_solution_payload())}}]})):
                    with redirect_stdout(StringIO()):
                        exit_code = main(
                            [
                                "design",
                                "from-requirement",
                                "--requirement",
                                str(requirement_path),
                                "--repo",
                                str(repo),
                                "--out",
                                str(out_path),
                            ]
                        )

            artifact = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
