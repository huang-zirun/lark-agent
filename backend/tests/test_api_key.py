#!/usr/bin/env python3
"""
测试 API Key 配置是否正确
"""
import asyncio
import sys
from pathlib import Path

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.shared.config import settings
from app.core.provider.openai_compatible import OpenAICompatibleProvider


async def test_openai_provider():
    """测试 OpenAI Compatible Provider"""
    print("=" * 60)
    print("测试 OpenAI Compatible Provider (火山引擎)")
    print("=" * 60)

    # 检查配置
    print("\n[配置信息]")
    print(f"   API Base: {settings.OPENAI_API_BASE}")
    print(f"   API Key: {settings.OPENAI_API_KEY[:20]}..." if settings.OPENAI_API_KEY else "   API Key: 未设置")
    print(f"   Model: {settings.OPENAI_DEFAULT_MODEL}")

    if not settings.OPENAI_API_KEY:
        print("\n[X] 错误: OPENAI_API_KEY 未设置")
        return False

    # 创建 Provider 实例
    provider = OpenAICompatibleProvider(
        api_base=settings.OPENAI_API_BASE,
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_DEFAULT_MODEL,
    )

    # 测试 1: 验证 API Key（调用 /models 接口）
    print("\n[测试 1] 验证 API Key...")
    try:
        is_valid = await provider.validate()
        if is_valid:
            print("   [OK] API Key 验证通过")
        else:
            print("   [X] API Key 验证失败")
            return False
    except Exception as e:
        print(f"   [X] 验证出错: {e}")
        return False

    # 测试 2: 简单文本生成
    print("\n[测试 2] 测试文本生成...")
    try:
        response = await provider.generate(
            prompt="你好，请用一句话介绍自己。",
            system_prompt="你是一个有帮助的AI助手。",
        )
        print(f"   [OK] 文本生成成功")
        print(f"   响应: {response[:100]}..." if len(str(response)) > 100 else f"   响应: {response}")
    except Exception as e:
        print(f"   [X] 文本生成失败: {e}")
        return False

    # 测试 3: 结构化输出（JSON）
    print("\n[测试 3] 测试结构化输出...")
    try:
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["name", "description"],
        }
        response = await provider.generate(
            prompt="请用 JSON 格式介绍 Python 编程语言，包含 name 和 description 字段。",
            schema=schema,
        )
        print(f"   [OK] 结构化输出成功")
        print(f"   响应: {response}")
    except Exception as e:
        print(f"   [X] 结构化输出失败: {e}")
        return False

    print("\n" + "=" * 60)
    print("[OK] 所有测试通过！API Key 配置正确")
    print("=" * 60)
    return True


async def main():
    print("\nDevFlow Engine API Key 测试工具\n")

    success = await test_openai_provider()

    if success:
        print("\n配置正确，可以开始使用 DevFlow Engine！")
        return 0
    else:
        print("\n配置有误，请检查 .env 文件中的 API Key 设置")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
