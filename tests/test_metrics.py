from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from devflow.metrics import get_run_artifact_markdown, get_run_detail, get_run_llm_trace


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request_payload(model: str, system: str, user: str) -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }


def response_payload(content: str, total_tokens: int) -> dict:
    return {
        "started_at": "2026-05-06T00:00:00Z",
        "ended_at": "2026-05-06T00:00:01Z",
        "duration_ms": 1000,
        "content": content,
        "usage": {
            "prompt_tokens": total_tokens - 1,
            "completion_tokens": 1,
            "total_tokens": total_tokens,
        },
        "usage_source": "provider",
    }


class MetricsTraceTests(unittest.TestCase):
    def test_llm_trace_normalizes_intake_and_multi_turn_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            write_json(run_dir / "llm-request.json", request_payload("intake-model", "intake system", "intake user"))
            write_json(run_dir / "llm-response.json", response_payload("intake output", 10))
            write_json(run_dir / "code-llm-request-turn1.json", request_payload("code-model", "code system", "code user 1"))
            write_json(run_dir / "code-llm-response-turn1.json", response_payload("code output 1", 20))
            write_json(run_dir / "code-llm-response-turn2.json", response_payload("code output 2", 30))

            trace = get_run_llm_trace(run_dir)

        self.assertEqual([record["stage"] for record in trace], ["requirement_intake", "code_generation", "code_generation"])
        self.assertEqual(trace[0]["model"], "intake-model")
        self.assertEqual(trace[0]["system_prompt"], "intake system")
        self.assertEqual(trace[0]["user_prompt"], "intake user")
        self.assertEqual(trace[0]["content"], "intake output")
        self.assertIsNone(trace[0]["turn"])
        self.assertEqual(trace[1]["turn"], 1)
        self.assertEqual(trace[1]["model"], "code-model")
        self.assertEqual(trace[2]["turn"], 2)
        self.assertIsNone(trace[2]["request_path"])
        self.assertEqual(trace[2]["content"], "code output 2")

    def test_run_detail_token_summary_uses_normalized_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            write_json(
                run_dir / "run.json",
                {
                    "run_id": "run_metrics",
                    "stages": [
                        {"name": "requirement_intake", "status": "success"},
                        {"name": "solution_design", "status": "success"},
                        {"name": "code_generation", "status": "success"},
                        {"name": "test_generation", "status": "success"},
                        {"name": "code_review", "status": "success"},
                    ],
                },
            )
            write_json(run_dir / "llm-request.json", request_payload("intake-model", "s", "u"))
            write_json(run_dir / "llm-response.json", response_payload("intake", 10))
            write_json(run_dir / "solution-llm-request.json", request_payload("solution-model", "s", "u"))
            write_json(run_dir / "solution-llm-response.json", response_payload("solution", 20))
            write_json(run_dir / "code-llm-request-turn1.json", request_payload("code-model", "s", "u"))
            write_json(run_dir / "code-llm-response-turn1.json", response_payload("code", 30))
            write_json(run_dir / "test-llm-request-turn1.json", request_payload("test-model", "s", "u"))
            write_json(run_dir / "test-llm-response-turn1.json", response_payload("test", 40))
            write_json(run_dir / "review-llm-request-turn1.json", request_payload("review-model", "s", "u"))
            write_json(run_dir / "review-llm-response-turn1.json", response_payload("review", 50))

            detail = get_run_detail(run_dir)

        summary = detail["token_summary"]
        self.assertEqual(summary["requirement_intake"]["total_tokens"], 10)
        self.assertEqual(summary["solution_design"]["total_tokens"], 20)
        self.assertEqual(summary["code_generation"]["total_tokens"], 30)
        self.assertEqual(summary["test_generation"]["total_tokens"], 40)
        self.assertEqual(summary["code_review"]["total_tokens"], 50)
        self.assertEqual(summary["code_review"]["model"], "review-model")

    def test_artifact_markdown_supports_all_stages_and_run_json_path_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            custom_requirement = run_dir / "custom-requirement.md"
            custom_requirement.write_text("# Custom requirement\n", encoding="utf-8")
            (run_dir / "requirement.md").write_text("# Fallback requirement\n", encoding="utf-8")
            (run_dir / "solution.md").write_text("# Solution\n", encoding="utf-8")
            (run_dir / "code-generation.md").write_text("# Code\n", encoding="utf-8")
            (run_dir / "test-generation.md").write_text("# Test\n", encoding="utf-8")
            (run_dir / "code-review.md").write_text("# Review\n", encoding="utf-8")
            (run_dir / "delivery.md").write_text("# Delivery\n", encoding="utf-8")
            write_json(run_dir / "run.json", {"run_id": "run_md", "requirement_markdown": str(custom_requirement)})

            self.assertEqual(get_run_artifact_markdown(run_dir, "requirement_intake"), "# Custom requirement\n")
            self.assertEqual(get_run_artifact_markdown(run_dir, "solution_design"), "# Solution\n")
            self.assertEqual(get_run_artifact_markdown(run_dir, "code_generation"), "# Code\n")
            self.assertEqual(get_run_artifact_markdown(run_dir, "test_generation"), "# Test\n")
            self.assertEqual(get_run_artifact_markdown(run_dir, "code_review"), "# Review\n")
            self.assertEqual(get_run_artifact_markdown(run_dir, "delivery"), "# Delivery\n")

    def test_missing_artifact_markdown_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            write_json(run_dir / "run.json", {"run_id": "run_missing"})

            self.assertIsNone(get_run_artifact_markdown(run_dir, "code_generation"))


if __name__ == "__main__":
    unittest.main()

