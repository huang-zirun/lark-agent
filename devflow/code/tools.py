from __future__ import annotations

import difflib
import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devflow.code.permissions import PermissionDenied, resolve_workspace_path, validate_powershell_command
from devflow.semantic.query import SemanticQueryEngine


MAX_READ_SIZE = 10 * 1024 * 1024
MAX_WRITE_SIZE = 10 * 1024 * 1024
EXCLUDED_DIRECTORIES = {".git", ".devflow-index", ".venv", "node_modules", "__pycache__", "artifacts", ".test-tmp"}
EXCLUDED_RUNTIME_FILE_PATTERNS = {
    "trace.jsonl",
    "*-llm-request-turn*.json",
    "*-llm-response-turn*.json",
}
PROMPT_PREVIEW_CHARS = 500


@dataclass(slots=True)
class CodeToolExecutor:
    workspace_root: Path | str
    events: list[dict[str, Any]] = field(default_factory=list)
    root: Path = field(init=False)
    _query_engine: SemanticQueryEngine | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.root = Path(self.workspace_root).expanduser().resolve()
        self._query_engine = None

    def execute(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            if tool == "read_file":
                result = self.read_file(str(payload.get("path") or ""), int(payload.get("offset") or 0), payload.get("limit"))
            elif tool == "write_file":
                result = self.write_file(str(payload.get("path") or ""), str(payload.get("content") or ""))
            elif tool == "edit_file":
                result = self.edit_file(
                    str(payload.get("path") or ""),
                    str(payload.get("old_string") or ""),
                    str(payload.get("new_string") or ""),
                    bool(payload.get("replace_all") or False),
                )
            elif tool == "glob_search":
                result = self.glob_search(str(payload.get("pattern") or "*"))
            elif tool == "grep_search":
                result = self.grep_search(str(payload.get("pattern") or ""), str(payload.get("glob") or "*"))
            elif tool == "powershell":
                result = self.powershell(str(payload.get("command") or ""), int(payload.get("timeout_seconds") or 60))
            elif tool == "semantic_search":
                result = self.semantic_search(
                    str(payload.get("query_type") or ""),
                    pattern=str(payload.get("pattern") or ""),
                    symbol_id=str(payload.get("symbol_id") or ""),
                    symbol_name=str(payload.get("symbol_name") or ""),
                    file_path=str(payload.get("file_path") or ""),
                )
            else:
                raise ValueError(f"未知代码工具：{tool}")
            self._record(tool, payload, "success", result)
            return result
        except Exception as exc:
            result = {"status": "failed", "error": str(exc)}
            self._record(tool, payload, "failed", result)
            raise

    def read_file(self, path: str, offset: int = 0, limit: Any = None) -> dict[str, Any]:
        file_path = resolve_workspace_path(self.root, path)
        if file_path.stat().st_size > MAX_READ_SIZE:
            raise ValueError(f"文件过大，拒绝读取：{path}")
        data = file_path.read_bytes()
        if b"\0" in data[:8192]:
            raise ValueError(f"文件疑似二进制，拒绝读取：{path}")
        content = data.decode("utf-8")
        lines = content.splitlines(keepends=True)
        start = max(0, offset)
        end = len(lines) if limit in (None, "") else min(len(lines), start + int(limit))
        selected = "".join(lines[start:end])
        return {
            "status": "success",
            "path": _relative(file_path, self.root),
            "content": selected,
            "start_line": start + 1,
            "line_count": max(0, end - start),
            "total_lines": len(lines),
        }

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        if len(content.encode("utf-8")) > MAX_WRITE_SIZE:
            raise ValueError(f"写入内容过大：{path}")
        file_path = resolve_workspace_path(self.root, path, must_exist=False)
        original = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8", newline="\n")
        return {
            "status": "success",
            "path": _relative(file_path, self.root),
            "operation": "modify" if original else "create",
            "patch": _unified_patch(path, original, content),
        }

    def edit_file(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> dict[str, Any]:
        if old_string == new_string:
            raise ValueError("old_string 和 new_string 必须不同")
        if not old_string:
            raise ValueError("old_string 不能为空")
        file_path = resolve_workspace_path(self.root, path)
        original = file_path.read_text(encoding="utf-8")
        if old_string not in original:
            raise ValueError(f"未找到待替换文本：{path}")
        updated = original.replace(old_string, new_string) if replace_all else original.replace(old_string, new_string, 1)
        file_path.write_text(updated, encoding="utf-8", newline="\n")
        return {
            "status": "success",
            "path": _relative(file_path, self.root),
            "operation": "modify",
            "patch": _unified_patch(path, original, updated),
        }

    def glob_search(self, pattern: str) -> dict[str, Any]:
        matches: list[str] = []
        for path in self._iter_files():
            rel = _relative(path, self.root)
            if fnmatch.fnmatch(rel, pattern):
                matches.append(rel)
        return {"status": "success", "matches": matches[:100], "truncated": len(matches) > 100}

    def grep_search(self, pattern: str, glob: str = "*") -> dict[str, Any]:
        regex = re.compile(pattern)
        matches: list[dict[str, Any]] = []
        for path in self._iter_files():
            rel = _relative(path, self.root)
            if not fnmatch.fnmatch(rel, glob):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for index, line in enumerate(lines, start=1):
                if regex.search(line):
                    matches.append({"path": rel, "line": index, "text": line})
        return {"status": "success", "matches": matches[:100], "truncated": len(matches) > 100}

    def powershell(self, command: str, timeout_seconds: int) -> dict[str, Any]:
        validate_powershell_command(command)
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=self.root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "status": "success" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "")[-4000:],
            "stderr": (completed.stderr or "")[-4000:],
        }

    def semantic_search(self, query_type: str, pattern: str = "", symbol_id: str = "", symbol_name: str = "", file_path: str = "") -> dict[str, Any]:
        if self._query_engine is None:
            self._query_engine = SemanticQueryEngine(self.root)
            self._query_engine.load_index()
        if not self._query_engine.is_loaded():
            from devflow.semantic.indexer import SemanticIndexer
            from devflow.config import SemanticConfig
            indexer = SemanticIndexer(self.root, SemanticConfig())
            indexer.build_index()
            self._query_engine = SemanticQueryEngine(self.root)
            self._query_engine.load_index()
        if not self._query_engine.is_loaded():
            return {"status": "failed", "error": "无法构建语义索引"}
        result = self._query_engine.query(query_type, pattern=pattern, symbol_id=symbol_id, symbol_name=symbol_name, file_path=file_path)
        return {
            "status": "success",
            "query_type": result.query_type,
            "results": result.results,
            "total_count": result.total_count,
            "truncated": result.truncated,
            "error": result.error,
        }

    def _iter_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(self.root).parts):
                continue
            files.append(path)
        return sorted(files)

    def _record(self, tool: str, payload: dict[str, Any], status: str, result: dict[str, Any]) -> None:
        self.events.append(
            {
                "tool": tool,
                "input": _redact(payload),
                "status": status,
                "result": _redact(result),
            }
        )


def capture_git_diff(workspace_root: Path | str) -> str:
    return str(capture_workspace_changes(workspace_root).get("diff") or "")


def capture_workspace_changes(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve()
    result: dict[str, Any] = {
        "diff": "",
        "changed_files": [],
        "untracked_files": [],
        "excluded_files": [],
    }
    has_git = (root / ".git").exists()
    diff_text = ""
    changed_files: list[str] = []
    if has_git:
        completed = subprocess.run(
            ["git", "diff", "--no-ext-diff"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
        diff_text = (completed.stdout or "") if completed.returncode == 0 else ""
        changed_files = _changed_files_from_diff(diff_text)

    untracked_files: list[str] = []
    synthetic_diffs: list[str] = []
    excluded_files: list[str] = []
    candidates = _git_untracked_files(root) if has_git else _workspace_text_file_candidates(root)
    for rel in candidates:
        rel_path = rel.replace("\\", "/").strip()
        if not rel_path:
            continue
        path = (root / rel_path).resolve()
        if _is_excluded_relative(rel_path):
            excluded_files.append(rel_path)
            continue
        if not path.is_file() or not _is_text_file(path):
            excluded_files.append(rel_path)
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            excluded_files.append(rel_path)
            continue
        untracked_files.append(rel_path)
        synthetic_diffs.append(_unified_patch(rel_path, "", content))

    all_changed = _unique_texts(changed_files, untracked_files)
    combined_diff = diff_text
    if synthetic_diffs:
        combined_diff += ("\n" if combined_diff and not combined_diff.endswith("\n") else "")
        combined_diff += "".join(synthetic_diffs)
    result.update(
        {
            "diff": combined_diff,
            "changed_files": all_changed,
            "untracked_files": untracked_files,
            "excluded_files": excluded_files,
        }
    )
    return result


def compact_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("status", "path", "operation", "returncode", "start_line", "line_count", "total_lines", "truncated", "error"):
        if key in result:
            compact[key] = result[key]
    if "matches" in result and isinstance(result["matches"], list):
        compact["match_count"] = len(result["matches"])
        compact["matches"] = result["matches"][:20]
    for key in ("content", "patch", "stdout", "stderr"):
        value = result.get(key)
        if isinstance(value, str):
            compact[f"{key}_chars"] = len(value)
            compact[f"{key}_preview"] = _compact_text(value)
            if len(value) > PROMPT_PREVIEW_CHARS:
                compact["truncated"] = True
    for key, value in result.items():
        if key not in compact and key not in {"content", "patch", "stdout", "stderr", "matches"}:
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact[key] = value
    return compact


def compact_tool_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("input") if isinstance(event.get("input"), dict) else {}
    result = event.get("result") if isinstance(event.get("result"), dict) else {}
    return {
        "tool": event.get("tool"),
        "input": compact_tool_input(payload),
        "status": event.get("status"),
        "result": compact_tool_result(result),
    }


def compact_tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    compact_input: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > PROMPT_PREVIEW_CHARS:
            compact_input[f"{key}_chars"] = len(value)
            compact_input[f"{key}_preview"] = _compact_text(value)
            compact_input["truncated"] = True
        else:
            compact_input[key] = value
    return compact_input


def compact_agent_action(action: dict[str, Any]) -> dict[str, Any]:
    if action.get("action") != "tool":
        return action
    payload = action.get("input") if isinstance(action.get("input"), dict) else {}
    return {
        "action": "tool",
        "tool": action.get("tool"),
        "input": compact_tool_input(payload),
    }


def compact_tool_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [compact_tool_event(event) for event in events[-20:]]


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _unified_patch(path: str, original: str, updated: str) -> str:
    body = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    return f"diff --git a/{path} b/{path}\n{body}"


def _git_untracked_files(root: Path) -> list[str]:
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    if untracked.returncode != 0:
        return []
    return [line for line in (untracked.stdout or "").splitlines() if line.strip()]


def _workspace_text_file_candidates(root: Path) -> list[str]:
    candidates: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = _relative(path, root)
        if _is_excluded_relative(rel):
            continue
        if _is_text_file(path):
            candidates.append(rel)
    return candidates


def _redact(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    if len(text) <= 1000:
        return value
    return {"truncated": True, "preview": text[:1000]}


def _is_excluded_relative(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    if any(part in EXCLUDED_DIRECTORIES for part in parts):
        return True
    name = Path(rel_path).name
    return any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_RUNTIME_FILE_PATTERNS)


def _is_text_file(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if len(data) > MAX_READ_SIZE:
        return False
    if b"\0" in data[:8192]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _changed_files_from_diff(diff_text: str) -> list[str]:
    files: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[3].removeprefix("b/"))
    return _unique_texts(files)


def _unique_texts(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for group in groups:
        for item in group:
            text = str(item).strip().replace("\\", "/")
            if text and text not in seen:
                seen.add(text)
                values.append(text)
    return values


def _compact_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    if len(normalized) <= PROMPT_PREVIEW_CHARS:
        return normalized
    return normalized[:PROMPT_PREVIEW_CHARS].rstrip() + "...[truncated]"
