import subprocess
from pathlib import Path

from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)

MAX_PATCH_RETRIES = 2


async def apply_patch(workspace_path: str, patch_content: str, file_path: str | None = None) -> dict:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        raise ExecutionError(f"Workspace not found: {workspace_path}")

    if file_path:
        target_file = ws_path / file_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(patch_content, encoding="utf-8")
        return {"success": True, "method": "direct_write", "file": file_path}

    for attempt in range(1, MAX_PATCH_RETRIES + 2):
        try:
            result = subprocess.run(
                ["git", "apply", "--allow-empty"],
                input=patch_content,
                capture_output=True,
                text=True,
                cwd=str(ws_path),
                timeout=30,
            )
            if result.returncode == 0:
                logger.info(f"Patch applied successfully (attempt {attempt})")
                return {"success": True, "method": "git_apply", "attempt": attempt}

            logger.warning(f"Patch apply attempt {attempt} failed: {result.stderr}")

            if attempt <= MAX_PATCH_RETRIES:
                try:
                    result_fuzzy = subprocess.run(
                        ["git", "apply", "--3way", "--allow-empty"],
                        input=patch_content,
                        capture_output=True,
                        text=True,
                        cwd=str(ws_path),
                        timeout=30,
                    )
                    if result_fuzzy.returncode == 0:
                        logger.info(f"Patch applied with 3way merge (attempt {attempt})")
                        return {"success": True, "method": "git_apply_3way", "attempt": attempt}
                except Exception:
                    pass

        except subprocess.TimeoutExpired:
            logger.warning(f"Patch apply attempt {attempt} timed out")

    return {"success": False, "method": "failed", "attempts": MAX_PATCH_RETRIES + 1}


async def generate_diff(workspace_path: str) -> dict:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        raise ExecutionError(f"Workspace not found: {workspace_path}")

    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=10,
        )
        base_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"

        diff_result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )

        stat_result = subprocess.run(
            ["git", "diff", "--numstat", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )

        name_result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(ws_path),
            timeout=30,
        )

        changed_files = [f for f in name_result.stdout.strip().split("\n") if f]

        insertions = 0
        deletions = 0
        for line in stat_result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        if parts[0] != "-":
                            insertions += int(parts[0])
                        if parts[1] != "-":
                            deletions += int(parts[1])
                    except ValueError:
                        pass

        return {
            "base_commit": base_commit,
            "changed_files": changed_files,
            "diff_path": str(ws_path),
            "stats": {
                "files_changed": len(changed_files),
                "insertions": insertions,
                "deletions": deletions,
            },
        }

    except subprocess.TimeoutExpired:
        raise ExecutionError("Git diff generation timed out")
