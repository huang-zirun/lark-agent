from app.agents.runner import run_agent
from sqlalchemy.ext.asyncio import AsyncSession


async def code_patch_agent(
    session: AsyncSession,
    design_spec: dict,
    code_context: dict | None = None,
    reject_reason: str | None = None,
    provider_id: str | None = None,
) -> dict:
    input_data = {
        "design_spec": design_spec,
        "code_context": code_context,
        "reject_reason": reject_reason,
    }
    result = await run_agent(session, "code_patch_agent", input_data, provider_id=provider_id)
    return result
