import json
import sys

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.artifact import Artifact
from app.core.artifact.artifact_store import save_artifact_file, load_artifact_file
from app.shared.ids import generate_id
from app.shared.logging import get_logger

logger = get_logger(__name__)

INLINE_THRESHOLD = 10 * 1024


async def save_artifact(
    session: AsyncSession,
    run_id: str,
    stage_run_id: str,
    artifact_type: str,
    data: dict,
    stage_key: str = "",
) -> Artifact:
    artifact_id = generate_id()
    content_json = json.dumps(data, ensure_ascii=False)
    content_bytes = content_json.encode("utf-8")
    content_size = len(content_bytes)

    summary = _generate_summary(data, artifact_type)

    if content_size < INLINE_THRESHOLD:
        artifact = Artifact(
            id=artifact_id,
            run_id=run_id,
            stage_run_id=stage_run_id,
            artifact_type=artifact_type,
            schema_version=data.get("schema_version", "1.0"),
            content_summary=summary,
            content=data,
            storage_uri=None,
        )
    else:
        file_path = await save_artifact_file(run_id, stage_key, artifact_id, artifact_type, data)
        artifact = Artifact(
            id=artifact_id,
            run_id=run_id,
            stage_run_id=stage_run_id,
            artifact_type=artifact_type,
            schema_version=data.get("schema_version", "1.0"),
            content_summary=summary,
            content=None,
            storage_uri=file_path,
        )

    session.add(artifact)
    await session.flush()
    logger.info(f"Saved artifact {artifact_id} (type={artifact_type}, size={content_size})")
    return artifact


async def load_artifact(session: AsyncSession, artifact_id: str) -> dict | None:
    artifact = await session.get(Artifact, artifact_id)
    if not artifact:
        return None

    if artifact.content is not None:
        return artifact.content

    if artifact.storage_uri:
        return await load_artifact_file(artifact.storage_uri)

    return None


async def list_artifacts_by_run(session: AsyncSession, run_id: str) -> list[Artifact]:
    result = await session.execute(
        select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)
    )
    return list(result.scalars().all())


def _generate_summary(data: dict, artifact_type: str) -> str:
    if artifact_type == "requirement_brief":
        return data.get("goal", "")[:128]
    elif artifact_type == "design_spec":
        return data.get("summary", "")[:128]
    elif artifact_type == "change_set":
        files = data.get("files", [])
        return f"{len(files)} file(s) changed"
    elif artifact_type == "test_report":
        summary = data.get("summary", {})
        return f"total={summary.get('total', 0)}, passed={summary.get('passed', 0)}, failed={summary.get('failed', 0)}"
    elif artifact_type == "review_report":
        return f"recommendation={data.get('recommendation', 'unknown')}"
    elif artifact_type == "delivery_summary":
        return f"status={data.get('status', 'unknown')}"
    return f"{artifact_type} artifact"
