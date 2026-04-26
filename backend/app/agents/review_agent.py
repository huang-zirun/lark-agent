from app.agents.runner import run_agent
from sqlalchemy.ext.asyncio import AsyncSession


async def review_agent(
    session: AsyncSession,
    design_spec: dict,
    change_set: dict,
    test_report: dict,
    diff_manifest: dict | None = None,
    provider_id: str | None = None,
) -> dict:
    input_data = {
        "design_spec": design_spec,
        "change_set": change_set,
        "test_report": test_report,
        "diff_manifest": diff_manifest,
    }
    result = await run_agent(session, "review_agent", input_data, provider_id=provider_id)
    return result
