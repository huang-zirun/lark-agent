from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.provider import ProviderConfig, ProviderType
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)

_providers: dict[str, Any] = {}


def register_provider_instance(provider_id: str, provider: Any):
    _providers[provider_id] = provider


def get_provider_instance(provider_id: str) -> Any | None:
    return _providers.get(provider_id)


def clear_provider_instances():
    _providers.clear()


async def resolve_provider(
    session: AsyncSession,
    provider_id: str | None = None,
    provider_type: ProviderType | None = None,
) -> Any:
    if provider_id:
        instance = get_provider_instance(provider_id)
        if instance:
            return instance

        config = await session.get(ProviderConfig, provider_id)
        if config:
            instance = await _create_provider_from_config(config)
            register_provider_instance(provider_id, instance)
            return instance

    if provider_type:
        result = await session.execute(
            select(ProviderConfig)
            .where(ProviderConfig.provider_type == provider_type, ProviderConfig.enabled == True)
            .order_by(ProviderConfig.priority.desc())
            .limit(1)
        )
        config = result.scalar_one_or_none()
        if config:
            instance = get_provider_instance(config.id)
            if instance:
                return instance
            instance = await _create_provider_from_config(config)
            register_provider_instance(config.id, instance)
            return instance

    result = await session.execute(
        select(ProviderConfig)
        .where(ProviderConfig.enabled == True)
        .order_by(ProviderConfig.priority.desc())
        .limit(1)
    )
    config = result.scalar_one_or_none()
    if config:
        instance = get_provider_instance(config.id)
        if instance:
            return instance
        instance = await _create_provider_from_config(config)
        register_provider_instance(config.id, instance)
        return instance

    raise ExecutionError(
        "No LLM Provider configured. Please configure at least one provider "
        "(OpenAI or Anthropic) via the /api/providers endpoint or environment variables "
        "(OPENAI_API_KEY or ANTHROPIC_API_KEY)."
    )


async def _create_provider_from_config(config: ProviderConfig) -> Any:
    if config.provider_type == ProviderType.MOCK:
        raise ExecutionError(
            "Mock Provider is no longer supported in production. "
            "Please configure a real LLM Provider (OpenAI or Anthropic) instead."
        )
    elif config.provider_type == ProviderType.OPENAI:
        from app.core.provider.openai_compatible import OpenAICompatibleProvider
        api_key = _decrypt_api_key(config.api_key_encrypted) if config.api_key_encrypted else ""
        return OpenAICompatibleProvider(
            api_base=config.api_base or "https://api.openai.com/v1",
            api_key=api_key,
            model=config.default_model or "gpt-4o",
        )
    elif config.provider_type == ProviderType.ANTHROPIC:
        from app.core.provider.anthropic import AnthropicProvider
        api_key = _decrypt_api_key(config.api_key_encrypted) if config.api_key_encrypted else ""
        return AnthropicProvider(
            api_key=api_key,
            model=config.default_model or "claude-sonnet-4-20250514",
        )
    else:
        raise ExecutionError(f"Unknown provider type: {config.provider_type}")


def _decrypt_api_key(encrypted: str | None) -> str:
    if not encrypted:
        return ""
    try:
        from cryptography.fernet import Fernet
        from app.shared.config import settings
        key = settings.ENCRYPTION_KEY.encode()[:32]
        import base64
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


def encrypt_api_key(api_key: str) -> str:
    try:
        from cryptography.fernet import Fernet
        from app.shared.config import settings
        import base64
        key = settings.ENCRYPTION_KEY.encode()[:32]
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.encrypt(api_key.encode()).decode()
    except Exception:
        return api_key
