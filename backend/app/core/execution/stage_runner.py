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
from app.agents.mock_agents import MOCK_AGENTS
from app.schemas.artifacts import ARTIFACT_TYPE_TO_SCHEMA
from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def execute_stage(
    session: AsyncSession,
    run_id: str,
    stage_key: str,
    use_mock: bool = True,
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

        if use_mock and agent_profile_id in MOCK_AGENTS:
            agent_result = await MOCK_AGENTS[agent_profile_id](**input_data)
        else:
            from app.agents.runner import run_agent
            agent_result = await run_agent(session, agent_profile_id, input_data)

        output_artifact_refs = {}
        for artifact_type, artifact_data in agent_result.items():
            schema_cls = ARTIFACT_TYPE_TO_SCHEMA.get(artifact_type)
            if schema_cls:
                try:
                    schema_cls.model_validate(artifact_data)
                except Exception as e:
                    logger.warning(f"Schema validation warning for {artifact_type}: {e}")

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
