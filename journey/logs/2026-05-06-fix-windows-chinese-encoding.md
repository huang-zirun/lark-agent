# 2026-05-06 修复 Windows 中文乱码并恢复中文控制台消息

## 问题

`npm run dev` 启动后，bot 进程输出中文乱码：
```
[bot] 欢迎消息发送失败，lark-cli 执行失败，The system cannot find the file specified.
```

## 根因

Windows PowerShell 默认代码页为 GBK (CP936)，Python 的 `sys.stderr`/`sys.stdout` 跟随控制台代码页。当 Python 以 GBK 编码输出中文、而终端或 `concurrently` 以 UTF-8 解读时，产生乱码。

## 修复

### 1. 编码修复（根因）

- **PowerShell Profile**：在 `D:\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` 中添加 `$env:PYTHONUTF8 = "1"`，使所有新 PowerShell 会话中 Python 强制使用 UTF-8 模式。
- **package.json**：安装 `cross-env` 并在 `dev` 脚本中嵌入 `cross-env PYTHONUTF8=1`，确保 `npm run dev` 在任何环境下都能正确设置 Python UTF-8 模式。

### 2. 恢复中文消息（消除历史规避）

之前为规避 GBK 编码问题，部分控制台输出被刻意改为英文。编码问题修复后，将这些消息恢复为中文：

| 文件 | 修改数 | 说明 |
|------|--------|------|
| `devflow/pipeline.py` | 4 行 | `_print_no_default_chat_guidance()` 引导消息 |
| `devflow/cli.py` | 21 行 | 审批默认原因、轮询输出、doctor 状态、语义索引、主入口错误 |
| `devflow/api.py` | 5 行 | API 服务器启动信息 |
| `devflow/graph_runner.py` | 1 行 | LangGraph 入口缺失异常 |
| `devflow/semantic/parsers/__init__.py` | 3 行 | 解析超时消息 |

### 3. 同步更新测试

| 文件 | 修改数 |
|------|--------|
| `tests/test_welcome_message.py` | 3 处断言 |
| `tests/test_config.py` | 5 处断言 |

全部 26 个测试通过。

## 设计决策更新

在 `journey/design.md` 中新增 Windows UTF-8 编码强制策略的记录，并更新 Bot UX v2 决策（引导消息从英文恢复为中文）。
