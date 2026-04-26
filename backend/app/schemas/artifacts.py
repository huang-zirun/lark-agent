from pydantic import BaseModel, Field


class AffectedFile(BaseModel):
    path: str
    change_type: str = Field(pattern=r"^(create|modify|delete)$")
    reason: str


class RequirementBrief(BaseModel):
    schema_version: str = "1.0"
    goal: str
    acceptance_criteria: list[str]
    constraints: list[str]
    assumptions: list[str]
    risks: list[str]
    estimated_effort: str = Field(default="medium", pattern=r"^(small|medium|large)$")


class DesignSpec(BaseModel):
    schema_version: str = "1.0"
    summary: str
    affected_files: list[AffectedFile]
    api_changes: list[dict] = Field(default_factory=list)
    data_changes: list[dict] = Field(default_factory=list)
    test_strategy: str
    risks: list[dict] = Field(default_factory=list)


class ChangeSetFile(BaseModel):
    path: str
    change_type: str = Field(pattern=r"^(create|modify|delete)$")
    content: str | None = None
    patch: str | None = None


class ChangeSet(BaseModel):
    schema_version: str = "1.0"
    files: list[ChangeSetFile]
    reasoning: str


class DiffStats(BaseModel):
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


class DiffManifest(BaseModel):
    schema_version: str = "1.0"
    base_commit: str
    changed_files: list[str]
    diff_path: str
    stats: DiffStats


class TestSummary(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class TestReport(BaseModel):
    schema_version: str = "1.0"
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    summary: TestSummary


class ReviewIssue(BaseModel):
    severity: str = Field(pattern=r"^(critical|major|minor|info)$")
    category: str
    description: str
    suggestion: str


class ReviewScores(BaseModel):
    correctness: int = Field(ge=0, le=10)
    security: int = Field(ge=0, le=10)
    style: int = Field(ge=0, le=10)
    test_coverage: int = Field(ge=0, le=10)


class ReviewReport(BaseModel):
    schema_version: str = "1.0"
    recommendation: str = Field(pattern=r"^(approve|reject|needs_improvement)$")
    scores: ReviewScores
    issues: list[ReviewIssue]
    summary: str


class DeliverySummary(BaseModel):
    schema_version: str = "1.0"
    status: str = Field(pattern=r"^(ready|needs_fix)$")
    deliverables: list[str]
    test_summary: str
    known_risks: list[str]
    next_steps: list[str]


ARTIFACT_TYPE_TO_SCHEMA = {
    "requirement_brief": RequirementBrief,
    "design_spec": DesignSpec,
    "change_set": ChangeSet,
    "diff_manifest": DiffManifest,
    "test_report": TestReport,
    "review_report": ReviewReport,
    "delivery_summary": DeliverySummary,
}

OUTPUT_SCHEMA_TO_ARTIFACT_TYPE = {
    "requirement": "requirement_brief",
    "design": "design_spec",
    "codepatch": "change_set",
    "test": "test_report",
    "review": "review_report",
    "delivery": "delivery_summary",
}
