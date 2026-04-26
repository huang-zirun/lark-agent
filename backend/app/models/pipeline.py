import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PipelineRunStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_CHECKPOINT = "waiting_checkpoint"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TERMINATED = "terminated"


class PipelineTemplate(Base):
    __tablename__ = "pipeline_template"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    template_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="feature_delivery")
    stages: Mapped[dict] = mapped_column(JSON, nullable=False)
    entry_stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    default_provider_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_run"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_template.id"), nullable=False)
    workspace_ref_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PipelineRunStatus] = mapped_column(
        Enum(PipelineRunStatus), nullable=False, default=PipelineRunStatus.DRAFT
    )
    current_stage_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_selection_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved_provider_map: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    stage_runs: Mapped[list["StageRun"]] = relationship(back_populates="pipeline_run", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="pipeline_run", cascade="all, delete-orphan")
    checkpoints: Mapped[list["CheckpointRecord"]] = relationship(back_populates="pipeline_run", cascade="all, delete-orphan")
