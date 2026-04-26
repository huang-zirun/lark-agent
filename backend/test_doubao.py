"""测试豆包模型输出格式"""
import asyncio
import json
import httpx

async def test_doubao():
    api_base = "https://ark.cn-beijing.volces.com/api/v3"
    api_key = "ark-68e0d61c-2646-4a0e-8ac1-7ea35da99d21-a6c8f"
    model = "ep-20260423222610-xbx2l"

    system_prompt = """You are a senior requirement analyst. Analyze the given requirement text and produce a structured requirement brief.
Identify the goal, acceptance criteria, constraints, assumptions, and risks.
Be thorough and specific. Output valid JSON only."""

    prompt = """## Task: requirement_analyst

## Input Data:
```json
{
  "requirement_text": "为 FastAPI 服务添加一个健康检查接口 GET /api/health，返回包含 service、status、version、time 字段的 JSON 响应。service 固定为 test-service，status 为 ok，version 从配置或代码读取，time 为当前 ISO 格式时间戳。"
}
```

## Instructions:
You are a senior requirement analyst. Analyze the given requirement text and produce a structured requirement brief.
Identify the goal, acceptance criteria, constraints, assumptions, and risks.
Be thorough and specific. Output valid JSON only.

Respond with valid JSON matching the expected output schema.

## Expected Output Schema:
```json
{
  "requirement_brief": {
    "schema_version": "1.0",
    "goal": "string",
    "acceptance_criteria": ["string"],
    "constraints": ["string"],
    "assumptions": ["string"],
    "risks": ["string"],
    "estimated_effort": "small | medium | large"
  }
}
```

请严格按照以上 JSON Schema 格式返回结果，只返回 JSON，不要包含其他内容。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        print(f"Status: {response.status_code}")
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print(f"\nRaw content:\n{content}")

        # Try to parse as JSON
        try:
            parsed = json.loads(content)
            print(f"\nParsed JSON type: {type(parsed)}")
            print(f"\nParsed JSON:\n{json.dumps(parsed, ensure_ascii=False, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"\nJSON parse error: {e}")

            # Try to extract JSON from markdown
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    extracted = json.loads(content[json_start:json_end])
                    print(f"\nExtracted JSON type: {type(extracted)}")
                    print(f"\nExtracted JSON:\n{json.dumps(extracted, ensure_ascii=False, indent=2)}")
                except json.JSONDecodeError as e2:
                    print(f"Extraction also failed: {e2}")

if __name__ == "__main__":
    asyncio.run(test_doubao())
