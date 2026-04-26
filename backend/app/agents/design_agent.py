from app.agents.runner import run_agent
from sqlalchemy.ext.asyncio import AsyncSession


async def design_agent(
    session: AsyncSession,
    requirement_brief: dict,
    code_context: dict | None = None,
    reject_reason: str | None = None,
    provider_id: str | None = None,
) -> dict:
    input_data = {
        "requirement_brief": requirement_brief,
        "code_context": code_context,
        "reject_reason": reject_reason,
    }
    result = await run_agent(session, "design_agent", input_data, provider_id=provider_id)
    return result
