import json

import httpx

from app.shared.config import settings
from app.shared.errors import ExecutionError, AuthenticationError, RateLimitError
from app.shared.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self._last_usage: dict | None = None

    async def generate(
        self,
        prompt: str,
        schema: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict | str:
        system_content = system_prompt or ""
        if schema:
            system_content += f"\n\nYou MUST respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
            system_content += "\nDo NOT wrap the JSON in markdown code blocks. Respond with raw JSON only."

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_content:
            payload["system"] = system_content

        timeout_seconds = settings.LLM_TIMEOUT_SECONDS

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code == 401 or response.status_code == 403:
                    raise AuthenticationError(f"Anthropic API authentication failed: {response.status_code}")
                if response.status_code == 429:
                    retry_after = None
                    try:
                        retry_after = float(response.headers.get("retry-after", 5))
                    except (ValueError, TypeError):
                        retry_after = 5.0
                    raise RateLimitError(f"Anthropic API rate limited: {response.text[:500]}", retry_after=retry_after)
                if response.status_code >= 500:
                    raise ExecutionError(f"Anthropic API server error: {response.status_code} - {response.text[:500]}")

                response.raise_for_status()
                data = response.json()
                content = data["content"][0]["text"]

                self._last_usage = {}
                if "usage" in data:
                    self._last_usage = {
                        "prompt_tokens": data["usage"].get("input_tokens", 0),
                        "completion_tokens": data["usage"].get("output_tokens", 0),
                        "total_tokens": data["usage"].get("input_tokens", 0) + data["usage"].get("output_tokens", 0),
                    }

                if schema:
                    return _parse_anthropic_json(content)

                return content

        except (AuthenticationError, RateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise ExecutionError(f"Anthropic API error: {e.response.status_code} - {e.response.text[:500]}")
        except httpx.RequestError as e:
            raise ExecutionError(f"Anthropic API request failed: {str(e)}")

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "Hi"}],
                    },
                )
                return response.status_code == 200
        except Exception:
            return False


def _parse_anthropic_json(content: str) -> dict:
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

    raise ExecutionError(f"Anthropic: Failed to parse JSON response: {content[:500]}")
