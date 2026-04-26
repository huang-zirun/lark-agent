import json
import time

import httpx

from app.shared.config import settings
from app.shared.errors import ExecutionError, AuthenticationError, RateLimitError
from app.shared.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatibleProvider:
    def __init__(self, api_base: str, api_key: str, model: str = "gpt-4o"):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._last_usage: dict | None = None

    async def generate(
        self,
        prompt: str,
        schema: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict | str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }

        use_structured_output = schema is not None
        if use_structured_output:
            schema_prompt = f"\n\n请严格按照以下 JSON Schema 格式返回结果：\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n只返回 JSON，不要包含其他内容。"
            messages[-1]["content"] = messages[-1]["content"] + schema_prompt

        timeout_seconds = settings.LLM_TIMEOUT_SECONDS

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code == 401 or response.status_code == 403:
                    raise AuthenticationError(f"OpenAI API authentication failed: {response.status_code}")
                if response.status_code == 429:
                    retry_after = None
                    try:
                        retry_after = float(response.headers.get("retry-after", 5))
                    except (ValueError, TypeError):
                        retry_after = 5.0
                    raise RateLimitError(f"OpenAI API rate limited: {response.text[:500]}", retry_after=retry_after)
                if response.status_code >= 500:
                    raise ExecutionError(f"OpenAI API server error: {response.status_code} - {response.text[:500]}")

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                self._last_usage = {}
                if "usage" in data:
                    self._last_usage = {
                        "prompt_tokens": data["usage"].get("prompt_tokens", 0),
                        "completion_tokens": data["usage"].get("completion_tokens", 0),
                        "total_tokens": data["usage"].get("total_tokens", 0),
                    }

                if schema:
                    return _parse_json_response(content, "OpenAI")

                return content

        except (AuthenticationError, RateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise ExecutionError(f"OpenAI API error: {e.response.status_code} - {e.response.text[:500]}")
        except httpx.RequestError as e:
            raise ExecutionError(f"OpenAI API request failed: {str(e)}")

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception:
            return False


def _parse_json_response(content: str, provider_name: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    json_start = content.find("{")
    json_end = content.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        try:
            return json.loads(content[json_start:json_end])
        except json.JSONDecodeError:
            pass

    code_block_start = content.find("```json")
    if code_block_start >= 0:
        code_start = content.find("\n", code_block_start) + 1
        code_end = content.find("```", code_start)
        if code_start > 0 and code_end > code_start:
            try:
                return json.loads(content[code_start:code_end])
            except json.JSONDecodeError:
                pass

    code_block_start = content.find("```")
    if code_block_start >= 0:
        code_start = content.find("\n", code_block_start) + 1
        code_end = content.find("```", code_start)
        if code_start > 0 and code_end > code_start:
            try:
                return json.loads(content[code_start:code_end])
            except json.JSONDecodeError:
                pass

    raise ExecutionError(f"{provider_name}: Failed to parse JSON response: {content[:500]}")
