import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CORRUPTED = "corrupted"


class Workspace(Base):
    __tablename__ = "workspace"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("pipeline_run.id"), nullable=True)
    source_repo_path: Mapped[str] = mapped_column(Text, nullable=False)
    workspace_path: Mapped[str] = mapped_column(Text, nullable=False)
    git_commit_at_create: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus), nullable=False, default=WorkspaceStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
