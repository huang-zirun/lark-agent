from __future__ import annotations

import re
from pathlib import Path


class PermissionDenied(ValueError):
    """Raised when a code-generation tool would escape its workspace boundary."""


DESTRUCTIVE_COMMAND_PATTERNS = [
    r"\bRemove-Item\b.*(?:^|\s)-Recurse(?:\s|$)",
    r"\brm\b.*\b-rf\b",
    r"\bdel\b",
    r"\bformat\b",
    r"\bgit\s+reset\b.*\b--hard\b",
    r"\bgit\s+checkout\b.*\s--\s",
]


def resolve_workspace_path(root: Path | str, path: str, *, must_exist: bool = True) -> Path:
    root_path = Path(root).expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root_path / candidate
    resolved = candidate.resolve(strict=must_exist)
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise PermissionDenied(f"路径超出工作区边界：{resolved}") from exc
    return resolved


def validate_powershell_command(command: str) -> None:
    normalized = command.strip()
    for pattern in DESTRUCTIVE_COMMAND_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            raise PermissionDenied(f"命令被安全策略拒绝：{normalized}")
