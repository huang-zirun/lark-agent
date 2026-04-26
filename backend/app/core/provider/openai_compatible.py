import json

import httpx

from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatibleProvider:
    def __init__(self, api_base: str, api_key: str, model: str = "gpt-4o"):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

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

        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": schema,
                },
            }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                if schema:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        raise ExecutionError(f"Failed to parse JSON response: {content[:200]}")
                return content

        except httpx.HTTPStatusError as e:
            raise ExecutionError(f"OpenAI API error: {e.response.status_code} - {e.response.text[:200]}")
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
