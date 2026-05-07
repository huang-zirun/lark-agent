from __future__ import annotations

import json
import socket
import threading
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
    "longcat": "https://api.longcat.chat/openai",
    "mimo": "https://api.xiaomimimo.com/v1",
    "openai": "https://api.openai.com/v1",
}


class LlmError(RuntimeError):
    """Raised when an LLM request or response is unusable."""


UrlOpen = Callable[..., Any]
_ORIGINAL_URLOPEN = request.urlopen


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    content: str
    raw_response: dict[str, Any]
    usage: dict[str, Any] | None
    usage_source: str
    provider: str
    model: str
    base_url_host: str | None
    started_at: str
    ended_at: str
    duration_ms: int
    request_body: dict[str, Any]
    finish_reason: str

    def to_audit_payload(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "content": self.content,
            "usage": self.usage,
            "usage_source": self.usage_source,
            "provider": self.provider,
            "model": self.model,
            "base_url_host": self.base_url_host,
            "raw_response": self.raw_response,
            "finish_reason": self.finish_reason,
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


def build_chat_completion_request_body(
    config: LlmConfig,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.response_format_json:
        payload["response_format"] = {"type": "json_object"}
    return payload


def chat_completion(
    config: LlmConfig,
    messages: list[dict[str, str]],
    *,
    opener: UrlOpen | None = None,
) -> LlmCompletion:
    check_llm_config(config)
    payload = build_chat_completion_request_body(config, messages)
    url = f"{resolve_base_url(config)}/chat/completions"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    open_url = opener or request.urlopen
    started_at = utc_now()
    started_counter = perf_counter()
    try:
        if opener is not None or _is_patched_urlopen(open_url):
            status, response_body = _open_chat_completion_direct(
                url,
                body,
                headers,
                config.timeout_seconds,
                open_url,
            )
        else:
            status, response_body = _open_chat_completion_with_deadline(
                url,
                body,
                headers,
                config.timeout_seconds,
            )
    except error.HTTPError as exc:
        error_body = _read_error_body(exc)
        if config.api_key:
            error_body = error_body.replace(config.api_key, "[REDACTED]")
        detail = f": {error_body}" if error_body else ""
        raise LlmError(f"LLM 请求失败，HTTP {exc.code}{detail}") from exc
    except _TotalTimeoutError as exc:
        raise LlmError(f"LLM 请求总耗时超时，已等待 {config.timeout_seconds} 秒。") from exc
    except socket.timeout as exc:
        if opener is None:
            raise LlmError(f"LLM 请求总耗时超时，已等待 {config.timeout_seconds} 秒。") from exc
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
    finish_reason = response_json["choices"][0].get("finish_reason", "")
    result = LlmCompletion(
        content=content.strip(),
        raw_response=response_json,
        usage=usage,
        usage_source="provider" if usage is not None else "missing",
        provider=config.provider,
        model=config.model,
        base_url_host=base_url_host(config),
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        request_body=payload,
        finish_reason=finish_reason,
    )
    if finish_reason == "length":
        raise LlmError(f"LLM 响应被截断（finish_reason=length），模型 {config.model} 的 max_tokens={config.max_tokens} 不足以完成完整输出。建议增大 llm.max_tokens 或精简 prompt。")
    return result


class _TotalTimeoutError(TimeoutError):
    pass


def _build_http_request(url: str, body: bytes, headers: dict[str, str]) -> request.Request:
    return request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )


def _is_patched_urlopen(open_url: UrlOpen) -> bool:
    return not (
        getattr(open_url, "__module__", "") == "urllib.request"
        and getattr(open_url, "__name__", "") == "urlopen"
    )


def _open_chat_completion_direct(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout_seconds: int,
    opener: UrlOpen,
) -> tuple[int, str]:
    http_request = _build_http_request(url, body, headers)
    response_context = opener(http_request, timeout=timeout_seconds)
    with response_context as response:
        status = getattr(response, "status", response.getcode())
        response_body = response.read().decode("utf-8")
    return status, response_body


def _open_chat_completion_with_deadline(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout_seconds: int,
) -> tuple[int, str]:
    # Use a threading-based deadline instead of multiprocessing.spawn.
    # The previous multiprocessing.spawn approach had two critical issues on Windows:
    # 1. It requires the calling script to have ``if __name__ == "__main__":`` protection;
    #    without it, the child process re-imports the main module and recurses.
    # 2. Starting a fresh Python process for every LLM call adds significant overhead
    #    (multiple seconds on Windows) and is incompatible with environments where
    #    the entry point is a script without the __main__ guard.
    # The threading approach avoids both problems: no __main__ guard is needed,
    # no process spawn overhead, and the socket timeout + join deadline together
    # enforce a hard wall-clock limit.
    worker_socket_timeout = timeout_seconds + 5
    result: dict[str, Any] = {"done": False}

    def _worker() -> None:
        try:
            status, response_body = _open_chat_completion_direct(
                url,
                body,
                headers,
                worker_socket_timeout,
                request.urlopen,
            )
            result["kind"] = "ok"
            result["payload"] = {"status": status, "body": response_body}
        except error.HTTPError as exc:
            result["kind"] = "http_error"
            result["payload"] = {"code": exc.code, "reason": str(exc)}
        except socket.timeout:
            result["kind"] = "socket_timeout"
        except TimeoutError as exc:
            result["kind"] = "timeout"
            result["payload"] = str(exc)
        except BaseException as exc:
            result["kind"] = "error"
            result["payload"] = f"{type(exc).__name__}: {exc}"
        finally:
            result["done"] = True

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        # Thread is still running past the deadline. The daemon flag ensures it
        # won't block process exit, and the socket timeout will eventually let
        # it clean up on its own.
        raise _TotalTimeoutError()

    if not result.get("done"):
        raise error.URLError("LLM request worker exited without a result")

    kind = result.get("kind", "error")
    payload = result.get("payload")

    if kind == "ok":
        return payload["status"], payload["body"]
    if kind == "http_error":
        raise error.HTTPError(url, payload["code"], payload.get("reason") or "", {}, None)
    if kind == "socket_timeout":
        raise _TotalTimeoutError()
    if kind == "timeout":
        raise TimeoutError(payload)
    raise error.URLError(payload)


def chat_completion_content(
    config: LlmConfig,
    messages: list[dict[str, str]],
    *,
    opener: UrlOpen | None = None,
) -> str:
    return chat_completion(config, messages, opener=opener).content


def _repair_truncated_json(text: str) -> str:
    stack = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append(ch)
        elif ch == '}':
            if stack and stack[-1] == '{':
                stack.pop()
        elif ch == ']':
            if stack and stack[-1] == '[':
                stack.pop()
    result = text
    if in_string:
        result += '"'
    for bracket in reversed(stack):
        result += '}' if bracket == '{' else ']'
    return result


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
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(text[start:] if start >= 0 else text)
            try:
                parsed, _ = decoder.raw_decode(repaired)
            except json.JSONDecodeError as exc:
                raise LlmError(
                    f"LLM 响应被截断，JSON 不完整且无法自动修复。原始响应前200字符：{original_text[:200]}"
                ) from exc
            if not isinstance(parsed, dict):
                raise LlmError(
                    f"LLM 响应 JSON 必须是 object，实际是 {type(parsed).__name__}。"
                )
            return parsed
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
