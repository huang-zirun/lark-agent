from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.shared.config import ensure_directories, settings
from app.shared.logging import setup_logging
from app.db.base import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(debug=settings.DEBUG)
    ensure_directories()
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "service": settings.APP_NAME,
        "status": "ok",
        "version": settings.APP_VERSION,
        "time": datetime.now(timezone.utc).isoformat(),
    }


from app.api.routes_pipeline import router as pipeline_router
from app.api.routes_checkpoint import router as checkpoint_router
from app.api.routes_artifact import router as artifact_router
from app.api.routes_workspace import router as workspace_router
from app.api.routes_provider import router as provider_router

app.include_router(pipeline_router, prefix="/api", tags=["Pipeline"])
app.include_router(checkpoint_router, prefix="/api", tags=["Checkpoint"])
app.include_router(artifact_router, prefix="/api", tags=["Artifact"])
app.include_router(workspace_router, prefix="/api", tags=["Workspace"])
app.include_router(provider_router, prefix="/api", tags=["Provider"])
