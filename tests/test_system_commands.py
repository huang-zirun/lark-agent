from __future__ import annotations

import json
import unittest
from pathlib import Path
from uuid import uuid4

from devflow.checkpoint import SystemCommand, parse_system_command
from devflow.intake.models import RequirementSource
from devflow.pipeline import (
    _build_help_card,
    _build_status_card,
    _find_active_runs,
    handle_system_command,
    maybe_process_checkpoint_event,
)


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


def temp_out_dir() -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / f"syscmd-{uuid4().hex}"
    path.mkdir()
    return path


def make_source(
    content: str,
    *,
    chat_id: str = "oc_test",
    sender_id: str = "ou_test",
    source_id: str = "om_test",
) -> RequirementSource:
    return RequirementSource(
        source_type="lark_bot_event",
        source_id=source_id,
        reference=source_id,
        content=content,
        metadata={"chat_id": chat_id, "sender_id": sender_id},
    )


def write_run(
    out_dir: Path,
    run_id: str,
    *,
    status: str = "running",
    chat_id: str = "oc_test",
    sender_id: str = "ou_test",
    started_at: str = "2026-05-05T10:00:00Z",
    stages: list[dict] | None = None,
) -> Path:
    run_dir = out_dir / run_id
    run_dir.mkdir(exist_ok=True)
    payload = {
        "run_id": run_id,
        "status": status,
        "lifecycle_status": status,
        "started_at": started_at,
        "trigger": {"chat_id": chat_id, "sender_id": sender_id},
        "stages": stages or [{"name": "solution_design", "status": "running"}],
    }
    (run_dir / "run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return run_dir


class ParseSystemCommandTests(unittest.TestCase):
    def test_help_aliases(self) -> None:
        self.assertEqual(parse_system_command("/help"), SystemCommand("help"))
        self.assertEqual(parse_system_command("/帮助"), SystemCommand("help"))
        self.assertEqual(parse_system_command("/Help"), SystemCommand("help"))
        self.assertEqual(parse_system_command("/HELP"), SystemCommand("help"))

    def test_status_aliases(self) -> None:
        self.assertEqual(parse_system_command("/status"), SystemCommand("status"))
        self.assertEqual(parse_system_command("/状态"), SystemCommand("status"))
        self.assertEqual(parse_system_command("/Status"), SystemCommand("status"))
        self.assertEqual(parse_system_command("/STATUS"), SystemCommand("status"))

    def test_non_matching_returns_none(self) -> None:
        self.assertIsNone(parse_system_command("hello world"))
        self.assertIsNone(parse_system_command("Approve run-123"))
        self.assertIsNone(parse_system_command("/unknown"))
        self.assertIsNone(parse_system_command(""))
        self.assertIsNone(parse_system_command("创建一个 HTML 小游戏"))

    def test_leading_trailing_whitespace(self) -> None:
        self.assertEqual(parse_system_command("  /help  "), SystemCommand("help"))
        self.assertEqual(parse_system_command("\t/status\t"), SystemCommand("status"))


class HelpCardTests(unittest.TestCase):
    def test_help_card_structure(self) -> None:
        card = _build_help_card()
        self.assertEqual(card["header"]["template"], "blue")
        self.assertIn("📖", card["header"]["title"]["content"])
        elements = card["elements"]
        self.assertTrue(len(elements) >= 1)
        md_content = elements[0]["text"]["content"]
        self.assertIn("输入格式", md_content)
        self.assertIn("系统命令", md_content)
        self.assertIn("检查点命令", md_content)

    def test_help_card_uses_bullet_not_dash(self) -> None:
        card = _build_help_card()
        for element in card["elements"]:
            if element.get("tag") == "div" and element.get("text", {}).get("tag") == "lark_md":
                content = element["text"]["content"]
                for line in content.split("\n"):
                    if line.startswith("- "):
                        self.fail(f"lark_md uses unsupported '- ' list syntax: {line!r}")


class StatusCardTests(unittest.TestCase):
    def test_status_no_active_runs(self) -> None:
        out_dir = temp_out_dir()
        source = make_source("/status")
        card = _build_status_card(source, out_dir=out_dir)
        md_content = card["elements"][0]["text"]["content"]
        self.assertIn("当前没有进行中的任务", md_content)

    def test_status_with_active_runs(self) -> None:
        out_dir = temp_out_dir()
        write_run(out_dir, "run-001", status="running", started_at="2026-05-05T10:00:00Z")
        source = make_source("/status")
        card = _build_status_card(source, out_dir=out_dir)
        md_content = card["elements"][0]["text"]["content"]
        self.assertIn("run-001", md_content)
        self.assertIn("方案设计", md_content)

    def test_status_ignores_non_matching_user(self) -> None:
        out_dir = temp_out_dir()
        write_run(out_dir, "run-002", status="running", chat_id="oc_other", sender_id="ou_other")
        source = make_source("/status", chat_id="oc_test", sender_id="ou_test")
        card = _build_status_card(source, out_dir=out_dir)
        md_content = card["elements"][0]["text"]["content"]
        self.assertIn("当前没有进行中的任务", md_content)

    def test_status_filters_by_active_statuses(self) -> None:
        out_dir = temp_out_dir()
        write_run(out_dir, "run-active", status="running")
        write_run(out_dir, "run-blocked", status="blocked")
        write_run(out_dir, "run-waiting", status="waiting_approval")
        write_run(out_dir, "run-done", status="success")
        write_run(out_dir, "run-failed", status="failed")
        source = make_source("/status")
        runs = _find_active_runs(out_dir, source)
        run_ids = {r["run_id"] for r in runs}
        self.assertIn("run-active", run_ids)
        self.assertIn("run-blocked", run_ids)
        self.assertIn("run-waiting", run_ids)
        self.assertNotIn("run-done", run_ids)
        self.assertNotIn("run-failed", run_ids)


class HandleSystemCommandTests(unittest.TestCase):
    def test_help_returns_system_command_status(self) -> None:
        out_dir = temp_out_dir()
        source = make_source("/help")
        sent_cards: list[tuple[str, dict, str]] = []

        def card_sender(message_id: str, card: dict, key: str) -> None:
            sent_cards.append((message_id, card, key))

        result = handle_system_command(
            SystemCommand("help"),
            source,
            out_dir=out_dir,
            reply_sender=None,
            card_reply_sender=card_sender,
        )
        self.assertEqual(result.status, "system_command")
        self.assertEqual(len(sent_cards), 1)
        self.assertIn("📖", sent_cards[0][1]["header"]["title"]["content"])

    def test_status_returns_system_command_status(self) -> None:
        out_dir = temp_out_dir()
        source = make_source("/status")
        sent_cards: list[tuple[str, dict, str]] = []

        def card_sender(message_id: str, card: dict, key: str) -> None:
            sent_cards.append((message_id, card, key))

        result = handle_system_command(
            SystemCommand("status"),
            source,
            out_dir=out_dir,
            reply_sender=None,
            card_reply_sender=card_sender,
        )
        self.assertEqual(result.status, "system_command")
        self.assertEqual(len(sent_cards), 1)
        self.assertIn("📊", sent_cards[0][1]["header"]["title"]["content"])

    def test_help_does_not_create_run_dir(self) -> None:
        out_dir = temp_out_dir()
        source = make_source("/help")
        existing_dirs = set(out_dir.iterdir())

        def noop_card(*args: object) -> None:
            pass

        handle_system_command(
            SystemCommand("help"),
            source,
            out_dir=out_dir,
            reply_sender=None,
            card_reply_sender=noop_card,
        )
        self.assertEqual(set(out_dir.iterdir()), existing_dirs)


class MaybeProcessCheckpointEventRoutingTests(unittest.TestCase):
    def test_system_command_takes_priority_over_checkpoint(self) -> None:
        out_dir = temp_out_dir()
        source = make_source("/help")
        sent_cards: list[tuple[str, dict, str]] = []

        def card_sender(message_id: str, card: dict, key: str) -> None:
            sent_cards.append((message_id, card, key))

        result = maybe_process_checkpoint_event(
            source,
            out_dir=out_dir,
            reply_sender=None,
            card_reply_sender=card_sender,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "system_command")

    def test_non_system_command_falls_through(self) -> None:
        out_dir = temp_out_dir()
        source = make_source("创建一个 HTML 小游戏")
        result = maybe_process_checkpoint_event(
            source,
            out_dir=out_dir,
            reply_sender=None,
            card_reply_sender=None,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
