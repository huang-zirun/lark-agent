"""测试 Agent Runner 完整流程"""
import asyncio
import json
import sys
sys.path.insert(0, 'd:/进阶指南/lark-agent/backend')

from app.agents.runner import run_agent, _get_output_schema, _validate_and_fix_output
from app.agents.profiles import get_profile
from app.core.provider.openai_compatible import OpenAICompatibleProvider
from app.core.provider.base import generate_with_retry

async def test_agent_runner():
    # 创建 provider
    provider = OpenAICompatibleProvider(
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        api_key="ark-68e0d61c-2646-4a0e-8ac1-7ea35da99d21-a6c8f",
        model="ep-20260423222610-xbx2l"
    )

    # 获取 profile
    profile = get_profile("requirement_agent")
    print(f"Profile: {profile}")

    # 获取 output schema
    schema = _get_output_schema(profile)
    print(f"\nSchema: {json.dumps(schema, ensure_ascii=False, indent=2)[:500]}...")

    # 构建输入
    input_data = {
        "requirement_text": "为 FastAPI 服务添加一个健康检查接口 GET /api/health，返回包含 service、status、version、time 字段的 JSON 响应。"
    }

    # 构建 prompt
    from app.agents.runner import _build_prompt
    prompt = _build_prompt(profile, input_data)
    print(f"\nPrompt preview:\n{prompt[:500]}...")

    # 调用 provider
    print("\n--- Calling provider ---")
    try:
        result = await provider.generate(
            prompt=prompt,
            schema=schema,
            system_prompt=profile.system_prompt,
        )
        print(f"Result type: {type(result)}")
        print(f"Result:\n{json.dumps(result, ensure_ascii=False, indent=2)[:1000]}...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent_runner())
