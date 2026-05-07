from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from devflow.intake.lark_cli import event_to_source


class UserMessageQueue:
    def __init__(
        self,
        events: Iterable[dict[str, Any]],
        *,
        max_queue_size: int = 5,
        processor: Callable[[dict[str, Any]], Any],
        on_queue_overflow: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._events = events
        self._max_queue_size = max_queue_size
        self._processor = processor
        self._on_queue_overflow = on_queue_overflow
        self._user_queues: dict[str, deque[dict[str, Any]]] = {}
        self._user_active: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._result_queue: deque[Any] = deque()
        self._result_event = threading.Event()
        self._finished = False
        self._error: BaseException | None = None
        self._active_count = 0
        self._active_zero = threading.Event()

    def __iter__(self) -> Iterator[Any]:
        consumer = threading.Thread(target=self._consume, daemon=True)
        consumer.start()
        return self._drain()

    def _user_key(self, event: dict[str, Any]) -> str:
        source = event_to_source(event)
        chat_id = source.metadata.get("chat_id") or ""
        sender_id = source.metadata.get("sender_id") or ""
        return f"{chat_id}:{sender_id}"

    def _consume(self) -> None:
        with ThreadPoolExecutor() as executor:
            try:
                for event in self._events:
                    self._enqueue_event(event, executor)
            except BaseException as exc:
                with self._lock:
                    self._error = exc
            finally:
                while True:
                    with self._lock:
                        if self._active_count == 0:
                            break
                    self._active_zero.wait(timeout=0.1)
                with self._lock:
                    self._finished = True
                self._result_event.set()

    def _enqueue_event(
        self, event: dict[str, Any], executor: ThreadPoolExecutor
    ) -> None:
        key = self._user_key(event)
        dropped = None
        with self._lock:
            if key not in self._user_queues:
                self._user_queues[key] = deque()
                self._user_active[key] = False

            queue = self._user_queues[key]
            if len(queue) >= self._max_queue_size:
                dropped = queue.popleft()
            queue.append(event)

            if not self._user_active[key]:
                self._user_active[key] = True
                self._active_count += 1
                self._active_zero.clear()
                executor.submit(self._process_user, key)

        if dropped is not None and self._on_queue_overflow is not None:
            self._on_queue_overflow(dropped)

    def _process_user(self, key: str) -> None:
        try:
            while True:
                with self._lock:
                    queue = self._user_queues[key]
                    if not queue:
                        self._user_active[key] = False
                        self._active_count -= 1
                        if self._active_count == 0:
                            self._active_zero.set()
                        return
                    event = queue.popleft()

                result = self._processor(event)

                with self._lock:
                    self._result_queue.append(result)
                self._result_event.set()
        except BaseException as exc:
            with self._lock:
                self._error = exc
                self._user_active[key] = False
                self._active_count -= 1
                if self._active_count == 0:
                    self._active_zero.set()
            self._result_event.set()

    def _drain(self) -> Iterator[Any]:
        while True:
            self._result_event.wait(timeout=0.1)
            self._result_event.clear()

            with self._lock:
                batch = list(self._result_queue)
                self._result_queue.clear()
                done = self._finished

            for result in batch:
                yield result

            if done:
                if self._error is not None:
                    raise self._error
                break
