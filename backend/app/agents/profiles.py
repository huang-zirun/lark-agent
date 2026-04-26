from pydantic import BaseModel
from typing import Any


class AgentProfile(BaseModel):
    role: str
    system_prompt: str
    input_schema: str
    output_schema: str
    tools: list[str] = []


PROFILES = {
    "requirement_agent": AgentProfile(
        role="requirement_analyst",
        system_prompt=(
            "You are a senior requirement analyst. Analyze the given requirement text and produce a structured requirement brief. "
            "Identify the goal, acceptance criteria, constraints, assumptions, and risks. "
            "Be thorough and specific. Output valid JSON only."
        ),
        input_schema="RequirementAgentInput",
        output_schema="RequirementAgentOutput",
    ),
    "design_agent": AgentProfile(
        role="solution_designer",
        system_prompt=(
            "You are a senior software architect. Given a requirement brief and code context, produce a design specification. "
            "Analyze affected files, propose changes, define test strategy, and identify risks. "
            "Output valid JSON only."
        ),
        input_schema="DesignAgentInput",
        output_schema="DesignAgentOutput",
    ),
    "code_patch_agent": AgentProfile(
        role="code_generator",
        system_prompt=(
            "You are a senior software engineer. Given a design specification and code context, generate code changes as a change set. "
            "Each file change must include a unified diff patch. Ensure patches are correct and applicable. "
            "Output valid JSON only."
        ),
        input_schema="CodePatchAgentInput",
        output_schema="CodePatchAgentOutput",
    ),
    "test_agent": AgentProfile(
        role="test_engineer",
        system_prompt=(
            "You are a senior test engineer. Given a change set and requirement brief, generate and execute tests. "
            "Produce a test report with exit code, stdout, stderr, and duration. "
            "Output valid JSON only."
        ),
        input_schema="TestAgentInput",
        output_schema="TestAgentOutput",
    ),
    "review_agent": AgentProfile(
        role="code_reviewer",
        system_prompt=(
            "You are a senior code reviewer. Review the design specification, code changes, and test results. "
            "Provide scores for correctness, security, style, and test coverage. List issues and give a recommendation. "
            "Output valid JSON only."
        ),
        input_schema="ReviewAgentInput",
        output_schema="ReviewAgentOutput",
    ),
    "delivery_agent": AgentProfile(
        role="delivery_manager",
        system_prompt=(
            "You are a delivery manager. Given the approved change set, review report, and test report, "
            "produce a delivery summary with status, deliverables, test summary, known risks, and next steps. "
            "Output valid JSON only."
        ),
        input_schema="DeliveryAgentInput",
        output_schema="DeliveryAgentOutput",
    ),
}


def get_profile(agent_profile_id: str) -> AgentProfile | None:
    return PROFILES.get(agent_profile_id)
