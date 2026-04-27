import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.pipeline import PipelineRun
from app.models.workspace import Workspace
from app.models.artifact import Artifact
from app.core.artifact.artifact_service import load_artifact
from app.shared.subprocess_utils import run_git
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class PushRequest(BaseModel):
    remote_url: str
    remote_branch: str | None = None


class PRRequest(BaseModel):
    repo_owner: str
    repo_name: str
    base_branch: str = "main"
    github_token: str | None = None


@router.get("/pipelines/{run_id}/delivery")
async def get_delivery(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PipelineRun not found")

    manifest_result = await db.execute(
        select(Artifact).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == "delivery_manifest",
        )
    )
    manifest_artifact = manifest_result.scalar_one_or_none()

    summary_result = await db.execute(
        select(Artifact).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == "delivery_summary",
        )
    )
    summary_artifact = summary_result.scalar_one_or_none()

    manifest_data = await load_artifact(db, manifest_artifact.id) if manifest_artifact else None
    summary_data = await load_artifact(db, summary_artifact.id) if summary_artifact else None

    return {
        "run_id": run_id,
        "delivery_manifest": manifest_data,
        "delivery_summary": summary_data,
    }


@router.get("/pipelines/{run_id}/delivery/patch")
async def get_delivery_patch(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PipelineRun not found")

    workspace = await db.get(Workspace, run.workspace_ref_id) if run.workspace_ref_id else None
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    proc = run_git(["diff", "HEAD"], cwd=workspace.workspace_path)
    return Response(content=proc.stdout, media_type="text/x-diff")


@router.post("/pipelines/{run_id}/delivery/push")
async def push_delivery(run_id: str, body: PushRequest, db: AsyncSession = Depends(get_db)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PipelineRun not found")

    workspace = await db.get(Workspace, run.workspace_ref_id) if run.workspace_ref_id else None
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    manifest_result = await db.execute(
        select(Artifact).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == "delivery_manifest",
        )
    )
    manifest_artifact = manifest_result.scalar_one_or_none()

    manifest_data = await load_artifact(db, manifest_artifact.id) if manifest_artifact else None
    branch_name = manifest_data.get("branch_name") if manifest_data else None

    if not branch_name:
        raise HTTPException(status_code=400, detail="No delivery branch found")

    try:
        # Remove existing delivery remote if it exists
        run_git(["remote", "remove", "delivery"], cwd=workspace.workspace_path)
    except Exception:
        # Ignore error if remote doesn't exist
        pass

    try:
        run_git(["remote", "add", "delivery", body.remote_url], cwd=workspace.workspace_path)
        if body.remote_branch:
            run_git(["push", "delivery", f"{branch_name}:{body.remote_branch}"], cwd=workspace.workspace_path)
        else:
            run_git(["push", "delivery", branch_name], cwd=workspace.workspace_path)
        return {"success": True, "remote_url": body.remote_url, "branch": branch_name}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/pipelines/{run_id}/delivery/pr")
async def create_pull_request(run_id: str, body: PRRequest, db: AsyncSession = Depends(get_db)):
    run = await db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="PipelineRun not found")

    manifest_result = await db.execute(
        select(Artifact).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == "delivery_manifest",
        )
    )
    manifest_artifact = manifest_result.scalar_one_or_none()

    summary_result = await db.execute(
        select(Artifact).where(
            Artifact.run_id == run_id,
            Artifact.artifact_type == "delivery_summary",
        )
    )
    summary_artifact = summary_result.scalar_one_or_none()

    manifest_data = await load_artifact(db, manifest_artifact.id) if manifest_artifact else None
    summary_data = await load_artifact(db, summary_artifact.id) if summary_artifact else None

    branch_name = manifest_data.get("branch_name") if manifest_data else None
    if not branch_name:
        raise HTTPException(status_code=400, detail="No delivery branch found")

    pr_title = run.requirement_text[:80]
    pr_body = str(summary_data) if summary_data else ""

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Accept": "application/vnd.github.v3+json",
            }
            if body.github_token:
                headers["Authorization"] = f"Bearer {body.github_token}"

            response = await client.post(
                f"https://api.github.com/repos/{body.repo_owner}/{body.repo_name}/pulls",
                headers=headers,
                json={
                    "title": pr_title,
                    "body": pr_body,
                    "head": branch_name,
                    "base": body.base_branch,
                },
            )
            response.raise_for_status()
            response_data = response.json()
            return {"success": True, "pr_url": response_data.get("html_url")}
    except Exception as e:
        return {"success": False, "error": str(e)}
