from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from devflow.config import ConfigError, DevflowConfig, InteractionConfig, LarkConfig, LlmConfig
from devflow.intake.lark_cli import LarkCliError
from devflow.pipeline import (
    STAGE_DISPLAY_NAMES,
    ThinkingTimer,
    _idempotency_key,
    _trigger_message_id,
    initial_stages,
    send_stage_notification,
    send_thinking_notification,
    set_stage_status,
)


def _fake_config(*, progress_notifications_enabled: bool = True) -> DevflowConfig:
    return DevflowConfig(
        llm=LlmConfig(provider="ark", api_key="test-key", model="test-model"),
        lark=LarkConfig(
            cli_version="1.0.23",
            app_id="cli_a",
            app_secret="test-secret",
            test_doc="doc_123",
        ),
        interaction=InteractionConfig(
            progress_notifications_enabled=progress_notifications_enabled,
        ),
    )


class StageStartedNotificationTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_started_format(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        set_stage_status(stages, "requirement_intake", "running")
        send_stage_notification(
            "om_test", "run-abc123", "requirement_intake", "started", stages,
        )
        mock_send.assert_called_once()
        args = mock_send.call_args
        self.assertEqual(args[0][0], "om_test")
        self.assertIn("需求分析", args[0][1])
        self.assertIn("进行中", args[0][1])
        self.assertIn("0/6", args[0][1])

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_started_shows_completed_count(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        set_stage_status(stages, "requirement_intake", "success")
        set_stage_status(stages, "solution_design", "success")
        set_stage_status(stages, "code_generation", "running")
        send_stage_notification(
            "om_test", "run-abc123", "code_generation", "started", stages,
        )
        args = mock_send.call_args
        self.assertIn("2/6", args[0][1])


class StageCompletedNotificationTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_completed_format(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        set_stage_status(stages, "requirement_intake", "success")
        send_stage_notification(
            "om_test", "run-abc123", "requirement_intake", "completed", stages,
        )
        mock_send.assert_called_once()
        args = mock_send.call_args
        self.assertEqual(args[0][0], "om_test")
        self.assertIn("需求分析", args[0][1])
        self.assertIn("已完成", args[0][1])


class StageFailedNotificationTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_failed_format(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        set_stage_status(stages, "requirement_intake", "failed", error="bad input")
        send_stage_notification(
            "om_test", "run-abc123", "requirement_intake", "failed", stages, error_summary="bad input",
        )
        mock_send.assert_called_once()
        args = mock_send.call_args
        self.assertEqual(args[0][0], "om_test")
        self.assertIn("需求分析", args[0][1])
        self.assertIn("失败", args[0][1])
        self.assertIn("bad input", args[0][1])
        self.assertIn("💡", args[0][1])
        self.assertIn("补充更具体的需求上下文", args[0][1])

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_failed_without_error_summary_uses_default(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        send_stage_notification(
            "om_test", "run-abc123", "code_generation", "failed", stages,
        )
        args = mock_send.call_args
        self.assertIn("未知错误", args[0][1])
        self.assertIn("💡", args[0][1])


class NotificationsDisabledTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_no_notification_when_disabled(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config(progress_notifications_enabled=False)
        stages = initial_stages()
        send_stage_notification(
            "om_test", "run-abc123", "requirement_intake", "started", stages,
        )
        mock_send.assert_not_called()


class IdempotencyKeyTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_uses_correct_idempotency_key(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        send_stage_notification(
            "om_test", "run-abc123", "code_generation", "started", stages,
        )
        args = mock_send.call_args
        idem_key = args[0][2]
        self.assertIn("stage-code_generation-started", idem_key)


class NotificationFailureTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply", side_effect=LarkCliError("network error"))
    @patch("devflow.pipeline.load_config")
    def test_notification_failure_does_not_crash(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        try:
            send_stage_notification(
                "om_test", "run-abc123", "requirement_intake", "started", stages,
            )
        except LarkCliError:
            self.fail("send_stage_notification should not propagate LarkCliError")


class StageDisplayNamesTests(unittest.TestCase):
    def test_all_stages_have_display_names(self) -> None:
        from devflow.pipeline import STAGE_NAMES
        for name in STAGE_NAMES:
            self.assertIn(name, STAGE_DISPLAY_NAMES)
            self.assertTrue(len(STAGE_DISPLAY_NAMES[name]) > 0)


class TriggerMessageIdTests(unittest.TestCase):
    def test_extracts_message_id_from_trigger(self) -> None:
        run_payload = {"trigger": {"message_id": "om_abc123"}}
        self.assertEqual(_trigger_message_id(run_payload), "om_abc123")

    def test_returns_empty_string_when_trigger_missing(self) -> None:
        self.assertEqual(_trigger_message_id({}), "")

    def test_returns_empty_string_when_message_id_missing(self) -> None:
        self.assertEqual(_trigger_message_id({"trigger": {}}), "")


class UnknownEventTypeTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_unknown_event_type_sends_nothing(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        stages = initial_stages()
        send_stage_notification(
            "om_test", "run-abc123", "requirement_intake", "unknown", stages,
        )
        mock_send.assert_not_called()


class ThinkingNotificationFormatTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_thinking_notification_contains_stage_name(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        send_thinking_notification("om_test", "run-abc123", "solution_design")
        mock_send.assert_called_once()
        args = mock_send.call_args
        self.assertEqual(args[0][0], "om_test")
        self.assertIn("🤔", args[0][1])
        self.assertIn("方案设计", args[0][1])
        self.assertIn("正在思考", args[0][1])

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_thinking_notification_all_stages(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        for stage_name, display_name in STAGE_DISPLAY_NAMES.items():
            mock_send.reset_mock()
            send_thinking_notification("om_test", "run-abc", stage_name)
            mock_send.assert_called_once()
            text = mock_send.call_args[0][1]
            self.assertIn(display_name, text)

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_thinking_notification_uses_idempotency_key(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        send_thinking_notification("om_test", "run-abc123", "code_generation")
        args = mock_send.call_args
        idem_key = args[0][2]
        self.assertIn("thinking-code_generation", idem_key)


class ThinkingNotificationDisabledTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_no_thinking_notification_when_disabled(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config(progress_notifications_enabled=False)
        send_thinking_notification("om_test", "run-abc123", "requirement_intake")
        mock_send.assert_not_called()

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_no_thinking_notification_on_config_error(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.side_effect = ConfigError("missing config")
        send_thinking_notification("om_test", "run-abc123", "requirement_intake")
        mock_send.assert_not_called()


class ThinkingNotificationFailureTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply", side_effect=LarkCliError("network error"))
    @patch("devflow.pipeline.load_config")
    def test_thinking_notification_failure_does_not_crash(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        try:
            send_thinking_notification("om_test", "run-abc123", "requirement_intake")
        except LarkCliError:
            self.fail("send_thinking_notification should not propagate LarkCliError")


class ThinkingTimerTests(unittest.TestCase):
    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_timer_fires_after_timeout(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        timer = ThinkingTimer("om_test", "run-abc", "solution_design", timeout_seconds=0.1)
        timer.start()
        time.sleep(0.3)
        mock_send.assert_called_once()
        text = mock_send.call_args[0][1]
        self.assertIn("⏳", text)
        self.assertIn("仍在处理中", text)

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_timer_cancelled_before_timeout(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        timer = ThinkingTimer("om_test", "run-abc", "solution_design", timeout_seconds=0.5)
        timer.start()
        timer.cancel()
        time.sleep(0.7)
        mock_send.assert_not_called()

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_timer_uses_idempotency_key(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        timer = ThinkingTimer("om_test", "run-abc", "code_review", timeout_seconds=0.1)
        timer.start()
        time.sleep(0.3)
        idem_key = mock_send.call_args[0][2]
        self.assertIn("timeout-code_review", idem_key)

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_timer_respects_disabled_config(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config(progress_notifications_enabled=False)
        timer = ThinkingTimer("om_test", "run-abc", "solution_design", timeout_seconds=0.1)
        timer.start()
        time.sleep(0.3)
        mock_send.assert_not_called()

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_timer_fired_flag(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        timer = ThinkingTimer("om_test", "run-abc", "solution_design", timeout_seconds=0.1)
        self.assertFalse(timer._fired)
        timer.start()
        time.sleep(0.3)
        self.assertTrue(timer._fired)

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_timer_does_not_fire_after_cancel(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        timer = ThinkingTimer("om_test", "run-abc", "solution_design", timeout_seconds=0.1)
        timer.start()
        timer.cancel()
        self.assertFalse(timer._fired)

    @patch("devflow.pipeline.send_bot_reply", side_effect=LarkCliError("network error"))
    @patch("devflow.pipeline.load_config")
    def test_timer_timeout_send_failure_does_not_crash(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.return_value = _fake_config()
        timer = ThinkingTimer("om_test", "run-abc", "solution_design", timeout_seconds=0.1)
        timer.start()
        time.sleep(0.3)
        self.assertTrue(timer._fired)

    @patch("devflow.pipeline.send_bot_reply")
    @patch("devflow.pipeline.load_config")
    def test_timer_config_error_does_not_crash(self, mock_load_config: MagicMock, mock_send: MagicMock) -> None:
        mock_load_config.side_effect = ConfigError("missing")
        timer = ThinkingTimer("om_test", "run-abc", "solution_design", timeout_seconds=0.1)
        timer.start()
        time.sleep(0.3)
        mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
