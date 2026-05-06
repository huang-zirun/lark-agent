from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from devflow.config import ConfigError, load_config
from devflow.intake.lark_cli import publish_document


DocumentPublisher = Callable[[str, str, str | None], dict[str, Any]]


def publish_artifact_document(
    run_payload: dict[str, Any],
    stage: str,
    title: str,
    markdown: str,
    *,
    publisher: DocumentPublisher | None = None,
    folder_token: str | None = None,
) -> dict[str, Any]:
    """Publish a human-readable stage artifact and record the result on run_payload."""
    result: dict[str, Any] = {
        "stage": stage,
        "title": title,
        "document_id": None,
        "url": None,
        "status": "running",
        "error": None,
    }
    _record_publication(run_payload, stage, result)
    try:
        effective_folder_token = folder_token if folder_token is not None else artifact_folder_token()
        publish = publisher or _default_publisher
        document = publish(title, markdown, effective_folder_token)
        result.update(
            {
                "document_id": document.get("document_id"),
                "url": document.get("url"),
                "status": "success",
                "error": None,
            }
        )
    except Exception as exc:
        result.update({"status": "failed", "error": str(exc)})
    _record_publication(run_payload, stage, result)
    _write_run_payload_if_possible(run_payload)
    return result


def artifact_folder_token() -> str | None:
    try:
        config = load_config()
    except ConfigError:
        return None
    return config.lark.artifact_folder_token or config.lark.prd_folder_token or None


def render_code_generation_markdown(
    artifact: dict[str, Any],
    *,
    run_id: str,
    artifact_path: Path | str | None = None,
    diff_path: Path | str | None = None,
) -> str:
    summary = _text(artifact.get("summary")) or "代码生成已完成。"
    files = _text_list(artifact.get("changed_files"))
    warnings = _text_list(artifact.get("warnings"))
    diff = _text(artifact.get("diff")) or ""
    lines = [
        f"# DevFlow 代码生成：{run_id}",
        "",
        "## 摘要",
        "",
        summary,
        "",
        "## 变更文件",
        "",
        *_bullet_list(files, empty="暂无变更文件。", code=True),
        "",
        "## 警告",
        "",
        *_bullet_list(warnings, empty="暂无警告。"),
        "",
        "## Diff 概览",
        "",
        *_diff_overview(diff),
        "",
        "## 本地产物",
        "",
    ]
    if artifact_path is not None:
        lines.append(f"- JSON：`{_path_text(artifact_path)}`")
    if diff_path is not None:
        lines.append(f"- Diff：`{_path_text(diff_path)}`")
    if artifact_path is None and diff_path is None:
        lines.append("- 暂无本地产物路径。")
    return "\n".join(lines).rstrip() + "\n"


def render_test_generation_markdown(
    artifact: dict[str, Any],
    *,
    run_id: str,
    artifact_path: Path | str | None = None,
    diff_path: Path | str | None = None,
) -> str:
    summary = _text(artifact.get("summary")) or "测试生成已完成。"
    generated_tests = _text_list(artifact.get("generated_tests"))
    warnings = _text_list(artifact.get("warnings"))
    commands = artifact.get("test_commands") if isinstance(artifact.get("test_commands"), list) else []
    diff = _text(artifact.get("diff")) or ""
    lines = [
        f"# DevFlow 测试生成：{run_id}",
        "",
        "## 摘要",
        "",
        summary,
        "",
        "## 生成的测试",
        "",
        *_bullet_list(generated_tests, empty="暂无生成的测试。", code=True),
        "",
        "## 测试命令",
        "",
    ]
    if commands:
        for command in commands:
            if not isinstance(command, dict):
                continue
            lines.append(
                f"- `{command.get('command', '')}`：{command.get('status', '')} ({command.get('returncode', '')})"
            )
    else:
        lines.append("- 暂无测试命令。")
    lines.extend(
        [
            "",
            "## 警告",
            "",
            *_bullet_list(warnings, empty="暂无警告。"),
            "",
            "## Diff 概览",
            "",
            *_diff_overview(diff),
            "",
            "## 本地产物",
            "",
        ]
    )
    if artifact_path is not None:
        lines.append(f"- JSON：`{_path_text(artifact_path)}`")
    if diff_path is not None:
        lines.append(f"- Diff：`{_path_text(diff_path)}`")
    if artifact_path is None and diff_path is None:
        lines.append("- 暂无本地产物路径。")
    return "\n".join(lines).rstrip() + "\n"


def _default_publisher(title: str, markdown: str, folder_token: str | None) -> dict[str, Any]:
    return publish_document(title, markdown, folder_token=folder_token)


def _record_publication(run_payload: dict[str, Any], stage: str, result: dict[str, Any]) -> None:
    publications = run_payload.get("artifact_publications")
    if not isinstance(publications, dict):
        publications = {}
        run_payload["artifact_publications"] = publications
    publications[stage] = dict(result)


def _write_run_payload_if_possible(run_payload: dict[str, Any]) -> None:
    path_text = run_payload.get("run_path")
    if not isinstance(path_text, str) or not path_text:
        return
    try:
        Path(path_text).write_text(
            json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _diff_overview(diff: str) -> list[str]:
    if not diff.strip():
        return ["- 暂无 diff。"]
    files = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[3].removeprefix("b/"))
    overview = [f"- 变更文件数：{len(files)}"]
    overview.extend(f"- `{path}`" for path in files[:20])
    if len(files) > 20:
        overview.append(f"- 另有 {len(files) - 20} 个文件未展示。")
    if len(overview) == 1:
        overview.append("- diff 已生成，但未识别到文件头。")
    return overview


def _bullet_list(values: list[str], *, empty: str, code: bool = False) -> list[str]:
    if not values:
        return [f"- {empty}"]
    if code:
        return [f"- `{value}`" for value in values]
    return [f"- {value}" for value in values]


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if value is None:
        return None
    return str(value).strip() or None


def _path_text(value: Path | str) -> str:
    if isinstance(value, Path):
        return value.as_posix()
    return str(value).replace("\\", "/")
