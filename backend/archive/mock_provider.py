"""
[ARCHIVED] Mock Provider - 已归档，不再用于生产环境

归档日期: 2026-04-27
归档原因: 系统从 MOCK Agent 环境迁移到真实 LLM Provider 生产环境
原始路径: backend/app/core/provider/mock_provider.py

此文件包含 MockProvider 类，用于早期开发阶段在没有 LLM API 的情况下
验证 Provider 接口和 Pipeline 链路。迁移后，系统使用 OpenAI 和 Anthropic
真实 Provider，不再需要 Mock Provider。

如需临时回退，可将此文件恢复到原始路径，并在 provider_registry.py 中
重新添加 MockProvider 降级逻辑。但生产环境严禁使用。
"""

from app.shared.logging import get_logger

logger = get_logger(__name__)


class MockProvider:
    def __init__(self):
        self._last_usage: dict | None = None

    async def generate(
        self,
        prompt: str,
        schema: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict | str:
        logger.info("MockProvider.generate called")
        self._last_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        if schema:
            return self._generate_from_schema(schema)
        return "Mock response"

    async def validate(self) -> bool:
        return True

    def _generate_from_schema(self, schema: dict) -> dict:
        result = {}
        if "properties" in schema:
            for key, prop in schema["properties"].items():
                prop_type = prop.get("type", "string")
                if prop_type == "string":
                    result[key] = f"mock_{key}"
                elif prop_type == "integer":
                    result[key] = 0
                elif prop_type == "number":
                    result[key] = 0.0
                elif prop_type == "boolean":
                    result[key] = True
                elif prop_type == "array":
                    result[key] = []
                elif prop_type == "object":
                    result[key] = {}
        return result
