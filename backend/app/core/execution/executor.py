from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from app.models.pipeline import PipelineRun, PipelineRunStatus
from app.models.stage import StageRun, StageRunStatus
from app.core.pipeline.orchestrator import handle_stage_success, handle_stage_failure
from app.core.pipeline.template_loader import get_stage_definitions, DEFAULT_TEMPLATE_ID
from app.core.execution.stage_runner import execute_stage
from app.db.session import get_background_session
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def run_pipeline_stages(
    run_id: str,
    session: AsyncSession | None = None,
) -> PipelineRun:
    own_session = session is None
    if own_session:
        ctx = get_background_session()
        session = await ctx.__aenter__()

    try:
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

        stage_idx = 0
        while stage_idx < len(stage_defs):
            stage_def = stage_defs[stage_idx]

            if stage_def.stage_type == "checkpoint":
                stage_idx += 1
                continue

            run = await session.get(PipelineRun, run_id)
            if run.status == PipelineRunStatus.WAITING_CHECKPOINT:
                logger.info(f"PipelineRun {run_id} waiting at checkpoint, stopping execution")
                await session.commit()
                break
            if run.status in (PipelineRunStatus.FAILED, PipelineRunStatus.TERMINATED):
                logger.info(f"PipelineRun {run_id} is {run.status.value}, stopping execution")
                await session.commit()
                break

            existing = stage_runs.get(stage_def.key)
            if existing and existing.status == StageRunStatus.SUCCEEDED:
                logger.debug(f"Stage {stage_def.key} already succeeded, skipping")
                stage_idx += 1
                continue

            try:
                result = await execute_stage(session, run_id, stage_def.key)
                await handle_stage_success(session, run_id, stage_def.key)
                await session.commit()
                logger.info(f"Stage {stage_def.key} completed successfully for run {run_id}")
                stage_idx += 1
            except Exception as e:
                will_retry = await handle_stage_failure(session, run_id, stage_def.key, str(e))
                await session.commit()
                logger.error(f"Stage {stage_def.key} failed for run {run_id}: {e}")
                if will_retry:
                    existing = stage_runs.get(stage_def.key)
                    delay = 2 ** ((existing.attempt if existing else 1) - 1)
                    logger.info(f"Stage {stage_def.key} will retry after {delay}s delay")
                    await asyncio.sleep(delay)
                else:
                    break

        run = await session.get(PipelineRun, run_id)
        return run
    except Exception:
        if own_session:
            await ctx.__aexit__(type(None), None, None)
        raise
    else:
        if own_session:
            await ctx.__aexit__(None, None, None)
