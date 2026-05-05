from __future__ import annotations

import threading
import time
import unittest

from devflow.intake.lark_cli import event_to_source
from devflow.message_queue import UserMessageQueue


def bot_event(
    text: str,
    message_id: str = "om_evt",
    chat_id: str = "oc_123",
    sender_id: str = "ou_123",
) -> dict:
    return {
        "event": {
            "message_id": message_id,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "content": {"text": text},
        }
    }


class SameUserSerialTests(unittest.TestCase):
    def test_same_user_messages_processed_serially(self) -> None:
        processing_order: list[str] = []
        processing_lock = threading.Lock()

        def slow_processor(event: dict) -> str:
            source = event_to_source(event)
            text = source.content
            with processing_lock:
                processing_order.append(f"start:{text}")
            time.sleep(0.1)
            with processing_lock:
                processing_order.append(f"end:{text}")
            return text

        events = [
            bot_event("msg1", message_id="om_1", sender_id="ou_A"),
            bot_event("msg2", message_id="om_2", sender_id="ou_A"),
            bot_event("msg3", message_id="om_3", sender_id="ou_A"),
        ]

        results = list(
            UserMessageQueue(
                iter(events),
                max_queue_size=5,
                processor=slow_processor,
            )
        )

        self.assertEqual(len(results), 3)
        self.assertEqual(set(results), {"msg1", "msg2", "msg3"})

        for i in range(0, len(processing_order) - 1, 2):
            start = processing_order[i]
            end = processing_order[i + 1]
            self.assertTrue(start.startswith("start:"))
            self.assertTrue(end.startswith("end:"))
            self.assertEqual(start.split(":")[1], end.split(":")[1])

    def test_same_user_no_overlap(self) -> None:
        active_count = 0
        max_active = 0
        count_lock = threading.Lock()

        def processor(event: dict) -> str:
            nonlocal active_count, max_active
            with count_lock:
                active_count += 1
                max_active = max(max_active, active_count)
            time.sleep(0.1)
            with count_lock:
                active_count -= 1
            return event_to_source(event).content

        events = [
            bot_event(f"msg{i}", message_id=f"om_{i}", sender_id="ou_A")
            for i in range(4)
        ]

        list(
            UserMessageQueue(
                iter(events),
                max_queue_size=10,
                processor=processor,
            )
        )

        self.assertEqual(max_active, 1)


class DifferentUsersParallelTests(unittest.TestCase):
    def test_different_users_processed_in_parallel(self) -> None:
        active_count = 0
        max_active = 0
        count_lock = threading.Lock()

        def processor(event: dict) -> str:
            nonlocal active_count, max_active
            with count_lock:
                active_count += 1
                max_active = max(max_active, active_count)
            time.sleep(0.15)
            with count_lock:
                active_count -= 1
            return event_to_source(event).content

        events = [
            bot_event("user1_msg", message_id="om_1", sender_id="ou_1"),
            bot_event("user2_msg", message_id="om_2", sender_id="ou_2"),
            bot_event("user3_msg", message_id="om_3", sender_id="ou_3"),
        ]

        results = list(
            UserMessageQueue(
                iter(events),
                max_queue_size=5,
                processor=processor,
            )
        )

        self.assertEqual(len(results), 3)
        self.assertGreater(max_active, 1)

    def test_parallel_faster_than_serial(self) -> None:
        def processor(event: dict) -> str:
            time.sleep(0.1)
            return event_to_source(event).content

        events = [
            bot_event(f"msg{i}", message_id=f"om_{i}", sender_id=f"ou_{i}")
            for i in range(3)
        ]

        start = time.monotonic()
        list(
            UserMessageQueue(
                iter(events),
                max_queue_size=5,
                processor=processor,
            )
        )
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 0.35)


class QueueOverflowTests(unittest.TestCase):
    def test_overflow_drops_oldest(self) -> None:
        processed_ids: list[str] = []
        overflow_ids: list[str] = []

        def processor(event: dict) -> str:
            source = event_to_source(event)
            processed_ids.append(source.source_id)
            time.sleep(0.05)
            return source.source_id

        def on_overflow(dropped: dict) -> None:
            source = event_to_source(dropped)
            overflow_ids.append(source.source_id)

        events = [
            bot_event(f"msg{i}", message_id=f"om_{i}", sender_id="ou_A")
            for i in range(7)
        ]

        results = list(
            UserMessageQueue(
                iter(events),
                max_queue_size=5,
                processor=processor,
                on_queue_overflow=on_overflow,
            )
        )

        self.assertGreater(len(overflow_ids), 0)
        self.assertIn("om_0", overflow_ids)

    def test_overflow_callback_called(self) -> None:
        overflow_events: list[dict] = []

        def processor(event: dict) -> str:
            time.sleep(0.05)
            return "ok"

        def on_overflow(dropped: dict) -> None:
            overflow_events.append(dropped)

        events = [
            bot_event(f"msg{i}", message_id=f"om_{i}", sender_id="ou_A")
            for i in range(8)
        ]

        list(
            UserMessageQueue(
                iter(events),
                max_queue_size=5,
                processor=processor,
                on_queue_overflow=on_overflow,
            )
        )

        self.assertGreater(len(overflow_events), 0)
        for evt in overflow_events:
            source = event_to_source(evt)
            self.assertTrue(source.source_id.startswith("om_"))


class QueueSizeConfigurableTests(unittest.TestCase):
    def test_default_queue_size(self) -> None:
        overflow_count = 0

        def processor(event: dict) -> str:
            time.sleep(0.05)
            return "ok"

        def on_overflow(dropped: dict) -> None:
            nonlocal overflow_count
            overflow_count += 1

        events = [
            bot_event(f"msg{i}", message_id=f"om_{i}", sender_id="ou_A")
            for i in range(5)
        ]

        list(
            UserMessageQueue(
                iter(events),
                processor=processor,
                on_queue_overflow=on_overflow,
            )
        )

        self.assertEqual(overflow_count, 0)

    def test_custom_queue_size(self) -> None:
        overflow_count = 0

        def processor(event: dict) -> str:
            time.sleep(0.05)
            return "ok"

        def on_overflow(dropped: dict) -> None:
            nonlocal overflow_count
            overflow_count += 1

        events = [
            bot_event(f"msg{i}", message_id=f"om_{i}", sender_id="ou_A")
            for i in range(5)
        ]

        list(
            UserMessageQueue(
                iter(events),
                max_queue_size=2,
                processor=processor,
                on_queue_overflow=on_overflow,
            )
        )

        self.assertGreater(overflow_count, 0)

    def test_queue_size_one(self) -> None:
        overflow_count = 0

        def processor(event: dict) -> str:
            time.sleep(0.05)
            return "ok"

        def on_overflow(dropped: dict) -> None:
            nonlocal overflow_count
            overflow_count += 1

        events = [
            bot_event(f"msg{i}", message_id=f"om_{i}", sender_id="ou_A")
            for i in range(4)
        ]

        list(
            UserMessageQueue(
                iter(events),
                max_queue_size=1,
                processor=processor,
                on_queue_overflow=on_overflow,
            )
        )

        self.assertGreaterEqual(overflow_count, 2)


class EmptyAndSingleEventTests(unittest.TestCase):
    def test_empty_stream(self) -> None:
        results = list(
            UserMessageQueue(
                iter([]),
                max_queue_size=5,
                processor=lambda e: "ok",
            )
        )
        self.assertEqual(len(results), 0)

    def test_single_event(self) -> None:
        events = [bot_event("hello", message_id="om_1")]

        results = list(
            UserMessageQueue(
                iter(events),
                max_queue_size=5,
                processor=lambda e: event_to_source(e).content,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "hello")


class DifferentChatsIsolatedTests(unittest.TestCase):
    def test_same_sender_different_chats_are_parallel(self) -> None:
        active_count = 0
        max_active = 0
        count_lock = threading.Lock()

        def processor(event: dict) -> str:
            nonlocal active_count, max_active
            with count_lock:
                active_count += 1
                max_active = max(max_active, active_count)
            time.sleep(0.1)
            with count_lock:
                active_count -= 1
            return event_to_source(event).content

        events = [
            bot_event("msg1", message_id="om_1", chat_id="oc_A", sender_id="ou_X"),
            bot_event("msg2", message_id="om_2", chat_id="oc_B", sender_id="ou_X"),
        ]

        list(
            UserMessageQueue(
                iter(events),
                max_queue_size=5,
                processor=processor,
            )
        )

        self.assertGreater(max_active, 1)


if __name__ == "__main__":
    unittest.main()
