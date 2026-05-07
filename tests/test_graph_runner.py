from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from devflow.config import DevflowConfig, LarkConfig, LlmConfig
from devflow.graph_runner import PipelineLifecycleError, run_pipeline_graph
from devflow.pipeline import initial_stages, new_run_id, utc_now, write_json


TEST_TMP_ROOT = Path(__file__).resolve().parents[1] / "tmp" / "graph-runner-tests"


def make_run_root() -> Path:
    root = TEST_TMP_ROOT / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class GraphRunnerTests(unittest.TestCase):
    def test_trigger_runs_requirement_intake_on_same_run_and_records_graph_state(self) -> None:
        run_root = make_run_root()
        run_dir = run_root / new_run_id("api")
        run_dir.mkdir()
        run_path = run_dir / "run.json"
        write_json(
            run_path,
            {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_dir.name,
                "status": "created",
                "lifecycle_status": "created",
                "run_dir": str(run_dir),
                "run_path": str(run_path),
                "started_at": utc_now(),
                "ended_at": None,
                "trigger": {"source_type": "api"},
                "detected_input": {"kind": "inline_text", "value": "实现一个登录页"},
                
                
                "stages": initial_stages(),
                "error": None,
                "publication": {"status": "pending"},
            },
        )

        result = run_pipeline_graph(run_dir, entrypoint="trigger")
        updated = json.loads(run_path.read_text(encoding="utf-8-sig"))

        self.assertEqual(result["run_id"], run_dir.name)
        self.assertEqual(updated["run_id"], run_dir.name)
        self.assertEqual(updated["stages"][0]["status"], "success")
        self.assertTrue((run_dir / "requirement.json").exists())
        self.assertEqual(updated["graph_state"]["engine"], "langgraph")
        self.assertEqual(updated["graph_state"]["last_entrypoint"], "trigger")

    def test_provider_override_is_applied_to_llm_requirement_intake(self) -> None:
        seen_providers: list[str] = []

        def fake_build_artifact(source, *, llm_config=None, stage_trace=None):
            seen_providers.append(llm_config.provider)
            return {
                "schema_version": "devflow.requirement.v1",
                "metadata": {"title": "API 需求"},
                "normalized_requirement": {"title": "API 需求"},
                "quality": {"ready_for_next_stage": True},
            }

        fake_config = DevflowConfig(
            llm=LlmConfig(provider="ark", api_key="SECRET", model="test-model"),
            lark=LarkConfig(cli_version="1.0.23", app_id="", app_secret="", test_doc=""),
        )
        run_root = make_run_root()
        run_dir = run_root / new_run_id("api")
        run_dir.mkdir()
        run_path = run_dir / "run.json"
        write_json(
            run_path,
            {
                "schema_version": "devflow.pipeline_run.v1",
                "run_id": run_dir.name,
                "status": "created",
                "lifecycle_status": "created",
                "run_dir": str(run_dir),
                "run_path": str(run_path),
                "started_at": utc_now(),
                "ended_at": None,
                "trigger": {"source_type": "api"},
                "detected_input": {"kind": "inline_text", "value": "实现 API"},
                
                
                "provider_override": "deepseek",
                "stages": initial_stages(),
                "error": None,
                "publication": {"status": "pending"},
            },
        )

        with patch("devflow.graph_runner.load_config", return_value=fake_config):
            with patch("devflow.graph_runner.build_requirement_artifact", side_effect=fake_build_artifact):
                with patch("devflow.graph_runner.maybe_run_solution_design", return_value=None):
                    run_pipeline_graph(run_dir, entrypoint="trigger")

        self.assertEqual(seen_providers, ["deepseek"])

    def test_paused_and_terminated_runs_do_not_execute(self) -> None:
        for status in ("paused", "terminated"):
            with self.subTest(status=status):
                run_root = make_run_root()
                run_dir = run_root / new_run_id("api")
                run_dir.mkdir()
                run_path = run_dir / "run.json"
                write_json(
                    run_path,
                    {
                        "schema_version": "devflow.pipeline_run.v1",
                        "run_id": run_dir.name,
                        "status": status,
                        "lifecycle_status": status,
                        "run_dir": str(run_dir),
                        "run_path": str(run_path),
                        "detected_input": {"kind": "inline_text", "value": "需求"},
                        "stages": initial_stages(),
                    },
                )

                with self.assertRaises(PipelineLifecycleError):
                    run_pipeline_graph(run_dir, entrypoint="trigger")
