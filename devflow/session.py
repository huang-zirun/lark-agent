from __future__ import annotations

import threading
import time
from dataclasses import dataclass

TERMINAL_STATUSES = frozenset({
    "success",
    "failed",
    "delivered",
    "rejected",
})

ACTIVE_STATUSES = frozenset({
    "running",
    "blocked",
    "waiting_approval",
    "waiting_approval_with_warnings",
    "waiting_clarification",
    "waiting_code_review",
})


@dataclass(slots=True)
class SessionInfo:
    run_id: str
    status: str
    last_updated: float


class SessionManager:
    def __init__(
        self,
        *,
        session_timeout_seconds: int = 1800,
    ) -> None:
        self._session_timeout_seconds = session_timeout_seconds
        self._sessions: dict[str, SessionInfo] = {}
        self._lock = threading.Lock()

    def _key(self, chat_id: str, sender_id: str) -> str:
        return f"{chat_id}:{sender_id}"

    def _purge_expired(self, now: float) -> None:
        expired = [
            k for k, v in self._sessions.items()
            if now - v.last_updated > self._session_timeout_seconds
        ]
        for k in expired:
            del self._sessions[k]

    def register(
        self, chat_id: str, sender_id: str, run_id: str, status: str
    ) -> None:
        key = self._key(chat_id, sender_id)
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            self._sessions[key] = SessionInfo(
                run_id=run_id,
                status=status,
                last_updated=now,
            )

    def unregister(self, chat_id: str, sender_id: str) -> None:
        key = self._key(chat_id, sender_id)
        with self._lock:
            self._sessions.pop(key, None)

    def lookup(
        self, chat_id: str, sender_id: str
    ) -> SessionInfo | None:
        key = self._key(chat_id, sender_id)
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            return self._sessions.get(key)

    def update_status(
        self, chat_id: str, sender_id: str, status: str
    ) -> None:
        key = self._key(chat_id, sender_id)
        now = time.monotonic()
        with self._lock:
            info = self._sessions.get(key)
            if info is None:
                raise KeyError(f"会话 {key} 不存在")
            info.status = status
            info.last_updated = now
