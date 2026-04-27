from pathlib import Path

from app.core.workspace.patch_applier import generate_diff
from app.shared.logging import get_logger
from app.shared.subprocess_utils import run_git

logger = get_logger(__name__)


async def commit_delivery_changes(workspace_path: str, goal_summary: str) -> dict:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        return {"success": False, "has_changes": False, "commit_hash": None, "error": f"Workspace not found: {workspace_path}"}

    try:
        status_result = run_git(["status", "--porcelain"], cwd=str(ws_path), timeout=10)
        if status_result.returncode != 0:
            return {"success": False, "has_changes": False, "commit_hash": None, "error": status_result.stderr.strip()}

        if not status_result.stdout.strip():
            return {"success": True, "has_changes": False, "commit_hash": None}

        add_result = run_git(["add", "-A"], cwd=str(ws_path), timeout=30)
        if add_result.returncode != 0:
            return {"success": False, "has_changes": False, "commit_hash": None, "error": add_result.stderr.strip()}

        commit_result = run_git(["commit", "-m", f"feat: {goal_summary}"], cwd=str(ws_path), timeout=30)
        if commit_result.returncode != 0:
            return {"success": False, "has_changes": False, "commit_hash": None, "error": commit_result.stderr.strip()}

        hash_result = run_git(["rev-parse", "HEAD"], cwd=str(ws_path), timeout=10)
        commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None

        return {"success": True, "has_changes": True, "commit_hash": commit_hash}

    except Exception as e:
        logger.error(f"commit_delivery_changes failed: {e}")
        return {"success": False, "has_changes": False, "commit_hash": None, "error": str(e)}


async def create_delivery_branch(workspace_path: str, run_id: str) -> dict:
    branch_name = f"devflow/{run_id[:12]}"

    try:
        verify_result = run_git(["rev-parse", "--verify", branch_name], cwd=str(workspace_path), timeout=10)
        if verify_result.returncode == 0:
            logger.warning(f"Branch {branch_name} already exists, deleting it")
            run_git(["branch", "-D", branch_name], cwd=str(workspace_path), timeout=10)

        checkout_result = run_git(["checkout", "-b", branch_name], cwd=str(workspace_path), timeout=15)
        if checkout_result.returncode != 0:
            return {"success": False, "branch_name": None, "error": checkout_result.stderr.strip()}

        return {"success": True, "branch_name": branch_name}

    except Exception as e:
        logger.error(f"create_delivery_branch failed: {e}")
        return {"success": False, "branch_name": None, "error": str(e)}


async def generate_delivery_diff(workspace_path: str) -> dict:
    try:
        result = await generate_diff(workspace_path)
        return result
    except Exception as e:
        logger.error(f"generate_delivery_diff failed: {e}")
        return {"success": False, "error": str(e)}


async def execute_delivery(workspace_path: str, run_id: str, goal_summary: str) -> dict:
    commit_result = await commit_delivery_changes(workspace_path, goal_summary)

    branch_result = None
    diff_result = None
    error = None

    if commit_result.get("success") and commit_result.get("has_changes"):
        branch_result = await create_delivery_branch(workspace_path, run_id)
        if not branch_result.get("success"):
            error = branch_result.get("error")

        diff_result = await generate_delivery_diff(workspace_path)
        if not diff_result.get("success") and diff_result.get("error") and not error:
            error = diff_result.get("error")
    elif not commit_result.get("success"):
        error = commit_result.get("error")

    return {
        "commit_hash": commit_result.get("commit_hash"),
        "branch_name": branch_result.get("branch_name") if branch_result else None,
        "changed_files": diff_result.get("changed_files", []) if diff_result else [],
        "diff_stats": diff_result.get("stats", {}) if diff_result else {},
        "has_changes": commit_result.get("has_changes", False),
        "error": error,
    }
