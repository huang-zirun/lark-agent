from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from devflow.checkpoint import parse_checkpoint_command, parse_system_command
from devflow.intake.lark_cli import event_to_source
from devflow.solution.workspace import parse_workspace_directive

AppendCallback = Callable[[dict[str, Any]], None]


def _is_command_event(event: dict[str, Any]) -> bool:
    source = event_to_source(event)
    content = source.content.strip()
    if not content:
        return False
    if content.startswith("/"):
        return parse_system_command(content) is not None
    if parse_checkpoint_command(content) is not None:
        return True
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()),
        "",
    )
    return bool(first_line and parse_workspace_directive(first_line) is not None)


class _BufferEntry:
    __slots__ = ("event", "deadline", "lock")

    def __init__(self, event: dict[str, Any], deadline: float) -> None:
        self.event = event
        self.deadline = deadline
        self.lock = threading.Lock()


class MessageBuffer:
    def __init__(
        self,
        events: Iterable[dict[str, Any]],
        *,
        merge_window_seconds: int = 5,
        on_append: AppendCallback | None = None,
    ) -> None:
        self._events = events
        self._merge_window_seconds = merge_window_seconds
        self._on_append = on_append
        self._buffers: dict[str, _BufferEntry] = {}
        self._lock = threading.Lock()
        self._ready: list[dict[str, Any]] = []
        self._ready_event = threading.Event()
        self._finished = False
        self._error: BaseException | None = None
        self._consumer_thread: threading.Thread | None = None

    def __iter__(self) -> Iterator[dict[str, Any]]:
        self._consumer_thread = threading.Thread(
            target=self._consume, daemon=True
        )
        self._consumer_thread.start()
        return self._drain()

    def _user_key(self, event: dict[str, Any]) -> str:
        source = event_to_source(event)
        chat_id = source.metadata.get("chat_id") or ""
        sender_id = source.metadata.get("sender_id") or ""
        return f"{chat_id}:{sender_id}"

    def _consume(self) -> None:
        try:
            for event in self._events:
                self._handle_event(event)
        except BaseException as exc:
            with self._lock:
                self._error = exc
        finally:
            with self._lock:
                for key in list(self._buffers):
                    entry = self._buffers.pop(key)
                    self._ready.append(entry.event)
                self._finished = True
            self._ready_event.set()

    def _handle_event(self, event: dict[str, Any]) -> None:
        now = time.monotonic()
        key = self._user_key(event)

        if _is_command_event(event):
            with self._lock:
                self._flush_expired(now)
                if key in self._buffers:
                    entry = self._buffers.pop(key)
                    self._ready.append(entry.event)
                self._ready.append(event)
            self._ready_event.set()
            return

        with self._lock:
            self._flush_expired(now)

            if key in self._buffers:
                entry = self._buffers[key]
                with entry.lock:
                    existing_source = event_to_source(entry.event)
                    new_source = event_to_source(event)
                    merged_content = existing_source.content + "\n" + new_source.content
                    entry.event = self._merge_event_content(
                        entry.event, merged_content
                    )
                    entry.deadline = now + self._merge_window_seconds
                if self._on_append is not None:
                    self._on_append(event)
            else:
                deadline = now + self._merge_window_seconds
                self._buffers[key] = _BufferEntry(event, deadline)

        self._ready_event.set()

    def _flush_expired(self, now: float) -> None:
        expired_keys = [
            k for k, v in self._buffers.items() if now >= v.deadline
        ]
        for key in expired_keys:
            entry = self._buffers.pop(key)
            self._ready.append(entry.event)

    def _drain(self) -> Iterator[dict[str, Any]]:
        while True:
            self._ready_event.wait(timeout=0.1)

            with self._lock:
                now = time.monotonic()
                self._flush_expired(now)
                batch = list(self._ready)
                self._ready.clear()
                done = self._finished and not self._buffers and not batch

            for event in batch:
                yield event

            if done:
                if self._error is not None:
                    raise self._error
                break

    @staticmethod
    def _merge_event_content(
        event: dict[str, Any], merged_content: str
    ) -> dict[str, Any]:
        import copy

        merged = copy.deepcopy(event)
        body = merged.get("event") or merged
        if "event" in merged and isinstance(merged["event"], dict):
            body = merged["event"]

        if "content" in body and isinstance(body["content"], dict):
            body["content"] = {"text": merged_content}
        elif "content" in body:
            body["content"] = merged_content
        elif "text" in body:
            body["text"] = merged_content
        elif "message_content" in body:
            body["message_content"] = merged_content
        else:
            body["content"] = {"text": merged_content}

        message = body.get("message")
        if isinstance(message, dict):
            if "content" in message:
                message["content"] = {"text": merged_content}

        return merged
