"""测试 stage_runner 中的问题"""
import asyncio
import json
import os
import sys

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test.db"

sys.path.insert(0, 'd:/进阶指南/lark-agent/backend')

async def test_stage_runner():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.core.execution.stage_runner import execute_stage
    from app.core.provider.provider_registry import register_provider_instance
    from app.core.provider.openai_compatible import OpenAICompatibleProvider
    from app.models.pipeline import PipelineRun
    from app.models.workspace import Workspace

    # 创建内存数据库
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 创建 provider
        provider = OpenAICompatibleProvider(
            api_base="https://ark.cn-beijing.volces.com/api/v3",
            api_key="ark-68e0d61c-2646-4a0e-8ac1-7ea35da99d21-a6c8f",
            model="ep-20260423222610-xbx2l"
        )
        register_provider_instance("doubao", provider)

        # 创建 workspace
        workspace = Workspace(
            id="test-ws-001",
            source_repo_path="D:/temp/test-repo",
            workspace_path="D:/temp/test-repo",
            git_commit_at_create="abc123",
            status="active"
        )
        session.add(workspace)

        # 创建 pipeline run
        run = PipelineRun(
            id="test-run-001",
            template_id="feature_delivery_default",
            workspace_ref_id="test-ws-001",
            requirement_text="为 FastAPI 服务添加一个健康检查接口 GET /api/health",
            status="running",
            current_stage_key="requirement_analysis"
        )
        session.add(run)
        await session.flush()

        # 创建 stage run
        from app.models.stage import StageRun, StageRunStatus
        stage_run = StageRun(
            id="test-stage-001",
            run_id="test-run-001",
            stage_key="requirement_analysis",
            agent_profile_id="requirement_agent",
            resolved_provider_id="doubao",
            status=StageRunStatus.RUNNING,
            attempt=1
        )
        session.add(stage_run)
        await session.flush()

        print("Executing stage...")
        try:
            result = await execute_stage(session, "test-run-001", "requirement_analysis")
            print(f"\nResult: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_stage_runner())
