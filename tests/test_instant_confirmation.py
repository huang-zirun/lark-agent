from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from devflow.checkpoint import build_solution_review_checkpoint, write_checkpoint
from devflow.intake.lark_cli import LarkCliError
from devflow.pipeline import _idempotency_key, process_bot_event


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


@contextmanager
def temp_run_dir():
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    unique_dir = TEST_TMP_ROOT / f"confirm-{uuid4().hex}"
    unique_dir.mkdir(parents=True, exist_ok=True)
    yield str(unique_dir)


def bot_event(text: str, message_id: str = "om_evt") -> dict:
    return {
        "event": {
            "message_id": message_id,
            "chat_id": "oc_123",
            "sender_id": "ou_123",
            "content": {"text": text},
        }
    }


class InstantConfirmationTests(unittest.TestCase):
    @patch("devflow.pipeline.send_stage_notification")
    def test_confirmation_reply_sent_for_new_requirement(self, _mock_notify) -> None:
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：构建一键启动\n用户：产品经理\n范围：CLI"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到需求" in r[1]]
        self.assertEqual(len(confirm_replies), 1)
        self.assertEqual(confirm_replies[0][0], "om_evt")
        self.assertIn("正在分析中", confirm_replies[0][1])
        self.assertIn(result.run_id, confirm_replies[0][1])

    @patch("devflow.pipeline.send_stage_notification")
    def test_confirmation_reply_uses_correct_idempotency_key(self, _mock_notify) -> None:
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：验证幂等键\n用户：测试\n范围：CLI"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到需求" in r[1]]
        expected_key = _idempotency_key(result.run_id, "confirm")
        self.assertEqual(confirm_replies[0][2], expected_key)
        self.assertTrue(expected_key.startswith("df-"))
        self.assertIn("confirm", expected_key)

    @patch("devflow.pipeline.send_stage_notification")
    def test_confirmation_failure_does_not_block_processing(self, _mock_notify) -> None:
        call_count = 0

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            nonlocal call_count
            call_count += 1
            if "收到需求" in text:
                raise LarkCliError("网络超时")

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：容错测试\n用户：测试\n范围：CLI"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                reply_sender=reply_sender,
            )

        self.assertEqual(result.status, "success")
        self.assertGreater(call_count, 1)

    def test_confirmation_reply_sent_for_checkpoint_command(self) -> None:
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            run_id = f"run_confirm_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [
                    {"name": name, "status": "pending"}
                    for name in [
                        "requirement_intake",
                        "solution_design",
                        "code_generation",
                        "test_generation",
                        "code_review",
                        "delivery",
                    ]
                ],
            }
            (run_dir / "run.json").write_text(
                json.dumps(run_payload), encoding="utf-8"
            )
            write_checkpoint(
                run_dir,
                build_solution_review_checkpoint(
                    run_payload,
                    run_dir / "solution.json",
                    run_dir / "solution.md",
                ),
            )

            process_bot_event(
                bot_event(f"Approve {run_id}"),
                out_dir=Path(temp_dir),
                analyzer="llm",
                model="unused-model",
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到" in r[1] and "指令" in r[1]]
        self.assertEqual(len(confirm_replies), 1)
        self.assertEqual(confirm_replies[0][0], "om_evt")
        self.assertIn("继续", confirm_replies[0][1])

    def test_checkpoint_confirmation_uses_correct_idempotency_key(self) -> None:
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            run_id = f"run_cmdkey_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [
                    {"name": name, "status": "pending"}
                    for name in [
                        "requirement_intake",
                        "solution_design",
                        "code_generation",
                        "test_generation",
                        "code_review",
                        "delivery",
                    ]
                ],
            }
            (run_dir / "run.json").write_text(
                json.dumps(run_payload), encoding="utf-8"
            )
            write_checkpoint(
                run_dir,
                build_solution_review_checkpoint(
                    run_payload,
                    run_dir / "solution.json",
                    run_dir / "solution.md",
                ),
            )

            process_bot_event(
                bot_event(f"Approve {run_id}"),
                out_dir=Path(temp_dir),
                analyzer="llm",
                model="unused-model",
                reply_sender=reply_sender,
            )

        confirm_replies = [r for r in replies if "收到" in r[1] and "指令" in r[1]]
        expected_key = _idempotency_key(run_id, "cmd-confirm")
        self.assertEqual(confirm_replies[0][2], expected_key)
        self.assertTrue(expected_key.startswith("df-"))
        self.assertIn("cmd-confirm", expected_key)

    def test_checkpoint_confirmation_failure_does_not_block_processing(self) -> None:
        call_count = 0

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            nonlocal call_count
            call_count += 1
            if "收到" in text and "指令" in text:
                raise LarkCliError("网络超时")

        with temp_run_dir() as temp_dir:
            run_id = f"run_cmdfail_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [
                    {"name": name, "status": "pending"}
                    for name in [
                        "requirement_intake",
                        "solution_design",
                        "code_generation",
                        "test_generation",
                        "code_review",
                        "delivery",
                    ]
                ],
            }
            (run_dir / "run.json").write_text(
                json.dumps(run_payload), encoding="utf-8"
            )
            write_checkpoint(
                run_dir,
                build_solution_review_checkpoint(
                    run_payload,
                    run_dir / "solution.json",
                    run_dir / "solution.md",
                ),
            )

            result = process_bot_event(
                bot_event(f"Approve {run_id}"),
                out_dir=Path(temp_dir),
                analyzer="llm",
                model="unused-model",
                reply_sender=reply_sender,
            )

        self.assertEqual(result.status, "approved")
        self.assertGreater(call_count, 1)

    @patch("devflow.pipeline.send_stage_notification")
    def test_no_confirmation_when_reply_sender_is_none(self, _mock_notify) -> None:
        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：无回复发送器\n用户：测试\n范围：CLI"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                reply_sender=None,
            )

        self.assertEqual(result.status, "success")


if __name__ == "__main__":
    unittest.main()
