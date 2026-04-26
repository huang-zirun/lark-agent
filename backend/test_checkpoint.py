"""测试检查点审批"""
import asyncio
import sys
sys.path.insert(0, 'd:/进阶指南/lark-agent/backend')

async def test_checkpoint():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.core.checkpoint.checkpoint_service import approve_checkpoint
    from app.core.execution.executor import run_pipeline_stages

    # 创建数据库连接
    engine = create_async_engine("sqlite+aiosqlite:///./data/devflow.db", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("Approving checkpoint...")
            record = await approve_checkpoint(
                session=session,
                checkpoint_id="b0494f36b34842bdaeb93851dd9053f6",
                decision_by="tester"
            )
            print(f"Checkpoint approved: {record.id}")
            print(f"Status: {record.status}")

            print("\nRunning pipeline stages...")
            run = await run_pipeline_stages(session, "88a6fd3796e249ef890fc46b3b0a0b5b", use_mock=True)
            print(f"Pipeline run status: {run.status}")
            print(f"Current stage: {run.current_stage_key}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_checkpoint())
