from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devflow.semantic.models import (
    FileMeta,
    NodeType,
    ParseStatus,
    RelationType,
    SemanticNode,
    SemanticRelation,
)


PYTHON_EXTENSIONS = {".py"}
JSTS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
PROGRAMMING_EXTENSIONS = PYTHON_EXTENSIONS | JSTS_EXTENSIONS

EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "artifacts",
    ".test-tmp",
    ".devflow-index",
}


@dataclass(slots=True)
class FileParseResult:
    file_path: str
    symbols: list[SemanticNode] = field(default_factory=list)
    relations: list[SemanticRelation] = field(default_factory=list)
    file_meta: FileMeta | None = None
    error: str = ""


def detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext in PYTHON_EXTENSIONS:
        return "python"
    if ext in JSTS_EXTENSIONS:
        if ext in (".ts", ".tsx"):
            return "typescript"
        return "javascript"
    return "text"


def parse_file(
    file_path: str,
    content: str,
    max_symbols: int = 500,
    timeout_seconds: int = 10,
) -> FileParseResult:
    import signal

    language = detect_language(file_path)
    result = FileParseResult(file_path=file_path)

    if language == "text":
        result.file_meta = _build_file_meta(file_path, content, "text", ParseStatus.SKIPPED)
        return result

    try:
        if timeout_seconds > 0 and hasattr(signal, "SIGALRM"):
            def _timeout_handler(signum, frame):
                raise TimeoutError("解析超时")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout_seconds)
            try:
                result = _do_parse(file_path, content, language, max_symbols)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        else:
            result = _do_parse(file_path, content, language, max_symbols)
    except TimeoutError:
        result = FileParseResult(file_path=file_path, error="解析超时")
        result.file_meta = _build_file_meta(file_path, content, language, ParseStatus.TIMEOUT, "解析超时")

    return result


def _do_parse(file_path: str, content: str, language: str, max_symbols: int) -> FileParseResult:
    if language == "python":
        return _parse_python(file_path, content, max_symbols)
    elif language in ("javascript", "typescript"):
        return _parse_jsts(file_path, content, language, max_symbols)
    return FileParseResult(file_path=file_path)


def _parse_python(file_path: str, content: str, max_symbols: int) -> FileParseResult:
    from devflow.semantic.parsers.python_parser import parse_python_file

    parse_result = parse_python_file(file_path, content, max_symbols=max_symbols)
    result = FileParseResult(
        file_path=file_path,
        symbols=parse_result.symbols,
        relations=parse_result.relations,
    )
    result.file_meta = _build_file_meta(
        file_path, content, "python", parse_result.status, parse_result.error, len(parse_result.symbols),
    )
    if hasattr(parse_result, "truncated"):
        result.file_meta = FileMeta(
            **{**_meta_dict(result.file_meta), "truncated": parse_result.truncated}
        )
    return result


def _parse_jsts(file_path: str, content: str, language: str, max_symbols: int) -> FileParseResult:
    from devflow.semantic.parsers.jsts_parser import parse_jsts_file

    parse_result = parse_jsts_file(file_path, content, language=language, max_symbols=max_symbols)
    result = FileParseResult(
        file_path=file_path,
        symbols=parse_result.symbols,
        relations=parse_result.relations,
    )
    result.file_meta = _build_file_meta(
        file_path, content, language, parse_result.status, parse_result.error, len(parse_result.symbols),
    )
    return result


def _build_file_meta(
    file_path: str,
    content: str,
    language: str,
    status: ParseStatus,
    error: str = "",
    symbol_count: int = 0,
) -> FileMeta:
    import hashlib
    from datetime import UTC, datetime

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    line_count = content.count("\n") + 1 if content else 0
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    return FileMeta(
        path=file_path,
        hash=content_hash,
        language=language,
        line_count=line_count,
        parse_status=status,
        parse_error=error,
        symbol_count=symbol_count,
        last_indexed_at=now,
    )


def _meta_dict(meta: FileMeta) -> dict[str, Any]:
    return {
        "path": meta.path,
        "hash": meta.hash,
        "language": meta.language,
        "line_count": meta.line_count,
        "parse_status": meta.parse_status,
        "parse_error": meta.parse_error,
        "symbol_count": meta.symbol_count,
        "last_indexed_at": meta.last_indexed_at,
        "truncated": meta.truncated,
    }
