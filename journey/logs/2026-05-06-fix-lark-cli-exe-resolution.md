# 修复 lark-cli "The system cannot find the file specified" 根因

## 问题

`devflow start` 启动后欢迎消息发送失败：
```
[bot] 欢迎消息发送失败：lark-cli 执行失败（D:\lark\node_modules\.bin\lark-cli.cmd）：The system cannot find the file specified.
```

此问题之前"修复"过（`shell=True` → `shell=False`），但反复出现。

## 根因

之前的修复基于错误假设：认为 `shell=False` 时 `CreateProcessW` 对 `.cmd` 文件不经过 `cmd.exe /c`。

**实际机制**：`CreateProcessW` 检测到 `.cmd` 扩展名后，仍构造 `cmd.exe /c "<命令行>"` 执行。`cmd.exe /c` 的引号剥离规则在命令行含超过 2 个引号时剥离首尾引号。`send_bot_text()` 通过 `--content` 传递 JSON（含大量双引号），触发引号剥离，导致 `.cmd` 文件路径被破坏。

`iter_lark_cli_event_stream()` 不受影响是因为其参数简单、不含嵌入引号。

## 修复

**核心策略**：使用原生 `lark-cli.exe`，绕过 `.cmd` shim 和 `cmd.exe /c`。

### 代码变更

- `devflow/intake/lark_cli.py`：
  - 新增 `_resolve_native_exe_from_cmd_shim()`：从 `.cmd` shim 路径解析 `node_modules/@larksuite/cli/bin/lark-cli.exe`
  - 修改 `find_lark_cli_executable()`：候选顺序改为 `["lark-cli.exe", "lark-cli.cmd", "lark-cli"]`；找到 `.cmd` 时尝试解析 `.exe`，存在则优先使用，否则回退

### 设计决策更新

- `journey/design.md` 第 55 行：修正关于 `CreateProcessW` 的错误描述，明确 `shell=False` 不能绕过 `cmd.exe /c` 引号陷阱，使用原生 `.exe` 才是正确方案

### 测试

- `tests/test_requirement_intake.py`：
  - `test_windows_resolves_native_exe_from_cmd_shim`：验证 `.exe` 存在时优先使用
  - `test_windows_falls_back_to_cmd_shim_when_exe_missing`：验证 `.exe` 不存在时回退到 `.cmd`
  - `test_resolve_native_exe_returns_none_when_missing`：验证解析函数对不存在路径返回 `None`

41 个相关测试全部通过。

## 历史修复对比

| 日期 | 修复 | 为何无效 |
|------|------|----------|
| 05-03 | 优先 `lark-cli.cmd` 避免 `.ps1` 被阻止 | 未解决 `.cmd` 本身的引号问题 |
| 05-06 | `shell=True` → `shell=False` | `CreateProcessW` 对 `.cmd` 仍用 `cmd.exe /c` |
| 05-06 | `--text` → `--content` JSON 编码 | 消除换行符截断，但 JSON 引号仍触发剥离 |
| **05-06** | **解析原生 `.exe`，绕过 `.cmd` shim** | **根本解决：不经过 `cmd.exe /c`** |
