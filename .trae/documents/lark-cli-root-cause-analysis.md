# 根因分析：lark-cli "The system cannot find the file specified" 反复出现

## 错误现象

```
[bot] 欢迎消息发送失败：lark-cli 执行失败（D:\lark\node_modules\.bin\lark-cli.cmd）：The system cannot find the file specified.
```

## 根因分析

### 之前的修复及其错误假设

2026-05-06 的修复将 `shell=True` 改为 `shell=False`，基于以下假设（记录在 `journey/design.md` 第 55 行）：

> With `shell=False`, `CreateProcessW()` automatically delegates `.cmd` files to `cmd.exe` without going through the `/c` quoting trap.

**这个假设是错误的。**

### 真实机制：`CreateProcessW` 对 `.cmd` 文件的处理

当 Python `subprocess.run([executable, *args], shell=False)` 在 Windows 上执行 `.cmd` 文件时：

1. `CreateProcessW` 检测到 `.cmd` 扩展名
2. `CreateProcessW` 构造新命令行：`cmd.exe /c "<原始命令行>"`
3. `CreateProcessW` 递归调用自身执行新命令行

**`cmd.exe /c` 仍然被使用，`/c` 引号剥离陷阱仍然生效。** `shell=False` 与 `shell=True` 的区别仅在于 Python 如何构造初始命令行——但最终都经过 `cmd.exe /c`。

### 引号剥离的完整推导

Python 构造的命令行（`shell=False`）：
```
"D:\lark\node_modules\.bin\lark-cli.cmd" im +messages-send --chat-id oc_xxx --msg-type text --content "{\"text\": \"🤖 DevFlow 已就绪\\n\\n...\"}" --as bot --idempotency-key df-welcome-xxx
```

`CreateProcessW` 将其转为：
```
cmd.exe /c "D:\lark\node_modules\.bin\lark-cli.cmd" im +messages-send --chat-id oc_xxx --msg-type text --content "{\"text\": \"🤖 DevFlow 已就绪\\n\\n...\"}" --as bot --idempotency-key df-welcome-xxx
```

`cmd.exe /c` 的引号剥离规则：当 `/c` 后的字符串以 `"` 开头时，`cmd.exe` 扫描整个字符串，**剥离第一个和最后一个引号**。

剥离后：
```
D:\lark\node_modules\.bin\lark-cli.cmd" im +messages-send --chat-id oc_xxx --msg-type text --content "{\"text\": \"🤖 DevFlow 已就绪\\n\\n...\"} --as bot --idempotency-key df-welcome-xxx
```

可执行文件路径变成 `D:\lark\node_modules\.bin\lark-cli.cmd"`（末尾多了引号），文件不存在 → **"The system cannot find the file specified."**

### 为什么 `iter_lark_cli_event_stream()` 不受影响

事件监听使用 `lark-cli event consume im.message.receive_v1 --as bot`，参数简单、不含嵌入引号。`cmd.exe /c` 不触发引号剥离，所以 `shell=False` 对它有效。

**而 `send_bot_text()` 通过 `--content` 传递 JSON（含大量双引号），必然触发引号剥离。**

### 为什么之前"修复"后看似有效

可能原因：
1. 修复后未实际测试欢迎消息发送（仅跑单元测试，单元测试 mock 了 subprocess）
2. 当时 PATH 中存在全局安装的 `lark-cli.exe`，`shutil.which("lark-cli.exe")` 优先命中了原生二进制
3. 欢迎消息内容较短时引号数量不足以触发剥离

### 根因总结

| 层级 | 问题 |
|------|------|
| **直接原因** | `cmd.exe /c` 剥离首尾引号，导致 `.cmd` 文件路径被破坏 |
| **设计缺陷** | 在 Windows 上通过 `.cmd` shim 传递含嵌入引号的命令行参数，这是不可靠的 |
| **之前的修复为何无效** | `shell=False` 并不能绕过 `cmd.exe /c`，`CreateProcessW` 对 `.cmd` 文件仍使用 `cmd.exe /c` |
| **深层原因** | `find_lark_cli_executable()` 优先选择 `lark-cli.cmd`（候选顺序 `["lark-cli.cmd", "lark-cli.exe", "lark-cli"]`），而 `.cmd` shim 必然经过 `cmd.exe /c` |

## 修复方案

### 核心策略：使用原生 `lark-cli.exe`，绕过 `.cmd` shim

`@larksuite/cli` 包在 `node_modules/@larksuite/cli/bin/lark-cli.exe` 提供了原生二进制。直接使用 `.exe` 可以完全绕过 `cmd.exe /c`，从根本上消除引号剥离问题。

### 实现步骤

1. **修改 `find_lark_cli_executable()`**：
   - 当 `shutil.which` 找到 `.cmd` shim 时，解析对应的 `.exe` 路径
   - `.cmd` shim 位于 `node_modules/.bin/lark-cli.cmd`，对应的 `.exe` 位于 `node_modules/@larksuite/cli/bin/lark-cli.exe`
   - 相对路径关系：`<shim_dir>/../@larksuite/cli/bin/lark-cli.exe`
   - 如果 `.exe` 存在，返回 `.exe` 路径；否则回退到 `.cmd`

2. **更新 `journey/design.md`**：
   - 修正第 55 行关于 `CreateProcessW` 的错误描述
   - 记录新决策：Windows 上优先使用原生 `.exe` 而非 `.cmd` shim

3. **更新测试**：
   - 添加测试验证 `.exe` 解析逻辑
   - 确保回退到 `.cmd` 的路径仍然可用

### 为什么这不是 ad-hoc patch

- **解决根因**：不再依赖 `cmd.exe /c`，从根本上消除引号剥离问题
- **架构一致**：与项目"将 lark-cli 视为外部集成边界"的设计一致，只是选择了更可靠的调用方式
- **向后兼容**：如果 `.exe` 不存在（如全局安装场景），自动回退到 `.cmd`
- **可验证**：`lark-cli.exe` 已确认存在于 `node_modules/@larksuite/cli/bin/`

### 涉及文件

| 文件 | 变更 |
|------|------|
| `devflow/intake/lark_cli.py` | 修改 `find_lark_cli_executable()`，添加 `.exe` 解析逻辑 |
| `journey/design.md` | 修正第 55 行错误描述，记录新决策 |
| `tests/test_requirement_intake.py` | 更新 mock 以覆盖 `.exe` 解析路径 |
