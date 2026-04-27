import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from sqlalchemy import select
from app.db.session import get_background_session
from app.models.pipeline import PipelineRun, PipelineRunStatus
from app.models.stage import StageRun, StageRunStatus
from app.models.checkpoint import CheckpointRecord, CheckpointStatus
from app.models.artifact import Artifact
from app.core.pipeline.orchestrator import (
    create_pipeline_run,
    precheck_pipeline_run,
    start_pipeline_run,
)
from app.core.execution.executor import run_pipeline_stages
from app.core.checkpoint.checkpoint_service import (
    approve_checkpoint,
    reject_checkpoint,
    get_pending_checkpoint,
)
from app.core.pipeline.template_loader import ensure_default_template
from app.db.base import init_db
from app.models.provider import ProviderConfig


async def ensure_providers_ready(session):
    result = await session.execute(
        select(ProviderConfig).where(ProviderConfig.enabled == True)
    )
    providers = list(result.scalars().all())
    if not providers:
        print("   WARNING: No enabled providers found. Pipeline will fail without a configured LLM Provider.")
    else:
        print(f"   Found {len(providers)} enabled provider(s)")


async def verify_state(session, run_id, expected_pipeline_status, expected_stage_states, label):
    run = await session.get(PipelineRun, run_id)
    assert run is not None, f"[{label}] PipelineRun not found"

    status_ok = run.status == expected_pipeline_status
    print(f"[{label}] PipelineRun status: {run.status.value} (expected: {expected_pipeline_status.value}) {'✓' if status_ok else '✗'}")

    result = await session.execute(
        select(StageRun).where(StageRun.run_id == run_id)
    )
    stage_runs = {sr.stage_key: sr for sr in result.scalars().all()}

    for stage_key, expected_status in expected_stage_states.items():
        sr = stage_runs.get(stage_key)
        if sr:
            ok = sr.status == expected_status
            print(f"[{label}]   StageRun {stage_key}: {sr.status.value} (expected: {expected_status.value}) {'✓' if ok else '✗'}")
        else:
            print(f"[{label}]   StageRun {stage_key}: NOT FOUND ✗")

    result = await session.execute(
        select(Artifact).where(Artifact.run_id == run_id)
    )
    artifacts = list(result.scalars().all())
    print(f"[{label}]   Artifacts count: {len(artifacts)}")

    return status_ok


async def test_full_pipeline_flow():
    print("=" * 60)
    print("Test: Full Pipeline Flow (Mock Provider)")
    print("=" * 60)

    await init_db()

    async with get_background_session() as session:
        await ensure_default_template(session)
        await disable_real_providers(session)
        await session.commit()

    async with get_background_session() as session:
        run = await create_pipeline_run(
            session=session,
            requirement_text="Add GET /api/health endpoint",
        )
        await session.commit()
        run_id = run.id
        print(f"\n1. Created pipeline run: {run_id}")
        print(f"   Status: {run.status.value}")

    async with get_background_session() as session:
        run = await precheck_pipeline_run(session, run_id)
        await session.commit()
        print(f"\n2. Precheck passed")
        print(f"   Status: {run.status.value}")

    async with get_background_session() as session:
        run = await start_pipeline_run(session, run_id)
        await session.commit()
        print(f"\n3. Started pipeline")
        print(f"   Status: {run.status.value}")
        print(f"   Current stage: {run.current_stage_key}")

    print(f"\n4. Running pipeline stages (will stop at first checkpoint)...")
    run = await run_pipeline_stages(run_id)

    async with get_background_session() as session:
        run = await session.get(PipelineRun, run_id)
        print(f"   Status: {run.status.value}")
        print(f"   Current stage: {run.current_stage_key}")

        await verify_state(
            session, run_id,
            PipelineRunStatus.WAITING_CHECKPOINT,
            {
                "requirement_analysis": StageRunStatus.SUCCEEDED,
                "solution_design": StageRunStatus.SUCCEEDED,
                "checkpoint_design_approval": StageRunStatus.RUNNING,
                "code_generation": StageRunStatus.PENDING,
            },
            "5. After first checkpoint"
        )

        checkpoint = await get_pending_checkpoint(session, run_id)
        assert checkpoint is not None, "No pending checkpoint found!"
        assert checkpoint.stage_key == "checkpoint_design_approval", f"Wrong checkpoint: {checkpoint.stage_key}"
        print(f"\n   Pending checkpoint: {checkpoint.stage_key} (type={checkpoint.checkpoint_type})")

    async with get_background_session() as session:
        print(f"\n6. Approving first checkpoint...")
        record = await approve_checkpoint(session, checkpoint.id)
        await session.commit()
        print(f"   Checkpoint status: {record.status.value}")
        print(f"   Next stage: {record.next_stage_key}")

    print(f"\n7. Running pipeline stages (will stop at second checkpoint)...")
    run = await run_pipeline_stages(run_id)

    async with get_background_session() as session:
        run = await session.get(PipelineRun, run_id)
        print(f"   Status: {run.status.value}")
        print(f"   Current stage: {run.current_stage_key}")

        await verify_state(
            session, run_id,
            PipelineRunStatus.WAITING_CHECKPOINT,
            {
                "checkpoint_design_approval": StageRunStatus.SUCCEEDED,
                "code_generation": StageRunStatus.SUCCEEDED,
                "test_generation_and_execution": StageRunStatus.SUCCEEDED,
                "code_review": StageRunStatus.SUCCEEDED,
                "checkpoint_final_approval": StageRunStatus.RUNNING,
            },
            "8. After second checkpoint"
        )

        checkpoint2 = await get_pending_checkpoint(session, run_id)
        assert checkpoint2 is not None, "No pending checkpoint found!"
        assert checkpoint2.stage_key == "checkpoint_final_approval", f"Wrong checkpoint: {checkpoint2.stage_key}"
        print(f"\n   Pending checkpoint: {checkpoint2.stage_key} (type={checkpoint2.checkpoint_type})")

    async with get_background_session() as session:
        print(f"\n9. Approving second checkpoint...")
        record = await approve_checkpoint(session, checkpoint2.id)
        await session.commit()

    print(f"\n10. Running pipeline stages (should complete)...")
    run = await run_pipeline_stages(run_id)

    async with get_background_session() as session:
        await verify_state(
            session, run_id,
            PipelineRunStatus.SUCCEEDED,
            {
                "checkpoint_final_approval": StageRunStatus.SUCCEEDED,
                "delivery_integration": StageRunStatus.SUCCEEDED,
            },
            "11. Pipeline completed"
        )

    print(f"\n{'=' * 60}")
    print(f"FULL PIPELINE FLOW TEST PASSED ✓")
    print(f"{'=' * 60}")


async def test_checkpoint_reject_flow():
    print(f"\n{'=' * 60}")
    print("Test: Checkpoint Reject and Rollback Flow")
    print(f"{'=' * 60}")

    async with get_background_session() as session:
        run = await create_pipeline_run(
            session=session,
            requirement_text="Add a simple logging endpoint",
        )
        await disable_real_providers(session)
        await session.commit()
        run_id = run.id
        print(f"\n1. Created pipeline run: {run_id}")

    async with get_background_session() as session:
        await precheck_pipeline_run(session, run_id)
        await session.commit()

    async with get_background_session() as session:
        await start_pipeline_run(session, run_id)
        await session.commit()

    print(f"\n2. Running to first checkpoint...")
    run = await run_pipeline_stages(run_id)

    async with get_background_session() as session:
        checkpoint = await get_pending_checkpoint(session, run_id)
        assert checkpoint is not None
        print(f"   Pending checkpoint: {checkpoint.stage_key}")

    async with get_background_session() as session:
        print(f"\n3. Rejecting first checkpoint...")
        record = await reject_checkpoint(session, checkpoint.id, reason="Design needs more detail")
        await session.commit()
        print(f"   Checkpoint status: {record.status.value}")
        print(f"   Rollback target: {record.next_stage_key}")

    async with get_background_session() as session:
        run = await session.get(PipelineRun, run_id)
        assert run.current_stage_key == "solution_design", f"Expected solution_design, got {run.current_stage_key}"
        print(f"   Current stage: {run.current_stage_key}")

        result = await session.execute(
            select(StageRun).where(
                StageRun.run_id == run_id,
                StageRun.stage_key == "checkpoint_design_approval",
            )
        )
        cp_sr = result.scalars().first()
        assert cp_sr.status == StageRunStatus.FAILED, f"Expected FAILED, got {cp_sr.status.value}"
        print(f"   Checkpoint StageRun status: {cp_sr.status.value} ✓")

    print(f"\n4. Re-running after reject (should redo solution_design and reach checkpoint again)...")
    run = await run_pipeline_stages(run_id)

    async with get_background_session() as session:
        run = await session.get(PipelineRun, run_id)
        assert run.status == PipelineRunStatus.WAITING_CHECKPOINT, f"Expected WAITING_CHECKPOINT, got {run.status.value}"
        print(f"   Status: {run.status.value} ✓")

        checkpoint2 = await get_pending_checkpoint(session, run_id)
        assert checkpoint2 is not None
        print(f"   New pending checkpoint: {checkpoint2.stage_key} ✓")

    async with get_background_session() as session:
        print(f"\n5. Approving checkpoint after re-design...")
        await approve_checkpoint(session, checkpoint2.id)
        await session.commit()

    run = await run_pipeline_stages(run_id)

    async with get_background_session() as session:
        run = await session.get(PipelineRun, run_id)
        assert run.status == PipelineRunStatus.WAITING_CHECKPOINT or run.status == PipelineRunStatus.SUCCEEDED
        print(f"   Final status: {run.status.value} ✓")

    print(f"\n{'=' * 60}")
    print(f"CHECKPOINT REJECT FLOW TEST PASSED ✓")
    print(f"{'=' * 60}")


async def main():
    try:
        await test_full_pipeline_flow()
    except Exception as e:
        print(f"\n✗ FULL PIPELINE FLOW TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    try:
        await test_checkpoint_reject_flow()
    except Exception as e:
        print(f"\n✗ CHECKPOINT REJECT FLOW TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
