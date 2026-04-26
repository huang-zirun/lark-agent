from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pipeline import PipelineRun, PipelineRunStatus, PipelineTemplate
from app.models.stage import StageRun, StageRunStatus, StageDefinition
from app.models.checkpoint import CheckpointRecord, CheckpointStatus
from app.core.pipeline.state_machine import PipelineRunStateMachine, StageRunStateMachine
from app.core.pipeline.template_loader import (
    DEFAULT_TEMPLATE_ID,
    get_stage_definitions,
    get_stage_definition_by_key,
)
from app.shared.ids import generate_id
from app.shared.errors import PrecheckError, ExecutionError, StateTransitionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def create_pipeline_run(
    session: AsyncSession,
    requirement_text: str,
    workspace_id: str | None = None,
    provider_selection_override: dict | None = None,
) -> PipelineRun:
    result = await session.execute(
        select(PipelineTemplate).where(PipelineTemplate.id == DEFAULT_TEMPLATE_ID)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise ExecutionError("Default template not found")

    run = PipelineRun(
        id=generate_id(),
        template_id=DEFAULT_TEMPLATE_ID,
        workspace_ref_id=workspace_id,
        requirement_text=requirement_text,
        status=PipelineRunStatus.DRAFT,
        current_stage_key=None,
        provider_selection_override=provider_selection_override,
    )
    session.add(run)

    stage_defs = await get_stage_definitions(session, DEFAULT_TEMPLATE_ID)
    for sd in stage_defs:
        stage_run = StageRun(
            id=generate_id(),
            run_id=run.id,
            stage_key=sd.key,
            agent_profile_id=sd.agent_profile_id,
            status=StageRunStatus.PENDING,
            attempt=1,
        )
        session.add(stage_run)

    await session.flush()
    logger.info(f"Created pipeline run {run.id} with status draft")
    return run


async def precheck_pipeline_run(session: AsyncSession, run_id: str) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise PrecheckError(f"PipelineRun {run_id} not found")

    if run.workspace_ref_id:
        from app.models.workspace import Workspace
        workspace = await session.get(Workspace, run.workspace_ref_id)
        if not workspace:
            raise PrecheckError(f"Workspace {run.workspace_ref_id} not found")

    new_status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.READY)
    run.status = new_status
    await session.flush()
    logger.info(f"PipelineRun {run_id} precheck passed, status -> ready")
    return run


async def start_pipeline_run(session: AsyncSession, run_id: str) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise ExecutionError(f"PipelineRun {run_id} not found")

    new_status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.RUNNING)
    run.status = new_status
    run.started_at = datetime.now(timezone.utc)
    run.current_stage_key = "requirement_analysis"

    if run.workspace_ref_id:
        from app.core.workspace.workspace_manager import create_workspace_for_run
        await create_workspace_for_run(session, run_id, run.workspace_ref_id)

    await session.flush()
    logger.info(f"PipelineRun {run_id} started")
    return run


async def advance_to_next_stage(session: AsyncSession, run_id: str, current_stage_key: str) -> str | None:
    stage_defs = await get_stage_definitions(session, DEFAULT_TEMPLATE_ID)
    current_idx = None
    for i, sd in enumerate(stage_defs):
        if sd.key == current_stage_key:
            current_idx = i
            break

    if current_idx is None:
        return None

    if current_idx + 1 < len(stage_defs):
        next_stage = stage_defs[current_idx + 1]
        return next_stage.key
    return None


async def handle_stage_success(session: AsyncSession, run_id: str, stage_key: str):
    run = await session.get(PipelineRun, run_id)
    if not run:
        return

    next_stage_key = await advance_to_next_stage(session, run_id, stage_key)

    if next_stage_key is None:
        run.status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.SUCCEEDED)
        run.ended_at = datetime.now(timezone.utc)
        run.current_stage_key = stage_key
        logger.info(f"PipelineRun {run_id} completed successfully")
    else:
        next_stage_def = await get_stage_definition_by_key(session, DEFAULT_TEMPLATE_ID, next_stage_key)
        if next_stage_def and next_stage_def.stage_type == "checkpoint":
            run.status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.WAITING_CHECKPOINT)
            run.current_stage_key = next_stage_key
            await _create_checkpoint_record(session, run_id, next_stage_def)
            logger.info(f"PipelineRun {run_id} waiting for checkpoint: {next_stage_key}")
        else:
            run.current_stage_key = next_stage_key
            logger.info(f"PipelineRun {run_id} advancing to stage: {next_stage_key}")

    await session.flush()


async def handle_stage_failure(session: AsyncSession, run_id: str, stage_key: str, error_message: str):
    run = await session.get(PipelineRun, run_id)
    if not run:
        return

    result = await session.execute(
        select(StageRun).where(
            StageRun.run_id == run_id,
            StageRun.stage_key == stage_key,
        ).order_by(StageRun.attempt.desc())
    )
    stage_run = result.scalars().first()

    if stage_run and stage_run.attempt < 3:
        new_status = StageRunStateMachine.transition(stage_run.status, StageRunStatus.RETRYING)
        stage_run.status = new_status
        new_status = StageRunStateMachine.transition(stage_run.status, StageRunStatus.RUNNING)
        stage_run.status = new_status
        stage_run.attempt += 1
        stage_run.error_message = error_message
        logger.info(f"StageRun {stage_key} retrying (attempt {stage_run.attempt})")
    else:
        run.status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.FAILED)
        run.ended_at = datetime.now(timezone.utc)
        run.failure_reason = f"Stage {stage_key} failed: {error_message}"
        if stage_run:
            stage_run.status = StageRunStatus.FAILED
            stage_run.error_message = error_message
        logger.error(f"PipelineRun {run_id} failed at stage {stage_key}: {error_message}")

    await session.flush()


async def _create_checkpoint_record(session: AsyncSession, run_id: str, stage_def: StageDefinition):
    checkpoint_type = "design_approval" if "design" in stage_def.key else "final_approval"
    record = CheckpointRecord(
        id=generate_id(),
        run_id=run_id,
        stage_key=stage_def.key,
        checkpoint_type=checkpoint_type,
        status=CheckpointStatus.PENDING,
    )
    session.add(record)
    await session.flush()


async def pause_pipeline_run(session: AsyncSession, run_id: str) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise ExecutionError(f"PipelineRun {run_id} not found")
    new_status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.PAUSED)
    run.status = new_status
    await session.flush()
    return run


async def resume_pipeline_run(session: AsyncSession, run_id: str) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise ExecutionError(f"PipelineRun {run_id} not found")
    new_status = PipelineRunStateMachine.transition(run.status, PipelineRunStatus.RUNNING)
    run.status = new_status
    await session.flush()
    return run


async def terminate_pipeline_run(session: AsyncSession, run_id: str) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise ExecutionError(f"PipelineRun {run_id} not found")
    run.status = PipelineRunStatus.TERMINATED
    run.ended_at = datetime.now(timezone.utc)
    await session.flush()
    return run
