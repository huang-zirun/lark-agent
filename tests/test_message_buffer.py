from __future__ import annotations

import time
import unittest

from devflow.intake.lark_cli import event_to_source
from devflow.message_buffer import MessageBuffer


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


class MessageBufferMergeTests(unittest.TestCase):
    def test_messages_within_merge_window_are_merged(self) -> None:
        events = [
            bot_event("第一行", message_id="om_1"),
            bot_event("第二行", message_id="om_2"),
        ]

        results = list(
            MessageBuffer(
                iter(events),
                merge_window_seconds=5,
            )
        )

        self.assertEqual(len(results), 1)
        source = event_to_source(results[0])
        self.assertIn("第一行", source.content)
        self.assertIn("第二行", source.content)

    def test_workspace_directive_flushes_buffered_requirement(self) -> None:
        appended_events = []
        events = [
            bot_event("我想要制作一个贪吃蛇小游戏，夏天主题", message_id="om_1"),
            bot_event("新项目：snake-game", message_id="om_2"),
        ]

        results = list(
            MessageBuffer(
                iter(events),
                merge_window_seconds=5,
                on_append=appended_events.append,
            )
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(
            event_to_source(results[0]).content,
            "我想要制作一个贪吃蛇小游戏，夏天主题",
        )
        self.assertEqual(event_to_source(results[1]).content, "新项目：snake-game")
        self.assertEqual(appended_events, [])

    def test_messages_outside_merge_window_create_separate_events(self) -> None:
        def delayed_events():
            yield bot_event("消息A", message_id="om_1")
            time.sleep(0.4)
            yield bot_event("消息B", message_id="om_2")

        results = list(
            MessageBuffer(
                delayed_events(),
                merge_window_seconds=0,
            )
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(event_to_source(results[0]).content, "消息A")
        self.assertEqual(event_to_source(results[1]).content, "消息B")

    def test_different_users_are_isolated(self) -> None:
        events = [
            bot_event("用户1消息", message_id="om_1", sender_id="ou_1"),
            bot_event("用户2消息", message_id="om_2", sender_id="ou_2"),
        ]

        results = list(
            MessageBuffer(
                iter(events),
                merge_window_seconds=5,
            )
        )

        self.assertEqual(len(results), 2)
        contents = [event_to_source(r).content for r in results]
        self.assertIn("用户1消息", contents)
        self.assertIn("用户2消息", contents)

    def test_merge_window_is_configurable(self) -> None:
        def timed_events():
            yield bot_event("快速A", message_id="om_1")
            time.sleep(0.15)
            yield bot_event("快速B", message_id="om_2")

        results_short = list(
            MessageBuffer(
                timed_events(),
                merge_window_seconds=0,
            )
        )
        self.assertEqual(len(results_short), 2)

        results_long = list(
            MessageBuffer(
                timed_events(),
                merge_window_seconds=5,
            )
        )
        self.assertEqual(len(results_long), 1)

    def test_on_append_callback_is_called(self) -> None:
        appended_events = []

        def on_append(event: dict) -> None:
            appended_events.append(event)

        events = [
            bot_event("首条", message_id="om_1"),
            bot_event("追加", message_id="om_2"),
        ]

        list(
            MessageBuffer(
                iter(events),
                merge_window_seconds=5,
                on_append=on_append,
            )
        )

        self.assertEqual(len(appended_events), 1)
        source = event_to_source(appended_events[0])
        self.assertEqual(source.content, "追加")

    def test_single_message_passes_through(self) -> None:
        events = [bot_event("只有一条", message_id="om_1")]

        results = list(
            MessageBuffer(
                iter(events),
                merge_window_seconds=5,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(event_to_source(results[0]).content, "只有一条")

    def test_different_chats_are_isolated(self) -> None:
        events = [
            bot_event("聊天1消息", message_id="om_1", chat_id="oc_A"),
            bot_event("聊天2消息", message_id="om_2", chat_id="oc_B"),
        ]

        results = list(
            MessageBuffer(
                iter(events),
                merge_window_seconds=5,
            )
        )

        self.assertEqual(len(results), 2)

    def test_three_messages_merged_in_order(self) -> None:
        events = [
            bot_event("第一", message_id="om_1"),
            bot_event("第二", message_id="om_2"),
            bot_event("第三", message_id="om_3"),
        ]

        results = list(
            MessageBuffer(
                iter(events),
                merge_window_seconds=5,
            )
        )

        self.assertEqual(len(results), 1)
        source = event_to_source(results[0])
        parts = source.content.split("\n")
        self.assertEqual(parts, ["第一", "第二", "第三"])


if __name__ == "__main__":
    unittest.main()
