# Fix Welcome Message: lark-cli "The system cannot find the file specified"

## Context

`devflow start` 启动后机器人不会自动发送 welcome message，错误信息：
```
欢迎消息发送失败：lark-cli 执行失败：The system cannot find the file specified
```

lark-cli 实际已安装，此问题之前出现过但未修复。

## Root Cause

`run_lark_cli_text()` 使用 `shell=True` 执行 `lark-cli.cmd`，导致两个致命问题：

1. **`cmd.exe /c` 引号解析陷阱**：`shell=True` 将命令传给 `cmd.exe /c`，当命令行包含超过 2 个引号时，`cmd.exe` 会剥离首尾引号。`send_bot_text()` 通过 `--content` 传递 JSON 内容（如 `{"text": "..."}`），其中包含大量双引号，导致可执行文件路径被截断 → `cmd.exe` 报 "The system cannot find the file specified"。

2. **命令行长度限制**：`cmd.exe /c` 限制 8,191 字符，而 `CreateProcessW()` 允许 32,768 字符。

佐证：`iter_lark_cli_event_stream()` 使用 `shell=False` 长期运行稳定，说明 `shell=False` 在 Windows 上可以正确执行 `.cmd` 文件。

## Fix

- 移除 `use_shell = os.name == "nt" and executable.endswith(".cmd")` 逻辑，固定使用 `shell=False`
- `CreateProcessW()` 自动识别 `.cmd` 文件并委托给 `cmd.exe`，绕过 `/c` 引号陷阱
- `LarkCliError` 错误信息中增加可执行文件路径：`lark-cli 执行失败（{executable}）：{stderr}`

## Verification

- 71 个相关测试全部通过（test_welcome_message + test_pipeline_start + test_requirement_intake）
- 完整测试套件运行至 83%+ 无失败

## Files Changed

- `devflow/intake/lark_cli.py` — 移除 `shell=True`，增强错误信息
- `journey/design.md` — 新增 Windows `shell=False` 决策记录
