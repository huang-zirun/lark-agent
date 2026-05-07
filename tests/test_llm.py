from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib import error

from devflow.config import LlmConfig
from devflow.intake.analyzer import build_requirement_artifact, normalize_llm_analysis
from devflow.intake.models import SCHEMA_VERSION, RequirementSource
from devflow.llm import (
    LlmError,
    chat_completion,
    chat_completion_content,
    parse_llm_json,
    probe_llm,
    resolve_base_url,
)


class FakeResponse:
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


class LlmTests(unittest.TestCase):
    def test_provider_default_base_urls(self) -> None:
        self.assertEqual(
            resolve_base_url(LlmConfig(provider="ark")),
            "https://ark.cn-beijing.volces.com/api/v3",
        )
        self.assertEqual(
            resolve_base_url(LlmConfig(provider="bailian")),
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(
            resolve_base_url(LlmConfig(provider="deepseek")),
            "https://api.deepseek.com",
        )
        self.assertEqual(
            resolve_base_url(LlmConfig(provider="mimo")),
            "https://api.xiaomimimo.com/v1",
        )
        self.assertEqual(
            resolve_base_url(LlmConfig(provider="openai")),
            "https://api.openai.com/v1",
        )

    def test_custom_provider_requires_base_url(self) -> None:
        with self.assertRaises(LlmError) as raised:
            resolve_base_url(LlmConfig(provider="custom"))

        self.assertIn("llm.base_url", str(raised.exception))
        self.assertIn("缺少必填配置", str(raised.exception))

    def test_chat_completion_builds_openai_compatible_request(self) -> None:
        seen = {}

        def opener(request, timeout: int):
            seen["url"] = request.full_url
            seen["auth"] = request.headers["Authorization"]
            seen["timeout"] = timeout
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(
                {
                    "choices": [
                        {"message": {"content": "{\"ok\":true}"}},
                    ]
                }
            )

        content = chat_completion_content(
            LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
                timeout_seconds=12,
            ),
            [{"role": "user", "content": "hi"}],
            opener=opener,
        )

        self.assertEqual(content, "{\"ok\":true}")
        self.assertEqual(seen["url"], "https://example.test/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer SECRET_VALUE")
        self.assertEqual(seen["timeout"], 12)
        self.assertEqual(seen["body"]["model"], "test-model")
        self.assertNotIn("response_format", seen["body"])

    def test_chat_completion_returns_raw_response_usage_and_timing(self) -> None:
        def opener(request, timeout: int):
            return FakeResponse(
                {
                    "id": "chatcmpl_123",
                    "choices": [
                        {"message": {"content": "{\"ok\":true}"}},
                    ],
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 7,
                        "total_tokens": 12,
                    },
                }
            )

        result = chat_completion(
            LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
            ),
            [{"role": "user", "content": "hi"}],
            opener=opener,
        )

        self.assertEqual(result.content, "{\"ok\":true}")
        self.assertEqual(result.usage["total_tokens"], 12)
        self.assertEqual(result.usage_source, "provider")
        self.assertEqual(result.raw_response["id"], "chatcmpl_123")
        self.assertIsInstance(result.duration_ms, int)
        audit_payload = result.to_audit_payload()
        self.assertIn("started_at", audit_payload)
        self.assertEqual(audit_payload["provider"], "custom")
        self.assertEqual(audit_payload["model"], "test-model")
        self.assertEqual(audit_payload["base_url_host"], "example.test")
        self.assertEqual(audit_payload["usage_source"], "provider")

    def test_chat_completion_marks_missing_usage_without_estimating(self) -> None:
        def opener(request, timeout: int):
            return FakeResponse({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

        result = chat_completion(
            LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
            ),
            [{"role": "user", "content": "hi"}],
            opener=opener,
        )

        self.assertIsNone(result.usage)
        self.assertEqual(result.usage_source, "missing")

    def test_chat_completion_audit_request_does_not_include_secret_or_authorization(self) -> None:
        def opener(request, timeout: int):
            return FakeResponse({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

        result = chat_completion(
            LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
            ),
            [{"role": "user", "content": "hi"}],
            opener=opener,
        )

        request_text = json.dumps(result.request_body, ensure_ascii=False)
        self.assertNotIn("SECRET_VALUE", request_text)
        self.assertNotIn("Authorization", request_text)

    def test_chat_completion_can_request_json_response_format(self) -> None:
        seen = {}

        def opener(request, timeout: int):
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

        chat_completion_content(
            LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
                response_format_json=True,
            ),
            [{"role": "user", "content": "hi"}],
            opener=opener,
        )

        self.assertEqual(seen["body"]["response_format"], {"type": "json_object"})

    def test_http_error_does_not_echo_secret(self) -> None:
        def opener(request, timeout: int):
            raise error.HTTPError(request.full_url, 401, "bad SECRET_VALUE", {}, None)

        with self.assertRaises(LlmError) as raised:
            chat_completion_content(
                LlmConfig(
                    provider="custom",
                    api_key="SECRET_VALUE",
                    model="test-model",
                    base_url="https://example.test/v1",
                ),
                [{"role": "user", "content": "hi"}],
                opener=opener,
            )

        self.assertNotIn("SECRET_VALUE", str(raised.exception))
        self.assertIn("HTTP 401", str(raised.exception))
        self.assertIn("LLM 请求失败", str(raised.exception))

    def test_parse_llm_json_extracts_json_object(self) -> None:
        self.assertEqual(parse_llm_json("```json\n{\"ok\": true}\n```"), {"ok": True})

    def test_normalize_llm_analysis_requires_fields(self) -> None:
        with self.assertRaises(LlmError) as raised:
            normalize_llm_analysis({"normalized_requirement": {}})

        self.assertIn("product_analysis", str(raised.exception))
        self.assertIn("缺少必填字段", str(raised.exception))

    def test_llm_prompt_requests_chinese_values_with_english_contract(self) -> None:
        seen = {}

        def fake_chat(config: LlmConfig, messages: list[dict[str, str]]):
            seen["messages"] = messages
            return json.dumps(
                {
                    "normalized_requirement": {
                        "title": "需求采集",
                        "background": ["需求来自飞书"],
                        "target_users": ["产品经理"],
                        "problem": ["信息分散"],
                        "goals": ["输出结构化需求"],
                        "non_goals": [],
                        "scope": ["首版支持文档"],
                    },
                    "product_analysis": {
                        "user_scenarios": ["产品经理提交需求"],
                        "business_value": ["减少沟通成本"],
                        "evidence": [],
                        "assumptions": [],
                        "risks": [],
                        "dependencies": [],
                    },
                    "acceptance_criteria": [
                        {"id": "AC-001", "source": "llm", "criterion": "能生成中文需求分析"}
                    ],
                    "open_questions": [],
                    "quality": {
                        "completeness_score": 0.8,
                        "ambiguity_score": 0.1,
                        "ready_for_next_stage": True,
                        "warnings": [],
                    },
                },
                ensure_ascii=False,
            )

        source = RequirementSource(
            source_type="fixture",
            source_id="fixture-1",
            reference="fixture",
            content="目标：生成结构化需求。",
        )
        with patch("devflow.intake.analyzer.chat_completion_content", side_effect=fake_chat):
            build_requirement_artifact(
                source,
                llm_config=LlmConfig(
                    provider="custom",
                    api_key="test-api-key",
                    model="test-model",
                    base_url="https://example.test/v1",
                ),
            )

        self.assertIn("简体中文", seen["messages"][0]["content"])
        self.assertIn("字段名必须保持英文", seen["messages"][1]["content"])
        self.assertIn("normalized_requirement", seen["messages"][1]["content"])

    def test_build_requirement_artifact_with_llm_metadata(self) -> None:
        payload = {
            "normalized_requirement": {
                "title": "需求",
                "background": ["背景"],
                "target_users": ["PM"],
                "problem": ["问题"],
                "goals": ["目标"],
                "non_goals": [],
                "scope": ["首版"],
            },
            "product_analysis": {
                "user_scenarios": ["场景"],
                "business_value": ["价值"],
                "evidence": [],
                "assumptions": [],
                "risks": [],
                "dependencies": [],
            },
            "acceptance_criteria": [{"id": "AC-001", "source": "llm", "criterion": "可验收"}],
            "open_questions": [],
            "quality": {
                "completeness_score": 0.8,
                "ambiguity_score": 0.1,
                "ready_for_next_stage": True,
                "warnings": [],
            },
        }

        source = RequirementSource(
            source_type="fixture",
            source_id="fixture-1",
            reference="fixture",
            content="目标：生成结构化需求。",
        )
        with patch("devflow.intake.analyzer.chat_completion_content", return_value=json.dumps(payload)):
            artifact = build_requirement_artifact(
                source,
                llm_config=LlmConfig(
                    provider="custom",
                    api_key="test-api-key",
                    model="test-model",
                    base_url="https://example.test/v1",
                ),
            )

        self.assertEqual(artifact["schema_version"], SCHEMA_VERSION)
        self.assertEqual(artifact["metadata"]["analyzer"], "llm")
        self.assertEqual(artifact["metadata"]["model"], "test-model")

    def test_probe_llm_uses_chinese_json_probe_prompt(self) -> None:
        seen = {}

        def opener(request, timeout: int):
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

        probe_llm(
            LlmConfig(
                provider="custom",
                api_key="SECRET_VALUE",
                model="test-model",
                base_url="https://example.test/v1",
            ),
            opener=opener,
        )

        self.assertIn("只返回 JSON", seen["body"]["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
