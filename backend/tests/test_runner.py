import pytest

from app.agents.runner import _build_prompt, _validate_and_fix_output, _try_fix_artifact, _get_default_for_property
from app.agents.profiles import get_profile, PROFILES
from app.schemas.artifacts import RequirementBrief
from app.shared.errors import OutputValidationError


class TestBuildPrompt:
    def test_basic_prompt(self):
        profile = get_profile("requirement_agent")
        prompt = _build_prompt(profile, {"requirement_text": "Add health endpoint"})
        assert "requirement_analyst" in prompt
        assert "Add health endpoint" in prompt
        assert "valid JSON" in prompt

    def test_prompt_with_validation_error(self):
        profile = get_profile("requirement_agent")
        prompt = _build_prompt(
            profile,
            {"requirement_text": "test"},
            validation_error="Missing field 'goal'",
        )
        assert "Previous Output Error" in prompt
        assert "Missing field 'goal'" in prompt


class TestValidateAndFixOutput:
    def test_valid_output(self):
        result = {
            "requirement_brief": {
                "schema_version": "1.0",
                "goal": "Add health endpoint",
                "acceptance_criteria": ["Returns 200"],
                "constraints": [],
                "assumptions": [],
                "risks": [],
                "estimated_effort": "small",
            }
        }
        validated = _validate_and_fix_output(result, "requirement_agent")
        assert "requirement_brief" in validated

    def test_output_missing_schema_version(self):
        result = {
            "requirement_brief": {
                "goal": "Add health endpoint",
                "acceptance_criteria": ["Returns 200"],
                "constraints": [],
                "assumptions": [],
                "risks": [],
            }
        }
        validated = _validate_and_fix_output(result, "requirement_agent")
        assert "requirement_brief" in validated
        assert validated["requirement_brief"]["schema_version"] == "1.0"

    def test_output_auto_fixable_missing_required(self):
        result = {
            "requirement_brief": {
                "invalid_data": True,
            }
        }
        validated = _validate_and_fix_output(result, "requirement_agent")
        assert "requirement_brief" in validated
        assert validated["requirement_brief"]["schema_version"] == "1.0"
        assert validated["requirement_brief"]["goal"] == ""

    def test_output_invalid_enum_value(self):
        result = {
            "requirement_brief": {
                "goal": "Test",
                "acceptance_criteria": [],
                "constraints": [],
                "assumptions": [],
                "risks": [],
                "estimated_effort": "huge",
            }
        }
        with pytest.raises((OutputValidationError, Exception)):
            _validate_and_fix_output(result, "requirement_agent")

    def test_output_with_unknown_artifact_type(self):
        result = {
            "unknown_type": {"some": "data"},
        }
        validated = _validate_and_fix_output(result, "test_agent")
        assert "unknown_type" in validated


class TestGetDefaultForProperty:
    def test_string_default(self):
        assert _get_default_for_property({"type": "string"}) == ""

    def test_integer_default(self):
        assert _get_default_for_property({"type": "integer"}) == 0

    def test_array_default(self):
        assert _get_default_for_property({"type": "array"}) == []

    def test_explicit_default(self):
        assert _get_default_for_property({"type": "string", "default": "hello"}) == "hello"


class TestProfiles:
    def test_all_profiles_exist(self):
        expected = ["requirement_agent", "design_agent", "code_patch_agent", "test_agent", "review_agent", "delivery_agent"]
        for name in expected:
            assert name in PROFILES
            profile = get_profile(name)
            assert profile is not None
            assert profile.role
            assert profile.system_prompt
            assert profile.input_schema
            assert profile.output_schema
