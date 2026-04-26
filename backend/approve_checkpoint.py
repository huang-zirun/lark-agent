"""审批检查点"""
import asyncio
import sys
sys.path.insert(0, 'd:/进阶指南/lark-agent/backend')

async def approve():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.core.checkpoint.checkpoint_service import approve_checkpoint

    # 创建数据库连接
    engine = create_async_engine("sqlite+aiosqlite:///./data/devflow.db", echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("Approving checkpoint...")
            record = await approve_checkpoint(
                session=session,
                checkpoint_id="b0494f36b34842bdaeb93851dd9053f6",
                decision_by="tester"
            )
            await session.commit()
            print(f"Checkpoint approved: {record.id}")
            print(f"Status: {record.status}")
            print(f"Decision By: {record.decision_by}")
            print(f"Decision At: {record.decision_at}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(approve())
