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
        await session.commit()
