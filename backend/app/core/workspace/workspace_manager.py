import subprocess
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.workspace import Workspace, WorkspaceStatus
from app.models.pipeline import PipelineRun
from app.shared.config import settings
from app.shared.ids import generate_id
from app.shared.errors import PrecheckError, ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


def _validate_git_repo(path: str) -> bool:
    repo_path = Path(path)
    if not repo_path.exists():
        return False
    git_dir = repo_path / ".git"
    return git_dir.exists()


async def register_repo(session: AsyncSession, source_repo_path: str) -> Workspace:
    source_path = Path(source_repo_path).resolve()
    if not source_path.exists():
        raise PrecheckError(f"Path does not exist: {source_repo_path}")
    if not _validate_git_repo(str(source_path)):
        raise PrecheckError(f"Not a Git repository: {source_repo_path}")

    workspace_root = Path(settings.WORKSPACE_ROOT_PATH)
    workspace_root.mkdir(parents=True, exist_ok=True)

    workspace_path = workspace_root / f"ws_{generate_id()[:12]}"

    try:
        subprocess.run(
            ["git", "clone", str(source_path), str(workspace_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        raise ExecutionError(f"Git clone failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise ExecutionError("Git clone timed out")

    commit_hash = _get_current_commit(str(workspace_path))

    workspace = Workspace(
        id=generate_id(),
        run_id=None,
        source_repo_path=str(source_path),
        workspace_path=str(workspace_path),
        git_commit_at_create=commit_hash,
        status=WorkspaceStatus.ACTIVE,
    )
    session.add(workspace)
    await session.flush()
    logger.info(f"Registered workspace {workspace.id} from {source_repo_path}")
    return workspace


async def create_workspace_for_run(session: AsyncSession, run_id: str, base_workspace_id: str) -> Workspace:
    base_ws = await session.get(Workspace, base_workspace_id)
    if not base_ws:
        raise ExecutionError(f"Base workspace {base_workspace_id} not found")

    workspace_root = Path(settings.WORKSPACE_ROOT_PATH)
    workspace_path = workspace_root / f"run_{run_id[:12]}"

    try:
        subprocess.run(
            ["git", "clone", base_ws.source_repo_path, str(workspace_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        raise ExecutionError(f"Git clone for run failed: {e.stderr}")

    commit_hash = _get_current_commit(str(workspace_path))

    workspace = Workspace(
        id=generate_id(),
        run_id=run_id,
        source_repo_path=base_ws.source_repo_path,
        workspace_path=str(workspace_path),
        git_commit_at_create=commit_hash,
        status=WorkspaceStatus.ACTIVE,
    )
    session.add(workspace)

    run = await session.get(PipelineRun, run_id)
    if run:
        run.workspace_ref_id = workspace.id

    await session.flush()
    logger.info(f"Created workspace {workspace.id} for run {run_id}")
    return workspace


async def get_workspace(session: AsyncSession, workspace_id: str) -> Workspace | None:
    return await session.get(Workspace, workspace_id)


async def list_workspaces(session: AsyncSession) -> list[Workspace]:
    result = await session.execute(
        select(Workspace).order_by(Workspace.created_at.desc())
    )
    return list(result.scalars().all())


async def archive_workspace(session: AsyncSession, workspace_id: str) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if not workspace:
        raise ExecutionError(f"Workspace {workspace_id} not found")
    workspace.status = WorkspaceStatus.ARCHIVED
    await session.flush()
    return workspace


async def get_diff(session: AsyncSession, workspace_id: str) -> dict:
    workspace = await session.get(Workspace, workspace_id)
    if not workspace:
        raise ExecutionError(f"Workspace {workspace_id} not found")

    ws_path = Path(workspace.workspace_path)
    if not ws_path.exists():
        raise ExecutionError(f"Workspace directory not found: {ws_path}")

    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )
        diff_output = result.stdout

        stat_result = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )

        name_only_result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )
        changed_files = [f for f in name_only_result.stdout.strip().split("\n") if f]

    except subprocess.TimeoutExpired:
        raise ExecutionError("Git diff timed out")

    return {
        "workspace_id": workspace_id,
        "diff": diff_output,
        "changed_files": changed_files,
        "stats": _parse_diff_stats(stat_result.stdout),
    }


def _get_current_commit(repo_path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _parse_diff_stats(stat_output: str) -> dict:
    lines = stat_output.strip().split("\n")
    if not lines or not lines[-1]:
        return {"files_changed": 0, "insertions": 0, "deletions": 0}

    last_line = lines[-1]
    parts = last_line.split()
    try:
        files_changed = int(parts[0]) if parts else 0
        insertions = 0
        deletions = 0
        for part in parts[1:]:
            if part.startswith("+"):
                insertions += int(part[1:])
            elif part.startswith("-"):
                deletions += int(part[1:])
        return {"files_changed": files_changed, "insertions": insertions, "deletions": deletions}
    except (ValueError, IndexError):
        return {"files_changed": 0, "insertions": 0, "deletions": 0}


EXCLUDED_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".eggs", "*.egg-info", ".next", ".nuxt",
}

EXCLUDED_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".rar",
    ".db", ".sqlite", ".sqlite3",
}


def get_directory_tree(
    workspace_path: str,
    max_depth: int = 3,
    exclude_dirs: set[str] | None = None,
) -> dict:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        return {"root": str(ws_path), "tree": {}, "error": "workspace not found"}

    excludes = exclude_dirs or EXCLUDED_DIRS

    def _build_tree(path: Path, depth: int) -> dict | str:
        if depth > max_depth:
            return "..."

        if not path.exists():
            return ""

        if path.is_file():
            return f"[file] {path.name}"

        result = {}
        try:
            for child in sorted(path.iterdir()):
                if child.name in excludes:
                    continue
                if child.name.startswith(".") and child.name not in {".env.example", ".env"}:
                    continue
                if child.suffix in EXCLUDED_EXTENSIONS:
                    continue
                result[child.name] = _build_tree(child, depth + 1)
        except PermissionError:
            return "[permission denied]"

        return result

    tree = _build_tree(ws_path, 0)
    return {"root": str(ws_path), "tree": tree}


def read_file_content(
    workspace_path: str,
    file_path: str,
    max_lines: int = 200,
) -> str | None:
    ws_path = Path(workspace_path)
    target = ws_path / file_path

    if not target.exists():
        return None

    if not target.is_file():
        return None

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        if len(lines) > max_lines:
            kept = lines[:max_lines]
            kept.append(f"\n... [{len(lines) - max_lines} more lines truncated]")
            return "\n".join(kept)
        return content
    except Exception as e:
        logger.warning(f"Failed to read file {file_path}: {e}")
        return None


def get_code_context(
    workspace_path: str,
    affected_files: list[str] | None = None,
    max_depth: int = 3,
    max_file_lines: int = 200,
) -> dict:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        return {"directory_tree": None, "file_contents": None}

    directory_tree = get_directory_tree(workspace_path, max_depth=max_depth)

    file_contents = {}
    if affected_files:
        for fp in affected_files:
            content = read_file_content(workspace_path, fp, max_lines=max_file_lines)
            if content is not None:
                file_contents[fp] = content

    return {
        "directory_tree": directory_tree,
        "file_contents": file_contents if file_contents else None,
    }


def snapshot_workspace(workspace_path: str, message: str) -> str | None:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        return None

    try:
        subprocess.run(
            ["git", "add", "-A"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )
        result = subprocess.run(
            ["git", "commit", "-m", f"snapshot: {message}", "--allow-empty"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )
        if result.returncode == 0:
            return _get_current_commit(str(ws_path))
        logger.warning(f"Snapshot commit failed: {result.stderr}")
        return None
    except Exception as e:
        logger.warning(f"Snapshot failed: {e}")
        return None


def restore_workspace_snapshot(workspace_path: str, commit_hash: str) -> bool:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        return False

    try:
        result = subprocess.run(
            ["git", "reset", "--hard", commit_hash],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Restore snapshot failed: {e}")
        return False
