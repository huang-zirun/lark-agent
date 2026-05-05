from __future__ import annotations

import json
from typing import Any


TEST_GENERATION_SYSTEM_PROMPT = """你是 DevFlow 的 TestGenerationAgent。你负责根据需求、技术方案和代码变更生成或补充测试，并执行现有测试框架命令验证结果。优先复用仓库已有测试框架；不要自动安装依赖；只通过工具读写工作区文件或运行受限 PowerShell 命令。字段名使用英文；summary、warnings 等人类可读内容使用简体中文。每次只返回一个 JSON object，不要使用 Markdown 代码块。
可返回两类对象：
{"action":"tool","tool":"read_file|write_file|edit_file|glob_search|grep_search|powershell","input":{...}}
{"action":"finish","summary":"...","generated_tests":["relative/path"],"warnings":[]}

工具参数签名：
- read_file: {"path":"相对路径","offset":0,"limit":null}
- write_file: {"path":"相对路径","content":"文件内容"}
- edit_file: {"path":"相对路径","old_string":"待查找的原始文本","new_string":"替换后的新文本","replace_all":false}
- glob_search: {"pattern":"glob模式"}
- grep_search: {"pattern":"正则表达式","glob":"文件模式"}
- powershell: {"command":"命令","timeout_seconds":60}
"""


def build_test_generation_user_prompt(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    detected_stack: dict[str, Any],
    tool_events: list[dict[str, Any]],
) -> str:
    payload = {
        "requirement": {
            "normalized_requirement": requirement.get("normalized_requirement"),
            "acceptance_criteria": requirement.get("acceptance_criteria"),
        },
        "solution": {
            "workspace": solution.get("workspace"),
            "requirement_summary": solution.get("requirement_summary"),
            "proposed_solution": solution.get("proposed_solution"),
            "change_plan": solution.get("change_plan"),
            "testing_strategy": solution.get("testing_strategy"),
        },
        "code_generation": {
            "changed_files": code_generation.get("changed_files"),
            "summary": code_generation.get("summary"),
            "diff": code_generation.get("diff"),
        },
        "detected_stack": detected_stack,
        "tool_events": tool_events[-20:],
        "instruction": "生成必要的单元测试或集成测试，优先运行 detected_stack.commands 中的命令验证。完成后返回 finish。",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
