from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from pathlib import Path

from devflow.intake.lark_cli import create_prd_document, publish_document, send_bot_card_reply
from devflow.checkpoint import build_solution_review_card, build_code_review_card
from devflow.pipeline import process_bot_event
from devflow.prd import build_prd_preview_card, render_prd_markdown


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


@contextmanager
def temp_run_dir():
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    yield str(TEST_TMP_ROOT)


def requirement_artifact() -> dict:
    return {
        "schema_version": "devflow.requirement.v1",
        "metadata": {"agent_name": "ProductRequirementAnalyst", "analyzer": "llm"},
        "source_summary": {
            "source_type": "lark_bot_text",
            "source_id": "om_evt",
            "reference": "om_evt",
            "title": "智能工单分流",
        },
        "normalized_requirement": {
            "title": "智能工单分流",
            "background": ["客服团队每天需要处理大量重复工单。"],
            "target_users": ["客服主管", "一线客服"],
            "problem": ["高峰期工单无法及时分配。"],
            "goals": ["自动识别工单类型", "把高优工单分配给合适客服"],
            "non_goals": ["不替代人工最终回复"],
            "scope": ["飞书机器人内提交需求并生成分流建议"],
        },
        "product_analysis": {
            "user_scenarios": ["客服主管查看待处理高优工单。"],
            "business_value": ["缩短首次响应时间。"],
            "evidence": ["用户反馈高峰期响应慢。"],
            "assumptions": ["已有工单文本分类数据。"],
            "risks": ["分类错误会影响客户体验。"],
            "dependencies": ["工单系统 API。"],
        },
        "acceptance_criteria": [
            {"id": "AC-001", "source": "llm", "criterion": "给定新工单，系统返回分类和优先级。"},
            {"id": "AC-002", "source": "llm", "criterion": "高优工单进入主管可见队列。"},
        ],
        "open_questions": ["是否需要支持夜间值班规则？"],
        "quality": {
            "completeness_score": 0.82,
            "ambiguity_score": 0.18,
            "ready_for_next_stage": True,
            "warnings": ["缺少具体 SLA 阈值。"],
        },
        "sections": [],
    }


def bot_event(text: str, message_id: str = "om_evt") -> dict:
    return {
        "event": {
            "message_id": message_id,
            "chat_id": "oc_123",
            "sender_id": "ou_123",
            "content": {"text": text},
        }
    }


class PrdPublishTests(unittest.TestCase):
    def test_render_prd_markdown_maps_requirement_artifact_to_readable_prd(self) -> None:
        markdown = render_prd_markdown(requirement_artifact(), run_id="run_123")

        self.assertIn("# 智能工单分流", markdown)
        self.assertIn("## 背景", markdown)
        self.assertIn("- 客服团队每天需要处理大量重复工单。", markdown)
        self.assertIn("## 验收标准", markdown)
        self.assertIn("- **AC-001**：给定新工单，系统返回分类和优先级。", markdown)
        self.assertIn("## 待澄清问题", markdown)
        self.assertIn("- 是否需要支持夜间值班规则？", markdown)
        self.assertIn("run_123", markdown)

    def test_render_prd_markdown_handles_sparse_artifact(self) -> None:
        markdown = render_prd_markdown(
            {
                "normalized_requirement": {"title": "未命名需求"},
                "acceptance_criteria": [],
                "open_questions": [],
                "quality": {},
            }
        )

        self.assertIn("# 未命名需求", markdown)
        self.assertIn("- 暂无明确内容。", markdown)
        self.assertIn("- 暂无待澄清问题。", markdown)

    def test_create_prd_document_uses_bot_docs_create_command(self) -> None:
        calls = []

        def runner(args: list[str], timeout: int | None):
            calls.append((args, timeout))
            return {
                "ok": True,
                "data": {
                    "document": {
                        "document_id": "docx_123",
                        "url": "https://example.feishu.cn/docx/docx_123",
                    }
                },
            }

        result = create_prd_document("智能工单分流", "# 智能工单分流", runner=runner)

        self.assertEqual(result["document_id"], "docx_123")
        self.assertEqual(result["url"], "https://example.feishu.cn/docx/docx_123")
        self.assertEqual(
            calls[0][0],
            [
                "docs",
                "+create",
                "--api-version",
                "v2",
                "--as",
                "bot",
                "--doc-format",
                "markdown",
                "--content",
                "# 智能工单分流",
            ],
        )
        self.assertEqual(calls[0][1], 120)

    def test_send_bot_card_reply_uses_interactive_content(self) -> None:
        calls = []
        card = build_prd_preview_card(
            requirement_artifact(),
            run_id="run_123",
            detected_input={"kind": "inline_text", "value": "目标：智能工单分流"},
            prd_url="https://example.feishu.cn/docx/docx_123",
        )

        def runner(args: list[str], timeout: int | None):
            calls.append((args, timeout))
            return {"ok": True}

        send_bot_card_reply("om_evt", card, "key-123", runner=runner)

        args, timeout = calls[0]
        self.assertEqual(timeout, 120)
        self.assertEqual(args[:8], ["im", "+messages-reply", "--message-id", "om_evt", "--msg-type", "interactive", "--content", json.dumps(card, ensure_ascii=False)])
        self.assertEqual(args[8:], ["--as", "bot", "--idempotency-key", "key-123"])

    def test_preview_card_does_not_render_empty_prd_link(self) -> None:
        card = build_prd_preview_card(
            requirement_artifact(),
            run_id="run_123",
            detected_input={"kind": "inline_text", "value": "目标：智能工单分流"},
            prd_url="",
        )

        first_element = card["elements"][0]["text"]["content"]

        self.assertNotIn("[查看完整 PRD 文档]()", first_element)
        self.assertIn("PRD 文档", first_element)
        self.assertIn("暂未返回链接", first_element)

    def test_preview_card_does_not_use_dash_list_syntax_in_lark_md(self) -> None:
        card = build_prd_preview_card(
            requirement_artifact(),
            run_id="run_123",
            detected_input={"kind": "inline_text", "value": "目标：智能工单分流"},
            prd_url="https://example.feishu.cn/docx/docx_123",
        )

        for element in card["elements"]:
            if element.get("tag") == "div" and element.get("text", {}).get("tag") == "lark_md":
                content = element["text"]["content"]
                for line in content.split("\n"):
                    if line.startswith("- "):
                        self.fail(f"lark_md content uses unsupported '- ' list syntax: {line!r}")

    def test_process_success_creates_prd_and_replies_with_preview_card(self) -> None:
        created = []
        cards = []

        def build_artifact(*_args):
            return requirement_artifact()

        def create_prd(title: str, markdown: str):
            created.append((title, markdown))
            return {"document_id": "docx_123", "url": "https://example.feishu.cn/docx/docx_123"}

        def card_reply(message_id: str, card: dict, idempotency_key: str):
            cards.append((message_id, card, idempotency_key))

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：智能工单分流"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                build_artifact=build_artifact,
                prd_creator=create_prd,
                card_reply_sender=card_reply,
                reply_sender=None,
            )
            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "success")
        self.assertEqual(created[0][0], "智能工单分流")
        self.assertIn("# 智能工单分流", created[0][1])
        self.assertEqual(cards[0][0], "om_evt")
        self.assertIn("docx_123", run_payload["publication"]["prd"]["document_id"])
        self.assertEqual(run_payload["publication"]["card_reply"]["status"], "success")

    def test_process_prd_publish_failure_keeps_analysis_success(self) -> None:
        def build_artifact(*_args):
            return requirement_artifact()

        def create_prd(_title: str, _markdown: str):
            raise RuntimeError("create doc failed")

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：智能工单分流"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                build_artifact=build_artifact,
                prd_creator=create_prd,
                card_reply_sender=None,
                reply_sender=lambda *_args: None,
            )
            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "success")
        self.assertEqual(run_payload["stages"][0]["status"], "success")
        self.assertEqual(run_payload["publication"]["status"], "failed")
        self.assertIn("create doc failed", run_payload["publication"]["error"])

    def test_process_card_reply_failure_records_reply_error(self) -> None:
        def build_artifact(*_args):
            return requirement_artifact()

        def create_prd(_title: str, _markdown: str):
            return {"document_id": "docx_123", "url": "https://example.feishu.cn/docx/docx_123"}

        def card_reply(_message_id: str, _card: dict, _idempotency_key: str):
            raise RuntimeError("card reply failed")

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：智能工单分流"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                build_artifact=build_artifact,
                prd_creator=create_prd,
                card_reply_sender=card_reply,
                reply_sender=lambda *_args: None,
            )
            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "success")
        self.assertEqual(result.reply_error, "card reply failed")
        self.assertEqual(run_payload["reply_error"], "card reply failed")
        self.assertEqual(run_payload["publication"]["status"], "failed")

    def test_process_card_reply_failure_sends_text_fallback(self) -> None:
        replies = []

        def build_artifact(*_args):
            return requirement_artifact()

        def create_prd(_title: str, _markdown: str):
            return {"document_id": "docx_123", "url": None}

        def card_reply(_message_id: str, _card: dict, _idempotency_key: str):
            raise RuntimeError("card reply failed")

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：智能工单分流"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                build_artifact=build_artifact,
                prd_creator=create_prd,
                card_reply_sender=card_reply,
                reply_sender=reply_sender,
            )

        self.assertEqual(result.status, "success")
        self.assertEqual(replies[-1][0], "om_evt")
        self.assertIn("DevFlow 流水线已完成", replies[-1][1])
        self.assertIn("PRD 发布：失败", replies[-1][1])
        self.assertTrue(replies[-1][2].startswith("df-"))


class PublishDocumentTests(unittest.TestCase):
    def test_publish_document_uses_bot_docs_create_command(self) -> None:
        calls = []

        def runner(args: list[str], timeout: int | None):
            calls.append((args, timeout))
            return {
                "ok": True,
                "data": {
                    "document": {
                        "document_id": "docx_pub",
                        "url": "https://example.feishu.cn/docx/docx_pub",
                    }
                },
            }

        result = publish_document("技术方案", "# 方案内容", runner=runner)

        self.assertEqual(result["document_id"], "docx_pub")
        self.assertEqual(result["url"], "https://example.feishu.cn/docx/docx_pub")
        self.assertEqual(
            calls[0][0],
            [
                "docs",
                "+create",
                "--api-version",
                "v2",
                "--as",
                "bot",
                "--doc-format",
                "markdown",
                "--content",
                "# 方案内容",
            ],
        )

    def test_publish_document_with_folder_token(self) -> None:
        calls = []

        def runner(args: list[str], timeout: int | None):
            calls.append((args, timeout))
            return {
                "ok": True,
                "data": {
                    "document": {
                        "document_id": "docx_folder",
                        "url": "https://example.feishu.cn/docx/docx_folder",
                    }
                },
            }

        result = publish_document("标题", "内容", folder_token="fld_abc", runner=runner)

        self.assertIn("--parent-token", calls[0][0])
        self.assertIn("fld_abc", calls[0][0])
        self.assertEqual(result["document_id"], "docx_folder")

    def test_publish_document_raises_on_failure(self) -> None:
        def runner(_args: list[str], _timeout: int | None):
            return "not a dict"

        from devflow.intake.lark_cli import LarkCliError

        with self.assertRaises(LarkCliError):
            publish_document("标题", "内容", runner=runner)


class PrdPreviewCardDocLinkTests(unittest.TestCase):
    def test_prd_card_includes_doc_link_at_top_when_url_provided(self) -> None:
        card = build_prd_preview_card(
            requirement_artifact(),
            run_id="run_123",
            detected_input={"kind": "inline_text", "value": "目标：智能工单分流"},
            prd_url="https://example.feishu.cn/docx/docx_123",
        )

        first_element = card["elements"][0]
        self.assertEqual(first_element["tag"], "div")
        self.assertIn("[查看完整 PRD 文档](https://example.feishu.cn/docx/docx_123)", first_element["text"]["content"])

    def test_prd_card_shows_fallback_when_url_empty(self) -> None:
        card = build_prd_preview_card(
            requirement_artifact(),
            run_id="run_123",
            detected_input={"kind": "inline_text", "value": "目标：智能工单分流"},
            prd_url="",
        )

        first_element = card["elements"][0]
        self.assertIn("PRD 文档", first_element["text"]["content"])
        self.assertIn("暂未返回链接", first_element["text"]["content"])


class SolutionReviewCardDocUrlTests(unittest.TestCase):
    def _solution_artifact(self) -> dict:
        return {
            "proposed_solution": {"summary": "方案摘要"},
            "quality": {"risk_level": "low", "ready_for_code_generation": True, "warnings": []},
            "change_plan": [],
        }

    def test_solution_review_card_includes_doc_url_when_provided(self) -> None:
        card = build_solution_review_card(
            {"run_id": "run_abc", "detected_input": {"kind": "inline_text"}},
            self._solution_artifact(),
            solution_path=Path("solution.json"),
            solution_markdown_path=Path("solution.md"),
            solution_doc_url="https://example.feishu.cn/docx/sol_doc",
        )

        first_element = card["elements"][0]
        self.assertIn("[查看完整方案](https://example.feishu.cn/docx/sol_doc)", first_element["text"]["content"])

    def test_solution_review_card_shows_local_path_when_url_is_none(self) -> None:
        card = build_solution_review_card(
            {"run_id": "run_abc", "detected_input": {"kind": "inline_text"}},
            self._solution_artifact(),
            solution_path=Path("solution.json"),
            solution_markdown_path=Path("solution.md"),
            solution_doc_url=None,
        )

        first_element = card["elements"][0]
        self.assertIn("发布失败", first_element["text"]["content"])
        self.assertIn("solution.md", first_element["text"]["content"])

    def test_solution_review_card_preview_up_to_10_files(self) -> None:
        change_plan = [{"path": f"file_{i}.py", "action": "create", "responsibility": f"文件 {i}"} for i in range(12)]
        artifact = {
            "proposed_solution": {"summary": "方案"},
            "quality": {"risk_level": "low", "ready_for_code_generation": True, "warnings": []},
            "change_plan": change_plan,
        }

        card = build_solution_review_card(
            {"run_id": "run_abc", "detected_input": {"kind": "inline_text"}},
            artifact,
            solution_path=Path("solution.json"),
            solution_markdown_path=Path("solution.md"),
        )

        body_element = card["elements"][-1]
        content = body_element["text"]["content"]
        self.assertIn("file_9.py", content)
        self.assertNotIn("file_10.py", content)
        self.assertNotIn("file_11.py", content)


class CodeReviewCardDocUrlTests(unittest.TestCase):
    def _review_artifact(self) -> dict:
        return {
            "review_status": "passed",
            "summary": "评审摘要",
            "quality_gate": {"passed": True, "risk_level": "low", "blocking_findings": 0},
            "findings": [],
        }

    def test_code_review_card_includes_doc_url_when_provided(self) -> None:
        card = build_code_review_card(
            {"run_id": "run_abc", "detected_input": {"kind": "inline_text"}},
            self._review_artifact(),
            review_path=Path("review.json"),
            review_markdown_path=Path("review.md"),
            review_doc_url="https://example.feishu.cn/docx/review_doc",
        )

        first_element = card["elements"][0]
        self.assertIn("[查看完整评审报告](https://example.feishu.cn/docx/review_doc)", first_element["text"]["content"])

    def test_code_review_card_shows_local_path_when_url_is_none(self) -> None:
        card = build_code_review_card(
            {"run_id": "run_abc", "detected_input": {"kind": "inline_text"}},
            self._review_artifact(),
            review_path=Path("review.json"),
            review_markdown_path=Path("review.md"),
            review_doc_url=None,
        )

        first_element = card["elements"][0]
        self.assertIn("发布失败", first_element["text"]["content"])
        self.assertIn("review.md", first_element["text"]["content"])

    def test_code_review_card_preview_up_to_10_findings(self) -> None:
        findings = [{"severity": "P2", "path": f"src/{i}.py", "title": f"问题 {i}"} for i in range(12)]
        artifact = {
            "review_status": "needs_changes",
            "summary": "评审摘要",
            "quality_gate": {"passed": False, "risk_level": "high", "blocking_findings": 12},
            "findings": findings,
        }

        card = build_code_review_card(
            {"run_id": "run_abc", "detected_input": {"kind": "inline_text"}},
            artifact,
            review_path=Path("review.json"),
            review_markdown_path=Path("review.md"),
        )

        body_element = card["elements"][-1]
        content = body_element["text"]["content"]
        self.assertIn("src/9.py", content)
        self.assertNotIn("src/10.py", content)
        self.assertNotIn("src/11.py", content)


if __name__ == "__main__":
    unittest.main()
