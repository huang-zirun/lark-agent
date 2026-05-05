from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError:  # pragma: no cover - exercised only before dependency install
    END = "__end__"

    class StateGraph:
        def __init__(self, _state_type):
            self._nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
            self._entry: str | None = None
            self._edges: dict[str, str] = {}

        def add_node(self, name: str, func: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
            self._nodes[name] = func

        def set_entry_point(self, name: str) -> None:
            self._entry = name

        def add_edge(self, start: str, end: str) -> None:
            self._edges[start] = end

        def compile(self):
            graph = self

            class _CompiledGraph:
                def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
                    if graph._entry is None:
                        raise RuntimeError("LangGraph 入口点缺失。")
                    current = graph._entry
                    current_state = state
                    while current != END:
                        current_state = graph._nodes[current](current_state)
                        current = graph._edges.get(current, END)
                    return current_state

            return _CompiledGraph()

from devflow.code.agent import QualityGateError
from devflow.config import DevflowConfig, LlmConfig, load_config
from devflow.intake.analyzer import build_requirement_artifact
from devflow.intake.models import RequirementSource
from devflow.intake.output import write_artifact
from devflow.pipeline import (
    build_audit_payload,
    load_run_payload,
    maybe_run_solution_design,
    run_code_generation_after_approval,
    run_delivery_after_code_review_approval,
    send_stage_notification,
    set_stage_status,
    stage_status,
    utc_now,
    write_json,
)
from devflow.pipeline_config import resolve_pipeline_config, stage_names_from_config
from devflow.trace import RunTrace


class PipelineLifecycleError(ValueError):
    """Raised when a run is paused, terminated, or otherwise not executable."""


class PipelineGraphError(RuntimeError):
    """Raised when the graph runner cannot continue a run."""


def run_pipeline_graph(
    run_dir: Path | str,
    *,
    entrypoint: str,
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_path = Path(run_dir) / "run.json"
    run_payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
    _assert_executable(run_payload, entrypoint=entrypoint)
    graph = _compile_graph(entrypoint)
    state = graph.invoke(
        {
            "run_dir": str(run_dir),
            "entrypoint": entrypoint,
            "checkpoint": checkpoint,
        }
    )
    updated = load_run_payload(Path(run_dir))
    updated["graph_state"] = {
        "engine": "langgraph",
        "last_entrypoint": entrypoint,
        "last_node": state.get("last_node"),
        "updated_at": utc_now(),
    }
    if updated.get("status") not in {"paused", "terminated"}:
        updated["lifecycle_status"] = updated.get("status", "running")
    write_json(Path(run_dir) / "run.json", updated)
    return updated


def load_config_for_run(
    run_payload: dict[str, Any],
    *,
    require_llm_api_key: bool = False,
    require_llm_model: bool = False,
) -> DevflowConfig:
    loader = load_config
    try:
        import devflow.pipeline as pipeline_module

        if getattr(pipeline_module, "load_config", loader) is not loader:
            loader = pipeline_module.load_config
    except Exception:
        pass
    config = loader(
        require_llm_api_key=require_llm_api_key,
        require_llm_model=require_llm_model,
    )
    provider = run_payload.get("provider_override")
    if not isinstance(provider, str) or not provider.strip():
        return config
    return replace(config, llm=replace(config.llm, provider=provider.strip()))


def _compile_graph(entrypoint: str):
    if entrypoint not in {"trigger", "solution_approved", "code_review_approved"}:
        raise PipelineGraphError(f"不支持的图入口：{entrypoint}。")

    graph = StateGraph(dict)
    graph.add_node("trigger", _trigger_node)
    graph.add_node("solution_approved", _solution_approved_node)
    graph.add_node("code_review_approved", _code_review_approved_node)
    graph.set_entry_point(entrypoint)
    graph.add_edge(entrypoint, END)
    return graph.compile()


def _trigger_node(state: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(state["run_dir"])
    run_path = run_dir / "run.json"
    run_payload = load_run_payload(run_dir)
    _ensure_pipeline_config(run_payload)

    source = _api_requirement_source(run_payload)
    trace = RunTrace(run_payload["run_id"], run_dir)
    stage_trace = trace.stage("requirement_intake")
    started_at = utc_now()
    set_stage_status(run_payload["stages"], "requirement_intake", "running", started_at=started_at)
    run_payload["status"] = "running"
    run_payload["lifecycle_status"] = "running"
    write_json(run_path, run_payload)

    analyzer = str(run_payload.get("analyzer") or "llm")
    model = str(run_payload.get("model") or "heuristic-local-v1")
    if analyzer == "heuristic":
        artifact = build_requirement_artifact(source, model=model, analyzer="heuristic", stage_trace=stage_trace)
    else:
        config = load_config_for_run(run_payload, require_llm_api_key=True, require_llm_model=True)
        artifact = build_requirement_artifact(source, analyzer="llm", llm_config=config.llm, stage_trace=stage_trace)

    requirement_path = run_dir / "requirement.json"
    write_artifact(artifact, requirement_path)
    ended_at = utc_now()
    set_stage_status(
        run_payload["stages"],
        "requirement_intake",
        "success",
        ended_at=ended_at,
        artifact=str(requirement_path),
    )
    run_payload["status"] = "success"
    run_payload["lifecycle_status"] = "success"
    run_payload["ended_at"] = ended_at
    run_payload["requirement_artifact"] = str(requirement_path)
    run_payload["requirement_title"] = (
        artifact.get("normalized_requirement", {}).get("title")
        if isinstance(artifact.get("normalized_requirement"), dict)
        else None
    )
    quality = artifact.get("quality") if isinstance(artifact.get("quality"), dict) else {}
    run_payload["ready_for_next_stage"] = quality.get("ready_for_next_stage")
    run_payload["audit"] = build_audit_payload(trace, run_dir)
    write_json(run_path, run_payload)

    if analyzer == "llm" and _stage_enabled(run_payload, "solution_design"):
        config = load_config_for_run(run_payload, require_llm_api_key=True, require_llm_model=True)
        with _patched_pipeline_config(config):
            maybe_run_solution_design(
                artifact,
                requirement_path,
                source,
                analyzer=analyzer,
                run_dir=run_dir,
                stages=run_payload["stages"],
                trace=trace,
                run_payload=run_payload,
                message_id="api",
                card_reply_sender=_noop_card_reply,
            )
        write_json(run_path, run_payload)

    state["last_node"] = "requirement_intake"
    return state


def _solution_approved_node(state: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(state["run_dir"])
    run_payload = load_run_payload(run_dir)
    _ensure_pipeline_config(run_payload)
    config = load_config_for_run(run_payload, require_llm_api_key=True, require_llm_model=True)
    with _patched_pipeline_config(config):
        try:
            run_code_generation_after_approval(run_dir, run_payload)
        except QualityGateError as exc:
            run_payload["status"] = "failed"
            run_payload["lifecycle_status"] = "failed"
            run_payload["ended_at"] = utc_now()
            run_payload["error"] = {
                "stage": "code_generation",
                "message": str(exc),
                "reasons": exc.reasons,
                "quality_snapshot": exc.quality_snapshot,
            }
    write_json(run_dir / "run.json", run_payload)
    state["last_node"] = "solution_approved"
    return state


def _code_review_approved_node(state: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(state["run_dir"])
    run_payload = load_run_payload(run_dir)
    _ensure_pipeline_config(run_payload)
    run_delivery_after_code_review_approval(run_dir, run_payload, state.get("checkpoint"))
    state["last_node"] = "code_review_approved"
    return state


def _assert_executable(run_payload: dict[str, Any], *, entrypoint: str) -> None:
    status = str(run_payload.get("lifecycle_status") or run_payload.get("status") or "")
    if status == "paused":
        raise PipelineLifecycleError("流水线已暂停，请先恢复后再继续执行。")
    if status == "terminated":
        raise PipelineLifecycleError("流水线已终止，不能继续执行。")
    if entrypoint == "trigger" and status not in {"", "created", "running"}:
        raise PipelineLifecycleError(f"当前状态 {status} 不允许触发执行。")
    if entrypoint != "trigger" and status in {"failed", "delivered"}:
        raise PipelineLifecycleError(f"当前状态 {status} 不允许继续执行。")


def _ensure_pipeline_config(run_payload: dict[str, Any]) -> None:
    config = run_payload.get("pipeline_config")
    if not isinstance(config, dict):
        config = resolve_pipeline_config(None)
        run_payload["pipeline_config"] = config
    configured_names = stage_names_from_config(config)
    existing_names = [stage.get("name") for stage in run_payload.get("stages", []) if isinstance(stage, dict)]
    if existing_names != configured_names:
        run_payload["stages"] = [{"name": name, "status": "pending"} for name in configured_names]


def _stage_enabled(run_payload: dict[str, Any], name: str) -> bool:
    return stage_status(run_payload.get("stages", []), name) is not None


def _api_requirement_source(run_payload: dict[str, Any]) -> RequirementSource:
    detected = run_payload.get("detected_input") if isinstance(run_payload.get("detected_input"), dict) else {}
    content = str(detected.get("value") or "").strip()
    if not content:
        raise PipelineGraphError("需求文本为空，无法触发流水线。")
    return RequirementSource(
        source_type="api",
        source_id=run_payload["run_id"],
        reference="API 请求",
        title="API 触发需求",
        content=content,
        identity=None,
        metadata={"source": "api"},
    )


def _noop_card_reply(message_id: str, card: dict[str, Any], idempotency_key: str) -> None:
    return None


@contextmanager
def _patched_pipeline_config(config: DevflowConfig):
    import devflow.pipeline as pipeline_module

    original = pipeline_module.load_config

    def _load_config(*args, **kwargs):
        return config

    pipeline_module.load_config = _load_config
    try:
        yield
    finally:
        pipeline_module.load_config = original
