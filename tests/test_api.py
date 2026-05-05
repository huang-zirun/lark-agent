from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from devflow.api import DevFlowApiHandler, create_server, OPENAPI_SPEC


@pytest.fixture
def api_out_dir():
    out_dir = Path(__file__).resolve().parents[1] / "tmp" / "api-tests" / uuid4().hex / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


@pytest.fixture
def server(api_out_dir):
    api_out_dir.mkdir(parents=True, exist_ok=True)
    srv = create_server(host="127.0.0.1", port=0, out_dir=api_out_dir)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield srv, port
    srv.shutdown()


import urllib.request
import urllib.error


def _base_url(port):
    return f"http://127.0.0.1:{port}"


def _get(port, path):
    req = urllib.request.Request(f"{_base_url(port)}{path}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


def _post(port, path, body=None):
    data = json.dumps(body or {}).encode("utf-8") if body else b"{}"
    req = urllib.request.Request(
        f"{_base_url(port)}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


def _delete(port, path):
    req = urllib.request.Request(f"{_base_url(port)}{path}", method="DELETE")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


class TestOpenApi:
    def test_openapi_spec_returned(self, server):
        srv, port = server
        body, status = _get(port, "/api/v1/openapi.json")
        assert status == 200
        assert body["openapi"] == "3.0.3"
        assert "/api/v1/pipelines" in body["paths"]
        assert "/api/v1/pipelines/{run_id}" in body["paths"]
        assert "/api/v1/pipelines/{run_id}/checkpoint" in body["paths"]
        assert "/api/v1/pipelines/{run_id}/pause" in body["paths"]
        assert "/api/v1/pipelines/{run_id}/resume" in body["paths"]
        assert "/api/v1/pipelines/{run_id}/trigger" in body["paths"]


class TestPipelineCrud:
    def test_list_pipelines_empty(self, server):
        srv, port = server
        body, status = _get(port, "/api/v1/pipelines")
        assert status == 200
        assert body["runs"] == []
        assert body["total"] == 0

    def test_create_pipeline(self, server):
        srv, port = server
        body, status = _post(port, "/api/v1/pipelines", {
            "requirement_text": "实现一个贪吃蛇游戏",
        })
        assert status == 201
        assert body["status"] == "created"
        assert body["detected_input"]["kind"] == "inline_text"
        assert body["detected_input"]["value"] == "实现一个贪吃蛇游戏"
        assert "run_id" in body
        assert len(body["stages"]) == 6

    def test_create_pipeline_with_custom_stages(self, server):
        srv, port = server
        body, status = _post(port, "/api/v1/pipelines", {
            "requirement_text": "测试需求",
            "stages": ["requirement_intake", "solution_design"],
        })
        assert status == 201
        assert len(body["stages"]) == 2
        assert body["stages"][0]["name"] == "requirement_intake"
        assert body["stages"][1]["name"] == "solution_design"
        assert body["pipeline_config"]["template"] == "inline"

    def test_create_pipeline_rejects_invalid_custom_stage(self, server):
        srv, port = server
        try:
            _post(port, "/api/v1/pipelines", {
                "requirement_text": "测试需求",
                "stages": ["requirement_intake", "magic_stage"],
            })
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read().decode("utf-8"))
            assert "不支持的流水线阶段" in body["error"]

    def test_create_pipeline_empty_requirement(self, server):
        srv, port = server
        try:
            _post(port, "/api/v1/pipelines", {"requirement_text": ""})
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read().decode("utf-8"))
            assert "requirement_text" in body["error"]

    def test_get_pipeline(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {
            "requirement_text": "测试需求",
        })
        run_id = created["run_id"]
        body, status = _get(port, f"/api/v1/pipelines/{run_id}")
        assert status == 200
        assert body["run_id"] == run_id

    def test_get_pipeline_not_found(self, server):
        srv, port = server
        try:
            _get(port, "/api/v1/pipelines/nonexistent")
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_list_pipelines_after_create(self, server):
        srv, port = server
        _post(port, "/api/v1/pipelines", {"requirement_text": "需求1"})
        _post(port, "/api/v1/pipelines", {"requirement_text": "需求2"})
        body, status = _get(port, "/api/v1/pipelines")
        assert status == 200
        assert body["total"] == 2

    def test_create_pipeline_with_provider_override(self, server):
        srv, port = server
        body, status = _post(port, "/api/v1/pipelines", {
            "requirement_text": "测试需求",
            "provider": "deepseek",
        })
        assert status == 201
        assert body["provider_override"] == "deepseek"


class TestPipelineLifecycle:
    def test_trigger_pipeline_executes_same_run_id(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {
            "requirement_text": "测试需求",
            "analyzer": "heuristic",
        })
        run_id = created["run_id"]

        def fake_run_pipeline_graph(run_dir, *, entrypoint):
            run_path = run_dir / "run.json"
            payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
            payload["status"] = "success"
            payload["lifecycle_status"] = "success"
            payload["graph_state"] = {"engine": "langgraph", "last_entrypoint": entrypoint}
            payload["requirement_artifact"] = str(run_dir / "requirement.json")
            (run_dir / "requirement.json").write_text("{}", encoding="utf-8")
            run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return payload

        with patch("devflow.api.run_pipeline_graph", side_effect=fake_run_pipeline_graph):
            body, status = _post(port, f"/api/v1/pipelines/{run_id}/trigger")

        assert status == 200
        assert body["run_id"] == run_id
        assert body["graph_state"]["last_entrypoint"] == "trigger"
        assert len(list(api_out_dir.glob("*/run.json"))) == 1

    def test_pause_pipeline(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]
        run_path = api_out_dir / run_id / "run.json"
        payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        payload["status"] = "running"
        run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        body, status = _post(port, f"/api/v1/pipelines/{run_id}/pause")
        assert status == 200
        assert body["status"] == "paused"
        assert body["lifecycle_status"] == "paused"

    def test_resume_pipeline(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]
        run_path = api_out_dir / run_id / "run.json"
        payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        payload["status"] = "paused"
        run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        body, status = _post(port, f"/api/v1/pipelines/{run_id}/resume")
        assert status == 200
        assert body["status"] == "running"
        assert body["lifecycle_status"] == "running"

    def test_terminate_pipeline(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]

        body, status = _delete(port, f"/api/v1/pipelines/{run_id}")
        assert status == 200
        assert body["status"] == "terminated"
        assert body["lifecycle_status"] == "terminated"

    def test_terminate_already_delivered(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]
        run_path = api_out_dir / run_id / "run.json"
        payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        payload["status"] = "delivered"
        run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        try:
            _delete(port, f"/api/v1/pipelines/{run_id}")
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 409

    def test_pause_non_running_pipeline(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]

        try:
            _post(port, f"/api/v1/pipelines/{run_id}/pause")
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 409

    def test_resume_non_paused_pipeline(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]

        try:
            _post(port, f"/api/v1/pipelines/{run_id}/resume")
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 409


class TestCheckpoint:
    def test_get_checkpoint_not_found(self, server):
        srv, port = server
        try:
            _get(port, "/api/v1/pipelines/nonexistent/checkpoint")
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_decide_checkpoint_approve(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]
        run_dir = api_out_dir / run_id

        from devflow.checkpoint import build_solution_review_checkpoint, write_checkpoint
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
        checkpoint = build_solution_review_checkpoint(run_payload, None, None)
        write_checkpoint(run_dir, checkpoint)

        body, status = _post(port, f"/api/v1/pipelines/{run_id}/checkpoint", {
            "decision": "approve",
        })
        assert status == 200
        assert body["checkpoint"]["status"] == "approved"

    def test_decide_checkpoint_reject(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]
        run_dir = api_out_dir / run_id

        from devflow.checkpoint import build_solution_review_checkpoint, write_checkpoint
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
        checkpoint = build_solution_review_checkpoint(run_payload, None, None)
        write_checkpoint(run_dir, checkpoint)

        body, status = _post(port, f"/api/v1/pipelines/{run_id}/checkpoint", {
            "decision": "reject",
            "reason": "方案不合理",
        })
        assert status == 200
        assert body["checkpoint"]["status"] == "rejected"

    def test_decide_checkpoint_invalid_decision(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]
        run_dir = api_out_dir / run_id

        from devflow.checkpoint import build_solution_review_checkpoint, write_checkpoint
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
        checkpoint = build_solution_review_checkpoint(run_payload, None, None)
        write_checkpoint(run_dir, checkpoint)

        try:
            _post(port, f"/api/v1/pipelines/{run_id}/checkpoint", {
                "decision": "maybe",
            })
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_decide_checkpoint_paused_run_is_blocked(self, server, api_out_dir):
        srv, port = server
        created, _ = _post(port, "/api/v1/pipelines", {"requirement_text": "测试需求"})
        run_id = created["run_id"]
        run_dir = api_out_dir / run_id

        from devflow.checkpoint import build_solution_review_checkpoint, write_checkpoint
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
        checkpoint = build_solution_review_checkpoint(run_payload, None, None)
        write_checkpoint(run_dir, checkpoint)
        run_payload["status"] = "paused"
        run_payload["lifecycle_status"] = "paused"
        (run_dir / "run.json").write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        try:
            _post(port, f"/api/v1/pipelines/{run_id}/checkpoint", {"decision": "approve"})
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 409


class TestRouteNotFound:
    def test_unknown_route(self, server):
        srv, port = server
        try:
            _get(port, "/api/v1/unknown")
            assert False, "Expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 404
