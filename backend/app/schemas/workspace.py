from datetime import datetime

from pydantic import BaseModel, Field

from app.models.workspace import WorkspaceStatus


class WorkspaceRegister(BaseModel):
    source_repo_path: str = Field(..., min_length=1, description="Local Git repository path")


class WorkspaceResponse(BaseModel):
    id: str
    run_id: str | None
    source_repo_path: str
    workspace_path: str
    git_commit_at_create: str | None
    status: WorkspaceStatus
    created_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class DiffResponse(BaseModel):
    workspace_id: str
    diff: str
    changed_files: list[str]
    stats: dict
