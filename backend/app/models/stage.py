import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StageRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class StageDefinition(Base):
    __tablename__ = "stage_definition"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_template.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    stage_type: Mapped[str] = mapped_column(String(32), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depends_on: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_artifact_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_artifact_types: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider_policy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approve_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reject_target: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allowed_reject_targets: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class StageRun(Base):
    __tablename__ = "stage_run"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_run.id"), nullable=False)
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_provider_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[StageRunStatus] = mapped_column(
        Enum(StageRunStatus), nullable=False, default=StageRunStatus.PENDING
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_artifact_refs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_artifact_refs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="stage_runs")
