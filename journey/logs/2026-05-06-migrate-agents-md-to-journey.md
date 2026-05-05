# Migrate AGENTS.md to Journey System

## Summary

将 `d:\lark\AGENTS.md` 的内容整合到 journey 系统中，确保项目规范统一存储在 `journey/` 目录下。

## Changes Made

### 1. Updated `journey/design.md`

在文件开头添加了 **Working Rules** 部分：

- **Use `uv` for Python**: prefer `uv pip install`, `uv run`, `uv venv` over pip/conda.
- **Use PowerShell**: all CLI operations use PowerShell syntax; avoid cmd.exe/Bash.
- **PowerShell Limitation**: PowerShell does not support `&&` syntax for chaining commands; use semicolon `;` or separate commands instead.
- **Use Standard Git Commit**: follow conventional commits format (`type(scope): subject`) with clear, descriptive messages; keep commits atomic and focused.
- **Clean Up Temporary Scripts**: delete any temporary scripts created for testing or validation purposes once verification is complete.

同时更新了文件头部的 Last updated 日期。

## Rationale

根据 `journey/design.md` 的说明：

> Use `journey/` as the shared project memory across agent sessions.
> - Read `journey/design.md` first at the start of each session. It is the canonical snapshot of the project: current strategy, key design decisions, trade-offs, constraints, and scope.

AGENTS.md 中定义的 Working Rules 是项目的基础规范，应该被纳入 design.md 作为 canonical snapshot 的一部分。

## Files Modified

- `journey/design.md` - 添加 Working Rules 部分，更新日期

## Backward Compatibility

原始的 `d:\lark\AGENTS.md` 文件可以保留作为参考，但后续更新应优先修改 `journey/design.md`。
