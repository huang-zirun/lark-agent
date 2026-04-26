from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from app.db.session import get_db
from app.models.pipeline import PipelineRun
from app.schemas.pipeline import (
    PipelineRunCreate,
    PipelineRunResponse,
    PipelineRunListResponse,
    StageRunResponse,
    TimelineResponse,
)
from app.core.pipeline.orchestrator import (
    create_pipeline_run,
    precheck_pipeline_run,
    start_pipeline_run,
    pause_pipeline_run,
    resume_pipeline_run,
    terminate_pipeline_run,
)
from app.core.execution.executor import run_pipeline_stages
from app.shared.errors import DevFlowError, PrecheckError, ExecutionError

router = APIRouter()


@router.post("/pipelines", response_model=PipelineRunResponse, status_code=201)
async def create_pipeline(body: PipelineRunCreate, db: AsyncSession = Depends(get_db)):
    try:
        run = await create_pipeline_run(
            session=db,
            requirement_text=body.requirement_text,
            workspace_id=body.workspace_id,
            provider_selection_override=body.provider_selection_override,
        )
        await precheck_pipeline_run(db, run.id)
        return run
    except PrecheckError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DevFlowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines", response_model=PipelineRunListResponse)
async def list_pipelines(status: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(PipelineRun).order_by(PipelineRun.created_at.desc())
    if status:
        from app.models.pipeline import PipelineRunStatus
        try:
            status_enum = PipelineRunStatus(status)
            query = query.where(PipelineRun.status == status_enum)
        except ValueError:
            pass

    result = await db.execute(query)
    runs = list(result.scalars().all())
    return PipelineRunListResponse(items=runs, total=len(runs))


@router.get("/pipelines/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PipelineRun not found")
    return run


@router.post("/pipelines/{run_id}/start", response_model=PipelineRunResponse)
async def start_pipeline(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        run = await start_pipeline_run(db, run_id)
        asyncio.create_task(run_pipeline_stages(run_id))
        return run
    except ExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DevFlowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines/{run_id}/pause", response_model=PipelineRunResponse)
async def pause_pipeline(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await pause_pipeline_run(db, run_id)
    except DevFlowError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pipelines/{run_id}/resume", response_model=PipelineRunResponse)
async def resume_pipeline(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        run = await resume_pipeline_run(db, run_id)
        asyncio.create_task(run_pipeline_stages(run_id))
        return run
    except DevFlowError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pipelines/{run_id}/terminate", response_model=PipelineRunResponse)
async def terminate_pipeline(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await terminate_pipeline_run(db, run_id)
    except DevFlowError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pipelines/{run_id}/timeline", response_model=TimelineResponse)
async def get_timeline(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PipelineRun not found")

    from app.models.stage import StageRun
    result = await db.execute(
        select(StageRun).where(StageRun.run_id == run_id).order_by(StageRun.id)
    )
    stages = list(result.scalars().all())

    return TimelineResponse(
        run_id=run_id,
        run_status=run.status,
        stages=stages,
    )
