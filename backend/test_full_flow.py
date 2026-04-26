"""测试完整流程，找出问题所在"""
import asyncio
import json
import os
import sys

# 设置环境变量
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test.db"
os.environ["OPENAI_API_KEY"] = "ark-68e0d61c-2646-4a0e-8ac1-7ea35da99d21-a6c8f"
os.environ["OPENAI_API_BASE"] = "https://ark.cn-beijing.volces.com/api/v3"
os.environ["OPENAI_DEFAULT_MODEL"] = "ep-20260423222610-xbx2l"

sys.path.insert(0, 'd:/进阶指南/lark-agent/backend')

async def test_full_flow():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.agents.runner import run_agent
    from app.core.provider.provider_registry import register_provider_instance
    from app.core.provider.openai_compatible import OpenAICompatibleProvider

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

        # 准备输入
        input_data = {
            "requirement_text": "为 FastAPI 服务添加一个健康检查接口 GET /api/health，返回包含 service、status、version、time 字段的 JSON 响应。"
        }

        print("Calling run_agent...")
        try:
            result = await run_agent(
                session=session,
                agent_profile_id="requirement_agent",
                input_data=input_data,
                provider_id="doubao"
            )
            print(f"\nResult type: {type(result)}")
            print(f"Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            print(f"Result:\n{json.dumps(result, ensure_ascii=False, indent=2)[:2000]}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_flow())
