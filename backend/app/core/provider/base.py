import asyncio
from typing import Protocol, Any

from pydantic import BaseModel

from app.shared.config import settings
from app.shared.errors import ExecutionError, AuthenticationError, RateLimitError
from app.shared.logging import get_logger

logger = get_logger(__name__)


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMCallResult(BaseModel):
    content: dict | str
    usage: TokenUsage = TokenUsage()
    latency_ms: int = 0
    model: str = ""


class LLMProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        schema: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict | str: ...

    async def validate(self) -> bool: ...


async def generate_with_retry(
    provider: Any,
    prompt: str,
    schema: dict | None = None,
    system_prompt: str | None = None,
    max_retries: int | None = None,
    base_delay: float | None = None,
) -> LLMCallResult:
    import time

    max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
    base_delay = base_delay if base_delay is not None else settings.LLM_RETRY_BASE_DELAY

    last_error = None
    for attempt in range(max_retries + 1):
        start_time = time.time()
        try:
            result = await provider.generate(
                prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            usage = TokenUsage()
            model = ""
            if hasattr(provider, "model"):
                model = provider.model or ""
            if hasattr(provider, "_last_usage") and provider._last_usage:
                usage = TokenUsage(**provider._last_usage)

            return LLMCallResult(
                content=result,
                usage=usage,
                latency_ms=latency_ms,
                model=model,
            )

        except AuthenticationError:
            raise
        except RateLimitError as e:
            last_error = e
            if attempt < max_retries:
                retry_after = getattr(e, "retry_after", None) or (base_delay * (2 ** attempt))
                logger.warning(f"Rate limited, retrying after {retry_after}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_after)
            else:
                raise
        except ExecutionError as e:
            last_error = e
            error_str = str(e)
            is_retryable = any(code in error_str for code in ["429", "500", "502", "503", "504"])
            if is_retryable and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Retryable error, retrying after {delay}s (attempt {attempt + 1}/{max_retries}): {error_str[:200]}")
                await asyncio.sleep(delay)
            elif not is_retryable:
                raise
            else:
                raise
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Unexpected error, retrying after {delay}s (attempt {attempt + 1}/{max_retries}): {str(e)[:200]}")
                await asyncio.sleep(delay)
            else:
                raise ExecutionError(f"All {max_retries + 1} attempts failed. Last error: {str(last_error)[:500]}")

    raise ExecutionError(f"All {max_retries + 1} attempts failed. Last error: {str(last_error)[:500]}")
