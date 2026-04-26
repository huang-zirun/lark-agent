import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CheckpointStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CheckpointRecord(Base):
    __tablename__ = "checkpoint_record"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("pipeline_run.id"), nullable=False)
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[CheckpointStatus] = mapped_column(
        Enum(CheckpointStatus), nullable=False, default=CheckpointStatus.PENDING
    )
    decision_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_stage_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="checkpoints")
