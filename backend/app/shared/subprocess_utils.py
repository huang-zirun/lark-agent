import os
import shutil
import subprocess
import sys
from pathlib import Path

_GIT_ISOLATED_ENV = {
    "GIT_AUTHOR_NAME": "devflow",
    "GIT_AUTHOR_EMAIL": "devflow@bot",
    "GIT_COMMITTER_NAME": "devflow",
    "GIT_COMMITTER_EMAIL": "devflow@bot",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_PAGER": "cat",
    "LC_ALL": "C.UTF-8",
}


def _strip_win_long_prefix(path_str: str) -> str:
    if sys.platform == "win32" and path_str.startswith("\\\\?\\"):
        return path_str[4:]
    return path_str


def run_git(
    args: list[str],
    cwd: str,
    timeout: int = 30,
    input: str | None = None,
) -> subprocess.CompletedProcess:
    env = {**os.environ, **_GIT_ISOLATED_ENV}
    cwd = _strip_win_long_prefix(cwd)
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        timeout=timeout,
        env=env,
        input=input,
    )


def normalize_absolute_path(p: Path) -> str:
    resolved = str(p.resolve())
    result = _strip_win_long_prefix(resolved)
    if sys.platform == "win32" and len(result) >= 2 and result[1] == ":":
        result = result[0].upper() + result[1:]
    return result


def safe_join(root: str | Path, user_path: str) -> Path:
    root_resolved = Path(root).resolve()
    target = (root_resolved / user_path).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        raise ValueError(f"Path escapes workspace: {user_path}")
    return target


def find_git() -> str:
    git_path = shutil.which("git")
    if git_path:
        return git_path
    if sys.platform == "win32":
        common_paths = [
            Path(os.environ.get("PROGRAMFILES", "")) / "Git" / "bin" / "git.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Git" / "bin" / "git.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "bin" / "git.exe",
        ]
        for p in common_paths:
            if p.exists():
                return str(p)
    raise RuntimeError(
        "Git is not installed or not in PATH. "
        "Please install Git from https://git-scm.com/downloads"
    )


def normalize_patch_content(content: str) -> str:
    content = content.lstrip("\ufeff")
    content = content.replace("\r\n", "\n")
    return content
