from __future__ import annotations

import json
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

from devflow.checkpoint import apply_checkpoint_decision, load_checkpoint, write_checkpoint
from devflow.config import ConfigError, DevflowConfig, LlmConfig, load_config
from devflow.graph_runner import PipelineLifecycleError, run_pipeline_graph
from devflow.pipeline import (
    STAGE_NAMES,
    PipelineResult,
    approve_checkpoint_run,
    detect_requirement_input,
    initial_stages,
    load_run_payload,
    new_run_id,
    process_bot_event,
    run_code_generation_after_approval,
    run_delivery_after_code_review_approval,
    set_stage_status,
    utc_now,
    write_json,
)
from devflow.pipeline_config import PipelineConfigError, resolve_pipeline_config, stage_names_from_config
from devflow.intake.models import RequirementSource
from devflow.metrics import (
    compute_overview,
    compute_stage_stats,
    compute_token_usage,
    get_active_run,
    get_recent_runs,
    get_run_artifacts,
    get_run_detail,
    get_run_diff,
    get_run_llm_trace,
    get_run_timeline,
    load_all_runs,
)


OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "DevFlow Engine API",
        "description": "AI 驱动的研发流程引擎 RESTful API",
        "version": "1.0.0",
    },
    "paths": {
        "/api/v1/pipelines": {
            "get": {
                "summary": "列出 Pipeline 运行",
                "operationId": "listPipelines",
                "tags": ["Pipeline"],
                "parameters": [
                    {"name": "status", "in": "query", "schema": {"type": "string"}, "description": "按状态筛选"},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}, "description": "返回数量上限"},
                ],
                "responses": {"200": {"description": "Pipeline 运行列表"}},
            },
            "post": {
                "summary": "创建 Pipeline 运行",
                "operationId": "createPipeline",
                "tags": ["Pipeline"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["requirement_text"],
                                "properties": {
                                    "requirement_text": {"type": "string", "description": "需求文本"},
                                    "analyzer": {"type": "string", "enum": ["llm", "heuristic"], "default": "llm"},
                                    "model": {"type": "string", "default": "heuristic-local-v1"},
                                    "provider": {"type": "string", "description": "LLM Provider 覆盖"},
                                    "stages": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "自定义阶段列表",
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Pipeline 运行已创建"}},
            },
        },
        "/api/v1/pipelines/{run_id}": {
            "get": {
                "summary": "查询 Pipeline 运行状态",
                "operationId": "getPipeline",
                "tags": ["Pipeline"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "Pipeline 运行详情"}, "404": {"description": "未找到"}},
            },
            "delete": {
                "summary": "终止 Pipeline 运行",
                "operationId": "terminatePipeline",
                "tags": ["Pipeline"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "已终止"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/pipelines/{run_id}/trigger": {
            "post": {
                "summary": "触发 Pipeline 执行",
                "operationId": "triggerPipeline",
                "tags": ["Pipeline"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "已触发"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/pipelines/{run_id}/pause": {
            "post": {
                "summary": "暂停 Pipeline 运行",
                "operationId": "pausePipeline",
                "tags": ["Pipeline"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "已暂停"}, "404": {"description": "未找到"}, "409": {"description": "当前状态不允许暂停"}},
            },
        },
        "/api/v1/pipelines/{run_id}/resume": {
            "post": {
                "summary": "恢复 Pipeline 运行",
                "operationId": "resumePipeline",
                "tags": ["Pipeline"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "已恢复"}, "404": {"description": "未找到"}, "409": {"description": "当前状态不允许恢复"}},
            },
        },
        "/api/v1/pipelines/{run_id}/checkpoint": {
            "get": {
                "summary": "查询检查点状态",
                "operationId": "getCheckpoint",
                "tags": ["Checkpoint"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "检查点详情"}, "404": {"description": "未找到"}},
            },
            "post": {
                "summary": "操作检查点（approve/reject）",
                "operationId": "decideCheckpoint",
                "tags": ["Checkpoint"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["decision"],
                                "properties": {
                                    "decision": {"type": "string", "enum": ["approve", "reject"]},
                                    "reason": {"type": "string", "description": "Reject 理由"},
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "决策已记录"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/metrics/overview": {
            "get": {
                "summary": "运行概览统计",
                "operationId": "getMetricsOverview",
                "tags": ["Metrics"],
                "responses": {"200": {"description": "概览统计 JSON"}},
            },
        },
        "/api/v1/metrics/stage-stats": {
            "get": {
                "summary": "阶段耗时统计",
                "operationId": "getMetricsStageStats",
                "tags": ["Metrics"],
                "responses": {"200": {"description": "阶段统计 JSON"}},
            },
        },
        "/api/v1/metrics/token-usage": {
            "get": {
                "summary": "Token 消耗趋势",
                "operationId": "getMetricsTokenUsage",
                "tags": ["Metrics"],
                "responses": {"200": {"description": "Token 使用 JSON"}},
            },
        },
        "/api/v1/metrics/recent-runs": {
            "get": {
                "summary": "最近运行列表",
                "operationId": "getMetricsRecentRuns",
                "tags": ["Metrics"],
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20}, "description": "返回数量上限"},
                ],
                "responses": {"200": {"description": "最近运行列表 JSON"}},
            },
        },
        "/api/v1/metrics/runs/{run_id}/timeline": {
            "get": {
                "summary": "运行时间线",
                "operationId": "getMetricsRunTimeline",
                "tags": ["Metrics"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "时间线 JSON"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/metrics/active-run": {
            "get": {
                "summary": "获取活跃运行",
                "operationId": "getMetricsActiveRun",
                "tags": ["Metrics"],
                "responses": {"200": {"description": "活跃运行 JSON 或 null"}},
            },
        },
        "/api/v1/metrics/runs/{run_id}/detail": {
            "get": {
                "summary": "获取运行完整详情",
                "operationId": "getMetricsRunDetail",
                "tags": ["Metrics"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "运行详情 JSON"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/metrics/runs/{run_id}/llm-trace": {
            "get": {
                "summary": "获取运行 LLM 推理链",
                "operationId": "getMetricsRunLlmTrace",
                "tags": ["Metrics"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "LLM 推理链 JSON"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/metrics/runs/{run_id}/artifacts": {
            "get": {
                "summary": "获取运行产物列表",
                "operationId": "getMetricsRunArtifacts",
                "tags": ["Metrics"],
                "parameters": [{"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "产物摘要 JSON"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/metrics/runs/{run_id}/diff": {
            "get": {
                "summary": "获取 Diff 内容",
                "operationId": "getMetricsRunDiff",
                "tags": ["Metrics"],
                "parameters": [
                    {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["code", "test", "delivery"]}, "description": "Diff 类型"},
                ],
                "responses": {"200": {"description": "Diff 文本内容"}, "404": {"description": "未找到"}},
            },
        },
        "/api/v1/openapi.json": {
            "get": {
                "summary": "OpenAPI 规范文档",
                "operationId": "getOpenApi",
                "tags": ["Meta"],
                "responses": {"200": {"description": "OpenAPI 3.0.3 JSON"}},
            },
        },
        "/docs": {
            "get": {
                "summary": "Swagger UI 交互式文档",
                "operationId": "getSwaggerUI",
                "tags": ["Meta"],
                "responses": {"200": {"description": "Swagger UI HTML 页面"}},
            },
        },
        "/redoc": {
            "get": {
                "summary": "ReDoc 交互式文档",
                "operationId": "getReDoc",
                "tags": ["Meta"],
                "responses": {"200": {"description": "ReDoc HTML 页面"}},
            },
        },
    },
}


SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DevFlow Engine API - Swagger UI</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.20.1/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.20.1/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.20.1/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "/api/v1/openapi.json",
        dom_id: '#swagger-ui',
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "StandaloneLayout",
        docExpansion: "list",
        defaultModelsExpandDepth: 1,
        defaultModelExpandDepth: 1,
        displayRequestDuration: true,
        filter: true,
        tryItOutEnabled: true,
      });
    };
  </script>
</body>
</html>"""

REDOC_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DevFlow Engine API - ReDoc</title>
  <style>body { margin: 0; padding: 0; }</style>
</head>
<body>
  <div id="redoc-container"></div>
  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
  <script>
    Redoc.init(
      '/api/v1/openapi.json',
      {
        scrollYOffset: 50,
        hideDownloadButton: false,
        expandResponses: "200,201",
        pathInMiddlePanel: true,
        theme: {
          colors: { primary: { main: '#1890ff' } }
        }
      },
      document.getElementById('redoc-container')
    );
  </script>
</body>
</html>"""


_ROUTE_PATTERNS: list[tuple[str, str]] = [
    ("GET", r"^/api/v1/pipelines$"),
    ("POST", r"^/api/v1/pipelines$"),
    ("GET", r"^/api/v1/pipelines/([^/]+)$"),
    ("DELETE", r"^/api/v1/pipelines/([^/]+)$"),
    ("POST", r"^/api/v1/pipelines/([^/]+)/trigger$"),
    ("POST", r"^/api/v1/pipelines/([^/]+)/pause$"),
    ("POST", r"^/api/v1/pipelines/([^/]+)/resume$"),
    ("GET", r"^/api/v1/pipelines/([^/]+)/checkpoint$"),
    ("POST", r"^/api/v1/pipelines/([^/]+)/checkpoint$"),
    ("GET", r"^/api/v1/metrics/overview$"),
    ("GET", r"^/api/v1/metrics/stage-stats$"),
    ("GET", r"^/api/v1/metrics/token-usage$"),
    ("GET", r"^/api/v1/metrics/recent-runs$"),
    ("GET", r"^/api/v1/metrics/runs/([^/]+)/timeline$"),
    ("GET", r"^/api/v1/metrics/active-run$"),
    ("GET", r"^/api/v1/metrics/runs/([^/]+)/detail$"),
    ("GET", r"^/api/v1/metrics/runs/([^/]+)/llm-trace$"),
    ("GET", r"^/api/v1/metrics/runs/([^/]+)/artifacts$"),
    ("GET", r"^/api/v1/metrics/runs/([^/]+)/diff$"),
    ("GET", r"^/dashboard$"),
    ("GET", r"^/dashboard/assets/(.+)$"),
    ("GET", r"^/api/v1/openapi\.json$"),
    ("GET", r"^/docs$"),
    ("GET", r"^/redoc$"),
]


class DevFlowApiHandler(BaseHTTPRequestHandler):
    out_dir: Path = Path("artifacts/runs")

    def log_message(self, format, *args):
        pass

    def _json_response(self, status: int, body: Any) -> None:
        payload = json.dumps(body, ensure_ascii=False, indent=2)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(payload.encode("utf-8"))

    def _html_response(self, html: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _resolve_route(self, method: str) -> tuple[str, list[str]] | None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        for pattern_method, pattern in _ROUTE_PATTERNS:
            if method != pattern_method:
                continue
            m = re.match(pattern, path)
            if m is not None:
                return pattern, list(m.groups())
        return None

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        result = self._resolve_route(method)
        if result is None:
            self._json_response(404, {"error": "未找到路由"})
            return
        pattern, groups = result

        if pattern == r"^/api/v1/openapi\.json$":
            self._json_response(200, OPENAPI_SPEC)
            return

        if pattern == r"^/api/v1/pipelines$" and method == "GET":
            self._handle_list_pipelines()
            return
        if pattern == r"^/api/v1/pipelines$" and method == "POST":
            self._handle_create_pipeline()
            return

        run_id = groups[0] if groups else ""

        if pattern == r"^/api/v1/pipelines/([^/]+)$" and method == "GET":
            self._handle_get_pipeline(run_id)
            return
        if pattern == r"^/api/v1/pipelines/([^/]+)$" and method == "DELETE":
            self._handle_terminate_pipeline(run_id)
            return
        if pattern == r"^/api/v1/pipelines/([^/]+)/trigger$" and method == "POST":
            self._handle_trigger_pipeline(run_id)
            return
        if pattern == r"^/api/v1/pipelines/([^/]+)/pause$" and method == "POST":
            self._handle_pause_pipeline(run_id)
            return
        if pattern == r"^/api/v1/pipelines/([^/]+)/resume$" and method == "POST":
            self._handle_resume_pipeline(run_id)
            return
        if pattern == r"^/api/v1/pipelines/([^/]+)/checkpoint$" and method == "GET":
            self._handle_get_checkpoint(run_id)
            return
        if pattern == r"^/api/v1/pipelines/([^/]+)/checkpoint$" and method == "POST":
            self._handle_decide_checkpoint(run_id)
            return

        if pattern == r"^/api/v1/metrics/overview$" and method == "GET":
            self._handle_metrics_overview()
            return
        if pattern == r"^/api/v1/metrics/stage-stats$" and method == "GET":
            self._handle_metrics_stage_stats()
            return
        if pattern == r"^/api/v1/metrics/token-usage$" and method == "GET":
            self._handle_metrics_token_usage()
            return
        if pattern == r"^/api/v1/metrics/recent-runs$" and method == "GET":
            self._handle_metrics_recent_runs()
            return
        if pattern == r"^/api/v1/metrics/runs/([^/]+)/timeline$" and method == "GET":
            self._handle_metrics_run_timeline(run_id)
            return
        if pattern == r"^/api/v1/metrics/active-run$" and method == "GET":
            self._handle_metrics_active_run()
            return
        if pattern == r"^/api/v1/metrics/runs/([^/]+)/detail$" and method == "GET":
            self._handle_metrics_run_detail(run_id)
            return
        if pattern == r"^/api/v1/metrics/runs/([^/]+)/llm-trace$" and method == "GET":
            self._handle_metrics_run_llm_trace(run_id)
            return
        if pattern == r"^/api/v1/metrics/runs/([^/]+)/artifacts$" and method == "GET":
            self._handle_metrics_run_artifacts(run_id)
            return
        if pattern == r"^/api/v1/metrics/runs/([^/]+)/diff$" and method == "GET":
            self._handle_metrics_run_diff(run_id)
            return
        if pattern == r"^/dashboard$" and method == "GET":
            self._handle_dashboard()
            return
        if pattern == r"^/dashboard/assets/(.+)$" and method == "GET":
            self._handle_dashboard_assets(groups[0])
            return

        if pattern == r"^/docs$" and method == "GET":
            self._html_response(SWAGGER_UI_HTML)
            return
        if pattern == r"^/redoc$" and method == "GET":
            self._html_response(REDOC_HTML)
            return

        self._json_response(404, {"error": "未找到路由"})

    def _handle_list_pipelines(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        status_filter = params.get("status", [None])[0]
        limit = int(params.get("limit", ["50"])[0])

        runs: list[dict[str, Any]] = []
        if self.out_dir.exists():
            for run_path in sorted(self.out_dir.glob("*/run.json"), reverse=True)[:limit]:
                try:
                    payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError):
                    continue
                if status_filter and payload.get("status") != status_filter:
                    continue
                runs.append(payload)

        self._json_response(200, {"runs": runs, "total": len(runs)})

    def _handle_create_pipeline(self) -> None:
        body = self._read_body()
        requirement_text = body.get("requirement_text", "").strip()
        if not requirement_text:
            self._json_response(400, {"error": "requirement_text 不能为空"})
            return

        analyzer = body.get("analyzer", "llm")
        model = body.get("model", "heuristic-local-v1")
        custom_stages = body.get("stages")
        pipeline_template = body.get("pipeline_template")
        provider_override = body.get("provider")

        detected = detect_requirement_input(requirement_text)
        source = RequirementSource(
            source_type="api",
            source_id="api-request",
            reference="API 请求",
            title="API 触发需求",
            content=requirement_text,
            identity=None,
            metadata={"source": "api"},
        )

        run_id = new_run_id("api")
        run_dir = self.out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_path = run_dir / "run.json"
        started_at = utc_now()

        try:
            pipeline_config = resolve_pipeline_config(custom_stages, template=pipeline_template)
        except PipelineConfigError as exc:
            self._json_response(400, {"error": str(exc)})
            return

        stage_names = stage_names_from_config(pipeline_config)
        stages = [{"name": name, "status": "pending"} for name in stage_names]

        run_payload: dict[str, Any] = {
            "schema_version": "devflow.pipeline_run.v1",
            "run_id": run_id,
            "status": "created",
            "lifecycle_status": "created",
            "run_dir": str(run_dir),
            "run_path": str(run_path),
            "started_at": started_at,
            "ended_at": None,
            "trigger": {
                "source_type": "api",
                "message_id": None,
                "chat_id": None,
                "sender_id": None,
            },
            "detected_input": {"kind": detected.kind, "value": detected.value},
            "analyzer": analyzer,
            "model": model,
            "stages": stages,
            "pipeline_config": pipeline_config,
            "graph_state": {"engine": "langgraph", "status": "created", "updated_at": started_at},
            "error": None,
            "publication": {"status": "pending"},
        }

        if provider_override:
            run_payload["provider_override"] = provider_override

        write_json(run_path, run_payload)
        self._json_response(201, run_payload)

    def _handle_get_pipeline(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        run_path = run_dir / "run.json"
        if not run_path.exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        self._json_response(200, payload)

    def _handle_terminate_pipeline(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        run_path = run_dir / "run.json"
        if not run_path.exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        current_status = payload.get("status")
        if current_status in ("delivered", "terminated", "failed"):
            self._json_response(409, {"error": f"当前状态 {current_status} 不允许终止"})
            return
        payload["status"] = "terminated"
        payload["lifecycle_status"] = "terminated"
        payload["ended_at"] = utc_now()
        write_json(run_path, payload)
        self._json_response(200, payload)

    def _handle_trigger_pipeline(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        run_path = run_dir / "run.json"
        if not run_path.exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        try:
            updated = run_pipeline_graph(run_dir, entrypoint="trigger")
            self._json_response(200, updated)
        except PipelineLifecycleError as exc:
            self._json_response(409, {"error": str(exc)})
        except Exception as exc:
            self._json_response(500, {"error": str(exc)})

    def _handle_pause_pipeline(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        run_path = run_dir / "run.json"
        if not run_path.exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        current_status = payload.get("status")
        if current_status not in ("running", "success"):
            self._json_response(409, {"error": f"当前状态 {current_status} 不允许暂停"})
            return
        payload["paused_from_status"] = current_status
        payload["status"] = "paused"
        payload["lifecycle_status"] = "paused"
        write_json(run_path, payload)
        self._json_response(200, payload)

    def _handle_resume_pipeline(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        run_path = run_dir / "run.json"
        if not run_path.exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        if payload.get("lifecycle_status") != "paused" and payload.get("status") != "paused":
            self._json_response(409, {"error": f"当前状态 {payload.get('status')} 不允许恢复"})
            return
        payload["status"] = payload.get("paused_from_status") or "running"
        if payload["status"] == "created":
            payload["status"] = "running"
        payload["lifecycle_status"] = payload["status"]
        payload.pop("paused_from_status", None)
        write_json(run_path, payload)
        self._json_response(200, payload)

    def _handle_get_checkpoint(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        checkpoint_path = run_dir / "checkpoint.json"
        if not checkpoint_path.exists():
            self._json_response(404, {"error": f"未找到检查点：{run_id}"})
            return
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
        self._json_response(200, checkpoint)

    def _handle_decide_checkpoint(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        run_path = run_dir / "run.json"
        if not run_path.exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return

        body = self._read_body()
        decision = body.get("decision", "").strip().lower()
        if decision not in ("approve", "reject"):
            self._json_response(400, {"error": "decision 必须为 approve 或 reject"})
            return

        reason = body.get("reason")
        run_payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        lifecycle_status = run_payload.get("lifecycle_status") or run_payload.get("status")
        if lifecycle_status in {"paused", "terminated"}:
            self._json_response(409, {"error": f"当前状态 {lifecycle_status} 不允许操作检查点"})
            return
        try:
            current_checkpoint = load_checkpoint(run_dir)
        except (OSError, json.JSONDecodeError):
            self._json_response(404, {"error": "未找到检查点"})
            return

        checkpoint = apply_checkpoint_decision(
            run_dir,
            decision,
            reason=reason,
            reviewer={"source": "api"},
        )

        run_payload = load_run_payload(run_dir)
        run_payload["checkpoint_status"] = checkpoint["status"]
        run_payload["checkpoint_artifact"] = str(run_dir / "checkpoint.json")
        write_json(run_path, run_payload)

        try:
            if checkpoint["status"] == "approved" and current_checkpoint.get("stage") != "code_review":
                run_payload = run_pipeline_graph(run_dir, entrypoint="solution_approved", checkpoint=checkpoint)
            elif checkpoint["status"] == "approved":
                run_payload = run_pipeline_graph(run_dir, entrypoint="code_review_approved", checkpoint=checkpoint)
            else:
                write_json(run_path, run_payload)
        except PipelineLifecycleError as exc:
            self._json_response(409, {"error": str(exc)})
            return

        self._json_response(200, {"checkpoint": checkpoint, "run": run_payload})

    def _handle_metrics_overview(self) -> None:
        runs = load_all_runs(self.out_dir)
        overview = compute_overview(runs)
        self._json_response(200, overview)

    def _handle_metrics_stage_stats(self) -> None:
        runs = load_all_runs(self.out_dir)
        stats = compute_stage_stats(runs)
        self._json_response(200, {"stage_stats": stats})

    def _handle_metrics_token_usage(self) -> None:
        usage = compute_token_usage(self.out_dir)
        self._json_response(200, {"token_usage": usage})

    def _handle_metrics_recent_runs(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        limit = int(params.get("limit", ["20"])[0])
        runs = load_all_runs(self.out_dir)
        recent = get_recent_runs(runs, limit=limit)
        self._json_response(200, {"runs": recent})

    def _handle_metrics_run_timeline(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        if not (run_dir / "run.json").exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        timeline = get_run_timeline(run_dir)
        self._json_response(200, {"timeline": timeline})

    def _handle_metrics_active_run(self) -> None:
        active = get_active_run(self.out_dir)
        self._json_response(200, active if active else None)

    def _handle_metrics_run_detail(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        if not (run_dir / "run.json").exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        detail = get_run_detail(run_dir)
        self._json_response(200, detail)

    def _handle_metrics_run_llm_trace(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        if not (run_dir / "run.json").exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        trace = get_run_llm_trace(run_dir)
        self._json_response(200, {"llm_trace": trace})

    def _handle_metrics_run_artifacts(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        if not (run_dir / "run.json").exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        artifacts = get_run_artifacts(run_dir)
        self._json_response(200, {"artifacts": artifacts})

    def _handle_metrics_run_diff(self, run_id: str) -> None:
        run_dir = self.out_dir / run_id
        if not (run_dir / "run.json").exists():
            self._json_response(404, {"error": f"未找到运行：{run_id}"})
            return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        diff_type = params.get("type", ["code"])[0]
        content = get_run_diff(run_dir, diff_type)
        if content is None:
            self._json_response(404, {"error": f"未找到 Diff：{diff_type}"})
            return
        self._json_response(200, {"type": diff_type, "content": content})

    def _handle_dashboard(self) -> None:
        dist_dir = Path(__file__).parent / "dashboard" / "dist"
        index_path = dist_dir / "index.html"
        if not index_path.exists():
            self._json_response(503, {"error": "仪表板未构建，请先运行 npm run build"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(index_path.read_bytes())

    def _handle_dashboard_assets(self, filepath: str) -> None:
        dist_dir = Path(__file__).parent / "dashboard" / "dist"
        asset_path = dist_dir / "assets" / filepath
        try:
            asset_path.resolve().relative_to(dist_dir.resolve())
        except ValueError:
            self._json_response(403, {"error": "禁止访问"})
            return
        if not asset_path.exists():
            self._json_response(404, {"error": "未找到资源"})
            return
        content_type = "application/javascript"
        if filepath.endswith(".css"):
            content_type = "text/css"
        elif filepath.endswith(".png"):
            content_type = "image/png"
        elif filepath.endswith(".svg"):
            content_type = "image/svg+xml"
        elif filepath.endswith(".woff2"):
            content_type = "font/woff2"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(asset_path.read_bytes())


def _make_overridden_llm_config(base: LlmConfig, provider: str) -> LlmConfig:
    return LlmConfig(
        provider=provider,
        api_key=base.api_key,
        model=base.model,
        base_url=base.base_url,
        temperature=base.temperature,
        max_tokens=base.max_tokens,
        timeout_seconds=base.timeout_seconds,
        response_format_json=base.response_format_json,
    )


def create_server(host: str = "127.0.0.1", port: int = 8080, out_dir: Path | str | None = None) -> HTTPServer:
    out = Path(out_dir) if out_dir else Path("artifacts/runs")
    DevFlowApiHandler.out_dir = out
    server = HTTPServer((host, port), DevFlowApiHandler)
    return server


def run_server(host: str = "127.0.0.1", port: int = 8080, out_dir: Path | str | None = None) -> None:
    server = create_server(host, port, out_dir)
    print(f"DevFlow API 服务器：http://{host}:{port}")
    print(f"Swagger UI：http://{host}:{port}/docs")
    print(f"ReDoc：http://{host}:{port}/redoc")
    print(f"控制台：http://{host}:{port}/dashboard")
    print(f"OpenAPI JSON：http://{host}:{port}/api/v1/openapi.json")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
