from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Callable
from urllib import error, request
from urllib.parse import urlparse

from devflow.config import LlmConfig


PROVIDER_BASE_URLS = {
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
    "bailian": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
}


class LlmError(RuntimeError):
    """Raised when an LLM request or response is unusable."""


UrlOpen = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    content: str
    raw_response: dict[str, Any]
    usage: dict[str, Any] | None
    usage_source: str
    started_at: str
    ended_at: str
    duration_ms: int
    request_body: dict[str, Any]

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "content": self.content,
            "usage": self.usage,
            "usage_source": self.usage_source,
            "raw_response": self.raw_response,
        }


def resolve_base_url(config: LlmConfig) -> str:
    provider = config.provider.lower()
    if config.base_url:
        return config.base_url.rstrip("/")
    if provider in PROVIDER_BASE_URLS:
        return PROVIDER_BASE_URLS[provider]
    if provider == "custom":
        raise LlmError("缺少必填配置项：custom provider 需要 llm.base_url。")
    raise LlmError(f"不支持的 llm.provider：{config.provider}。")


def base_url_host(config: LlmConfig) -> str:
    host = urlparse(resolve_base_url(config)).netloc
    if not host:
        raise LlmError("配置项必须是有效 URL：llm.base_url。")
    return host


def check_llm_config(config: LlmConfig) -> None:
    if not config.api_key:
        raise LlmError("缺少必填配置项：llm.api_key。")
    if not config.model:
        raise LlmError("缺少必填配置项：llm.model。")
    resolve_base_url(config)


def chat_completion(
    config: LlmConfig,
    messages: list[dict[str, str]],
    *,
    opener: UrlOpen | None = None,
) -> LlmCompletion:
    check_llm_config(config)
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.response_format_json:
        payload["response_format"] = {"type": "json_object"}
    url = f"{resolve_base_url(config)}/chat/completions"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    open_url = opener or request.urlopen
    started_at = utc_now()
    started_counter = perf_counter()
    try:
        response_context = open_url(http_request, timeout=config.timeout_seconds)
        with response_context as response:
            status = getattr(response, "status", response.getcode())
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_body = _read_error_body(exc)
        if config.api_key:
            error_body = error_body.replace(config.api_key, "[REDACTED]")
        detail = f": {error_body}" if error_body else ""
        raise LlmError(f"LLM 请求失败，HTTP {exc.code}{detail}") from exc
    except socket.timeout as exc:
        raise LlmError(f"LLM 请求超时，已等待 {config.timeout_seconds} 秒。") from exc
    except (error.URLError, TimeoutError) as exc:
        raise LlmError("LLM 请求在收到响应前失败。") from exc
    ended_at = utc_now()
    duration_ms = max(0, int((perf_counter() - started_counter) * 1000))

    if status < 200 or status >= 300:
        raise LlmError(f"LLM 请求失败，HTTP {status}。")

    try:
        response_json = json.loads(response_body)
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LlmError("LLM 响应不符合 Chat Completions 格式。") from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmError("LLM 响应内容为空。")
    if not isinstance(response_json, dict):
        raise LlmError("LLM 响应不符合 Chat Completions 格式。")
    usage = response_json.get("usage")
    if not isinstance(usage, dict):
        usage = None
    return LlmCompletion(
        content=content.strip(),
        raw_response=response_json,
        usage=usage,
        usage_source="provider" if usage is not None else "missing",
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        request_body=payload,
    )


def chat_completion_content(
    config: LlmConfig,
    messages: list[dict[str, str]],
    *,
    opener: UrlOpen | None = None,
) -> str:
    return chat_completion(config, messages, opener=opener).content


def parse_llm_json(text: str) -> dict[str, Any]:
    original_text = text
    text = text.strip()

    # 去除 Markdown 代码块标记
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 使用 raw_decode 解析第一个完整 JSON 值，自动忽略尾部多余内容
    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise LlmError(
                f"LLM 响应不是有效 JSON。原始响应前200字符：{original_text[:200]}"
            )
        try:
            parsed, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError as exc:
            raise LlmError(
                f"LLM 响应不是有效 JSON。原始响应前200字符：{original_text[:200]}"
            ) from exc
    if not isinstance(parsed, dict):
        raise LlmError(
            f"LLM 响应 JSON 必须是 object，实际是 {type(parsed).__name__}。"
        )
    return parsed


def _read_error_body(exc: error.HTTPError) -> str:
    try:
        raw = exc.read()
    except Exception:
        return ""
    if not raw:
        return ""
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return ""
    return text[:500]


def probe_llm(config: LlmConfig, *, opener: UrlOpen | None = None) -> None:
    chat_completion_content(
        config,
        [
            {"role": "system", "content": "只返回 JSON。"},
            {"role": "user", "content": '{"ping":"ok"} -> 返回 {"ok":true}'},
        ],
        opener=opener,
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
