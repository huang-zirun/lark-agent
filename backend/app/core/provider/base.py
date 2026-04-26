from typing import Protocol, Any


class LLMProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        schema: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict | str: ...

    async def validate(self) -> bool: ...
