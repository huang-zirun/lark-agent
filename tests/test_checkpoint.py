from __future__ import annotations

import json
import unittest
from pathlib import Path
from uuid import uuid4

from devflow.checkpoint import (
    SCHEMA_VERSION,
    apply_checkpoint_decision,
    build_code_review_card,
    build_code_review_checkpoint,
    build_solution_review_card,
    build_solution_review_checkpoint,
    parse_checkpoint_command,
    resolve_run_id_prefix,
    write_checkpoint,
    PrefixMatchError,
)
from devflow.pipeline import publish_solution_review_checkpoint
from devflow.solution.render import render_solution_markdown


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


def temp_run_dir() -> Path:
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TMP_ROOT / f"checkpoint-{uuid4().hex}"
    path.mkdir()
    return path


def solution_artifact() -> dict:
    return {
        "schema_version": "devflow.solution_design.v1",
        "proposed_solution": {
            "summary": "新增方案评审检查点。",
            "data_flow": ["requirement.json -> solution.json -> checkpoint.json"],
            "implementation_steps": ["生成方案", "等待用户确认"],
        },
        "change_plan": [
            {
                "path": "devflow/checkpoint.py",
                "action": "create",
                "responsibility": "管理检查点状态",
            }
        ],
        "api_design": {
            "cli": ["devflow checkpoint decide --run <run_id> --decision approve"],
            "python": ["build_solution_review_checkpoint(run_payload, solution_path, solution_markdown_path)"],
            "json_contracts": ["devflow.checkpoint.v1"],
            "external": ["im +messages-reply interactive"],
        },
        "testing_strategy": {
            "unit_tests": ["检查点状态流转"],
            "integration_tests": ["pipeline 发送方案评审卡片"],
            "acceptance_mapping": ["AC-001"],
            "regression_tests": ["pytest"],
        },
        "risks_and_assumptions": {
            "risks": ["卡片按钮回调暂不可用"],
            "assumptions": ["用户通过消息确认"],
            "open_questions": [],
        },
        "human_review": {
            "status": "pending",
            "checklist": ["确认文件变更清单", "确认 API 设计"],
        },
        "quality": {
            "completeness_score": 0.9,
            "risk_level": "medium",
            "ready_for_code_generation": True,
            "warnings": [],
        },
    }


class CheckpointTests(unittest.TestCase):
    def test_parse_checkpoint_commands(self) -> None:
        approve = parse_checkpoint_command("同意 20260503T083136Z-run")
        reject = parse_checkpoint_command("Reject 20260503T083136Z-run: 需要增加移动端适配")
        unrelated = parse_checkpoint_command("创建一个 HTML 小游戏")

        self.assertIsNotNone(approve)
        self.assertEqual(approve.decision, "approve")
        self.assertEqual(approve.run_id, "20260503T083136Z-run")
        self.assertIsNotNone(reject)
        self.assertEqual(reject.decision, "reject")
        self.assertEqual(reject.reason, "需要增加移动端适配")
        self.assertIsNone(unrelated)

    def test_checkpoint_state_transitions(self) -> None:
        run_dir = temp_run_dir()
        checkpoint = build_solution_review_checkpoint(
            {"run_id": "run_123"},
            run_dir / "solution.json",
            run_dir / "solution.md",
        )
        write_checkpoint(run_dir, checkpoint)

        saved = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["schema_version"], SCHEMA_VERSION)
        self.assertEqual(saved["status"], "waiting_approval")
        self.assertEqual(saved["attempt"], 1)

        awaiting = apply_checkpoint_decision(
            run_dir,
            "reject",
            reviewer={"chat_id": "oc_1", "sender_id": "ou_1"},
        )
        self.assertEqual(awaiting["status"], "awaiting_reject_reason")
        self.assertEqual(awaiting["reviewer"]["sender_id"], "ou_1")

        rejected = apply_checkpoint_decision(run_dir, "reject", reason="请补充触屏控制")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["reject_reason"], "请补充触屏控制")

        approved = apply_checkpoint_decision(run_dir, "approve", reviewer={"sender_id": "ou_2"})
        self.assertEqual(approved["status"], "approved")
        self.assertTrue(approved["continue_requested"])

    def test_solution_markdown_and_review_card_include_key_sections(self) -> None:
        markdown = render_solution_markdown(solution_artifact(), run_id="run_123")

        self.assertIn("# 技术方案：新增方案评审检查点。", markdown)
        self.assertIn("## 文件变更清单", markdown)
        self.assertIn("devflow/checkpoint.py", markdown)
        self.assertIn("## API 设计", markdown)
        self.assertIn("## 测试策略", markdown)

        card = build_solution_review_card(
            {"run_id": "run_123", "detected_input": {"kind": "inline_text"}},
            solution_artifact(),
            solution_path=Path("artifacts/runs/run_123/solution.json"),
            solution_markdown_path=Path("artifacts/runs/run_123/solution.md"),
        )
        content = json.dumps(card, ensure_ascii=False)
        self.assertIn("技术方案评审", content)
        self.assertIn("Approve run_123", content)
        self.assertIn("Reject run_123", content)
        self.assertIn("artifacts/runs/run_123/solution.md", content)

    def test_solution_review_card_does_not_use_dash_list_syntax_in_lark_md(self) -> None:
        card = build_solution_review_card(
            {"run_id": "run_123", "detected_input": {"kind": "inline_text"}},
            solution_artifact(),
            solution_path=Path("artifacts/runs/run_123/solution.json"),
            solution_markdown_path=Path("artifacts/runs/run_123/solution.md"),
        )

        for element in card["elements"]:
            if element.get("tag") == "div" and element.get("text", {}).get("tag") == "lark_md":
                content = element["text"]["content"]
                for line in content.split("\n"):
                    if line.startswith("- "):
                        self.fail(f"lark_md content uses unsupported '- ' list syntax: {line!r}")

    def test_publish_solution_review_checkpoint_sets_reply_error_on_card_failure(self) -> None:
        run_payload = {
            "run_id": "run_123",
            "detected_input": {"kind": "inline_text"},
            "stages": [],
        }

        def card_reply(_message_id: str, _card: dict, _idempotency_key: str):
            raise RuntimeError("card reply failed")

        from devflow.trace import RunTrace

        trace = RunTrace("run_123", temp_run_dir())

        publish_solution_review_checkpoint(
            run_payload,
            solution_artifact(),
            solution_path=Path("solution.json"),
            solution_markdown_path=Path("solution.md"),
            message_id="om_evt",
            card_reply_sender=card_reply,
            stage_trace=trace.stage("solution_design"),
        )

        self.assertEqual(run_payload["checkpoint_publication"]["status"], "failed")
        self.assertIn("card reply failed", run_payload["checkpoint_publication"]["error"])
        self.assertEqual(run_payload["reply_error"], "card reply failed")


class ResolveRunIdPrefixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.out_dir = TEST_TMP_ROOT / f"prefix-test-{uuid4().hex}"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "20260503T083136Z-run-abc").mkdir()
        (self.out_dir / "20260503T083136Z-run-def").mkdir()
        (self.out_dir / "20260504T120000Z-run-xyz").mkdir()

    def test_exact_match_returns_same_id(self) -> None:
        result = resolve_run_id_prefix("20260504T120000Z-run-xyz", self.out_dir)
        self.assertEqual(result, "20260504T120000Z-run-xyz")

    def test_prefix_match_single_result(self) -> None:
        result = resolve_run_id_prefix("20260504", self.out_dir)
        self.assertEqual(result, "20260504T120000Z-run-xyz")

    def test_prefix_match_multiple_results_raises(self) -> None:
        with self.assertRaises(PrefixMatchError) as ctx:
            resolve_run_id_prefix("20260503", self.out_dir)
        self.assertEqual(len(ctx.exception.matches), 2)
        self.assertIn("20260503T083136Z-run-abc", ctx.exception.matches)
        self.assertIn("20260503T083136Z-run-def", ctx.exception.matches)

    def test_no_match_raises(self) -> None:
        with self.assertRaises(PrefixMatchError) as ctx:
            resolve_run_id_prefix("9999", self.out_dir)
        self.assertEqual(ctx.exception.matches, [])

    def test_empty_prefix_raises(self) -> None:
        with self.assertRaises(PrefixMatchError) as ctx:
            resolve_run_id_prefix("", self.out_dir)
        self.assertEqual(ctx.exception.matches, [])

    def test_nonexistent_out_dir_raises(self) -> None:
        with self.assertRaises(PrefixMatchError):
            resolve_run_id_prefix("abc", TEST_TMP_ROOT / f"no-such-dir-{uuid4().hex}")


class ParseCheckpointCommandPrefixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.out_dir = TEST_TMP_ROOT / f"parse-prefix-test-{uuid4().hex}"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "20260503T083136Z-run-abc").mkdir()

    def test_exact_run_id_without_out_dir(self) -> None:
        cmd = parse_checkpoint_command("同意 20260503T083136Z-run-abc")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.run_id, "20260503T083136Z-run-abc")

    def test_exact_run_id_with_out_dir(self) -> None:
        cmd = parse_checkpoint_command("同意 20260503T083136Z-run-abc", out_dir=self.out_dir)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.run_id, "20260503T083136Z-run-abc")

    def test_prefix_resolved_with_out_dir(self) -> None:
        cmd = parse_checkpoint_command("同意 20260503", out_dir=self.out_dir)
        self.assertIsNotNone(cmd)
        self.assertIsInstance(cmd, type(cmd))
        self.assertNotIsInstance(cmd, PrefixMatchError)
        self.assertEqual(cmd.run_id, "20260503T083136Z-run-abc")

    def test_prefix_ambiguous_returns_error(self) -> None:
        (self.out_dir / "20260503T083136Z-run-def").mkdir()
        result = parse_checkpoint_command("同意 20260503", out_dir=self.out_dir)
        self.assertIsInstance(result, PrefixMatchError)
        self.assertEqual(len(result.matches), 2)

    def test_no_match_returns_error(self) -> None:
        result = parse_checkpoint_command("同意 9999", out_dir=self.out_dir)
        self.assertIsInstance(result, PrefixMatchError)
        self.assertEqual(result.matches, [])

    def test_without_out_dir_no_resolution(self) -> None:
        cmd = parse_checkpoint_command("同意 20260503")
        self.assertIsNotNone(cmd)
        self.assertNotIsInstance(cmd, PrefixMatchError)
        self.assertEqual(cmd.run_id, "20260503")


class ConfirmationReplyFormatTests(unittest.TestCase):
    def test_approve_reply_format(self) -> None:
        cmd = parse_checkpoint_command("同意 20260503T083136Z-run-abc")
        self.assertIsNotNone(cmd)
        confirm_text = (
            f"✅ 已收到同意指令，正在继续… 运行 ID：{cmd.run_id}"
            if cmd.decision == "approve"
            else f"🔄 已收到拒绝指令，正在处理… 运行 ID：{cmd.run_id}"
        )
        self.assertEqual(confirm_text, "✅ 已收到同意指令，正在继续… 运行 ID：20260503T083136Z-run-abc")

    def test_reject_reply_format(self) -> None:
        cmd = parse_checkpoint_command("拒绝 20260503T083136Z-run-abc")
        self.assertIsNotNone(cmd)
        confirm_text = (
            f"✅ 已收到同意指令，正在继续… 运行 ID：{cmd.run_id}"
            if cmd.decision == "approve"
            else f"🔄 已收到拒绝指令，正在处理… 运行 ID：{cmd.run_id}"
        )
        self.assertEqual(confirm_text, "🔄 已收到拒绝指令，正在处理… 运行 ID：20260503T083136Z-run-abc")

    def test_approve_english_reply_format(self) -> None:
        cmd = parse_checkpoint_command("Approve 20260503T083136Z-run-abc")
        self.assertIsNotNone(cmd)
        confirm_text = (
            f"✅ 已收到同意指令，正在继续… 运行 ID：{cmd.run_id}"
            if cmd.decision == "approve"
            else f"🔄 已收到拒绝指令，正在处理… 运行 ID：{cmd.run_id}"
        )
        self.assertEqual(confirm_text, "✅ 已收到同意指令，正在继续… 运行 ID：20260503T083136Z-run-abc")

    def test_reject_with_reason_reply_format(self) -> None:
        cmd = parse_checkpoint_command("Reject 20260503T083136Z-run-abc: 需要修改")
        self.assertIsNotNone(cmd)
        confirm_text = (
            f"✅ 已收到同意指令，正在继续… 运行 ID：{cmd.run_id}"
            if cmd.decision == "approve"
            else f"🔄 已收到拒绝指令，正在处理… 运行 ID：{cmd.run_id}"
        )
        self.assertEqual(confirm_text, "🔄 已收到拒绝指令，正在处理… 运行 ID：20260503T083136Z-run-abc")


class CodeReviewApprovalTests(unittest.TestCase):
    def test_build_code_review_checkpoint(self) -> None:
        run_dir = temp_run_dir()
        checkpoint = build_code_review_checkpoint(
            {"run_id": "run_cr_123"},
            run_dir / "code-review.json",
            run_dir / "code-review.md",
        )
        write_checkpoint(run_dir, checkpoint)

        saved = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["schema_version"], SCHEMA_VERSION)
        self.assertEqual(saved["stage"], "code_review")
        self.assertEqual(saved["status"], "waiting_approval")
        self.assertEqual(saved["attempt"], 1)

    def test_code_review_card_without_approval_instance(self) -> None:
        review_artifact = {
            "review_status": "passed",
            "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"},
            "findings": [],
            "summary": "代码评审通过",
        }
        card = build_code_review_card(
            {"run_id": "run_cr_123", "detected_input": {"kind": "inline_text"}},
            review_artifact,
            review_path=Path("artifacts/runs/run_cr_123/code-review.json"),
            review_markdown_path=Path("artifacts/runs/run_cr_123/code-review.md"),
        )
        content = json.dumps(card, ensure_ascii=False)
        self.assertIn("Approve run_cr_123", content)
        self.assertIn("Reject run_cr_123", content)
        self.assertNotIn("审批", content)

    def test_code_review_card_with_approval_instance(self) -> None:
        review_artifact = {
            "review_status": "needs_changes",
            "quality_gate": {"passed": False, "blocking_findings": 2, "risk_level": "high"},
            "findings": [
                {"severity": "P1", "path": "main.py", "title": "SQL 注入风险"},
            ],
            "summary": "发现阻塞问题",
        }
        card = build_code_review_card(
            {"run_id": "run_cr_456", "detected_input": {"kind": "inline_text"}},
            review_artifact,
            review_path=Path("artifacts/runs/run_cr_456/code-review.json"),
            review_markdown_path=Path("artifacts/runs/run_cr_456/code-review.md"),
            has_approval_instance=True,
        )
        content = json.dumps(card, ensure_ascii=False)
        self.assertIn("Approve run_cr_456", content)
        self.assertIn("Reject run_cr_456", content)
        self.assertIn("审批", content)

    def test_code_review_card_does_not_use_dash_list_syntax_in_lark_md(self) -> None:
        review_artifact = {
            "review_status": "passed",
            "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"},
            "findings": [],
            "summary": "通过",
        }
        card = build_code_review_card(
            {"run_id": "run_cr_789", "detected_input": {"kind": "inline_text"}},
            review_artifact,
            review_path=Path("artifacts/runs/run_cr_789/code-review.json"),
            review_markdown_path=Path("artifacts/runs/run_cr_789/code-review.md"),
            has_approval_instance=True,
        )
        for element in card["elements"]:
            if element.get("tag") == "div" and element.get("text", {}).get("tag") == "lark_md":
                content = element["text"]["content"]
                for line in content.split("\n"):
                    if line.startswith("- "):
                        self.fail(f"lark_md content uses unsupported '- ' list syntax: {line!r}")


if __name__ == "__main__":
    unittest.main()
