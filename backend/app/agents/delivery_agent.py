from app.agents.runner import run_agent
from sqlalchemy.ext.asyncio import AsyncSession


async def delivery_agent(
    session: AsyncSession,
    change_set: dict,
    review_report: dict,
    test_report: dict,
    diff_manifest: dict | None = None,
    provider_id: str | None = None,
) -> dict:
    input_data = {
        "change_set": change_set,
        "review_report": review_report,
        "test_report": test_report,
        "diff_manifest": diff_manifest,
    }
    result = await run_agent(session, "delivery_agent", input_data, provider_id=provider_id)
    return result
