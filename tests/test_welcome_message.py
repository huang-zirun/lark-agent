from __future__ import annotations

import json
import subprocess
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from devflow.config import DevflowConfig, InteractionConfig, LarkConfig, LlmConfig, WorkspaceConfig
from devflow.intake.lark_cli import LarkCliError, send_bot_message, send_bot_text
from devflow.pipeline import _FIRST_INTERACTION_GUIDE, _seen_senders, build_welcome_card, process_bot_event
from uuid import uuid4


def _unique_out_dir() -> Path:
    base = Path(__file__).resolve().parents[1] / ".test-tmp"
    base.mkdir(exist_ok=True)
    unique = base / f"welcome-{uuid4().hex}"
    unique.mkdir(parents=True, exist_ok=True)
    return unique


class BuildWelcomeCardTests(unittest.TestCase):
    def test_returns_valid_card_structure(self) -> None:
        card = build_welcome_card()

        self.assertEqual(card["config"]["wide_screen_mode"], True)
        self.assertEqual(card["header"]["template"], "blue")
        self.assertEqual(card["header"]["title"]["tag"], "plain_text")
        self.assertEqual(card["header"]["title"]["content"], "🤖 DevFlow 已就绪")

        elements = card["elements"]
        self.assertTrue(len(elements) >= 5)

        div_tags = [e["tag"] for e in elements]
        self.assertIn("div", div_tags)
        self.assertIn("hr", div_tags)

        for element in elements:
            if element["tag"] == "div":
                text = element["text"]
                self.assertEqual(text["tag"], "lark_md")
                self.assertNotIn("\n- ", text["content"])

    def test_includes_workspace_config_when_provided(self) -> None:
        card = build_welcome_card(workspace_root="D:\\lark", default_repo="D:\\lark\\myrepo")

        elements = card["elements"]
        workspace_element = None
        for element in elements:
            if element["tag"] == "div":
                content = element["text"]["content"]
                if "工作区配置" in content:
                    workspace_element = element
                    break

        self.assertIsNotNone(workspace_element)
        content = workspace_element["text"]["content"]
        self.assertIn("D:\\lark", content)
        self.assertIn("myrepo", content)

    def test_omits_workspace_config_when_not_provided(self) -> None:
        card = build_welcome_card()

        for element in card["elements"]:
            if element["tag"] == "div":
                self.assertNotIn("工作区配置", element["text"]["content"])

    def test_uses_unicode_bullet_not_dash(self) -> None:
        card = build_welcome_card()

        all_content = ""
        for element in card["elements"]:
            if element["tag"] == "div":
                content = element["text"]["content"]
                self.assertNotIn("\n- ", content)
                all_content += content

        self.assertIn("•", all_content)

    def test_uses_lark_md_tag(self) -> None:
        card = build_welcome_card()

        for element in card["elements"]:
            if element["tag"] == "div":
                self.assertEqual(element["text"]["tag"], "lark_md")


class WelcomeMessageSkippedTests(unittest.TestCase):
    def test_skipped_when_default_chat_id_not_configured(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id=""),
        )

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            with patch("devflow.pipeline.send_bot_message") as mock_send:
                from devflow.pipeline import _send_welcome_message

                stderr = StringIO()
                with patch("sys.stderr", stderr):
                    _send_welcome_message()

        mock_send.assert_not_called()
        output = stderr.getvalue()
        self.assertIn("DevFlow 机器人已就绪", output)
        self.assertIn("default_chat_id", output)

    def test_skipped_when_config_load_fails(self) -> None:
        from devflow.config import ConfigError

        with patch("devflow.pipeline.load_config", side_effect=ConfigError("config not found")):
            with patch("devflow.pipeline.send_bot_message") as mock_send:
                from devflow.pipeline import _send_welcome_message

                stderr = StringIO()
                with patch("sys.stderr", stderr):
                    _send_welcome_message()

        mock_send.assert_not_called()
        output = stderr.getvalue()
        self.assertIn("DevFlow 机器人已就绪", output)
        self.assertIn("default_chat_id", output)

    def test_guidance_includes_feishu_hint(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id=""),
        )

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            with patch("devflow.pipeline.send_bot_message"):
                from devflow.pipeline import _send_welcome_message

                stderr = StringIO()
                with patch("sys.stderr", stderr):
                    _send_welcome_message()

        output = stderr.getvalue()
        self.assertIn("飞书", output)


class WelcomeMessageSentTests(unittest.TestCase):
    def test_sent_when_default_chat_id_configured(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id="oc_welcome_chat"),
        )

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            with patch("devflow.pipeline.send_bot_text") as mock_send:
                from devflow.pipeline import _send_welcome_message

                _send_welcome_message()

        mock_send.assert_called_once()
        args = mock_send.call_args
        self.assertEqual(args[0][0], "oc_welcome_chat")
        welcome_text = args[0][1]
        self.assertIn("🤖 DevFlow 已就绪", welcome_text)
        self.assertIn("【简介】", welcome_text)
        self.assertIn("【核心能力】", welcome_text)
        self.assertIn("【使用方法】", welcome_text)
        self.assertTrue(args[0][2].startswith("df-welcome-"))

    def test_send_failure_does_not_crash(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id="oc_welcome_chat"),
        )

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            with patch(
                "devflow.pipeline.send_bot_text",
                side_effect=LarkCliError("HTTP 400: forbidden"),
            ):
                from devflow.pipeline import _send_welcome_message

                stderr = StringIO()
                with patch("sys.stderr", stderr):
                    _send_welcome_message()

        self.assertIn("欢迎消息发送失败", stderr.getvalue())


class SendBotMessageTests(unittest.TestCase):
    def test_uses_im_send_command(self) -> None:
        calls = []

        def runner(args: list[str], timeout: int | None):
            calls.append((args, timeout))
            return {"ok": True}

        send_bot_message("oc_123", "interactive", '{"header":{}}', "key-1", runner=runner)

        args, timeout = calls[0]
        self.assertEqual(timeout, 120)
        self.assertEqual(
            args,
            [
                "im",
                "+messages-send",
                "--chat-id",
                "oc_123",
                "--msg-type",
                "interactive",
                "--content",
                '{"header":{}}',
                "--as",
                "bot",
                "--idempotency-key",
                "key-1",
            ],
        )


class SendBotTextTests(unittest.TestCase):
    def test_multiline_text_sent_as_json_content(self) -> None:
        calls = []

        def runner(args: list[str], timeout: int | None):
            calls.append((args, timeout))
            return {"ok": True}

        text = "第一行\n第二行"
        send_bot_text("oc_123", text, "key-1", runner=runner)

        args, timeout = calls[0]
        self.assertEqual(timeout, 120)
        self.assertNotIn("--text", args)
        self.assertIn("--content", args)
        self.assertIn("--msg-type", args)
        self.assertEqual(args[args.index("--msg-type") + 1], "text")
        content = json.loads(args[args.index("--content") + 1])
        self.assertEqual(content, {"text": text})
        self.assertNotIn("\n", subprocess.list2cmdline(args))


class FirstInteractionGuideTests(unittest.TestCase):
    def setUp(self) -> None:
        _seen_senders.clear()

    def _bot_event(self, text: str, sender_id: str = "ou_first_user", message_id: str = "om_first_evt") -> dict:
        return {
            "event": {
                "message_id": message_id,
                "chat_id": "oc_123",
                "sender_id": sender_id,
                "content": {"text": text},
            }
        }

    @patch("devflow.pipeline.send_stage_notification")
    def test_first_interaction_includes_guide_when_no_default_chat(self, _mock_notify) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id=""),
        )
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            from devflow.pipeline import process_bot_event

            process_bot_event(
                self._bot_event("目标：首次交互测试"),
                out_dir=_unique_out_dir(),
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到需求" in r[1]]
        self.assertEqual(len(confirm_replies), 1)
        self.assertIn(_FIRST_INTERACTION_GUIDE, confirm_replies[0][1])

    @patch("devflow.pipeline.send_stage_notification")
    def test_second_interaction_omits_guide(self, _mock_notify) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id=""),
        )
        replies = []
        out_dir = _unique_out_dir()

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            from devflow.pipeline import process_bot_event

            process_bot_event(
                self._bot_event("目标：首次\n用户：测试\n范围：CLI", message_id="om_first"),
                out_dir=out_dir,
                reply_sender=reply_sender,
            )
            process_bot_event(
                self._bot_event("目标：第二次\n用户：测试\n范围：CLI", message_id="om_second"),
                out_dir=out_dir,
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到需求" in r[1]]
        self.assertEqual(len(confirm_replies), 2)
        self.assertIn(_FIRST_INTERACTION_GUIDE, confirm_replies[0][1])
        self.assertNotIn(_FIRST_INTERACTION_GUIDE, confirm_replies[1][1])

    @patch("devflow.pipeline.send_stage_notification")
    def test_no_guide_when_default_chat_configured(self, _mock_notify) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id="oc_default"),
        )
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            from devflow.pipeline import process_bot_event

            process_bot_event(
                self._bot_event("目标：有默认聊天"),
                out_dir=_unique_out_dir(),
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到需求" in r[1]]
        self.assertEqual(len(confirm_replies), 1)
        self.assertNotIn(_FIRST_INTERACTION_GUIDE, confirm_replies[0][1])

    @patch("devflow.pipeline.send_stage_notification")
    def test_no_guide_when_no_sender_id(self, _mock_notify) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            interaction=InteractionConfig(default_chat_id=""),
        )
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        event_no_sender = {
            "event": {
                "message_id": "om_no_sender",
                "chat_id": "oc_123",
                "content": {"text": "目标：无发送者"},
            }
        }

        with patch("devflow.pipeline.load_config", return_value=fake_config):
            from devflow.pipeline import process_bot_event

            process_bot_event(
                event_no_sender,
                out_dir=_unique_out_dir(),
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到需求" in r[1]]
        self.assertEqual(len(confirm_replies), 1)
        self.assertNotIn(_FIRST_INTERACTION_GUIDE, confirm_replies[0][1])


if __name__ == "__main__":
    unittest.main()
