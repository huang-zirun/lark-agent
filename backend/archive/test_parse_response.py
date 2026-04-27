"""测试解析响应"""
import json
import sys
sys.path.insert(0, 'd:/进阶指南/lark-agent/backend')

from app.core.provider.openai_compatible import _parse_json_response

# 测试各种可能的响应格式
test_cases = [
    # 正常 JSON
    '{"requirement_brief": {"schema_version": "1.0", "goal": "test"}}',

    # 带 markdown 的 JSON
    '```json\n{"requirement_brief": {"schema_version": "1.0", "goal": "test"}}\n```',

    # 带额外文本的 JSON
    'Here is the result:\n{"requirement_brief": {"schema_version": "1.0", "goal": "test"}}\nHope this helps!',

    # 纯字符串（错误情况）
    'This is just a plain text response',
]

for i, test in enumerate(test_cases):
    print(f"\n=== Test case {i+1} ===")
    print(f"Input: {test[:80]}...")
    try:
        result = _parse_json_response(test, "Test")
        print(f"Result type: {type(result)}")
        print(f"Result: {json.dumps(result, indent=2)[:200]}")
    except Exception as e:
        print(f"Error: {e}")
