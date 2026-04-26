from datetime import datetime

from pydantic import BaseModel, Field

from app.models.pipeline import PipelineRunStatus
from app.models.stage import StageRunStatus


class PipelineRunCreate(BaseModel):
    requirement_text: str = Field(..., min_length=1, description="Natural language requirement")
    workspace_id: str | None = Field(None, description="Registered workspace ID")
    provider_selection_override: dict | None = Field(None, description="Override provider selection per stage")


class PipelineRunResponse(BaseModel):
    id: str
    template_id: str
    workspace_ref_id: str | None
    requirement_text: str
    status: PipelineRunStatus
    current_stage_key: str | None
    provider_selection_override: dict | None
    resolved_provider_map: dict | None
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class PipelineRunListResponse(BaseModel):
    items: list[PipelineRunResponse]
    total: int


class StageRunResponse(BaseModel):
    id: str
    run_id: str
    stage_key: str
    agent_profile_id: str | None
    resolved_provider_id: str | None
    status: StageRunStatus
    attempt: int
    input_artifact_refs: dict | None
    output_artifact_refs: dict | None
    error_message: str | None
    started_at: datetime | None
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class TimelineResponse(BaseModel):
    run_id: str
    run_status: PipelineRunStatus
    stages: list[StageRunResponse]
