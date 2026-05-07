from __future__ import annotations

import json
import unittest
from pathlib import Path
from uuid import uuid4

from devflow.checkpoint import (
    SCHEMA_VERSION,
    build_clarification_card,
    build_clarification_checkpoint,
    parse_clarification_reply,
    write_checkpoint,
    ClarificationReply,
)
from devflow.intake.models import RequirementSource
from devflow.pipeline import (
    find_waiting_clarification_run,
    maybe_process_checkpoint_event,
    process_bot_event,
    PipelineResult,
)


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp-clarification"


def temp_out_dir() -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / f"run-{uuid4().hex}"
    path.mkdir(parents=True)
    return path


def make_event_source(
    content: str = "test",
    *,
    chat_id: str = "oc_test",
    sender_id: str = "ou_test",
    source_id: str = "om_test",
) -> RequirementSource:
    return RequirementSource(
        source_type="lark_bot_text",
        source_id=source_id,
        reference="",
        title="",
        content=content,
        identity=None,
        metadata={"chat_id": chat_id, "sender_id": sender_id},
    )


def make_requirement_artifact(
    *,
    ready: bool = True,
    open_questions: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": "devflow.requirement.v1",
        "normalized_requirement": {
            "title": "测试需求",
            "background": [],
            "target_users": ["用户A"],
            "problem": ["问题1"],
            "goals": ["目标1"],
            "non_goals": [],
            "scope": ["范围1"],
        },
        "product_analysis": {
            "user_scenarios": [],
            "business_value": [],
            "evidence": [],
            "assumptions": [],
            "risks": [],
            "dependencies": [],
        },
        "acceptance_criteria": [],
        "open_questions": open_questions or [],
        "quality": {
            "completeness_score": 0.8 if ready else 0.4,
            "ambiguity_score": 0.2 if ready else 0.8,
            "ready_for_next_stage": ready,
            "warnings": [],
        },
        "sections": [],
        "implementation_hints": {},
        "source": {},
        "metadata": {},
        "prompt": {},
    }


class BuildClarificationCheckpointTests(unittest.TestCase):
    def test_produces_correct_structure(self) -> None:
        run_payload = {"run_id": "run_abc"}
        open_questions = [
            {"field": "target_users", "question": "目标用户是谁？"},
            {"field": "scope", "question": "首版范围是什么？"},
        ]
        checkpoint = build_clarification_checkpoint(run_payload, open_questions)

        self.assertEqual(checkpoint["schema_version"], SCHEMA_VERSION)
        self.assertEqual(checkpoint["run_id"], "run_abc")
        self.assertEqual(checkpoint["stage"], "clarification")
        self.assertEqual(checkpoint["status"], "waiting_clarification")
        self.assertEqual(checkpoint["attempt"], 1)
        self.assertIsNone(checkpoint["reviewer"])
        self.assertIsNone(checkpoint["decision"])
        self.assertIsNone(checkpoint["reject_reason"])
        self.assertIsNone(checkpoint["blocked_reason"])
        self.assertFalse(checkpoint["continue_requested"])
        self.assertEqual(checkpoint["artifact_history"], [])
        self.assertEqual(len(checkpoint["open_questions"]), 2)
        self.assertEqual(checkpoint["open_questions"][0]["field"], "target_users")
        self.assertIn("updated_at", checkpoint)

    def test_empty_open_questions(self) -> None:
        checkpoint = build_clarification_checkpoint({"run_id": "run_empty"}, [])
        self.assertEqual(checkpoint["open_questions"], [])


class BuildClarificationCardTests(unittest.TestCase):
    def test_has_orange_header(self) -> None:
        card = build_clarification_card(
            {"run_id": "run_card"},
            [{"field": "scope", "question": "范围是什么？"}],
        )
        header = card["header"]
        self.assertEqual(header["template"], "orange")
        self.assertEqual(header["title"]["content"], "🔍 需求待澄清")

    def test_lists_questions(self) -> None:
        questions = [
            {"field": "target_users", "question": "目标用户是谁？"},
            {"field": "scope", "question": "首版范围是什么？"},
        ]
        card = build_clarification_card({"run_id": "run_card"}, questions)
        content = json.dumps(card, ensure_ascii=False)
        self.assertIn("Q1", content)
        self.assertIn("Q2", content)
        self.assertIn("目标用户是谁？", content)
        self.assertIn("首版范围是什么？", content)

    def test_has_operation_guide(self) -> None:
        card = build_clarification_card(
            {"run_id": "run_card"},
            [{"field": "scope", "question": "范围？"}],
        )
        content = json.dumps(card, ensure_ascii=False)
        self.assertIn("继续", content)
        self.assertIn("跳过澄清", content)

    def test_empty_questions_shows_placeholder(self) -> None:
        card = build_clarification_card({"run_id": "run_card"}, [])
        content = json.dumps(card, ensure_ascii=False)
        self.assertIn("暂无待澄清问题", content)


class ParseClarificationReplyTests(unittest.TestCase):
    def test_skip_chinese(self) -> None:
        reply = parse_clarification_reply("继续")
        self.assertEqual(reply.action, "skip")
        self.assertIsNone(reply.text)

    def test_skip_english(self) -> None:
        reply = parse_clarification_reply("skip")
        self.assertEqual(reply.action, "skip")

    def test_skip_chinese_alt(self) -> None:
        reply = parse_clarification_reply("跳过")
        self.assertEqual(reply.action, "skip")

    def test_skip_with_whitespace(self) -> None:
        reply = parse_clarification_reply("  继续  ")
        self.assertEqual(reply.action, "skip")

    def test_answer_text(self) -> None:
        reply = parse_clarification_reply("目标用户是产品经理")
        self.assertEqual(reply.action, "answer")
        self.assertEqual(reply.text, "目标用户是产品经理")

    def test_answer_with_whitespace(self) -> None:
        reply = parse_clarification_reply("  这是我的回答  ")
        self.assertEqual(reply.action, "answer")
        self.assertEqual(reply.text, "这是我的回答")


class ClarificationReplyDataclassTests(unittest.TestCase):
    def test_frozen(self) -> None:
        reply = ClarificationReply(action="skip")
        with self.assertRaises(AttributeError):
            reply.action = "answer"

    def test_answer_reply(self) -> None:
        reply = ClarificationReply(action="answer", text="some text")
        self.assertEqual(reply.action, "answer")
        self.assertEqual(reply.text, "some text")


class FindWaitingClarificationRunTests(unittest.TestCase):
    def test_finds_matching_run(self) -> None:
        out_dir = temp_out_dir()
        run_dir = out_dir / "run_clarify"
        run_dir.mkdir()
        checkpoint = build_clarification_checkpoint(
            {"run_id": "run_clarify"},
            [{"field": "scope", "question": "范围？"}],
        )
        write_checkpoint(run_dir, checkpoint)
        run_payload = {
            "run_id": "run_clarify",
            "trigger": {"chat_id": "oc_test", "sender_id": "ou_test"},
        }
        (run_dir / "run.json").write_text(
            json.dumps(run_payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        event_source = make_event_source()
        result = find_waiting_clarification_run(out_dir, event_source)
        self.assertIsNotNone(result)
        self.assertEqual(result, run_dir)

    def test_no_match_different_user(self) -> None:
        out_dir = temp_out_dir()
        run_dir = out_dir / "run_other"
        run_dir.mkdir()
        checkpoint = build_clarification_checkpoint(
            {"run_id": "run_other"},
            [{"field": "scope", "question": "范围？"}],
        )
        write_checkpoint(run_dir, checkpoint)
        run_payload = {
            "run_id": "run_other",
            "trigger": {"chat_id": "oc_other", "sender_id": "ou_other"},
        }
        (run_dir / "run.json").write_text(
            json.dumps(run_payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        event_source = make_event_source()
        result = find_waiting_clarification_run(out_dir, event_source)
        self.assertIsNone(result)

    def test_no_match_non_clarification_status(self) -> None:
        out_dir = temp_out_dir()
        run_dir = out_dir / "run_approved"
        run_dir.mkdir()
        checkpoint = {
            "schema_version": SCHEMA_VERSION,
            "run_id": "run_approved",
            "stage": "solution_design",
            "status": "approved",
        }
        write_checkpoint(run_dir, checkpoint)
        run_payload = {
            "run_id": "run_approved",
            "trigger": {"chat_id": "oc_test", "sender_id": "ou_test"},
        }
        (run_dir / "run.json").write_text(
            json.dumps(run_payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        event_source = make_event_source()
        result = find_waiting_clarification_run(out_dir, event_source)
        self.assertIsNone(result)

    def test_empty_out_dir(self) -> None:
        out_dir = temp_out_dir()
        event_source = make_event_source()
        result = find_waiting_clarification_run(out_dir, event_source)
        self.assertIsNone(result)


class ProcessBotEventClarificationTests(unittest.TestCase):
    def test_pauses_when_open_questions_and_not_ready(self) -> None:
        out_dir = temp_out_dir()
        open_questions = [
            {"field": "target_users", "question": "目标用户是谁？"},
        ]
        artifact = make_requirement_artifact(ready=False, open_questions=open_questions)

        def build_artifact(_source):
            return artifact

        replies: list[str] = []
        cards: list[dict] = []

        def reply_sender(_msg_id, text, _key):
            replies.append(text)

        def card_sender(_msg_id, card, _key):
            cards.append(card)

        event = {
            "event": {
                "message_id": "om_test",
                "chat_id": "oc_test",
                "sender_id": "ou_test",
                "content": {"text": "创建一个小游戏"},
            }
        }

        result = process_bot_event(
            event,
            out_dir=out_dir,
            build_artifact=build_artifact,
            reply_sender=reply_sender,
            card_reply_sender=card_sender,
        )

        self.assertEqual(result.status, "waiting_clarification")
        self.assertTrue(any("需求待澄清" in json.dumps(c, ensure_ascii=False) for c in cards))

    def test_continues_normally_when_ready(self) -> None:
        out_dir = temp_out_dir()
        artifact = make_requirement_artifact(ready=True, open_questions=[])

        def build_artifact(_source):
            return artifact

        cards: list[dict] = []

        def card_sender(_msg_id, card, _key):
            cards.append(card)

        event = {
            "event": {
                "message_id": "om_test2",
                "chat_id": "oc_test",
                "sender_id": "ou_test2",
                "content": {"text": "创建一个小游戏"},
            }
        }

        result = process_bot_event(
            event,
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
        )

        self.assertNotEqual(result.status, "waiting_clarification")

    def test_continues_normally_when_ready_with_questions(self) -> None:
        out_dir = temp_out_dir()
        open_questions = [
            {"field": "scope", "question": "范围？"},
        ]
        artifact = make_requirement_artifact(ready=True, open_questions=open_questions)

        def build_artifact(_source):
            return artifact

        cards: list[dict] = []

        def card_sender(_msg_id, card, _key):
            cards.append(card)

        event = {
            "event": {
                "message_id": "om_test3",
                "chat_id": "oc_test",
                "sender_id": "ou_test3",
                "content": {"text": "创建一个小游戏"},
            }
        }

        result = process_bot_event(
            event,
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
        )

        self.assertNotEqual(result.status, "waiting_clarification")


class ClarificationReplyRoutingTests(unittest.TestCase):
    def _setup_clarification_run(self, out_dir: Path) -> Path:
        run_dir = out_dir / "run_clarify_route"
        run_dir.mkdir(parents=True, exist_ok=True)
        open_questions = [
            {"field": "target_users", "question": "目标用户是谁？"},
            {"field": "scope", "question": "首版范围是什么？"},
        ]
        checkpoint = build_clarification_checkpoint(
            {"run_id": "run_clarify_route"},
            open_questions,
        )
        write_checkpoint(run_dir, checkpoint)
        artifact = make_requirement_artifact(ready=False, open_questions=open_questions)
        (run_dir / "requirement.json").write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        run_payload = {
            "run_id": "run_clarify_route",
            "status": "waiting_clarification",
            "requirement_artifact": str(run_dir / "requirement.json"),
            "trigger": {"chat_id": "oc_test", "sender_id": "ou_test"},
            "stages": [
                {"name": "requirement_intake", "status": "success"},
                {"name": "solution_design", "status": "pending"},
                {"name": "code_generation", "status": "pending"},
                {"name": "test_generation", "status": "pending"},
                {"name": "code_review", "status": "pending"},
                {"name": "delivery", "status": "pending"},
            ],
        }
        (run_dir / "run.json").write_text(
            json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return run_dir

    def test_skip_clarification_resolves(self) -> None:
        out_dir = temp_out_dir()
        run_dir = self._setup_clarification_run(out_dir)

        event_source = make_event_source(content="继续")
        replies: list[str] = []

        def reply_sender(_msg_id, text, _key):
            replies.append(text)

        result = maybe_process_checkpoint_event(
            event_source,
            out_dir=out_dir,
            reply_sender=reply_sender,
            card_reply_sender=lambda *_: None,
        )

        self.assertIsNotNone(result)
        self.assertNotEqual(result.status, "waiting_clarification")
        self.assertTrue(any("跳过需求澄清" in r for r in replies))

        requirement = json.loads(
            (run_dir / "requirement.json").read_text(encoding="utf-8")
        )
        for q in requirement["open_questions"]:
            if isinstance(q, dict):
                self.assertEqual(q.get("answer"), "__skipped__")
        self.assertTrue(requirement["quality"]["ready_for_next_stage"])

    def test_answer_clarification_resolves(self) -> None:
        out_dir = temp_out_dir()
        run_dir = self._setup_clarification_run(out_dir)

        event_source = make_event_source(content="目标用户是产品经理")
        replies: list[str] = []

        def reply_sender(_msg_id, text, _key):
            replies.append(text)

        result = maybe_process_checkpoint_event(
            event_source,
            out_dir=out_dir,
            reply_sender=reply_sender,
            card_reply_sender=lambda *_: None,
        )

        self.assertIsNotNone(result)
        self.assertTrue(any("澄清回复" in r for r in replies))

        requirement = json.loads(
            (run_dir / "requirement.json").read_text(encoding="utf-8")
        )
        first_question = requirement["open_questions"][0]
        self.assertEqual(first_question.get("answer"), "目标用户是产品经理")

    def test_no_clarification_run_returns_none(self) -> None:
        out_dir = temp_out_dir()
        event_source = make_event_source(content="普通消息")
        result = maybe_process_checkpoint_event(
            event_source,
            out_dir=out_dir,
            reply_sender=lambda *_: None,
            card_reply_sender=lambda *_: None,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
