from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from devflow.checkpoint import (
    build_clarification_checkpoint,
    build_solution_review_checkpoint,
    write_checkpoint,
)
from devflow.intake.models import RequirementSource
from devflow.pipeline import (
    PipelineResult,
    _append_to_active_requirement,
    _route_active_session,
    _update_session_from_result,
    process_bot_event,
)
from devflow.session import SessionManager


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp-session"


def temp_out_dir() -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / f"run-{uuid4().hex}"
    path.mkdir(parents=True)
    return path


def bot_event(
    text: str,
    *,
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


def make_event_source(
    content: str = "test",
    *,
    chat_id: str = "oc_123",
    sender_id: str = "ou_123",
    source_id: str = "om_evt",
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
    raw_content: str = "",
) -> dict:
    return {
        "schema_version": "devflow.requirement.v1",
        "metadata": {"agent": "ProductRequirementAnalyst"},
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
        "source_summary": {"raw_content": raw_content},
        "sections": [],
        "implementation_hints": {},
        "source": {},
        "prompt": {},
    }


def _write_run_files(
    run_dir: Path,
    run_id: str,
    *,
    status: str = "running",
    chat_id: str = "oc_123",
    sender_id: str = "ou_123",
    requirement_artifact: dict | None = None,
    checkpoint_status: str | None = None,
    checkpoint: dict | None = None,
    stages: list[dict] | None = None,
) -> dict:
    requirement_path = run_dir / "requirement.json"
    if requirement_artifact is not None:
        requirement_path.write_text(
            json.dumps(requirement_artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    default_stages = [
        {"name": "requirement_intake", "status": "success"},
        {"name": "solution_design", "status": "pending"},
        {"name": "code_generation", "status": "pending"},
        {"name": "test_generation", "status": "pending"},
        {"name": "code_review", "status": "pending"},
        {"name": "delivery", "status": "pending"},
    ]
    run_payload = {
        "schema_version": "devflow.pipeline_run.v1",
        "run_id": run_id,
        "status": status,
        "run_dir": str(run_dir),
        "run_path": str(run_dir / "run.json"),
        "trigger": {"chat_id": chat_id, "sender_id": sender_id},
        "detected_input": {"kind": "inline_text", "value": "测试需求"},
        "stages": stages if stages is not None else default_stages,
    }
    if requirement_artifact is not None:
        run_payload["requirement_artifact"] = str(requirement_path)
    if checkpoint_status is not None:
        run_payload["checkpoint_status"] = checkpoint_status
    (run_dir / "run.json").write_text(
        json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if checkpoint is not None:
        write_checkpoint(run_dir, checkpoint)
    return run_payload


class ActiveRunAppendTests(unittest.TestCase):
    def test_supplementary_message_appended_to_running_session(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()
        run_id = f"run_append_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        artifact = make_requirement_artifact(ready=True, raw_content="贪吃蛇游戏")
        _write_run_files(
            run_dir, run_id, status="running", requirement_artifact=artifact,
            stages=[
                {"name": "requirement_intake", "status": "running"},
                {"name": "solution_design", "status": "pending"},
                {"name": "code_generation", "status": "pending"},
                {"name": "test_generation", "status": "pending"},
                {"name": "code_review", "status": "pending"},
                {"name": "delivery", "status": "pending"},
            ],
        )
        session.register("oc_123", "ou_123", run_id, "running")

        info = session.lookup("oc_123", "ou_123")
        self.assertIsNotNone(info)
        self.assertEqual(info.run_id, run_id)

        replies: list[tuple[str, str, str]] = []

        def reply_sender(msg_id: str, text: str, key: str):
            replies.append((msg_id, text, key))

        event_source = make_event_source(content="春天主题", source_id="om_second")
        result = _route_active_session(
            event_source,
            session=session,
            out_dir=out_dir,
            reply_sender=reply_sender,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "appended")
        self.assertEqual(result.run_id, run_id)

        updated_requirement = json.loads(
            (run_dir / "requirement.json").read_text(encoding="utf-8")
        )
        raw = updated_requirement["source_summary"]["raw_content"]
        self.assertIn("贪吃蛇游戏", raw)
        self.assertIn("春天主题", raw)

        history = updated_requirement.get("input_history") or []
        supplement_entries = [h for h in history if h.get("mode") == "supplement"]
        self.assertEqual(len(supplement_entries), 1)
        self.assertEqual(supplement_entries[0]["text"], "春天主题")

        self.assertTrue(any("已追加" in r[1] for r in replies))

        info_after = session.lookup("oc_123", "ou_123")
        self.assertIsNotNone(info_after)
        self.assertEqual(info_after.run_id, run_id)

    def test_no_new_run_created_when_appending(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()
        run_id = f"run_no_new_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        artifact = make_requirement_artifact(ready=True, raw_content="初始需求")
        _write_run_files(
            run_dir, run_id, status="running", requirement_artifact=artifact,
            stages=[
                {"name": "requirement_intake", "status": "running"},
                {"name": "solution_design", "status": "pending"},
                {"name": "code_generation", "status": "pending"},
                {"name": "test_generation", "status": "pending"},
                {"name": "code_review", "status": "pending"},
                {"name": "delivery", "status": "pending"},
            ],
        )
        session.register("oc_123", "ou_123", run_id, "running")

        event_source = make_event_source(content="补充信息", source_id="om_third")
        result = _route_active_session(
            event_source,
            session=session,
            out_dir=out_dir,
            reply_sender=None,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "appended")

        subdirs_before = {p.name for p in out_dir.iterdir() if p.is_dir()}
        self.assertIn(run_id, subdirs_before)
        self.assertEqual(len(subdirs_before), 1)


class OtherStageQueueTests(unittest.TestCase):
    def test_solution_design_stage_queues_message(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()
        run_id = f"run_queue_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        artifact = make_requirement_artifact(ready=True, raw_content="贪吃蛇游戏")
        _write_run_files(
            run_dir, run_id, status="running", requirement_artifact=artifact,
            stages=[
                {"name": "requirement_intake", "status": "success"},
                {"name": "solution_design", "status": "running"},
                {"name": "code_generation", "status": "pending"},
                {"name": "test_generation", "status": "pending"},
                {"name": "code_review", "status": "pending"},
                {"name": "delivery", "status": "pending"},
            ],
        )
        session.register("oc_123", "ou_123", run_id, "running")

        replies: list[tuple[str, str, str]] = []

        def reply_sender(msg_id: str, text: str, key: str):
            replies.append((msg_id, text, key))

        event_source = make_event_source(content="用 TypeScript 写", source_id="om_queue")
        result = _route_active_session(
            event_source,
            session=session,
            out_dir=out_dir,
            reply_sender=reply_sender,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "queued")
        self.assertEqual(result.run_id, run_id)
        self.assertTrue(any("正在处理中" in r[1] for r in replies))

        requirement = json.loads((run_dir / "requirement.json").read_text(encoding="utf-8"))
        self.assertNotIn("TypeScript", requirement.get("source_summary", {}).get("raw_content", ""))


class WaitingApprovalPromptTests(unittest.TestCase):
    def test_non_command_message_prompts_approval(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()
        run_id = f"run_approval_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        _write_run_files(run_dir, run_id, status="waiting_approval")
        session.register("oc_123", "ou_123", run_id, "waiting_approval")

        replies: list[tuple[str, str, str]] = []

        def reply_sender(msg_id: str, text: str, key: str):
            replies.append((msg_id, text, key))

        event_source = make_event_source(
            content="这个方案看起来不错", source_id="om_approval_msg"
        )
        result = _route_active_session(
            event_source,
            session=session,
            out_dir=out_dir,
            reply_sender=reply_sender,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "waiting_approval")
        self.assertEqual(result.run_id, run_id)
        self.assertTrue(any("等待审批" in r[1] for r in replies))
        self.assertTrue(any(f"Approve {run_id}" in r[1] for r in replies))

    def test_no_new_run_created_for_approval_prompt(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()
        run_id = f"run_approval_no_new_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        _write_run_files(run_dir, run_id, status="waiting_approval")
        session.register("oc_123", "ou_123", run_id, "waiting_approval")

        event_source = make_event_source(content="随便说说", source_id="om_chat")
        result = _route_active_session(
            event_source,
            session=session,
            out_dir=out_dir,
            reply_sender=None,
        )

        self.assertIsNotNone(result)
        subdirs = {p.name for p in out_dir.iterdir() if p.is_dir()}
        self.assertEqual(len(subdirs), 1)
        self.assertIn(run_id, subdirs)


class NoActiveRunNewRunTests(unittest.TestCase):
    @patch("devflow.pipeline.maybe_run_solution_design", return_value=None)
    def test_no_session_creates_new_run_via_process_bot_event(self, _mock_sol) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()

        artifact = make_requirement_artifact(ready=True)

        def build_artifact(_source):
            return artifact

        cards: list[dict] = []

        def card_sender(_msg_id, card, _key):
            cards.append(card)

        result = process_bot_event(
            bot_event("目标：创建新功能\n用户：开发者\n范围：CLI"),
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
            reply_sender=None,
            session=session,
        )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.run_dir.exists())
        self.assertTrue((result.run_dir / "run.json").exists())
        self.assertTrue((result.run_dir / "requirement.json").exists())

        run_payload = json.loads(
            (result.run_dir / "run.json").read_text(encoding="utf-8")
        )
        self.assertEqual(run_payload["status"], "success")

    def test_lookup_returns_none_without_session(self) -> None:
        session = SessionManager()
        info = session.lookup("oc_nonexist", "ou_nonexist")
        self.assertIsNone(info)


class SessionTimeoutTests(unittest.TestCase):
    def test_expired_session_returns_none_on_lookup(self) -> None:
        session = SessionManager(session_timeout_seconds=1)
        session.register("oc_timeout", "ou_timeout", "run_expired", "running")

        info = session.lookup("oc_timeout", "ou_timeout")
        self.assertIsNotNone(info)

        time.sleep(1.5)

        info = session.lookup("oc_timeout", "ou_timeout")
        self.assertIsNone(info)

    def test_expired_session_allows_new_run(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager(session_timeout_seconds=1)
        run_id = f"run_timeout_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        _write_run_files(run_dir, run_id, status="running")
        session.register("oc_timeout", "ou_timeout", run_id, "running")

        time.sleep(1.5)

        event_source = make_event_source(
            content="新需求",
            chat_id="oc_timeout",
            sender_id="ou_timeout",
            source_id="om_new",
        )
        result = _route_active_session(
            event_source,
            session=session,
            out_dir=out_dir,
            reply_sender=None,
        )

        self.assertIsNone(result)


class OriginalBugScenarioTests(unittest.TestCase):
    def test_multi_message_snake_game_appends_not_creates(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()

        open_questions = [
            {"field": "scope", "question": "游戏的具体范围是什么？"},
            {"field": "theme", "question": "需要什么主题风格？"},
        ]
        artifact = make_requirement_artifact(
            ready=False,
            open_questions=open_questions,
            raw_content="贪吃蛇",
        )

        def build_artifact(_source):
            return artifact

        cards: list[dict] = []

        def card_sender(_msg_id, card, _key):
            cards.append(card)

        first_result = process_bot_event(
            bot_event("贪吃蛇"),
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
            reply_sender=None,
            session=session,
        )

        self.assertEqual(first_result.status, "waiting_clarification")
        first_run_id = first_result.run_id

        info = session.lookup("oc_123", "ou_123")
        self.assertIsNotNone(info)
        self.assertEqual(info.status, "waiting_clarification")

        second_result = process_bot_event(
            bot_event("春天主题", message_id="om_second"),
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
            reply_sender=None,
            session=session,
        )

        self.assertNotEqual(second_result.status, "waiting_clarification")
        self.assertEqual(second_result.run_id, first_run_id)

        updated_requirement = json.loads(
            (first_result.run_dir / "requirement.json").read_text(encoding="utf-8")
        )
        first_question = updated_requirement["open_questions"][0]
        self.assertEqual(first_question.get("answer"), "春天主题")

        subdirs = {p.name for p in out_dir.iterdir() if p.is_dir()}
        self.assertEqual(len(subdirs), 1)

    def test_blocked_session_appends_supplemental_message(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()
        run_id = f"run_blocked_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        artifact = make_requirement_artifact(
            ready=True, raw_content="贪吃蛇 + 春天主题 + 美丽花花"
        )
        checkpoint = build_clarification_checkpoint(
            {"run_id": run_id}, []
        )
        checkpoint["status"] = "blocked"
        checkpoint["stage"] = "solution_design"
        _write_run_files(
            run_dir,
            run_id,
            status="blocked",
            requirement_artifact=artifact,
            checkpoint_status="blocked",
            checkpoint=checkpoint,
        )
        session.register("oc_123", "ou_123", run_id, "blocked")

        replies: list[tuple[str, str, str]] = []

        def reply_sender(msg_id: str, text: str, key: str):
            replies.append((msg_id, text, key))

        event_source = make_event_source(
            content="绿色草草", source_id="om_green_grass"
        )
        result = _route_active_session(
            event_source,
            session=session,
            out_dir=out_dir,
            reply_sender=reply_sender,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "appended")
        self.assertEqual(result.run_id, run_id)

        updated_requirement = json.loads(
            (run_dir / "requirement.json").read_text(encoding="utf-8")
        )
        raw = updated_requirement["source_summary"]["raw_content"]
        self.assertIn("美丽花花", raw)
        self.assertIn("绿色草草", raw)

        subdirs = {p.name for p in out_dir.iterdir() if p.is_dir()}
        self.assertEqual(len(subdirs), 1)

    def test_full_pipeline_multi_message_no_duplicate_runs(self) -> None:
        out_dir = temp_out_dir()
        session = SessionManager()

        open_questions = [
            {"field": "scope", "question": "游戏范围？"},
        ]
        artifact = make_requirement_artifact(
            ready=False,
            open_questions=open_questions,
            raw_content="贪吃蛇",
        )

        def build_artifact(_source):
            return artifact

        cards: list[dict] = []

        def card_sender(_msg_id, card, _key):
            cards.append(card)

        first = process_bot_event(
            bot_event("贪吃蛇"),
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
            reply_sender=None,
            session=session,
        )

        self.assertEqual(first.status, "waiting_clarification")
        first_run_id = first.run_id

        second = process_bot_event(
            bot_event("春天主题", message_id="om_spring"),
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
            reply_sender=None,
            session=session,
        )

        self.assertEqual(second.run_id, first_run_id)

        third = process_bot_event(
            bot_event("美丽花花", message_id="om_flower"),
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
            reply_sender=None,
            session=session,
        )

        self.assertEqual(third.run_id, first_run_id)

        fourth = process_bot_event(
            bot_event("绿色草草", message_id="om_grass"),
            out_dir=out_dir,
            build_artifact=build_artifact,
            card_reply_sender=card_sender,
            reply_sender=None,
            session=session,
        )

        self.assertEqual(fourth.run_id, first_run_id)

        subdirs = {p.name for p in out_dir.iterdir() if p.is_dir()}
        self.assertEqual(len(subdirs), 1)

        updated_requirement = json.loads(
            (first.run_dir / "requirement.json").read_text(encoding="utf-8")
        )
        raw = updated_requirement["source_summary"]["raw_content"]
        self.assertIn("贪吃蛇", raw)
        self.assertIn("美丽花花", raw)
        self.assertIn("绿色草草", raw)

        first_question = updated_requirement["open_questions"][0]
        self.assertEqual(first_question.get("answer"), "春天主题")

        history = updated_requirement.get("input_history") or []
        supplement_entries = [h for h in history if h.get("mode") == "supplement"]
        self.assertEqual(len(supplement_entries), 2)


class UpdateSessionFromResultTests(unittest.TestCase):
    def test_terminal_status_unregisters_session(self) -> None:
        session = SessionManager()
        session.register("oc_term", "ou_term", "run_term", "running")
        self.assertIsNotNone(session.lookup("oc_term", "ou_term"))

        _update_session_from_result(
            session, "oc_term", "ou_term", "run_term", {"status": "success"}
        )
        self.assertIsNone(session.lookup("oc_term", "ou_term"))

    def test_waiting_status_updates_session(self) -> None:
        session = SessionManager()
        session.register("oc_wait", "ou_wait", "run_wait", "running")

        _update_session_from_result(
            session, "oc_wait", "ou_wait", "run_wait", {"status": "waiting_approval"}
        )
        info = session.lookup("oc_wait", "ou_wait")
        self.assertIsNotNone(info)
        self.assertEqual(info.status, "waiting_approval")

    def test_blocked_status_updates_session(self) -> None:
        session = SessionManager()
        session.register("oc_block", "ou_block", "run_block", "running")

        _update_session_from_result(
            session, "oc_block", "ou_block", "run_block", {"status": "blocked"}
        )
        info = session.lookup("oc_block", "ou_block")
        self.assertIsNotNone(info)
        self.assertEqual(info.status, "blocked")

    def test_none_session_is_noop(self) -> None:
        _update_session_from_result(
            None, "oc_x", "ou_x", "run_x", {"status": "success"}
        )

    def test_empty_chat_id_is_noop(self) -> None:
        session = SessionManager()
        _update_session_from_result(
            session, "", "ou_x", "run_x", {"status": "success"}
        )
        self.assertEqual(len(session._sessions), 0)


class AppendToActiveRequirementTests(unittest.TestCase):
    def test_appends_content_to_source_summary(self) -> None:
        out_dir = temp_out_dir()
        run_id = f"run_append_unit_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        artifact = make_requirement_artifact(ready=True, raw_content="原始需求")
        _write_run_files(run_dir, run_id, requirement_artifact=artifact)

        event_source = make_event_source(content="补充说明")
        result = _append_to_active_requirement(
            event_source,
            run_dir=run_dir,
            run_id=run_id,
            reply_sender=None,
        )

        self.assertEqual(result.status, "appended")
        self.assertEqual(result.run_id, run_id)

        updated = json.loads(
            (run_dir / "requirement.json").read_text(encoding="utf-8")
        )
        self.assertIn("原始需求", updated["source_summary"]["raw_content"])
        self.assertIn("补充说明", updated["source_summary"]["raw_content"])

    def test_appends_without_existing_requirement(self) -> None:
        out_dir = temp_out_dir()
        run_id = f"run_append_no_req_{uuid4().hex}"
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        _write_run_files(run_dir, run_id)

        event_source = make_event_source(content="新内容")
        result = _append_to_active_requirement(
            event_source,
            run_dir=run_dir,
            run_id=run_id,
            reply_sender=None,
        )

        self.assertEqual(result.status, "appended")
        self.assertIsNone(result.requirement_path)


if __name__ == "__main__":
    unittest.main()
