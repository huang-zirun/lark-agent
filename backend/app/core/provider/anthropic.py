import json

import httpx

from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model

    async def generate(
        self,
        prompt: str,
        schema: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict | str:
        system_content = system_prompt or ""
        if schema:
            system_content += f"\n\nYou MUST respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_content:
            payload["system"] = system_content

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["content"][0]["text"]

                if schema:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        json_start = content.find("{")
                        json_end = content.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            return json.loads(content[json_start:json_end])
                        raise ExecutionError(f"Failed to parse JSON response: {content[:200]}")
                return content

        except httpx.HTTPStatusError as e:
            raise ExecutionError(f"Anthropic API error: {e.response.status_code} - {e.response.text[:200]}")
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
