from app.agents.runner import run_agent
from sqlalchemy.ext.asyncio import AsyncSession


async def requirement_agent(
    session: AsyncSession,
    requirement_text: str,
    workspace_meta: dict | None = None,
    provider_id: str | None = None,
) -> dict:
    input_data = {
        "requirement_text": requirement_text,
        "workspace_meta": workspace_meta,
    }
    result = await run_agent(session, "requirement_agent", input_data, provider_id=provider_id)
    return result
