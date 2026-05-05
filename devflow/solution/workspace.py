from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devflow.config import ReferenceConfig, SemanticConfig, WorkspaceConfig


EXCLUDED_DIRECTORIES = [
    ".git",
    ".venv",
    "node_modules",
    "artifacts",
    ".test-tmp",
    "__pycache__",
    "claw-code-main",
]
TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".toml",
    ".json",
    ".txt",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
}


class WorkspaceError(ValueError):
    """Raised when a workspace cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class WorkspaceDirective:
    mode: str
    value: str


def parse_workspace_directive(text: str) -> WorkspaceDirective | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        new_project = re.match(r"^(?:新建项目|新项目|project)\s*[:：]\s*(.+)$", stripped, re.IGNORECASE)
        if new_project is not None:
            return WorkspaceDirective("new_project", _clean_value(new_project.group(1)))
        repo = re.match(r"^(?:仓库|代码库|repo|repository)\s*[:：]\s*(.+)$", stripped, re.IGNORECASE)
        if repo is not None:
            return WorkspaceDirective("existing_path", _clean_value(repo.group(1)))
    return None


def resolve_workspace(
    *,
    repo_path: str | None = None,
    new_project: str | None = None,
    message_text: str | None = None,
    config: WorkspaceConfig | None = None,
) -> dict[str, Any]:
    workspace_config = config or WorkspaceConfig()
    if message_text and not repo_path and not new_project:
        directive = parse_workspace_directive(message_text)
        if directive is not None and directive.mode == "existing_path":
            repo_path = directive.value
        elif directive is not None and directive.mode == "new_project":
            new_project = directive.value

    if not repo_path and not new_project and workspace_config.default_repo:
        repo_path = workspace_config.default_repo

    if new_project:
        return _resolve_new_project(new_project, workspace_config)
    if repo_path:
        return _resolve_existing_path(repo_path, workspace_config)
    raise WorkspaceError("缺少仓库上下文：请提供 --repo、--new-project、机器人消息中的“仓库：...”或 workspace.default_repo。")


def build_codebase_context(
    root: Path | str,
    *,
    max_files: int = 60,
    max_chars_per_file: int = 2000,
    max_total_chars: int = 20000,
    semantic_config: SemanticConfig | None = None,
    reference_config: ReferenceConfig | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    files: list[dict[str, Any]] = []
    tree: list[str] = []
    total_chars = 0
    excluded_seen: set[str] = set()

    for current_root, dir_names, file_names in os.walk(root_path):
        dir_names[:] = [
            name
            for name in dir_names
            if not _exclude_dir(name, excluded_seen)
        ]
        for file_name in sorted(file_names):
            path = Path(current_root) / file_name
            rel_path = _relative_posix(path, root_path)
            tree.append(rel_path)
            if len(files) >= max_files or total_chars >= max_total_chars:
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            snippet = content[:max_chars_per_file]
            total_chars += len(snippet)
            files.append(
                {
                    "path": rel_path,
                    "character_count": len(content),
                    "summary": _summarize(content, 240),
                    "content": snippet,
                }
            )

    semantic_summary: dict[str, Any] = {"status": "disabled"}
    semantic_symbols: list[dict[str, Any]] = []
    semantic_relations_count: dict[str, int] = {}

    effective_config = semantic_config or SemanticConfig()
    if effective_config.enabled:
        try:
            from devflow.semantic.indexer import SemanticIndexer
            from devflow.semantic.query import SemanticQueryEngine

            indexer = SemanticIndexer(root_path, effective_config)
            indexer.build_index()

            engine = SemanticQueryEngine(root_path)
            engine.load_index()

            if engine.is_loaded():
                summary_data = engine.get_summary()
                semantic_summary = summary_data
                semantic_symbols = engine.get_top_level_symbols()
                rel_counts = summary_data.get("relation_type_counts", {})
                semantic_relations_count = rel_counts
            else:
                semantic_summary = {"status": "unavailable", "error": "索引构建后无法加载"}
        except Exception as exc:
            semantic_summary = {"status": "unavailable", "error": str(exc)}

    reference_documents: list[dict[str, Any]] = []
    effective_ref_config = reference_config or ReferenceConfig()
    if effective_ref_config.enabled:
        try:
            from devflow.references.registry import ReferenceRegistry

            registry = ReferenceRegistry()
            reference_documents = registry.get_documents_for_stage(
                "solution_design",
                max_total_chars=effective_ref_config.max_chars_per_stage,
            )
        except Exception:
            reference_documents = []

    return {
        "root": str(root_path),
        "excluded_directories": EXCLUDED_DIRECTORIES,
        "excluded_seen": sorted(excluded_seen),
        "file_count": len(tree),
        "included_file_count": len(files),
        "context_character_count": total_chars,
        "tree": tree[:200],
        "files": files,
        "semantic_summary": semantic_summary,
        "semantic_symbols": semantic_symbols,
        "semantic_relations_count": semantic_relations_count,
        "reference_documents": reference_documents,
    }


def _resolve_new_project(project_name: str, config: WorkspaceConfig) -> dict[str, Any]:
    cleaned = _safe_project_name(project_name)
    if not config.root:
        raise WorkspaceError("新建项目需要先配置 workspace.root。")
    root = Path(config.root).expanduser().resolve()
    project_path = (root / cleaned).resolve()
    _ensure_inside_root(project_path, root)
    project_path.mkdir(parents=True, exist_ok=True)
    _init_git(project_path)
    return _workspace_payload("new_project", project_path, project_name=cleaned, writable=True)


def _resolve_existing_path(repo_path: str, config: WorkspaceConfig) -> dict[str, Any]:
    path = Path(repo_path).expanduser()
    if not path.is_absolute() and config.root:
        path = Path(config.root) / path
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise WorkspaceError(f"仓库路径不存在或不是文件夹：{resolved}。")
    if config.root:
        _ensure_inside_root(resolved, Path(config.root).expanduser().resolve())
    return _workspace_payload("existing_path", resolved, project_name=resolved.name, writable=True)


def _workspace_payload(
    mode: str,
    path: Path,
    *,
    project_name: str,
    writable: bool,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "path": str(path),
        "project_name": project_name,
        "repo_url": "",
        "base_branch": "main",
        "writable": writable,
    }


def _ensure_inside_root(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(f"仓库路径必须位于 workspace.root 内：{root}。") from exc


def _init_git(path: Path) -> None:
    if (path / ".git").exists():
        return
    try:
        subprocess.run(
            ["git", "init"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkspaceError(f"新项目目录已创建，但 git init 失败：{path}。") from exc


def _exclude_dir(name: str, excluded_seen: set[str]) -> bool:
    if name in EXCLUDED_DIRECTORIES:
        excluded_seen.add(name)
        return True
    return False


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _clean_value(value: str) -> str:
    return value.strip().strip("\"'")


def _safe_project_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise WorkspaceError("新建项目名称不能为空。")
    return cleaned[:80]


def _summarize(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."
