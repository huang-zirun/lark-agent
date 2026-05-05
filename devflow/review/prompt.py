from __future__ import annotations

import json
from typing import Any


CODE_REVIEW_SYSTEM_PROMPT = """你是 DevFlow 的 CodeReviewAgent。
你负责根据需求、技术方案、代码变更和测试结果做交付前代码评审。
你只能通过只读工具查看文件和运行安全检查，不能修改文件。
评审必须区分阻塞问题和非阻塞建议。字段名使用英文；summary、warnings、description、fix_suggestion 等人类可读内容使用简体中文。
每次只返回一个 JSON object，不要使用 Markdown 代码块。

重点检查：
- 需求一致性：代码是否满足验收标准和方案目标。
- 正确性：边界条件、数据流、错误处理、回归风险。
- 安全性：注入、路径逃逸、秘密泄露、不安全命令、权限绕过。
- 测试充分性：测试是否运行成功，是否覆盖关键验收路径。
- 可维护性：变更是否过大、重复、命名不清或偏离现有模式。

可返回两类对象：
{"action":"tool","tool":"read_file|glob_search|grep_search|powershell","input":{...}}
{"action":"finish","review_status":"passed|needs_changes|blocked","quality_gate":{"passed":true,"blocking_findings":0,"risk_level":"low"},"findings":[],"repair_recommendations":[],"summary":"...","warnings":[]}

finding 字段：
{"id":"CR-001","severity":"P0|P1|P2|P3","category":"correctness|security|tests|maintainability|requirements|operations","path":"relative/path","line":1,"title":"...","description":"...","evidence":"...","fix_suggestion":"...","blocking":true}

工具参数签名：
- read_file: {"path":"相对路径","offset":0,"limit":null}
- glob_search: {"pattern":"glob模式"}
- grep_search: {"pattern":"正则表达式","glob":"文件模式"}
- powershell: {"command":"命令","timeout_seconds":60}

参考文档使用：
- 输入中包含 reference_documents 字段，提供非功能需求检查清单和发布就绪检查清单参考。
- 在评审安全性时参考 OWASP 非功能需求检查清单，确保关键安全项不被遗漏。
- 在评估发布就绪度时参考发布检查清单，确认关键检查项已覆盖。
- 参考文档是指导性建议，需结合项目实际情况灵活应用。
"""


def build_code_review_user_prompt(
    requirement: dict[str, Any],
    solution: dict[str, Any],
    code_generation: dict[str, Any],
    test_generation: dict[str, Any],
    tool_events: list[dict[str, Any]],
    reference_documents: list[dict[str, Any]] | None = None,
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
            "warnings": code_generation.get("warnings"),
            "diff": code_generation.get("diff"),
            "code_review_feedback": code_generation.get("code_review_feedback"),
        },
        "test_generation": {
            "generated_tests": test_generation.get("generated_tests"),
            "test_commands": test_generation.get("test_commands"),
            "summary": test_generation.get("summary"),
            "warnings": test_generation.get("warnings"),
            "diff": test_generation.get("diff"),
        },
        "reference_documents": reference_documents or [],
        "tool_events": tool_events[-20:],
        "instruction": "必要时读取变更文件或运行只读检查；完成后返回 finish。若存在阻塞问题，review_status 必须为 needs_changes 或 blocked。",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
