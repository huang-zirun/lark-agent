from app.shared.logging import get_logger

logger = get_logger(__name__)


async def mock_requirement_agent(requirement_text: str, **kwargs) -> dict:
    return {
        "requirement_brief": {
            "schema_version": "1.0",
            "goal": f"Implement the requested feature: {requirement_text[:100]}",
            "acceptance_criteria": [
                "Feature is implemented as specified",
                "All tests pass",
                "Code follows project conventions",
                "API documentation is updated",
            ],
            "constraints": [
                "Must not break existing functionality",
                "Must follow existing code patterns",
            ],
            "assumptions": [
                "The requirement is self-contained",
                "No external dependencies needed",
            ],
            "risks": [
                "Edge cases may not be covered",
                "Integration with existing code may need adjustment",
            ],
            "estimated_effort": "small",
        }
    }


async def mock_design_agent(requirement_brief: dict, **kwargs) -> dict:
    return {
        "design_spec": {
            "schema_version": "1.0",
            "summary": "Add a new health check endpoint to the API",
            "affected_files": [
                {
                    "path": "app/main.py",
                    "change_type": "modify",
                    "reason": "Add health check route handler",
                },
                {
                    "path": "tests/test_health.py",
                    "change_type": "create",
                    "reason": "Add health check tests",
                },
            ],
            "api_changes": [
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
            ],
            "data_changes": [],
            "test_strategy": "Unit test the health endpoint returns correct response with service, status, version, and time fields",
            "risks": [
                {"level": "low", "description": "Minimal change, low risk"}
            ],
        }
    }


async def mock_code_patch_agent(design_spec: dict, **kwargs) -> dict:
    return {
        "change_set": {
            "schema_version": "1.0",
            "files": [
                {
                    "path": "app/main.py",
                    "change_type": "modify",
                    "content": None,
                    "patch": (
                        "--- a/app/main.py\n"
                        "+++ b/app/main.py\n"
                        "@@ -1,0 +1,5 @@\n"
                        "+# Health endpoint added by DevFlow Engine\n"
                    ),
                },
                {
                    "path": "tests/test_health.py",
                    "change_type": "create",
                    "content": (
                        "from fastapi.testclient import TestClient\n"
                        "from app.main import app\n"
                        "\n"
                        "client = TestClient(app)\n"
                        "\n"
                        "\n"
                        "def test_health_check():\n"
                        '    response = client.get("/api/health")\n'
                        "    assert response.status_code == 200\n"
                        "    data = response.json()\n"
                        '    assert "service" in data\n'
                        '    assert data["status"] == "ok"\n'
                        '    assert "version" in data\n'
                        '    assert "time" in data\n'
                    ),
                    "patch": "",
                },
            ],
            "reasoning": "Added health check endpoint and corresponding test file",
        }
    }


async def mock_test_agent(change_set: dict, **kwargs) -> dict:
    return {
        "test_report": {
            "schema_version": "1.0",
            "exit_code": 0,
            "stdout": "test_health_check PASSED\n1 passed in 0.5s",
            "stderr": "",
            "duration_ms": 500,
            "summary": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
        }
    }


async def mock_review_agent(design_spec: dict, change_set: dict, test_report: dict, **kwargs) -> dict:
    return {
        "review_report": {
            "schema_version": "1.0",
            "recommendation": "approve",
            "scores": {
                "correctness": 9,
                "security": 10,
                "style": 8,
                "test_coverage": 8,
            },
            "issues": [
                {
                    "severity": "info",
                    "category": "style",
                    "description": "Consider adding docstring to the test function",
                    "suggestion": "Add a docstring explaining what the test verifies",
                }
            ],
            "summary": "The implementation is clean and correct. Minor style suggestion for documentation.",
        }
    }


async def mock_delivery_agent(change_set: dict, review_report: dict, test_report: dict, **kwargs) -> dict:
    return {
        "delivery_summary": {
            "schema_version": "1.0",
            "status": "ready",
            "deliverables": [
                "Health check endpoint implementation",
                "Unit test for health check",
            ],
            "test_summary": "All 1 test passed successfully",
            "known_risks": [
                "Health endpoint does not check database connectivity",
            ],
            "next_steps": [
                "Merge the changes to main branch",
                "Deploy to staging environment",
                "Verify in staging before production",
            ],
        }
    }


MOCK_AGENTS = {
    "requirement_agent": mock_requirement_agent,
    "design_agent": mock_design_agent,
    "code_patch_agent": mock_code_patch_agent,
    "test_agent": mock_test_agent,
    "review_agent": mock_review_agent,
    "delivery_agent": mock_delivery_agent,
}
