"""测试 JSON 解析问题"""
import json

# 模拟豆包模型的输出
raw_content = '''{
  "requirement_brief": {
    "schema_version": "1.0",
    "goal": "Add a health check endpoint",
    "acceptance_criteria": ["Returns 200"],
    "constraints": [],
    "assumptions": [],
    "risks": [],
    "estimated_effort": "small"
  }
}'''

parsed = json.loads(raw_content)
print(f"Parsed type: {type(parsed)}")
print(f"Parsed: {json.dumps(parsed, indent=2)}")

# 检查每个 value 的类型
for key, value in parsed.items():
    print(f"  {key}: {type(value)}")
