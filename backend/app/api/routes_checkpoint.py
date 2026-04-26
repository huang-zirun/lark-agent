from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from app.db.session import get_db
from app.models.checkpoint import CheckpointRecord, CheckpointStatus
from app.schemas.checkpoint import CheckpointApproveRequest, CheckpointRejectRequest, CheckpointResponse
from app.core.checkpoint.checkpoint_service import approve_checkpoint, reject_checkpoint, get_pending_checkpoint
from app.core.execution.executor import run_pipeline_stages
from app.shared.errors import DevFlowError, ExecutionError

router = APIRouter()


@router.get("/pipelines/{run_id}/checkpoints", response_model=list[CheckpointResponse])
async def list_checkpoints(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CheckpointRecord).where(CheckpointRecord.run_id == run_id).order_by(CheckpointRecord.created_at)
    )
    return list(result.scalars().all())


@router.get("/pipelines/{run_id}/pending-checkpoint", response_model=CheckpointResponse | None)
async def get_pending(run_id: str, db: AsyncSession = Depends(get_db)):
    record = await get_pending_checkpoint(db, run_id)
    return record


@router.post("/checkpoints/{checkpoint_id}/approve", response_model=CheckpointResponse)
async def approve_checkpoint_endpoint(
    checkpoint_id: str,
    body: CheckpointApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        record = await approve_checkpoint(db, checkpoint_id, decision_by=body.decision_by)
        await db.commit()
        asyncio.create_task(run_pipeline_stages(record.run_id))
        await db.refresh(record)
        return record
    except ExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DevFlowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checkpoints/{checkpoint_id}/reject", response_model=CheckpointResponse)
async def reject_checkpoint_endpoint(
    checkpoint_id: str,
    body: CheckpointRejectRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        record = await reject_checkpoint(
            db,
            checkpoint_id,
            reason=body.reason,
            decision_by=body.decision_by,
            reject_target_override=body.reject_target,
        )
        await db.commit()
        asyncio.create_task(run_pipeline_stages(record.run_id))
        await db.refresh(record)
        return record
    except ExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DevFlowError as e:
        raise HTTPException(status_code=500, detail=str(e))
