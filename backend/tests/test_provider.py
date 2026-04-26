import pytest

from app.core.provider.mock_provider import MockProvider
from app.shared.errors import ExecutionError, AuthenticationError, RateLimitError


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_generate_without_schema(self):
        provider = MockProvider()
        result = await provider.generate(prompt="test prompt")
        assert result == "Mock response"

    @pytest.mark.asyncio
    async def test_generate_with_schema(self):
        provider = MockProvider()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "active": {"type": "boolean"},
            },
        }
        result = await provider.generate(prompt="test", schema=schema)
        assert isinstance(result, dict)
        assert result["name"] == "mock_name"
        assert result["count"] == 0
        assert result["active"] is True

    @pytest.mark.asyncio
    async def test_validate(self):
        provider = MockProvider()
        assert await provider.validate() is True

    @pytest.mark.asyncio
    async def test_last_usage(self):
        provider = MockProvider()
        await provider.generate(prompt="test")
        assert provider._last_usage is not None
        assert provider._last_usage["total_tokens"] == 0


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
