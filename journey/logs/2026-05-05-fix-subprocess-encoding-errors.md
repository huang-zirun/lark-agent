# 修复 subprocess 编码错误导致 devflow start 崩溃

## 日期
2026-05-05

## 问题
`devflow start` 在 Windows 中文环境下执行代码生成阶段时崩溃，出现两个连锁错误：

1. **UnicodeDecodeError: 'gbk' codec can't decode byte 0xae** — `subprocess.run(text=True)` 未指定 `encoding`，Windows 默认使用 GBK 解码 PowerShell 输出，遇到无法解码的字节时异常。
2. **TypeError: 'NoneType' object is not subscriptable** — 错误 1 导致 `completed.stdout` 为 `None`，对 `None` 执行 `[-4000:]` 切片操作失败。

## 根因
`devflow/code/tools.py` 中 `powershell()` 和 `capture_git_diff()` 两个函数调用 `subprocess.run()` 时使用了 `text=True` 但未显式指定 `encoding` 参数。在 Windows 中文环境下，Python 默认使用系统编码 GBK，而 PowerShell/git 输出可能包含 GBK 无法解码的字节。

## 修复
在 `devflow/code/tools.py` 中：
- `powershell()`: 添加 `encoding="utf-8", errors="replace"` 参数，并将 `completed.stdout[-4000:]` 改为 `(completed.stdout or "")[-4000:]`
- `capture_git_diff()`: 同样添加 `encoding="utf-8", errors="replace"` 参数，并将 `completed.stdout` 改为 `(completed.stdout or "")`

此修复与项目中 `delivery/agent.py` 和 `intake/lark_cli.py` 已有的编码处理模式保持一致。

## 教训
在 Windows 中文环境下，所有 `subprocess.run(text=True)` 调用都必须显式指定 `encoding="utf-8"` 和 `errors="replace"`，否则会因系统默认 GBK 编码导致解码失败。对 `subprocess.run` 返回的 `stdout`/`stderr` 也应做 `None` 防御性检查。
