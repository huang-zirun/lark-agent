from __future__ import annotations

import json
import unittest
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from devflow.cli import main
from devflow.config import DevflowConfig, LarkConfig, LlmConfig, WorkspaceConfig
from devflow.intake.lark_cli import LarkCliError, send_bot_reply
from devflow.intake.models import RequirementSource
from devflow.pipeline import (
    build_failure_reply,
    build_workspace_blocked_reply,
    detect_requirement_input,
    is_workspace_resume_reply,
    process_bot_event,
    _stage_failure_suggestion,
)
from devflow.checkpoint import build_code_review_checkpoint, build_solution_review_checkpoint, write_checkpoint


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"


@contextmanager
def temp_run_dir():
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    unique_dir = TEST_TMP_ROOT / f"pipeline-{uuid4().hex}"
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


class FakeLlmResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def llm_analysis_payload() -> dict:
    content = {
        "normalized_requirement": {
            "title": "Audit logging",
            "background": ["Need reliable pipeline observability."],
            "target_users": ["Developer"],
            "problem": ["LLM responses are hard to audit."],
            "goals": ["Record request and response details."],
            "non_goals": [],
            "scope": ["Requirement intake stage."],
        },
        "product_analysis": {
            "user_scenarios": ["Developer reviews a failed run."],
            "business_value": ["Faster troubleshooting."],
            "evidence": [],
            "assumptions": [],
            "risks": [],
            "dependencies": [],
        },
        "acceptance_criteria": [
            {"id": "AC-001", "source": "llm", "criterion": "Audit files are written."}
        ],
        "open_questions": [],
        "quality": {
            "completeness_score": 0.8,
            "ambiguity_score": 0.1,
            "ready_for_next_stage": True,
            "warnings": [],
        },
    }
    return {
        "id": "chatcmpl_audit",
        "choices": [{"message": {"content": json.dumps(content)}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def llm_solution_payload() -> dict:
    content = {
        "architecture_analysis": {
            "current_architecture": ["现有运行时由 devflow.pipeline 串联阶段。"],
            "related_modules": ["devflow.pipeline", "devflow.cli"],
            "constraints": ["保持标准库依赖。"],
            "reusable_patterns": ["RunTrace 事件审计。"],
        },
        "proposed_solution": {
            "summary": "新增方案设计 agent 并接入 start。",
            "data_flow": ["requirement.json -> solution.json"],
            "implementation_steps": ["扫描仓库上下文", "调用 LLM 输出方案"],
        },
        "change_plan": [
            {"path": "devflow/solution/designer.py", "action": "create", "responsibility": "方案设计"}
        ],
        "api_design": {
            "cli": ["devflow design from-requirement"],
            "python": ["build_solution_design_artifact"],
            "json_contracts": ["devflow.solution_design.v1"],
            "external": [],
        },
        "testing_strategy": {
            "unit_tests": ["workspace 和 solution 单测"],
            "integration_tests": ["start 写出 solution.json"],
            "acceptance_mapping": ["AC-001"],
            "regression_tests": ["完整 unittest"],
        },
        "risks_and_assumptions": {
            "risks": ["LLM 响应不稳定"],
            "assumptions": ["仓库路径可访问"],
            "open_questions": [],
        },
        "human_review": {
            "status": "pending",
            "checklist": ["确认文件清单"],
        },
        "quality": {
            "completeness_score": 0.82,
            "risk_level": "medium",
            "ready_for_code_generation": True,
            "warnings": [],
        },
    }
    return {
        "id": "chatcmpl_solution",
        "choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
    }
class PipelineStartTests(unittest.TestCase):
    def test_detects_doc_url_before_message_id(self) -> None:
        detected = detect_requirement_input(
            "please read https://example.feishu.cn/docx/doc_abc and om_other"
        )

        self.assertEqual(detected.kind, "lark_doc")
        self.assertEqual(detected.value, "https://example.feishu.cn/docx/doc_abc")

    def test_detects_message_id(self) -> None:
        detected = detect_requirement_input("please analyze om_abc123")

        self.assertEqual(detected.kind, "lark_message")
        self.assertEqual(detected.value, "om_abc123")

    def test_detects_doc_token(self) -> None:
        detected = detect_requirement_input("please analyze doc_abc123")

        self.assertEqual(detected.kind, "lark_doc")
        self.assertEqual(detected.value, "doc_abc123")

    def test_falls_back_to_inline_text(self) -> None:
        detected = detect_requirement_input("目标：构建一键启动")

        self.assertEqual(detected.kind, "inline_text")
        self.assertEqual(detected.value, "目标：构建一键启动")

    def test_process_inline_message_writes_successful_run_and_replies(self) -> None:
        cards = []

        def create_prd(title: str, markdown: str) -> dict:
            self.assertIn(title, markdown)
            return {"document_id": "docx_test", "url": "https://example.feishu.cn/docx/docx_test"}

        def card_reply(message_id: str, card: dict, idempotency_key: str) -> None:
            cards.append((message_id, card, idempotency_key))

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：构建一键启动\n用户：产品经理\n范围：CLI"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                prd_creator=create_prd,
                card_reply_sender=card_reply,
                reply_sender=None,
            )

            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))
            requirement_payload = json.loads(result.requirement_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "success")
        self.assertEqual(run_payload["status"], "success")
        self.assertEqual(run_payload["detected_input"]["kind"], "inline_text")
        self.assertEqual(run_payload["stages"][0]["status"], "success")
        self.assertTrue(run_payload["stages"][1]["status"], "pending")
        self.assertEqual(requirement_payload["schema_version"], "devflow.requirement.v1")
        self.assertEqual(cards[0][0], "om_evt")
        self.assertEqual(run_payload["publication"]["prd"]["document_id"], "docx_test")
        self.assertEqual(run_payload["publication"]["card_reply"]["status"], "success")
        # idempotency key uses short format: df-{uuid_suffix}-prd-card
        self.assertTrue(cards[0][2].startswith("df-"))
        self.assertIn("prd-card", cards[0][2])

    def test_process_doc_failure_writes_failed_run_and_reply(self) -> None:
        replies = []

        def fetch_doc(_: str) -> RequirementSource:
            raise LarkCliError("文档不可访问")

        def reply(message_id: str, text: str, idempotency_key: str) -> None:
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("https://example.feishu.cn/docx/doc_missing"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                fetch_doc=fetch_doc,
                reply_sender=reply,
            )

            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.requirement_path)
        self.assertEqual(run_payload["stages"][0]["status"], "failed")
        self.assertIn("文档不可访问", run_payload["error"]["message"])
        self.assertIn("补充更具体的需求上下文", build_failure_reply(run_payload))
        self.assertIn("❌ 需求分析 失败", replies[-1][1])

    def test_cli_start_once_processes_mocked_event(self) -> None:
        with temp_run_dir() as temp_dir:
            existing_run_dirs = {path for path in Path(temp_dir).iterdir() if path.is_dir()}
            with patch("devflow.pipeline.listen_bot_events", return_value=[bot_event("目标：演示\n用户：测试\n范围：CLI")]) as listen:
                with patch("devflow.pipeline.send_bot_reply", return_value={"ok": True}):
                    stdout = StringIO()
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "start",
                                "--once",
                                "--timeout",
                                "1",
                                "--out-dir",
                                temp_dir,
                                "--analyzer",
                                "heuristic",
                            ]
                        )

            run_dirs = [
                path
                for path in Path(temp_dir).iterdir()
                if path.is_dir() and path not in existing_run_dirs
            ]
            run_json_exists = (run_dirs[0] / "run.json").exists()
            requirement_json_exists = (run_dirs[0] / "requirement.json").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(run_dirs), 1)
        self.assertTrue(run_json_exists)
        self.assertTrue(requirement_json_exists)
        self.assertIn("success", stdout.getvalue())
        listen.assert_called_once_with(max_events=1, timeout_seconds=1)

    def test_send_bot_reply_uses_expected_lark_cli_command(self) -> None:
        calls = []

        def runner(args: list[str], timeout: int | None):
            calls.append((args, timeout))
            return {"ok": True}

        send_bot_reply("om_123", "完成", "key-123", runner=runner)

        args, timeout = calls[0]
        self.assertEqual(timeout, 120)
        self.assertEqual(
            args,
            [
                "im",
                "+messages-reply",
                "--message-id",
                "om_123",
                "--text",
                "完成",
                "--as",
                "bot",
                "--idempotency-key",
                "key-123",
            ],
        )

    def test_process_llm_message_writes_audit_trace_and_llm_payloads(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
            ),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
        )

        def opener(request, timeout: int):
            return FakeLlmResponse(llm_analysis_payload())

        with temp_run_dir() as temp_dir:
            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=opener):
                    result = process_bot_event(
                        bot_event("Goal: add audit logging"),
                        out_dir=Path(temp_dir),
                        analyzer="llm",
                        model="unused-model",
                        reply_sender=None,
                    )

            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))
            trace_path = result.run_dir / "trace.jsonl"
            request_path = result.run_dir / "llm-request.json"
            response_path = result.run_dir / "llm-response.json"
            trace_text = trace_path.read_text(encoding="utf-8")
            request_text = request_path.read_text(encoding="utf-8")
            response_payload = json.loads(response_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "blocked")
        self.assertEqual(run_payload["audit"]["trace_path"], str(trace_path))
        self.assertEqual(run_payload["audit"]["llm"]["token_usage"]["total_tokens"], 30)
        self.assertEqual(run_payload["audit"]["llm"]["usage_source"], "provider")
        self.assertIn("run_started", trace_text)
        self.assertIn("llm_completed", trace_text)
        self.assertIn("artifact_written", trace_text)
        self.assertIn("Goal: add audit logging", request_text)
        self.assertNotIn("SECRET_VALUE", request_text)
        self.assertNotIn("Authorization", request_text)
        self.assertEqual(response_payload["usage"]["total_tokens"], 30)
        self.assertEqual(response_payload["usage_source"], "provider")

    def test_process_heuristic_message_writes_trace_without_llm_payloads(self) -> None:
        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("目标：构建一键启动\n用户：产品经理\n范围：CLI"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                reply_sender=None,
            )

            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))
            trace_path = result.run_dir / "trace.jsonl"
            trace_text = trace_path.read_text(encoding="utf-8")

        self.assertEqual(result.status, "success")
        self.assertEqual(run_payload["audit"]["trace_path"], str(trace_path))
        self.assertIsNone(run_payload["audit"].get("llm"))
        self.assertIn("analysis_completed", trace_text)
        self.assertFalse((result.run_dir / "llm-request.json").exists())
        self.assertFalse((result.run_dir / "llm-response.json").exists())

    def test_process_llm_message_runs_solution_design_stage(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
            ),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            workspace=WorkspaceConfig(root="", default_repo=""),
        )
        responses = [FakeLlmResponse(llm_analysis_payload()), FakeLlmResponse(llm_solution_payload())]

        def opener(request, timeout: int):
            return responses.pop(0)

        with temp_run_dir() as temp_dir:
            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=opener):
                    result = process_bot_event(
                        bot_event(f"目标：增加方案设计节点\n仓库：{Path.cwd()}"),
                        out_dir=Path(temp_dir),
                        analyzer="llm",
                        model="unused-model",
                        reply_sender=None,
                    )

            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))
            solution_path = result.run_dir / "solution.json"
            solution_payload = json.loads(solution_path.read_text(encoding="utf-8"))
            trace_text = (result.run_dir / "trace.jsonl").read_text(encoding="utf-8")

        self.assertEqual(result.status, "success")
        self.assertEqual(run_payload["stages"][1]["status"], "success")
        self.assertEqual(run_payload["solution_artifact"], str(solution_path))
        self.assertEqual(run_payload["solution_markdown"], str(result.run_dir / "solution.md"))
        self.assertEqual(run_payload["checkpoint_status"], "waiting_approval")
        self.assertEqual(run_payload["checkpoint_artifact"], str(result.run_dir / "checkpoint.json"))
        self.assertEqual(solution_payload["schema_version"], "devflow.solution_design.v1")
        self.assertTrue((result.run_dir / "solution.md").exists())
        self.assertTrue((result.run_dir / "checkpoint.json").exists())
        self.assertIn("workspace_resolved", trace_text)
        self.assertIn("codebase_context_built", trace_text)
        self.assertIn("solution_llm_completed", trace_text)
        self.assertIn("solution_artifact_written", trace_text)

    def test_solution_review_card_failure_sends_text_fallback(self) -> None:
        replies = []
        fake_config = DevflowConfig(
            llm=LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
            ),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            workspace=WorkspaceConfig(root="", default_repo=""),
        )
        responses = [FakeLlmResponse(llm_analysis_payload()), FakeLlmResponse(llm_solution_payload())]

        def opener(request, timeout: int):
            return responses.pop(0)

        def card_reply(_message_id: str, _card: dict, _idempotency_key: str):
            raise LarkCliError("HTTP 400: field validation failed")

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=opener):
                    result = process_bot_event(
                        bot_event(f"目标：增加方案评审\n仓库：{Path.cwd()}"),
                        out_dir=Path(temp_dir),
                        analyzer="llm",
                        model="unused-model",
                        reply_sender=reply_sender,
                        card_reply_sender=card_reply,
                    )

            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "success")
        self.assertEqual(run_payload["checkpoint_publication"]["status"], "failed")
        self.assertIn("field validation failed", run_payload["reply_error"])
        self.assertEqual(replies[-1][0], "om_evt")
        self.assertIn("DevFlow 流水线已完成", replies[-1][1])
        self.assertIn("技术方案", replies[-1][1])

    def test_process_llm_message_without_workspace_blocks_solution_design(self) -> None:
        replies = []
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            workspace=WorkspaceConfig(root="", default_repo=""),
        )

        def build_artifact(*_args):
            payload = llm_analysis_payload()
            content = json.loads(payload["choices"][0]["message"]["content"])
            content["quality"]["ready_for_next_stage"] = True
            return {
                "schema_version": "devflow.requirement.v1",
                "metadata": {"agent": "ProductRequirementAnalyst"},
                **content,
            }

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            with patch("devflow.pipeline.load_config", return_value=fake_config):
                result = process_bot_event(
                    bot_event("目标：新增检查点"),
                    out_dir=Path(temp_dir),
                    analyzer="llm",
                    model="unused-model",
                    build_artifact=build_artifact,
                    prd_creator=lambda *_args: {"document_id": "docx_123", "url": None},
                    card_reply_sender=lambda *_args: None,
                    reply_sender=reply_sender,
                )

            run_payload = json.loads(result.run_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "blocked")
        self.assertEqual(run_payload["stages"][1]["status"], "blocked")
        self.assertEqual(run_payload["checkpoint_status"], "blocked")
        self.assertTrue((result.run_dir / "checkpoint.json").exists())
        self.assertFalse((result.run_dir / "solution.json").exists())
        self.assertIn("技术方案需要读取本机可访问的代码库", replies[-1][1])
        self.assertIn("只回复一行", replies[-1][1])
        self.assertIn("仓库：D:\\path\\to\\repo", replies[-1][1])
        self.assertIn("新项目：snake-game", replies[-1][1])
        self.assertIn("收到后我会继续生成技术方案", replies[-1][1])

    def test_workspace_resume_reply_requires_one_workspace_directive_line(self) -> None:
        self.assertTrue(is_workspace_resume_reply("仓库：D:\\lark"))
        self.assertTrue(is_workspace_resume_reply("新项目：snake-game"))
        self.assertFalse(is_workspace_resume_reply("仓库：D:\\lark\n收到后我会继续生成技术方案"))

    def test_workspace_blocked_reply_first_line_contains_reason_and_action(self) -> None:
        reply = build_workspace_blocked_reply(
            {
                "run_id": "run_visible",
                "requirement_artifact": "artifacts/runs/run_visible/requirement.json",
                "checkpoint_blocked_reason": "仓库路径必须位于 workspace.root 内：D:\\lark\\workspaces。",
            }
        )

        first_line = reply.splitlines()[0]
        self.assertIn("仓库路径必须位于 workspace.root 内：D:\\lark\\workspaces。", first_line)
        self.assertIn("只回复一行", first_line)
        self.assertIn("仓库：D:\\path\\to\\repo", first_line)
        self.assertIn("新项目：snake-game", first_line)

    def test_workspace_resume_records_reply_failure_without_crashing_start(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            workspace=WorkspaceConfig(root=str(Path.cwd()), default_repo=str(Path.cwd())),
        )

        def reply_sender(_message_id: str, _text: str, _idempotency_key: str):
            raise LarkCliError("HTTP 400: field validation failed")

        with temp_run_dir() as temp_dir:
            run_id = f"run_resume_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            requirement_path = run_dir / "requirement.json"
            requirement_path.write_text(
                json.dumps(
                    {
                        "schema_version": "devflow.requirement.v1",
                        "metadata": {"agent": "ProductRequirementAnalyst"},
                        "normalized_requirement": {"title": "检查点", "goals": ["生成方案"], "scope": ["pipeline"]},
                        "acceptance_criteria": [{"id": "AC-001", "criterion": "重跑方案"}],
                        "open_questions": [],
                        "quality": {"ready_for_next_stage": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "status": "blocked",
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "requirement_artifact": str(requirement_path),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "detected_input": {"kind": "inline_text", "value": "目标：检查点"},
                "stages": [{"name": name, "status": "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
                "checkpoint_status": "blocked",
            }
            (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
            write_checkpoint(
                run_dir,
                build_solution_review_checkpoint(run_payload, None, None, status="blocked"),
            )

            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", return_value=FakeLlmResponse(llm_solution_payload())):
                    result = process_bot_event(
                        bot_event(f"仓库：{Path.cwd()}"),
                        out_dir=Path(temp_dir),
                        analyzer="llm",
                        model="unused-model",
                        reply_sender=reply_sender,
                        card_reply_sender=lambda *_args: None,
                    )

            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        self.assertEqual(result.status, "waiting_approval")
        self.assertIn("field validation failed", updated["reply_error"])

    def test_approve_checkpoint_message_records_continue_request(self) -> None:
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            run_id = f"run_approve_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [{"name": name, "status": "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            }
            (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
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
            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        self.assertEqual(result.status, "approved")
        self.assertEqual(updated["checkpoint_status"], "approved")
        self.assertTrue(updated["continuation"]["requested"])
        self.assertIn("已确认", replies[-1][1])

    def test_approve_checkpoint_with_solution_runs_code_test_and_review_generation(self) -> None:
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            run_id = f"run_approve_codegen_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            workspace = run_dir / "workspace"
            workspace.mkdir()
            requirement_path = run_dir / "requirement.json"
            requirement_path.write_text(
                json.dumps(
                    {
                        "schema_version": "devflow.requirement.v1",
                        "normalized_requirement": {"title": "生成代码"},
                        "quality": {"ready_for_next_stage": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            solution_path = run_dir / "solution.json"
            solution_path.write_text(
                json.dumps(
                    {
                        "schema_version": "devflow.solution_design.v1",
                        "workspace": {
                            "mode": "existing_path",
                            "path": str(workspace),
                            "project_name": "workspace",
                            "repo_url": "",
                            "base_branch": "main",
                            "writable": True,
                        },
                        "requirement_summary": {"title": "生成代码"},
                        "proposed_solution": {"summary": "写入 hello.txt"},
                        "change_plan": [{"path": "hello.txt", "action": "create", "responsibility": "示例"}],
                        "quality": {"ready_for_code_generation": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "requirement_artifact": str(requirement_path),
                "solution_artifact": str(solution_path),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [{"name": name, "status": "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            }
            (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
            write_checkpoint(run_dir, build_solution_review_checkpoint(run_payload, solution_path, run_dir / "solution.md"))
            fake_config = DevflowConfig(
                llm=LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
                workspace=WorkspaceConfig(root="", default_repo=str(workspace)),
            )
            code_responses = [
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "tool", "tool": "write_file", "input": {"path": "hello.txt", "content": "hello\n"}})}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "summary": "已生成代码", "changed_files": ["hello.txt"]}, ensure_ascii=False)}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "summary": "已完成测试生成", "generated_tests": []}, ensure_ascii=False)}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "review_status": "passed", "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"}, "findings": [], "repair_recommendations": [], "summary": "代码评审通过", "warnings": []}, ensure_ascii=False)}}]}),
            ]

            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=lambda *args, **kwargs: code_responses.pop(0)):
                    result = process_bot_event(
                        bot_event(f"Approve {run_id}"),
                        out_dir=Path(temp_dir),
                        analyzer="llm",
                        model="unused-model",
                        reply_sender=reply_sender,
                    )
            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        self.assertEqual(result.status, "waiting_code_review")
        self.assertEqual(updated["checkpoint_status"], "waiting_approval")
        self.assertEqual(updated["stages"][2]["status"], "success")
        self.assertEqual(updated["stages"][3]["status"], "success")
        self.assertEqual(updated["stages"][4]["status"], "success")
        self.assertTrue((run_dir / "code-generation.json").exists())
        self.assertTrue((run_dir / "test-generation.json").exists())
        self.assertTrue((run_dir / "code-review.json").exists())
        self.assertTrue((run_dir / "code-review.md").exists())
        self.assertEqual(json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))["stage"], "code_review")
        self.assertTrue((workspace / "hello.txt").exists())
        self.assertIn("代码评审", replies[-1][1])

    def test_blocking_code_review_auto_repairs_once_then_waits_for_review(self) -> None:
        with temp_run_dir() as temp_dir:
            run_id = f"run_review_repair_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            workspace = run_dir / "workspace"
            workspace.mkdir()
            requirement_path = run_dir / "requirement.json"
            requirement_path.write_text(
                json.dumps({"schema_version": "devflow.requirement.v1", "normalized_requirement": {"title": "评审修复"}, "quality": {"ready_for_next_stage": True}}, ensure_ascii=False),
                encoding="utf-8",
            )
            solution_path = run_dir / "solution.json"
            solution_path.write_text(
                json.dumps(
                    {
                        "schema_version": "devflow.solution_design.v1",
                        "workspace": {"mode": "existing_path", "path": str(workspace), "project_name": "workspace", "repo_url": "", "base_branch": "main", "writable": True},
                        "requirement_summary": {"title": "评审修复"},
                        "proposed_solution": {"summary": "写入 hello.txt"},
                        "change_plan": [{"path": "hello.txt", "action": "create", "responsibility": "示例"}],
                        "quality": {"ready_for_code_generation": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "requirement_artifact": str(requirement_path),
                "solution_artifact": str(solution_path),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [{"name": name, "status": "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            }
            fake_config = DevflowConfig(
                llm=LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
                workspace=WorkspaceConfig(root="", default_repo=str(workspace)),
            )
            responses = [
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "tool", "tool": "write_file", "input": {"path": "hello.txt", "content": "bad\n"}})}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "summary": "已生成存在问题的代码", "changed_files": ["hello.txt"]}, ensure_ascii=False)}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "summary": "已完成测试生成", "generated_tests": []}, ensure_ascii=False)}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "review_status": "needs_changes", "quality_gate": {"passed": False, "blocking_findings": 1, "risk_level": "high"}, "findings": [{"id": "CR-001", "severity": "P1", "category": "correctness", "path": "hello.txt", "line": 1, "title": "内容不符合需求", "description": "hello.txt 写入了错误内容。", "evidence": "bad", "fix_suggestion": "写入 hello", "blocking": True}], "repair_recommendations": ["写入 hello"], "summary": "需要修复", "warnings": []}, ensure_ascii=False)}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "tool", "tool": "write_file", "input": {"path": "hello.txt", "content": "hello\n"}})}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "summary": "已按评审意见修复", "changed_files": ["hello.txt"]}, ensure_ascii=False)}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "summary": "已重跑测试", "generated_tests": []}, ensure_ascii=False)}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "review_status": "passed", "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"}, "findings": [], "repair_recommendations": [], "summary": "修复后评审通过", "warnings": []}, ensure_ascii=False)}}]}),
            ]

            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=lambda *args, **kwargs: responses.pop(0)):
                    from devflow.pipeline import run_code_generation_after_approval

                    final_path = run_code_generation_after_approval(run_dir, run_payload)

            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        self.assertEqual(final_path, run_dir / "code-review-attempt-2.json")
        self.assertEqual(updated["repair_attempts"], 1)
        self.assertTrue((run_dir / "code-generation-attempt-2.json").exists())
        self.assertTrue((run_dir / "test-generation-attempt-2.json").exists())
        self.assertTrue((run_dir / "code-review-attempt-2.json").exists())
        self.assertEqual((workspace / "hello.txt").read_text(encoding="utf-8"), "hello\n")
        self.assertEqual(updated["checkpoint_status"], "waiting_approval")

    def test_approve_code_review_checkpoint_generates_delivery_package(self) -> None:
        replies = []

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            run_id = f"run_delivery_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            workspace = run_dir / "workspace"
            workspace.mkdir()
            (workspace / "hello.txt").write_text("hello\n", encoding="utf-8")
            requirement_path = run_dir / "requirement.json"
            solution_path = run_dir / "solution.json"
            code_path = run_dir / "code-generation.json"
            test_path = run_dir / "test-generation.json"
            review_path = run_dir / "code-review.json"
            review_markdown_path = run_dir / "code-review.md"
            workspace_payload = {
                "mode": "existing_path",
                "path": str(workspace),
                "project_name": "workspace",
                "repo_url": "",
                "base_branch": "main",
                "writable": True,
            }
            requirement_path.write_text(
                json.dumps({"schema_version": "devflow.requirement.v1", "normalized_requirement": {"title": "Delivery"}, "quality": {"ready_for_next_stage": True}}, ensure_ascii=False),
                encoding="utf-8",
            )
            solution_path.write_text(
                json.dumps({"schema_version": "devflow.solution_design.v1", "workspace": workspace_payload, "requirement_summary": {"title": "Delivery"}, "proposed_solution": {"summary": "Package change"}, "change_plan": [{"path": "hello.txt"}], "quality": {"ready_for_code_generation": True}}, ensure_ascii=False),
                encoding="utf-8",
            )
            code_path.write_text(
                json.dumps({"schema_version": "devflow.code_generation.v1", "status": "success", "workspace": workspace_payload, "solution_summary": {"title": "Delivery"}, "changed_files": ["hello.txt"], "summary": "已生成代码。", "warnings": [], "tool_events": [], "diff": ""}, ensure_ascii=False),
                encoding="utf-8",
            )
            test_path.write_text(
                json.dumps({"schema_version": "devflow.test_generation.v1", "status": "success", "workspace": workspace_payload, "inputs": {}, "detected_stack": {}, "generated_tests": [], "test_commands": [{"command": "manual", "status": "success", "returncode": 0, "stdout": "ok", "stderr": ""}], "summary": "已验证。", "warnings": [], "tool_events": [], "diff": ""}, ensure_ascii=False),
                encoding="utf-8",
            )
            review_path.write_text(
                json.dumps({"schema_version": "devflow.code_review.v1", "status": "success", "workspace": workspace_payload, "inputs": {}, "review_status": "passed", "quality_gate": {"passed": True, "blocking_findings": 0, "risk_level": "low"}, "findings": [], "test_summary": {}, "diff_summary": {"changed_files": ["hello.txt"]}, "repair_recommendations": [], "summary": "评审通过。", "warnings": [], "tool_events": [], "prompt": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            review_markdown_path.write_text("# review\n", encoding="utf-8")
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "requirement_artifact": str(requirement_path),
                "solution_artifact": str(solution_path),
                "code_generation_artifact": str(code_path),
                "test_generation_artifact": str(test_path),
                "code_review_artifact": str(review_path),
                "code_review_markdown": str(review_markdown_path),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [{"name": name, "status": "success" if name != "delivery" else "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            }
            (run_dir / "run.json").write_text(json.dumps(run_payload, ensure_ascii=False), encoding="utf-8")
            write_checkpoint(run_dir, build_code_review_checkpoint(run_payload, review_path, review_markdown_path))

            result = process_bot_event(
                bot_event(f"Approve {run_id}"),
                out_dir=Path(temp_dir),
                analyzer="llm",
                model="unused-model",
                reply_sender=reply_sender,
            )
            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        self.assertEqual(result.status, "delivered")
        self.assertEqual(updated["status"], "delivered")
        self.assertEqual(updated["stages"][5]["status"], "success")
        self.assertTrue((run_dir / "delivery.json").exists())
        self.assertTrue((run_dir / "delivery.md").exists())
        self.assertTrue((run_dir / "delivery.diff").exists())
        self.assertIn("delivery.json", replies[-1][1])

    def test_reject_code_review_checkpoint_does_not_generate_delivery(self) -> None:
        with temp_run_dir() as temp_dir:
            run_id = f"run_delivery_reject_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            review_path = run_dir / "code-review.json"
            review_markdown_path = run_dir / "code-review.md"
            review_path.write_text("{}", encoding="utf-8")
            review_markdown_path.write_text("# review\n", encoding="utf-8")
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "repair_attempts": 1,
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [{"name": name, "status": "success" if name != "delivery" else "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            }
            (run_dir / "run.json").write_text(json.dumps(run_payload, ensure_ascii=False), encoding="utf-8")
            write_checkpoint(run_dir, build_code_review_checkpoint(run_payload, review_path, review_markdown_path))

            result = process_bot_event(
                bot_event(f"Reject {run_id}: not ready"),
                out_dir=Path(temp_dir),
                analyzer="llm",
                model="unused-model",
                reply_sender=None,
            )
            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        self.assertEqual(result.status, "rejected")
        self.assertEqual(updated["stages"][5]["status"], "pending")
        self.assertFalse((run_dir / "delivery.json").exists())

    def test_test_generation_failure_records_test_stage_without_losing_code_artifact(self) -> None:
        with temp_run_dir() as temp_dir:
            run_id = f"run_testgen_fail_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            workspace = run_dir / "workspace"
            workspace.mkdir()
            requirement_path = run_dir / "requirement.json"
            requirement_path.write_text(
                json.dumps(
                    {
                        "schema_version": "devflow.requirement.v1",
                        "normalized_requirement": {"title": "生成测试"},
                        "quality": {"ready_for_next_stage": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            solution_path = run_dir / "solution.json"
            solution_path.write_text(
                json.dumps(
                    {
                        "schema_version": "devflow.solution_design.v1",
                        "workspace": {
                            "mode": "existing_path",
                            "path": str(workspace),
                            "project_name": "workspace",
                            "repo_url": "",
                            "base_branch": "main",
                            "writable": True,
                        },
                        "requirement_summary": {"title": "生成测试"},
                        "proposed_solution": {"summary": "写入 hello.txt"},
                        "change_plan": [{"path": "hello.txt", "action": "create", "responsibility": "示例"}],
                        "quality": {"ready_for_code_generation": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "requirement_artifact": str(requirement_path),
                "solution_artifact": str(solution_path),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "stages": [{"name": name, "status": "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            }
            (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
            fake_config = DevflowConfig(
                llm=LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
                lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
                workspace=WorkspaceConfig(root="", default_repo=str(workspace)),
            )
            code_responses = [
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "tool", "tool": "write_file", "input": {"path": "hello.txt", "content": "hello\n"}})}}]}),
                FakeLlmResponse({"choices": [{"message": {"content": json.dumps({"action": "finish", "summary": "已生成代码", "changed_files": ["hello.txt"]}, ensure_ascii=False)}}]}),
            ]

            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=lambda *args, **kwargs: code_responses.pop(0)):
                    with patch("devflow.pipeline.build_test_generation_artifact", side_effect=ValueError("测试生成失败")):
                        with self.assertRaises(ValueError):
                            from devflow.pipeline import run_code_generation_after_approval

                            run_code_generation_after_approval(run_dir, run_payload)

            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

        self.assertEqual(updated["stages"][2]["status"], "success")
        self.assertEqual(updated["stages"][3]["status"], "failed")
        self.assertTrue((run_dir / "code-generation.json").exists())
        self.assertEqual(updated["error"]["stage"], "test_generation")

    def test_reject_checkpoint_captures_reason_and_reruns_solution_design(self) -> None:
        replies = []
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="custom", api_key="SECRET_VALUE", model="test-model", base_url="https://example.test/v1"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
            workspace=WorkspaceConfig(root="", default_repo=str(Path.cwd())),
        )

        def reply_sender(message_id: str, text: str, idempotency_key: str):
            replies.append((message_id, text, idempotency_key))

        with temp_run_dir() as temp_dir:
            run_id = f"run_reject_{uuid4().hex}"
            run_dir = Path(temp_dir) / run_id
            run_dir.mkdir()
            requirement_path = run_dir / "requirement.json"
            requirement_path.write_text(
                json.dumps(
                    {
                        "schema_version": "devflow.requirement.v1",
                        "metadata": {"agent": "ProductRequirementAnalyst"},
                        "normalized_requirement": {"title": "检查点", "goals": ["生成方案"], "scope": ["pipeline"]},
                        "acceptance_criteria": [{"id": "AC-001", "criterion": "重跑方案"}],
                        "open_questions": [],
                        "quality": {"ready_for_next_stage": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run_payload = {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_id,
                "status": "success",
                "run_dir": str(run_dir),
                "run_path": str(run_dir / "run.json"),
                "requirement_artifact": str(requirement_path),
                "trigger": {"chat_id": "oc_123", "sender_id": "ou_123"},
                "detected_input": {"kind": "inline_text", "value": "目标：检查点\n仓库：D:\\lark"},
                "stages": [{"name": name, "status": "pending"} for name in ["requirement_intake", "solution_design", "code_generation", "test_generation", "code_review", "delivery"]],
            }
            (run_dir / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
            write_checkpoint(
                run_dir,
                build_solution_review_checkpoint(run_payload, run_dir / "solution.json", run_dir / "solution.md"),
            )

            first = process_bot_event(
                bot_event(f"Reject {run_id}"),
                out_dir=Path(temp_dir),
                analyzer="llm",
                model="unused-model",
                reply_sender=reply_sender,
            )
            responses = [FakeLlmResponse(llm_solution_payload())]
            with patch("devflow.pipeline.load_config", return_value=fake_config):
                with patch("devflow.llm.request.urlopen", side_effect=lambda *args, **kwargs: responses.pop(0)):
                    second = process_bot_event(
                        bot_event("请补充移动端触屏控制"),
                        out_dir=Path(temp_dir),
                        analyzer="llm",
                        model="unused-model",
                        reply_sender=reply_sender,
                        card_reply_sender=lambda *_args: None,
                    )

            updated = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))

        self.assertEqual(first.status, "awaiting_reject_reason")
        self.assertEqual(second.status, "waiting_approval")
        self.assertEqual(checkpoint["attempt"], 2)
        self.assertEqual(checkpoint["reject_reason"], "请补充移动端触屏控制")
        self.assertTrue((run_dir / "solution-attempt-2.json").exists())
        self.assertEqual(updated["checkpoint_status"], "waiting_approval")
        reject_reason_replies = [r for r in replies if "请补充 Reject 理由" in r[1]]
        self.assertTrue(len(reject_reason_replies) >= 1)

    def test_process_doc_failure_writes_trace_before_failed_run(self) -> None:
        def fetch_doc(_: str) -> RequirementSource:
            raise LarkCliError("document is not accessible")

        with temp_run_dir() as temp_dir:
            result = process_bot_event(
                bot_event("https://example.feishu.cn/docx/doc_missing"),
                out_dir=Path(temp_dir),
                analyzer="heuristic",
                model="test-model",
                fetch_doc=fetch_doc,
                reply_sender=None,
            )

            trace_text = (result.run_dir / "trace.jsonl").read_text(encoding="utf-8")

        self.assertEqual(result.status, "failed")
        self.assertIn("source_resolution_failed", trace_text)
        self.assertIn("run_failed", trace_text)


def _failure_payload(stage: str, message: str) -> dict:
    return {
        "run_id": "run_test",
        "run_path": "/tmp/run.json",
        "detected_input": {"kind": "inline_text", "value": "test"},
        "error": {"stage": stage, "message": message, "hint": "default hint"},
    }


class StageFailureSuggestionTests(unittest.TestCase):
    def test_requirement_intake_suggestion(self) -> None:
        suggestion = _stage_failure_suggestion("requirement_intake", "文档不可访问")
        self.assertEqual(suggestion, "补充更具体的需求上下文后重新发送消息。")

    def test_solution_design_llm_error(self) -> None:
        suggestion = _stage_failure_suggestion("solution_design", "LlmError: api_key missing")
        self.assertEqual(suggestion, "检查 LLM 配置和 API Key 是否有效。")

    def test_solution_design_timeout(self) -> None:
        suggestion = _stage_failure_suggestion("solution_design", "请求 timeout 超时")
        self.assertEqual(suggestion, "检查 LLM 配置和 API Key 是否有效。")

    def test_solution_design_non_llm_error(self) -> None:
        suggestion = _stage_failure_suggestion("solution_design", "方案解析失败")
        self.assertEqual(suggestion, "检查需求描述是否足够清晰，或尝试简化需求范围。")

    def test_code_generation_quality_gate_error(self) -> None:
        suggestion = _stage_failure_suggestion("code_generation", "QualityGateError: 方案质量未通过")
        self.assertEqual(suggestion, "方案质量未通过门禁，可尝试 Reject 后重新设计方案。")

    def test_code_generation_non_quality_gate_error(self) -> None:
        suggestion = _stage_failure_suggestion("code_generation", "代码生成失败")
        self.assertEqual(suggestion, "检查需求描述是否足够清晰，或尝试简化需求范围。")

    def test_test_generation_suggestion(self) -> None:
        suggestion = _stage_failure_suggestion("test_generation", "测试框架未找到")
        self.assertEqual(suggestion, "检查项目测试框架配置是否正确。")

    def test_code_review_suggestion(self) -> None:
        suggestion = _stage_failure_suggestion("code_review", "评审发现严重问题")
        self.assertEqual(suggestion, "检查代码变更是否符合需求描述。")

    def test_delivery_suggestion(self) -> None:
        suggestion = _stage_failure_suggestion("delivery", "Git 操作失败")
        self.assertEqual(suggestion, "检查工作区 Git 状态是否正常。")

    def test_unknown_stage_suggestion(self) -> None:
        suggestion = _stage_failure_suggestion("unknown_stage", "some error")
        self.assertEqual(suggestion, "请检查错误信息后重试。")


class BuildFailureReplySuggestionTests(unittest.TestCase):
    def test_requirement_intake_reply_contains_suggestion_and_retry(self) -> None:
        reply = build_failure_reply(_failure_payload("requirement_intake", "文档不可访问"))
        self.assertIn("❌ 需求分析 失败：文档不可访问", reply)
        self.assertIn("💡 建议：补充更具体的需求上下文后重新发送消息。", reply)
        self.assertIn("🔄 请修改后重新发送需求描述。", reply)

    def test_solution_design_llm_reply_contains_llm_suggestion(self) -> None:
        reply = build_failure_reply(_failure_payload("solution_design", "LlmError: api_key invalid"))
        self.assertIn("❌ 方案设计 失败", reply)
        self.assertIn("💡 建议：检查 LLM 配置和 API Key 是否有效。", reply)

    def test_solution_design_non_llm_reply_contains_generic_suggestion(self) -> None:
        reply = build_failure_reply(_failure_payload("solution_design", "方案解析失败"))
        self.assertIn("💡 建议：检查需求描述是否足够清晰，或尝试简化需求范围。", reply)

    def test_code_generation_quality_gate_reply_contains_suggestion(self) -> None:
        reply = build_failure_reply(_failure_payload("code_generation", "QualityGateError: 质量门禁未通过"))
        self.assertIn("❌ 代码生成 失败", reply)
        self.assertIn("💡 建议：方案质量未通过门禁，可尝试 Reject 后重新设计方案。", reply)

    def test_test_generation_reply_contains_suggestion(self) -> None:
        reply = build_failure_reply(_failure_payload("test_generation", "测试框架未配置"))
        self.assertIn("❌ 测试生成 失败", reply)
        self.assertIn("💡 建议：检查项目测试框架配置是否正确。", reply)

    def test_code_review_reply_contains_suggestion(self) -> None:
        reply = build_failure_reply(_failure_payload("code_review", "评审不通过"))
        self.assertIn("❌ 代码评审 失败", reply)
        self.assertIn("💡 建议：检查代码变更是否符合需求描述。", reply)

    def test_delivery_reply_contains_suggestion(self) -> None:
        reply = build_failure_reply(_failure_payload("delivery", "Git merge conflict"))
        self.assertIn("❌ 交付 失败", reply)
        self.assertIn("💡 建议：检查工作区 Git 状态是否正常。", reply)

    def test_reply_contains_run_id_and_run_path(self) -> None:
        reply = build_failure_reply(_failure_payload("delivery", "error"))
        self.assertIn("运行 ID：run_test", reply)
        self.assertIn("运行记录：/tmp/run.json", reply)


if __name__ == "__main__":
    unittest.main()
