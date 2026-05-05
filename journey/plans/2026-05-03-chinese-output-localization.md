# 中文化输出与 Prompt 改造计划

## 目标

将 DevFlow 运行时的人可读输出统一为简体中文，同时保持 `devflow.requirement.v1` 与 `devflow.pipeline_run.v1` 的英文字段名、schema/version、枚举值和下游机器接口不变。

## 实施范围

- 中文化 ProductRequirementAnalyst 系统提示词与 LLM user prompt，要求字段结构保持英文、字段值使用简体中文。
- 中文化 artifact 中由本地规则生成的默认标题、开放问题、验收标准、质量告警、交接提示和 section 默认标题。
- 修复启发式分析中文关键词乱码，覆盖“背景、用户、问题、目标、范围、验收”等常见需求写法。
- 中文化飞书机器人回复、CLI help、doctor 输出、配置错误、LLM 错误和 lark-cli 适配层错误。
- 修复 README 和测试样例中的中文乱码，统一按 UTF-8 保存。
- 更新 `journey/design.md`，记录契约字段保持英文、用户可读输出中文化的设计决策。

## 验收

- 现有测试和新增中文化测试通过。
- `uv run python -m unittest discover -s tests -v` 通过。
- 不新增中文别名字段，不修改 JSON contract 字段名。
