from pathlib import Path

from app.shared.errors import ExecutionError
from app.shared.logging import get_logger
from app.shared.subprocess_utils import (
    run_git,
    safe_join,
    normalize_patch_content,
)

logger = get_logger(__name__)

MAX_PATCH_RETRIES = 2


async def apply_patch(workspace_path: str, patch_content: str, file_path: str | None = None) -> dict:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        raise ExecutionError(f"Workspace not found: {workspace_path}")

    if file_path:
        try:
            target_file = safe_join(ws_path, file_path)
        except ValueError:
            raise ExecutionError(f"Path escapes workspace: {file_path}")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(patch_content, encoding="utf-8")
        return {"success": True, "method": "direct_write", "file": file_path}

    patch_content = normalize_patch_content(patch_content)

    check_result = run_git(
        ["apply", "--check"],
        cwd=str(ws_path),
        timeout=30,
        input=patch_content,
    )
    if check_result.returncode != 0:
        logger.info(f"Patch check indicates issues: {check_result.stderr}")

    for attempt in range(1, MAX_PATCH_RETRIES + 2):
        try:
            result = run_git(
                ["apply", "--allow-empty"],
                cwd=str(ws_path),
                timeout=30,
                input=patch_content,
            )
            if result.returncode == 0:
                logger.info(f"Patch applied successfully (attempt {attempt})")
                return {"success": True, "method": "git_apply", "attempt": attempt}

            logger.warning(f"Patch apply attempt {attempt} failed: {result.stderr}")

            if attempt <= MAX_PATCH_RETRIES:
                try:
                    result_fuzzy = run_git(
                        ["apply", "--3way", "--allow-empty"],
                        cwd=str(ws_path),
                        timeout=30,
                        input=patch_content,
                    )
                    if result_fuzzy.returncode == 0:
                        logger.info(f"Patch applied with 3way merge (attempt {attempt})")
                        return {"success": True, "method": "git_apply_3way", "attempt": attempt}
                    logger.warning(f"3way merge also failed: {result_fuzzy.stderr}")
                except Exception as e3:
                    logger.warning(f"3way merge exception: {e3}")

        except Exception as e:
            if "timed out" in str(e).lower():
                logger.warning(f"Patch apply attempt {attempt} timed out")
            else:
                logger.warning(f"Patch apply attempt {attempt} error: {e}")

    return {
        "success": False,
        "method": "failed",
        "attempts": MAX_PATCH_RETRIES + 1,
        "check_stderr": check_result.stderr if check_result.returncode != 0 else None,
    }


async def generate_diff(workspace_path: str) -> dict:
    ws_path = Path(workspace_path)
    if not ws_path.exists():
        raise ExecutionError(f"Workspace not found: {workspace_path}")

    try:
        commit_result = run_git(
            ["rev-parse", "HEAD"],
            cwd=str(ws_path),
            timeout=10,
        )
        base_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"

        diff_result = run_git(
            ["diff", "HEAD"],
            cwd=str(ws_path),
            timeout=30,
        )

        stat_result = run_git(
            ["diff", "--numstat", "HEAD"],
            cwd=str(ws_path),
            timeout=30,
        )

        name_result = run_git(
            ["diff", "--name-only", "HEAD"],
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

    except Exception as e:
        if "timed out" in str(e).lower():
            raise ExecutionError("Git diff generation timed out")
        raise ExecutionError(f"Git diff generation failed: {e}")
