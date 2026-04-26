import pytest

from app.schemas.artifacts import (
    RequirementBrief,
    DesignSpec,
    ChangeSet,
    ChangeSetFile,
    DiffManifest,
    DiffStats,
    TestReport,
    TestSummary,
    ReviewReport,
    ReviewScores,
    ReviewIssue,
    DeliverySummary,
)


class TestRequirementBrief:
    def test_valid_input(self):
        brief = RequirementBrief(
            goal="Add health endpoint",
            acceptance_criteria=["Returns 200"],
            constraints=["Must not break existing"],
            assumptions=["Self-contained"],
            risks=["Edge cases"],
            estimated_effort="small",
        )
        assert brief.goal == "Add health endpoint"
        assert brief.schema_version == "1.0"

    def test_default_effort(self):
        brief = RequirementBrief(
            goal="Test",
            acceptance_criteria=[],
            constraints=[],
            assumptions=[],
            risks=[],
        )
        assert brief.estimated_effort == "medium"

    def test_invalid_effort(self):
        with pytest.raises(Exception):
            RequirementBrief(
                goal="Test",
                acceptance_criteria=[],
                constraints=[],
                assumptions=[],
                risks=[],
                estimated_effort="huge",
            )


class TestDesignSpec:
    def test_valid_input(self):
        spec = DesignSpec(
            summary="Add health check",
            affected_files=[],
            test_strategy="Unit test",
        )
        assert spec.summary == "Add health check"

    def test_default_lists(self):
        spec = DesignSpec(
            summary="Test",
            affected_files=[],
            test_strategy="Test",
        )
        assert spec.api_changes == []
        assert spec.data_changes == []
        assert spec.risks == []


class TestChangeSet:
    def test_valid_input(self):
        cs = ChangeSet(
            files=[
                ChangeSetFile(
                    path="app/main.py",
                    change_type="modify",
                    patch="--- a/app/main.py\n+++ b/app/main.py\n",
                )
            ],
            reasoning="Add health endpoint",
        )
        assert len(cs.files) == 1

    def test_invalid_change_type(self):
        with pytest.raises(Exception):
            ChangeSetFile(
                path="app/main.py",
                change_type="rename",
                patch="",
            )


class TestTestReport:
    def test_valid_input(self):
        report = TestReport(
            exit_code=0,
            stdout="1 passed",
            stderr="",
            duration_ms=500,
            summary=TestSummary(total=1, passed=1, failed=0, skipped=0),
        )
        assert report.exit_code == 0


class TestReviewReport:
    def test_valid_input(self):
        report = ReviewReport(
            recommendation="approve",
            scores=ReviewScores(correctness=9, security=10, style=8, test_coverage=8),
            issues=[],
            summary="Good implementation",
        )
        assert report.recommendation == "approve"

    def test_invalid_recommendation(self):
        with pytest.raises(Exception):
            ReviewReport(
                recommendation="maybe",
                scores=ReviewScores(correctness=9, security=10, style=8, test_coverage=8),
                issues=[],
                summary="Test",
            )

    def test_score_out_of_range(self):
        with pytest.raises(Exception):
            ReviewScores(correctness=11, security=10, style=8, test_coverage=8)


class TestDeliverySummary:
    def test_valid_input(self):
        summary = DeliverySummary(
            status="ready",
            deliverables=["Health endpoint"],
            test_summary="All tests passed",
            known_risks=[],
            next_steps=["Merge to main"],
        )
        assert summary.status == "ready"

    def test_invalid_status(self):
        with pytest.raises(Exception):
            DeliverySummary(
                status="pending",
                deliverables=[],
                test_summary="",
                known_risks=[],
                next_steps=[],
            )
