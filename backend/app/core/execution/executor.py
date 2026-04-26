from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pipeline import PipelineRun, PipelineRunStatus
from app.models.stage import StageRun, StageRunStatus
from app.core.pipeline.orchestrator import handle_stage_success, handle_stage_failure
from app.core.pipeline.template_loader import get_stage_definitions, DEFAULT_TEMPLATE_ID
from app.core.execution.stage_runner import execute_stage
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def run_pipeline_stages(
    session: AsyncSession,
    run_id: str,
    use_mock: bool = True,
) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise ExecutionError(f"PipelineRun {run_id} not found")
    if run.status not in (PipelineRunStatus.RUNNING,):
        raise ExecutionError(f"PipelineRun {run_id} is not in running state (status={run.status.value})")

    stage_defs = await get_stage_definitions(session, DEFAULT_TEMPLATE_ID)

    result = await session.execute(
        select(StageRun).where(StageRun.run_id == run_id)
    )
    stage_runs = {sr.stage_key: sr for sr in result.scalars().all()}

    for stage_def in stage_defs:
        if stage_def.stage_type == "checkpoint":
            continue

        run = await session.get(PipelineRun, run_id)
        if run.status == PipelineRunStatus.WAITING_CHECKPOINT:
            logger.info(f"PipelineRun {run_id} waiting at checkpoint, stopping execution")
            return run
        if run.status in (PipelineRunStatus.FAILED, PipelineRunStatus.TERMINATED):
            logger.info(f"PipelineRun {run_id} is {run.status.value}, stopping execution")
            return run

        existing = stage_runs.get(stage_def.key)
        if existing and existing.status == StageRunStatus.SUCCEEDED:
            logger.debug(f"Stage {stage_def.key} already succeeded, skipping")
            continue

        try:
            result = await execute_stage(session, run_id, stage_def.key, use_mock=use_mock)
            await handle_stage_success(session, run_id, stage_def.key)
            logger.info(f"Stage {stage_def.key} completed successfully for run {run_id}")
        except Exception as e:
            await handle_stage_failure(session, run_id, stage_def.key, str(e))
            logger.error(f"Stage {stage_def.key} failed for run {run_id}: {e}")
            break

    run = await session.get(PipelineRun, run_id)
    return run
