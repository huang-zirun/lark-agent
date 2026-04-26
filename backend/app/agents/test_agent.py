from app.agents.runner import run_agent
from sqlalchemy.ext.asyncio import AsyncSession


async def test_agent(
    session: AsyncSession,
    change_set: dict,
    requirement_brief: dict,
    design_spec: dict | None = None,
    provider_id: str | None = None,
) -> dict:
    input_data = {
        "change_set": change_set,
        "requirement_brief": requirement_brief,
        "design_spec": design_spec,
    }
    result = await run_agent(session, "test_agent", input_data, provider_id=provider_id)
    return result
