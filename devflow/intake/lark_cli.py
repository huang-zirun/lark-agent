from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from devflow.config import LOCKED_LARK_CLI_VERSION
from devflow.intake.models import RequirementSource


JsonValue = dict[str, Any] | list[Any]
Runner = Callable[[list[str], int | None], JsonValue]
BOT_MESSAGE_EVENT_KEY = "im.message.receive_v1"


class LarkCliError(RuntimeError):
    """Raised when the lark-cli integration cannot produce usable data."""


class LarkCliNotFound(LarkCliError):
    """Raised when lark-cli is not installed or not on PATH."""


def _resolve_native_exe_from_cmd_shim(cmd_path: str) -> str | None:
    shim_dir = os.path.dirname(cmd_path)
    exe_path = os.path.normpath(
        os.path.join(shim_dir, "..", "@larksuite", "cli", "bin", "lark-cli.exe")
    )
    if os.path.isfile(exe_path):
        return exe_path
    return None


def find_lark_cli_executable() -> str:
    candidates = ["lark-cli"]
    if os.name == "nt":
        candidates = ["lark-cli.exe", "lark-cli.cmd", "lark-cli"]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable is not None:
            if os.name == "nt" and executable.endswith(".cmd"):
                native_exe = _resolve_native_exe_from_cmd_shim(executable)
                if native_exe is not None:
                    return native_exe
            return executable
    raise LarkCliNotFound(
        "未在 PATH 中找到 lark-cli。请先运行 "
        f"`npm.cmd install -g @larksuite/cli@{LOCKED_LARK_CLI_VERSION}`，然后执行 "
        "`lark-cli config init --new` 和 `lark-cli auth login --recommend`。"
    )


def run_lark_cli_text(args: list[str], timeout_seconds: int | None = 120) -> str:
    executable = find_lark_cli_executable()
    completed = subprocess.run(
        [executable, *args],
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise LarkCliError(f"lark-cli 执行失败（{executable}）：{stderr}")
    return completed.stdout.strip()


def run_lark_cli(args: list[str], timeout_seconds: int | None = 120) -> JsonValue:
    return _load_json(run_lark_cli_text(args, timeout_seconds))


def get_lark_cli_version(timeout_seconds: int | None = 30) -> str:
    output = run_lark_cli_text(["--version"], timeout_seconds)
    match = re.search(r"(\d+\.\d+\.\d+)", output)
    if match is None:
        raise LarkCliError("无法解析 lark-cli 版本输出。")
    return match.group(1)


def get_lark_cli_auth_status(timeout_seconds: int | None = 30) -> str:
    return run_lark_cli_text(["auth", "status"], timeout_seconds)


def ensure_lark_cli_version(expected: str = LOCKED_LARK_CLI_VERSION) -> str:
    version = get_lark_cli_version()
    if version != expected:
        raise LarkCliError(f"lark-cli 版本不匹配：期望 {expected}，实际为 {version}。")
    return version


def fetch_doc_source(doc: str, runner: Runner = run_lark_cli) -> RequirementSource:
    payload = runner(
        [
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            doc,
            "--doc-format",
            "markdown",
            "--format",
            "json",
        ],
        120,
    )
    if not isinstance(payload, dict):
        raise LarkCliError("docs +fetch 输出异常：期望 JSON object。")

    data = _dict(payload.get("data"))
    document = _dict(data.get("document")) or data
    content = (
        _string(document.get("content"))
        or _string(document.get("markdown"))
        or _string(data.get("content"))
        or _string(data.get("markdown"))
        or ""
    )
    document_id = (
        _string(document.get("document_id"))
        or _string(document.get("doc_id"))
        or _string(document.get("doc_token"))
        or doc
    )
    title = _string(document.get("title")) or _first_heading(content)

    source = RequirementSource(
        source_type="lark_doc",
        source_id=document_id,
        reference=doc,
        title=title,
        content=content,
        identity=_string(payload.get("identity")),
        metadata={
            "lark_command": "docs +fetch",
            "revision_id": document.get("revision_id"),
            "raw_ok": payload.get("ok"),
        },
        embedded_resources=_embedded_resources_from_text(content),
    )
    _ensure_source(source)
    return source


def fetch_message_source(message_id: str, runner: Runner = run_lark_cli) -> RequirementSource:
    payload = runner(
        ["im", "+messages-mget", "--message-ids", message_id, "--format", "json"],
        120,
    )
    if not isinstance(payload, dict):
        raise LarkCliError("im +messages-mget 输出异常：期望 JSON object。")

    messages = _messages_from_payload(payload)
    if not messages:
        raise LarkCliError(f"没有找到机器人可访问的消息：{message_id}。")

    message = messages[0]
    content = content_to_text(message.get("content"))
    resolved_message_id = _string(message.get("message_id")) or message_id
    source = RequirementSource(
        source_type="lark_message",
        source_id=resolved_message_id,
        reference=resolved_message_id,
        title=_first_heading(content),
        content=content,
        identity=_string(payload.get("identity")),
        metadata={
            "lark_command": "im +messages-mget",
            "msg_type": message.get("msg_type"),
            "chat_id": message.get("chat_id"),
            "create_time": message.get("create_time"),
            "sender": message.get("sender"),
        },
        attachments=_attachments_from_message(message),
    )
    _ensure_source(source)
    return source


def listen_bot_sources(
    max_events: int,
    timeout_seconds: int = 60,
    runner: Runner | None = None,
) -> list[RequirementSource]:
    sources: list[RequirementSource] = []
    for index, event in enumerate(
        listen_bot_events(
            max_events=max_events,
            timeout_seconds=timeout_seconds,
            runner=runner,
        ),
        start=1,
    ):
        source = event_to_source(event, fallback_index=index)
        if source.content.strip():
            sources.append(source)
    return sources


def listen_bot_events(
    max_events: int | None,
    timeout_seconds: int | None = 60,
    runner: Runner | None = None,
) -> Iterable[dict[str, Any]]:
    command = bot_message_event_command(max_events=max_events, timeout_seconds=timeout_seconds)
    if runner is not None:
        timeout = timeout_seconds + 15 if timeout_seconds is not None else None
        payload = runner(command, timeout)
        yield from _events_from_payload(payload)
        return

    yield from iter_lark_cli_event_stream(
        command,
        max_events=max_events,
        timeout_seconds=timeout_seconds,
    )


def bot_message_event_command(
    max_events: int | None,
    timeout_seconds: int | None,
) -> list[str]:
    command = ["event", "consume", BOT_MESSAGE_EVENT_KEY]
    if max_events is not None:
        command.extend(["--max-events", str(max_events)])
    if timeout_seconds is not None:
        command.extend(["--timeout", f"{timeout_seconds}s"])
    command.extend(["--as", "bot"])
    return command


def run_lark_cli_event_stream(
    args: list[str],
    max_events: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    return list(
        iter_lark_cli_event_stream(
            args,
            max_events=max_events,
            timeout_seconds=timeout_seconds,
        )
    )


def iter_lark_cli_event_stream(
    args: list[str],
    max_events: int | None,
    timeout_seconds: int | None,
) -> Iterable[dict[str, Any]]:
    executable = find_lark_cli_executable()
    process = subprocess.Popen(
        [executable, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout_queue: queue.Queue[str | None] = queue.Queue()
    stderr_lines: list[str] = []

    def read_stdout() -> None:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                stdout_queue.put(line)
        finally:
            stdout_queue.put(None)

    def read_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            stderr_lines.append(line.rstrip())

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    seen_events = 0
    deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
    terminated_by_timeout = False
    try:
        while max_events is None or seen_events < max_events:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                terminated_by_timeout = True
                break
            try:
                queue_timeout = 0.5 if remaining is None else min(0.5, remaining)
                line = stdout_queue.get(timeout=queue_timeout)
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise LarkCliError("lark-cli event 输出不是有效 NDJSON。") from exc
            if isinstance(event, dict):
                seen_events += 1
                yield event
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    stderr_thread.join(timeout=1)
    return_code = process.returncode
    if return_code not in (0, None) and seen_events == 0 and not terminated_by_timeout:
        stderr = "\n".join(line for line in stderr_lines if line).strip()
        raise LarkCliError(f"lark-cli 执行失败：{stderr or f'exit code {return_code}'}")


def send_bot_reply(
    message_id: str,
    text: str,
    idempotency_key: str,
    runner: Runner = run_lark_cli,
) -> JsonValue:
    return runner(
        [
            "im",
            "+messages-reply",
            "--message-id",
            message_id,
            "--text",
            text,
            "--as",
            "bot",
            "--idempotency-key",
            idempotency_key,
        ],
        120,
    )


def publish_document(
    title: str,
    markdown: str,
    *,
    folder_token: str | None = None,
    runner: Runner = run_lark_cli,
) -> dict[str, Any]:
    args = [
        "docs",
        "+create",
        "--as",
        "bot",
        "--title",
        title,
        "--markdown",
        markdown,
    ]
    if folder_token:
        args.extend(["--folder-token", folder_token])
    payload = runner(args, 120)
    if not isinstance(payload, dict):
        raise LarkCliError("docs +create 输出异常：期望 JSON object。")
    data = _dict(payload.get("data"))
    document = _dict(data.get("document")) or _dict(payload.get("document")) or data
    document_id = (
        _string(document.get("document_id"))
        or _string(document.get("doc_id"))
        or _string(document.get("doc_token"))
    )
    url = _string(document.get("url")) or _string(data.get("url")) or _string(payload.get("url"))
    if not document_id and not url:
        raise LarkCliError("docs +create 未返回可用的文档标识或链接。")
    return {
        "document_id": document_id,
        "url": url,
    }


def create_prd_document(
    title: str,
    markdown: str,
    *,
    folder_token: str | None = None,
    runner: Runner = run_lark_cli,
) -> dict[str, Any]:
    result = publish_document(title, markdown, folder_token=folder_token, runner=runner)
    result["raw_ok"] = True
    return result


def send_bot_card_reply(
    message_id: str,
    card: dict[str, Any],
    idempotency_key: str,
    runner: Runner = run_lark_cli,
) -> JsonValue:
    return runner(
        [
            "im",
            "+messages-reply",
            "--message-id",
            message_id,
            "--msg-type",
            "interactive",
            "--content",
            json.dumps(card, ensure_ascii=False),
            "--as",
            "bot",
            "--idempotency-key",
            idempotency_key,
        ],
        120,
    )


def send_bot_message(
    chat_id: str,
    msg_type: str,
    content: str,
    idempotency_key: str,
    runner: Runner = run_lark_cli,
) -> JsonValue:
    return runner(
        [
            "im",
            "+messages-send",
            "--chat-id",
            chat_id,
            "--msg-type",
            msg_type,
            "--content",
            content,
            "--as",
            "bot",
            "--idempotency-key",
            idempotency_key,
        ],
        120,
    )


def send_bot_text(
    chat_id: str,
    text: str,
    idempotency_key: str,
    runner: Runner = run_lark_cli,
) -> JsonValue:
    """Send a text message to a chat without passing raw newlines via shell args."""
    return runner(
        [
            "im",
            "+messages-send",
            "--chat-id",
            chat_id,
            "--msg-type",
            "text",
            "--content",
            json.dumps({"text": text}, ensure_ascii=False),
            "--as",
            "bot",
            "--idempotency-key",
            idempotency_key,
        ],
        120,
    )


def event_to_source(event: dict[str, Any], fallback_index: int = 1) -> RequirementSource:
    body = _dict(event.get("event")) or event
    message = _dict(body.get("message"))
    content_value = (
        body.get("content")
        or message.get("content")
        or body.get("text")
        or body.get("message_content")
    )
    content = content_to_text(content_value)
    message_id = (
        _string(body.get("message_id"))
        or _string(message.get("message_id"))
        or _string(body.get("open_message_id"))
        or f"event-{fallback_index}"
    )
    chat_id = _string(body.get("chat_id")) or _string(message.get("chat_id"))
    source = RequirementSource(
        source_type="lark_bot_event",
        source_id=message_id,
        reference=message_id,
        title=_first_heading(content),
        content=content,
        identity="bot",
        metadata={
            "lark_command": "event consume im.message.receive_v1",
            "chat_id": chat_id,
            "sender_id": body.get("sender_id") or body.get("sender"),
            "create_time": body.get("create_time"),
            "event_key": body.get("event_key") or event.get("event_key"),
        },
        attachments=_attachments_from_message(body),
    )
    _ensure_source(source)
    return source


def content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if _looks_like_json(stripped):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
            return content_to_text(decoded)
        return stripped
    if isinstance(value, dict):
        for key in ("text", "title", "content", "markdown", "plain_text"):
            if key in value:
                text = content_to_text(value[key])
                if text:
                    return text
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        parts = [content_to_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value)


def _load_json(stdout: str) -> JsonValue:
    text = stdout.strip()
    if not text:
        raise LarkCliError("lark-cli 返回了空输出。")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        events = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise LarkCliError("lark-cli 输出不是有效 JSON 或 NDJSON。") from exc
        return events


def _events_from_payload(payload: JsonValue) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_dict(item) for item in payload if isinstance(item, dict)]
    data = _dict(payload.get("data")) if isinstance(payload, dict) else {}
    events = payload.get("events") if isinstance(payload, dict) else None
    events = events or data.get("events") or data.get("items") or []
    if isinstance(events, dict):
        events = [events]
    return [_dict(item) for item in events if isinstance(item, dict)]


def _messages_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = _dict(payload.get("data"))
    candidates = payload.get("messages") or data.get("messages") or data.get("items") or []
    if isinstance(candidates, dict):
        candidates = [candidates]
    return [_dict(item) for item in candidates if isinstance(item, dict)]


def _attachments_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for key in ("attachments", "files", "images", "resources"):
        value = message.get(key)
        if isinstance(value, list):
            attachments.extend(_dict(item) for item in value if isinstance(item, dict))
    content = content_to_text(message.get("content"))
    for token in ("[Image:", "[File:", "[Video:", "[Audio:"):
        if token in content:
            attachments.append({"kind": token.strip("[:"), "source": "message_content"})
    return attachments


def _embedded_resources_from_text(text: str) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for marker, kind in (
        ("<sheet", "sheet"),
        ("<bitable", "bitable"),
        ("<file", "file"),
        ("<image", "image"),
        ("![", "markdown_image"),
    ):
        if marker in text:
            resources.append({"kind": kind, "source": "document_content"})
    return resources


def _ensure_source(source: RequirementSource) -> None:
    try:
        source.ensure_content()
    except ValueError as exc:
        raise LarkCliError(str(exc)) from exc


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:120] or None
        return stripped[:120]
    return None


def _looks_like_json(text: str) -> bool:
    return (text.startswith("{") and text.endswith("}")) or (
        text.startswith("[") and text.endswith("]")
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
