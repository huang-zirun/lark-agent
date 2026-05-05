from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _parse_iso_timestamp(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def load_all_runs(out_dir: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    if not out_dir.exists():
        return runs
    for run_path in sorted(out_dir.glob("*/run.json"), reverse=True):
        try:
            payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
            runs.append(payload)
        except (OSError, json.JSONDecodeError):
            continue
    return runs


def compute_overview(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    runs_today = 0
    success_count = 0
    completed_durations: list[int] = []
    active_runs = 0
    pending_checkpoints = 0

    for run in runs:
        started_at = _parse_iso_timestamp(run.get("started_at"))
        if started_at and started_at >= today_start:
            runs_today += 1

        status = run.get("status", "")
        if status in ("success", "delivered"):
            success_count += 1

        if status in ("running", "paused"):
            active_runs += 1

        if run.get("checkpoint_status") == "waiting_approval":
            pending_checkpoints += 1

        ended_at = _parse_iso_timestamp(run.get("ended_at"))
        if started_at and ended_at:
            completed_durations.append(int((ended_at - started_at).total_seconds() * 1000))

    success_rate = round((success_count / total * 100), 1) if total else 0.0
    avg_duration_ms = int(sum(completed_durations) / len(completed_durations)) if completed_durations else 0

    return {
        "total_runs": total,
        "runs_today": runs_today,
        "success_rate": success_rate,
        "avg_duration_ms": avg_duration_ms,
        "active_runs": active_runs,
        "pending_checkpoints": pending_checkpoints,
    }


def compute_stage_stats(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stage_data: dict[str, dict[str, Any]] = {}

    for run in runs:
        stages = run.get("stages", [])
        for stage in stages:
            name = stage.get("name")
            if not name:
                continue
            if name not in stage_data:
                stage_data[name] = {
                    "stage_name": name,
                    "total_executions": 0,
                    "durations": [],
                    "success_count": 0,
                    "failure_count": 0,
                }
            entry = stage_data[name]
            entry["total_executions"] += 1

            started = _parse_iso_timestamp(stage.get("started_at"))
            ended = _parse_iso_timestamp(stage.get("ended_at"))
            if started and ended:
                entry["durations"].append(int((ended - started).total_seconds() * 1000))

            status = stage.get("status", "")
            if status == "success":
                entry["success_count"] += 1
            elif status in ("failed", "error"):
                entry["failure_count"] += 1

    result: list[dict[str, Any]] = []
    for name in sorted(stage_data.keys()):
        entry = stage_data[name]
        durations = entry.pop("durations")
        result.append({
            "stage_name": entry["stage_name"],
            "total_executions": entry["total_executions"],
            "avg_duration_ms": int(sum(durations) / len(durations)) if durations else 0,
            "success_count": entry["success_count"],
            "failure_count": entry["failure_count"],
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
        })
    return result


def compute_token_usage(out_dir: Path) -> list[dict[str, Any]]:
    usage_records: list[dict[str, Any]] = []
    if not out_dir.exists():
        return usage_records

    for run_dir in sorted(out_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        run_json = run_dir / "run.json"
        if not run_json.exists():
            continue
        try:
            run = json.loads(run_json.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue

        provider = run.get("provider_override") or "default"
        run_id = run.get("run_id", run_dir.name)

        total_prompt = 0
        total_completion = 0
        total_tokens = 0

        for llm_file in run_dir.glob("*llm-response.json"):
            try:
                llm = json.loads(llm_file.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            usage = llm.get("usage") or {}
            if usage:
                total_prompt += usage.get("prompt_tokens", 0) or 0
                total_completion += usage.get("completion_tokens", 0) or 0
                total_tokens += usage.get("total_tokens", 0) or 0
            if not provider or provider == "default":
                src = llm.get("usage_source")
                if src:
                    provider = src

        if total_tokens > 0:
            usage_records.append({
                "run_id": run_id,
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "total_tokens": total_tokens,
                "provider": provider,
            })

    return usage_records


def get_recent_runs(runs: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    recent: list[dict[str, Any]] = []
    for run in runs[:limit]:
        started_at = run.get("started_at")
        ended_at = run.get("ended_at")
        duration_ms = 0
        if started_at and ended_at:
            s = _parse_iso_timestamp(started_at)
            e = _parse_iso_timestamp(ended_at)
            if s and e:
                duration_ms = int((e - s).total_seconds() * 1000)

        stages = run.get("stages", [])
        current_stage = None
        for stage in stages:
            if stage.get("status") in ("running", "pending"):
                current_stage = stage.get("name")
                break
        if not current_stage and stages:
            current_stage = stages[-1].get("name")

        recent.append({
            "run_id": run.get("run_id"),
            "status": run.get("status"),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "current_stage": current_stage,
            "checkpoint_status": run.get("checkpoint_status"),
            "provider_override": run.get("provider_override"),
        })
    return recent


def get_run_timeline(run_dir: Path) -> list[dict[str, Any]]:
    trace_path = run_dir / "trace.jsonl"
    events: list[dict[str, Any]] = []
    if not trace_path.exists():
        return events
    try:
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    events.append({
                        "timestamp": event.get("timestamp"),
                        "stage": event.get("stage"),
                        "event_type": event.get("type"),
                        "status": event.get("status"),
                        "duration_ms": event.get("duration_ms"),
                        "payload": event.get("payload"),
                    })
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return events


def get_active_run(out_dir: Path) -> dict[str, Any] | None:
    if not out_dir.exists():
        return None
    candidates: list[dict[str, Any]] = []
    for run_path in out_dir.glob("*/run.json"):
        try:
            payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("status") in ("running", "paused"):
            candidates.append(payload)
    if not candidates:
        return None
    candidates.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return candidates[0]


def get_run_llm_trace(run_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not run_dir.exists():
        return results
    request_files: dict[str, Path] = {}
    response_files: dict[str, Path] = {}
    for f in run_dir.glob("*-llm-request.json"):
        prefix = f.name.replace("-llm-request.json", "")
        request_files[prefix] = f
    for f in run_dir.glob("*-llm-response.json"):
        prefix = f.name.replace("-llm-response.json", "")
        response_files[prefix] = f
    all_prefixes = sorted(set(request_files.keys()) | set(response_files.keys()))
    for prefix in all_prefixes:
        entry: dict[str, Any] = {
            "stage": prefix,
            "system_prompt_summary": None,
            "user_prompt_summary": None,
            "content_summary": None,
            "usage": None,
            "duration_ms": None,
            "provider": None,
        }
        req_path = request_files.get(prefix)
        if req_path:
            try:
                req = json.loads(req_path.read_text(encoding="utf-8-sig"))
                messages = req.get("messages", [])
                system_parts: list[str] = []
                user_parts: list[str] = []
                for msg in messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            str(c.get("text", "")) if isinstance(c, dict) else str(c)
                            for c in content
                        )
                    if role == "system":
                        system_parts.append(str(content)[:500])
                    elif role == "user":
                        user_parts.append(str(content)[:500])
                entry["system_prompt_summary"] = "; ".join(system_parts) if system_parts else None
                entry["user_prompt_summary"] = "; ".join(user_parts) if user_parts else None
            except (OSError, json.JSONDecodeError):
                pass
        resp_path = response_files.get(prefix)
        if resp_path:
            try:
                resp = json.loads(resp_path.read_text(encoding="utf-8-sig"))
                raw_content = resp.get("content", "")
                if isinstance(raw_content, list):
                    raw_content = " ".join(
                        str(c.get("text", "")) if isinstance(c, dict) else str(c)
                        for c in raw_content
                    )
                entry["content_summary"] = str(raw_content)[:1000] if raw_content else None
                usage = resp.get("usage")
                if usage:
                    entry["usage"] = {
                        "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
                        "completion_tokens": usage.get("completion_tokens", 0) or 0,
                        "total_tokens": usage.get("total_tokens", 0) or 0,
                    }
                entry["duration_ms"] = resp.get("duration_ms")
                entry["provider"] = resp.get("usage_source") or resp.get("provider")
            except (OSError, json.JSONDecodeError):
                pass
        results.append(entry)
    return results


def get_run_artifacts(run_dir: Path) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    if not run_dir.exists():
        return artifacts

    req_path = run_dir / "requirement.json"
    if req_path.exists():
        try:
            data = json.loads(req_path.read_text(encoding="utf-8-sig"))
            req = data.get("requirement", data)
            quality = data.get("quality", {})
            artifacts["requirement"] = {
                "title": req.get("title") or data.get("source_summary"),
                "acceptance_criteria_count": len(req.get("acceptance_criteria", [])),
                "quality_score": quality.get("overall_score"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    sol_path = run_dir / "solution.json"
    if sol_path.exists():
        try:
            data = json.loads(sol_path.read_text(encoding="utf-8-sig"))
            proposed = data.get("proposed_solution", data)
            quality = data.get("quality", {})
            artifacts["solution"] = {
                "summary": proposed.get("summary"),
                "change_plan_count": len(data.get("change_plan", [])),
                "risk_level": quality.get("risk_level"),
                "ready_for_code_generation": quality.get("ready_for_code_generation"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    cg_path = run_dir / "code-generation.json"
    if cg_path.exists():
        try:
            data = json.loads(cg_path.read_text(encoding="utf-8-sig"))
            changed_files = data.get("changed_files", [])
            diff_stats = data.get("captured_diff_stats")
            if not diff_stats and changed_files:
                additions = sum(f.get("additions", 0) for f in changed_files if isinstance(f, dict))
                deletions = sum(f.get("deletions", 0) for f in changed_files if isinstance(f, dict))
                diff_stats = {"additions": additions, "deletions": deletions}
            artifacts["code-generation"] = {
                "changed_files": [f.get("path") if isinstance(f, dict) else f for f in changed_files],
                "diff_stats": diff_stats,
            }
        except (OSError, json.JSONDecodeError):
            pass

    tg_path = run_dir / "test-generation.json"
    if tg_path.exists():
        try:
            data = json.loads(tg_path.read_text(encoding="utf-8-sig"))
            artifacts["test-generation"] = {
                "detected_stack": data.get("detected_stack"),
                "test_count": data.get("test_count"),
                "test_results_summary": data.get("test_results_summary"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    cr_path = run_dir / "code-review.json"
    if cr_path.exists():
        try:
            data = json.loads(cr_path.read_text(encoding="utf-8-sig"))
            quality_gate = data.get("quality_gate", {})
            artifacts["code-review"] = {
                "review_status": data.get("review_status"),
                "blocking_findings": quality_gate.get("blocking_findings"),
                "risk_level": quality_gate.get("risk_level"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    del_path = run_dir / "delivery.json"
    if del_path.exists():
        try:
            data = json.loads(del_path.read_text(encoding="utf-8-sig"))
            readiness = data.get("readiness", {})
            artifacts["delivery"] = {
                "change_summary": data.get("change_summary"),
                "merge_readiness": readiness.get("merge_ready"),
                "git_branch": data.get("git_branch"),
            }
        except (OSError, json.JSONDecodeError):
            pass

    return artifacts


def get_run_detail(run_dir: Path) -> dict[str, Any]:
    run_json_path = run_dir / "run.json"
    if not run_json_path.exists():
        return {"error": "Run not found", "status_code": 404}
    try:
        run = json.loads(run_json_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"error": "Failed to load run.json", "status_code": 404}

    stages_detail: list[dict[str, Any]] = []
    for stage in run.get("stages", []):
        started = _parse_iso_timestamp(stage.get("started_at"))
        ended = _parse_iso_timestamp(stage.get("ended_at"))
        duration_ms = None
        if started and ended:
            duration_ms = int((ended - started).total_seconds() * 1000)
        stages_detail.append({
            "name": stage.get("name"),
            "status": stage.get("status"),
            "started_at": stage.get("started_at"),
            "ended_at": stage.get("ended_at"),
            "duration_ms": duration_ms,
        })

    checkpoint_path = run_dir / "checkpoint.json"
    checkpoints: list[dict[str, Any]] = []
    if checkpoint_path.exists():
        try:
            cp = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
            checkpoints = [cp]
        except (OSError, json.JSONDecodeError):
            pass

    llm_calls = get_run_llm_trace(run_dir)

    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    for llm_file in run_dir.glob("*-llm-response.json"):
        try:
            llm = json.loads(llm_file.read_text(encoding="utf-8-sig"))
            usage = llm.get("usage") or {}
            if usage:
                total_prompt += usage.get("prompt_tokens", 0) or 0
                total_completion += usage.get("completion_tokens", 0) or 0
                total_tokens += usage.get("total_tokens", 0) or 0
        except (OSError, json.JSONDecodeError):
            continue

    delivery_path = run_dir / "delivery.json"
    delivery = None
    if delivery_path.exists():
        try:
            delivery = json.loads(delivery_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "run": run,
        "stages": stages_detail,
        "artifacts": get_run_artifacts(run_dir),
        "checkpoints": checkpoints,
        "llm_calls": llm_calls,
        "token_summary": {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_tokens,
        },
        "delivery": delivery,
    }


def get_run_diff(run_dir: Path, stage: str) -> str | None:
    stage_map = {
        "code": "code-generation.diff",
        "test": "test-generation.diff",
        "delivery": "delivery.diff",
    }
    filename = stage_map.get(stage)
    if not filename:
        return None
    diff_path = run_dir / filename
    if not diff_path.exists():
        return None
    try:
        return diff_path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
