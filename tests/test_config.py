from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from devflow.cli import main
from devflow.config import (
    ConfigError,
    DevflowConfig,
    LarkConfig,
    LlmConfig,
    load_config,
)
from devflow.intake.models import RequirementSource


class ConfigTests(unittest.TestCase):
    def test_missing_config_has_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"

            with self.assertRaises(ConfigError) as raised:
                load_config(config_path)

        message = str(raised.exception)
        self.assertIn("config.example.json", message)
        self.assertIn("config.json", message)
        self.assertIn("未找到配置文件", message)

    def test_invalid_json_error_does_not_echo_secret_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"llm":{"api_key":"SECRET_VALUE"}', encoding="utf-8")

            with self.assertRaises(ConfigError) as raised:
                load_config(config_path)

        self.assertNotIn("SECRET_VALUE", str(raised.exception))
        self.assertIn("不是有效的 JSON", str(raised.exception))

    def test_loads_config_with_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {"provider": "ark", "api_key": "test-api-key"},
                        "lark": {"cli_version": "1.0.23", "test_doc": "doc_123"},
                    }
                ),
                encoding="utf-8-sig",
            )

            config = load_config(config_path, require_lark_test_doc=True)

        self.assertEqual(config.lark.test_doc, "doc_123")
        self.assertEqual(config.llm.temperature, 0.2)
        self.assertEqual(config.llm.max_tokens, 4096)
        self.assertEqual(config.llm.timeout_seconds, 120)
        self.assertFalse(config.llm.response_format_json)

    def test_missing_required_fields_report_field_names_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {"provider": "ark", "api_key": ""},
                        "lark": {
                            "cli_version": "1.0.23",
                            "app_id": "",
                            "app_secret": "",
                            "test_doc": "",
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as raised:
                load_config(
                    config_path,
                    require_llm_api_key=True,
                    require_llm_model=True,
                    require_lark_credentials=True,
                    require_lark_test_doc=True,
                )

        self.assertEqual(str(raised.exception), "缺少必填配置项：llm.api_key。")

    def test_loads_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "llm": {
                            "provider": "ark",
                            "api_key": "test-api-key",
                            "model": "ep-test",
                            "temperature": 0,
                            "max_tokens": 1000,
                            "timeout_seconds": 30,
                            "response_format_json": True,
                        },
                        "lark": {
                            "cli_version": "1.0.23",
                            "app_id": "cli_a",
                            "app_secret": "test-secret",
                            "test_doc": "doc_123",
                            "artifact_folder_token": "fld_artifacts",
                            "prd_folder_token": "fld_prd",
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(
                config_path,
                require_llm_api_key=True,
                require_llm_model=True,
                require_lark_credentials=True,
                require_lark_test_doc=True,
            )

        self.assertEqual(config.llm.provider, "ark")
        self.assertEqual(config.llm.api_key, "test-api-key")
        self.assertEqual(config.llm.model, "ep-test")
        self.assertEqual(config.llm.temperature, 0.0)
        self.assertEqual(config.llm.max_tokens, 1000)
        self.assertEqual(config.llm.timeout_seconds, 30)
        self.assertTrue(config.llm.response_format_json)
        self.assertEqual(config.lark.cli_version, "1.0.23")
        self.assertEqual(config.lark.app_id, "cli_a")
        self.assertEqual(config.lark.app_secret, "test-secret")
        self.assertEqual(config.lark.test_doc, "doc_123")
        self.assertEqual(config.lark.artifact_folder_token, "fld_artifacts")
        self.assertEqual(config.lark.prd_folder_token, "fld_prd")

    def test_rejects_unlocked_lark_cli_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps({"lark": {"cli_version": "1.0.15"}}),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError) as raised:
                load_config(config_path)

        self.assertIn("期望 1.0.23", str(raised.exception))


class CliConfigFallbackTests(unittest.TestCase):
    def test_from_doc_uses_config_test_doc_when_doc_argument_is_missing(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test-api-key", model="ep-test"),
            lark=LarkConfig(
                cli_version="1.0.23",
                app_id="cli_a",
                app_secret="test-secret",
                test_doc="doc_from_config",
            ),
        )
        fake_source = RequirementSource(
            source_type="lark_doc",
            source_id="doc_from_config",
            reference="doc_from_config",
            content="目标：生成 JSON。",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = Path(temp_dir) / "requirement.json"
            with patch("devflow.cli.load_config", return_value=fake_config):
                with patch("devflow.cli.fetch_doc_source", return_value=fake_source) as fetch:
                    with patch("devflow.cli.build_requirement_artifact", return_value={}) as build:
                        with redirect_stdout(StringIO()):
                            exit_code = main(
                                    [
                                        "intake",
                                        "from-doc",
                                        "--out",
                                        str(out_path),
                                    ]
                            )

        self.assertEqual(exit_code, 0)
        fetch.assert_called_once_with("doc_from_config")

    def test_doctor_reports_ready_when_config_cli_and_auth_are_ok(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test-api-key", model="ep-test"),
            lark=LarkConfig(
                cli_version="1.0.23",
                app_id="cli_a",
                app_secret="test-secret",
                test_doc="doc_from_config",
            ),
        )

        with patch("devflow.cli.load_config", return_value=fake_config):
            with patch("devflow.cli.find_lark_cli_executable", return_value="lark-cli.cmd"):
                with patch("devflow.cli.ensure_lark_cli_version", return_value="1.0.23"):
                    with patch("devflow.cli.get_lark_cli_auth_status", return_value="ok"):
                        stdout = StringIO()
                        with redirect_stdout(stdout):
                            exit_code = main(["intake", "doctor"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("配置：正常", output)
        self.assertIn("LLM 提供者：ark", output)
        self.assertIn("LLM 模型：ep-test", output)
        self.assertIn("lark-cli 版本：1.0.23", output)
        self.assertIn("lark-cli 认证：正常", output)

    def test_doctor_can_skip_auth_before_interactive_login(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test-api-key", model="ep-test"),
            lark=LarkConfig(
                cli_version="1.0.23",
                app_id="cli_a",
                app_secret="test-secret",
                test_doc="doc_from_config",
            ),
        )

        with patch("devflow.cli.load_config", return_value=fake_config):
            with patch("devflow.cli.find_lark_cli_executable", return_value="lark-cli.cmd"):
                with patch("devflow.cli.ensure_lark_cli_version", return_value="1.0.23"):
                    with patch("devflow.cli.get_lark_cli_auth_status") as auth_status:
                        stdout = StringIO()
                        with redirect_stdout(stdout):
                            exit_code = main(["intake", "doctor", "--skip-auth"])

        self.assertEqual(exit_code, 0)
        auth_status.assert_not_called()
        self.assertIn("lark-cli 认证：已跳过", stdout.getvalue())

    def test_doctor_can_probe_llm(self) -> None:
        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="test-api-key", model="ep-test"),
            lark=LarkConfig(
                cli_version="1.0.23",
                app_id="cli_a",
                app_secret="test-secret",
                test_doc="doc_from_config",
            ),
        )

        with patch("devflow.cli.load_config", return_value=fake_config):
            with patch("devflow.cli.find_lark_cli_executable", return_value="lark-cli.cmd"):
                with patch("devflow.cli.ensure_lark_cli_version", return_value="1.0.23"):
                    with patch("devflow.cli.probe_llm") as probe:
                        stdout = StringIO()
                        with redirect_stdout(stdout):
                            exit_code = main(["intake", "doctor", "--skip-auth", "--check-llm"])

        self.assertEqual(exit_code, 0)
        probe.assert_called_once_with(fake_config.llm)
        self.assertIn("LLM 连通性：正常", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
