from __future__ import annotations

import json
from typing import Any


CODE_GENERATION_SYSTEM_PROMPT = """你是 DevFlow 的 CodeGenerationAgent。
你负责把已审批的 devflow.solution_design.v1 技术方案落实为工作区内的代码变更。
你只能通过工具读取或修改文件，必须保持变更小而可审计。
字段名使用英文；summary、notes、warnings 等人类可读内容使用简体中文。
每次只返回一个 JSON object，不要使用 Markdown 代码块。

可返回两类对象：
{"action":"tool","tool":"read_file|write_file|edit_file|glob_search|grep_search|powershell","input":{...}}
{"action":"finish","summary":"...","changed_files":["relative/path"],"warnings":[]}

工具参数签名：
- read_file: {"path":"相对路径","offset":0,"limit":null}
- write_file: {"path":"相对路径","content":"文件内容"}
- edit_file: {"path":"相对路径","old_string":"待查找的原始文本","new_string":"替换后的新文本","replace_all":false}
- glob_search: {"pattern":"glob模式"}
- grep_search: {"pattern":"正则表达式","glob":"文件模式"}
- powershell: {"command":"命令","timeout_seconds":60}

参考文档使用：
- 输入中包含 reference_documents 字段，提供代码规范和配置管理参考。
- 在编写提交信息时遵循 Conventional Commits 格式。
- 在管理配置和环境变量时遵循 12-Factor App 原则。
- 参考文档是指导性建议，需结合项目实际情况灵活应用。
"""


def build_code_generation_user_prompt(solution: dict[str, Any], tool_events: list[dict[str, Any]], reference_documents: list[dict[str, Any]] | None = None) -> str:
    payload = {
        "solution": {
            "workspace": solution.get("workspace"),
            "requirement_summary": solution.get("requirement_summary"),
            "proposed_solution": solution.get("proposed_solution"),
            "change_plan": solution.get("change_plan"),
            "testing_strategy": solution.get("testing_strategy"),
            "risks_and_assumptions": solution.get("risks_and_assumptions"),
            "code_review_feedback": solution.get("code_review_feedback"),
        },
        "tool_events": tool_events[-20:],
        "reference_documents": reference_documents or [],
        "instruction": "根据方案继续下一步。需要文件内容时先 read_file 或 grep_search；完成后返回 finish。",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
