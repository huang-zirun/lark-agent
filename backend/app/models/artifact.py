from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Artifact(Base):
    __tablename__ = "artifact"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_run.id"), nullable=False)
    stage_run_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("stage_run.id"), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    content_summary: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    storage_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="artifacts")
