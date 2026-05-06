from __future__ import annotations

import unittest
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from devflow.config import ProjectEntry, WorkspaceConfig
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

    def test_project_entry_parsing(self) -> None:
        entry = ProjectEntry(
            name="api-server",
            path="workspaces/api-server",
            remote="https://github.com/org/api.git",
            description="API",
        )
        config = WorkspaceConfig(projects=(entry,))

        self.assertEqual(len(config.projects), 1)
        self.assertEqual(config.projects[0].name, "api-server")
        self.assertEqual(config.projects[0].path, "workspaces/api-server")
        self.assertEqual(config.projects[0].remote, "https://github.com/org/api.git")
        self.assertEqual(config.projects[0].description, "API")

    def test_resolve_by_project_name(self) -> None:
        with temp_dir() as temp_root:
            (Path(temp_root) / "api-server").mkdir()
            config = WorkspaceConfig(
                root=str(temp_root),
                projects=(ProjectEntry(name="api-server", path="api-server"),),
            )
            workspace = resolve_workspace(
                message_text="仓库：api-server", config=config,
            )

            self.assertEqual(workspace["source"], "project_config")
            self.assertEqual(workspace["project_name"], "api-server")
            self.assertEqual(
                Path(workspace["path"]).resolve(),
                (Path(temp_root) / "api-server").resolve(),
            )

    def test_project_name_fallback_to_path(self) -> None:
        with temp_dir() as temp_root:
            (Path(temp_root) / "real-dir").mkdir()
            config = WorkspaceConfig(root=str(temp_root), projects=())
            workspace = resolve_workspace(
                message_text="仓库：real-dir", config=config,
            )

            self.assertEqual(workspace["source"], "message_directive")

    def test_workspace_source_field(self) -> None:
        with temp_dir() as temp_root:
            existing_dir = Path(temp_root) / "repo"
            existing_dir.mkdir()

            ws_cli = resolve_workspace(
                repo_path=str(existing_dir), config=WorkspaceConfig(),
            )
            self.assertEqual(ws_cli["source"], "cli_argument")

            config_msg = WorkspaceConfig(root=str(temp_root))
            ws_msg = resolve_workspace(
                message_text=f"仓库：repo", config=config_msg,
            )
            self.assertEqual(ws_msg["source"], "message_directive")

            ws_default = resolve_workspace(
                config=WorkspaceConfig(default_repo=str(existing_dir)),
            )
            self.assertEqual(ws_default["source"], "default_repo")

            (Path(temp_root) / "proj-dir").mkdir()
            config_proj = WorkspaceConfig(
                root=str(temp_root),
                projects=(ProjectEntry(name="my-proj", path="proj-dir"),),
            )
            ws_proj = resolve_workspace(
                message_text="仓库：my-proj", config=config_proj,
            )
            self.assertEqual(ws_proj["source"], "project_config")

    def test_project_name_takes_priority_over_path(self) -> None:
        with temp_dir() as temp_root:
            (Path(temp_root) / "actual-dir").mkdir()
            config = WorkspaceConfig(
                root=str(temp_root),
                projects=(ProjectEntry(name="my-project", path="actual-dir"),),
            )
            workspace = resolve_workspace(
                message_text="仓库：my-project", config=config,
            )

            self.assertEqual(workspace["source"], "project_config")
            self.assertEqual(workspace["project_name"], "my-project")
            self.assertEqual(
                Path(workspace["path"]).resolve(),
                (Path(temp_root) / "actual-dir").resolve(),
            )

    def test_project_path_not_exists_raises_error(self) -> None:
        with temp_dir() as temp_root:
            config = WorkspaceConfig(
                root=str(temp_root),
                projects=(ProjectEntry(name="missing", path="nonexistent"),),
            )
            with self.assertRaises(WorkspaceError) as raised:
                resolve_workspace(
                    message_text="仓库：missing", config=config,
                )

            self.assertIn("missing", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
