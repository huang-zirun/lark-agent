from datetime import datetime

from pydantic import BaseModel, Field

from app.models.checkpoint import CheckpointStatus


class CheckpointApproveRequest(BaseModel):
    decision_by: str = Field(default="user", description="Who approved")


class CheckpointRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Rejection reason")
    decision_by: str = Field(default="user", description="Who rejected")
    reject_target: str | None = Field(None, description="Override reject target stage")


class CheckpointResponse(BaseModel):
    id: str
    run_id: str
    stage_key: str
    checkpoint_type: str
    status: CheckpointStatus
    decision_by: str | None
    decision_at: datetime | None
    reason: str | None
    next_stage_key: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
