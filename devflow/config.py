from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("config.json")
LOCKED_LARK_CLI_VERSION = "1.0.23"


class ConfigError(ValueError):
    """Raised when local runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class LlmConfig:
    provider: str = "ark"
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    temperature: float = 0.2
    max_tokens: int = 2000
    timeout_seconds: int = 120
    response_format_json: bool = False


@dataclass(frozen=True, slots=True)
class LarkConfig:
    cli_version: str
    app_id: str
    app_secret: str
    test_doc: str
    prd_folder_token: str = ""


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    root: str = ""
    default_repo: str = ""


@dataclass(frozen=True, slots=True)
class ApprovalConfig:
    enabled: bool = False
    definition_code: str = ""
    poll_interval_seconds: int = 60


@dataclass(frozen=True, slots=True)
class SemanticConfig:
    enabled: bool = True
    max_workers: int = 4
    parse_timeout_seconds: int = 10
    max_symbols_per_file: int = 500
    index_dir_name: str = ".devflow-index"


@dataclass(frozen=True, slots=True)
class InteractionConfig:
    default_chat_id: str = ""
    max_queue_size: int = 5
    message_merge_window_seconds: int = 5
    progress_notifications_enabled: bool = True


@dataclass(frozen=True, slots=True)
class DevflowConfig:
    llm: LlmConfig
    lark: LarkConfig
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)
    interaction: InteractionConfig = field(default_factory=InteractionConfig)


def load_config(
    path: Path | str = DEFAULT_CONFIG_PATH,
    *,
    require_llm_api_key: bool = False,
    require_llm_model: bool = False,
    require_lark_credentials: bool = False,
    require_lark_test_doc: bool = False,
    provider_override: str | None = None,
) -> DevflowConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(
            f"未找到配置文件：{config_path}。"
            "请复制 config.example.json 为 config.json，并填写必填字段。"
        )

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是有效的 JSON：{config_path}。") from exc

    if not isinstance(payload, dict):
        raise ConfigError("配置根节点必须是 JSON object。")

    llm_section = _section(payload, "llm")
    lark_section = _section(payload, "lark")
    workspace_section = _section(payload, "workspace")
    approval_section = _section(payload, "approval")
    semantic_section = _section(payload, "semantic")
    interaction_section = _section(payload, "interaction")

    effective_provider = provider_override or _string(llm_section.get("provider")) or "ark"

    import os
    env_override = os.environ.get("DEVFLOW_PROVIDER_OVERRIDE")
    if env_override:
        effective_provider = env_override

    llm = LlmConfig(
        provider=effective_provider,
        api_key=_string(llm_section.get("api_key")) or "",
        model=_string(llm_section.get("model")) or "",
        base_url=_string(llm_section.get("base_url")) or "",
        temperature=_float(llm_section.get("temperature"), 0.2),
        max_tokens=_int(llm_section.get("max_tokens"), 2000),
        timeout_seconds=_int(llm_section.get("timeout_seconds"), 120),
        response_format_json=_bool(llm_section.get("response_format_json"), False),
    )
    lark = LarkConfig(
        cli_version=_string(lark_section.get("cli_version")) or LOCKED_LARK_CLI_VERSION,
        app_id=_string(lark_section.get("app_id")) or "",
        app_secret=_string(lark_section.get("app_secret")) or "",
        test_doc=_string(lark_section.get("test_doc")) or "",
        prd_folder_token=_string(lark_section.get("prd_folder_token")) or "",
    )
    workspace = WorkspaceConfig(
        root=_string(workspace_section.get("root")) or "",
        default_repo=_string(workspace_section.get("default_repo")) or "",
    )
    approval = ApprovalConfig(
        enabled=_bool(approval_section.get("enabled"), False),
        definition_code=_string(approval_section.get("definition_code")) or "",
        poll_interval_seconds=_int(approval_section.get("poll_interval_seconds"), 60),
    )
    semantic = SemanticConfig(
        enabled=_bool(semantic_section.get("enabled"), True),
        max_workers=_int(semantic_section.get("max_workers"), 4),
        parse_timeout_seconds=_int(semantic_section.get("parse_timeout_seconds"), 10),
        max_symbols_per_file=_int(semantic_section.get("max_symbols_per_file"), 500),
        index_dir_name=_string(semantic_section.get("index_dir_name")) or ".devflow-index",
    )
    interaction = InteractionConfig(
        default_chat_id=_string(interaction_section.get("default_chat_id")) or "",
        max_queue_size=_int(interaction_section.get("max_queue_size"), 5),
        message_merge_window_seconds=_int(interaction_section.get("message_merge_window_seconds"), 5),
        progress_notifications_enabled=_bool(interaction_section.get("progress_notifications_enabled"), True),
    )

    if lark.cli_version != LOCKED_LARK_CLI_VERSION:
        raise ConfigError(
            "不支持的 lark.cli_version："
            f"期望 {LOCKED_LARK_CLI_VERSION}，实际为 {lark.cli_version}。"
        )
    if require_llm_api_key and not llm.api_key:
        raise ConfigError("缺少必填配置项：llm.api_key。")
    if require_llm_model and not llm.model:
        raise ConfigError("缺少必填配置项：llm.model。")
    if require_lark_credentials:
        _require("lark.app_id", lark.app_id)
        _require("lark.app_secret", lark.app_secret)
    if require_lark_test_doc:
        _require("lark.test_doc", lark.test_doc)

    return DevflowConfig(llm=llm, lark=lark, workspace=workspace, approval=approval, semantic=semantic, interaction=interaction)


def _section(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"配置段必须是 object：{name}。")
    return value


def _require(name: str, value: str) -> None:
    if not value:
        raise ConfigError(f"缺少必填配置项：{name}。")


def _string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise ConfigError("配置项必须是数字：llm.temperature。") from exc
    raise ConfigError("配置项必须是数字：llm.temperature。")


def _int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise ConfigError("配置项必须是整数。") from exc
    raise ConfigError("配置项必须是整数。")


def _bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    raise ConfigError("配置项必须是布尔值：llm.response_format_json。")
