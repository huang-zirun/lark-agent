from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.checkpoint import CheckpointRecord, CheckpointStatus
from app.models.pipeline import PipelineRun, PipelineRunStatus
from app.models.stage import StageRun, StageRunStatus
from app.core.pipeline.state_machine import PipelineRunStateMachine
from app.core.pipeline.template_loader import get_stage_definition_by_key, DEFAULT_TEMPLATE_ID
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def create_checkpoint(
    session: AsyncSession,
    run_id: str,
    stage_key: str,
    checkpoint_type: str,
) -> CheckpointRecord:
    from app.shared.ids import generate_id
    record = CheckpointRecord(
        id=generate_id(),
        run_id=run_id,
        stage_key=stage_key,
        checkpoint_type=checkpoint_type,
        status=CheckpointStatus.PENDING,
    )
    session.add(record)
    await session.flush()
    return record


async def approve_checkpoint(
    session: AsyncSession,
    checkpoint_id: str,
    decision_by: str = "user",
) -> CheckpointRecord:
    record = await session.get(CheckpointRecord, checkpoint_id)
    if not record:
        raise ExecutionError(f"Checkpoint {checkpoint_id} not found")
    if record.status != CheckpointStatus.PENDING:
        raise ExecutionError(f"Checkpoint {checkpoint_id} is not pending (status={record.status.value})")

    stage_def = await get_stage_definition_by_key(session, DEFAULT_TEMPLATE_ID, record.stage_key)
    if not stage_def:
        raise ExecutionError(f"StageDefinition for {record.stage_key} not found")

    approve_target = stage_def.approve_target

    record.status = CheckpointStatus.APPROVED
    record.decision_by = decision_by
    record.decision_at = datetime.now(timezone.utc)
    record.next_stage_key = approve_target

    run = await session.get(PipelineRun, record.run_id)
    if run:
        new_status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.RUNNING)
        run.status = new_status
        run.current_stage_key = approve_target

    await session.flush()
    logger.info(f"Checkpoint {checkpoint_id} approved, next stage: {approve_target}")
    return record


async def reject_checkpoint(
    session: AsyncSession,
    checkpoint_id: str,
    reason: str,
    decision_by: str = "user",
    reject_target_override: str | None = None,
) -> CheckpointRecord:
    record = await session.get(CheckpointRecord, checkpoint_id)
    if not record:
        raise ExecutionError(f"Checkpoint {checkpoint_id} not found")
    if record.status != CheckpointStatus.PENDING:
        raise ExecutionError(f"Checkpoint {checkpoint_id} is not pending (status={record.status.value})")

    stage_def = await get_stage_definition_by_key(session, DEFAULT_TEMPLATE_ID, record.stage_key)
    if not stage_def:
        raise ExecutionError(f"StageDefinition for {record.stage_key} not found")

    reject_target = reject_target_override or stage_def.reject_target

    record.status = CheckpointStatus.REJECTED
    record.decision_by = decision_by
    record.decision_at = datetime.now(timezone.utc)
    record.reason = reason
    record.next_stage_key = reject_target

    run = await session.get(PipelineRun, record.run_id)
    if run:
        new_status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.RUNNING)
        run.status = new_status
        run.current_stage_key = reject_target

        result = await session.execute(
            select(StageRun).where(
                StageRun.run_id == run.id,
                StageRun.stage_key == reject_target,
            )
        )
        target_stage_run = result.scalars().first()
        if target_stage_run:
            target_stage_run.status = StageRunStatus.PENDING
            target_stage_run.attempt += 1

    await session.flush()
    logger.info(f"Checkpoint {checkpoint_id} rejected, rollback to: {reject_target}")
    return record


async def get_pending_checkpoint(session: AsyncSession, run_id: str) -> CheckpointRecord | None:
    result = await session.execute(
        select(CheckpointRecord).where(
            CheckpointRecord.run_id == run_id,
            CheckpointRecord.status == CheckpointStatus.PENDING,
        )
    )
    return result.scalar_one_or_none()
