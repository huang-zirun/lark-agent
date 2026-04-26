from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.artifact import Artifact
from app.core.artifact.artifact_service import load_artifact, list_artifacts_by_run

router = APIRouter()


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, db: AsyncSession = Depends(get_db)):
    data = await load_artifact(db, artifact_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return data


@router.get("/pipelines/{run_id}/artifacts")
async def list_pipeline_artifacts(run_id: str, db: AsyncSession = Depends(get_db)):
    artifacts = await list_artifacts_by_run(db, run_id)
    result = []
    for a in artifacts:
        data = await load_artifact(db, a.id)
        result.append({
            "id": a.id,
            "run_id": a.run_id,
            "stage_run_id": a.stage_run_id,
            "artifact_type": a.artifact_type,
            "schema_version": a.schema_version,
            "content_summary": a.content_summary,
            "data": data,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return result
