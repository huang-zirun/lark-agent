from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from devflow.approval_client import (
    ApprovalError,
    build_code_review_form,
    build_solution_review_form,
    create_external_approval_instance,
    create_stage_approval_instance,
    ensure_approval_definition,
    ensure_stage_approval_definition,
    _STAGE_APPROVAL_CONFIG,
)


class StageApprovalConfigTests(unittest.TestCase):
    def test_solution_design_config_exists(self) -> None:
        cfg = _STAGE_APPROVAL_CONFIG["solution_design"]
        self.assertEqual(cfg["default_code"], "devflow-solution-review")
        self.assertIn("技术方案", cfg["title"])

    def test_code_review_config_exists(self) -> None:
        cfg = _STAGE_APPROVAL_CONFIG["code_review"]
        self.assertEqual(cfg["default_code"], "devflow-code-review")
        self.assertIn("代码评审", cfg["title"])

    def test_unknown_stage_falls_back_to_solution_design(self) -> None:
        cfg = _STAGE_APPROVAL_CONFIG.get("unknown_stage", _STAGE_APPROVAL_CONFIG["solution_design"])
        self.assertEqual(cfg["default_code"], "devflow-solution-review")


class BuildFormTests(unittest.TestCase):
    def test_build_solution_review_form(self) -> None:
        form = build_solution_review_form(
            run_id="run-123",
            summary="实现用户登录",
            risk_level="medium",
            solution_markdown_path="/path/to/solution.md",
        )
        self.assertEqual(len(form), 4)
        self.assertEqual(form[0]["id"], "run_id")
        self.assertEqual(form[0]["value"], "run-123")

    def test_build_code_review_form(self) -> None:
        form = build_code_review_form(
            run_id="run-456",
            summary="发现阻塞问题",
            risk_level="high",
            blocking_count=3,
            review_doc_path="/path/to/review.md",
        )
        self.assertEqual(len(form), 5)
        self.assertEqual(form[0]["id"], "run_id")
        self.assertEqual(form[0]["value"], "run-456")
        self.assertEqual(form[3]["id"], "blocking_count")
        self.assertEqual(form[3]["value"], "3")


class EnsureStageApprovalDefinitionTests(unittest.TestCase):
    @patch("devflow.approval_client._run_lark_api")
    def test_returns_hint_if_valid(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"approval_code": "existing-code"}
        result = ensure_stage_approval_definition(
            stage="code_review",
            approval_code_hint="existing-code",
        )
        self.assertEqual(result, "existing-code")
        mock_api.assert_called_once_with("GET", "/open-apis/approval/v4/approvals/existing-code")

    @patch("devflow.approval_client._run_lark_api")
    def test_creates_new_definition_when_hint_invalid(self, mock_api: MagicMock) -> None:
        mock_api.side_effect = [
            ApprovalError("not found"),
            {"approval_code": "invalid-code"},
        ]
        result = ensure_stage_approval_definition(
            stage="code_review",
            approval_code_hint="invalid-code",
        )
        self.assertEqual(result, "invalid-code")
        self.assertEqual(mock_api.call_count, 2)
        second_call = mock_api.call_args_list[1]
        self.assertEqual(second_call[0][0], "POST")
        self.assertIn("external_approvals", second_call[0][1])
        payload = second_call[0][2]
        self.assertEqual(payload["approval_code"], "invalid-code")

    @patch("devflow.approval_client._run_lark_api")
    def test_creates_new_definition_without_hint(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"approval_code": "new-code-review-code"}
        result = ensure_stage_approval_definition(stage="code_review")
        self.assertEqual(result, "new-code-review-code")
        mock_api.assert_called_once()
        payload = mock_api.call_args[0][2]
        self.assertEqual(payload["approval_code"], "devflow-code-review")

    @patch("devflow.approval_client._run_lark_api")
    def test_ensure_approval_definition_delegates_to_stage(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"approval_code": "existing"}
        result = ensure_approval_definition(approval_code_hint="existing")
        self.assertEqual(result, "existing")


class CreateStageApprovalInstanceTests(unittest.TestCase):
    @patch("devflow.approval_client._run_lark_api")
    def test_create_stage_approval_instance_code_review(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"data": {"instance_id": "inst-cr-001"}}
        result = create_stage_approval_instance(
            approval_code="devflow-code-review",
            user_open_id="ou_test",
            run_id="run-cr-001",
            stage="code_review",
            summary="发现2个阻塞问题",
            risk_level="high",
            doc_path="/path/to/review.md",
            form_fields=[{"name": "blocking_count", "value": "阻塞问题数：2"}],
        )
        self.assertEqual(result, "inst-cr-001")
        payload = mock_api.call_args[0][2]
        self.assertEqual(payload["approval_code"], "devflow-code-review")
        task = payload["task_list"][0]
        self.assertEqual(task["task_id"], "task-run-cr-001")
        i18n = payload["i18n_resources"][0]["texts"]
        title_text = next(t["value"] for t in i18n if "代码评审" in t.get("value", ""))
        self.assertIn("代码评审", title_text)

    @patch("devflow.approval_client._run_lark_api")
    def test_create_external_approval_instance_delegates(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"data": {"instance_id": "inst-sol-001"}}
        result = create_external_approval_instance(
            approval_code="devflow-solution-review",
            user_open_id="ou_test",
            run_id="run-sol-001",
            summary="实现用户登录",
            risk_level="medium",
            solution_markdown_path="/path/to/solution.md",
        )
        self.assertEqual(result, "inst-sol-001")
        payload = mock_api.call_args[0][2]
        i18n = payload["i18n_resources"][0]["texts"]
        title_text = next(t["value"] for t in i18n if "技术方案" in t.get("value", ""))
        self.assertIn("技术方案", title_text)


if __name__ == "__main__":
    unittest.main()
