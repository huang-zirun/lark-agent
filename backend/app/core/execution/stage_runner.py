from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.pipeline import PipelineRun, PipelineRunStatus
from app.models.stage import StageRun, StageRunStatus, StageDefinition
from app.models.artifact import Artifact
from app.models.checkpoint import CheckpointRecord, CheckpointStatus
from app.core.pipeline.state_machine import StageRunStateMachine
from app.core.pipeline.template_loader import DEFAULT_TEMPLATE_ID, get_stage_definitions
from app.core.artifact.artifact_service import save_artifact, load_artifact, list_artifacts_by_run
from app.core.checkpoint.checkpoint_service import get_pending_checkpoint
from app.core.provider.provider_registry import resolve_provider
from app.core.provider.mock_provider import MockProvider
from app.agents.mock_agents import MOCK_AGENTS
from app.schemas.artifacts import ARTIFACT_TYPE_TO_SCHEMA
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def execute_stage(
    session: AsyncSession,
    run_id: str,
    stage_key: str,
) -> dict:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise ExecutionError(f"PipelineRun {run_id} not found")

    result = await session.execute(
        select(StageRun).where(
            StageRun.run_id == run_id,
            StageRun.stage_key == stage_key,
        ).order_by(StageRun.attempt.desc())
    )
    stage_run = result.scalars().first()
    if not stage_run:
        raise ExecutionError(f"StageRun for {stage_key} not found in run {run_id}")

    new_status = StageRunStateMachine.transition(stage_run.status, StageRunStatus.RUNNING)
    stage_run.status = new_status
    stage_run.started_at = datetime.now(timezone.utc)
    await session.flush()

    try:
        input_data = await _assemble_input(session, run, stage_key)
        agent_profile_id = stage_run.agent_profile_id

        snapshot_commit = await _snapshot_before_stage(session, run, stage_key)

        provider = await resolve_provider(session, provider_id=stage_run.resolved_provider_id)
        is_mock = isinstance(provider, MockProvider)

        if is_mock and agent_profile_id in MOCK_AGENTS:
            agent_result = await MOCK_AGENTS[agent_profile_id](**input_data)
        elif stage_key == "test_generation_and_execution" and not is_mock:
            agent_result = await _execute_test_stage(session, run, input_data, stage_run)
        else:
            from app.agents.runner import run_agent
            agent_result = await run_agent(session, agent_profile_id, input_data, provider_id=stage_run.resolved_provider_id)

        output_artifact_refs = {}
        for artifact_type, artifact_data in agent_result.items():
            schema_cls = ARTIFACT_TYPE_TO_SCHEMA.get(artifact_type)
            if not schema_cls:
                logger.warning(f"Skipping unregistered artifact_type '{artifact_type}' (not in ARTIFACT_TYPE_TO_SCHEMA)")
                continue

            try:
                schema_cls.model_validate(artifact_data)
            except Exception as e:
                logger.error(f"Schema validation failed for artifact '{artifact_type}': {e}")
                output_artifact_refs[artifact_type] = "__validation_failed__"
                continue

            artifact = await save_artifact(
                session=session,
                run_id=run_id,
                stage_run_id=stage_run.id,
                artifact_type=artifact_type,
                data=artifact_data,
                stage_key=stage_key,
            )
            output_artifact_refs[artifact_type] = artifact.id

        stage_run.status = StageRunStatus.SUCCEEDED
        stage_run.output_artifact_refs = output_artifact_refs
        stage_run.ended_at = datetime.now(timezone.utc)
        await session.flush()

        return {"status": "succeeded", "stage_key": stage_key, "artifacts": output_artifact_refs}

    except Exception as e:
        stage_run.status = StageRunStatus.FAILED
        stage_run.error_message = str(e)
        stage_run.ended_at = datetime.now(timezone.utc)
        await session.flush()
        raise ExecutionError(f"Stage {stage_key} execution failed: {str(e)}")


async def _assemble_input(session: AsyncSession, run: PipelineRun, stage_key: str) -> dict:
    artifacts = await list_artifacts_by_run(session, run.id)
    artifact_map = {}
    for a in artifacts:
        data = await load_artifact(session, a.id)
        if data:
            artifact_map[a.artifact_type] = data

    input_data = {"requirement_text": run.requirement_text}

    code_context = await _get_code_context(session, run, artifact_map, stage_key)
    if code_context:
        input_data["code_context"] = code_context

    if stage_key == "requirement_analysis":
        pass
    elif stage_key == "solution_design":
        if "requirement_brief" in artifact_map:
            input_data["requirement_brief"] = artifact_map["requirement_brief"]
        checkpoint_result = await session.execute(
            select(CheckpointRecord).where(
                CheckpointRecord.run_id == run.id,
                CheckpointRecord.status == CheckpointStatus.REJECTED,
            ).order_by(CheckpointRecord.decision_at.desc())
        )
        last_reject = checkpoint_result.scalars().first()
        if last_reject and last_reject.reason:
            input_data["reject_reason"] = last_reject.reason
    elif stage_key == "code_generation":
        if "design_spec" in artifact_map:
            input_data["design_spec"] = artifact_map["design_spec"]
        checkpoint_result = await session.execute(
            select(CheckpointRecord).where(
                CheckpointRecord.run_id == run.id,
                CheckpointRecord.status == CheckpointStatus.REJECTED,
            ).order_by(CheckpointRecord.decision_at.desc())
        )
        last_reject = checkpoint_result.scalars().first()
        if last_reject and last_reject.reason:
            input_data["reject_reason"] = last_reject.reason
    elif stage_key == "test_generation_and_execution":
        if "change_set" in artifact_map:
            input_data["change_set"] = artifact_map["change_set"]
        if "requirement_brief" in artifact_map:
            input_data["requirement_brief"] = artifact_map["requirement_brief"]
        if "design_spec" in artifact_map:
            input_data["design_spec"] = artifact_map["design_spec"]
    elif stage_key == "code_review":
        if "design_spec" in artifact_map:
            input_data["design_spec"] = artifact_map["design_spec"]
        if "change_set" in artifact_map:
            input_data["change_set"] = artifact_map["change_set"]
        if "test_report" in artifact_map:
            input_data["test_report"] = artifact_map["test_report"]
    elif stage_key == "delivery_integration":
        if "change_set" in artifact_map:
            input_data["change_set"] = artifact_map["change_set"]
        if "review_report" in artifact_map:
            input_data["review_report"] = artifact_map["review_report"]
        if "test_report" in artifact_map:
            input_data["test_report"] = artifact_map["test_report"]

    return input_data


async def _get_code_context(
    session: AsyncSession,
    run: PipelineRun,
    artifact_map: dict,
    stage_key: str,
) -> dict | None:
    from app.models.workspace import Workspace
    from app.core.workspace.workspace_manager import get_code_context

    workspace = None
    if run.workspace_ref_id:
        workspace = await session.get(Workspace, run.workspace_ref_id)

    if not workspace or not workspace.workspace_path:
        return None

    needs_context = stage_key in (
        "solution_design",
        "code_generation",
        "test_generation_and_execution",
    )
    if not needs_context:
        return None

    affected_files = None
    if stage_key in ("code_generation", "test_generation_and_execution"):
        design_spec = artifact_map.get("design_spec", {})
        if isinstance(design_spec, dict):
            affected_files = [
                f.get("path") for f in design_spec.get("affected_files", [])
                if isinstance(f, dict) and f.get("path")
            ]

    return get_code_context(
        workspace_path=workspace.workspace_path,
        affected_files=affected_files,
    )


async def _execute_test_stage(
    session: AsyncSession,
    run: PipelineRun,
    input_data: dict,
    stage_run,
) -> dict:
    from app.agents.runner import run_agent
    from app.core.workspace.workspace_manager import Workspace
    from app.core.workspace.patch_applier import apply_patch
    from app.core.workspace.command_runner import run_command
    from app.shared.config import settings

    workspace = None
    if run.workspace_ref_id:
        workspace = await session.get(Workspace, run.workspace_ref_id)

    test_gen_input = {
        "requirement_text": input_data.get("requirement_text", ""),
        "change_set": input_data.get("change_set", {}),
        "requirement_brief": input_data.get("requirement_brief", {}),
        "design_spec": input_data.get("design_spec"),
    }
    if "code_context" in input_data:
        test_gen_input["code_context"] = input_data["code_context"]

    test_change_set_result = await run_agent(
        session, "test_agent", test_gen_input, provider_id=stage_run.resolved_provider_id
    )

    test_artifact_refs = {}
    test_change_set = test_change_set_result.get("test_change_set") or test_change_set_result.get("change_set")

    if test_change_set and workspace and workspace.workspace_path:
        for file_entry in test_change_set.get("files", []):
            file_path = file_entry.get("path", "")
            content = file_entry.get("content")
            patch = file_entry.get("patch")

            if content:
                await apply_patch(
                    workspace_path=workspace.workspace_path,
                    patch_content=content,
                    file_path=file_path,
                )
            elif patch:
                await apply_patch(
                    workspace_path=workspace.workspace_path,
                    patch_content=patch,
                )

        test_command = settings.TEST_COMMAND
        test_timeout = settings.TEST_TIMEOUT

        cmd_result = await run_command(
            command=test_command,
            cwd=workspace.workspace_path,
            timeout=test_timeout,
        )

        test_report = {
            "schema_version": "1.0",
            "exit_code": cmd_result["exit_code"],
            "stdout": cmd_result["stdout"][-5000:] if len(cmd_result["stdout"]) > 5000 else cmd_result["stdout"],
            "stderr": cmd_result["stderr"][-5000:] if len(cmd_result["stderr"]) > 5000 else cmd_result["stderr"],
            "duration_ms": cmd_result["duration_ms"],
            "summary": _parse_test_summary(cmd_result),
        }

        return {"test_report": test_report}

    return test_change_set_result


def _parse_test_summary(cmd_result: dict) -> dict:
    stdout = cmd_result.get("stdout", "")
    stderr = cmd_result.get("stderr", "")
    exit_code = cmd_result.get("exit_code", -1)

    total = 0
    passed = 0
    failed = 0
    skipped = 0

    for line in stdout.split("\n"):
        line = line.strip()
        if " passed" in line or " failed" in line:
            parts = line.split()
            for part in parts:
                if part.endswith("passed"):
                    try:
                        passed = int(part.replace("passed", ""))
                    except ValueError:
                        pass
                elif part.endswith("failed"):
                    try:
                        failed = int(part.replace("failed", ""))
                    except ValueError:
                        pass
                elif part.endswith("skipped"):
                    try:
                        skipped = int(part.replace("skipped", ""))
                    except ValueError:
                        pass

    if passed == 0 and failed == 0 and skipped == 0:
        if exit_code == 0:
            passed = 1
        else:
            failed = 1

    total = passed + failed + skipped

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


async def _snapshot_before_stage(session: AsyncSession, run: PipelineRun, stage_key: str) -> str | None:
    from app.models.workspace import Workspace
    from app.core.workspace.workspace_manager import snapshot_workspace

    workspace = None
    if run.workspace_ref_id:
        workspace = await session.get(Workspace, run.workspace_ref_id)

    if not workspace or not workspace.workspace_path:
        return None

    commit = snapshot_workspace(workspace.workspace_path, f"before {stage_key}")
    if commit:
        logger.info(f"Workspace snapshot created before {stage_key}: {commit}")
    return commit
