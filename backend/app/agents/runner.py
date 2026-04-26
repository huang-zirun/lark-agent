import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.profiles import get_profile, AgentProfile
from app.core.provider.provider_registry import resolve_provider
from app.schemas.artifacts import ARTIFACT_TYPE_TO_SCHEMA
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def run_agent(
    session: AsyncSession,
    agent_profile_id: str,
    input_data: dict,
    provider_id: str | None = None,
) -> dict:
    profile = get_profile(agent_profile_id)
    if not profile:
        raise ExecutionError(f"Agent profile not found: {agent_profile_id}")

    provider = await resolve_provider(session, provider_id=provider_id)

    prompt = _build_prompt(profile, input_data)
    schema = _get_output_schema(profile)

    try:
        result = await provider.generate(
            prompt=prompt,
            schema=schema,
            system_prompt=profile.system_prompt,
        )
    except Exception as e:
        raise ExecutionError(f"Agent {agent_profile_id} execution failed: {str(e)}")

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            raise ExecutionError(f"Agent {agent_profile_id} returned invalid JSON")

    return result


def _build_prompt(profile: AgentProfile, input_data: dict) -> str:
    parts = [f"## Task: {profile.role}"]
    parts.append(f"\n## Input Data:\n```json\n{json.dumps(input_data, ensure_ascii=False, indent=2)}\n```")
    parts.append(f"\n## Instructions:\n{profile.system_prompt}")
    parts.append("\nRespond with valid JSON matching the expected output schema.")
    return "\n".join(parts)


def _get_output_schema(profile: AgentProfile) -> dict | None:
    output_type = profile.output_schema.replace("AgentOutput", "").lower()
    if output_type == "requirement":
        output_type = "requirement_brief"
    elif output_type == "design":
        output_type = "design_spec"
    elif output_type == "codepatch":
        output_type = "change_set"
    elif output_type == "test":
        output_type = "test_report"
    elif output_type == "review":
        output_type = "review_report"
    elif output_type == "delivery":
        output_type = "delivery_summary"

    schema_cls = ARTIFACT_TYPE_TO_SCHEMA.get(output_type)
    if schema_cls:
        return schema_cls.model_json_schema()
    return None
