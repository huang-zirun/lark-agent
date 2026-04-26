"""测试豆包模型完整输出"""
import asyncio
import json
import sys
sys.path.insert(0, 'd:/进阶指南/lark-agent/backend')

from app.agents.runner import run_agent, _get_output_schema, _build_prompt
from app.agents.profiles import get_profile
from app.core.provider.openai_compatible import OpenAICompatibleProvider

async def test_doubao():
    # 创建 provider
    provider = OpenAICompatibleProvider(
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        api_key="ark-68e0d61c-2646-4a0e-8ac1-7ea35da99d21-a6c8f",
        model="ep-20260423222610-xbx2l"
    )

    # 获取 profile
    profile = get_profile("requirement_agent")
    print(f"Profile ID: {profile.id}")
    print(f"Expected outputs: {profile.expected_outputs}")

    # 获取 schema
    schema = _get_output_schema(profile)
    print(f"\nSchema keys: {schema.keys() if isinstance(schema, dict) else 'N/A'}")

    # 构建输入
    input_data = {
        "requirement_text": "为 FastAPI 服务添加一个健康检查接口 GET /api/health，返回包含 service、status、version、time 字段的 JSON 响应。"
    }

    # 构建 prompt
    prompt = _build_prompt(profile, input_data)
    print(f"\nPrompt length: {len(prompt)}")

    # 调用 provider
    print("\n--- Calling provider ---")
    result = await provider.generate(
        prompt=prompt,
        schema=schema,
        system_prompt=profile.system_prompt,
    )

    print(f"\nResult type: {type(result)}")
    print(f"Result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")

    if isinstance(result, dict):
        for key, value in result.items():
            print(f"\n  Key: {key}")
            print(f"  Value type: {type(value)}")
            if isinstance(value, dict):
                print(f"  Value keys: {value.keys()}")
                print(f"  Value content: {json.dumps(value, ensure_ascii=False, indent=2)[:300]}")
            else:
                print(f"  Value: {str(value)[:100]}")

if __name__ == "__main__":
    asyncio.run(test_doubao())
