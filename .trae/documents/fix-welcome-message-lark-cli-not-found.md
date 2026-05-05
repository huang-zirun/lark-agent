# 修复：欢迎消息发送失败 — lark-cli 执行失败：The system cannot find the file specified

## 问题描述

`devflow start` 启动后，机器人不会自动发送 welcome message，错误信息：
```
欢迎消息发送失败：lark-cli 执行失败：The system cannot find the file specified
```

lark-cli 实际已安装，此问题之前出现过但未修复。

## 根因分析

### 调用链路

```
_send_welcome_message()          [pipeline.py:2081]
  → send_bot_text()              [lark_cli.py:451]
    → run_lark_cli()             [lark_cli.py:69]
      → run_lark_cli_text()      [lark_cli.py:48]
        → find_lark_cli_executable()  [lark_cli.py:33]  ← shutil.which() 找到 lark-cli.cmd
        → subprocess.run(shell=True)  [lark_cli.py:53]  ← 问题出在这里
```

### 核心问题：`shell=True` 在 Windows 上的双重缺陷

[lark_cli.py:50-52](file:///d:/lark/devflow/intake/lark_cli.py#L50-L52) 当前代码：
```python
use_shell = os.name == "nt" and executable.endswith(".cmd")
```

**缺陷 1：`cmd.exe /c` 的引号解析问题**

当 `shell=True` 时，Python 构造命令行 `cmd.exe /c "C:\...\lark-cli.cmd" im +messages-send --content {"text":"..."} ...`。`send_bot_text()` 通过 `--content` 传递 JSON 内容，其中包含双引号。`cmd.exe /c` 的引号解析规则与 MS C runtime 不同：

- `cmd.exe` 在命令行中出现超过 2 个引号时，会剥离首尾引号
- JSON 内容 `{"text": "🤖 DevFlow 已就绪\n..."}` 包含大量双引号
- 导致可执行文件路径被截断/损坏 → `cmd.exe` 报 "The system cannot find the file specified"

**缺陷 2：`cmd.exe /c` 的命令行长度限制**

- `shell=True` → `cmd.exe /c` 限制 8,191 字符
- `shell=False` → `CreateProcessW()` 限制 32,768 字符
- 欢迎文本约 600-800 中文字符，JSON 序列化后约 1,500-2,000 字节，加上其他参数，当前虽未超限但余量很小

### 佐证：`iter_lark_cli_event_stream()` 使用 `shell=False` 正常工作

[lark_cli.py:253-259](file:///d:/lark/devflow/intake/lark_cli.py#L253-L259) 事件流监听使用 `subprocess.Popen(shell=False)`，长期运行稳定。这说明 `shell=False` 在 Windows 上可以正确执行 `.cmd` 文件——`CreateProcessW()` 会自动识别 `.cmd` 扩展名并委托给 `cmd.exe` 处理，但绕过了 `cmd.exe /c` 的引号解析陷阱。

### 历史对照

| 问题 | 根因 | 修复方式 |
|------|------|---------|
| PowerShell `.ps1` shim 被阻止 | 执行策略拦截 | 改用 `lark-cli.cmd` |
| 欢迎消息截断 | `--text` 传多行文本被 shell 截断 | 改用 `--content` JSON |
| **当前：The system cannot find the file specified** | `shell=True` + JSON 引号冲突 | **移除 `shell=True`** |

## 修复方案

### 步骤 1：移除 `run_lark_cli_text()` 中的 `shell=True`

修改 [lark_cli.py:48-66](file:///d:/lark/devflow/intake/lark_cli.py#L48-L66)：

```python
def run_lark_cli_text(args: list[str], timeout_seconds: int | None = 120) -> str:
    executable = find_lark_cli_executable()
    completed = subprocess.run(
        [executable, *args],
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise LarkCliError(f"lark-cli 执行失败：{stderr}")
    return completed.stdout.strip()
```

关键变更：
- 移除 `use_shell = os.name == "nt" and executable.endswith(".cmd")` 逻辑
- 固定使用 `shell=False`
- `CreateProcessW()` 会自动识别 `.cmd` 文件并委托给 `cmd.exe`，但不会经过 `cmd.exe /c` 的引号解析

### 步骤 2：增强错误诊断

修改 [lark_cli.py:63-65](file:///d:/lark/devflow/intake/lark_cli.py#L63-L65)，在 `LarkCliError` 中包含可执行文件路径：

```python
if completed.returncode != 0:
    stderr = completed.stderr.strip() or completed.stdout.strip()
    raise LarkCliError(
        f"lark-cli 执行失败（{executable}）：{stderr}"
    )
```

这样下次出现类似错误时，可以立即看到 `shutil.which()` 解析到的完整路径，便于排查。

### 步骤 3：更新测试

更新 `tests/test_welcome_message.py` 和 `tests/test_pipeline_start.py` 中所有 mock `run_lark_cli_text` 或 `subprocess.run` 的测试用例，确保：
- 不再验证 `shell=True`
- 验证 `shell=False`（或默认值）
- 验证错误信息中包含可执行文件路径

### 步骤 4：验证修复

1. 运行 `uv run python -m pytest tests/test_welcome_message.py -q`
2. 运行 `uv run python -m pytest tests/test_pipeline_start.py -q`
3. 运行 `uv run python -m pytest tests/test_lark_cli.py -q`（如存在）
4. 运行完整测试套件 `uv run python -m pytest -q --basetemp .test-tmp\pytest-basetemp`
5. 手动验证：`uv run devflow start --once --timeout 10`，确认欢迎消息发送成功或给出更清晰的错误信息

## 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| `shell=False` 在某些 Windows 环境下无法执行 `.cmd` 文件 | 低 | 高 | `iter_lark_cli_event_stream()` 已长期使用 `shell=False` 运行稳定；若出问题，回退方案是显式使用 `cmd.exe /c` 并正确转义参数 |
| 移除 `shell=True` 后其他 lark-cli 命令失败 | 低 | 中 | 所有 lark-cli 命令都通过 `run_lark_cli_text()` 执行，统一修改后行为一致；完整测试套件覆盖 |
| 测试用例需要更新 | 中 | 低 | 仅需调整 mock 参数验证，不涉及逻辑变更 |

## 涉及文件

| 文件 | 变更类型 |
|------|---------|
| [devflow/intake/lark_cli.py](file:///d:/lark/devflow/intake/lark_cli.py) | 移除 `shell=True`，增强错误信息 |
| [tests/test_welcome_message.py](file:///d:/lark/tests/test_welcome_message.py) | 更新 mock 验证 |
| [tests/test_pipeline_start.py](file:///d:/lark/tests/test_pipeline_start.py) | 更新 mock 验证（如有） |
| [journey/design.md](file:///d:/lark/journey/design.md) | 更新 Windows subprocess 决策记录 |
