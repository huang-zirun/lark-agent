# 飞书云文档阶段产物发布计划

## Goal

实现统一阶段产物发布层：各阶段的人类可读 Markdown 产物发布为飞书云文档，并把发布结果记录到 `run.json.artifact_publications`。发布失败不影响流水线阶段成功。

## Scope

- 修正 `lark-cli docs +create` 参数为 `--as bot --title --markdown --folder-token`。
- 新增 `devflow.publication`，统一发布记录、folder token 选择、code/test Markdown renderer。
- 接入 requirement、solution、code generation、test generation、code review、delivery 阶段。
- 外部审批消息使用云文档 URL，失败时保留本地路径兜底。
- 更新配置示例、测试、journey 设计快照。

## Verification

- `uv run pytest tests/test_prd_publish.py tests/test_checkpoint.py tests/test_delivery.py tests/test_pipeline_start.py -q`
- `uv run python -m compileall devflow`
