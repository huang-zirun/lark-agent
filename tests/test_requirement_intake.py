from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from devflow.cli import main
from devflow.config import DevflowConfig, LarkConfig, LlmConfig
from devflow.intake.analyzer import build_requirement_artifact
from devflow.intake.lark_cli import (
    LarkCliNotFound,
    bot_message_event_command,
    event_to_source,
    fetch_doc_source,
    fetch_message_source,
    find_lark_cli_executable,
    listen_bot_sources,
    run_lark_cli,
)
from devflow.intake.models import SCHEMA_VERSION, RequirementSource


class RequirementIntakeTests(unittest.TestCase):
    def test_doc_payload_normalizes_to_requirement_source(self) -> None:
        def runner(args: list[str], timeout: int | None):
            self.assertIn("+fetch", args)
            return {
                "ok": True,
                "identity": "user",
                "data": {
                    "document": {
                        "document_id": "doc_123",
                        "title": "客服工单分流优化",
                        "content": "# 客服工单分流优化\n\n背景：客服响应慢。\n目标：提升分流效率。",
                    }
                },
            }

        source = fetch_doc_source("https://example.feishu.cn/docx/doc_123", runner=runner)

        self.assertEqual(source.source_type, "lark_doc")
        self.assertEqual(source.source_id, "doc_123")
        self.assertIn("提升分流效率", source.content)
        self.assertEqual(source.identity, "user")

    def test_doc_payload_uses_lark_cli_1_0_23_v2_markdown_shape(self) -> None:
        def runner(args: list[str], timeout: int | None):
            self.assertEqual(
                args,
                [
                    "docs",
                    "+fetch",
                    "--api-version",
                    "v2",
                    "--doc",
                    "https://example.feishu.cn/docx/doc_real",
                    "--doc-format",
                    "markdown",
                    "--format",
                    "json",
                ],
            )
            return {
                "ok": True,
                "identity": "bot",
                "data": {
                    "doc_id": "doc_real",
                    "title": "真实文档",
                    "markdown": "# 真实文档\n\n目标：验证真实 lark-cli 文档读取。",
                    "total_length": 33,
                },
            }

        source = fetch_doc_source("https://example.feishu.cn/docx/doc_real", runner=runner)

        self.assertEqual(source.source_id, "doc_real")
        self.assertEqual(source.title, "真实文档")
        self.assertEqual(source.identity, "bot")
        self.assertIn("验证真实 lark-cli", source.content)

    def test_message_payload_normalizes_json_content(self) -> None:
        def runner(args: list[str], timeout: int | None):
            self.assertIn("+messages-mget", args)
            return {
                "identity": "user",
                "data": {
                    "messages": [
                        {
                            "message_id": "om_123",
                            "msg_type": "text",
                            "content": json.dumps({"text": "需求：支持从飞书机器人提交需求"}),
                        }
                    ]
                },
            }

        source = fetch_message_source("om_123", runner=runner)

        self.assertEqual(source.source_type, "lark_message")
        self.assertEqual(source.source_id, "om_123")
        self.assertEqual(source.content, "需求：支持从飞书机器人提交需求")

    def test_event_payload_normalizes_to_bot_source(self) -> None:
        source = event_to_source(
            {
                "event": {
                    "message_id": "om_evt",
                    "chat_id": "oc_123",
                    "content": {"text": "目标：让产品经理在飞书里提交 PRD"},
                }
            }
        )

        self.assertEqual(source.source_type, "lark_bot_event")
        self.assertEqual(source.identity, "bot")
        self.assertIn("PRD", source.content)

    def test_listen_bot_uses_lark_cli_consume_shape(self) -> None:
        def runner(args: list[str], timeout: int | None):
            self.assertEqual(
                args,
                [
                    "event",
                    "consume",
                    "im.message.receive_v1",
                    "--max-events",
                    "1",
                    "--timeout",
                    "60s",
                    "--as",
                    "bot",
                ],
            )
            self.assertEqual(timeout, 75)
            return [
                {
                    "event": {
                        "message_id": "om_evt",
                        "chat_id": "oc_123",
                        "content": {"text": "目标：让机器人消息生成需求 JSON"},
                    }
                }
            ]

        sources = listen_bot_sources(max_events=1, timeout_seconds=60, runner=runner)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_type, "lark_bot_event")
        self.assertIn("需求 JSON", sources[0].content)

    def test_bot_message_event_command_uses_consume_with_bounds(self) -> None:
        self.assertEqual(
            bot_message_event_command(max_events=2, timeout_seconds=30),
            [
                "event",
                "consume",
                "im.message.receive_v1",
                "--max-events",
                "2",
                "--timeout",
                "30s",
                "--as",
                "bot",
            ],
        )

    def test_artifact_has_required_contract_fields_and_chinese_runtime_text(self) -> None:
        source = RequirementSource(
            source_type="fixture",
            source_id="fixture-1",
            reference="fixture",
            title="需求采集节点",
            content=(
                "# 需求采集节点\n\n"
                "背景：需求散落在飞书文档和群消息里。\n"
                "用户：产品经理和研发负责人。\n"
                "问题：下游 agent 难以理解原始需求。\n"
                "目标：输出稳定 JSON。\n"
                "范围：首版支持文档和消息。\n"
                "验收：给定飞书文档，运行命令后生成 devflow.requirement.v1 JSON。"
            ),
        )

        artifact = build_requirement_artifact(source)

        self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)
        self.assertIn("metadata", artifact)
        self.assertIn("normalized_requirement", artifact)
        self.assertIn("acceptance_criteria", artifact)
        self.assertIn("sections", artifact)
        self.assertTrue(artifact["quality"]["ready_for_next_stage"])
        self.assertIn("资深产品经理", artifact["prompt"]["system_prompt"])
        self.assertIn("优先阅读 normalized_requirement", artifact["implementation_hints"]["handoff_note"])

    def test_chinese_heuristic_extracts_core_fields(self) -> None:
        source = RequirementSource(
            source_type="fixture",
            source_id="zh-fixture",
            reference="fixture",
            content=(
                "背景：客服工单依赖人工分配，响应速度慢。\n"
                "用户：客服主管和一线客服。\n"
                "问题：高峰期工单无法及时分流。\n"
                "目标：自动识别工单类型并提升分流效率。\n"
                "范围：首版支持文本工单和人工兜底。\n"
                "非目标：本期不做自动回复。\n"
                "验收：创建新工单后，系统能在 10 秒内给出分流建议。"
            ),
        )

        artifact = build_requirement_artifact(source)

        self.assertIn("客服主管", artifact["normalized_requirement"]["target_users"][0])
        self.assertIn("高峰期工单", artifact["normalized_requirement"]["problem"][0])
        self.assertIn("自动识别工单类型", artifact["normalized_requirement"]["goals"][0])
        self.assertEqual(artifact["acceptance_criteria"][0]["source"], "explicit")
        self.assertIn("创建新工单", artifact["acceptance_criteria"][0]["criterion"])
        self.assertTrue(artifact["quality"]["ready_for_next_stage"])

    def test_long_content_is_split_into_progressive_sections(self) -> None:
        content = "目标：支持需求采集。\n\n" + "\n\n".join(
            f"段落 {index}：这是很长的需求背景，用于验证渐进式披露。" * 20
            for index in range(40)
        )
        source = RequirementSource(
            source_type="fixture",
            source_id="long-doc",
            reference="fixture",
            content=content,
        )

        artifact = build_requirement_artifact(source)

        self.assertLessEqual(len(artifact["source"]["safe_summary"]), 600)
        self.assertGreater(len(artifact["sections"]), 1)
        self.assertIn("content_ref", artifact["sections"][0])
        self.assertTrue(artifact["sections"][0]["title"].startswith("片段 "))

    def test_missing_lark_cli_has_actionable_error(self) -> None:
        with patch("shutil.which", return_value=None):
            with self.assertRaises(LarkCliNotFound) as raised:
                run_lark_cli(["auth", "status"])

        message = str(raised.exception)
        self.assertIn("未在 PATH 中找到 lark-cli", message)
        self.assertIn("npm.cmd install -g @larksuite/cli@1.0.23", message)

    def test_windows_prefers_cmd_shim_for_lark_cli(self) -> None:
        def which(name: str) -> str | None:
            if name == "lark-cli.cmd":
                return r"D:\DevTools\npm-global\lark-cli.cmd"
            if name == "lark-cli":
                return r"D:\DevTools\npm-global\lark-cli.ps1"
            return None

        with patch("devflow.intake.lark_cli.os.name", "nt"):
            with patch("shutil.which", side_effect=which):
                executable = find_lark_cli_executable()

        self.assertTrue(executable.endswith("lark-cli.cmd"))

    def test_cli_from_doc_writes_artifact(self) -> None:
        fake_source = RequirementSource(
            source_type="lark_doc",
            source_id="doc_123",
            reference="doc_123",
            content="目标：生成 JSON。\n用户：产品经理。\n范围：首版 CLI。",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = Path(temp_dir) / "requirement.json"
            with patch("devflow.cli.fetch_doc_source", return_value=fake_source):
                with redirect_stdout(StringIO()):
                    exit_code = main(
                        [
                            "intake",
                            "from-doc",
                            "--doc",
                            "doc_123",
                            "--analyzer",
                            "heuristic",
                            "--out",
                            str(out_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            artifact = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)

    def test_cli_from_doc_defaults_to_llm_analyzer(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test-api-key", model="ep-test"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
        )
        fake_source = RequirementSource(
            source_type="lark_doc",
            source_id="doc_123",
            reference="doc_123",
            content="目标：生成 JSON。",
        )
        fake_artifact = {
            "schema_version": SCHEMA_VERSION,
            "metadata": {"analyzer": "llm"},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = Path(temp_dir) / "requirement.json"
            with patch("devflow.cli.fetch_doc_source", return_value=fake_source):
                with patch("devflow.cli.load_config", return_value=fake_config):
                    with patch(
                        "devflow.cli.build_requirement_artifact",
                        return_value=fake_artifact,
                    ) as build:
                        with redirect_stdout(StringIO()):
                            exit_code = main(
                                ["intake", "from-doc", "--doc", "doc_123", "--out", str(out_path)]
                            )

        self.assertEqual(exit_code, 0)
        build.assert_called_once()
        _, kwargs = build.call_args
        self.assertEqual(kwargs["analyzer"], "llm")
        self.assertEqual(kwargs["llm_config"].model, "ep-test")


if __name__ == "__main__":
    unittest.main()
