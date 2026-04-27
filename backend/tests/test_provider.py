import pytest

from app.shared.errors import ExecutionError, AuthenticationError, RateLimitError


class TestErrorClasses:
    def test_authentication_error(self):
        err = AuthenticationError("bad key")
        assert isinstance(err, Exception)
        assert str(err) == "bad key"

    def test_rate_limit_error(self):
        err = RateLimitError("too many requests", retry_after=5.0)
        assert isinstance(err, Exception)
        assert err.retry_after == 5.0

    def test_rate_limit_error_no_retry_after(self):
        err = RateLimitError("too many requests")
        assert err.retry_after is None


class TestProviderRegistryNoFallback:
    @pytest.mark.asyncio
    async def test_no_provider_raises_error(self):
        from app.core.provider.provider_registry import resolve_provider
        from app.shared.errors import ExecutionError
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session.get.return_value = None

        with pytest.raises(ExecutionError, match="No LLM Provider configured"):
            await resolve_provider(mock_session)


class TestOpenAICompatibleProvider:
    @pytest.mark.asyncio
    async def test_validate_with_invalid_key(self):
        from app.core.provider.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            api_base="https://api.openai.com/v1",
            api_key="invalid-key-for-testing",
            model="gpt-4o",
        )
        result = await provider.validate()
        assert result is False
