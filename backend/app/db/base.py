from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

from app.shared.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


async def init_db():
    from app.models.pipeline import PipelineTemplate, PipelineRun
    from app.models.stage import StageDefinition, StageRun
    from app.models.artifact import Artifact
    from app.models.checkpoint import CheckpointRecord
    from app.models.workspace import Workspace
    from app.models.provider import ProviderConfig

    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")

    from app.core.pipeline.template_loader import ensure_default_template
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        await ensure_default_template(session)
        await _ensure_default_providers(session)
        await session.commit()


async def _ensure_default_providers(session):
    from app.models.provider import ProviderConfig, ProviderType
    from app.core.provider.provider_registry import encrypt_api_key
    from app.shared.config import settings
    from app.shared.ids import generate_id

    result = await session.execute(select(ProviderConfig))
    existing = list(result.scalars().all())
    existing_types = {p.provider_type.value for p in existing}

    if settings.OPENAI_API_KEY and "openai" not in existing_types:
        openai_provider = ProviderConfig(
            id=generate_id(),
            name="OpenAI Compatible",
            provider_type=ProviderType.OPENAI,
            api_base=settings.OPENAI_API_BASE,
            api_key_encrypted=encrypt_api_key(settings.OPENAI_API_KEY),
            default_model=settings.OPENAI_DEFAULT_MODEL,
            enabled=True,
            priority=10 if settings.DEFAULT_PROVIDER_TYPE == "openai" else 5,
        )
        session.add(openai_provider)
        logger.info("Created OpenAI Provider from environment config")

    if settings.ANTHROPIC_API_KEY and "anthropic" not in existing_types:
        anthropic_provider = ProviderConfig(
            id=generate_id(),
            name="Anthropic Claude",
            provider_type=ProviderType.ANTHROPIC,
            api_key_encrypted=encrypt_api_key(settings.ANTHROPIC_API_KEY),
            default_model=settings.ANTHROPIC_DEFAULT_MODEL,
            enabled=True,
            priority=10 if settings.DEFAULT_PROVIDER_TYPE == "anthropic" else 5,
        )
        session.add(anthropic_provider)
        logger.info("Created Anthropic Provider from environment config")

    real_providers = [p for p in existing if p.provider_type != ProviderType.MOCK and p.enabled]
    if not real_providers and not settings.OPENAI_API_KEY and not settings.ANTHROPIC_API_KEY:
        logger.warning(
            "No real LLM Provider configured! Please set OPENAI_API_KEY or ANTHROPIC_API_KEY "
            "in environment variables or configure providers via /api/providers endpoint."
        )

    await session.flush()
