from __future__ import annotations

from typing import Any


class PipelineConfigError(ValueError):
    """Raised when a pipeline template cannot be executed safely."""


DEFAULT_STAGE_SEQUENCE = [
    "requirement_intake",
    "solution_design",
    "code_generation",
    "test_generation",
    "code_review",
    "delivery",
]

BUILT_IN_STAGE_AGENTS = {
    "requirement_intake": "requirement_intake",
    "solution_design": "solution_design",
    "code_generation": "code_generation",
    "test_generation": "test_generation",
    "code_review": "code_review",
    "delivery": "delivery",
}


def resolve_pipeline_config(
    stages: list[Any] | dict[str, Any] | None,
    *,
    template: str | None = None,
) -> dict[str, Any]:
    if stages is None:
        if template not in (None, "", "default"):
            raise PipelineConfigError(f"不支持的流水线模板：{template}。")
        stage_specs: list[Any] = list(DEFAULT_STAGE_SEQUENCE)
        template_name = "default"
    elif isinstance(stages, dict):
        template_name = _string(stages.get("template")) or template or "inline"
        stage_specs = _stage_list(stages.get("stages"))
    else:
        template_name = template or "inline"
        stage_specs = _stage_list(stages)

    normalized = _normalize_stages(stage_specs)
    _validate_dependencies(normalized)
    return {
        "schema_version": "devflow.pipeline_config.v1",
        "template": template_name,
        "stages": normalized,
    }


def stage_names_from_config(config: dict[str, Any]) -> list[str]:
    stages = config.get("stages")
    if not isinstance(stages, list):
        raise PipelineConfigError("流水线配置缺少 stages 列表。")
    names: list[str] = []
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get("name"), str):
            raise PipelineConfigError("流水线阶段配置必须包含 name。")
        names.append(stage["name"])
    return names


def _normalize_stages(stage_specs: list[Any]) -> list[dict[str, Any]]:
    if not stage_specs:
        raise PipelineConfigError("流水线至少需要一个阶段。")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous_name: str | None = None
    for raw in stage_specs:
        if isinstance(raw, str):
            name = raw.strip()
            agent = BUILT_IN_STAGE_AGENTS.get(name)
            dependencies = [] if previous_name is None else [previous_name]
        elif isinstance(raw, dict):
            name = _string(raw.get("name")) or ""
            agent = _string(raw.get("agent")) or BUILT_IN_STAGE_AGENTS.get(name)
            if "dependencies" in raw:
                dependencies = _string_list(raw.get("dependencies"), field="dependencies")
            else:
                dependencies = [] if previous_name is None else [previous_name]
        else:
            raise PipelineConfigError("流水线阶段必须是字符串或 object。")

        if name not in BUILT_IN_STAGE_AGENTS:
            raise PipelineConfigError(f"不支持的流水线阶段：{name}。")
        if agent not in BUILT_IN_STAGE_AGENTS.values():
            raise PipelineConfigError(f"阶段 {name} 绑定了不支持的 Agent：{agent}。")
        if name in seen:
            raise PipelineConfigError(f"流水线阶段重复：{name}。")

        normalized.append(
            {
                "name": name,
                "agent": agent,
                "dependencies": dependencies,
            }
        )
        seen.add(name)
        previous_name = name
    return normalized


def _validate_dependencies(stages: list[dict[str, Any]]) -> None:
    names = {stage["name"] for stage in stages}
    graph = {stage["name"]: list(stage["dependencies"]) for stage in stages}

    for stage in stages:
        for dependency in stage["dependencies"]:
            if dependency not in names:
                raise PipelineConfigError(
                    f"阶段 {stage['name']} 依赖的阶段不存在：{dependency}。"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise PipelineConfigError("流水线阶段依赖存在循环依赖。")
        visiting.add(name)
        for dependency in graph[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in graph:
        visit(name)


def _stage_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise PipelineConfigError("流水线 stages 必须是数组。")
    return value


def _string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PipelineConfigError(f"流水线字段必须是字符串数组：{field}。")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PipelineConfigError(f"流水线字段必须是字符串数组：{field}。")
        result.append(item.strip())
    return result

