import json
import copy

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.profiles import get_profile, AgentProfile
from app.core.provider.provider_registry import resolve_provider
from app.core.provider.base import generate_with_retry
from app.schemas.artifacts import ARTIFACT_TYPE_TO_SCHEMA
from app.shared.errors import ExecutionError, OutputValidationError
from app.shared.logging import get_logger

logger = get_logger(__name__)

OUTPUT_FIX_MAX_RETRIES = 2


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
    schema = _get_output_schema(profile)

    last_validation_error = None
    for attempt in range(OUTPUT_FIX_MAX_RETRIES + 1):
        prompt = _build_prompt(profile, input_data, last_validation_error)

        try:
            call_result = await generate_with_retry(
                provider=provider,
                prompt=prompt,
                schema=schema,
                system_prompt=profile.system_prompt,
            )
            result = call_result.content

            logger.info(
                f"Agent {agent_profile_id} LLM call: "
                f"model={call_result.model}, "
                f"tokens={call_result.usage.total_tokens}, "
                f"latency={call_result.latency_ms}ms"
            )
        except Exception as e:
            raise ExecutionError(f"Agent {agent_profile_id} execution failed: {str(e)}")

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                raise ExecutionError(f"Agent {agent_profile_id} returned invalid JSON")

        if not isinstance(result, dict):
            raise ExecutionError(f"Agent {agent_profile_id} returned non-dict result: {type(result)}")

        try:
            validated = _validate_and_fix_output(result, agent_profile_id)
            return validated
        except OutputValidationError as e:
            last_validation_error = str(e)
            logger.warning(
                f"Agent {agent_profile_id} output validation failed (attempt {attempt + 1}): {last_validation_error[:300]}"
            )
            if attempt == OUTPUT_FIX_MAX_RETRIES:
                raise ExecutionError(
                    f"Agent {agent_profile_id} output validation failed after {OUTPUT_FIX_MAX_RETRIES + 1} attempts: {last_validation_error[:500]}"
                )

    raise ExecutionError(f"Agent {agent_profile_id} output validation failed unexpectedly")


def _build_prompt(profile: AgentProfile, input_data: dict, validation_error: str | None = None) -> str:
    parts = [f"## Task: {profile.role}"]
    parts.append(f"\n## Input Data:\n```json\n{json.dumps(input_data, ensure_ascii=False, indent=2)}\n```")
    parts.append(f"\n## Instructions:\n{profile.system_prompt}")
    parts.append("\nRespond with valid JSON matching the expected output schema.")

    if validation_error:
        parts.append(f"\n## Previous Output Error:\nYour previous output had validation errors:\n{validation_error}")
        parts.append("\nPlease fix these errors and respond with valid JSON matching the schema exactly.")

    return "\n".join(parts)


def _get_output_schema(profile: AgentProfile) -> dict | None:
    from app.schemas.artifacts import OUTPUT_SCHEMA_TO_ARTIFACT_TYPE

    raw_type = profile.output_schema.replace("AgentOutput", "").lower()
    artifact_type = OUTPUT_SCHEMA_TO_ARTIFACT_TYPE.get(raw_type)
    if not artifact_type:
        logger.warning(f"No artifact type mapping for output_schema '{profile.output_schema}' (raw_type='{raw_type}')")
        return None

    schema_cls = ARTIFACT_TYPE_TO_SCHEMA.get(artifact_type)
    if schema_cls:
        return schema_cls.model_json_schema()
    return None


def _validate_and_fix_output(result: dict, agent_profile_id: str) -> dict:
    fixed = copy.deepcopy(result)

    has_artifact_key = any(key in ARTIFACT_TYPE_TO_SCHEMA for key in fixed.keys())

    if not has_artifact_key:
        expected_type = _infer_artifact_type(agent_profile_id)
        if expected_type and expected_type in ARTIFACT_TYPE_TO_SCHEMA:
            schema_cls = ARTIFACT_TYPE_TO_SCHEMA[expected_type]
            try:
                schema_cls.model_validate(fixed)
                logger.info(f"Auto-wrapping flat output from agent {agent_profile_id} under key '{expected_type}'")
                fixed = {expected_type: fixed}
            except Exception as e:
                logger.warning(f"Flat output from agent {agent_profile_id} does not match schema for '{expected_type}': {e}")

    filtered_keys = []
    for key in list(fixed.keys()):
        if key not in ARTIFACT_TYPE_TO_SCHEMA:
            logger.info(f"Filtering non-artifact key '{key}' from agent {agent_profile_id} output")
            filtered_keys.append(key)
            del fixed[key]

    if filtered_keys:
        logger.info(f"Filtered {len(filtered_keys)} non-artifact key(s) from agent {agent_profile_id} output: {filtered_keys}")

    for artifact_type, artifact_data in fixed.items():
        schema_cls = ARTIFACT_TYPE_TO_SCHEMA.get(artifact_type)
        if not schema_cls:
            continue

        try:
            validated_model = schema_cls.model_validate(artifact_data)
            fixed[artifact_type] = validated_model.model_dump()
        except Exception as e:
            fixed_data = _try_fix_artifact(artifact_data, schema_cls, str(e))
            if fixed_data is not None:
                fixed[artifact_type] = fixed_data
                try:
                    validated_model = schema_cls.model_validate(fixed_data)
                    fixed[artifact_type] = validated_model.model_dump()
                except Exception as e2:
                    raise OutputValidationError(
                        f"Artifact '{artifact_type}' validation failed even after fix: {str(e2)[:300]}"
                    )
            else:
                raise OutputValidationError(
                    f"Artifact '{artifact_type}' validation failed and could not be auto-fixed: {str(e)[:300]}"
                )

    return fixed


def _infer_artifact_type(agent_profile_id: str) -> str | None:
    profile = get_profile(agent_profile_id)
    if not profile:
        return None
    from app.schemas.artifacts import OUTPUT_SCHEMA_TO_ARTIFACT_TYPE
    raw_type = profile.output_schema.replace("AgentOutput", "").lower()
    return OUTPUT_SCHEMA_TO_ARTIFACT_TYPE.get(raw_type)


def _try_fix_artifact(data: dict, schema_cls, error_msg: str) -> dict | None:
    try:
        fixed = copy.deepcopy(data)

        if "schema_version" not in fixed:
            fixed["schema_version"] = "1.0"

        schema = schema_cls.model_json_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for field_name in required:
            if field_name not in fixed:
                if field_name in properties:
                    prop = properties[field_name]
                    default = _get_default_for_property(prop)
                    if default is not None:
                        fixed[field_name] = default

        for key, value in list(fixed.items()):
            if key in properties:
                prop = properties[key]
                coerced = _try_coerce_type(value, prop)
                if coerced is not None:
                    fixed[key] = coerced

        return fixed
    except Exception:
        return None


def _get_default_for_property(prop: dict):
    if "default" in prop:
        return prop["default"]
    prop_type = prop.get("type", "string")
    if prop_type == "string":
        return ""
    elif prop_type == "integer":
        return 0
    elif prop_type == "number":
        return 0.0
    elif prop_type == "boolean":
        return True
    elif prop_type == "array":
        return []
    elif prop_type == "object":
        return {}
    return None


def _try_coerce_type(value, prop: dict):
    prop_type = prop.get("type", "string")
    try:
        if prop_type == "string" and not isinstance(value, str):
            return str(value)
        elif prop_type == "integer" and isinstance(value, (float, str)):
            return int(float(value))
        elif prop_type == "number" and isinstance(value, (int, str)):
            return float(value)
        elif prop_type == "boolean" and isinstance(value, str):
            if value.lower() in ("true", "1", "yes"):
                return True
            elif value.lower() in ("false", "0", "no"):
                return False
    except (ValueError, TypeError):
        pass
    return None
