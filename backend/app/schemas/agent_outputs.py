from pydantic import BaseModel, Field

from app.schemas.artifacts import (
    RequirementBrief,
    DesignSpec,
    ChangeSet,
    DiffManifest,
    TestReport,
    ReviewReport,
    DeliverySummary,
)


class CodeContext(BaseModel):
    directory_tree: dict | None = None
    file_contents: dict[str, str] | None = None


class RequirementAgentInput(BaseModel):
    requirement_text: str
    workspace_meta: dict | None = None


class RequirementAgentOutput(BaseModel):
    requirement_brief: RequirementBrief


class DesignAgentInput(BaseModel):
    requirement_brief: RequirementBrief
    code_context: CodeContext | None = None
    reject_reason: str | None = None


class DesignAgentOutput(BaseModel):
    design_spec: DesignSpec


class CodePatchAgentInput(BaseModel):
    design_spec: DesignSpec
    code_context: CodeContext | None = None
    reject_reason: str | None = None


class CodePatchAgentOutput(BaseModel):
    change_set: ChangeSet


class TestAgentInput(BaseModel):
    change_set: ChangeSet
    requirement_brief: RequirementBrief
    design_spec: DesignSpec | None = None
    code_context: CodeContext | None = None


class TestAgentOutput(BaseModel):
    test_report: TestReport


class ReviewAgentInput(BaseModel):
    design_spec: DesignSpec
    change_set: ChangeSet
    test_report: TestReport
    diff_manifest: DiffManifest | None = None


class ReviewAgentOutput(BaseModel):
    review_report: ReviewReport


class DeliveryAgentInput(BaseModel):
    change_set: ChangeSet
    review_report: ReviewReport
    test_report: TestReport
    diff_manifest: DiffManifest | None = None


class DeliveryAgentOutput(BaseModel):
    delivery_summary: DeliverySummary
