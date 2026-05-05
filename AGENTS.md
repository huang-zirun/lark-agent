# Project Instructions for Agents

## Working Rules

- **Use `uv` for Python**: prefer `uv pip install`, `uv run`, `uv venv` over pip/conda.
- **Use PowerShell**: all CLI operations use PowerShell syntax; avoid cmd.exe/Bash.
- **PowerShell Limitation**: PowerShell does not support `&&` syntax for chaining commands; use semicolon `;` or separate commands instead.
- **Use Standard Git Commit**: follow conventional commits format (`type(scope): subject`) with clear, descriptive messages; keep commits atomic and focused.
- **Clean Up Temporary Scripts**: delete any temporary scripts created for testing or validation purposes once verification is complete.

## Karpathy 编码原则

所有涉及代码编写、审查或重构的工作必须遵循以下四原则：

1. **编码前思考**：不要假设，不要隐藏困惑，呈现权衡。遇到歧义时先提问而非猜测；如果存在更简单的方案，说出来。
2. **简洁优先**：用最少的代码解决问题。不添加未要求的功能、抽象或"灵活性"。如果 200 行能写成 50 行，重写它。检验标准：资深工程师会觉得这过于复杂吗？
3. **精准修改**：只碰必须碰的，只清理自己造成的混乱。不"改进"相邻代码或格式，不重构没坏的东西，匹配现有风格。每行修改都应能追溯到用户请求。
4. **目标驱动执行**：定义可验证的成功标准，循环验证直到达成。将"添加验证"转化为"为无效输入写测试然后让它们通过"，将"修复 bug"转化为"写重现测试然后让它通过"。

对于琐碎任务（简单拼写修复、显然的一行改动），自行判断，不必走完整严谨流程。

## Journey memory

Use `journey/` as the shared project memory across agent sessions.

- Read `journey/design.md` first at the start of each session. It is the canonical snapshot of the project: current strategy, key design decisions, trade-offs, constraints, and scope.
- Use `journey/logs/` for chronological process notes, progress, experiments, and failed paths.
- Use `journey/research/` for research notes and background findings.
- Update `journey/design.md` whenever the effective understanding of the project changes. Do not leave important decisions or trade-offs only in logs.

For any new project, planning-focused request, or sufficiently complex task, start with a fresh plan and write it to `journey/plans/YYYY-MM-DD-{title}.md` before implementing. Treat files in `journey/plans/` as the canonical plans. As work progresses, record concise updates in `journey/logs/YYYY-MM-DD-{title}.md` using the same date and title convention. In chat, provide only a brief summary and the relevant file path(s).
