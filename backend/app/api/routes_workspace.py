from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceRegister, WorkspaceResponse, DiffResponse
from app.core.workspace.workspace_manager import register_repo, get_workspace, list_workspaces, get_diff
from app.shared.errors import DevFlowError, PrecheckError

router = APIRouter()


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(body: WorkspaceRegister, db: AsyncSession = Depends(get_db)):
    try:
        workspace = await register_repo(db, body.source_repo_path)
        return workspace
    except PrecheckError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DevFlowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_all_workspaces(db: AsyncSession = Depends(get_db)):
    return await list_workspaces(db)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace_detail(workspace_id: str, db: AsyncSession = Depends(get_db)):
    workspace = await get_workspace(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/workspaces/{workspace_id}/diff", response_model=DiffResponse)
async def get_workspace_diff(workspace_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await get_diff(db, workspace_id)
    except DevFlowError as e:
        raise HTTPException(status_code=400, detail=str(e))
