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
