from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from devflow.checkpoint import apply_checkpoint_decision, build_solution_review_checkpoint, load_checkpoint, write_checkpoint
from devflow.code.agent import (
    build_code_generation_artifact,
    load_solution_artifact,
    write_code_diff,
    write_code_generation_artifact,
)
from devflow.config import ConfigError, ProjectEntry, load_config
from devflow.semantic.indexer import SemanticIndexer
from devflow.llm import LlmError, base_url_host, probe_llm
from devflow.intake.analyzer import build_requirement_artifact
from devflow.intake.lark_cli import (
    LarkCliError,
    ensure_lark_cli_version,
    fetch_doc_source,
    fetch_message_source,
    find_lark_cli_executable,
    get_lark_cli_auth_status,
    listen_bot_sources,
)
from devflow.intake.output import default_artifact_path, write_artifact
from devflow.pipeline import run_code_generation_after_approval, run_start_loop
from devflow.pipeline import run_delivery_after_code_review_approval
from devflow.review.agent import (
    build_code_review_artifact,
    load_requirement_artifact as load_review_requirement_artifact,
    write_code_review_artifact,
)
from devflow.review.render import render_code_review_markdown
from devflow.solution.designer import (
    build_solution_design_artifact,
    load_requirement_artifact,
    write_solution_artifact,
)
from devflow.solution.render import render_solution_markdown
from devflow.solution.workspace import WorkspaceError, resolve_workspace
from devflow.test.agent import (
    build_test_generation_artifact,
    load_code_generation_artifact,
    load_requirement_artifact as load_test_requirement_artifact,
    write_test_diff,
    write_test_generation_artifact,
)

DEFAULT_MODEL = "heuristic-local-v1"
DEFAULT_ANALYZER = "llm"





def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devflow",
        description="DevFlow Engine 命令行工具。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser(
        "start",
        help="启动最小 DevFlow 流水线并监听机器人需求消息。",
    )
    start.add_argument(
        "--once",
        action="store_true",
        help="处理一条机器人消息后退出。",
    )
    start.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="等待机器人事件的最长秒数。默认不设置超时。",
    )
    start.add_argument(
        "--out-dir",
        default="artifacts/runs",
        help="流水线运行产物目录。",
    )
    start.add_argument(
        "--analyzer",
        choices=["heuristic", "llm"],
        default=None,
        help="兼容旧入口；当前流水线会根据配置选择需求分析方式。",
    )

    start.add_argument("--provider", default=None, help="覆盖 config.json 中的 LLM Provider。")
    start.set_defaults(handler=handle_start)

    serve = subparsers.add_parser(
        "serve",
        help="启动 RESTful API 服务器。",
    )
    serve.add_argument("--host", default="127.0.0.1", help="监听地址。")
    serve.add_argument("--port", type=int, default=8080, help="监听端口。")
    serve.add_argument("--out-dir", default="artifacts/runs", help="流水线运行产物目录。")
    serve.set_defaults(handler=handle_serve)

    checkpoint = subparsers.add_parser("checkpoint", help="人工检查点命令。")
    checkpoint_subparsers = checkpoint.add_subparsers(dest="checkpoint_command", required=True)

    decide = checkpoint_subparsers.add_parser("decide", help="记录检查点同意或拒绝。")
    decide.add_argument("--run", required=True, help="运行 ID。")
    decide.add_argument("--decision", required=True, choices=("approve", "reject"), help="检查点决策。")
    decide.add_argument("--reason", default="", help="Reject 理由。")
    decide.add_argument("--force", action="store_true", help="强制通过质量门禁。")
    decide.add_argument("--out-dir", default="artifacts/runs", help="运行目录根路径。")
    decide.set_defaults(handler=handle_checkpoint_decide)

    resume = checkpoint_subparsers.add_parser("resume", help="为阻塞运行补充仓库上下文并恢复方案设计。")
    resume.add_argument("--run", required=True, help="运行 ID。")
    resume_workspace = resume.add_mutually_exclusive_group(required=True)
    resume_workspace.add_argument("--repo", help="已有项目文件夹路径。")
    resume_workspace.add_argument("--new-project", help="在 workspace.root 下创建的新项目名。")
    resume.add_argument("--out-dir", default="artifacts/runs", help="运行目录根路径。")
    resume.set_defaults(handler=handle_checkpoint_resume)

    poll = checkpoint_subparsers.add_parser("poll", help="轮询飞书审批状态并更新检查点。")
    poll.add_argument("--out-dir", default="artifacts/runs", help="运行目录根路径。")
    poll.add_argument("--once", action="store_true", help="只执行一轮轮询后退出。")
    poll.set_defaults(handler=handle_checkpoint_poll)

    design = subparsers.add_parser("design", help="方案设计 agent 命令。")
    design_subparsers = design.add_subparsers(dest="design_command", required=True)

    from_requirement = design_subparsers.add_parser(
        "from-requirement",
        help="读取需求 JSON 和仓库上下文并输出技术方案 JSON。",
    )
    from_requirement.add_argument("--requirement", required=True, help="devflow.requirement.v1 JSON 路径。")
    workspace_group = from_requirement.add_mutually_exclusive_group(required=True)
    workspace_group.add_argument("--repo", help="已有项目文件夹路径。")
    workspace_group.add_argument("--new-project", help="在 workspace.root 下创建的新项目名称。")
    from_requirement.add_argument("--out", required=True, help="输出 solution JSON 路径。")
    from_requirement.set_defaults(handler=handle_design_from_requirement)

    code = subparsers.add_parser("code", help="代码生成 agent 命令。")
    code_subparsers = code.add_subparsers(dest="code_command", required=True)
    generate = code_subparsers.add_parser("generate", help="根据已审批技术方案生成代码变更。")
    generate_source = generate.add_mutually_exclusive_group(required=True)
    generate_source.add_argument("--solution", help="devflow.solution_design.v1 JSON 路径。")
    generate_source.add_argument("--run", help="运行 ID；默认读取 artifacts/runs/<run_id>/solution.json。")
    generate.add_argument("--out", help="输出 code-generation JSON 路径。使用 --solution 时必填。")
    generate.add_argument("--out-dir", default="artifacts/runs", help="运行目录根路径。")
    generate.set_defaults(handler=handle_code_generate)

    test = subparsers.add_parser("test", help="测试生成 agent 命令。")
    test_subparsers = test.add_subparsers(dest="test_command", required=True)
    test_generate = test_subparsers.add_parser("generate", help="根据代码变更和需求生成测试并执行验证。")
    test_generate.add_argument("--run", help="运行 ID；默认读取 artifacts/runs/<run_id> 下的上游产物。")
    test_generate.add_argument("--requirement", help="devflow.requirement.v1 JSON 路径。")
    test_generate.add_argument("--solution", help="devflow.solution_design.v1 JSON 路径。")
    test_generate.add_argument("--code-generation", help="devflow.code_generation.v1 JSON 路径。")
    test_generate.add_argument("--out", help="输出 test-generation JSON 路径。显式 artifact 模式必填。")
    test_generate.add_argument("--out-dir", default="artifacts/runs", help="运行目录根路径。")
    test_generate.set_defaults(handler=handle_test_generate)

    review = subparsers.add_parser("review", help="代码评审 agent 命令。")
    review_subparsers = review.add_subparsers(dest="review_command", required=True)
    review_generate = review_subparsers.add_parser("generate", help="根据代码变更和测试结果生成代码评审报告。")
    review_generate.add_argument("--run", help="运行 ID；默认读取 artifacts/runs/<run_id> 下的上游产物。")
    review_generate.add_argument("--requirement", help="devflow.requirement.v1 JSON 路径。")
    review_generate.add_argument("--solution", help="devflow.solution_design.v1 JSON 路径。")
    review_generate.add_argument("--code-generation", help="devflow.code_generation.v1 JSON 路径。")
    review_generate.add_argument("--test-generation", help="devflow.test_generation.v1 JSON 路径。")
    review_generate.add_argument("--out", help="输出 code-review JSON 路径。显式 artifact 模式必填。")
    review_generate.add_argument("--out-dir", default="artifacts/runs", help="运行目录根路径。")
    review_generate.set_defaults(handler=handle_review_generate)

    delivery = subparsers.add_parser("delivery", help="交付包生成 agent 命令。")
    delivery_subparsers = delivery.add_subparsers(dest="delivery_command", required=True)
    delivery_generate = delivery_subparsers.add_parser("generate", help="根据已审批代码评审生成最终交付包。")
    delivery_generate.add_argument("--run", required=True, help="运行 ID；默认读取 artifacts/runs/<run_id> 下的上游产物。")
    delivery_generate.add_argument("--out-dir", default="artifacts/runs", help="运行目录根路径。")
    delivery_generate.set_defaults(handler=handle_delivery_generate)

    intake = subparsers.add_parser("intake", help="需求采集命令。")
    intake_subparsers = intake.add_subparsers(dest="intake_command", required=True)

    from_doc = intake_subparsers.add_parser(
        "from-doc",
        help="读取飞书/Lark 文档并输出需求 JSON。",
    )
    from_doc.add_argument(
        "--doc",
        help="飞书/Lark 文档 URL 或 token。默认使用 config.json 中的 lark.test_doc。",
    )
    from_doc.add_argument("--out", required=True, help="输出 JSON 路径。")
    from_doc.add_argument("--model", default=DEFAULT_MODEL, help="分析器模型标签。")
    from_doc.add_argument(
        "--analyzer",
        choices=("llm", "heuristic"),
        default=DEFAULT_ANALYZER,
        help="需求分析器后端。",
    )

    from_doc.set_defaults(handler=handle_from_doc)

    from_message = intake_subparsers.add_parser(
        "from-message",
        help="读取飞书/Lark IM 消息并输出需求 JSON。",
    )
    from_message.add_argument("--message-id", required=True, help="消息 ID，例如 om_xxx。")
    from_message.add_argument("--out", required=True, help="输出 JSON 路径。")
    from_message.add_argument("--model", default=DEFAULT_MODEL, help="分析器模型标签。")
    from_message.add_argument(
        "--analyzer",
        choices=("llm", "heuristic"),
        default=DEFAULT_ANALYZER,
        help="需求分析器后端。",
    )

    from_message.set_defaults(handler=handle_from_message)

    listen_bot = intake_subparsers.add_parser(
        "listen-bot",
        help="消费有限数量的机器人消息事件，并为每个事件输出一个 JSON 文件。",
    )
    listen_bot.add_argument(
        "--max-events",
        type=int,
        default=1,
        help="退出前最多消费的事件数。",
    )
    listen_bot.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="等待事件的最长秒数。",
    )
    listen_bot.add_argument("--out-dir", required=True, help="输出目录。")

    listen_bot.set_defaults(handler=handle_listen_bot)

    doctor = intake_subparsers.add_parser(
        "doctor",
        help="检查本地配置和 lark-cli 是否已准备好执行真实采集。",
    )
    doctor.add_argument(
        "--skip-auth",
        action="store_true",
        help="尚未完成登录时跳过 `lark-cli auth status`。",
    )
    doctor.add_argument(
        "--check-llm",
        action="store_true",
        help="向已配置的 LLM provider 发送一次小型真实请求。",
    )
    doctor.set_defaults(handler=handle_doctor)

    semantic = subparsers.add_parser("semantic", help="语义索引命令。")
    semantic_subparsers = semantic.add_subparsers(dest="semantic_command", required=True)

    semantic_index = semantic_subparsers.add_parser("index", help="构建语义索引。")
    semantic_index.add_argument("--workspace", required=True, help="工作区路径。")
    semantic_index.add_argument("--force-full", action="store_true", help="强制全量重建。")
    semantic_index.set_defaults(handler=handle_semantic_index)

    workspace = subparsers.add_parser("workspace", help="工作区管理命令。")
    workspace_subparsers = workspace.add_subparsers(dest="workspace_command", required=True)

    workspace_list = workspace_subparsers.add_parser("list", help="列出工作区中的所有项目。")
    workspace_list.set_defaults(handler=handle_workspace_list)

    workspace_add = workspace_subparsers.add_parser("add", help="添加项目到工作区。")
    workspace_add.add_argument("--name", required=True, help="项目名称。")
    workspace_add.add_argument("--path", required=True, help="项目路径。")
    workspace_add.add_argument("--remote", default="", help="远程仓库 URL。")
    workspace_add.add_argument("--description", default="", help="项目描述。")
    workspace_add.set_defaults(handler=handle_workspace_add)

    workspace_resolve = workspace_subparsers.add_parser("resolve", help="解析项目工作区路径。")
    workspace_resolve.add_argument("name", help="项目名称。")
    workspace_resolve.set_defaults(handler=handle_workspace_resolve)

    workspace_validate = workspace_subparsers.add_parser("validate", help="验证工作区中所有项目的有效性。")
    workspace_validate.set_defaults(handler=handle_workspace_validate)

    return parser


def handle_start(args: argparse.Namespace) -> int:
    if args.provider:
        import os
        os.environ["DEVFLOW_PROVIDER_OVERRIDE"] = args.provider
    run_start_loop(
        out_dir=Path(args.out_dir),
        once=args.once,
        timeout_seconds=args.timeout,
    )
    return 0


def handle_serve(args: argparse.Namespace) -> int:
    from devflow.api import run_server
    run_server(host=args.host, port=args.port, out_dir=Path(args.out_dir))
    return 0


def handle_checkpoint_decide(args: argparse.Namespace) -> int:
    from devflow.graph_runner import run_pipeline_graph

    run_dir = Path(args.out_dir) / args.run
    current_checkpoint = load_checkpoint(run_dir)
    checkpoint = apply_checkpoint_decision(
        run_dir,
        args.decision,
        reason=args.reason or None,
        reviewer={"source": "cli"},
        force_override=args.force,
    )
    run_path = run_dir / "run.json"
    if run_path.exists():
        run_payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
        run_payload["checkpoint_status"] = checkpoint["status"]
        run_payload["checkpoint_artifact"] = str(run_dir / "checkpoint.json")
        run_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if checkpoint["status"] == "waiting_approval_with_warnings":
            print(checkpoint.get("approval_blocked_reason", "方案未就绪，无法批准。如需强制通过请使用 --force"))
        elif checkpoint["status"] in {"approved", "approved_with_override"} and current_checkpoint.get("stage") != "code_review":
            run_pipeline_graph(run_dir, entrypoint="solution_approved", checkpoint=checkpoint)
        elif checkpoint["status"] in {"approved", "approved_with_override"}:
            run_pipeline_graph(run_dir, entrypoint="code_review_approved", checkpoint=checkpoint)
        else:
            run_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(run_dir / "checkpoint.json"))
    return 0


def handle_checkpoint_resume(args: argparse.Namespace) -> int:
    run_dir = Path(args.out_dir) / args.run
    run_path = run_dir / "run.json"
    run_payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    requirement_path = Path(run_payload["requirement_artifact"])
    requirement = load_requirement_artifact(requirement_path)
    workspace = resolve_workspace(
        repo_path=args.repo,
        new_project=args.new_project,
        config=config.workspace,
    )
    artifact = build_solution_design_artifact(
        requirement,
        workspace,
        config.llm,
        requirement_path=requirement_path,
    )
    solution_path = write_solution_artifact(artifact, run_dir / "solution.json")
    solution_markdown_path = run_dir / "solution.md"
    solution_markdown_path.write_text(render_solution_markdown(artifact, run_id=args.run), encoding="utf-8")
    checkpoint = build_solution_review_checkpoint(run_payload, solution_path, solution_markdown_path)
    checkpoint_path = write_checkpoint(run_dir, checkpoint)
    run_payload["status"] = "success"
    run_payload["solution_artifact"] = str(solution_path)
    run_payload["solution_markdown"] = str(solution_markdown_path)
    run_payload["checkpoint_artifact"] = str(checkpoint_path)
    run_payload["checkpoint_status"] = checkpoint["status"]
    run_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(solution_markdown_path))
    return 0


def handle_checkpoint_poll(args: argparse.Namespace) -> int:
    from devflow.approval_client import (
        get_approval_instance,
        get_external_approval_instance,
        parse_approval_result,
        parse_external_approval_result,
    )
    from devflow.checkpoint import load_checkpoint, write_checkpoint
    from devflow.graph_runner import run_pipeline_graph

    out_dir = Path(args.out_dir)
    processed = 0
    for checkpoint_path in sorted(out_dir.glob("*/checkpoint.json")):
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if checkpoint.get("status") != "waiting_approval":
            continue
        instance_code = checkpoint.get("approval_instance_code")
        if not instance_code:
            continue

        # Determine whether this is an external or native approval
        approval_code = checkpoint.get("approval_code")
        try:
            if approval_code:
                detail = get_external_approval_instance(approval_code, instance_code)
                result = parse_external_approval_result(detail)
            else:
                detail = get_approval_instance(instance_code)
                result = parse_approval_result(detail)
        except Exception as exc:
            print(f"轮询失败 {instance_code}：{exc}", file=sys.stderr)
            continue

        if result.status in ("APPROVED", "REJECTED"):
            run_dir = checkpoint_path.parent
            if result.decision == "approve":
                checkpoint["status"] = "approved"
                checkpoint["decision"] = "approve"
                checkpoint["continue_requested"] = True
                checkpoint["reject_reason"] = None
            else:
                checkpoint["status"] = "rejected"
                checkpoint["decision"] = "reject"
                checkpoint["continue_requested"] = False
                checkpoint["reject_reason"] = result.reject_reason or ""
            checkpoint["updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            write_checkpoint(run_dir, checkpoint)
            # Sync run.json
            run_path = run_dir / "run.json"
            if run_path.exists():
                run_payload = json.loads(run_path.read_text(encoding="utf-8-sig"))
                run_payload["checkpoint_status"] = checkpoint["status"]
                run_payload["checkpoint_artifact"] = str(checkpoint_path)
                run_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if checkpoint["status"] == "approved" and checkpoint.get("stage") != "code_review":
                    run_pipeline_graph(run_dir, entrypoint="solution_approved", checkpoint=checkpoint)
                elif checkpoint["status"] == "approved":
                    run_pipeline_graph(run_dir, entrypoint="code_review_approved", checkpoint=checkpoint)
                else:
                    run_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"已更新 {checkpoint['run_id']}：{checkpoint['status']}")
            processed += 1
    if processed == 0:
        print("无需更新检查点。")
    return 0


def handle_code_generate(args: argparse.Namespace) -> int:
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    if args.run:
        run_dir = Path(args.out_dir) / args.run
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
        solution_path = Path(run_payload.get("solution_artifact") or run_dir / "solution.json")
        out_path = Path(args.out) if args.out else run_dir / "code-generation.json"
    else:
        if not args.out:
            raise ValueError("使用 --solution 时必须提供 --out。")
        solution_path = Path(args.solution)
        out_path = Path(args.out)

    solution = load_solution_artifact(solution_path)
    artifact = build_code_generation_artifact(solution, config.llm)
    written = write_code_generation_artifact(artifact, out_path)
    write_code_diff(artifact, out_path.with_suffix(".diff"))
    print(str(written))
    return 0


def handle_test_generate(args: argparse.Namespace) -> int:
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    if args.run:
        run_dir = Path(args.out_dir) / args.run
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
        requirement_path = Path(run_payload.get("requirement_artifact") or run_dir / "requirement.json")
        solution_path = Path(run_payload.get("solution_artifact") or run_dir / "solution.json")
        code_generation_path = Path(run_payload.get("code_generation_artifact") or run_dir / "code-generation.json")
        out_path = Path(args.out) if args.out else run_dir / "test-generation.json"
    else:
        if not args.requirement or not args.solution or not args.code_generation or not args.out:
            raise ValueError("显式测试生成模式必须提供 --requirement、--solution、--code-generation 和 --out。")
        requirement_path = Path(args.requirement)
        solution_path = Path(args.solution)
        code_generation_path = Path(args.code_generation)
        out_path = Path(args.out)

    requirement = load_test_requirement_artifact(requirement_path)
    solution = load_solution_artifact(solution_path)
    code_generation = load_code_generation_artifact(code_generation_path)
    artifact = build_test_generation_artifact(
        requirement,
        solution,
        code_generation,
        config.llm,
        requirement_path=requirement_path,
        solution_path=solution_path,
        code_generation_path=code_generation_path,
    )
    written = write_test_generation_artifact(artifact, out_path)
    write_test_diff(artifact, out_path.with_suffix(".diff"))
    print(str(written))
    return 0


def handle_review_generate(args: argparse.Namespace) -> int:
    config = load_config(require_llm_api_key=True, require_llm_model=True)
    if args.run:
        run_dir = Path(args.out_dir) / args.run
        run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
        requirement_path = Path(run_payload.get("requirement_artifact") or run_dir / "requirement.json")
        solution_path = Path(run_payload.get("solution_artifact") or run_dir / "solution.json")
        code_generation_path = Path(run_payload.get("code_generation_artifact") or run_dir / "code-generation.json")
        test_generation_path = Path(run_payload.get("test_generation_artifact") or run_dir / "test-generation.json")
        out_path = Path(args.out) if args.out else run_dir / "code-review.json"
    else:
        if not args.requirement or not args.solution or not args.code_generation or not args.test_generation or not args.out:
            raise ValueError("显式代码评审模式必须提供 --requirement、--solution、--code-generation、--test-generation 和 --out。")
        requirement_path = Path(args.requirement)
        solution_path = Path(args.solution)
        code_generation_path = Path(args.code_generation)
        test_generation_path = Path(args.test_generation)
        out_path = Path(args.out)

    requirement = load_review_requirement_artifact(requirement_path)
    solution = load_solution_artifact(solution_path)
    code_generation = load_code_generation_artifact(code_generation_path)
    test_generation = json.loads(test_generation_path.read_text(encoding="utf-8-sig"))
    artifact = build_code_review_artifact(
        requirement,
        solution,
        code_generation,
        test_generation,
        config.llm,
        requirement_path=requirement_path,
        solution_path=solution_path,
        code_generation_path=code_generation_path,
        test_generation_path=test_generation_path,
    )
    written = write_code_review_artifact(artifact, out_path)
    out_path.with_suffix(".md").write_text(
        render_code_review_markdown(artifact, run_id=args.run or out_path.stem),
        encoding="utf-8",
    )
    print(str(written))
    return 0


def handle_delivery_generate(args: argparse.Namespace) -> int:
    run_dir = Path(args.out_dir) / args.run
    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8-sig"))
    checkpoint = load_checkpoint(run_dir)
    written = run_delivery_after_code_review_approval(run_dir, run_payload, checkpoint)
    print(str(written))
    return 0


def handle_design_from_requirement(args: argparse.Namespace) -> int:
    try:
        config = load_config(require_llm_api_key=True, require_llm_model=True)
    except ConfigError as exc:
        raise LarkCliError(str(exc)) from exc
    requirement_path = Path(args.requirement)
    requirement = load_requirement_artifact(requirement_path)
    workspace = resolve_workspace(
        repo_path=args.repo,
        new_project=args.new_project,
        config=config.workspace,
    )
    artifact = build_solution_design_artifact(
        requirement,
        workspace,
        config.llm,
        requirement_path=requirement_path,
    )
    out_path = write_solution_artifact(artifact, Path(args.out))
    print(str(out_path))
    return 0


def handle_from_doc(args: argparse.Namespace) -> int:
    doc = args.doc or _configured_test_doc()
    source = fetch_doc_source(doc)
    artifact = _build_artifact(source, args)
    out_path = write_artifact(artifact, Path(args.out))
    print(str(out_path))
    return 0


def handle_from_message(args: argparse.Namespace) -> int:
    source = fetch_message_source(args.message_id)
    artifact = _build_artifact(source, args)
    out_path = write_artifact(artifact, Path(args.out))
    print(str(out_path))
    return 0


def handle_listen_bot(args: argparse.Namespace) -> int:
    if args.max_events < 1:
        raise LarkCliError("--max-events 至少为 1，才能执行有界机器人采集。")

    out_dir = Path(args.out_dir)
    written: list[Path] = []
    for source in listen_bot_sources(max_events=args.max_events, timeout_seconds=args.timeout):
        artifact = _build_artifact(source, args)
        out_path = default_artifact_path(out_dir, source)
        written.append(write_artifact(artifact, out_path))

    if not written:
        raise LarkCliError("命令结束前没有收到机器人消息事件。")

    for path in written:
        print(str(path))
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    try:
        config = load_config(
            require_llm_api_key=True,
            require_llm_model=True,
            require_lark_credentials=True,
            require_lark_test_doc=True,
        )
    except ConfigError as exc:
        raise LarkCliError(str(exc)) from exc

    executable = find_lark_cli_executable()
    version = ensure_lark_cli_version(config.lark.cli_version)
    print("配置：正常")
    print(f"LLM 提供者：{config.llm.provider}")
    print(f"LLM 模型：{config.llm.model}")
    print(f"LLM 基础 URL 主机：{base_url_host(config.llm)}")
    print(f"lark-cli 可执行文件：{executable}")
    print(f"lark-cli 版本：{version}")
    if config.approval.enabled:
        try:
            from devflow.pipeline import external_approval_unavailable_reason

            unavailable_reason = external_approval_unavailable_reason()
        except Exception:
            unavailable_reason = None
        if unavailable_reason:
            print(f"外部审批能力：不可用，{unavailable_reason}")
        else:
            print("外部审批能力：启用（运行时会预检并在权限不足时使用卡片兜底）")

    if args.skip_auth:
        print("lark-cli 认证：已跳过")
    else:
        get_lark_cli_auth_status()
        print("lark-cli 认证：正常")
    if args.check_llm:
        probe_llm(config.llm)
        print("LLM 连通性：正常")
    return 0


def handle_semantic_index(args: argparse.Namespace) -> int:
    config = load_config()
    indexer = SemanticIndexer(workspace_root=args.workspace, config=config.semantic)
    summary = indexer.build_index(force_full=args.force_full)
    lang_dist = ", ".join(f"{lang}={count}" for lang, count in sorted(summary.language_distribution.items()))
    print("语义索引已构建")
    print(f"  构建类型：{summary.build_type}")
    print(f"  符号总数：{summary.total_symbols}")
    print(f"  关系总数：{summary.total_relations}")
    print(f"  文件总数：{summary.total_files}")
    print(f"  语言分布：{lang_dist}")
    print(f"  耗时：{summary.build_time_ms}ms")
    return 0


def _workspace_project_status(entry: ProjectEntry, root: str) -> str:
    path = Path(entry.path).expanduser()
    if not path.is_absolute() and root:
        path = Path(root) / path
    resolved = path.resolve()
    if not resolved.exists():
        return "❌ 路径不存在"
    if root:
        try:
            resolved.relative_to(Path(root).expanduser().resolve())
        except ValueError:
            return "❌ 超出 root 边界"
    return "✅ 有效"


def handle_workspace_list(args: argparse.Namespace) -> int:
    config = load_config()
    projects = config.workspace.projects
    if not projects:
        print("工作区中没有项目。")
        return 0
    print(f"{'名称':<20}\t{'路径':<30}\t{'远程':<20}\t{'状态'}")
    for entry in projects:
        remote = entry.remote or "-"
        status = _workspace_project_status(entry, config.workspace.root)
        print(f"{entry.name:<20}\t{entry.path:<30}\t{remote:<20}\t{status}")
    return 0


def handle_workspace_add(args: argparse.Namespace) -> int:
    config = load_config()
    for entry in config.workspace.projects:
        if entry.name == args.name:
            print(f"项目名称「{args.name}」已存在。", file=sys.stderr)
            return 2
    config_path = Path("config.json")
    if not config_path.exists():
        print("未找到配置文件：config.json", file=sys.stderr)
        return 2
    payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    workspace_payload = payload.setdefault("workspace", {})
    projects_payload = workspace_payload.setdefault("projects", [])
    projects_payload.append({
        "name": args.name,
        "path": args.path,
        "remote": args.remote,
        "description": args.description,
    })
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已添加项目「{args.name}」→ {args.path}")
    return 0


def handle_workspace_resolve(args: argparse.Namespace) -> int:
    config = load_config()
    entry = None
    for p in config.workspace.projects:
        if p.name == args.name:
            entry = p
            break
    if entry is None:
        print(f"未找到项目「{args.name}」。", file=sys.stderr)
        return 2
    resolved = resolve_workspace(repo_path=entry.path, config=config.workspace)
    print(f"路径：{resolved['path']}")
    print(f"名称：{resolved['project_name']}")
    print(f"来源：{resolved['source']}")
    print(f"可写：{'是' if resolved['writable'] else '否'}")
    return 0


def handle_workspace_validate(args: argparse.Namespace) -> int:
    config = load_config()
    projects = config.workspace.projects
    if not projects:
        print("工作区中没有项目。")
        return 0
    ok_count = 0
    fail_count = 0
    for entry in projects:
        try:
            resolve_workspace(repo_path=entry.path, config=config.workspace)
            print(f"✅ {entry.name}")
            ok_count += 1
        except WorkspaceError as exc:
            print(f"❌ {entry.name}：{exc}")
            fail_count += 1
    print(f"\n验证完成：{ok_count} 个有效，{fail_count} 个无效。")
    return 0 if fail_count == 0 else 2


def _build_artifact(source, args: argparse.Namespace) -> dict:
    if args.analyzer == "heuristic":
        return build_requirement_artifact(source, model=args.model, analyzer="heuristic")
    try:
        config = load_config(require_llm_api_key=True, require_llm_model=True)
    except ConfigError as exc:
        raise LarkCliError(str(exc)) from exc
    return build_requirement_artifact(source, analyzer="llm", llm_config=config.llm)


def _configured_test_doc() -> str:
    try:
        return load_config(require_lark_test_doc=True).lark.test_doc
    except ConfigError as exc:
        raise LarkCliError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (ConfigError, LarkCliError, LlmError, WorkspaceError, ValueError) as exc:
        print(f"devflow 错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
