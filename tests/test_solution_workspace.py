from __future__ import annotations

import unittest
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from devflow.config import WorkspaceConfig
from devflow.solution.workspace import (
    WorkspaceError,
    build_codebase_context,
    parse_workspace_directive,
    resolve_workspace,
)


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


@contextmanager
def temp_dir():
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / f"solution-workspace-{uuid4().hex}"
    path.mkdir()
    yield str(path)


class SolutionWorkspaceTests(unittest.TestCase):
    def test_parse_bot_text_existing_repo_path(self) -> None:
        directive = parse_workspace_directive("需求：增加方案设计 agent\n仓库：D:\\lark")

        self.assertIsNotNone(directive)
        self.assertEqual(directive.mode, "existing_path")
        self.assertEqual(directive.value, "D:\\lark")

    def test_parse_bot_text_new_project(self) -> None:
        directive = parse_workspace_directive("需求：做一个新工具\n新建项目：smart-ticket")

        self.assertIsNotNone(directive)
        self.assertEqual(directive.mode, "new_project")
        self.assertEqual(directive.value, "smart-ticket")

    def test_new_project_resolves_inside_workspace_root_and_initializes_git(self) -> None:
        with temp_dir() as directory:
            root = Path(directory) / "workspaces"
            workspace = resolve_workspace(
                new_project="smart-ticket",
                config=WorkspaceConfig(root=str(root), default_repo=""),
            )

            self.assertEqual(workspace["mode"], "new_project")
            self.assertEqual(workspace["project_name"], "smart-ticket")
            self.assertTrue(Path(workspace["path"]).exists())
            self.assertTrue((Path(workspace["path"]) / ".git").exists())
            self.assertTrue(Path(workspace["path"]).is_relative_to(root.resolve()))

    def test_existing_path_outside_workspace_root_is_rejected(self) -> None:
        with temp_dir() as directory:
            root = Path(directory) / "allowed"
            outside = Path(directory) / "outside"
            outside.mkdir()

            with self.assertRaises(WorkspaceError) as raised:
                resolve_workspace(
                    repo_path=str(outside),
                    config=WorkspaceConfig(root=str(root), default_repo=""),
                )

        self.assertIn("workspace.root", str(raised.exception))

    def test_codebase_context_excludes_heavy_and_reference_directories(self) -> None:
        with temp_dir() as directory:
            root = Path(directory)
            (root / "devflow").mkdir()
            (root / "devflow" / "pipeline.py").write_text("STAGE_NAMES = []\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "huge.js").write_text("ignored\n", encoding="utf-8")
            (root / "claw-code-main").mkdir()
            (root / "claw-code-main" / "PROJECT_ANALYSIS.md").write_text("ignored\n", encoding="utf-8")

            context = build_codebase_context(root)

        files = [item["path"] for item in context["files"]]
        self.assertIn("devflow/pipeline.py", files)
        self.assertNotIn("node_modules/huge.js", files)
        self.assertNotIn("claw-code-main/PROJECT_ANALYSIS.md", files)
        self.assertIn("node_modules", context["excluded_directories"])
        self.assertIn("claw-code-main", context["excluded_directories"])


if __name__ == "__main__":
    unittest.main()
